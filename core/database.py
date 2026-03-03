from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import List

import aiosqlite


class MigrationDB:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def __aenter__(self) -> "MigrationDB":
        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS migrations (
                track_id   TEXT PRIMARY KEY,
                status     TEXT NOT NULL,
                dest_path  TEXT,
                error      TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        await self._conn.commit()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def _connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("MigrationDB is not initialized, use it as an async context manager.")
        return self._conn

    async def is_successful(self, track_id: str) -> bool:
        conn = self._connection
        async with conn.execute(
            "SELECT status FROM migrations WHERE track_id = ?", (track_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return bool(row and row[0] == "success")

    async def mark_success(self, track_id: str, dest_path: str) -> None:
        conn = self._connection
        now = _dt.datetime.utcnow().isoformat()
        await conn.execute(
            """
            INSERT INTO migrations (track_id, status, dest_path, error, updated_at)
            VALUES (?, 'success', ?, NULL, ?)
            ON CONFLICT(track_id) DO UPDATE SET
                status = 'success',
                dest_path = excluded.dest_path,
                error = NULL,
                updated_at = excluded.updated_at
            """,
            (track_id, dest_path, now),
        )
        await conn.commit()

    async def mark_failed(self, track_id: str, error: str) -> None:
        conn = self._connection
        now = _dt.datetime.utcnow().isoformat()
        await conn.execute(
            """
            INSERT INTO migrations (track_id, status, dest_path, error, updated_at)
            VALUES (?, 'failed', NULL, ?, ?)
            ON CONFLICT(track_id) DO UPDATE SET
                status = 'failed',
                error = excluded.error,
                updated_at = excluded.updated_at
            """,
            (track_id, error, now),
        )
        await conn.commit()

    async def get_failed_track_ids(self) -> List[str]:
        conn = self._connection
        async with conn.execute(
            "SELECT track_id FROM migrations WHERE status = 'failed'"
        ) as cursor:
            rows = await cursor.fetchall()
        return [row[0] for row in rows]

