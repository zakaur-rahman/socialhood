"""GR-28 tenancy: the website chat's public routes belong to one workspace each. A visitor, a token
or a widget id of one workspace never reads, writes or learns anything about another's, and the
settings routes of another workspace are 404 (the path walk in test_isolation.py covers them, this
adds the public side)."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.security import widget_tokens as tokens
from tests.support.api import TOKEN_KEY, Clerk
from tests.support.automation_api import Ws, workspace

A_HOST, B_HOST = "a.example", "b.example"


async def widget(ws: Ws, host: str) -> str:
    """The workspace's widget id, allowing ``host``."""
    made = await ws.ok("GET", "/widget")
    await ws.ok("PUT", "/widget", json={"allowed_domains": [host]})
    return str(made["widget_id"])


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def snapshot(engine: AsyncEngine, wid: str) -> dict[str, list[dict[str, Any]]]:
    tables = ("contacts", "conversations", "messages", "widget_settings", "contact_consents")
    return {
        table: await rows(
            engine,
            f"SELECT * FROM {table} WHERE workspace_id = :w ORDER BY id",  # noqa: S608
            w=wid,
        )
        for table in tables
    }


@pytest.fixture
async def both(client: httpx.AsyncClient, clerk: Clerk, queue: None) -> tuple[Ws, str, Ws, str]:
    a = await workspace(client, clerk, email="a@example.com")
    b = await workspace(client, clerk, email="b@example.com")
    return a, await widget(a, A_HOST), b, await widget(b, B_HOST)


async def open_session(
    client: httpx.AsyncClient, widget_id: str, host: str, key: str | None = None
) -> httpx.Response:
    return await client.post(
        "/v1/widget/session", json={"widget_id": widget_id, "host": host, "visitor_key": key}
    )


async def send(client: httpx.AsyncClient, opened: dict[str, Any], body: str) -> httpx.Response:
    return await client.post(
        "/v1/widget/messages",
        json={"text": body, "client_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {opened['session_key']}"},
    )


async def test_one_visitor_key_is_a_different_visitor_in_each_workspace(
    client: httpx.AsyncClient, engine: AsyncEngine, both: tuple[Ws, str, Ws, str]
) -> None:
    a, a_id, b, b_id = both
    in_b = (await open_session(client, b_id, B_HOST)).json()
    assert (await send(client, in_b, "A secret meant for B")).status_code == 200

    # The same visitor key at A's widget is a stranger there: no history, no shared contact.
    in_a = (await open_session(client, a_id, A_HOST, in_b["visitor_key"])).json()
    assert in_a["messages"] == []
    assert in_a["version"] == "0.0"
    assert (await send(client, in_a, "Hello A")).status_code == 200

    assert [
        r["text"]
        for r in await rows(engine, "SELECT text FROM messages WHERE workspace_id = :w", w=a.wid)
    ] == ["Hello A"]
    assert [
        r["text"]
        for r in await rows(engine, "SELECT text FROM messages WHERE workspace_id = :w", w=b.wid)
    ] == ["A secret meant for B"]
    for ws in (a, b):
        assert (
            len(
                await rows(
                    engine,
                    "SELECT id FROM contacts WHERE workspace_id = :w"
                    " AND platform_user_id LIKE 'v\\_%'",
                    w=ws.wid,
                )
            )
            == 1
        )


async def test_a_widget_id_works_only_for_its_own_sites(
    client: httpx.AsyncClient, both: tuple[Ws, str, Ws, str]
) -> None:
    _, a_id, _, b_id = both
    assert (await open_session(client, b_id, A_HOST)).status_code == 403  # B's id on A's site
    assert (await open_session(client, a_id, B_HOST)).status_code == 403
    for widget_id, host in ((a_id, A_HOST), (b_id, B_HOST)):
        frame = await client.get("/widget/frame", params={"w": widget_id, "h": host})
        assert frame.status_code == 200
        assert host in frame.headers["content-security-policy"]
        other = B_HOST if host == A_HOST else A_HOST
        assert other not in frame.headers["content-security-policy"]
        crossed = await client.get("/widget/frame", params={"w": widget_id, "h": other})
        assert crossed.status_code == 403


async def test_a_token_names_one_workspace_and_cannot_be_pointed_at_another(
    client: httpx.AsyncClient, engine: AsyncEngine, both: tuple[Ws, str, Ws, str]
) -> None:
    a, _, b, b_id = both
    in_b = (await open_session(client, b_id, B_HOST)).json()
    await send(client, in_b, "Private to B")
    [a_account] = await rows(
        engine,
        "SELECT id FROM social_accounts WHERE workspace_id = :w AND platform = 'web'",
        w=a.wid,
    )
    [b_account] = await rows(
        engine,
        "SELECT id FROM social_accounts WHERE workspace_id = :w AND platform = 'web'",
        w=b.wid,
    )
    visitor = tokens.visitor_id(in_b["visitor_key"])
    before = await snapshot(engine, b.wid)

    # Signed by the server, but naming A's account inside B's workspace (and the reverse): the
    # account is not visible there, so the widget is not found.
    crossed = (
        (a_account["id"], b.wid, B_HOST),
        (b_account["id"], a.wid, A_HOST),
    )
    for account_id, workspace_id, host in crossed:
        forged, _ = tokens.issue(
            account_id=account_id,
            workspace_id=uuid.UUID(workspace_id),
            visitor=visitor,
            host=host,
            keys=[TOKEN_KEY],
        )
        headers = {"Authorization": f"Bearer {forged}"}
        read = await client.get("/v1/widget/messages", headers=headers)
        assert read.status_code == 404, read.text
        write = await client.post(
            "/v1/widget/messages",
            json={"text": "Injected", "client_id": str(uuid.uuid4())},
            headers=headers,
        )
        assert write.status_code == 404, write.text
        email = await client.post(
            "/v1/widget/email", json={"email": "x@example.com"}, headers=headers
        )
        assert email.status_code == 404, email.text

    assert await snapshot(engine, b.wid) == before


async def test_a_visitors_chat_shows_only_in_its_own_workspace_inbox(
    client: httpx.AsyncClient, both: tuple[Ws, str, Ws, str]
) -> None:
    a, _, b, b_id = both
    in_b = (await open_session(client, b_id, B_HOST)).json()
    await send(client, in_b, "Only B should see this")
    listed_a = await a.ok("GET", "/conversations")
    assert [c for c in listed_a["items"] if c["platform"] == "web"] == []
    listed_b = await b.ok("GET", "/conversations")
    [mine] = [c for c in listed_b["items"] if c["platform"] == "web"]
    assert mine["last_message_preview"] == "Only B should see this"


async def test_another_workspaces_settings_are_not_found(
    both: tuple[Ws, str, Ws, str], engine: AsyncEngine
) -> None:
    a, _, b, _ = both
    before = await snapshot(engine, b.wid)
    for method, body in (("GET", None), ("PUT", {"enabled": False, "allowed_domains": []})):
        response = await a.client.request(
            method, f"/v1/w/{b.wid}/widget", json=body, headers=a.headers
        )
        assert response.status_code == 404, response.text
        assert response.json()["code"] == "not_found"
    assert await snapshot(engine, b.wid) == before


async def test_a_deleted_workspaces_widget_stops_answering(
    client: httpx.AsyncClient, engine: AsyncEngine, both: tuple[Ws, str, Ws, str]
) -> None:
    _, _, b, b_id = both
    opened = (await open_session(client, b_id, B_HOST)).json()
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET status = 'deleting' WHERE id = :w"), {"w": b.wid}
        )
    assert (await open_session(client, b_id, B_HOST)).status_code == 404
    assert (await send(client, opened, "Anyone?")).status_code == 404
