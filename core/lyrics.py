from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import aiohttp

from core.yandex_client import TrackMetadata


LRCLIB_SEARCH_URL = "https://lrclib.net/api/search"


logger = logging.getLogger("yandex_to_navidrome.lyrics")


async def _fetch_best_lrclib_entry(track: TrackMetadata) -> Optional[dict]:
    params = {
        "track_name": track.title,
        "artist_name": ", ".join(track.artists) if track.artists else "",
    }
    if track.album:
        params["album_name"] = track.album
    if track.duration_ms:
        params["duration"] = track.duration_ms / 1000.0

    async with aiohttp.ClientSession() as session:
        async with session.get(LRCLIB_SEARCH_URL, params=params, timeout=15) as resp:
            if resp.status != 200:
                logger.debug("LRCLIB request failed", extra={"status": resp.status})
                return None
            data = await resp.json()

    if not isinstance(data, list) or not data:
        return None

    # Prefer entries with syncedLyrics present and closest duration.
    def _score(item: dict) -> tuple[int, float]:
        has_synced = 1 if item.get("syncedLyrics") else 0
        duration = float(item.get("duration") or 0.0)
        target = float(track.duration_ms or 0) / 1000.0
        return has_synced, -abs(duration - target)

    best = max(data, key=_score)
    if not best.get("syncedLyrics"):
        return None
    return best


async def generate_lrc_for_track(audio_path: Path, track: TrackMetadata) -> None:
    lrc_path = audio_path.with_suffix(".lrc")
    if lrc_path.exists():
        return

    entry = await _fetch_best_lrclib_entry(track)
    if not entry:
        logger.info(
            "no_lyrics_found",
            extra={"title": track.title, "artists": ", ".join(track.artists)},
        )
        return

    synced = entry.get("syncedLyrics")
    if not isinstance(synced, str) or not synced.strip():
        return

    lrc_path.write_text(synced.strip() + "\n", encoding="utf-8")

