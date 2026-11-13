"""Cloudinary over its REST API (TR-MED-01…03), on the shared httpx client.

Signing follows Cloudinary's rule: sort the parameters (excluding file, api_key, resource_type
and cloud_name), join as ``k=v&k=v``, append the API secret, SHA-1. Every asset lives under
``ws/{workspace_id}/{purpose}/`` so a workspace can only register its own uploads.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from socialhood.observability.logging import get_logger
from socialhood.settings import Settings

log = get_logger(__name__)

API = "https://api.cloudinary.com/v1_1"
ResourceType = Literal["image", "video", "raw"]
UNSIGNED_KEYS = frozenset({"file", "api_key", "resource_type", "cloud_name", "signature"})


class CloudinaryError(Exception):
    pass


@dataclass(frozen=True)
class StoredResource:
    public_id: str
    resource_type: str
    format: str | None
    secure_url: str
    bytes: int
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    tags: tuple[str, ...] = ()

    @classmethod
    def from_api(cls, body: dict[str, Any]) -> StoredResource:
        return cls(
            public_id=str(body["public_id"]),
            resource_type=str(body.get("resource_type", "image")),
            format=body.get("format"),
            secure_url=str(body["secure_url"]),
            bytes=int(body.get("bytes") or 0),
            width=body.get("width"),
            height=body.get("height"),
            duration_s=body.get("duration"),
            tags=tuple(str(t) for t in body.get("tags") or ()),
        )


def sign(params: dict[str, Any], api_secret: str) -> str:
    pairs = sorted(
        (k, v) for k, v in params.items() if k not in UNSIGNED_KEYS and v not in (None, "")
    )
    payload = "&".join(f"{k}={v}" for k, v in pairs)
    return hashlib.sha1((payload + api_secret).encode(), usedforsecurity=False).hexdigest()


def workspace_folder(workspace_id: uuid.UUID, purpose: str) -> str:
    return f"ws/{workspace_id}/{purpose}"


def in_workspace(public_id: str, workspace_id: uuid.UUID) -> bool:
    return public_id.startswith(f"ws/{workspace_id}/")


class Cloudinary:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self.http = http
        self.cloud = settings.cloudinary_cloud_name or ""
        self.api_key = settings.cloudinary_api_key or ""
        self.secret = (
            settings.cloudinary_api_secret.get_secret_value()
            if settings.cloudinary_api_secret
            else ""
        )

    @property
    def configured(self) -> bool:
        return bool(self.cloud and self.api_key and self.secret)

    def _require(self) -> None:
        if not self.configured:
            raise CloudinaryError("Cloudinary is not configured")

    def upload_signature(
        self,
        *,
        folder: str,
        resource_type: ResourceType,
        timestamp: int | None = None,
        tags: str | None = None,
        public_id: str | None = None,
        allowed_formats: Collection[str] = (),
    ) -> dict[str, Any]:
        """Parameters for a signed direct upload from the browser (TR-MED-01). ``tags`` is signed
        too, so the upload carries it and nothing else can: an AI app's one-time ticket
        (mcp/tools/media.py) is the tag ``mcp_upload_{id}``. ``public_id`` (the file's name inside
        ``folder``) is signed as well, so sending the same signature again replaces that one file
        instead of storing another. ``allowed_formats`` is signed so Cloudinary itself refuses any
        other file: on the raw endpoint a file otherwise keeps its own extension and is served as
        that type."""
        self._require()
        ts = timestamp or int(time.time())
        signed: dict[str, Any] = {"folder": folder, "timestamp": ts}
        if tags:
            signed["tags"] = tags
        if public_id:
            signed["public_id"] = public_id
        formats = ",".join(sorted(allowed_formats))
        if formats:
            signed["allowed_formats"] = formats
        return {
            "cloud_name": self.cloud,
            "api_key": self.api_key,
            "timestamp": ts,
            "folder": folder,
            **({"tags": tags} if tags else {}),
            **({"public_id": public_id} if public_id else {}),
            **({"allowed_formats": formats} if formats else {}),
            "signature": sign(signed, self.secret),
            "upload_url": f"{API}/{self.cloud}/{resource_type}/upload",
        }

    async def upload(
        self,
        file: bytes | str,
        *,
        folder: str,
        resource_type: ResourceType | Literal["auto"] = "auto",
        public_id: str | None = None,
        filename: str = "upload",
        tags: str | None = None,
    ) -> StoredResource:
        """Server-side upload of bytes or a fetchable URL (inbound media, TR-MED-03). A network
        failure stays an ``httpx.HTTPError``: the inbound copy retries on it
        (services/ingest_followups.py)."""
        self._require()
        params: dict[str, Any] = {"folder": folder, "timestamp": int(time.time())}
        if public_id:
            params["public_id"] = public_id
        if tags:
            params["tags"] = tags
        data = {**params, "api_key": self.api_key, "signature": sign(params, self.secret)}
        url = f"{API}/{self.cloud}/{resource_type}/upload"
        if isinstance(file, bytes):
            response = await self.http.post(url, data=data, files={"file": (filename, file)})
        else:
            response = await self.http.post(url, data={**data, "file": file})
        if response.status_code >= 400:
            log.warning("cloudinary_upload_failed", status_code=response.status_code)
            raise CloudinaryError(f"upload failed with HTTP {response.status_code}")
        return StoredResource.from_api(response.json())

    async def get_resource(
        self, public_id: str, resource_type: ResourceType
    ) -> StoredResource | None:
        """Admin API lookup of an uploaded asset; None when it does not exist."""
        self._require()
        try:
            response = await self.http.get(
                f"{API}/{self.cloud}/resources/{resource_type}/upload/{public_id}",
                auth=(self.api_key, self.secret),
            )
        except httpx.HTTPError as error:  # a timeout is a storage failure like any other
            raise CloudinaryError(f"lookup failed: {type(error).__name__}") from error
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise CloudinaryError(f"lookup failed with HTTP {response.status_code}")
        return StoredResource.from_api(response.json())

    async def eager(self, public_id: str, resource_type: ResourceType, eager: str) -> None:
        """Start rendering a derived version now (``{transformation}/{extension}``), in the
        background: Cloudinary answers at once and later serves that transformation's URL from
        the stored render instead of rendering it on the first fetch (Explicit API)."""
        self._require()
        params: dict[str, Any] = {
            "public_id": public_id,
            "type": "upload",
            "eager": eager,
            "eager_async": "true",
            "timestamp": int(time.time()),
        }
        data = {**params, "api_key": self.api_key, "signature": sign(params, self.secret)}
        response = await self.http.post(f"{API}/{self.cloud}/{resource_type}/explicit", data=data)
        if response.status_code >= 400:
            raise CloudinaryError(f"explicit failed with HTTP {response.status_code}")

    async def destroy(self, public_id: str, resource_type: ResourceType) -> None:
        self._require()
        params: dict[str, Any] = {"public_id": public_id, "timestamp": int(time.time())}
        data = {**params, "api_key": self.api_key, "signature": sign(params, self.secret)}
        url = f"{API}/{self.cloud}/{resource_type}/destroy"
        try:
            response = await self.http.post(url, data=data)
        except httpx.HTTPError as error:
            raise CloudinaryError(f"destroy failed: {type(error).__name__}") from error
        if response.status_code >= 400:
            raise CloudinaryError(f"destroy failed with HTTP {response.status_code}")
