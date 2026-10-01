"""Deleting a workspace's Cloudinary folder (T9.6; FR-ACC-05, §5.9).

Every upload lives under ``ws/{workspace_id}/`` (media/cloudinary.py): browser uploads, inbound
media and generated files alike. The purge deletes by that prefix with the Admin API, for each
resource type, following ``next_cursor`` while Cloudinary reports a partial deletion (it deletes
up to 1000 per call), then deletes the emptied folder (Cloudinary deletes a folder only once it is
empty; empty subfolders go with it). A folder Cloudinary doesn't know is already gone.

Deleting one account's data (C-067) deletes named files instead: the ones its messages own
(services/account_deletion.py decides which), by public id, up to 100 per call and per resource
type (DELETE /resources/{type}/upload?public_ids[]=…). A file Cloudinary doesn't know is already
gone; a public id outside the workspace's folder is never sent.

Without Cloudinary credentials nothing can have been uploaded, so there is nothing to delete.
Tests swap the purger with ``use_media_purger`` (no test reaches Cloudinary).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import NamedTuple, Protocol

import httpx

from socialhood.media.cloudinary import API, Cloudinary, CloudinaryError, in_workspace
from socialhood.observability.logging import get_logger
from socialhood.settings import Settings

log = get_logger(__name__)

RESOURCE_TYPES = ("image", "video", "raw")
MAX_PAGES = 200  # 200,000 files per type in one run; the purge job runs again for the rest
IDS_PER_CALL = 100  # Cloudinary's limit for public_ids[] in one delete


def workspace_prefix(workspace_id: uuid.UUID) -> str:
    return f"ws/{workspace_id}"


class StoredFile(NamedTuple):
    public_id: str
    resource_type: str


class MediaPurger(Protocol):
    async def delete_workspace_folder(self, workspace_id: uuid.UUID) -> None:
        """Delete every file under ``ws/{workspace_id}/`` and the folder; raise CloudinaryError
        when Cloudinary can't be reached or refuses, so the purge tries again."""
        ...

    async def delete_files(self, workspace_id: uuid.UUID, files: Sequence[StoredFile]) -> None:
        """Delete these files of the workspace (never one outside its folder); raise
        CloudinaryError when Cloudinary can't be reached or refuses, so the purge tries again."""
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

    async def delete_files(self, workspace_id: uuid.UUID, files: Sequence[StoredFile]) -> None:
        storage = self.cloudinary
        mine = [f for f in files if in_workspace(f.public_id, workspace_id)]
        if not storage.configured or not mine:
            return
        deleted = 0
        for resource_type in RESOURCE_TYPES:
            ids = [f.public_id for f in mine if f.resource_type == resource_type]
            for start in range(0, len(ids), IDS_PER_CALL):
                deleted += await self._delete_ids(resource_type, ids[start : start + IDS_PER_CALL])
        log.info("media_files_purged", workspace_id=str(workspace_id), files=deleted)

    async def _delete_ids(self, resource_type: str, public_ids: list[str]) -> int:
        storage = self.cloudinary
        response = await storage.http.delete(
            f"{API}/{storage.cloud}/resources/{resource_type}/upload",
            params=[("public_ids[]", public_id) for public_id in public_ids],
            auth=(storage.api_key, storage.secret),
        )
        if response.status_code >= 400:
            raise CloudinaryError(
                f"deleting {resource_type} files failed with HTTP {response.status_code}"
            )
        results = response.json().get("deleted") or {}
        return sum(1 for outcome in results.values() if outcome == "deleted")

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
