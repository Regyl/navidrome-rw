from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import List, Optional

from yandex_music import Client, Track


_TOKEN_ENV_VAR = "YANDEX_MUSIC_TOKEN"


@dataclass
class TrackMetadata:
    track_id: str
    title: str
    artists: List[str]
    album: Optional[str]
    album_artists: List[str]
    year: Optional[int]
    track_number: Optional[int]
    disc_number: Optional[int]
    duration_ms: Optional[int]
    cover_uri: Optional[str]


def _get_client() -> Client:
    token = os.getenv(_TOKEN_ENV_VAR)
    if not token:
        raise RuntimeError(
            f"Environment variable '{_TOKEN_ENV_VAR}' is not set. "
            "Set it to a valid Yandex Music access token. "
            "See https://yandex-music.readthedocs.io/en/main/token.html for details."
        )
    return Client(token).init()


def _build_metadata(track: Track) -> TrackMetadata:
    album = track.albums[0] if track.albums else None
    track_position = getattr(track, "track_position", None)

    return TrackMetadata(
        track_id=str(getattr(track, "id", "")),
        title=track.title,
        artists=[a.name for a in track.artists] if track.artists else [],
        album=album.title if album else None,
        album_artists=[a.name for a in album.artists] if album and album.artists else [],
        year=getattr(album, "year", None) if album else None,
        track_number=getattr(track_position, "index", None) if track_position else None,
        disc_number=getattr(track_position, "volume", None) if track_position else None,
        duration_ms=getattr(track, "duration_ms", None),
        cover_uri=getattr(track, "cover_uri", None) or (
            getattr(album, "cover_uri", None) if album else None
        ),
    )


async def fetch_liked_tracks(limit: Optional[int] = None) -> list[TrackMetadata]:
    def _sync_fetch() -> list[TrackMetadata]:
        client = _get_client()
        likes = client.users_likes_tracks()
        result: list[TrackMetadata] = []

        for idx, liked in enumerate(likes):
            if limit is not None and idx >= limit:
                break
            full_track = liked.fetch_track()
            result.append(_build_metadata(full_track))

        return result

    return await asyncio.to_thread(_sync_fetch)


async def fetch_failed_track_metadata(track_id: str) -> TrackMetadata:
    def _sync_fetch_single() -> TrackMetadata:
        client = _get_client()
        # yandex-music expects "trackId:albumId" but track_id here is the "real_id"
        # To keep it robust, we first try as-is, then fall back to users_likes_tracks lookup.
        try:
            tr = client.tracks([track_id])[0]
            return _build_metadata(tr)
        except Exception:
            likes = client.users_likes_tracks()
            for liked in likes:
                full_track = liked.fetch_track()
                real_id = getattr(full_track, "real_id", getattr(full_track, "id", None))
                if str(real_id) == str(track_id):
                    return _build_metadata(full_track)
            raise RuntimeError(f"Could not resolve failed track metadata for id={track_id!r}")

    return await asyncio.to_thread(_sync_fetch_single)

