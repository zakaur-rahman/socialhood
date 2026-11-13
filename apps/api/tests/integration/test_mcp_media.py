"""C-165 phase B: the media tools (start/finish_media_upload, import_media_from_url), the signed
upload of a ticket's one file, the SSRF refusals of the link import, the daily upload caps, the
cleanup of unfinished tickets, and the upload page's routes. Cloudinary is mocked with respx on the
fake Clerk's router."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from socialhood.billing.plans import ENTITLEMENTS
from socialhood.jobs.tasks.purge import clean_mcp_upload_tickets
from socialhood.mcp import limits
from socialhood.media.cloudinary import sign
from socialhood.media.purge import StoredFile
from socialhood.security import ssrf
from socialhood.services import media_assets
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.mcp import connect, error_of, make_key, structured
from tests.support.sending import Setup, clean_outbox, workspace_with_thread

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


def mock_fetch(clerk: Clerk, kind: str = "image", **values: Any) -> None:
    """Storage fetching a link: it answers with the name it was told to store the file under."""

    def fetched(request: httpx.Request) -> httpx.Response:
        form = parse_qs(request.content.decode())
        name = f"{form['folder'][0]}/{form['public_id'][0]}"
        return httpx.Response(200, json=stored(name, kind, **values))

    clerk.router.post(f"{API}/{kind}/upload").mock(side_effect=fetched)
    clerk.router.post(f"{API}/{kind}/explicit").respond(200, json={})


def file_id(setup: Setup, upload_id: str) -> str:
    """The one file a ticket can bring in: its name is part of the signature."""
    return f"ws/{setup.wid}/post/{uuid.UUID(upload_id).hex}"


async def used(app: FastAPI, setup: Setup, name: str) -> int:
    """What today's cap ``name`` has counted for the workspace."""
    return await limits.used(app.state.redis, name, uuid.UUID(setup.wid), datetime.now(UTC))


async def start(app: FastAPI, key: str, kind: str = "video", **args: Any) -> dict[str, Any]:
    return structured(await call(app, key, "start_media_upload", {"kind": kind, **args}))


@dataclass
class FakeStorage:
    """The media purger of the daily cleanup: what it was asked to delete, as (name, kind)."""

    deleted: list[tuple[str, str]] = field(default_factory=list)

    async def delete_workspace_folder(self, workspace_id: uuid.UUID) -> None:
        raise AssertionError("not used")

    async def delete_files(self, workspace_id: uuid.UUID, files: Sequence[StoredFile]) -> None:
        self.deleted.extend((f.public_id, f.resource_type) for f in files)

    async def list_tagged(self, workspace_id: uuid.UUID, tag: str) -> list[StoredFile]:
        raise AssertionError("a ticket with a signed file name is never listed by tag")


async def clean_stale_tickets(engine: AsyncEngine) -> tuple[FakeStorage, dict[str, int]]:
    """The daily cleanup, a day and more after every ticket expired."""
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE mcp_uploads SET expires_at = now() - interval '30 hours'"))
    storage = FakeStorage()
    return storage, await clean_mcp_upload_tickets(async_sessionmaker(engine), storage)


# ---------------------------------------------------------------- the signed upload


async def test_start_returns_a_signed_command_and_the_limits(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    started = await start(mcp_app, key, filename="edits/reel.mp4", bytes=40 * MB)
    upload_id = started["upload_id"]
    fields = started["fields"]
    assert fields["folder"] == f"ws/{setup.wid}/post"
    assert fields["tags"] == f"mcp_upload_{upload_id}"
    # The file's name is signed: sending the fields again replaces that file, it stores no more.
    assert fields["public_id"] == uuid.UUID(upload_id).hex
    assert fields["signature"] == sign(
        {
            "allowed_formats": fields["allowed_formats"],
            "folder": fields["folder"],
            "public_id": fields["public_id"],
            "tags": fields["tags"],
            "timestamp": fields["timestamp"],
        },
        SECRET,
    )
    assert SECRET not in str(started)
    curl = started["curl"]
    assert curl.startswith("curl -sS")
    assert '-F "file=@reel.mp4"' in curl
    assert f'-F "public_id={fields["public_id"]}"' in curl
    assert f'-F "tags=mcp_upload_{upload_id}"' in curl
    assert f'-F "allowed_formats={fields["allowed_formats"]}"' in curl
    assert curl.endswith(f"{API}/video/upload")
    assert "public_id" not in started["next_step"]  # finishing takes the upload_id alone
    assert started["upload_page_url"].endswith(f"/upload/{upload_id}")
    assert started["limits"]["max_duration_s"]["reel"] == 900
    assert started["limits"]["max_mb"] == 100
    [ticket] = await rows(engine, "SELECT * FROM mcp_uploads")
    assert (str(ticket["id"]), ticket["status"], ticket["kind"]) == (upload_id, "waiting", "video")
    assert ticket["public_id"] == file_id(setup, upload_id)
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


async def test_finish_registers_the_tickets_file(
    mcp_app: FastAPI, key: str, setup: Setup, clerk: Clerk, engine: AsyncEngine
) -> None:
    started = await start(mcp_app, key)
    upload_id = started["upload_id"]
    public_id = file_id(setup, upload_id)
    mock_lookup(clerk, public_id, "video")

    args = {"upload_id": upload_id, "idempotency_key": "finish-0001"}
    done = structured(await call(mcp_app, key, "finish_media_upload", args))
    assert (done["status"], done["type"], done["duration_s"]) == ("uploaded", "video", 20.0)
    assert done["media_id"]
    [asset] = await rows(engine, "SELECT * FROM media_assets")
    assert (str(asset["id"]), asset["purpose"]) == (done["media_id"], "post")
    assert asset["public_id"] == public_id
    assert (await rows(engine, "SELECT * FROM mcp_uploads"))[0]["status"] == "uploaded"
    explicit = [c for c in clerk.router.calls if c.request.url.path.endswith("/video/explicit")]
    assert len(explicit) == 1  # the eager H.264 render started
    lookups = [c for c in clerk.router.calls if "/resources/" in c.request.url.path]
    assert len(lookups) == 1  # storage is asked once: the library registers what finish read

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


async def test_finish_takes_the_file_from_the_ticket_never_from_the_caller(
    client: httpx.AsyncClient,
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    clerk: Clerk,
    engine: AsyncEngine,
) -> None:
    upload_id = (await start(mcp_app, key))["upload_id"]
    # A file's name is not an argument any more: another file can't be passed off as the ticket's.
    named = error_of(
        await call(
            mcp_app,
            key,
            "finish_media_upload",
            {"upload_id": upload_id, "public_id": f"ws/{setup.wid}/post/other1"},
        )
    )
    assert named["code"] == "validation_error"
    assert named["field_errors"][0]["field"] == "public_id"
    clerk.router.get(f"{API}/resources/video/upload/{file_id(setup, upload_id)}").respond(404)
    waiting = error_of(await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id}))
    assert waiting["code"] == "conflict"
    assert "No file has arrived" in waiting["message"]
    assert await rows(engine, "SELECT 1 FROM media_assets") == []
    missing = error_of(
        await call(mcp_app, key, "finish_media_upload", {"upload_id": str(uuid.uuid4())})
    )
    assert missing["code"] == "not_found"
    # Another workspace's ticket, a real one, is not found: to finish and to read.
    other = await workspace_with_thread(client, clerk, engine, email="other@example.com")
    theirs = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO mcp_uploads (id, workspace_id, kind, status, public_id, expires_at) "
                "VALUES (:id, :w, 'video', 'waiting', :p, :at)"
            ),
            {
                "id": theirs,
                "w": other.wid,
                "p": f"ws/{other.wid}/post/{theirs.hex}",
                "at": datetime.now(UTC) + timedelta(minutes=30),
            },
        )
    for name in ("finish_media_upload", "get_media_upload"):
        error = error_of(await call(mcp_app, key, name, {"upload_id": str(theirs)}))
        assert error["code"] == "not_found", name
    [ticket] = await rows(engine, "SELECT status FROM mcp_uploads WHERE id = :i", i=theirs)
    assert ticket["status"] == "waiting"


async def test_a_file_over_a_limit_is_rejected_with_the_reason(
    mcp_app: FastAPI, key: str, setup: Setup, clerk: Clerk, engine: AsyncEngine
) -> None:
    upload_id = (await start(mcp_app, key))["upload_id"]
    mock_lookup(clerk, file_id(setup, upload_id), "video", duration=1000.0)
    result = structured(await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id}))
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
    error = error_of(await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id}))
    assert error["code"] == "conflict"
    assert "expired" in error["message"]


async def test_the_daily_upload_cap(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    clerk: Clerk,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(ENTITLEMENTS["mcp_uploads_daily"], "max", 1)
    upload_id = (await start(mcp_app, key))["upload_id"]
    mock_lookup(clerk, file_id(setup, upload_id), "video")
    structured(await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id}))
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
    monkeypatch.setitem(ENTITLEMENTS["mcp_upload_mb_daily"], "max", 4)
    upload_id = (await start(mcp_app, key))["upload_id"]
    mock_lookup(clerk, file_id(setup, upload_id), "video")  # 5 MB
    error = error_of(await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id}))
    assert error["code"] == "quota_exceeded"
    assert error["entitlement"] == "mcp_upload_mb_daily"
    assert await used(mcp_app, setup, limits.UPLOADS) == 0  # the file's place came back


async def test_the_caps_are_given_back_when_registering_fails_in_any_way(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    clerk: Clerk,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload_id = (await start(mcp_app, key))["upload_id"]
    mock_lookup(clerk, file_id(setup, upload_id), "video")

    async def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("the connection dropped")  # not an ApiError

    monkeypatch.setattr(media_assets, "register", broken)
    error = error_of(await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id}))
    assert error["code"] == "internal"
    assert await used(mcp_app, setup, limits.UPLOADS) == 0
    assert await used(mcp_app, setup, limits.UPLOAD_MB) == 0


async def test_a_replayed_signature_names_the_same_one_file(
    client: httpx.AsyncClient,
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    clerk: Clerk,
    engine: AsyncEngine,
) -> None:
    """A ticket's signed fields sent again replace its one file, and finishing again counts
    nothing more."""
    started = await start(mcp_app, key)
    upload_id = started["upload_id"]
    page = await client.get(f"/v1/w/{setup.wid}/mcp-uploads/{upload_id}", headers=setup.headers)
    # A fresh signature for the same ticket still names the same file.
    assert page.json()["upload"]["public_id"] == started["fields"]["public_id"]
    mock_lookup(clerk, file_id(setup, upload_id), "video")
    first = structured(await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id}))
    second = structured(await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id}))
    assert second["media_id"] == first["media_id"]
    assert len(await rows(engine, "SELECT 1 FROM media_assets")) == 1
    assert await used(mcp_app, setup, limits.UPLOADS) == 1
    assert await used(mcp_app, setup, limits.UPLOAD_MB) == 5


async def test_a_file_already_in_the_library_is_linked_without_counting_again(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    """A finish that failed after the library took the file (or one running at the same moment):
    the next finish links the ticket and leaves the caps as they are."""
    upload_id = (await start(mcp_app, key))["upload_id"]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO media_assets (workspace_id, public_id, resource_type, purpose, "
                "format, bytes, width, height, secure_url) VALUES (:w, :p, 'video', 'post', "
                "'mp4', 1000, 1080, 1920, 'https://res.cloudinary.com/x/video/upload/a.mp4')"
            ),
            {"w": setup.wid, "p": file_id(setup, upload_id)},
        )
    done = structured(await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id}))
    [asset] = await rows(engine, "SELECT id FROM media_assets")
    assert (done["status"], done["media_id"]) == ("uploaded", str(asset["id"]))
    assert await used(mcp_app, setup, limits.UPLOADS) == 0
    [ticket] = await rows(engine, "SELECT status, media_asset_id FROM mcp_uploads")
    assert (ticket["status"], ticket["media_asset_id"]) == ("uploaded", asset["id"])


async def test_a_workspace_holds_at_most_twenty_unfinished_uploads(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    async with engine.begin() as conn:  # twenty that expired an hour ago and were never finished
        await conn.execute(
            text(
                "INSERT INTO mcp_uploads (workspace_id, kind, status, expires_at) "
                "SELECT :w, 'video', 'waiting', now() - interval '1 hour' "
                "FROM generate_series(1, 20)"
            ),
            {"w": setup.wid},
        )
    error = error_of(await call(mcp_app, key, "start_media_upload", {"kind": "video"}))
    assert error["code"] == "conflict"
    assert "never finished" in error["message"]
    assert len(await rows(engine, "SELECT 1 FROM mcp_uploads")) == 20
    # One of them finished or rejected leaves room again.
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE mcp_uploads SET status = 'rejected' "
                "WHERE id = (SELECT id FROM mcp_uploads LIMIT 1)"
            )
        )
    assert (await start(mcp_app, key))["upload_id"]


async def test_cleanup_deletes_an_unfinished_tickets_one_file_as_every_kind(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    upload_id = (await start(mcp_app, key, kind="image"))["upload_id"]
    storage, counts = await clean_stale_tickets(engine)
    name = file_id(setup, upload_id)
    # An image ticket's fields also work on the video and raw endpoints: all three are deleted.
    assert storage.deleted == [(name, "image"), (name, "video"), (name, "raw")]
    assert (counts["tickets"], counts["failed"]) == (1, 0)
    assert await rows(engine, "SELECT 1 FROM mcp_uploads") == []


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
    """The preview, then the confirmed call; a preview's refusal is the answer."""
    first = await call(app, key, "import_media_from_url", {"url": url, **args})
    if first.is_error:
        return first
    token = structured(first)["confirmation_token"]
    return await call(
        app,
        key,
        "import_media_from_url",
        {"url": url, **args, "confirmed": True, "confirmation_token": token},
    )


async def test_an_import_preview_reaches_nothing_and_names_the_host(
    mcp_app: FastAPI,
    key: str,
    clerk: Clerk,
    dns: dict[str, list[str]],
    engine: AsyncEngine,
) -> None:
    route = clerk.router.route(host=PUBLIC_HOST).respond(200)
    url = "https://cdn.example.com/photo.jpg"
    preview = structured(await call(mcp_app, key, "import_media_from_url", {"url": url}))
    assert (preview["preview"], preview["status"]) == (True, "preview")
    assert preview["source_host"] == "cdn.example.com"
    assert route.call_count == 0
    assert await rows(engine, "SELECT 1 FROM mcp_uploads") == []
    refused = error_of(
        await call(mcp_app, key, "import_media_from_url", {"url": url, "confirmed": True})
    )
    assert refused["field_errors"][0]["field"] == "confirmation_token"
    assert route.call_count == 0


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
    mock_fetch(clerk, "image", width=1080, height=1350)
    result = structured(
        await import_url(mcp_app, key, "https://cdn.example.com/photo.jpg", kind="image")
    )
    assert (result["status"], result["type"]) == ("uploaded", "image")
    upload = next(c for c in clerk.router.calls if c.request.url.path.endswith("/image/upload"))
    body = upload.request.content.decode()
    assert "file=https%3A%2F%2Fcdn.example.com%2Fphoto.jpg" in body  # the checked final address
    assert "tags=mcp_upload_" in body
    [ticket] = await rows(engine, "SELECT id, status, kind, public_id FROM mcp_uploads")
    assert (ticket["status"], ticket["kind"]) == ("uploaded", "image")
    assert f"public_id={ticket['id'].hex}" in body  # stored under the ticket's one name
    [asset] = await rows(engine, "SELECT public_id FROM media_assets")
    assert asset["public_id"] == ticket["public_id"] == f"ws/{setup.wid}/post/{ticket['id'].hex}"
    # What storage answered is what gets registered: it isn't asked again.
    assert not [c for c in clerk.router.calls if "/resources/" in c.request.url.path]


async def test_an_import_that_fails_after_storage_took_the_file_leaves_a_ticket_for_the_cleanup(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    clerk: Clerk,
    dns: dict[str, list[str]],
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(ENTITLEMENTS["mcp_upload_mb_daily"], "max", 4)
    # The link declares no size, so only storage's answer shows it is over what is left today.
    clerk.router.get(f"https://{PUBLIC_HOST}/big.mp4").respond(
        200, headers={"content-type": "video/mp4"}
    )
    mock_fetch(clerk, "video")  # 5 MB
    error = error_of(await import_url(mcp_app, key, "https://cdn.example.com/big.mp4"))
    assert (error["code"], error["entitlement"]) == ("quota_exceeded", "mcp_upload_mb_daily")
    assert await rows(engine, "SELECT 1 FROM media_assets") == []
    assert await used(mcp_app, setup, limits.UPLOADS) == 0
    # The ticket outlives the failed call, so the daily cleanup finds the file storage holds.
    [ticket] = await rows(engine, "SELECT id, status, public_id FROM mcp_uploads")
    assert ticket["status"] == "waiting"
    assert ticket["public_id"] == f"ws/{setup.wid}/post/{ticket['id'].hex}"
    storage, counts = await clean_stale_tickets(engine)
    assert storage.deleted == [(ticket["public_id"], kind) for kind in ("image", "video", "raw")]
    assert counts["tickets"] == 1
    assert await rows(engine, "SELECT 1 FROM mcp_uploads") == []


async def test_storage_timing_out_on_an_import_is_a_rejected_ticket(
    mcp_app: FastAPI,
    key: str,
    clerk: Clerk,
    dns: dict[str, list[str]],
    engine: AsyncEngine,
) -> None:
    clerk.router.get(f"https://{PUBLIC_HOST}/slow.jpg").respond(
        200, headers={"content-type": "image/jpeg"}
    )
    clerk.router.post(f"{API}/image/upload").mock(side_effect=httpx.ReadTimeout("slow"))
    result = structured(await import_url(mcp_app, key, "https://cdn.example.com/slow.jpg"))
    assert result["status"] == "rejected"
    assert "couldn't fetch" in result["problems"][0]
    # The ticket is kept: storage may still finish the fetch, into this ticket's one file.
    [ticket] = await rows(engine, "SELECT status, public_id FROM mcp_uploads")
    assert ticket["status"] == "rejected"
    assert ticket["public_id"]
    assert await rows(engine, "SELECT 1 FROM media_assets") == []


async def test_an_import_over_what_is_left_today_is_refused_before_storage_fetches_it(
    mcp_app: FastAPI,
    key: str,
    clerk: Clerk,
    dns: dict[str, list[str]],
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(ENTITLEMENTS["mcp_upload_mb_daily"], "max", 4)
    clerk.router.get(f"https://{PUBLIC_HOST}/big.mp4").respond(
        200, headers={"content-type": "video/mp4", "content-length": str(5 * MB)}
    )
    error = error_of(await import_url(mcp_app, key, "https://cdn.example.com/big.mp4"))
    assert (error["code"], error["entitlement"]) == ("quota_exceeded", "mcp_upload_mb_daily")
    assert not [c for c in clerk.router.calls if "cloudinary" in str(c.request.url)]
    assert await rows(engine, "SELECT 1 FROM mcp_uploads") == []


async def test_a_link_to_amplychat_itself_is_refused(
    mcp_app: FastAPI, key: str, engine: AsyncEngine
) -> None:
    # The MCP app under test is served at http://api.test (tests/support/mcp.py).
    error = error_of(
        await call(mcp_app, key, "import_media_from_url", {"url": "https://api.test/v1/a.jpg"})
    )
    assert error["code"] == "validation_error"
    assert error["field_errors"][0]["field"] == "url"
    assert "Amplychat itself" in error["field_errors"][0]["message"]
    assert await rows(engine, "SELECT 1 FROM mcp_uploads") == []


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
    assert ticket["upload"]["public_id"] == uuid.UUID(upload_id).hex
    assert ticket["upload"]["signature"] == sign(
        {
            "allowed_formats": ticket["upload"]["allowed_formats"],
            "folder": ticket["upload"]["folder"],
            "public_id": ticket["upload"]["public_id"],
            "tags": ticket["upload"]["tags"],
            "timestamp": ticket["upload"]["timestamp"],
        },
        SECRET,
    )
    mock_lookup(clerk, file_id(setup, upload_id), "video")
    # The page sends no file name: the API reads the ticket's own.
    done = await client.post(f"{base}/complete", headers=setup.headers)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "uploaded"
    assert done.json()["upload"] is None
    # The AI app sees it through the tool.
    polled = structured(await call(mcp_app, key, "get_media_upload", {"upload_id": upload_id}))
    assert polled["status"] == "uploaded"
    assert polled["media_id"] == done.json()["media_asset_id"]
    finished = structured(await call(mcp_app, key, "finish_media_upload", {"upload_id": upload_id}))
    assert finished["media_id"] == polled["media_id"]
    missing = await client.get(
        f"/v1/w/{setup.wid}/mcp-uploads/{uuid.uuid4()}", headers=setup.headers
    )
    assert missing.status_code == 404
