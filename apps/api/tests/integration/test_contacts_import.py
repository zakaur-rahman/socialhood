"""GR-43: contact import from CSV on a WhatsApp number. The preview saves nothing; new numbers are
created, existing contacts only get blanks filled and tags added; consent is granted only when the
admin ticked the box, never over a withdrawal, with evidence; a file exported from the account
imports back as no change."""

from __future__ import annotations

import csv
import io
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.services import contacts_import
from tests.support.api import Clerk
from tests.support.broadcasts import Shop, shop

FILE = "\n".join(
    [
        "Phone,Name,Email,Tags,City,WhatsApp marketing",
        "+91 98765 43210,Asha Rao,Asha@Example.com,vip; march,Goa,yes",
        "9812345678,Ben Cole,,vip,,",
        "not a number,Nobody,,,,yes",
        "+919876543210,Asha again,,,,",
    ]
)


@pytest.fixture
async def desk(
    client: httpx.AsyncClient,
    clerk: Clerk,
    app: FastAPI,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Shop:
    desk = await shop(client, clerk, app, engine, redis, monkeypatch)
    await desk.ws.ok("POST", "/contact-fields", 201, json={"key": "city", "label": "City"})
    return desk


def body(desk: Shop, csv_text: str = FILE, *, tick: bool = False, **more: Any) -> dict[str, Any]:
    return {
        "account_id": desk.ws.account_id,
        "csv": csv_text,
        "grant_consent": tick,
        "file_name": "people.csv",
        **more,
    }


async def run(desk: Shop, csv_text: str = FILE, *, tick: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = await desk.ws.ok(
        "POST", "/contacts/import", json=body(desk, csv_text, tick=tick)
    )
    return result


async def consents(desk: Shop, wa_id: str) -> list[dict[str, Any]]:
    return await desk.rows(
        "SELECT k.status, k.source, k.evidence FROM contact_consents k"
        " JOIN contacts c ON c.id = k.contact_id WHERE c.platform_user_id = :w"
        " ORDER BY k.occurred_at, k.created_at",
        w=wa_id,
    )


async def test_the_preview_says_what_would_happen_and_saves_nothing(desk: Shop) -> None:
    preview = await desk.ws.ok("POST", "/contacts/import/preview", json=body(desk, tick=True))
    assert (preview["created"], preview["updated"], preview["skipped"]) == (2, 0, 2)
    assert preview["consents_granted"] == 1
    assert preview["tags_created"] == 2
    assert preview["ignored_columns"] == []
    by_line = {r["line"]: r for r in preview["rows"]}
    assert [by_line[n]["action"] for n in (2, 3, 4, 5)] == ["create", "create", "skip", "skip"]
    assert by_line[5]["reasons"] == [contacts_import.COPY["phone_twice"]]
    assert (await desk.ws.ok("GET", "/contacts"))["items"] == []


async def test_the_import_creates_contacts_with_tags_fields_and_consent_evidence(
    desk: Shop,
) -> None:
    result = await run(desk, tick=True)
    assert (result["created"], result["skipped"], result["consents_granted"]) == (2, 2, 1)

    [asha] = (await desk.ws.ok("GET", "/contacts", params={"q": "Asha"}))["items"]
    record = await desk.ws.ok("GET", f"/contacts/{asha['id']}")
    assert (record["phone"], record["email"], record["fields"]) == (
        "+919876543210",
        "asha@example.com",
        {"city": "Goa"},
    )
    assert sorted(t["name"] for t in record["tags"]) == ["march", "vip"]
    [consent] = await consents(desk, "919876543210")
    assert (consent["status"], consent["source"]) == ("granted", "import")
    assert consent["evidence"]["file_name"] == "people.csv"
    assert consent["evidence"]["row"] == 2
    assert consent["evidence"]["imported_by"] == desk.ws.user_id
    assert consent["evidence"]["imported_at"]
    assert await consents(desk, "919812345678") == []  # said nothing about marketing
    [audit] = await desk.rows("SELECT detail FROM audit_events WHERE action = 'contacts.imported'")
    assert audit["detail"]["created"] == 2


async def test_without_the_tick_the_marketing_column_is_ignored(desk: Shop) -> None:
    preview = await desk.ws.ok("POST", "/contacts/import/preview", json=body(desk))
    assert (preview["consents_granted"], preview["consent_ignored"]) == (0, 1)
    await run(desk)
    assert await consents(desk, "919876543210") == []


async def test_an_existing_contact_only_gets_blanks_filled_and_tags_added(desk: Shop) -> None:
    await run(desk, "Phone,Name,Email,City\n+919876543210,Typed Name,typed@example.com,Pune\n")
    result = await run(desk, "Phone,Name,Email,Tags,City\n+919876543210,Other,o@x.com,new,Goa\n")
    assert (result["created"], result["updated"]) == (0, 1)
    [contact] = (await desk.ws.ok("GET", "/contacts"))["items"]
    record = await desk.ws.ok("GET", f"/contacts/{contact['id']}")
    assert (record["name"], record["email"], record["fields"]) == (
        "Typed Name",
        "typed@example.com",
        {"city": "Pune"},
    )
    assert [t["name"] for t in record["tags"]] == ["new"]


async def test_a_stop_reply_stays_opted_out_after_an_import_that_says_yes(desk: Shop) -> None:
    wa = "919876543210"
    await run(desk, tick=True)
    response = await desk.inject(kind="dm", from_id=wa, from_username="Asha", text="STOP")
    assert response.status_code == 200, response.text
    await desk.process_webhooks()
    assert (await consents(desk, wa))[-1]["status"] == "revoked"

    preview = await desk.ws.ok("POST", "/contacts/import/preview", json=body(desk, tick=True))
    assert preview["consents_kept_withdrawn"] == 1
    result = await run(desk, tick=True)
    assert result["consents_granted"] == 0
    assert [(c["status"], c["source"]) for c in await consents(desk, wa)] == [
        ("granted", "import"),
        ("revoked", "stop_reply"),
    ]


async def test_exporting_and_importing_back_changes_nothing(desk: Shop) -> None:
    await run(desk, tick=True)
    exported = (await desk.ws.call("GET", "/contacts/export.csv")).text
    again = await desk.ws.ok(
        "POST", "/contacts/import/preview", json=body(desk, exported, tick=True)
    )
    assert (again["created"], again["updated"], again["skipped"]) == (0, 0, 0)
    assert again["unchanged"] == len(list(csv.reader(io.StringIO(exported)))) - 1
    assert again["tags_created"] == 0


async def test_only_whatsapp_accounts_take_an_import(desk: Shop, client: httpx.AsyncClient) -> None:
    instagram = await client.post(
        f"/v1/w/{desk.ws.wid}/dev/sandbox/accounts", headers=desk.ws.headers
    )
    response = await desk.ws.call(
        "POST", "/contacts/import", json=body(desk, account_id=instagram.json()["id"])
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "account_id"


async def test_only_admins_can_import(desk: Shop, engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w"),
            {"w": desk.ws.wid},
        )
    for path in ("/contacts/import/preview", "/contacts/import"):
        assert (await desk.ws.call("POST", path, json=body(desk))).status_code == 403, path


async def test_a_file_needs_a_phone_column_and_at_most_5000_rows(desk: Shop) -> None:
    no_phone = await desk.ws.call("POST", "/contacts/import", json=body(desk, "Name\nAsha\n"))
    assert no_phone.status_code == 422
    big = "Phone\n" + "\n".join(f"+9198{n:08d}" for n in range(contacts_import.MAX_ROWS + 1))
    too_many = await desk.ws.call("POST", "/contacts/import/preview", json=body(desk, big))
    assert too_many.status_code == 422
    assert contacts_import.COPY["too_many"].format(cap=5000) in too_many.text
