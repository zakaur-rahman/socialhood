"""GR-27: Google Sheets sync. Done when a capture appears as a row within a minute (the fake Google
here). Plus the OAuth callback and its nonce, the mapping, the header row, disconnecting, retries
with the webhook backoff, plain failure reasons and reconnecting, the plan and the roles."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.google.client import GoogleError
from socialhood.google.fake import FakeGoogle
from socialhood.security.crypto import cipher_for
from socialhood.services import sheets
from socialhood.services.automations.runtime import Outcome
from socialhood.services.sending import Delivery
from socialhood.services.webhooks import delivery
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.automations import make_automation
from tests.support.ingest import jobs
from tests.support.notify_team import make_user
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

BASE = "/integrations/google-sheets"


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def connect(ws: Ws, client: httpx.AsyncClient) -> dict[str, Any]:
    """The whole OAuth round trip on the fake Google: connect, the callback, complete."""
    started = await ws.ok("POST", f"{BASE}/connect")
    query = parse_qs(urlsplit(started["authorize_url"]).query)
    callback = await client.get(
        "/v1/oauth/google/callback",
        params={"code": query["code"][0], "state": query["state"][0]},
    )
    assert callback.status_code == 303, callback.text
    target = urlsplit(callback.headers["location"])
    assert target.path.endswith("/settings/integrations")
    nonce = parse_qs(target.query)["google"][0]
    return await ws.ok("POST", f"{BASE}/complete", json={"nonce": nonce})


# ---------------------------------------------------------------- the API


async def test_free_is_told_to_upgrade_and_an_agent_is_refused(ws: Ws, engine: AsyncEngine) -> None:
    status = await ws.ok("GET", BASE)
    assert (status["available"], status["entitled"], status["connected"]) == (True, False, False)
    assert [c["field"] for c in status["columns"]][:3] == ["contact_name", "username", "platform"]

    refused = await ws.call("POST", f"{BASE}/connect")
    assert (refused.status_code, refused.json()["entitlement"]) == (402, "sheets_sync")
    assert refused.json()["detail"] == "Google Sheets sync is part of Pro."

    await set_plan(engine, ws.wid, "pro")
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w"),
            {"w": ws.wid},
        )
    for method, path in [
        ("GET", BASE),
        ("POST", f"{BASE}/connect"),
        ("POST", f"{BASE}/test"),
        ("DELETE", BASE),
    ]:
        assert (await ws.call(method, path)).status_code == 403, (method, path)


async def test_connect_stores_the_credential_encrypted_and_never_returns_it(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, fake_google: FakeGoogle
) -> None:
    await set_plan(engine, ws.wid, "pro")
    status = await connect(ws, client)

    assert (status["connected"], status["status"], status["google_email"]) == (
        True,
        "active",
        "owner@example.com",
    )
    assert status["sheet"] is None
    assert "fake-refresh" not in json.dumps(status)
    [stored] = await rows(engine, "SELECT credential_enc, scopes FROM google_connections")
    assert b"fake-refresh" not in bytes(stored["credential_enc"])  # encrypted at rest
    assert "https://www.googleapis.com/auth/drive.file" in stored["scopes"]
    assert any(name == "exchange_code" for name, _ in fake_google.calls)


async def test_the_nonce_works_once_and_only_in_the_workspace_that_started_it(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await set_plan(engine, ws.wid, "pro")
    started = await ws.ok("POST", f"{BASE}/connect")
    query = parse_qs(urlsplit(started["authorize_url"]).query)
    callback = await client.get(
        "/v1/oauth/google/callback", params={"code": query["code"][0], "state": query["state"][0]}
    )
    nonce = parse_qs(urlsplit(callback.headers["location"]).query)["google"][0]
    await ws.ok("POST", f"{BASE}/complete", json={"nonce": nonce})
    again = await ws.call("POST", f"{BASE}/complete", json={"nonce": nonce})
    assert again.status_code == 404
    assert again.json()["detail"] == sheets.CONNECT_EXPIRED
    # The state is single-use too.
    replay = await client.get(
        "/v1/oauth/google/callback", params={"code": query["code"][0], "state": query["state"][0]}
    )
    assert replay.headers["location"].endswith("/app?error=state_invalid")


async def test_a_forged_state_and_a_refusal_at_google(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await set_plan(engine, ws.wid, "pro")
    forged = await client.get("/v1/oauth/google/callback", params={"code": "x", "state": "nope"})
    assert forged.status_code == 303
    assert forged.headers["location"].endswith("/app?error=state_invalid")
    started = await ws.ok("POST", f"{BASE}/connect")
    state = parse_qs(urlsplit(started["authorize_url"]).query)["state"][0]
    denied = await client.get(
        "/v1/oauth/google/callback", params={"error": "access_denied", "state": state}
    )
    assert denied.headers["location"].endswith("/settings/integrations?error=access_denied")
    assert (await ws.ok("GET", BASE))["connected"] is False


async def test_an_instagram_state_is_not_a_google_state(
    ws: Ws, client: httpx.AsyncClient, redis: Redis
) -> None:
    await redis.set(
        "oauth:ig-state",
        json.dumps(
            {"user_id": ws.user_id, "workspace_id": ws.wid, "slug": "x", "platform": "instagram"}
        ),
    )
    response = await client.get(
        "/v1/oauth/google/callback", params={"code": "x", "state": "ig-state"}
    )
    assert response.headers["location"].endswith("/app?error=state_invalid")


async def test_create_a_sheet_map_the_columns_and_send_a_test_row(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, fake_google: FakeGoogle
) -> None:
    await set_plan(engine, ws.wid, "pro")
    await ws.ok(
        "POST", "/contact-fields", 201, json={"key": "city", "label": "City", "type": "text"}
    )
    assert (await ws.call("POST", f"{BASE}/sheet", json={})).status_code == 409  # not connected
    await connect(ws, client)
    status = await ws.ok("POST", f"{BASE}/sheet", 201, json={"title": "My leads"})
    sheet = status["sheet"]
    assert (sheet["title"], sheet["tab"]) == ("My leads", "Leads")
    assert await fake_google.header(sheet["spreadsheet_id"]) == [
        "Name",
        "Username",
        "Platform",
        "Email",
        "Phone",
        "Automation",
        "Captured at",
        "Consent",
    ]
    assert {"field": "field:city", "label": "City", "custom": True} in status["fields"]

    mapped = await ws.ok(
        "PUT",
        f"{BASE}/mapping",
        json={
            "columns": [
                {"field": "email", "header": "Mail"},
                {"field": "field:city", "header": "Town"},
                {"field": "contact_name", "header": "Who"},
            ]
        },
    )
    assert [c["header"] for c in mapped["columns"]] == ["Mail", "Town", "Who"]
    assert await fake_google.header(sheet["spreadsheet_id"]) == ["Mail", "Town", "Who"]

    sent = await ws.ok("POST", f"{BASE}/test")
    assert sent == {"ok": True}
    assert await fake_google.rows(sheet["spreadsheet_id"]) == [
        ["test@example.com", "", "Test lead"]
    ]
    assert (await ws.ok("GET", BASE))["last_success_at"] is not None


async def test_the_mapping_is_checked(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await set_plan(engine, ws.wid, "pro")
    await connect(ws, client)
    unknown = await ws.call(
        "PUT", f"{BASE}/mapping", json={"columns": [{"field": "field:nothing", "header": "X"}]}
    )
    assert unknown.status_code == 422
    assert unknown.json()["errors"][0]["field"] == "columns.0.field"
    twice = await ws.call(
        "PUT",
        f"{BASE}/mapping",
        json={"columns": [{"field": "email", "header": "A"}, {"field": "email", "header": "B"}]},
    )
    assert twice.status_code == 422
    assert twice.json()["errors"][0]["field"] == "columns.1.field"
    empty = await ws.call("PUT", f"{BASE}/mapping", json={"columns": []})
    assert empty.status_code == 422
    # Before anything is saved, the default columns are shown.
    assert len((await ws.ok("GET", BASE))["columns"]) == len(sheets.FIELDS)


async def test_an_existing_sheet_is_used_only_if_google_lets_the_app_see_it(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, fake_google: FakeGoogle
) -> None:
    await set_plan(engine, ws.wid, "pro")
    await connect(ws, client)
    link = "https://docs.google.com/spreadsheets/d/existing-sheet-id-1234/edit"
    refused = await ws.call("PUT", f"{BASE}/sheet", json={"link": link})
    assert refused.status_code == 422
    assert refused.json()["errors"][0] == {"field": "link", "message": sheets.LINK_UNREADABLE}
    notasheet = await ws.call("PUT", f"{BASE}/sheet", json={"link": "https://example.com"})
    assert notasheet.json()["errors"][0]["message"] == sheets.LINK_INVALID

    await fake_google.add_sheet("existing-sheet-id-1234", "Customers")
    chosen = await ws.ok("PUT", f"{BASE}/sheet", json={"link": link})
    assert chosen["sheet"]["title"] == "Customers"
    # Theirs: no header row is written, then or when the mapping changes.
    await ws.ok("PUT", f"{BASE}/mapping", json={"columns": [{"field": "email", "header": "Mail"}]})
    assert await fake_google.header("existing-sheet-id-1234") == []


async def test_a_test_row_says_why_google_refused_it(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, fake_google: FakeGoogle
) -> None:
    await set_plan(engine, ws.wid, "pro")
    await connect(ws, client)
    assert (await ws.call("POST", f"{BASE}/test")).status_code == 409  # no sheet yet
    created = await ws.ok("POST", f"{BASE}/sheet", 201, json={})
    await fake_google.delete_sheet(created["sheet"]["spreadsheet_id"])
    gone = await ws.call("POST", f"{BASE}/test")
    assert (gone.status_code, gone.json()["detail"]) == (409, sheets.REASONS[sheets.SHEET_GONE])


async def test_revoked_access_marks_the_connection_for_reconnecting(
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    fake_google: FakeGoogle,
    api_settings: Settings,
) -> None:
    await set_plan(engine, ws.wid, "pro")
    await connect(ws, client)
    await ws.ok("POST", f"{BASE}/sheet", 201, json={})
    [conn] = await rows(engine, "SELECT credential_enc FROM google_connections")
    cipher = cipher_for(tuple(api_settings.token_encryption_keys))
    await fake_google.revoke_access(cipher.decrypt(bytes(conn["credential_enc"])))

    refused = await ws.call("POST", f"{BASE}/test")
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        sheets.REASONS[sheets.ACCESS_REMOVED],
    )
    status = await ws.ok("GET", BASE)
    assert (status["status"], status["last_error"]) == (
        "needs_reconnect",
        sheets.REASONS[sheets.ACCESS_REMOVED],
    )
    again = await ws.call("POST", f"{BASE}/test")
    assert again.json()["detail"] == sheets.NEEDS_RECONNECT

    # Reconnecting makes it work again, with the same sheet.
    reconnected = await connect(ws, client)
    assert (reconnected["status"], reconnected["sheet"] is not None) == ("active", True)
    assert (await ws.ok("POST", f"{BASE}/test")) == {"ok": True}


async def test_disconnect_revokes_and_removes_everything(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, fake_google: FakeGoogle
) -> None:
    await set_plan(engine, ws.wid, "pro")
    await connect(ws, client)
    await ws.ok("POST", f"{BASE}/sheet", 201, json={})
    await ws.ok("DELETE", BASE, 204)
    status = await ws.ok("GET", BASE)
    assert (status["connected"], status["sheet"]) == (False, None)
    assert await rows(engine, "SELECT id FROM google_connections") == []
    assert any(name == "revoke" for name, _ in fake_google.calls)
    await ws.ok("DELETE", BASE, 204)  # nothing to remove is fine


async def test_google_not_being_set_up_is_said_plainly(ws: Ws, engine: AsyncEngine) -> None:
    await set_plan(engine, ws.wid, "pro")
    from socialhood.google import registry

    registry._override.clear()  # the real client, whose OAuth client isn't set up in tests
    try:
        status = await ws.ok("GET", BASE)
        assert status["available"] is False
        refused = await ws.call("POST", f"{BASE}/connect")
        assert (refused.status_code, refused.json()["detail"]) == (503, sheets.NOT_CONFIGURED)
    finally:
        registry._override.append(FakeGoogle())  # the autouse fixture pops it


# ---------------------------------------------------------------- a capture becomes a row


@pytest.fixture
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def world(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    clean_db: None,
    queue: None,
    _outbox: None,
) -> AsyncIterator[World]:
    async with platform_deps(api_settings, monkeypatch) as deps:
        yield await make_world(engine, redis, deps)


async def execute(world: World, sql: str, **params: Any) -> None:
    async with world.engine.begin() as conn:
        await conn.execute(text(sql), params)


def ref() -> str:
    return f"99{uuid.uuid4().int % 10**13:013d}"


async def connect_world(
    world: World,
    fake: FakeGoogle,
    *,
    mapping: list[dict[str, str]] | None = None,
    plan: str = "pro",
) -> str:
    """A connection with a sheet, as the API would leave it; returns the sheet's id."""
    await world.plan(plan)
    grant = await fake.exchange_code("fake-code:owner@example.com")
    access = await fake.access_token(grant.refresh_token)
    columns = mapping or [c.model_dump() for c in sheets.DEFAULT_COLUMNS]
    info = await fake.create_spreadsheet(access, "Leads", [c["header"] for c in columns])
    await execute(
        world,
        "INSERT INTO google_connections (workspace_id, google_email, credential_enc, scopes,"
        " status, connected_at, spreadsheet_id, spreadsheet_title, spreadsheet_url, sheet_tab,"
        " sheet_created, mapping) VALUES (:w, 'owner@example.com', :c, '{}', 'active', now(),"
        " :s, :t, :u, :tab, true, CAST(:m AS jsonb))",
        w=world.wid,
        c=world.deps.cipher.encrypt(grant.refresh_token),
        s=info.spreadsheet_id,
        t=info.title,
        u=info.url,
        tab=info.tab,
        m=json.dumps(columns),
    )
    return info.spreadsheet_id


async def capture_email(world: World, email: str = "Priya@Example.com") -> None:
    automation_id = await make_automation(
        world.engine, workspace_id=world.wid, account_id=world.account_id, message_text=None
    )
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO automation_flows (workspace_id, automation_id, version, definition)"
                " VALUES (:w, :a, 1, CAST(:d AS jsonb))"
            ),
            {
                "w": world.wid,
                "a": automation_id,
                "d": json.dumps(
                    {
                        "start": "q",
                        "steps": [
                            {"type": "ask", "id": "q", "text": "Your email?", "expect": "email"}
                        ],
                    }
                ),
            },
        )
        await conn.execute(
            text("UPDATE automations SET flow_version = 1, name = 'Free guide' WHERE id = :a"),
            {"a": automation_id},
        )
    author = ref()
    dm = await world.dm(author, "link please")
    assert dm is not None
    assert await world.run("dm", dm) is Outcome.FIRED
    [question] = await world.rows(
        "SELECT id FROM messages WHERE direction = 'outbound' AND status = 'queued'"
    )
    assert await world.send(question["id"]) is Delivery.SENT
    answer = await world.dm(author, email)
    assert answer is not None
    assert await world.run("dm", answer) is Outcome.ANSWERED


async def pending_rows(world: World) -> list[dict[str, Any]]:
    return await world.rows("SELECT * FROM sheet_rows ORDER BY created_at")


async def append(
    world: World, row_id: uuid.UUID, fake: FakeGoogle, *, now: datetime | None = None
) -> str:
    with workspace_scope(world.wid):
        return await sheets.deliver(
            world.maker, world.deps.cipher, fake, row_id=row_id, now=now or datetime.now(UTC)
        )


async def test_a_capture_appears_as_a_row_in_the_sheet(
    world: World, fake_google: FakeGoogle
) -> None:
    sheet_id = await connect_world(world, fake_google)
    await capture_email(world)

    [row] = await pending_rows(world)
    assert (row["status"], row["attempts"]) == ("pending", 0)
    [job] = await jobs("append_sheet_row")
    assert job["args"]["row_id"] == str(row["id"])
    assert job["queueing_lock"] == f"sheet:{row['id']}"

    assert await append(world, row["id"], fake_google) == "delivered"
    [name, username, platform, email, phone, automation, captured, consent] = (
        await fake_google.rows(sheet_id)
    )[0]
    assert email == "priya@example.com"
    assert (platform, automation, consent, phone) == ("Instagram", "Free guide", "", "")
    assert captured.endswith("Z")
    assert isinstance(name, str)
    assert isinstance(username, str)  # empty cells when the contact has no name or handle
    [done] = await pending_rows(world)
    assert (done["status"], done["attempts"], done["error"]) == ("succeeded", 1, None)
    [conn] = await world.rows("SELECT last_success_at, last_error FROM google_connections")
    assert conn["last_success_at"] is not None
    assert conn["last_error"] is None
    assert await append(world, row["id"], fake_google) == "done"  # not added twice
    assert len(await fake_google.rows(sheet_id)) == 1


async def test_the_columns_follow_the_mapping_when_it_is_sent(
    world: World, fake_google: FakeGoogle
) -> None:
    sheet_id = await connect_world(
        world,
        fake_google,
        mapping=[
            {"field": "email", "header": "Mail"},
            {"field": "automation", "header": "From"},
        ],
    )
    await capture_email(world)
    [row] = await pending_rows(world)
    assert set(row["source"]["fields"]) == set()  # only mapped custom fields are kept
    await execute(
        world,
        "UPDATE google_connections SET mapping = CAST(:m AS jsonb)",
        m=json.dumps([{"field": "automation", "header": "From"}]),
    )
    await append(world, row["id"], fake_google)
    assert await fake_google.rows(sheet_id) == [["Free guide"]]


async def test_nothing_is_queued_without_a_sheet_or_a_plan_that_includes_it(
    world: World, fake_google: FakeGoogle
) -> None:
    await capture_email(world)  # no connection
    assert await pending_rows(world) == []

    await connect_world(world, fake_google, plan="free")
    await capture_email(world, "a@example.com")
    assert await pending_rows(world) == []  # Free: Sheets sync is part of Pro (PD-6, decided)

    await world.plan("pro")
    await execute(world, "UPDATE google_connections SET spreadsheet_id = NULL")
    await capture_email(world, "b@example.com")
    assert await pending_rows(world) == []  # connected but no sheet chosen yet


async def test_a_busy_google_is_retried_with_the_webhook_backoff(
    world: World, fake_google: FakeGoogle
) -> None:
    sheet_id = await connect_world(world, fake_google)
    await capture_email(world)
    [row] = await pending_rows(world)
    now = datetime.now(UTC)
    for attempt in range(1, delivery.MAX_ATTEMPTS):
        fake_google.fail_next(GoogleError("unavailable"))  # raised by the first call: the token
        assert await append(world, row["id"], fake_google, now=now) == "retrying"
        [state] = await pending_rows(world)
        wait = delivery.backoff(attempt)
        assert wait is not None
        assert (state["attempts"], state["next_attempt_at"]) == (attempt, now + wait)
        assert state["error"] == sheets.REASONS[sheets.GOOGLE_BUSY]
        now += wait
    assert [j for j in await jobs("append_sheet_row") if j["deferred"]]

    # The last attempt works: one row, no leftover error.
    assert await append(world, row["id"], fake_google, now=now) == "delivered"
    assert len(await fake_google.rows(sheet_id)) == 1
    [state] = await pending_rows(world)
    assert (state["status"], state["error"]) == ("succeeded", None)


async def test_a_row_that_runs_out_of_attempts_fails_with_a_plain_reason(
    world: World, fake_google: FakeGoogle
) -> None:
    await connect_world(world, fake_google)
    await capture_email(world)
    [row] = await pending_rows(world)
    now = datetime.now(UTC)
    outcome = ""
    for _ in range(delivery.MAX_ATTEMPTS):
        fake_google.fail_next(GoogleError("rate_limited"))
        outcome = await append(world, row["id"], fake_google, now=now)
        now += timedelta(hours=13)
    assert outcome == "failed"
    [state] = await pending_rows(world)
    assert (state["status"], state["attempts"], state["error_code"]) == (
        "failed",
        delivery.MAX_ATTEMPTS,
        sheets.GOOGLE_BUSY,
    )


async def test_a_deleted_sheet_fails_at_once_and_a_new_sheet_sends_it(
    world: World, fake_google: FakeGoogle
) -> None:
    sheet_id = await connect_world(world, fake_google)
    owner = await make_user(world.engine)
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " VALUES (:w, :u, 'owner')"
            ),
            {"w": world.wid, "u": owner},
        )
    await capture_email(world)
    [row] = await pending_rows(world)
    await fake_google.delete_sheet(sheet_id)

    assert await append(world, row["id"], fake_google) == "failed"
    [state] = await pending_rows(world)
    assert (state["status"], state["attempts"], state["error"]) == (
        "failed",
        1,
        "Google said the sheet was deleted. Pick or create a sheet again.",
    )
    [note] = await world.rows("SELECT type, body FROM notifications")
    assert note["type"] == "sheets_failing"
    assert note["body"] == sheets.REASONS[sheets.SHEET_GONE]

    # Making a new sheet sends what failed for that reason.
    with workspace_scope(world.wid):
        async with world.maker() as session:
            await sheets.create_sheet(
                session, fake_google, world.deps.cipher, title="Again", now=datetime.now(UTC)
            )
            await session.commit()
    [again] = await pending_rows(world)
    assert (again["status"], again["attempts"], again["error"]) == ("pending", 0, None)
    assert await append(world, row["id"], fake_google) == "delivered"
    [new_id] = [
        r["spreadsheet_id"]
        for r in await world.rows("SELECT spreadsheet_id FROM google_connections")
    ]
    assert len(await fake_google.rows(new_id)) == 1


async def test_removed_access_fails_the_row_and_reconnecting_sends_it(
    world: World, fake_google: FakeGoogle, redis: Redis
) -> None:
    sheet_id = await connect_world(world, fake_google)
    await capture_email(world)
    [row] = await pending_rows(world)
    [conn] = await world.rows("SELECT credential_enc FROM google_connections")
    await fake_google.revoke_access(world.deps.cipher.decrypt(bytes(conn["credential_enc"])))

    assert await append(world, row["id"], fake_google) == "failed"
    [state] = await pending_rows(world)
    assert (state["error_code"], state["error"]) == (
        sheets.ACCESS_REMOVED,
        "Access was removed: reconnect Google in Settings, under Integrations.",
    )
    [stored] = await world.rows("SELECT status, last_error FROM google_connections")
    assert stored["status"] == "needs_reconnect"

    # A later capture is queued, then fails without calling Google; reconnecting sends both.
    await capture_email(world, "second@example.com")
    second = (await pending_rows(world))[1]
    assert await append(world, second["id"], fake_google) == "failed"

    user = await make_user(world.engine)
    nonce = await sheets.hold_code(
        redis,
        world.deps.cipher,
        {"user_id": str(user), "workspace_id": str(world.wid)},
        "fake-code:owner@example.com",
    )
    with workspace_scope(world.wid):
        async with world.maker() as session:
            await sheets.finish_connect(
                session,
                redis,
                fake_google,
                world.deps.cipher,
                nonce=nonce,
                workspace_id=world.wid,
                user_id=user,
                now=datetime.now(UTC),
            )
            await session.commit()
    assert [r["status"] for r in await pending_rows(world)] == ["pending", "pending"]
    for r in await pending_rows(world):
        assert await append(world, r["id"], fake_google) == "delivered"
    emails = {cells[3] for cells in await fake_google.rows(sheet_id)}
    assert emails == {"priya@example.com", "second@example.com"}


async def test_someone_elses_connect_is_refused(
    world: World, fake_google: FakeGoogle, redis: Redis
) -> None:
    await world.plan("pro")
    starter, other = await make_user(world.engine), await make_user(world.engine)
    nonce = await sheets.hold_code(
        redis,
        world.deps.cipher,
        {"user_id": str(starter), "workspace_id": str(world.wid)},
        "fake-code:owner@example.com",
    )
    with workspace_scope(world.wid):
        async with world.maker() as session:
            with pytest.raises(ApiError) as refused:
                await sheets.finish_connect(
                    session,
                    redis,
                    fake_google,
                    world.deps.cipher,
                    nonce=nonce,
                    workspace_id=world.wid,
                    user_id=other,
                    now=datetime.now(UTC),
                )
    assert refused.value.code == "forbidden"
    assert await world.rows("SELECT id FROM google_connections") == []


async def test_consent_and_custom_fields_ride_along(world: World, fake_google: FakeGoogle) -> None:
    sheet_id = await connect_world(
        world,
        fake_google,
        mapping=[
            {"field": "email", "header": "Mail"},
            {"field": "field:city", "header": "City"},
            {"field": "consent", "header": "OK to message"},
        ],
    )
    await execute(
        world,
        "INSERT INTO contact_field_definitions (workspace_id, key, label, type)"
        " VALUES (:w, 'city', 'City', 'text')",
        w=world.wid,
    )
    await capture_email(world)
    [contact] = await world.rows("SELECT id FROM contacts")
    await execute(
        world, 'UPDATE contacts SET fields = CAST(\'{"city": "Kochi", "other": "x"}\' AS jsonb)'
    )
    await execute(
        world,
        "INSERT INTO contact_consents (workspace_id, contact_id, channel, purpose, status, source,"
        " occurred_at) VALUES (:w, :c, 'instagram', 'marketing', 'granted', 'flow', now())",
        w=world.wid,
        c=contact["id"],
    )
    with workspace_scope(world.wid):
        async with world.maker() as session:
            from socialhood.models.inbox import Contact

            found = await session.get(Contact, contact["id"])
            assert found is not None
            await sheets.queue_lead(
                session, found, platform="instagram", automation_name="Free guide"
            )
            await session.commit()
    second = (await pending_rows(world))[1]
    assert second["source"]["fields"] == {"city": "Kochi"}  # only what the columns use
    await append(world, second["id"], fake_google)
    assert await fake_google.rows(sheet_id) == [["priya@example.com", "Kochi", "Yes"]]


async def test_the_scrub_job_keeps_pending_rows_and_removes_old_finished_ones(
    world: World, fake_google: FakeGoogle
) -> None:
    from socialhood.repositories import retention

    await connect_world(world, fake_google)
    await capture_email(world)
    await capture_email(world, "two@example.com")
    first, _ = await pending_rows(world)
    await append(world, first["id"], fake_google)
    await execute(world, "UPDATE sheet_rows SET created_at = now() - interval '400 days'")
    async with world.maker() as session:
        removed = await retention.sheet_rows_before(
            session, datetime.now(UTC) - timedelta(days=90), limit=100
        )
        await session.commit()
    assert removed == 1
    [left] = await pending_rows(world)
    assert left["status"] == "pending"
