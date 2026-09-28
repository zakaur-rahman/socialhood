"""T3.7: signed uploads and asset registration (TR-MED-01, TR-MED-02). Cloudinary's Admin API is
mocked with respx on the same router as the fake Clerk."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.media.cloudinary import sign
from socialhood.settings import Settings
from tests.support.api import Clerk, sign_in

CLOUD = "socialhood-test"
API_KEY = "123456789012345"
API_SECRET = "cloudinary-test-secret"
RESOURCES = f"https://api.cloudinary.com/v1_1/{CLOUD}/resources"
MB = 1024 * 1024


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return api_settings.model_copy(
        update={
            "cloudinary_cloud_name": CLOUD,
            "cloudinary_api_key": API_KEY,
            "cloudinary_api_secret": SecretStr(API_SECRET),
        }
    )


async def owner(client: httpx.AsyncClient, clerk: Clerk) -> tuple[dict[str, str], str]:
    clerk_id, me = await sign_in(client, clerk)
    return clerk.headers(clerk_id), me["workspaces"][0]["id"]


def resource(public_id: str, **values: Any) -> dict[str, Any]:
    kind = values.pop("resource_type", "image")
    fmt = values.pop("format", "jpg")
    return {
        "public_id": public_id,
        "resource_type": kind,
        "format": fmt,
        "secure_url": f"https://res.cloudinary.com/{CLOUD}/{kind}/upload/v1/{public_id}"
        + (f".{fmt}" if fmt else ""),
        "bytes": 250_000,
        "width": 1080,
        "height": 1350,
        **values,
    }


async def register(
    client: httpx.AsyncClient, headers: dict[str, str], wid: str, public_id: str, kind: str
) -> httpx.Response:
    return await client.post(
        f"/v1/w/{wid}/media-assets",
        json={"public_id": public_id, "resource_type": kind},
        headers=headers,
    )


async def test_the_signature_is_for_the_workspace_folder(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    headers, wid = await owner(client, clerk)
    response = await client.post(
        f"/v1/w/{wid}/media-assets/upload-signature",
        json={"resource_type": "image", "purpose": "message"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["folder"] == f"ws/{wid}/message"
    assert body["cloud_name"] == CLOUD
    assert body["api_key"] == API_KEY
    assert body["upload_url"] == f"https://api.cloudinary.com/v1_1/{CLOUD}/image/upload"
    expected = sign({"folder": body["folder"], "timestamp": body["timestamp"]}, API_SECRET)
    assert body["signature"] == expected
    assert API_SECRET not in response.text


async def test_an_upload_in_the_workspace_folder_is_registered_once(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    headers, wid = await owner(client, clerk)
    public_id = f"ws/{wid}/message/abc123def456"
    route = clerk.router.get(f"{RESOURCES}/image/upload/{public_id}").respond(
        200, json=resource(public_id)
    )

    first = await register(client, headers, wid, public_id, "image")
    assert first.status_code == 201, first.text
    asset = first.json()
    assert asset["public_id"] == public_id
    assert asset["purpose"] == "message"
    assert asset["format"] == "jpg"
    assert asset["mime_type"] == "image/jpeg"
    assert asset["bytes"] == 250_000
    assert route.calls.last.request.headers["authorization"].startswith("Basic ")

    again = await register(client, headers, wid, public_id, "image")
    assert again.status_code == 201
    assert again.json()["id"] == asset["id"]
    assert route.call_count == 1
    async with engine.connect() as conn:
        count = await conn.scalar(text("SELECT count(*) FROM media_assets"))
    assert count == 1


async def test_an_asset_outside_the_workspace_folder_is_rejected(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    headers, wid = await owner(client, clerk)
    route = clerk.router.get(url__startswith=RESOURCES).respond(200, json={})
    for public_id in (
        f"ws/{uuid.uuid4()}/message/abc123",  # another workspace
        "samples/cloudinary-icon",  # not ours at all
        f"ws/{wid}/inbound/abc123",  # a server-only folder
        f"ws/{wid}/message/../../x",
    ):
        response = await register(client, headers, wid, public_id, "image")
        assert response.status_code == 422, (public_id, response.text)
        assert response.json()["code"] == "validation_error"
        assert response.json()["errors"][0]["field"] == "public_id"
    assert route.call_count == 0


@pytest.mark.parametrize(
    ("kind", "values", "detail"),
    [
        ("image", {"bytes": 8 * MB + 1}, "Images can be up to 8 MB."),
        ("image", {"format": "gif"}, None),
        ("video", {"format": "mp4", "bytes": 101 * MB}, "Videos can be up to 100 MB."),
        ("video", {"format": "mov", "duration": 90.5}, "Videos can be up to 90 seconds."),
        ("video", {"format": "avi"}, None),
        (
            "raw",
            {"format": None},
            "Posts use JPEG, PNG, WEBP or HEIC images, or MP4 or MOV video up to 90 seconds.",
        ),
    ],
)
async def test_files_over_the_limits_are_unsupported_media(
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    kind: str,
    values: dict[str, Any],
    detail: str | None,
) -> None:
    headers, wid = await owner(client, clerk)
    public_id = f"ws/{wid}/post/file1" + (".pdf" if kind == "raw" else "")
    clerk.router.get(f"{RESOURCES}/{kind}/upload/{public_id}").respond(
        200, json=resource(public_id, resource_type=kind, **values)
    )
    response = await register(client, headers, wid, public_id, kind)
    assert response.status_code == 415, response.text
    assert response.json()["code"] == "unsupported_media"
    if detail:
        assert response.json()["detail"] == detail
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM media_assets")) == 0


@pytest.mark.parametrize(
    ("kind", "values", "public_suffix"),
    [
        ("image", {"format": "heic", "bytes": 8 * MB}, ""),
        ("video", {"format": "mp4", "duration": 90.0, "bytes": 100 * MB}, ""),
        ("raw", {"format": None, "bytes": 20 * MB}, ".pdf"),
        ("image", {"format": "pdf", "bytes": 2 * MB}, ""),
        ("raw", {"format": None, "bytes": 100 * MB}, ".docx"),  # WhatsApp documents
        ("video", {"format": "m4a", "bytes": 3 * MB, "duration": 600.0}, ""),  # audio
        ("video", {"format": "webm", "bytes": 20 * MB, "duration": 180.0}, ""),  # DM video
    ],
)
async def test_files_within_the_limits_are_accepted(
    client: httpx.AsyncClient,
    clerk: Clerk,
    kind: str,
    values: dict[str, Any],
    public_suffix: str,
) -> None:
    headers, wid = await owner(client, clerk)
    public_id = f"ws/{wid}/message/file2{public_suffix}"
    clerk.router.get(f"{RESOURCES}/{kind}/upload/{public_id}").respond(
        200, json=resource(public_id, resource_type=kind, **values)
    )
    response = await register(client, headers, wid, public_id, kind)
    assert response.status_code == 201, response.text


async def test_an_upload_cloudinary_does_not_have_is_a_validation_error(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    headers, wid = await owner(client, clerk)
    public_id = f"ws/{wid}/message/missing1"
    clerk.router.get(f"{RESOURCES}/image/upload/{public_id}").respond(
        404, json={"error": {"message": "Resource not found"}}
    )
    response = await register(client, headers, wid, public_id, "image")
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "public_id"


async def test_a_cloudinary_outage_is_503(client: httpx.AsyncClient, clerk: Clerk) -> None:
    headers, wid = await owner(client, clerk)
    public_id = f"ws/{wid}/message/down1"
    clerk.router.get(f"{RESOURCES}/image/upload/{public_id}").respond(500)
    response = await register(client, headers, wid, public_id, "image")
    assert response.status_code == 503
    assert response.json()["code"] == "service_unavailable"


async def test_documents_for_messages_have_their_own_limit(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    headers, wid = await owner(client, clerk)
    public_id = f"ws/{wid}/message/big.pdf"
    clerk.router.get(f"{RESOURCES}/raw/upload/{public_id}").respond(
        200, json=resource(public_id, resource_type="raw", format=None, bytes=101 * MB)
    )
    response = await register(client, headers, wid, public_id, "raw")
    assert response.status_code == 415
    assert response.json()["detail"] == "Documents can be up to 100 MB."


@pytest.mark.parametrize(("status", "expected"), [(401, 503), (200, 201)])
async def test_a_pdf_the_storage_will_not_deliver_is_refused_with_the_fix(
    client: httpx.AsyncClient, clerk: Clerk, status: int, expected: int
) -> None:
    """Cloudinary blocks PDF delivery on new accounts; platforms then can't fetch the file."""
    headers, wid = await owner(client, clerk)
    public_id = f"ws/{wid}/message/brochure.pdf"
    body = resource(public_id, resource_type="raw", format=None)
    clerk.router.get(f"{RESOURCES}/raw/upload/{public_id}").respond(200, json=body)
    clerk.router.head(body["secure_url"]).respond(status)
    response = await register(client, headers, wid, public_id, "raw")
    assert response.status_code == expected, response.text
    if expected == 503:
        assert "Allow delivery of PDF and ZIP files" in response.json()["detail"]
