"""GR-02: contacts, tags, custom fields, consent and the CSV export."""

from __future__ import annotations

import csv
import io
import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.inbox import make_thread


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


async def person(
    engine: AsyncEngine, ws: Ws, ref: str, name: str, *, text: str = "Hi"
) -> uuid.UUID:
    thread = await make_thread(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        contact_ref=ref,
        username=ref,
        display_name=name,
        texts=(text,),
    )
    return thread.contact_id


def fields_of(response: httpx.Response) -> list[str]:
    return [e["field"] for e in response.json().get("errors", [])]


async def test_the_list_newest_activity_first_with_paging(engine: AsyncEngine, ws: Ws) -> None:
    ids = [await person(engine, ws, f"p{i}", f"Person {i}") for i in range(3)]
    first = await ws.ok("GET", "/contacts", params={"limit": 2})
    assert len(first["items"]) == 2
    assert first["next_cursor"]
    rest = await ws.ok("GET", "/contacts", params={"limit": 2, "cursor": first["next_cursor"]})
    seen = [c["id"] for c in first["items"] + rest["items"]]
    assert sorted(seen) == sorted(str(i) for i in ids)
    assert rest["next_cursor"] is None
    item = first["items"][0]
    assert item["platform"] == "instagram"
    assert item["conversation_id"] is not None
    assert item["last_activity_at"] is not None


async def test_search_by_name_username_email_or_phone(engine: AsyncEngine, ws: Ws) -> None:
    priya = await person(engine, ws, "priya.bakes", "Priya Shah")
    await person(engine, ws, "rahul.k", "Rahul Kumar")
    await ws.ok("PATCH", f"/contacts/{priya}", json={"email": "Priya@Example.com"})
    for term in ("priya", "@priya.bakes", "example.com"):
        found = await ws.ok("GET", "/contacts", params={"q": term})
        assert [c["id"] for c in found["items"]] == [str(priya)], term


async def test_tags_are_unique_counted_and_filterable(engine: AsyncEngine, ws: Ws) -> None:
    a = await person(engine, ws, "a", "Asha")
    b = await person(engine, ws, "b", "Bina")
    vip = await ws.ok("POST", "/tags", 201, json={"name": "VIP", "color": 2})
    lead = await ws.ok("POST", "/tags", 201, json={"name": "Lead"})
    duplicate = await ws.call("POST", "/tags", json={"name": "vip"})
    assert duplicate.status_code == 409

    record = await ws.ok("POST", f"/contacts/{a}/tags", json={"add": [vip["id"], lead["id"]]})
    assert [t["name"] for t in record["tags"]] == ["Lead", "VIP"]
    bulk = await ws.ok(
        "POST", "/contacts/bulk-tags", json={"contact_ids": [str(a), str(b)], "add": [lead["id"]]}
    )
    assert bulk == {"updated": 2}

    listed = {t["name"]: t["contact_count"] for t in (await ws.ok("GET", "/tags"))["items"]}
    assert listed == {"Lead": 2, "VIP": 1}
    both = await ws.ok("GET", "/contacts", params=[("tag_id", vip["id"]), ("tag_id", lead["id"])])
    assert [c["id"] for c in both["items"]] == [str(a)]

    await ws.ok("POST", f"/contacts/{a}/tags", json={"remove": [vip["id"]]})
    assert (await ws.ok("GET", "/contacts", params={"tag_id": vip["id"]}))["items"] == []
    await ws.ok("DELETE", f"/tags/{lead['id']}", 204)
    assert (await ws.ok("GET", f"/contacts/{b}"))["tags"] == []
    missing = await ws.call("POST", f"/contacts/{a}/tags", json={"add": [str(uuid.uuid4())]})
    assert missing.status_code == 404


async def test_email_and_phone_are_normalised(engine: AsyncEngine, ws: Ws) -> None:
    c = await person(engine, ws, "c", "Chetan")
    record = await ws.ok(
        "PATCH", f"/contacts/{c}", json={"email": " Chetan@Mail.COM ", "phone": "98765 43210"}
    )
    assert (record["email"], record["phone"]) == ("chetan@mail.com", "+919876543210")
    assert (record["email_source"], record["email_verified"]) == ("member", False)
    bad = await ws.call("PATCH", f"/contacts/{c}", json={"email": "not-an-email", "phone": "12345"})
    assert bad.status_code == 422
    assert sorted(fields_of(bad)) == ["email", "phone"]
    cleared = await ws.ok("PATCH", f"/contacts/{c}", json={"clear_email": True})
    assert cleared["email"] is None
    assert (await ws.ok("GET", "/contacts", params={"has_phone": "true"}))["items"][0]["id"] == str(
        c
    )


async def test_custom_fields_validate_by_type_and_go_with_their_definition(
    engine: AsyncEngine, ws: Ws
) -> None:
    c = await person(engine, ws, "d", "Divya")
    await ws.ok("POST", "/contact-fields", 201, json={"key": "city", "label": "City"})
    await ws.ok(
        "POST",
        "/contact-fields",
        201,
        json={"key": "size", "label": "Size", "type": "choice", "options": ["S", "M", "L"]},
    )
    birthday = await ws.ok(
        "POST",
        "/contact-fields",
        201,
        json={"key": "birthday", "label": "Birthday", "type": "date"},
    )
    clash = await ws.call("POST", "/contact-fields", json={"key": "city", "label": "Town"})
    assert clash.status_code == 409
    no_options = await ws.call(
        "POST", "/contact-fields", json={"key": "tier", "label": "Tier", "type": "choice"}
    )
    assert no_options.status_code == 422

    record = await ws.ok(
        "PATCH",
        f"/contacts/{c}",
        json={"fields": {"city": "Pune", "size": "M", "birthday": "1994-05-02"}},
    )
    assert record["fields"] == {"city": "Pune", "size": "M", "birthday": "1994-05-02"}
    bad = await ws.call(
        "PATCH", f"/contacts/{c}", json={"fields": {"size": "XXL", "nope": "x", "birthday": "May"}}
    )
    assert bad.status_code == 422
    assert sorted(fields_of(bad)) == ["fields.birthday", "fields.nope", "fields.size"]
    removed = await ws.ok("PATCH", f"/contacts/{c}", json={"fields": {"city": None}})
    assert "city" not in removed["fields"]

    other = await person(engine, ws, "d2", "Dev")
    await ws.ok("PATCH", f"/contacts/{other}", json={"fields": {"city": "Mumbai"}})
    # c's city was removed above; their size is M.
    for match, expected in (("city:MUMBAI", [other]), ("city:*", [other]), ("size:m", [c])):
        found = await ws.ok("GET", "/contacts", params={"field": match})
        assert sorted(x["id"] for x in found["items"]) == sorted(map(str, expected)), match
    both = await ws.ok("GET", "/contacts", params=[("field", "city:*"), ("field", "size:m")])
    assert both["items"] == []
    unknown = await ws.call("GET", "/contacts", params={"field": "shoe:9"})
    assert (unknown.status_code, fields_of(unknown)) == (422, ["field"])
    assert (await ws.call("GET", "/contacts", params={"field": "city"})).status_code == 422

    await ws.ok("DELETE", f"/contact-fields/{birthday['id']}", 204)
    assert "birthday" not in (await ws.ok("GET", f"/contacts/{c}"))["fields"]
    listed = await ws.ok("GET", "/contact-fields")
    assert [d["key"] for d in listed["items"]] == ["city", "size"]


async def test_the_plan_caps_custom_fields(engine: AsyncEngine, ws: Ws) -> None:
    listed = await ws.ok("GET", "/contact-fields")
    limit = listed["limit"]
    assert limit == 5  # Free (proposed, PD decisions)
    for i in range(limit):
        await ws.ok("POST", "/contact-fields", 201, json={"key": f"f{i}", "label": f"Field {i}"})
    over = await ws.call("POST", "/contact-fields", json={"key": "extra", "label": "Extra"})
    assert over.status_code == 402
    assert (over.json()["entitlement"], over.json()["limit"]) == ("contact_fields", 5)
    await set_plan(engine, ws.wid, "pro")
    await ws.ok("POST", "/contact-fields", 201, json={"key": "extra", "label": "Extra"})


async def test_consent_history_and_filter(engine: AsyncEngine, ws: Ws) -> None:
    c = await person(engine, ws, "e", "Esha")
    other = await person(engine, ws, "f", "Farah")
    record = await ws.ok(
        "POST",
        f"/contacts/{c}/consents",
        json={"channel": "whatsapp", "status": "granted", "note": "Signed up at the counter"},
    )
    [consent] = record["consents"]
    assert (consent["channel"], consent["status"], consent["source"], consent["note"]) == (
        "whatsapp",
        "granted",
        "member",
        "Signed up at the counter",
    )
    granted = await ws.ok("GET", "/contacts", params={"marketing_consent": "whatsapp"})
    assert [x["id"] for x in granted["items"]] == [str(c)]
    await ws.ok(
        "POST",
        f"/contacts/{c}/consents",
        json={"channel": "whatsapp", "status": "revoked", "note": "Asked us to stop"},
    )
    assert (await ws.ok("GET", "/contacts", params={"marketing_consent": "whatsapp"}))[
        "items"
    ] == []
    assert (await ws.ok("GET", f"/contacts/{other}"))["consents"] == []


async def test_the_csv_export(engine: AsyncEngine, ws: Ws) -> None:
    c = await person(engine, ws, "g", "=HYPERLINK(evil)")
    await person(engine, ws, "h", "Harsh")
    await ws.ok("POST", "/contact-fields", 201, json={"key": "city", "label": "City"})
    vip = await ws.ok("POST", "/tags", 201, json={"name": "VIP"})
    await ws.ok("POST", f"/contacts/{c}/tags", json={"add": [vip["id"]]})
    await ws.ok(
        "PATCH", f"/contacts/{c}", json={"email": "g@example.com", "fields": {"city": "Goa"}}
    )

    response = await ws.call("GET", "/contacts/export.csv", params={"tag_id": vip["id"]})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0][-1] == "City"
    assert len(rows) == 2
    row = dict(zip(rows[0], rows[1], strict=True))
    assert row["Name"] == "'=HYPERLINK(evil)"  # a formula is defused
    assert (row["Email"], row["Tags"], row["City"]) == ("g@example.com", "VIP", "Goa")


async def test_a_contact_of_nobody_is_not_found(ws: Ws) -> None:
    assert (await ws.call("GET", f"/contacts/{uuid.uuid4()}")).status_code == 404
    assert (
        await ws.call("PATCH", f"/contacts/{uuid.uuid4()}", json={"email": "x@y.zz"})
    ).status_code == 404
