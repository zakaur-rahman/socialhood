"""Cloudinary over its REST API (TR-MED-01…03), on the shared httpx client.

Signing follows Cloudinary's rule: sort the parameters (excluding file, api_key, resource_type
and cloud_name), join as ``k=v&k=v``, append the API secret, SHA-1. Every asset lives under
``ws/{workspace_id}/{purpose}/`` so a workspace can only register its own uploads.
"""

from __future__ import annotations

import hashlib
import time
import uuid
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
        self, *, folder: str, resource_type: ResourceType, timestamp: int | None = None
    ) -> dict[str, Any]:
        """Parameters for a signed direct upload from the browser (TR-MED-01)."""
        self._require()
        ts = timestamp or int(time.time())
        return {
            "cloud_name": self.cloud,
            "api_key": self.api_key,
            "timestamp": ts,
            "folder": folder,
            "signature": sign({"folder": folder, "timestamp": ts}, self.secret),
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
    ) -> StoredResource:
        """Server-side upload of bytes or a fetchable URL (inbound media, TR-MED-03)."""
        self._require()
        params: dict[str, Any] = {"folder": folder, "timestamp": int(time.time())}
        if public_id:
            params["public_id"] = public_id
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
        response = await self.http.get(
            f"{API}/{self.cloud}/resources/{resource_type}/upload/{public_id}",
            auth=(self.api_key, self.secret),
        )
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise CloudinaryError(f"lookup failed with HTTP {response.status_code}")
        return StoredResource.from_api(response.json())

    async def destroy(self, public_id: str, resource_type: ResourceType) -> None:
        self._require()
        params: dict[str, Any] = {"public_id": public_id, "timestamp": int(time.time())}
        data = {**params, "api_key": self.api_key, "signature": sign(params, self.secret)}
        response = await self.http.post(f"{API}/{self.cloud}/{resource_type}/destroy", data=data)
        if response.status_code >= 400:
            raise CloudinaryError(f"destroy failed with HTTP {response.status_code}")
