from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from core.database import MigrationDB
from core.lyrics import generate_lrc_for_track
from core.slsk_client import SlskClient
from core.tagging import embed_tags
from util.utils import (
    DownloadError,
    build_album_directory,
    build_track_filename,
    configure_logging,
    download_cover_image,
    ensure_directory,
)
from core.yandex_client import TrackMetadata, fetch_failed_track_metadata, fetch_liked_tracks


app = typer.Typer(help="Migrate Yandex Music likes into a Navidrome library.")


@dataclass
class AppConfig:
    music_root: Path
    limit: Optional[int]
    concurrency: int
    download_timeout_seconds: int = 600
    max_download_retries: int = 3


def get_logger() -> logging.Logger:
    return logging.getLogger("yandex_to_navidrome")

async def process_single_track(
    track: TrackMetadata,
    cfg: AppConfig,
    db: MigrationDB,
    slsk_client: SlskClient,
    dry_run: bool,
) -> None:
    logger = get_logger()

    if await db.is_successful(track.track_id):
        logger.info(
            "track_already_migrated",
            extra={"track_id": track.track_id, "title": track.title},
        )
        return

    album_dir = build_album_directory(cfg.music_root, track)
    ensure_directory(album_dir)

    audio_dest = album_dir / build_track_filename(track, extension="mp3")

    if audio_dest.exists():
        logger.info(
            "destination_exists_skip",
            extra={"track_id": track.track_id, "path": str(audio_dest)},
        )
        await db.mark_success(track.track_id, str(audio_dest))
        return

    if dry_run:
        logger.info(
            "dry_run_plan",
            extra={
                "track_id": track.track_id,
                "title": track.title,
                "dest": str(audio_dest),
                "artists": ", ".join(track.artists),
                "album": track.album or "",
            },
        )
        return

    try:
        download_path, actual_extension = await slsk_client.download_track_with_retries(
            track=track,
            timeout_seconds=cfg.download_timeout_seconds,
            max_retries=cfg.max_download_retries,
        )
    except DownloadError as exc:
        logger.error(
            "download_failed",
            extra={"track_id": track.track_id, "error": str(exc)},
        )
        await db.mark_failed(track.track_id, str(exc))
        return

    final_audio_dest = album_dir / build_track_filename(
        track, extension=actual_extension
    )

    ensure_directory(final_audio_dest.parent)
    download_path.replace(final_audio_dest)

    cover_bytes = await download_cover_image(track)

    # Save album cover once per album.
    cover_path = album_dir / "album-cover.jpg"
    if cover_bytes and not cover_path.exists():
        cover_path.write_bytes(cover_bytes)

    try:
        embed_tags(final_audio_dest, track, cover_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "tagging_failed",
            extra={
                "track_id": track.track_id,
                "path": str(final_audio_dest),
                "error": str(exc),
            },
        )

    try:
        await generate_lrc_for_track(final_audio_dest, track)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "lyrics_failed",
            extra={"track_id": track.track_id, "error": str(exc)},
        )

    await db.mark_success(track.track_id, str(final_audio_dest))


async def run_sync_like_tracks(cfg: AppConfig, dry_run: bool) -> None:
    logger = get_logger()

    async with MigrationDB(cfg.music_root / "migration.db") as db, SlskClient() as slsk:
        liked_tracks = await fetch_liked_tracks(limit=cfg.limit)
        logger.info(
            "fetched_yandex_liked_tracks",
            extra={"count": len(liked_tracks), "limit": cfg.limit},
        )

        semaphore = asyncio.Semaphore(cfg.concurrency)

        async def worker(track: TrackMetadata) -> None:
            async with semaphore:
                await process_single_track(track, cfg, db, slsk, dry_run=dry_run)

        tasks = [worker(t) for t in liked_tracks]
        await asyncio.gather(*tasks)


async def run_retry_failed(cfg: AppConfig) -> None:
    logger = get_logger()

    async with MigrationDB(cfg.music_root / "migration.db") as db, SlskClient() as slsk:
        failed_ids = await db.get_failed_track_ids()
        if not failed_ids:
            logger.info("no_failed_tracks_to_retry")
            return

        logger.info("retrying_failed_tracks", extra={"count": len(failed_ids)})

        semaphore = asyncio.Semaphore(cfg.concurrency)

        async def worker(track_id: str) -> None:
            track = await fetch_failed_track_metadata(track_id)
            async with semaphore:
                await process_single_track(track, cfg, db, slsk, dry_run=False)

        tasks = [worker(tid) for tid in failed_ids]
        await asyncio.gather(*tasks)


def _build_config(
    music_root: Path, limit: Optional[int], concurrency: int, timeout_minutes: int
) -> AppConfig:
    return AppConfig(
        music_root=music_root,
        limit=limit,
        concurrency=concurrency,
        download_timeout_seconds=timeout_minutes * 60,
    )


def common_options(
    music_root: Path = typer.Option(
        ...,
        "--music-root",
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=True,
        resolve_path=True,
        help="Root folder of the Navidrome music library.",
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Limit the number of tracks to process."
    ),
    concurrency: int = typer.Option(
        3,
        "--concurrency",
        min=1,
        help="Number of concurrent downloads.",
    ),
    timeout_minutes: int = typer.Option(
        10,
        "--timeout-minutes",
        min=1,
        help="Per-track download timeout in minutes.",
    ),
) -> AppConfig:
    configure_logging(music_root / "migration.log")
    return _build_config(music_root, limit, concurrency, timeout_minutes)


@app.command("sync")
def sync_command(  # pragma: no cover - Typer CLI wrapper
    cfg: AppConfig = typer.Option(  # type: ignore[assignment]
        None, callback=common_options, is_eager=True
    ),
) -> None:
    """Synchronize all liked tracks from Yandex Music into Navidrome."""
    if cfg is None:
        raise typer.BadParameter("Configuration could not be built.")
    asyncio.run(run_sync_like_tracks(cfg, dry_run=False))


@app.command("dry-run")
def dry_run_command(  # pragma: no cover - Typer CLI wrapper
    cfg: AppConfig = typer.Option(  # type: ignore[assignment]
        None, callback=common_options, is_eager=True
    ),
) -> None:
    """Show what would be migrated without downloading anything."""
    if cfg is None:
        raise typer.BadParameter("Configuration could not be built.")
    asyncio.run(run_sync_like_tracks(cfg, dry_run=True))


@app.command("retry-failed")
def retry_failed_command(  # pragma: no cover - Typer CLI wrapper
    cfg: AppConfig = typer.Option(  # type: ignore[assignment]
        None, callback=common_options, is_eager=True
    ),
) -> None:
    """Retry previously failed downloads recorded in migration.db."""
    if cfg is None:
        raise typer.BadParameter("Configuration could not be built.")
    asyncio.run(run_retry_failed(cfg))


def main() -> None:  # pragma: no cover - entry point
    load_dotenv()
    os.environ.setdefault("PYTHONASYNCIODEBUG", "0")
    app()


if __name__ == "__main__":  # pragma: no cover - script entry
    main()
