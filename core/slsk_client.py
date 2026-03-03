from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Tuple

from aioslsk.client import SoulSeekClient
from aioslsk.search.model import SearchRequest, SearchResult
from aioslsk.settings import CredentialsSettings, Settings, SharesSettings

from util.utils import DownloadError
from core.yandex_client import TrackMetadata


_SLSK_USER_ENV = "SLSK_USERNAME"
_SLSK_PASS_ENV = "SLSK_PASSWORD"
_SLSK_DOWNLOAD_ENV = "SLSK_DOWNLOAD_DIR"


class SlskClient:
    """Thin async wrapper around aioslsk SoulSeekClient."""

    def __init__(self) -> None:
        username = os.getenv(_SLSK_USER_ENV)
        password = os.getenv(_SLSK_PASS_ENV)
        if not username or not password:
            raise RuntimeError(
                f"Soulseek credentials are not configured. "
                f"Set {_SLSK_USER_ENV} and {_SLSK_PASS_ENV} environment variables."
            )

        download_dir_env = os.getenv(_SLSK_DOWNLOAD_ENV)
        download_dir = Path(download_dir_env) if download_dir_env else Path.cwd() / "slsk_downloads"
        download_dir.mkdir(parents=True, exist_ok=True)

        self._settings = Settings(
            credentials=CredentialsSettings(username=username, password=password),
            shares=SharesSettings(download=str(download_dir), directories=[]),
        )
        self._client: SoulSeekClient | None = None

    async def __aenter__(self) -> "SlskClient":
        self._client = SoulSeekClient(self._settings)
        await self._client.start()
        await self._client.login()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if self._client is not None:
            await self._client.stop()
            self._client = None

    @property
    def _c(self) -> SoulSeekClient:
        if self._client is None:
            raise RuntimeError("SlskClient is not started, use it as an async context manager.")
        return self._client

    async def _search_best_result(self, track: TrackMetadata) -> SearchResult:
        query = f"{track.title} - {', '.join(track.artists) or 'Unknown'}"
        request: SearchRequest = await self._c.searches.search(query)

        # Wait a bit for results to come in.
        await asyncio.sleep(5)
        if not request.results:
            raise DownloadError(f"No Soulseek search results for query {query!r}")

        # Prefer results with free slots and highest avg speed, then smallest queue.
        def _score(res: SearchResult) -> tuple[int, int]:
            free = 1 if res.has_free_slots else 0
            return (free, res.avg_speed or 0)

        best = max(request.results, key=_score)
        return best

    async def _download_once(self, track: TrackMetadata) -> Tuple[Path, str]:
        from aioslsk.transfer.model import Transfer  # imported lazily to speed import time

        result = await self._search_best_result(track)
        if not result.shared_items:
            raise DownloadError("Best Soulseek result has no shared items.")

        file = result.shared_items[0]
        transfer: Transfer = await self._c.transfers.download(result.username, file.filename)

        # Wait until transfer is finalized.
        while not transfer.is_finalized():
            await asyncio.sleep(0.5)

        snapshot = transfer.progress_snapshot
        if snapshot.fail_reason:
            raise DownloadError(f"Soulseek transfer failed: {snapshot.fail_reason}")
        if not transfer.local_path:
            raise DownloadError("Soulseek transfer finished but local_path is missing.")

        path = Path(transfer.local_path)
        if not path.exists():
            raise DownloadError(f"Soulseek reported completed download but file is missing: {path}")

        ext = path.suffix.lstrip(".").lower() or "mp3"
        return path, ext

    async def download_track_with_retries(
        self,
        track: TrackMetadata,
        timeout_seconds: int,
        max_retries: int,
    ) -> Tuple[Path, str]:
        last_error: Exception | None = None

        for _ in range(max_retries):
            try:
                return await asyncio.wait_for(
                    self._download_once(track),
                    timeout=timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise DownloadError(str(last_error) if last_error else "Unknown download error")

