"""GR-08: the entry links routes - create, list with counts, update, delete, QR download, and the
automation a link may start."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from tests.support.api import Clerk
from tests.support.automation_api import Ws, workspace


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


async def entry_automation(ws: Ws, **values: Any) -> dict[str, Any]:
    return await ws.active(
        **ws.definition(trigger="entry_link", keywords=[], message_buttons=[], **values)
    )


async def test_a_link_gets_a_code_an_ig_me_address_and_zero_counts(ws: Ws) -> None:
    automation = await entry_automation(ws)
    link = await ws.ok(
        "POST",
        "/entry-links",
        201,
        json={
            "social_account_id": ws.account_id,
            "name": "Shop window",
            "automation_id": automation["id"],
        },
    )
    assert len(link["code"]) == 8
    assert link["url"].startswith("https://ig.me/m/")
    assert link["url"].endswith(f"?ref={link['code']}")
    assert (link["opened_conversations"], link["runs"]) == (0, 0)
    assert link["automation_name"] == automation["name"]

    listed = await ws.ok("GET", f"/entry-links?account_id={ws.account_id}")
    assert [i["id"] for i in listed["items"]] == [link["id"]]


async def test_a_typed_code_is_kept_and_cannot_repeat_on_the_account(ws: Ws) -> None:
    body = {"social_account_id": ws.account_id, "name": "Menu", "code": "menu-qr"}
    link = await ws.ok("POST", "/entry-links", 201, json=body)
    assert link["code"] == "menu-qr"
    again = await ws.call("POST", "/entry-links", json=body)
    assert again.status_code == 422
    assert [e["field"] for e in again.json()["errors"]] == ["code"]
    bad = await ws.call("POST", "/entry-links", json={**body, "code": "no spaces"})
    assert bad.status_code == 422


async def test_a_link_can_only_start_an_entry_link_automation_of_its_account(ws: Ws) -> None:
    keyword = await ws.active()
    response = await ws.call(
        "POST",
        "/entry-links",
        json={
            "social_account_id": ws.account_id,
            "name": "Wrong",
            "automation_id": keyword["id"],
        },
    )
    assert response.status_code == 422
    assert [e["field"] for e in response.json()["errors"]] == ["automation_id"]


async def test_a_link_is_renamed_and_repointed_but_keeps_its_code(ws: Ws) -> None:
    first = await entry_automation(ws, name="First")
    second = await entry_automation(ws, name="Second")
    link = await ws.ok(
        "POST",
        "/entry-links",
        201,
        json={"social_account_id": ws.account_id, "name": "A", "automation_id": first["id"]},
    )
    changed = await ws.ok(
        "PUT",
        f"/entry-links/{link['id']}",
        json={"name": "B", "automation_id": second["id"]},
    )
    assert (changed["name"], changed["automation_name"], changed["code"]) == (
        "B",
        "Second",
        link["code"],
    )


async def test_the_qr_code_downloads_as_svg_and_png(ws: Ws) -> None:
    link = await ws.ok(
        "POST", "/entry-links", 201, json={"social_account_id": ws.account_id, "name": "QR"}
    )
    svg = await ws.call("GET", f"/entry-links/{link['id']}/qr?format=svg")
    assert svg.status_code == 200
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert "attachment" in svg.headers["content-disposition"]
    png = await ws.call("GET", f"/entry-links/{link['id']}/qr?format=png")
    assert png.content.startswith(b"\x89PNG")
    assert (await ws.call("GET", f"/entry-links/{link['id']}/qr?format=gif")).status_code == 422


async def test_deleting_the_automation_keeps_the_link_and_deleting_the_link_removes_it(
    ws: Ws,
) -> None:
    automation = await entry_automation(ws)
    link = await ws.ok(
        "POST",
        "/entry-links",
        201,
        json={
            "social_account_id": ws.account_id,
            "name": "Kept",
            "automation_id": automation["id"],
        },
    )
    await ws.ok("DELETE", f"/automations/{automation['id']}", 204)
    kept = await ws.ok("GET", f"/entry-links/{link['id']}")
    assert (kept["automation_id"], kept["automation_name"]) == (None, None)

    await ws.ok("DELETE", f"/entry-links/{link['id']}", 204)
    assert (await ws.call("GET", f"/entry-links/{link['id']}")).status_code == 404


async def test_an_entry_link_and_ad_click_automation_keep_their_settings(ws: Ws) -> None:
    ads = await ws.draft(
        **ws.definition(
            trigger="ad_click",
            keywords=[],
            message_buttons=[],
            post_scope="selected",
            ad_ids=["ad_1", "ad_2", "ad_1"],
        )
    )
    assert (ads["post_scope"], ads["ad_ids"]) == ("selected", ["ad_1", "ad_2"])
    assert ads["missing_for_activation"] == []
    empty = await ws.draft(
        **ws.definition(trigger="ad_click", keywords=[], message_buttons=[], post_scope="selected")
    )
    assert empty["missing_for_activation"] == ["ad_ids"]


async def test_members_who_are_not_admins_are_refused(
    ws: Ws, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    other = await workspace(client, clerk, email="other@example.com")
    response = await client.get(
        f"/v1/w/{ws.wid}/entry-links", headers=clerk.headers(other.clerk_id)
    )
    assert response.status_code in (403, 404)
