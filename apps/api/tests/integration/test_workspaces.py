"""T1.3: workspace context, roles and settings (TR-TEN-01, TR-TEN-05, FR-ACC-03); T1.8 overview."""

from __future__ import annotations

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.api import Clerk, sign_in


async def test_members_read_their_workspace(client: httpx.AsyncClient, clerk: Clerk) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    response = await client.get(f"/v1/w/{wid}", headers=clerk.headers(clerk_id))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == wid
    assert body["timezone"] == "UTC"
    assert body["reply_language"] == "auto"
    assert body["role"] == "owner"
    assert body["checklist_dismissed_at"] is None


async def test_a_non_member_gets_404(client: httpx.AsyncClient, clerk: Clerk) -> None:
    _, owner = await sign_in(client, clerk, email="owner@example.com")
    stranger, _ = await sign_in(client, clerk, email="stranger@example.com")
    wid = owner["workspaces"][0]["id"]
    for path in (f"/v1/w/{wid}", f"/v1/w/{wid}/overview"):
        response = await client.get(path, headers=clerk.headers(stranger))
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"


async def test_an_unknown_workspace_id_is_404(client: httpx.AsyncClient, clerk: Clerk) -> None:
    clerk_id, _ = await sign_in(client, clerk)
    missing = "00000000-0000-4000-8000-000000000000"
    response = await client.get(f"/v1/w/{missing}", headers=clerk.headers(clerk_id))
    assert response.status_code == 404


async def test_settings_update(client: httpx.AsyncClient, clerk: Clerk) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    response = await client.patch(
        f"/v1/w/{wid}",
        headers=clerk.headers(clerk_id),
        json={
            "name": "Aria Label",
            "slug": "aria-label",
            "timezone": "Asia/Kolkata",
            "reply_language": "hi",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["slug"], body["timezone"], body["reply_language"]) == (
        "Aria Label",
        "aria-label",
        "Asia/Kolkata",
        "hi",
    )


async def test_timezone_is_validated_against_iana(client: httpx.AsyncClient, clerk: Clerk) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    response = await client.patch(
        f"/v1/w/{wid}", headers=clerk.headers(clerk_id), json={"timezone": "Mars/Olympus"}
    )
    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "timezone", "message": "Choose a timezone from the list."}
    ]


async def test_invalid_and_taken_slugs_are_field_errors(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    first_id, first = await sign_in(client, clerk, email="a@example.com")
    _, second = await sign_in(client, clerk, email="b@example.com", first_name="Other")
    wid = first["workspaces"][0]["id"]
    headers = clerk.headers(first_id)

    bad = await client.patch(f"/v1/w/{wid}", headers=headers, json={"slug": "Bad Slug!"})
    assert bad.status_code == 422
    assert bad.json()["errors"][0]["field"] == "slug"

    taken = second["workspaces"][0]["slug"]
    clash = await client.patch(f"/v1/w/{wid}", headers=headers, json={"slug": taken})
    assert clash.status_code == 422
    assert clash.json()["errors"] == [{"field": "slug", "message": "That URL is already taken."}]


async def test_unknown_fields_are_rejected(client: httpx.AsyncClient, clerk: Clerk) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    response = await client.patch(
        f"/v1/w/{wid}", headers=clerk.headers(clerk_id), json={"owner_user_id": "x"}
    )
    assert response.status_code == 422


async def test_agents_cannot_change_settings(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE workspace_members SET role = 'agent'"))
    headers = clerk.headers(clerk_id)
    assert (await client.get(f"/v1/w/{wid}", headers=headers)).status_code == 200
    response = await client.patch(f"/v1/w/{wid}", headers=headers, json={"name": "Nope"})
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_opening_a_workspace_remembers_it(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE users SET last_workspace_id = NULL"))
    await client.get(f"/v1/w/{wid}", headers=clerk.headers(clerk_id))
    again = await client.get("/v1/me", headers=clerk.headers(clerk_id))
    assert again.json()["last_workspace_id"] == wid


async def test_workspace_list(client: httpx.AsyncClient, clerk: Clerk) -> None:
    clerk_id, me = await sign_in(client, clerk)
    response = await client.get("/v1/workspaces", headers=clerk.headers(clerk_id))
    assert response.status_code == 200
    assert response.json() == {"items": me["workspaces"], "next_cursor": None}


async def test_checklist_is_computed_and_dismiss_persists(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    headers = clerk.headers(clerk_id)

    overview = (await client.get(f"/v1/w/{wid}/overview", headers=headers)).json()
    assert overview["range"] == "7d"
    assert overview["checklist"]["dismissed"] is False
    assert [s["key"] for s in overview["checklist"]["steps"]] == [
        "connect_account",
        "add_knowledge",
        "choose_ai_mode",
        "create_automation",
    ]
    assert overview["checklist"]["completed"] == 0

    await client.patch(f"/v1/w/{wid}", headers=headers, json={"checklist_dismissed": True})
    again = (await client.get(f"/v1/w/{wid}/overview?range=30d", headers=headers)).json()
    assert again["range"] == "30d"
    assert again["checklist"]["dismissed"] is True

    await client.patch(f"/v1/w/{wid}", headers=headers, json={"checklist_dismissed": False})
    restored = (await client.get(f"/v1/w/{wid}/overview", headers=headers)).json()
    assert restored["checklist"]["dismissed"] is False
