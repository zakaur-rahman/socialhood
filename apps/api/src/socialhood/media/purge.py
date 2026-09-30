"""Deleting a workspace's Cloudinary folder (T9.6; FR-ACC-05, §5.9).

Every upload lives under ``ws/{workspace_id}/`` (media/cloudinary.py): browser uploads, inbound
media and generated files alike. The purge deletes by that prefix with the Admin API, for each
resource type, following ``next_cursor`` while Cloudinary reports a partial deletion (it deletes
up to 1000 per call), then deletes the emptied folder (Cloudinary deletes a folder only once it is
empty; empty subfolders go with it). A folder Cloudinary doesn't know is already gone.

Without Cloudinary credentials nothing can have been uploaded, so there is nothing to delete.
Tests swap the purger with ``use_media_purger`` (no test reaches Cloudinary).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

import httpx

from socialhood.media.cloudinary import API, Cloudinary, CloudinaryError
from socialhood.observability.logging import get_logger
from socialhood.settings import Settings

log = get_logger(__name__)

RESOURCE_TYPES = ("image", "video", "raw")
MAX_PAGES = 200  # 200,000 files per type in one run; the purge job runs again for the rest


def workspace_prefix(workspace_id: uuid.UUID) -> str:
    return f"ws/{workspace_id}"


class MediaPurger(Protocol):
    async def delete_workspace_folder(self, workspace_id: uuid.UUID) -> None:
        """Delete every file under ``ws/{workspace_id}/`` and the folder; raise CloudinaryError
        when Cloudinary can't be reached or refuses, so the purge tries again."""
        ...


class CloudinaryPurger:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self.cloudinary = Cloudinary(http, settings)

    async def delete_workspace_folder(self, workspace_id: uuid.UUID) -> None:
        storage = self.cloudinary
        if not storage.configured:
            log.info("media_purge_skipped", workspace_id=str(workspace_id), reason="unconfigured")
            return
        prefix = workspace_prefix(workspace_id)
        deleted = 0
        for resource_type in RESOURCE_TYPES:
            deleted += await self._delete_prefix(resource_type, f"{prefix}/")
        await self._delete_folder(prefix)
        log.info("media_purged", workspace_id=str(workspace_id), files=deleted)

    async def _delete_prefix(self, resource_type: str, prefix: str) -> int:
        storage = self.cloudinary
        url = f"{API}/{storage.cloud}/resources/{resource_type}/upload"
        cursor: str | None = None
        deleted = 0
        for _ in range(MAX_PAGES):
            params = {"prefix": prefix, **({"next_cursor": cursor} if cursor else {})}
            response = await storage.http.delete(
                url, params=params, auth=(storage.api_key, storage.secret)
            )
            if response.status_code >= 400:
                raise CloudinaryError(
                    f"deleting {resource_type} files failed with HTTP {response.status_code}"
                )
            body = response.json()
            deleted += len(body.get("deleted") or {})
            cursor = body.get("next_cursor")
            if not body.get("partial") or not cursor:
                return deleted
        raise CloudinaryError(f"more {resource_type} files remain; the purge continues later")

    async def _delete_folder(self, folder: str) -> None:
        storage = self.cloudinary
        response = await storage.http.delete(
            f"{API}/{storage.cloud}/folders/{folder}", auth=(storage.api_key, storage.secret)
        )
        if response.status_code == 404:
            return  # never created, or already deleted
        if response.status_code >= 400:
            raise CloudinaryError(f"deleting the folder failed with HTTP {response.status_code}")


_override: list[MediaPurger] = []


def get_media_purger(http: httpx.AsyncClient, settings: Settings) -> MediaPurger:
    return _override[-1] if _override else CloudinaryPurger(http, settings)


@contextmanager
def use_media_purger(purger: MediaPurger) -> Iterator[MediaPurger]:
    """Tests: every get_media_purger() in the block returns ``purger``."""
    _override.append(purger)
    try:
        yield purger
    finally:
        _override.pop()
