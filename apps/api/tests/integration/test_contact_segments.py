"""GR-17: the contacts page's API. Done when filtering by "tag = lead-magnet and has email" and
exporting gives the right rows. Also: the count, saved segments, bulk tagging by filter with its
cap, the timeline, and who may do what."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.services import contact_segments
from tests.support.api import Clerk, sign_in
from tests.support.automation_api import Ws, make_run, workspace
from tests.support.automations import make_automation, make_comment, make_media_item
from tests.support.inbox import make_thread


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


async def person(engine: AsyncEngine, ws: Ws, ref: str, name: str) -> uuid.UUID:
    thread = await make_thread(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        contact_ref=ref,
        username=ref,
        display_name=name,
        texts=("Hi",),
    )
    return thread.contact_id


async def as_agent(ws: Ws, engine: AsyncEngine, client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    """Another user who is an agent in the workspace, with a Ws that calls as them."""
    clerk_id, me = await sign_in(client, clerk, email="agent@example.com")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " VALUES (:w, :u, 'agent')"
            ),
            {"w": ws.wid, "u": me["id"]},
        )
    return Ws(client, clerk, clerk_id, ws.wid, me["id"], ws.account_id)


# ---------------------------------------------------------------- the done-when


async def test_tag_and_has_email_filter_then_export_gives_the_right_rows(
    engine: AsyncEngine, ws: Ws
) -> None:
    magnet = await ws.ok("POST", "/tags", 201, json={"name": "lead-magnet"})
    ids = {n: await person(engine, ws, n, n.title()) for n in ("asha", "bina", "chetan", "divya")}
    for n in ("asha", "bina", "chetan"):
        await ws.ok("POST", f"/contacts/{ids[n]}/tags", json={"add": [magnet["id"]]})
    for n in ("asha", "chetan", "divya"):
        await ws.ok("PATCH", f"/contacts/{ids[n]}", json={"email": f"{n}@example.com"})

    # lead-magnet and an email: Asha and Chetan. Bina has the tag only, Divya the email only.
    query = {"tag_id": magnet["id"], "has_email": "true"}
    listed = await ws.ok("GET", "/contacts", params=query)
    assert sorted(c["name"] for c in listed["items"]) == ["Asha", "Chetan"]
    assert (await ws.ok("GET", "/contacts/count", params=query)) == {"count": 2}

    response = await ws.call("GET", "/contacts/export.csv", params=query)
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert sorted(r["Name"] for r in rows) == ["Asha", "Chetan"]
    assert {r["Email"] for r in rows} == {"asha@example.com", "chetan@example.com"}
    assert all(r["Tags"] == "lead-magnet" for r in rows)


async def test_the_count_follows_every_filter_and_refuses_an_unknown_field(
    engine: AsyncEngine, ws: Ws
) -> None:
    for n in range(3):
        await person(engine, ws, f"p{n}", f"Person {n}")
    assert (await ws.ok("GET", "/contacts/count")) == {"count": 3}
    assert (await ws.ok("GET", "/contacts/count", params={"q": "person 1"})) == {"count": 1}
    assert (await ws.ok("GET", "/contacts/count", params={"has_phone": "true"})) == {"count": 0}
    refused = await ws.call("GET", "/contacts/count", params={"field": "city:pune"})
    assert refused.status_code == 422
    assert [e["field"] for e in refused.json()["errors"]] == ["field"]


async def test_a_field_filter_has_or_equals(engine: AsyncEngine, ws: Ws) -> None:
    pune = await person(engine, ws, "a", "Asha")
    await person(engine, ws, "b", "Bina")
    goa = await person(engine, ws, "c", "Chetan")
    await ws.ok("POST", "/contact-fields", 201, json={"key": "city", "label": "City"})
    await ws.ok("PATCH", f"/contacts/{pune}", json={"fields": {"city": "Pune"}})
    await ws.ok("PATCH", f"/contacts/{goa}", json={"fields": {"city": "Goa"}})
    has = await ws.ok("GET", "/contacts", params={"field": "city:*"})
    assert sorted(c["name"] for c in has["items"]) == ["Asha", "Chetan"]
    equals = await ws.ok("GET", "/contacts", params={"field": "city:pune"})
    assert [c["name"] for c in equals["items"]] == ["Asha"]


async def test_the_activity_filter_keeps_the_range(engine: AsyncEngine, ws: Ws) -> None:
    await person(engine, ws, "a", "Asha")
    now = datetime.now(UTC)
    inside = {
        "active_after": (now - timedelta(hours=1)).isoformat(),
        "active_before": (now + timedelta(hours=1)).isoformat(),
    }
    assert (await ws.ok("GET", "/contacts/count", params=inside)) == {"count": 1}
    before = {"active_before": (now - timedelta(days=1)).isoformat()}
    assert (await ws.ok("GET", "/contacts/count", params=before)) == {"count": 0}
    # The moving ranges a saved segment uses.
    assert (await ws.ok("GET", "/contacts/count", params={"active_within_days": 1})) == {"count": 1}
    assert (await ws.ok("GET", "/contacts/count", params={"inactive_for_days": 1})) == {"count": 0}


# ---------------------------------------------------------------- segments


async def test_segments_are_created_listed_renamed_and_deleted(engine: AsyncEngine, ws: Ws) -> None:
    magnet = await ws.ok("POST", "/tags", 201, json={"name": "lead-magnet"})
    await ws.ok("POST", "/contact-fields", 201, json={"key": "city", "label": "City"})
    spec = {"tag_ids": [magnet["id"]], "has_email": True, "fields": ["city:*"]}

    created = await ws.ok(
        "POST", "/contact-segments", 201, json={"name": "Warm leads", "filter": spec}
    )
    assert created["name"] == "Warm leads"
    assert created["filter"]["tag_ids"] == [magnet["id"]]
    assert created["filter"]["has_email"] is True

    duplicate = await ws.call(
        "POST", "/contact-segments", json={"name": "warm LEADS", "filter": {}}
    )
    assert duplicate.status_code == 409

    await ws.ok("POST", "/contact-segments", 201, json={"name": "Everyone", "filter": {}})
    names = [s["name"] for s in (await ws.ok("GET", "/contact-segments"))["items"]]
    assert names == ["Everyone", "Warm leads"]

    renamed = await ws.ok(
        "PATCH",
        f"/contact-segments/{created['id']}",
        json={"name": "Hot leads", "filter": {"min_lead_score": 70}},
    )
    assert renamed["name"] == "Hot leads"
    assert renamed["filter"]["min_lead_score"] == 70
    assert renamed["filter"].get("tag_ids", []) == []  # the filter is replaced, not merged

    clash = await ws.call("PATCH", f"/contact-segments/{created['id']}", json={"name": "everyone"})
    assert clash.status_code == 409

    await ws.ok("DELETE", f"/contact-segments/{created['id']}", 204)
    assert [s["name"] for s in (await ws.ok("GET", "/contact-segments"))["items"]] == ["Everyone"]
    gone = await ws.call("PATCH", f"/contact-segments/{created['id']}", json={"name": "x"})
    assert gone.status_code == 404


async def test_a_segment_refuses_a_missing_tag_or_field_and_a_bad_filter(ws: Ws) -> None:
    missing_tag = await ws.call(
        "POST",
        "/contact-segments",
        json={"name": "Ghost tag", "filter": {"tag_ids": [str(uuid.uuid4())]}},
    )
    assert missing_tag.status_code == 404
    missing_field = await ws.call(
        "POST", "/contact-segments", json={"name": "Ghost field", "filter": {"fields": ["city:*"]}}
    )
    assert missing_field.status_code == 422
    backwards = await ws.call(
        "POST",
        "/contact-segments",
        json={
            "name": "Backwards",
            "filter": {
                "active_after": "2026-02-01T00:00:00Z",
                "active_before": "2026-01-01T00:00:00Z",
            },
        },
    )
    assert backwards.status_code == 422
    assert (
        await ws.call("POST", "/contact-segments", json={"name": "", "filter": {}})
    ).status_code == 422
    assert (await ws.ok("GET", "/contact-segments"))["items"] == []


async def test_a_workspace_keeps_at_most_fifty_segments(
    ws: Ws, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(contact_segments, "MAX_SEGMENTS", 2)
    for n in range(2):
        await ws.ok("POST", "/contact-segments", 201, json={"name": f"S{n}", "filter": {}})
    over = await ws.call("POST", "/contact-segments", json={"name": "S2", "filter": {}})
    assert over.status_code == 422
    assert [e["field"] for e in over.json()["errors"]] == ["name"]


async def test_a_segments_filter_lists_and_exports_the_same_people(
    engine: AsyncEngine, ws: Ws
) -> None:
    magnet = await ws.ok("POST", "/tags", 201, json={"name": "lead-magnet"})
    a = await person(engine, ws, "a", "Asha")
    await person(engine, ws, "b", "Bina")
    await ws.ok("POST", f"/contacts/{a}/tags", json={"add": [magnet["id"]]})
    segment = await ws.ok(
        "POST",
        "/contact-segments",
        201,
        json={"name": "Magnet", "filter": {"tag_ids": [magnet["id"]]}},
    )
    params = [("tag_id", t) for t in segment["filter"]["tag_ids"]]
    assert [c["name"] for c in (await ws.ok("GET", "/contacts", params=params))["items"]] == [
        "Asha"
    ]


# ---------------------------------------------------------------- bulk tag


async def test_bulk_tag_by_filter_adds_and_removes_on_everyone_matching(
    engine: AsyncEngine, ws: Ws
) -> None:
    ids = [await person(engine, ws, f"p{n}", f"Person {n}") for n in range(4)]
    for n in (0, 1, 2):
        await ws.ok("PATCH", f"/contacts/{ids[n]}", json={"email": f"p{n}@example.com"})
    nurture = await ws.ok("POST", "/tags", 201, json={"name": "nurture"})
    old = await ws.ok("POST", "/tags", 201, json={"name": "old"})
    await ws.ok(
        "POST",
        "/contacts/bulk-tags",
        json={"contact_ids": [str(i) for i in ids], "add": [old["id"]]},
    )

    result = await ws.ok(
        "POST",
        "/contacts/bulk-tags",
        json={"filter": {"has_email": True}, "add": [nurture["id"]], "remove": [old["id"]]},
    )
    assert result == {"updated": 3}
    tagged = await ws.ok("GET", "/contacts", params={"tag_id": nurture["id"]})
    assert sorted(c["name"] for c in tagged["items"]) == ["Person 0", "Person 1", "Person 2"]
    still_old = await ws.ok("GET", "/contacts", params={"tag_id": old["id"]})
    assert [c["name"] for c in still_old["items"]] == ["Person 3"]

    again = await ws.ok(
        "POST", "/contacts/bulk-tags", json={"filter": {"has_email": True}, "add": [nurture["id"]]}
    )
    assert again == {"updated": 3}  # already tagged: nothing doubles
    counts = {t["name"]: t["contact_count"] for t in (await ws.ok("GET", "/tags"))["items"]}
    assert counts == {"nurture": 3, "old": 1}


async def test_bulk_tag_by_filter_is_capped_with_the_count(
    engine: AsyncEngine, ws: Ws, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(contact_segments, "BULK_FILTER_CAP", 2)
    for n in range(3):
        await person(engine, ws, f"p{n}", f"Person {n}")
    tag = await ws.ok("POST", "/tags", 201, json={"name": "all"})
    refused = await ws.call("POST", "/contacts/bulk-tags", json={"filter": {}, "add": [tag["id"]]})
    assert refused.status_code == 422
    error = refused.json()["errors"][0]
    assert error["field"] == "filter"
    assert "3" in error["message"]
    assert (await ws.ok("GET", "/tags"))["items"][0]["contact_count"] == 0
    narrowed = await ws.ok(
        "POST", "/contacts/bulk-tags", json={"filter": {"q": "person 1"}, "add": [tag["id"]]}
    )
    assert narrowed == {"updated": 1}


async def test_bulk_tag_needs_contacts_or_a_filter_and_a_real_tag(
    engine: AsyncEngine, ws: Ws
) -> None:
    c = await person(engine, ws, "a", "Asha")
    tag = await ws.ok("POST", "/tags", 201, json={"name": "x"})
    both = await ws.call(
        "POST",
        "/contacts/bulk-tags",
        json={"contact_ids": [str(c)], "filter": {}, "add": [tag["id"]]},
    )
    neither = await ws.call("POST", "/contacts/bulk-tags", json={"add": [tag["id"]]})
    assert (both.status_code, neither.status_code) == (422, 422)
    ghost = await ws.call(
        "POST", "/contacts/bulk-tags", json={"filter": {}, "add": [str(uuid.uuid4())]}
    )
    assert ghost.status_code == 404


# ---------------------------------------------------------------- timeline


async def test_the_timeline_lists_what_happened_newest_first_and_pages(
    engine: AsyncEngine, ws: Ws
) -> None:
    contact = await person(engine, ws, "a", "Asha")
    other = await person(engine, ws, "b", "Bina")
    now = datetime.now(UTC)
    media = await make_media_item(engine, workspace_id=ws.wid, account_id=ws.account_id)
    asked = await make_comment(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        media_item_id=media,
        text="LINK please " + "x" * 400,
        contact_id=contact,
        commented_at=now - timedelta(hours=3),
    )
    await make_comment(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        media_item_id=media,
        text="Not Asha",
        contact_id=other,
        commented_at=now - timedelta(hours=3),
    )
    automation = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    await make_run(
        engine,
        workspace_id=ws.wid,
        automation_id=automation,
        created_at=now - timedelta(hours=2),
        trigger_comment_id=asked,
        contact_id=contact,
    )
    tag = await ws.ok("POST", "/tags", 201, json={"name": "vip"})
    await ws.ok("POST", f"/contacts/{contact}/tags", json={"add": [tag["id"]]})
    await ws.ok(
        "POST",
        f"/contacts/{contact}/consents",
        json={"channel": "instagram", "status": "granted", "note": "Said yes in the shop"},
    )

    page = await ws.ok("GET", f"/contacts/{contact}/timeline")
    kinds = [i["kind"] for i in page["items"]]
    assert sorted(kinds) == sorted(["conversation", "comment", "automation_run", "tag", "consent"])
    times = [i["occurred_at"] for i in page["items"]]
    assert times == sorted(times, reverse=True)
    comment = next(i for i in page["items"] if i["kind"] == "comment")
    assert comment["title"] == "Commented"
    assert len(comment["detail"]) == 200  # cut short
    run = next(i for i in page["items"] if i["kind"] == "automation_run")
    assert run["title"] == "Automation: Send the link"
    assert run["detail"] == "Replied"
    consent = next(i for i in page["items"] if i["kind"] == "consent")
    assert consent["title"] == "Agreed to marketing on Instagram"
    assert "Not Asha" not in str(page)

    first = await ws.ok("GET", f"/contacts/{contact}/timeline", params={"limit": 2})
    assert len(first["items"]) == 2
    assert first["next_cursor"]
    rest = await ws.ok(
        "GET",
        f"/contacts/{contact}/timeline",
        params={"limit": 10, "cursor": first["next_cursor"]},
    )
    assert rest["next_cursor"] is None
    paged = [i["id"] for i in first["items"] + rest["items"]]
    assert paged == [i["id"] for i in page["items"]]  # nothing repeated or skipped


async def test_the_timeline_of_nobody_is_not_found_and_a_bad_cursor_is_refused(
    engine: AsyncEngine, ws: Ws
) -> None:
    assert (await ws.call("GET", f"/contacts/{uuid.uuid4()}/timeline")).status_code == 404
    c = await person(engine, ws, "a", "Asha")
    bad = await ws.call("GET", f"/contacts/{c}/timeline", params={"cursor": "nonsense"})
    assert bad.status_code == 400


# ---------------------------------------------------------------- who may do what


async def test_agents_read_and_tag_but_only_admins_manage_segments_and_export(
    engine: AsyncEngine, ws: Ws, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    c = await person(engine, ws, "a", "Asha")
    tag = await ws.ok("POST", "/tags", 201, json={"name": "vip"})
    segment = await ws.ok("POST", "/contact-segments", 201, json={"name": "All", "filter": {}})
    agent = await as_agent(ws, engine, client, clerk)

    assert len((await agent.ok("GET", "/contacts"))["items"]) == 1
    assert (await agent.ok("GET", "/contacts/count")) == {"count": 1}
    assert len((await agent.ok("GET", "/contact-segments"))["items"]) == 1
    await agent.ok("GET", f"/contacts/{c}/timeline")
    bulk = await agent.ok("POST", "/contacts/bulk-tags", json={"filter": {}, "add": [tag["id"]]})
    assert bulk == {"updated": 1}

    for method, path, body in (
        ("POST", "/contact-segments", {"name": "Mine", "filter": {}}),
        ("PATCH", f"/contact-segments/{segment['id']}", {"name": "Renamed"}),
        ("DELETE", f"/contact-segments/{segment['id']}", None),
        ("GET", "/contacts/export.csv", None),
    ):
        denied = await agent.call(method, path, **({"json": body} if body else {}))
        assert denied.status_code == 403, (method, path)


async def test_another_workspace_sees_none_of_it(
    engine: AsyncEngine, ws: Ws, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    c = await person(engine, ws, "a", "Asha")
    segment = await ws.ok("POST", "/contact-segments", 201, json={"name": "All", "filter": {}})
    other = await workspace(client, clerk, email="other@example.com")
    assert (await other.ok("GET", "/contact-segments"))["items"] == []
    assert (await other.ok("GET", "/contacts/count")) == {"count": 0}
    assert (await other.call("GET", f"/contacts/{c}/timeline")).status_code == 404
    gone = await other.call("DELETE", f"/contact-segments/{segment['id']}")
    assert gone.status_code == 404
    crossed = await client.get(f"/v1/w/{ws.wid}/contact-segments", headers=other.headers)
    assert crossed.status_code == 404
