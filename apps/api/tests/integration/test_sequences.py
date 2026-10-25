"""GR-24: sequences on the sandbox. Done when a three-day sequence sends day 1 and day 3 to an
opted-in sandbox contact and stops when they reply.

Also: entry (a tag, a reply to a broadcast), once at a time, re-entry, the stop rules (a reply, a
tag, a stage), the 24-hour window and consent on WhatsApp, Instagram sending only while the window
is open, business hours holding a step, the number's daily limit shared with broadcasts and the
quality pause, a step sending once, the plan's limits, the editing rules, Activity, the contact's
timeline and sequences, and roles.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.auth.invitations import FakeInvitationSender, use_invitation_sender
from socialhood.jobs.tasks import send as send_tasks
from socialhood.jobs.tasks import sequences as sequence_jobs
from socialhood.platforms.sandbox import outbox
from socialhood.services.broadcasts import throttle
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan
from tests.support.broadcasts import TEMPLATE, VARIABLES, Customer, Shop, shop
from tests.support.inbox import make_thread
from tests.support.sending import clean_outbox, context

DAY = 86400


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


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
    return await shop(client, clerk, app, engine, redis, monkeypatch)


def step(
    delay: int, *, text: str | None = None, template: bool = False, entry: bool = False, **more: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {"delay_seconds": delay, "delay_from": "entry" if entry else "previous"}
    if text:
        body["text"] = text
    if template:
        body.update(template_name=TEMPLATE, template_language="en", variables=VARIABLES)
    return {**body, **more}


async def tag(desk: Shop, name: str = "Follow up") -> str:
    made = await desk.ws.ok("POST", "/tags", 201, json={"name": name})
    return str(made["id"])


def body(
    desk: Shop, tag_id: str, steps: list[dict[str, Any]] | None = None, **more: Any
) -> dict[str, Any]:
    """Day 1, day 3 and day 5 by default: a template each (the 24-hour window is long closed)."""
    base: dict[str, Any] = {
        "name": "Three days",
        "social_account_id": desk.ws.account_id,
        "entry": {"type": "tagged", "tag_id": tag_id},
        "steps": steps
        or [
            step(DAY, template=True, text="Hi {first_name}, thanks for stopping by."),
            step(3 * DAY, template=True, entry=True),
            step(2 * DAY, template=True),
        ],
    }
    return {**base, **more}


async def running(
    desk: Shop, tag_id: str, steps: list[dict[str, Any]] | None = None, **more: Any
) -> dict[str, Any]:
    created = await desk.ws.ok("POST", "/sequences", 201, json=body(desk, tag_id, steps, **more))
    return await desk.ws.ok("POST", f"/sequences/{created['id']}/activate")


async def enter(desk: Shop, contact: Customer, tag_id: str) -> None:
    await desk.ws.ok("POST", f"/contacts/{contact.contact_id}/tags", json={"add": [tag_id]})


async def sweep(desk: Shop, now: datetime) -> dict[str, int]:
    return dict(await sequence_jobs.sweep(desk.maker, desk.redis, desk.deps, now=now))


async def deliver(desk: Shop) -> int:
    """Run send_message for every queued automation message, as the worker would."""
    queued = await desk.rows(
        "SELECT id, conversation_id FROM messages"
        " WHERE source = 'automation' AND status = 'queued' ORDER BY created_at"
    )
    for row in queued:
        await send_tasks.send_message(
            context(),
            message_id=str(row["id"]),
            conversation_id=str(row["conversation_id"]),
            workspace_id=desk.ws.wid,
        )
    return len(queued)


async def people(desk: Shop, sequence_id: str, **query: Any) -> list[dict[str, Any]]:
    page = await desk.ws.ok("GET", f"/sequences/{sequence_id}/enrolments", params=query)
    return list(page["items"])


async def reply(desk: Shop, who: Customer, said: str = "Yes please") -> None:
    sent = await desk.inject(kind="dm", text=said, from_id=who.wa_id, from_username=who.name)
    assert sent.status_code == 200, sent.text
    await desk.process_webhooks()


# ---------------------------------------------------------------- the done-when


async def test_a_three_day_sequence_sends_day_one_and_day_three_and_stops_when_they_reply(
    desk: Shop,
) -> None:
    asha = await desk.customer("Asha Rao")  # agreed to WhatsApp marketing
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id)
    assert sequence["status"] == "active"
    assert sequence["step_count"] == 3
    await enter(desk, asha, tag_id)

    [person] = await people(desk, sequence["id"])
    assert (person["status"], person["next_step"], person["step_count"]) == ("active", 1, 3)
    assert person["entry_event"] == "Tagged Follow up"
    start = datetime.now(UTC)

    # Nothing is due before day 1.
    assert await sweep(desk, start + timedelta(hours=23)) == {}

    # Day 1: the 24-hour window has closed, so the template goes.
    assert await sweep(desk, start + timedelta(hours=25)) == {"sent": 1}
    assert await deliver(desk) == 1
    [first] = [s for s in outbox.SENT if s.message.template is not None]
    assert first.message.template.name == TEMPLATE
    assert first.message.template.params[0] == "Asha"
    assert first.recipient_ref == asha.wa_id

    # Day 3 (counted from entry), not before.
    assert await sweep(desk, start + timedelta(days=2, hours=23)) == {}
    assert await sweep(desk, start + timedelta(days=3, hours=1)) == {"sent": 1}
    assert await deliver(desk) == 1
    assert len([s for s in outbox.SENT if s.message.template is not None]) == 2

    # The contact replies: the sequence stops, so day 5 is never sent.
    await reply(desk, asha)
    [stopped] = await people(desk, sequence["id"])
    assert (stopped["status"], stopped["stop_reason"]) == ("stopped", "reply")
    assert stopped["stop_text"] == "They replied"
    assert stopped["next_due_at"] is None
    assert await sweep(desk, start + timedelta(days=9)) == {}
    assert len([s for s in outbox.SENT if s.message.template is not None]) == 2

    # Every step is on the record, sent as automation messages.
    runs = await desk.rows(
        "SELECT position, status, sent_as FROM sequence_step_runs ORDER BY position"
    )
    assert runs == [
        {"position": 0, "status": "sent", "sent_as": "template"},
        {"position": 1, "status": "sent", "sent_as": "template"},
    ]
    sources = await desk.rows("SELECT DISTINCT source FROM messages WHERE template IS NOT NULL")
    assert sources == [{"source": "automation"}]
    counts = (await desk.ws.ok("GET", f"/sequences/{sequence['id']}"))["enrolments"]
    assert counts == {"active": 0, "completed": 0, "stopped": 1}


async def test_a_sequence_that_runs_out_of_steps_is_completed(desk: Shop) -> None:
    ben = await desk.customer("Ben Cole")
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id, [step(60, text="Hello again, {first_name}.")])
    await enter(desk, ben, tag_id)
    assert await sweep(desk, datetime.now(UTC) + timedelta(minutes=5)) == {"sent": 1}
    [done] = await people(desk, sequence["id"])
    assert (done["status"], done["next_step"]) == ("completed", None)
    [message] = await desk.rows("SELECT text FROM messages WHERE source = 'automation'")
    assert message["text"] == "Hello again, Ben."


# ---------------------------------------------------------------- the window and consent


async def test_a_template_needs_marketing_consent_and_a_skipped_step_moves_on(desk: Shop) -> None:
    never = await desk.customer("Chitra Iyer", consent=None)
    left = await desk.customer("Dev Nair", consent="revoked")
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id, [step(DAY, template=True), step(DAY, template=True)])
    await enter(desk, never, tag_id)
    await enter(desk, left, tag_id)
    start = datetime.now(UTC)
    assert await sweep(desk, start + timedelta(hours=25)) == {"skipped": 2}
    assert [s for s in outbox.SENT if s.message.template is not None] == []
    reasons = {
        r["contact"]["display_name"]: r["last_run"] for r in await people(desk, sequence["id"])
    }
    assert reasons["Chitra Iyer"]["status"] == "skipped"
    assert reasons["Chitra Iyer"]["reason"] == "They haven't agreed to WhatsApp marketing messages."
    assert reasons["Dev Nair"]["reason"] == "They opted out of WhatsApp marketing messages."
    # The sequence goes on: the second step is skipped a day later, and both are finished.
    assert await sweep(desk, start + timedelta(days=3)) == {"skipped": 2}
    assert {p["status"] for p in await people(desk, sequence["id"])} == {"completed"}


async def test_text_inside_the_window_goes_without_consent_and_text_outside_it_is_skipped(
    desk: Shop,
) -> None:
    quiet = await desk.customer("Esha Rao", consent=None)  # wrote an hour ago, never opted in
    tag_id = await tag(desk)
    sequence = await running(
        desk,
        tag_id,
        [step(600, text="Still interested, {first_name}?"), step(DAY, text="Last call")],
    )
    await enter(desk, quiet, tag_id)
    start = datetime.now(UTC)
    assert await sweep(desk, start + timedelta(minutes=11)) == {"sent": 1}  # inside the window
    assert await deliver(desk) == 1
    [message] = await desk.rows("SELECT text, template FROM messages WHERE source = 'automation'")
    assert message["template"] in (None, {})
    assert message["text"] == "Still interested, Esha?"
    # A day on, the window is closed and the step has no template.
    assert await sweep(desk, start + timedelta(days=1, hours=2)) == {"skipped": 1}
    [last] = [p["last_run"] for p in await people(desk, sequence["id"])]
    assert "no template" in last["reason"]


async def test_whatsapp_marketing_stays_off_until_the_legal_check(
    desk: Shop, monkeypatch: pytest.MonkeyPatch
) -> None:
    asha = await desk.customer("Asha Rao")
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id, [step(DAY, template=True)])
    await enter(desk, asha, tag_id)
    monkeypatch.setattr(desk.app.state.settings, "broadcasts_enabled", False)
    assert await sweep(desk, datetime.now(UTC) + timedelta(hours=25)) == {"skipped": 1}
    [run] = [p["last_run"] for p in await people(desk, sequence["id"])]
    assert run["reason"] == "WhatsApp marketing messages are switched off for now."


async def test_instagram_steps_run_only_while_the_window_is_open(desk: Shop) -> None:
    created = await desk.ws.client.post(
        f"/v1/w/{desk.ws.wid}/dev/sandbox/accounts", headers=desk.ws.headers
    )
    assert created.status_code == 201, created.text
    instagram = created.json()["id"]
    tag_id = await tag(desk)
    open_now = await make_thread(
        desk.engine,
        workspace_id=desk.ws.wid,
        account_id=instagram,
        display_name="Fay Open",
        last_inbound_at=datetime.now(UTC) - timedelta(hours=1),
    )
    long_ago = await make_thread(
        desk.engine,
        workspace_id=desk.ws.wid,
        account_id=instagram,
        display_name="Gus Closed",
        last_inbound_at=datetime.now(UTC) - timedelta(days=3),
    )
    sequence = await desk.ws.ok(
        "POST",
        "/sequences",
        201,
        json={
            **body(desk, tag_id, [step(300, text="Hi {first_name}, any questions?")]),
            "social_account_id": instagram,
        },
    )
    await desk.ws.ok("POST", f"/sequences/{sequence['id']}/activate")
    for thread in (open_now, long_ago):
        await desk.ws.ok("POST", f"/contacts/{thread.contact_id}/tags", json={"add": [tag_id]})
    assert await sweep(desk, datetime.now(UTC) + timedelta(minutes=10)) == {"sent": 1, "skipped": 1}
    by_name = {
        p["contact"]["display_name"]: p["last_run"] for p in await people(desk, sequence["id"])
    }
    assert by_name["Fay Open"]["status"] == "sent"
    assert by_name["Gus Closed"]["status"] == "skipped"
    assert "messaging window had closed" in by_name["Gus Closed"]["reason"]


# ---------------------------------------------------------------- entry and stop rules


async def test_a_contact_is_in_a_sequence_once_and_re_entry_is_a_setting(desk: Shop) -> None:
    asha = await desk.customer("Asha Rao")
    tag_id = await tag(desk)
    once = await running(desk, tag_id, [step(60, text="One")])
    await enter(desk, asha, tag_id)
    await desk.ws.ok("POST", f"/contacts/{asha.contact_id}/tags", json={"remove": [tag_id]})
    await enter(desk, asha, tag_id)  # tagged again while still in: nothing new
    assert len(await people(desk, once["id"])) == 1

    assert await sweep(desk, datetime.now(UTC) + timedelta(minutes=5)) == {"sent": 1}
    await desk.ws.ok("POST", f"/contacts/{asha.contact_id}/tags", json={"remove": [tag_id]})
    await enter(desk, asha, tag_id)  # finished: not again, re-entry is off
    assert len(await people(desk, once["id"])) == 1

    await desk.ws.ok("POST", f"/sequences/{once['id']}/pause")
    again = await desk.ws.ok(
        "PUT",
        f"/sequences/{once['id']}",
        json=body(desk, tag_id, [step(60, text="One")], allow_reentry=True),
    )
    assert again["allow_reentry"] is True
    await desk.ws.ok("POST", f"/sequences/{once['id']}/activate")
    await desk.ws.ok("POST", f"/contacts/{asha.contact_id}/tags", json={"remove": [tag_id]})
    await enter(desk, asha, tag_id)
    assert [p["status"] for p in await people(desk, once["id"])] == ["active", "completed"]


async def test_a_paused_sequence_takes_nobody_in_and_sends_nothing(desk: Shop) -> None:
    asha, ben = await desk.customer("Asha Rao"), await desk.customer("Ben Cole")
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id, [step(60, text="Hello")])
    await enter(desk, asha, tag_id)
    await desk.ws.ok("POST", f"/sequences/{sequence['id']}/pause")
    await enter(desk, ben, tag_id)
    assert len(await people(desk, sequence["id"])) == 1
    assert await sweep(desk, datetime.now(UTC) + timedelta(minutes=5)) == {}
    await desk.ws.ok("POST", f"/sequences/{sequence['id']}/activate")  # Asha carries on
    assert await sweep(desk, datetime.now(UTC) + timedelta(minutes=5)) == {"sent": 1}


async def test_a_stop_tag_and_a_stop_stage_stop_the_sequence(desk: Shop) -> None:
    asha, ben = await desk.customer("Asha Rao"), await desk.customer("Ben Cole")
    tag_id, stop_tag = await tag(desk), await tag(desk, "Bought")
    sequence = await running(
        desk,
        tag_id,
        [step(DAY, template=True)],
        stop={"on_reply": True, "tag_ids": [stop_tag], "stages": ["won"]},
    )
    assert sequence["stop"]["tag_names"] == ["Bought"]
    await enter(desk, asha, tag_id)
    await enter(desk, ben, tag_id)

    await desk.ws.ok("POST", f"/contacts/{asha.contact_id}/tags", json={"add": [stop_tag]})
    await desk.ws.ok(
        "POST", f"/contacts/{ben.contact_id}/lead-stage", json={"stage": "won", "note": "Paid"}
    )
    by_name = {p["contact"]["display_name"]: p for p in await people(desk, sequence["id"])}
    assert (by_name["Asha Rao"]["stop_reason"], by_name["Asha Rao"]["stop_text"]) == (
        "tag",
        "A stop tag was added: Bought",
    )
    assert by_name["Ben Cole"]["stop_text"] == "Their lead stage changed: Won"
    assert await sweep(desk, datetime.now(UTC) + timedelta(days=2)) == {}


async def test_a_sequence_can_ignore_replies(desk: Shop) -> None:
    asha = await desk.customer("Asha Rao")
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id, [step(DAY, template=True)], stop={"on_reply": False})
    await enter(desk, asha, tag_id)
    await reply(desk, asha)
    assert [p["status"] for p in await people(desk, sequence["id"])] == ["active"]


async def test_a_reply_to_a_broadcast_starts_a_sequence_and_does_not_stop_it(desk: Shop) -> None:
    asha = await desk.customer("Asha Rao")
    sequence = await desk.ws.ok(
        "POST",
        "/sequences",
        201,
        json={
            "name": "After the sale",
            "social_account_id": desk.ws.account_id,
            "entry": {"type": "broadcast_replied"},
            "steps": [step(DAY, template=True)],
        },
    )
    await desk.ws.ok("POST", f"/sequences/{sequence['id']}/activate")
    started = await desk.send_now()
    await desk.batch(started["id"])
    await desk.deliver_queued(send_tasks)
    await reply(desk, asha, "Is it still on?")
    [person] = await people(desk, sequence["id"])
    assert (person["status"], person["entry_event"]) == ("active", "Replied to a broadcast")


async def test_a_lead_capture_starts_a_sequence(desk: Shop) -> None:
    from socialhood.db.tenancy import workspace_scope
    from socialhood.models.inbox import Contact
    from socialhood.services.webhooks import events

    asha = await desk.customer("Asha Rao")
    sequence = await desk.ws.ok(
        "POST",
        "/sequences",
        201,
        json={
            "name": "After an email",
            "social_account_id": desk.ws.account_id,
            "entry": {"type": "captured", "capture_kind": "email"},
            "steps": [step(DAY, template=True)],
        },
    )
    await desk.ws.ok("POST", f"/sequences/{sequence['id']}/activate")
    with workspace_scope(uuid.UUID(desk.ws.wid)):
        async with desk.maker() as session:
            contact = await session.get(Contact, asha.contact_id)
            assert contact is not None
            await events.lead_captured(
                session,
                contact,
                kind="phone",  # not an email: this sequence waits for an email
                value="+919800000000",
                field_key=None,
                automation_id=uuid.uuid4(),
                automation_name="Lead magnet",
                run_id=uuid.uuid4(),
            )
            await session.commit()
    assert await people(desk, sequence["id"]) == []
    with workspace_scope(uuid.UUID(desk.ws.wid)):
        async with desk.maker() as session:
            contact = await session.get(Contact, asha.contact_id)
            assert contact is not None
            await events.lead_captured(
                session,
                contact,
                kind="email",
                value="asha@example.com",
                field_key=None,
                automation_id=uuid.uuid4(),
                automation_name="Lead magnet",
                run_id=uuid.uuid4(),
            )
            await session.commit()
    [person] = await people(desk, sequence["id"])
    assert person["entry_event"] == "Gave their email"


# ---------------------------------------------------------------- holds and limits


async def test_a_step_held_to_business_hours_waits_for_the_next_opening(desk: Shop) -> None:
    asha = await desk.customer("Asha Rao")
    other_day = (datetime.now(UTC).weekday() + 3) % 7  # a day that is not today (any zone)
    await desk.ws.ok(
        "PUT",
        "/business-hours",
        json={
            "enabled": True,
            "days": [{"day": other_day, "ranges": [{"start": "09:00", "end": "10:00"}]}],
            "away_enabled": False,
            "auto_mode": "always",
        },
    )
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id, [step(60, text="Hello", respect_hours=True)])
    await enter(desk, asha, tag_id)
    now = datetime.now(UTC) + timedelta(minutes=5)
    assert await sweep(desk, now) == {"held": 1}
    [person] = await people(desk, sequence["id"])
    assert person["status"] == "active"
    assert datetime.fromisoformat(person["next_due_at"]) > now
    assert await desk.rows("SELECT id FROM sequence_step_runs") == []


async def test_template_steps_share_the_numbers_daily_limit_with_broadcasts(
    desk: Shop, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(throttle.TIER_LIMITS, "TIER_1K", 1)  # the sandbox number reads as TIER_1K
    asha, ben = await desk.customer("Asha Rao"), await desk.customer("Ben Cole")
    tag_id = await tag(desk)
    await running(desk, tag_id, [step(DAY, template=True)])
    await enter(desk, asha, tag_id)
    await enter(desk, ben, tag_id)
    late = datetime.now(UTC) + timedelta(hours=25)
    assert await sweep(desk, late) == {"sent": 1, "held": 1}
    held = await desk.rows("SELECT next_due_at FROM sequence_enrolments WHERE status = 'active'")
    assert held[0]["next_due_at"] > late  # until a place frees in the 24-hour window


async def test_a_template_waits_while_the_numbers_quality_is_low(desk: Shop) -> None:
    asha = await desk.customer("Asha Rao")
    tag_id = await tag(desk)
    await running(desk, tag_id, [step(DAY, template=True)])
    await enter(desk, asha, tag_id)
    async with desk.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO whatsapp_number_health (workspace_id, social_account_id,"
                " quality_rating, checked_at) VALUES (:w, :a, 'red', now())"
                " ON CONFLICT (social_account_id) DO UPDATE SET quality_rating = 'red',"
                " checked_at = now()"
            ),
            {"w": desk.ws.wid, "a": desk.ws.account_id},
        )
    late = datetime.now(UTC) + timedelta(hours=25)
    assert await sweep(desk, late) == {"held": 1}
    assert [s for s in outbox.SENT if s.message.template is not None] == []


async def test_a_step_is_sent_once_however_often_it_is_run(desk: Shop) -> None:
    asha = await desk.customer("Asha Rao")
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id, [step(60, text="Hello"), step(DAY, text="Again")])
    await enter(desk, asha, tag_id)
    now = datetime.now(UTC) + timedelta(minutes=5)
    assert await sweep(desk, now) == {"sent": 1}
    assert await sweep(desk, now) == {}  # the next step is a day away
    # A second worker meeting the same step finds its run row and only moves on.
    [row] = await desk.rows("SELECT id FROM sequence_enrolments")
    async with desk.engine.begin() as conn:
        await conn.execute(
            text("UPDATE sequence_enrolments SET current_step = 0, next_due_at = :t WHERE id = :i"),
            {"t": now, "i": row["id"]},
        )
    assert await sweep(desk, now) == {"advanced": 1}
    messages = await desk.rows("SELECT id FROM messages WHERE source = 'automation'")
    assert len(messages) == 1
    [person] = await people(desk, sequence["id"])
    assert person["next_step"] == 2


async def test_an_account_that_needs_reconnecting_is_left_alone(desk: Shop) -> None:
    asha = await desk.customer("Asha Rao")
    tag_id = await tag(desk)
    await running(desk, tag_id, [step(60, text="Hello")])
    await enter(desk, asha, tag_id)
    async with desk.engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET status = 'needs_reconnect' WHERE id = :a"),
            {"a": desk.ws.account_id},
        )
    assert await sweep(desk, datetime.now(UTC) + timedelta(minutes=5)) == {}
    async with desk.engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET status = 'active' WHERE id = :a"),
            {"a": desk.ws.account_id},
        )
    assert await sweep(desk, datetime.now(UTC) + timedelta(minutes=5)) == {"sent": 1}


# ---------------------------------------------------------------- the routes


async def test_saving_checks_the_steps_the_account_and_the_workspace(desk: Shop) -> None:
    tag_id = await tag(desk)
    gone = await desk.ws.call(
        "POST",
        "/sequences",
        json=body(desk, tag_id, [step(60, template=True, template_name="nope")]),
    )
    assert gone.status_code == 422
    assert gone.json()["errors"][0]["field"] == "steps.0.template_name"
    wrong_vars = await desk.ws.call(
        "POST",
        "/sequences",
        json=body(desk, tag_id, [step(60, template=True, variables=[VARIABLES[0]])]),
    )
    assert wrong_vars.status_code == 422
    long_text = await desk.ws.call(
        "POST", "/sequences", json=body(desk, tag_id, [step(60, text="x" * 1001)])
    )
    assert long_text.status_code == 422
    stranger = await desk.ws.call(
        "POST",
        "/sequences",
        json={**body(desk, tag_id), "entry": {"type": "tagged", "tag_id": str(uuid.uuid4())}},
    )
    assert (stranger.status_code, stranger.json()["code"]) == (404, "not_found")
    foreign = await desk.ws.call(
        "POST", "/sequences", json={**body(desk, tag_id), "social_account_id": str(uuid.uuid4())}
    )
    assert foreign.status_code == 404


async def test_only_whatsapp_has_templates_and_broadcasts(desk: Shop) -> None:
    created = await desk.ws.client.post(
        f"/v1/w/{desk.ws.wid}/dev/sandbox/accounts", headers=desk.ws.headers
    )
    instagram = created.json()["id"]
    tag_id = await tag(desk)
    with_template = await desk.ws.call(
        "POST",
        "/sequences",
        json={**body(desk, tag_id, [step(60, template=True)]), "social_account_id": instagram},
    )
    assert with_template.status_code == 422
    assert with_template.json()["errors"][0]["message"] == "Only WhatsApp has templates."
    on_broadcast = await desk.ws.call(
        "POST",
        "/sequences",
        json={
            "name": "x",
            "social_account_id": instagram,
            "entry": {"type": "broadcast_replied"},
            "steps": [step(60, text="Hi")],
        },
    )
    assert on_broadcast.status_code == 422


async def test_an_active_sequence_cannot_be_changed_or_deleted(desk: Shop) -> None:
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id, [step(60, text="Hi")])
    changed = await desk.ws.call("PUT", f"/sequences/{sequence['id']}", json=body(desk, tag_id))
    assert (changed.status_code, changed.json()["code"]) == (409, "conflict")
    assert (await desk.ws.call("DELETE", f"/sequences/{sequence['id']}")).status_code == 409
    await desk.ws.ok("POST", f"/sequences/{sequence['id']}/pause")
    await desk.ws.ok("PUT", f"/sequences/{sequence['id']}", json=body(desk, tag_id))
    await desk.ws.ok("DELETE", f"/sequences/{sequence['id']}", 204)
    assert (await desk.ws.ok("GET", "/sequences"))["items"] == []


async def test_a_deleted_start_tag_is_a_problem_that_stops_activation(desk: Shop) -> None:
    tag_id = await tag(desk)
    created = await desk.ws.ok("POST", "/sequences", 201, json=body(desk, tag_id))
    await desk.ws.ok("DELETE", f"/tags/{tag_id}", 204)
    detail = await desk.ws.ok("GET", f"/sequences/{created['id']}")
    assert detail["problems"] == ["The tag that starts this sequence was deleted. Choose another."]
    refused = await desk.ws.call("POST", f"/sequences/{created['id']}/activate")
    assert refused.status_code == 422


async def test_the_plans_limits_apply(desk: Shop) -> None:
    await set_plan(desk.engine, desk.ws.wid, "free")
    tag_id = await tag(desk)
    too_many = await desk.ws.call(
        "POST", "/sequences", json=body(desk, tag_id, [step(60, text="a")] * 4)
    )
    assert too_many.status_code == 402
    assert (too_many.json()["code"], too_many.json()["entitlement"], too_many.json()["limit"]) == (
        "quota_exceeded",
        "sequence_steps",
        3,
    )
    first = await desk.ws.ok(
        "POST", "/sequences", 201, json=body(desk, tag_id, [step(60, text="a")])
    )
    second = await desk.ws.ok(
        "POST", "/sequences", 201, json=body(desk, tag_id, [step(60, text="b")])
    )
    await desk.ws.ok("POST", f"/sequences/{first['id']}/activate")
    blocked = await desk.ws.call("POST", f"/sequences/{second['id']}/activate")
    assert (blocked.status_code, blocked.json()["entitlement"], blocked.json()["limit"]) == (
        402,
        "active_sequences",
        1,
    )
    listed = await desk.ws.ok("GET", "/sequences")
    assert (listed["active"], listed["active_limit"], listed["step_limit"]) == (1, 1, 3)
    await set_plan(desk.engine, desk.ws.wid, "pro")
    await desk.ws.ok("POST", f"/sequences/{second['id']}/activate")


async def test_the_preview_shows_when_each_step_goes_and_what(desk: Shop) -> None:
    tag_id = await tag(desk)
    preview = await desk.ws.ok(
        "POST",
        "/sequences/preview",
        json=body(
            desk,
            tag_id,
            [
                step(600, text="Hi {first_name}, thanks for stopping by."),
                step(DAY, template=True, text="Hi again"),
                step(2 * DAY, text="Only text"),
            ],
        ),
    )
    steps = preview["steps"]
    assert [(s["position"], s["after_seconds"], s["sends"]) for s in steps] == [
        (0, 600, "text"),
        (1, 600 + DAY, "template"),
        (2, 600 + 3 * DAY, "nothing"),
    ]
    assert steps[0]["text"] == "Hi Priya, thanks for stopping by."
    assert "agreed to WhatsApp marketing" in steps[1]["note"]
    assert "no template" in steps[2]["note"]
    assert await desk.rows("SELECT id FROM sequences") == []  # nothing saved


async def test_a_person_can_be_taken_out_by_hand(desk: Shop) -> None:
    asha = await desk.customer("Asha Rao")
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id, [step(DAY, template=True)])
    await enter(desk, asha, tag_id)
    [person] = await people(desk, sequence["id"])
    stopped = await desk.ws.ok(
        "POST", f"/sequences/{sequence['id']}/enrolments/{person['id']}/stop"
    )
    assert (stopped["status"], stopped["stop_reason"]) == ("stopped", "member")
    assert await sweep(desk, datetime.now(UTC) + timedelta(days=2)) == {}
    missing = await desk.ws.call(
        "POST", f"/sequences/{sequence['id']}/enrolments/{uuid.uuid4()}/stop"
    )
    assert missing.status_code == 404


async def test_activity_the_timeline_and_the_contact_show_what_happened(desk: Shop) -> None:
    asha = await desk.customer("Asha Rao")
    never = await desk.customer("Chitra Iyer", consent=None)
    tag_id = await tag(desk)
    sequence = await running(desk, tag_id, [step(DAY, template=True)])
    await enter(desk, asha, tag_id)
    await enter(desk, never, tag_id)
    await sweep(desk, datetime.now(UTC) + timedelta(hours=25))

    everything = await desk.ws.ok(
        "GET", "/activity", params={"kind": "sequence", "failures_only": "false"}
    )
    outcomes = {i["title"]: i for i in everything["items"]}
    assert outcomes["Three days sent step 1 to Asha Rao"]["outcome"] == "ok"
    skipped = outcomes["Three days skipped step 1 for Chitra Iyer"]
    assert (skipped["outcome"], skipped["reason"]) == (
        "skipped",
        "They haven't agreed to WhatsApp marketing messages.",
    )
    problems_only = await desk.ws.ok("GET", "/activity", params={"kind": "sequence"})
    assert [i["outcome"] for i in problems_only["items"]] == ["skipped"]
    assert problems_only["items"][0]["action"] == {
        "label": "Open the sequence",
        "href": f"/sequences/{sequence['id']}",
    }

    timeline = (await desk.ws.ok("GET", f"/contacts/{asha.contact_id}/timeline"))["items"]
    assert [i["title"] for i in timeline if i["kind"] == "sequence"] == [
        "Sent step 1 of Three days"
    ]
    mine = await desk.ws.ok("GET", f"/contacts/{never.contact_id}/sequences")
    [entry] = mine["items"]
    assert entry["enrolment"]["sequence_name"] == "Three days"
    assert entry["enrolment"]["status"] == "completed"
    assert [(r["position"], r["status"]) for r in entry["runs"]] == [(1, "skipped")]


async def test_only_owners_and_admins_manage_sequences(
    desk: Shop, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    with use_invitation_sender(FakeInvitationSender()):
        await desk.ws.ok(
            "POST", "/invitations", 201, json={"email": "sam@example.com", "role": "agent"}
        )
        clerk_id = clerk.add(email="sam@example.com")
        me = await client.get("/v1/me", headers=clerk.headers(clerk_id))
    agent = Ws(client, clerk, clerk_id, desk.ws.wid, me.json()["id"], desk.ws.account_id)
    assert (await agent.call("GET", "/sequences")).status_code == 403
    assert (await agent.call("POST", "/sequences", json={})).status_code == 403
    asha = await desk.customer("Asha Rao")
    assert (await agent.call("GET", f"/contacts/{asha.contact_id}/sequences")).status_code == 200
