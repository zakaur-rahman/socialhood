"""C-165 phase B: the media tools (start/finish_media_upload, import_media_from_url), the signed
upload's verification, the SSRF refusals of the link import, the daily upload caps, and the upload
page's routes. Cloudinary is mocked with respx on the fake Clerk's router."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing.plans import ENTITLEMENTS
from socialhood.media.cloudinary import sign
from socialhood.security import ssrf
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.mcp import connect, error_of, make_key, structured
from tests.support.sending import Setup, clean_outbox

CLOUD = "socialhood-test"
SECRET = "cloudinary-test-secret"
API = f"https://api.cloudinary.com/v1_1/{CLOUD}"
MB = 1024 * 1024
PUBLIC_HOST = "93.184.216.34"


@pytest.fixture(autouse=True)
def _outbox() -> Any:
    yield from clean_outbox()


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return api_settings.model_copy(
        update={
            "cloudinary_cloud_name": CLOUD,
            "cloudinary_api_key": "123456789012345",
            "cloudinary_api_secret": SecretStr(SECRET),
        }
    )


@pytest.fixture
def setup(mcp_setup: Setup) -> Setup:
    return mcp_setup


@pytest.fixture
async def key(client: httpx.AsyncClient, setup: Setup) -> str:
    made, _ = await make_key(client, setup, "media:write", "posts:read")
    return made


async def call(app: FastAPI, key: str, name: str, args: dict[str, Any]) -> Any:
    async with connect(app, key) as mcp:
        return await mcp.call_tool(name, args)


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


def stored(public_id: str, kind: str = "video", **values: Any) -> dict[str, Any]:
    fmt = values.pop("format", "mp4" if kind == "video" else "jpg")
    return {
        "public_id": public_id,
        "resource_type": kind,
        "format": fmt,
        "secure_url": f"https://res.cloudinary.com/{CLOUD}/{kind}/upload/v1/{public_id}.{fmt}",
        "bytes": 5 * MB,
        "width": 1080,
        "height": 1920,
        "duration": 20.0,
        **values,
    }


def mock_lookup(clerk: Clerk, public_id: str, kind: str, **values: Any) -> None:
    clerk.router.get(f"{API}/resources/{kind}/upload/{public_id}").respond(
        200, json=stored(public_id, kind, **values)
    )
    clerk.router.post(f"{API}/{kind}/explicit").respond(200, json={})
    clerk.router.post(f"{API}/{kind}/destroy").respond(200, json={"result": "ok"})


async def start(app: FastAPI, key: str, kind: str = "video", **args: Any) -> dict[str, Any]:
    return structured(await call(app, key, "start_media_upload", {"kind": kind, **args}))


# ---------------------------------------------------------------- the signed upload


async def test_start_returns_a_signed_command_and_the_limits(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    started = await start(mcp_app, key, filename="edits/reel.mp4", bytes=40 * MB)
    upload_id = started["upload_id"]
    fields = started["fields"]
    assert fields["folder"] == f"ws/{setup.wid}/post"
    assert fields["tags"] == f"mcp_upload_{upload_id}"
    assert fields["signature"] == sign(
        {"folder": fields["folder"], "tags": fields["tags"], "timestamp": fields["timestamp"]},
        SECRET,
    )
    assert SECRET not in str(started)
    curl = started["curl"]
    assert curl.startswith("curl -sS")
    assert '-F "file=@reel.mp4"' in curl
    assert f'-F "tags=mcp_upload_{upload_id}"' in curl
    assert curl.endswith(f"{API}/video/upload")
    assert started["upload_page_url"].endswith(f"/upload/{upload_id}")
    assert started["limits"]["max_duration_s"]["reel"] == 900
    assert started["limits"]["max_mb"] == 100
    [ticket] = await rows(engine, "SELECT * FROM mcp_uploads")
    assert (str(ticket["id"]), ticket["status"], ticket["kind"]) == (upload_id, "waiting", "video")
    waiting = structured(await call(mcp_app, key, "get_media_upload", {"upload_id": upload_id}))
    assert waiting["status"] == "waiting"


async def test_start_refuses_a_file_over_the_limits_early(mcp_app: FastAPI, key: str) -> None:
    big = error_of(
        await call(mcp_app, key, "start_media_upload", {"kind": "video", "bytes": 101 * MB})
    )
    assert big["field_errors"][0] == {
        "field": "bytes",
        "message": "Videos can be up to 100 MB.",
    }
    long = error_of(
        await call(mcp_app, key, "start_media_upload", {"kind": "video", "duration_s": 1000})
    )
    assert long["field_errors"][0]["message"] == "Videos can be up to 15 minutes."
    huge_image = error_of(
        await call(mcp_app, key, "start_media_upload", {"kind": "image", "bytes": 9 * MB})
    )
    assert huge_image["field_errors"][0]["message"] == "Images can be up to 8 MB."


async def test_finish_registers_a_file_uploaded_with_the_ticket(
    mcp_app: FastAPI, key: str, setup: Setup, clerk: Clerk, engine: AsyncEngine
) -> None:
    started = await start(mcp_app, key)
    upload_id = started["upload_id"]
    public_id = f"ws/{setup.wid}/post/abc123"
    mock_lookup(clerk, public_id, "video", tags=[f"mcp_upload_{upload_id}"])

    args = {"upload_id": upload_id, "public_id": public_id, "idempotency_key": "finish-0001"}
    done = structured(await call(mcp_app, key, "finish_media_upload", args))
    assert (done["status"], done["type"], done["duration_s"]) == ("uploaded", "video", 20.0)
    assert done["media_id"]
    [asset] = await rows(engine, "SELECT * FROM media_assets")
    assert (str(asset["id"]), asset["purpose"]) == (done["media_id"], "post")
    assert (await rows(engine, "SELECT * FROM mcp_uploads"))[0]["status"] == "uploaded"
    explicit = [c for c in clerk.router.calls if c.request.url.path.endswith("/video/explicit")]
    assert len(explicit) == 1  # the eager H.264 render started

    again = structured(await call(mcp_app, key, "finish_media_upload", args))
    assert again == {**done, "duplicate_of_previous_call": True}  # same key, same result
    other = structured(
        await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id})
    )  # no key: the ticket itself is finished once
    assert other["media_id"] == done["media_id"]
    assert len(await rows(engine, "SELECT 1 FROM media_assets")) == 1
    polled = structured(await call(mcp_app, key, "get_media_upload", {"upload_id": upload_id}))
    assert (polled["status"], polled["media_id"]) == ("uploaded", done["media_id"])
    audit = await rows(engine, "SELECT 1 FROM audit_events WHERE action = 'media.uploaded'")
    assert len(audit) == 1


async def test_a_file_without_this_tickets_tag_is_refused(
    mcp_app: FastAPI, key: str, setup: Setup, clerk: Clerk, engine: AsyncEngine
) -> None:
    upload_id = (await start(mcp_app, key))["upload_id"]
    other = f"ws/{setup.wid}/post/other1"
    mock_lookup(clerk, other, "video", tags=["mcp_upload_" + str(uuid.uuid4())])
    refused = error_of(
        await call(
            mcp_app, key, "finish_media_upload", {"upload_id": upload_id, "public_id": other}
        )
    )
    assert refused["code"] == "validation_error"
    assert refused["field_errors"][0]["field"] == "public_id"
    assert await rows(engine, "SELECT 1 FROM media_assets") == []
    foreign = error_of(
        await call(
            mcp_app,
            key,
            "finish_media_upload",
            {"upload_id": upload_id, "public_id": f"ws/{uuid.uuid4()}/post/x1"},
        )
    )
    assert foreign["field_errors"][0]["field"] == "public_id"
    waiting = error_of(await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id}))
    assert waiting["code"] == "conflict"
    assert "No file has arrived" in waiting["message"]
    missing = error_of(
        await call(mcp_app, key, "finish_media_upload", {"upload_id": str(uuid.uuid4())})
    )
    assert missing["code"] == "not_found"


async def test_a_file_over_a_limit_is_rejected_with_the_reason(
    mcp_app: FastAPI, key: str, setup: Setup, clerk: Clerk, engine: AsyncEngine
) -> None:
    upload_id = (await start(mcp_app, key))["upload_id"]
    public_id = f"ws/{setup.wid}/post/long1"
    mock_lookup(clerk, public_id, "video", tags=[f"mcp_upload_{upload_id}"], duration=1000.0)
    result = structured(
        await call(
            mcp_app,
            key,
            "finish_media_upload",
            {"upload_id": upload_id, "public_id": public_id},
        )
    )
    assert result["status"] == "rejected"
    assert result["media_id"] is None
    assert result["problems"] == ["Videos can be up to 15 minutes."]
    assert await rows(engine, "SELECT 1 FROM media_assets") == []
    destroyed = [c for c in clerk.router.calls if c.request.url.path.endswith("/destroy")]
    assert len(destroyed) == 1  # the unregistered file isn't kept
    polled = structured(await call(mcp_app, key, "get_media_upload", {"upload_id": upload_id}))
    assert (polled["status"], polled["reason"]) == ("rejected", result["problems"][0])


async def test_an_expired_ticket_cannot_be_finished(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    upload_id = (await start(mcp_app, key))["upload_id"]
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE mcp_uploads SET expires_at = :at"),
            {"at": datetime.now(UTC) - timedelta(minutes=1)},
        )
    error = error_of(
        await call(
            mcp_app,
            key,
            "finish_media_upload",
            {"upload_id": upload_id, "public_id": f"ws/{setup.wid}/post/late1"},
        )
    )
    assert error["code"] == "conflict"
    assert "expired" in error["message"]


async def test_the_daily_upload_cap(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    clerk: Clerk,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(ENTITLEMENTS["mcp_uploads_daily"], "pro", 1)
    upload_id = (await start(mcp_app, key))["upload_id"]
    public_id = f"ws/{setup.wid}/post/cap1"
    mock_lookup(clerk, public_id, "video", tags=[f"mcp_upload_{upload_id}"])
    structured(
        await call(
            mcp_app, key, "finish_media_upload", {"upload_id": upload_id, "public_id": public_id}
        )
    )
    error = error_of(await call(mcp_app, key, "start_media_upload", {"kind": "video"}))
    assert (error["code"], error["entitlement"], error["limit"]) == (
        "quota_exceeded",
        "mcp_uploads_daily",
        1,
    )


async def test_the_daily_upload_megabytes(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    clerk: Clerk,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(ENTITLEMENTS["mcp_upload_mb_daily"], "pro", 4)
    upload_id = (await start(mcp_app, key))["upload_id"]
    public_id = f"ws/{setup.wid}/post/big1"
    mock_lookup(clerk, public_id, "video", tags=[f"mcp_upload_{upload_id}"])  # 5 MB
    error = error_of(
        await call(
            mcp_app, key, "finish_media_upload", {"upload_id": upload_id, "public_id": public_id}
        )
    )
    assert error["code"] == "quota_exceeded"
    assert error["entitlement"] == "mcp_upload_mb_daily"


# ---------------------------------------------------------------- the link import


@pytest.fixture
def dns(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Name resolution without the network: a host name maps to the addresses set here."""
    table: dict[str, list[str]] = {"cdn.example.com": [PUBLIC_HOST]}

    async def resolve(host: str, port: int) -> list[str]:
        return table.get(host, [])

    monkeypatch.setattr(ssrf, "resolve_host", resolve)
    return table


async def import_url(app: FastAPI, key: str, url: str, **args: Any) -> Any:
    return await call(app, key, "import_media_from_url", {"url": url, **args})


async def test_an_imported_image_lands_in_the_library(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    clerk: Clerk,
    dns: dict[str, list[str]],
    engine: AsyncEngine,
) -> None:
    clerk.router.get(f"https://{PUBLIC_HOST}/photo.jpg").respond(
        200, headers={"content-type": "image/jpeg", "content-length": str(2 * MB)}
    )
    public_id = f"ws/{setup.wid}/post/imp123"
    clerk.router.post(f"{API}/image/upload").respond(
        200, json=stored(public_id, "image", tags=["x"], width=1080, height=1350)
    )
    mock_lookup_ticket: dict[str, Any] = {}

    def lookup(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=stored(public_id, "image", **mock_lookup_ticket))

    clerk.router.get(f"{API}/resources/image/upload/{public_id}").mock(side_effect=lookup)
    result = structured(
        await import_url(mcp_app, key, "https://cdn.example.com/photo.jpg", kind="image")
    )
    assert (result["status"], result["type"]) == ("uploaded", "image")
    upload = next(c for c in clerk.router.calls if c.request.url.path.endswith("/image/upload"))
    body = upload.request.content.decode()
    assert "file=https%3A%2F%2Fcdn.example.com%2Fphoto.jpg" in body  # the checked final address
    assert "tags=mcp_upload_" in body
    [ticket] = await rows(engine, "SELECT status, kind FROM mcp_uploads")
    assert (ticket["status"], ticket["kind"]) == ("uploaded", "image")
    assert len(await rows(engine, "SELECT 1 FROM media_assets")) == 1


@pytest.mark.parametrize(
    ("url", "field_message"),
    [
        ("http://cdn.example.com/a.jpg", "Use an https:// link"),
        ("https://127.0.0.1/a.jpg", "private network"),
        ("https://[::1]/a.jpg", "private network"),
        ("https://169.254.169.254/latest/meta-data", "private network"),
        ("https://10.0.0.5/a.jpg", "private network"),
        ("https://user:pw@cdn.example.com/a.jpg", "user name and password"),
        ("https://internal.example.com/a.jpg", "private network"),
    ],
)
async def test_links_into_private_networks_are_refused(
    mcp_app: FastAPI,
    key: str,
    clerk: Clerk,
    dns: dict[str, list[str]],
    engine: AsyncEngine,
    url: str,
    field_message: str,
) -> None:
    dns["internal.example.com"] = ["10.1.2.3"]  # a public-looking name resolving privately
    route = clerk.router.route(
        url__regex=r"^https?://(10\.|127\.|169\.254\.|\[::1\]|user:)"
    ).respond(200)
    error = error_of(await import_url(mcp_app, key, url))
    assert error["code"] == "validation_error"
    assert field_message in error["field_errors"][0]["message"]
    assert error["field_errors"][0]["field"] == "url"
    assert route.call_count == 0  # nothing was fetched
    assert not [c for c in clerk.router.calls if "cloudinary" in str(c.request.url)]
    assert await rows(engine, "SELECT 1 FROM mcp_uploads") == []


async def test_a_redirect_to_a_private_address_is_refused(
    mcp_app: FastAPI, key: str, clerk: Clerk, dns: dict[str, list[str]]
) -> None:
    clerk.router.get(f"https://{PUBLIC_HOST}/a.jpg").respond(
        302, headers={"location": "https://10.0.0.1/secret.jpg"}
    )
    private = clerk.router.get("https://10.0.0.1/secret.jpg").respond(
        200, headers={"content-type": "image/jpeg"}
    )
    error = error_of(await import_url(mcp_app, key, "https://cdn.example.com/a.jpg"))
    assert error["code"] == "validation_error"
    assert "redirects to an address that can't be used" in error["field_errors"][0]["message"]
    assert private.call_count == 0
    # A redirect that stays public is followed, to the final address.
    clerk.router.get(f"https://{PUBLIC_HOST}/b.jpg").respond(
        302, headers={"location": "http://10.0.0.1/c.jpg"}
    )
    again = error_of(await import_url(mcp_app, key, "https://cdn.example.com/b.jpg"))
    assert again["code"] == "validation_error"


@pytest.mark.parametrize(
    ("headers", "message"),
    [
        ({"content-type": "text/html"}, "isn't a JPEG"),
        ({"content-type": "application/pdf"}, "isn't a JPEG"),
        ({"content-type": "image/gif"}, "isn't a JPEG"),
        ({"content-type": "image/jpeg", "content-length": str(9 * MB)}, "up to 8 MB"),
        ({"content-type": "video/mp4", "content-length": str(101 * MB)}, "up to 100 MB"),
    ],
)
async def test_the_wrong_type_or_size_is_refused_before_storage_fetches_it(
    mcp_app: FastAPI,
    key: str,
    clerk: Clerk,
    dns: dict[str, list[str]],
    engine: AsyncEngine,
    headers: dict[str, str],
    message: str,
) -> None:
    clerk.router.get(f"https://{PUBLIC_HOST}/file").respond(200, headers=headers)
    error = error_of(await import_url(mcp_app, key, "https://cdn.example.com/file"))
    assert error["code"] == "unsupported_media"
    assert message in error["message"]
    assert not [c for c in clerk.router.calls if "cloudinary" in str(c.request.url)]
    assert await rows(engine, "SELECT 1 FROM mcp_uploads") == []


async def test_a_link_that_errors_or_has_the_wrong_kind(
    mcp_app: FastAPI, key: str, clerk: Clerk, dns: dict[str, list[str]]
) -> None:
    clerk.router.get(f"https://{PUBLIC_HOST}/gone").respond(404)
    error = error_of(await import_url(mcp_app, key, "https://cdn.example.com/gone"))
    assert error["code"] == "validation_error"
    assert "error (404)" in str(error["field_errors"])
    clerk.router.get(f"https://{PUBLIC_HOST}/clip.mp4").respond(
        200, headers={"content-type": "video/mp4"}
    )
    wrong = error_of(
        await import_url(mcp_app, key, "https://cdn.example.com/clip.mp4", kind="image")
    )
    assert wrong["field_errors"][0]["field"] == "kind"


# ---------------------------------------------------------------- the upload page's routes


async def test_the_upload_page_reads_and_completes_a_ticket(
    client: httpx.AsyncClient,
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    clerk: Clerk,
    engine: AsyncEngine,
) -> None:
    upload_id = (await start(mcp_app, key))["upload_id"]
    base = f"/v1/w/{setup.wid}/mcp-uploads/{upload_id}"
    ticket = (await client.get(base, headers=setup.headers)).json()
    assert ticket["status"] == "waiting"
    assert ticket["upload"]["tags"] == f"mcp_upload_{upload_id}"
    assert ticket["upload"]["signature"] == sign(
        {
            "folder": ticket["upload"]["folder"],
            "tags": ticket["upload"]["tags"],
            "timestamp": ticket["upload"]["timestamp"],
        },
        SECRET,
    )
    public_id = f"ws/{setup.wid}/post/page1"
    mock_lookup(clerk, public_id, "video", tags=[f"mcp_upload_{upload_id}"])
    done = await client.post(
        f"{base}/complete", json={"public_id": public_id}, headers=setup.headers
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "uploaded"
    assert done.json()["upload"] is None
    # The AI app sees it through the tool, without a public_id.
    polled = structured(await call(mcp_app, key, "get_media_upload", {"upload_id": upload_id}))
    assert polled["status"] == "uploaded"
    assert polled["media_id"] == done.json()["media_asset_id"]
    finished = structured(await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id}))
    assert finished["media_id"] == polled["media_id"]
    missing = await client.get(
        f"/v1/w/{setup.wid}/mcp-uploads/{uuid.uuid4()}", headers=setup.headers
    )
    assert missing.status_code == 404
