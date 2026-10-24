"""GR-23: WhatsApp broadcasts on the sandbox number.

The routes (preview, create, start, schedule, pause, resume, cancel), the audience (consent
decides, STOP revokes), the dispatch job's batches and pacing, statuses arriving as sandbox
webhooks, the pause when quality drops, the plan's monthly recipients, Activity and the contact
timeline, roles, and the setting that is off by default.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing import plans
from socialhood.jobs.tasks import broadcasts as broadcast_tasks
from socialhood.jobs.tasks import send as send_tasks
from socialhood.models.platform import WebhookStatus
from socialhood.platforms.sandbox import outbox
from socialhood.services.broadcasts import rates, throttle
from tests.support.api import Clerk
from tests.support.broadcasts import Shop, shop
from tests.support.ingest import jobs
from tests.support.sending import clean_outbox


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


async def three_and_one(desk: Shop) -> tuple[list[Any], Any]:
    """Three customers who agreed to WhatsApp marketing and one who withdrew."""
    agreed = [await desk.customer(name) for name in ("Asha Rao", "Ben Cole", "Chitra Iyer")]
    withdrew = await desk.customer("Dev Nair", consent="revoked")
    return agreed, withdrew


async def recipients(desk: Shop, broadcast_id: str, **query: Any) -> list[dict[str, Any]]:
    page = await desk.ws.ok("GET", f"/broadcasts/{broadcast_id}/recipients", params=query)
    return list(page["items"])


async def get(desk: Shop, broadcast_id: str) -> dict[str, Any]:
    return await desk.ws.ok("GET", f"/broadcasts/{broadcast_id}")


async def settle(desk: Shop, **webhook: Any) -> None:
    """Inject one sandbox webhook and process everything stored."""
    response = await desk.inject(**webhook)
    assert response.status_code == 200, response.text
    assert all(
        s in (WebhookStatus.PROCESSED, WebhookStatus.IGNORED) for s in await desk.process_webhooks()
    )


# ---------------------------------------------------------------- the setting and the plan


async def test_with_the_setting_off_nothing_is_available(
    client: httpx.AsyncClient,
    clerk: Clerk,
    app: FastAPI,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    off = await shop(client, clerk, app, engine, redis, monkeypatch, enabled=False)
    availability = await off.ws.ok("GET", "/broadcasts/availability")
    assert availability["enabled"] is False
    assert availability["rate_card"] is None
    for method, path in (
        ("GET", "/broadcasts"),
        ("POST", "/broadcasts/preview"),
        ("POST", "/broadcasts"),
    ):
        response = await off.ws.call(method, path, json=off.body() if method == "POST" else None)
        assert response.status_code == 404, f"{method} {path}"
        body = response.json()
        assert body["code"] == "not_found"
        assert body["detail"] == "Broadcasts aren't available yet."


async def test_nothing_is_dispatched_with_the_setting_off(desk: Shop) -> None:
    await three_and_one(desk)
    started = await desk.send_now()
    desk.app.state.settings.broadcasts_enabled = False
    batch = await desk.batch(started["id"])
    assert (batch.handed_over, batch.state) == (0, "idle")
    assert await desk.rows("SELECT id FROM messages WHERE source = 'broadcast'") == []


async def test_the_free_plan_has_no_broadcasts(
    client: httpx.AsyncClient,
    clerk: Clerk,
    app: FastAPI,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    free = await shop(client, clerk, app, engine, redis, monkeypatch, plan="free")
    availability = await free.ws.ok("GET", "/broadcasts/availability")
    assert (availability["enabled"], availability["plan_allowed"]) == (True, False)
    assert availability["monthly_limit"] == 0
    for path in ("/broadcasts/preview", "/broadcasts"):
        response = await free.ws.call("POST", path, json=free.body())
        assert response.status_code == 402, response.text
        assert response.json()["code"] == "entitlement_required"
        assert response.json()["entitlement"] == "broadcast_recipients_monthly"
    # Reading what exists is never refused.
    assert (await free.ws.ok("GET", "/broadcasts"))["items"] == []


async def test_availability_names_the_plan_the_quota_and_the_rate_card(desk: Shop) -> None:
    availability = await desk.ws.ok("GET", "/broadcasts/availability")
    assert availability["plan_allowed"] is True
    assert availability["monthly_limit"] == 2_500
    assert availability["used_this_period"] == 0
    card = availability["rate_card"]
    assert (card["currency"], card["country"], card["verified"]) == ("INR", "India", False)
    assert Decimal(card["rates"]["marketing"]) == rates.RATE_CARD.rates["marketing"]


# ---------------------------------------------------------------- preview and create


async def test_the_preview_counts_who_is_sent_to_and_who_is_not(desk: Shop) -> None:
    await three_and_one(desk)
    await desk.customer("Esha Rao", consent=None)  # never agreed
    preview = await desk.ws.ok(
        "POST", "/broadcasts/preview", json={k: v for k, v in desk.body().items() if k != "name"}
    )
    assert preview["audience"] == {
        "matching": 5,
        "eligible": 3,
        "opted_out": 1,
        "no_consent": 1,
        "missing_value": 0,
    }
    cost = preview["cost"]
    assert (cost["currency"], cost["category"], cost["verified"]) == ("INR", "marketing", False)
    assert Decimal(cost["total"]) == rates.estimate("marketing", 3)
    assert preview["quota"]["limit"] == 2_500
    assert preview["quota"]["fits"] is True
    assert preview["number"]["limit_known"] is True  # the sandbox number reports its tier
    assert preview["number"]["daily_limit"] == 1_000
    sample = preview["sample"]
    assert sample["text"].startswith("Hi ")
    assert "31 October" in sample["text"]
    assert "{{" not in sample["text"]
    assert preview["problems"] == []


async def test_a_segment_with_no_one_to_send_to_says_so(desk: Shop) -> None:
    await desk.customer("Dev Nair", consent="revoked")
    preview = await desk.ws.ok(
        "POST", "/broadcasts/preview", json={k: v for k, v in desk.body().items() if k != "name"}
    )
    assert preview["audience"]["eligible"] == 0
    assert "agreed to WhatsApp marketing" in preview["problems"][0]
    started = await desk.ws.call(
        "POST", f"/broadcasts/{(await desk.broadcast())['id']}/start", json={}
    )
    assert started.status_code == 422
    assert started.json()["errors"][0]["field"] == "segment_id"


async def test_a_contact_missing_a_value_with_no_fallback_is_left_out(desk: Shop) -> None:
    await three_and_one(desk)
    body = desk.body(
        variables=[
            {"source": "field", "field": "email"},  # nobody has an email
            {"source": "fixed", "value": "31 October"},
        ]
    )
    preview = await desk.ws.ok(
        "POST", "/broadcasts/preview", json={k: v for k, v in body.items() if k != "name"}
    )
    assert preview["audience"]["eligible"] == 0
    assert preview["audience"]["missing_value"] == 3


async def test_a_broadcast_is_saved_as_a_draft_and_can_be_changed_and_deleted(desk: Shop) -> None:
    draft = await desk.broadcast()
    assert draft["status"] == "draft"
    assert draft["template"] == {
        "name": "sale_offer",
        "language": "en",
        "category": "marketing",
        "body": "Hi {{1}}, our sale is on until {{2}}. Reply STOP to opt out.",
    }
    assert draft["segment_name"] == "Everyone"
    assert draft["counts"]["total"] == 0
    changed = await desk.ws.ok(
        "PATCH",
        f"/broadcasts/{draft['id']}",
        json={
            "name": "Renamed",
            "variables": [VARIABLE_THERE, {"source": "fixed", "value": "Fri"}],
        },
    )
    assert changed["name"] == "Renamed"
    assert changed["variables"][1]["value"] == "Fri"
    listed = await desk.ws.ok("GET", "/broadcasts")
    assert [b["id"] for b in listed["items"]] == [draft["id"]]
    assert listed["total"] == 1
    await desk.ws.ok("DELETE", f"/broadcasts/{draft['id']}", 204)
    assert (await desk.ws.call("GET", f"/broadcasts/{draft['id']}")).status_code == 404


VARIABLE_THERE = {"source": "field", "field": "first_name", "fallback": "there"}


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"template_name": "no_such_template"}, "template_name"),
        ({"template_name": "login_code"}, "template_name"),  # authentication
        ({"variables": []}, "variables"),  # the template has two
        ({"variables": [{"source": "field", "field": "nope"}] * 2}, "variables"),
    ],
    ids=["unknown", "authentication", "count", "field"],
)
async def test_a_broadcast_must_fit_its_template(
    desk: Shop, changes: dict[str, Any], field: str
) -> None:
    response = await desk.ws.call("POST", "/broadcasts", json=desk.body(**changes))
    assert response.status_code == 422, response.text
    assert field in [e["field"] for e in response.json()["errors"]]


async def test_a_number_that_is_not_whatsapp_is_refused(
    desk: Shop, client: httpx.AsyncClient
) -> None:
    instagram = await client.post(
        f"/v1/w/{desk.ws.wid}/dev/sandbox/accounts", headers=desk.ws.headers
    )
    response = await desk.ws.call(
        "POST", "/broadcasts", json=desk.body(social_account_id=instagram.json()["id"])
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "social_account_id"


# ---------------------------------------------------------------- the sandbox broadcast


async def test_a_sandbox_broadcast_to_three_reports_each_status_and_skips_the_opted_out_one(
    desk: Shop,
) -> None:
    """The task's done-when: 3 opted-in contacts get each status, the opted-out one is skipped."""
    (asha, ben, chitra), dev = await three_and_one(desk)
    started = await desk.send_now()
    assert started["status"] == "sending"
    assert started["audience_size"] == 3
    assert Decimal(started["cost"]["total"]) == rates.estimate("marketing", 3)
    before = await recipients(desk, started["id"])
    assert sorted(r["status"] for r in before) == ["queued", "queued", "queued", "skipped"]
    [skipped] = [r for r in before if r["status"] == "skipped"]
    assert (skipped["contact_name"], skipped["reason"]) == (
        "Dev Nair",
        "Asked not to get marketing messages.",
    )

    batch = await desk.batch(started["id"])
    assert (batch.handed_over, batch.state) == (3, "completed")
    assert await desk.deliver_queued(send_tasks) == 3

    # The template went out with each person's parameters.
    sent = [s for s in outbox.SENT if s.message.template is not None]
    assert len(sent) == 3
    assert {s.message.template.name for s in sent} == {"sale_offer"}
    assert sorted(s.message.template.params[0] for s in sent) == ["Asha", "Ben", "Chitra"]
    assert {s.message.template.params[1] for s in sent} == {"31 October"}
    assert {s.recipient_ref for s in sent} == {asha.wa_id, ben.wa_id, chitra.wa_id}
    assert dev.wa_id not in {s.recipient_ref for s in outbox.SENT}

    counts = (await get(desk, started["id"]))["counts"]
    assert (counts["sent"], counts["queued"], counts["skipped"], counts["total"]) == (3, 0, 1, 4)

    await settle(desk, kind="status", from_id=asha.wa_id, delivery_status="delivered")
    await settle(desk, kind="status", from_id=ben.wa_id, delivery_status="delivered")
    await settle(desk, kind="status", from_id=ben.wa_id, delivery_status="read")
    await settle(
        desk,
        kind="status",
        from_id=chitra.wa_id,
        delivery_status="failed",
        error_code=131026,
        error_text="Message undeliverable",
    )
    by_name = {r["contact_name"]: r for r in await recipients(desk, started["id"])}
    assert by_name["Asha Rao"]["status"] == "delivered"
    assert by_name["Ben Cole"]["status"] == "read"
    assert by_name["Chitra Iyer"]["status"] == "failed"
    assert by_name["Chitra Iyer"]["reason"] == "This person can't receive messages right now."
    assert by_name["Dev Nair"]["status"] == "skipped"

    done = await get(desk, started["id"])
    assert done["status"] == "completed"
    assert done["counts"] == {
        "total": 4,
        "queued": 0,
        "sent": 0,
        "delivered": 1,
        "read": 1,
        "failed": 1,
        "skipped": 1,
        "replied": 0,
        "stopped": 0,
    }
    only_failed = await recipients(desk, started["id"], status="failed")
    assert [r["contact_name"] for r in only_failed] == ["Chitra Iyer"]
    # The messages are in the inbox as broadcast messages.
    sources = await desk.rows("SELECT DISTINCT source FROM messages WHERE template IS NOT NULL")
    assert sources == [{"source": "broadcast"}]


async def test_recipients_are_paged(desk: Shop) -> None:
    for i in range(5):
        await desk.customer(f"Customer {i}")
    started = await desk.send_now()
    first = await desk.ws.ok(
        "GET", f"/broadcasts/{started['id']}/recipients", params={"limit": 2, "offset": 0}
    )
    last = await desk.ws.ok(
        "GET", f"/broadcasts/{started['id']}/recipients", params={"limit": 2, "offset": 4}
    )
    assert (len(first["items"]), first["total"], len(last["items"])) == (2, 5, 1)


async def test_sending_twice_hands_over_each_person_once(desk: Shop) -> None:
    await three_and_one(desk)
    started = await desk.send_now()
    first = await desk.batch(started["id"])
    again = await desk.batch(started["id"])
    assert (first.handed_over, again.handed_over, again.state) == (3, 0, "idle")
    messages = await desk.rows("SELECT id FROM messages WHERE source = 'broadcast'")
    assert len(messages) == 3


async def test_a_double_click_on_send_starts_it_once(desk: Shop) -> None:
    await three_and_one(desk)
    draft = await desk.broadcast()
    first = await desk.ws.ok("POST", f"/broadcasts/{draft['id']}/start", json={})
    second = await desk.ws.ok("POST", f"/broadcasts/{draft['id']}/start", json={})
    assert (first["status"], second["status"]) == ("sending", "sending")
    assert second["counts"]["total"] == 4


async def test_a_started_broadcast_queues_its_first_batch(desk: Shop) -> None:
    await three_and_one(desk)
    started = await desk.send_now()
    queued = await jobs("dispatch_broadcast")
    assert len(queued) == 1
    assert queued[0]["queueing_lock"] == f"broadcast:{started['id']}"


# ---------------------------------------------------------------- consent


async def test_consent_is_checked_again_at_each_persons_turn(desk: Shop) -> None:
    (asha, _, _), _ = await three_and_one(desk)
    started = await desk.send_now()
    await desk.ws.ok(
        "POST",
        f"/contacts/{asha.contact_id}/consents",
        json={"channel": "whatsapp", "status": "revoked", "note": "Called to opt out"},
    )
    batch = await desk.batch(started["id"])
    assert (batch.handed_over, batch.skipped) == (2, 1)
    by_name = {r["contact_name"]: r for r in await recipients(desk, started["id"])}
    assert by_name["Asha Rao"]["status"] == "skipped"
    assert by_name["Asha Rao"]["reason"] == "Asked not to get marketing messages."


async def test_a_stop_reply_revokes_consent_and_they_are_never_sent_to_again(desk: Shop) -> None:
    (asha, _, _), _ = await three_and_one(desk)
    started = await desk.send_now()
    await desk.batch(started["id"])
    await desk.deliver_queued(send_tasks)

    await settle(desk, kind="dm", from_id=asha.wa_id, text="STOP")

    consent = await desk.rows(
        "SELECT status, source, evidence FROM contact_consents WHERE contact_id = :c"
        " ORDER BY occurred_at DESC, created_at DESC",
        c=asha.contact_id,
    )
    assert (consent[0]["status"], consent[0]["source"]) == ("revoked", "stop_reply")
    assert consent[0]["evidence"]["text"] == "STOP"
    assert consent[0]["evidence"]["message_id"]
    [evidence] = await desk.rows(
        "SELECT text FROM messages WHERE id = CAST(:m AS uuid)",
        m=consent[0]["evidence"]["message_id"],
    )
    assert evidence["text"] == "STOP"

    by_name = {r["contact_name"]: r for r in await recipients(desk, started["id"])}
    assert (by_name["Asha Rao"]["replied"], by_name["Asha Rao"]["stopped"]) == (True, True)
    assert (by_name["Ben Cole"]["replied"], by_name["Ben Cole"]["stopped"]) == (False, False)
    counts = (await get(desk, started["id"]))["counts"]
    assert (counts["replied"], counts["stopped"]) == (1, 1)

    # The contact page shows the consent as withdrawn, and the next broadcast leaves them out.
    record = await desk.ws.ok("GET", f"/contacts/{asha.contact_id}")
    [whatsapp] = [c for c in record["consents"] if c["channel"] == "whatsapp"]
    assert whatsapp["status"] == "revoked"
    preview = await desk.ws.ok(
        "POST", "/broadcasts/preview", json={k: v for k, v in desk.body().items() if k != "name"}
    )
    assert preview["audience"]["eligible"] == 2
    assert preview["audience"]["opted_out"] == 2  # Dev, who withdrew earlier, and Asha
    again = await desk.send_now(name="Second")
    skipped = [r for r in await recipients(desk, again["id"]) if r["status"] == "skipped"]
    assert sorted(r["contact_name"] for r in skipped) == ["Asha Rao", "Dev Nair"]


@pytest.mark.parametrize(
    "words",
    ["unsubscribe", "Stop please", "band karo"],
    ids=["unsubscribe", "stop-please", "hinglish"],
)
async def test_the_stop_words_work_without_a_broadcast(desk: Shop, words: str) -> None:
    person = await desk.customer("Asha Rao")
    await settle(desk, kind="dm", from_id=person.wa_id, text=words)
    [latest] = await desk.rows(
        "SELECT status, source FROM contact_consents WHERE contact_id = :c"
        " ORDER BY occurred_at DESC, created_at DESC LIMIT 1",
        c=person.contact_id,
    )
    assert (latest["status"], latest["source"]) == ("revoked", "stop_reply")


async def test_an_ordinary_reply_is_counted_and_keeps_consent(desk: Shop) -> None:
    (asha, _, _), _ = await three_and_one(desk)
    started = await desk.send_now()
    await desk.batch(started["id"])
    await desk.deliver_queued(send_tasks)
    await settle(desk, kind="dm", from_id=asha.wa_id, text="Do you have it in blue?")
    by_name = {r["contact_name"]: r for r in await recipients(desk, started["id"])}
    assert (by_name["Asha Rao"]["replied"], by_name["Asha Rao"]["stopped"]) == (True, False)
    [latest] = await desk.rows(
        "SELECT status FROM contact_consents WHERE contact_id = :c"
        " ORDER BY occurred_at DESC, created_at DESC LIMIT 1",
        c=asha.contact_id,
    )
    assert latest["status"] == "granted"


# ---------------------------------------------------------------- schedule, pause, resume, cancel


async def test_a_broadcast_can_be_scheduled_and_starts_when_due(desk: Shop) -> None:
    await three_and_one(desk)
    draft = await desk.broadcast()
    when = datetime.now(UTC) + timedelta(hours=2)
    scheduled = await desk.ws.ok(
        "POST", f"/broadcasts/{draft['id']}/start", json={"scheduled_at": when.isoformat()}
    )
    assert scheduled["status"] == "scheduled"
    assert scheduled["counts"]["total"] == 0  # the audience is fixed when it starts
    assert await jobs("dispatch_broadcast") == []

    nothing = await broadcast_tasks.start_due(desk.maker, desk.redis, desk.deps)
    assert nothing == []

    await desk.customer("Late Joiner")  # agreed after it was scheduled, before it started
    started = await broadcast_tasks.start_due(
        desk.maker, desk.redis, desk.deps, now=when + timedelta(minutes=1)
    )
    assert [str(b) for _, b in started] == [draft["id"]]
    live = await get(desk, draft["id"])
    assert (live["status"], live["audience_size"]) == ("sending", 4)


@pytest.mark.parametrize(
    ("offset", "message"),
    [
        (timedelta(seconds=10), "at least a minute"),
        (timedelta(days=120), "within the next 90 days"),
    ],
    ids=["too-soon", "too-far"],
)
async def test_a_schedule_must_be_a_sensible_time(
    desk: Shop, offset: timedelta, message: str
) -> None:
    await three_and_one(desk)
    draft = await desk.broadcast()
    when = datetime.now(UTC) + offset
    response = await desk.ws.call(
        "POST", f"/broadcasts/{draft['id']}/start", json={"scheduled_at": when.isoformat()}
    )
    assert response.status_code == 422
    assert message in response.json()["errors"][0]["message"]


async def test_a_scheduled_broadcast_whose_segment_is_gone_fails_with_the_reason(
    desk: Shop,
) -> None:
    await three_and_one(desk)
    draft = await desk.broadcast()
    when = datetime.now(UTC) + timedelta(hours=1)
    await desk.ws.ok(
        "POST", f"/broadcasts/{draft['id']}/start", json={"scheduled_at": when.isoformat()}
    )
    await desk.ws.ok("DELETE", f"/contact-segments/{desk.segment_id}", 204)
    await broadcast_tasks.start_due(
        desk.maker, desk.redis, desk.deps, now=when + timedelta(minutes=1)
    )
    failed = await get(desk, draft["id"])
    assert failed["status"] == "failed"
    assert "segment" in failed["paused_reason"]
    assert failed["segment_name"] == "Everyone"  # kept for the record


async def test_the_owner_can_pause_resume_and_cancel(
    desk: Shop, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(throttle, "BATCH_SIZE", 1)
    await three_and_one(desk)
    started = await desk.send_now()
    first = await desk.batch(started["id"])
    assert (first.handed_over, first.state) == (1, "sending")
    assert first.next_in_s == 60

    paused = await desk.ws.ok("POST", f"/broadcasts/{started['id']}/pause")
    assert (paused["status"], paused["paused_code"]) == ("paused", "member")
    idle = await desk.batch(started["id"])
    assert (idle.handed_over, idle.state) == (0, "idle")

    resumed = await desk.ws.ok("POST", f"/broadcasts/{started['id']}/resume")
    assert (resumed["status"], resumed["paused_reason"]) == ("sending", None)
    assert (await desk.batch(started["id"])).handed_over == 1

    cancelled = await desk.ws.ok("POST", f"/broadcasts/{started['id']}/cancel")
    assert cancelled["status"] == "cancelled"
    assert cancelled["counts"]["skipped"] == 2  # Dev, and the one nobody reached
    [last] = [
        r
        for r in await recipients(desk, started["id"])
        if r["status"] == "skipped" and "cancelled" in (r["reason"] or "")
    ]
    assert last["reason"] == "The broadcast was cancelled before their turn."
    assert (await desk.batch(started["id"])).state == "idle"
    # Cancelling again changes nothing; a sent one can't be deleted, a cancelled one can.
    assert (await desk.ws.ok("POST", f"/broadcasts/{started['id']}/cancel"))[
        "status"
    ] == "cancelled"
    await desk.ws.ok("DELETE", f"/broadcasts/{started['id']}", 204)


async def test_only_the_right_states_can_change(desk: Shop) -> None:
    await three_and_one(desk)
    draft = await desk.broadcast()
    for action in ("pause", "resume"):
        response = await desk.ws.call("POST", f"/broadcasts/{draft['id']}/{action}")
        assert response.status_code == 409, action
    started = await desk.ws.ok("POST", f"/broadcasts/{draft['id']}/start", json={})
    update = await desk.ws.call("PATCH", f"/broadcasts/{started['id']}", json={"name": "Late"})
    assert update.status_code == 409
    delete = await desk.ws.call("DELETE", f"/broadcasts/{started['id']}")
    assert delete.status_code == 409


# ---------------------------------------------------------------- pacing and quality


async def test_a_batch_waits_when_the_number_is_at_its_daily_limit(
    desk: Shop, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(throttle.TIER_LIMITS, "TIER_50", 2)  # usable: 1 a day
    await settle(desk, kind="quality", quality_event="UPGRADE", tier="TIER_50")
    [account] = await desk.rows("SELECT platform_account_id FROM social_accounts")
    # A day later the number is read again; it still says TIER_50.
    outbox.set_number_health(account["platform_account_id"], "unknown", "TIER_50")
    await three_and_one(desk)
    started = await desk.send_now()

    first = await desk.batch(started["id"])
    assert (first.handed_over, first.state) == (1, "sending")
    second = await desk.batch(started["id"])
    assert second.handed_over == 0
    assert second.next_in_s is not None
    assert second.next_in_s >= 60  # until the window frees
    assert await desk.rows("SELECT id FROM messages WHERE source = 'broadcast'") != []

    later = datetime.now(UTC) + timedelta(hours=25)
    third = await desk.batch(started["id"], now=later)
    assert third.handed_over == 1  # the first message has left the 24-hour window


async def test_the_numbers_tier_is_read_from_the_platform_when_none_is_stored(
    desk: Shop,
) -> None:
    await three_and_one(desk)
    started = await desk.send_now()
    await desk.batch(started["id"])
    [health] = await desk.rows("SELECT messaging_tier, daily_limit FROM whatsapp_number_health")
    # The sandbox number reports TIER_1K when read (the conservative default of 250 applies only
    # when WhatsApp tells us nothing; tests/unit/test_broadcast_throttle.py).
    assert (health["messaging_tier"], health["daily_limit"]) == ("TIER_1K", 1_000)


async def test_a_quality_drop_pauses_a_sending_broadcast_with_a_reason(
    desk: Shop, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(throttle, "BATCH_SIZE", 1)
    await three_and_one(desk)
    started = await desk.send_now()
    assert (await desk.batch(started["id"])).handed_over == 1

    await settle(desk, kind="quality", quality_event="FLAGGED")

    paused = await get(desk, started["id"])
    assert (paused["status"], paused["paused_code"]) == ("paused", "quality")
    assert "Low" in paused["paused_reason"]
    assert (await desk.batch(started["id"])).state == "idle"  # nothing more goes out

    # The owners are told, and Activity shows it with a way to the broadcast.
    notices = await desk.rows(
        "SELECT type, body, link FROM notifications WHERE type = 'broadcast_paused'"
    )
    assert len(notices) == 1
    assert notices[0]["link"] == f"/broadcasts/{started['id']}"
    feed = await desk.ws.ok("GET", "/activity", params={"kind": "broadcast"})
    [item] = feed["items"]
    assert item["kind"] == "broadcast"
    assert item["title"] == "Diwali sale was paused"
    assert "Low" in item["reason"]
    assert item["action"]["href"] == f"/broadcasts/{started['id']}"

    # While the rating is Low it can't be resumed; once WhatsApp says it recovered, it can.
    refused = await desk.ws.call("POST", f"/broadcasts/{started['id']}/resume")
    assert refused.status_code == 409
    await settle(desk, kind="quality", quality_event="UNFLAGGED")
    resumed = await desk.ws.ok("POST", f"/broadcasts/{started['id']}/resume")
    assert resumed["status"] == "sending"
    assert (await desk.batch(started["id"])).handed_over == 1


async def test_a_lower_tier_pauses_too(desk: Shop, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(throttle, "BATCH_SIZE", 1)
    await three_and_one(desk)
    started = await desk.send_now()
    await desk.batch(started["id"])
    await settle(desk, kind="quality", quality_event="DOWNGRADE", tier="TIER_250")
    paused = await get(desk, started["id"])
    assert paused["status"] == "paused"
    assert "250" in paused["paused_reason"]


async def test_a_quality_update_for_another_numbers_waba_changes_nothing_here(
    desk: Shop,
) -> None:
    await three_and_one(desk)
    started = await desk.send_now()
    response = await desk.inject(kind="quality", quality_event="FLAGGED")
    assert response.status_code == 200
    async with desk.engine.begin() as conn:  # the update names a WhatsApp account that isn't ours
        await conn.execute(text("UPDATE social_accounts SET waba_id = 'someone_else'"))
    statuses = await desk.process_webhooks()
    assert statuses == [WebhookStatus.IGNORED]
    assert (await get(desk, started["id"]))["status"] == "sending"


# ---------------------------------------------------------------- the monthly recipients


async def test_a_broadcast_over_the_months_recipients_is_refused_with_the_numbers(
    desk: Shop, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(plans.ENTITLEMENTS["broadcast_recipients_monthly"], "pro", 2)
    await three_and_one(desk)
    draft = await desk.broadcast()
    response = await desk.ws.call("POST", f"/broadcasts/{draft['id']}/start", json={})
    assert response.status_code == 402, response.text
    body = response.json()
    assert (body["code"], body["entitlement"], body["limit"]) == (
        "quota_exceeded",
        "broadcast_recipients_monthly",
        2,
    )
    assert "2 broadcast recipients a month" in body["detail"]
    preview = await desk.ws.ok(
        "POST", "/broadcasts/preview", json={k: v for k, v in desk.body().items() if k != "name"}
    )
    assert preview["quota"]["fits"] is False
    assert "3" in preview["problems"][0]
    assert (await get(desk, draft["id"]))["status"] == "draft"


async def test_the_quota_counts_recipients_handed_over_and_resets_each_period(
    desk: Shop, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(plans.ENTITLEMENTS["broadcast_recipients_monthly"], "pro", 4)
    await three_and_one(desk)
    first = await desk.send_now()
    await desk.batch(first["id"])
    availability = await desk.ws.ok("GET", "/broadcasts/availability")
    assert (availability["monthly_limit"], availability["used_this_period"]) == (4, 3)

    second = await desk.broadcast(name="Second")
    refused = await desk.ws.call("POST", f"/broadcasts/{second['id']}/start", json={})
    assert refused.status_code == 402
    assert "1 are left" in refused.json()["detail"]

    # Last month's recipients are not this month's: move them out of the period.
    async with desk.engine.begin() as conn:
        await conn.execute(
            text("UPDATE broadcast_recipients SET dispatched_at = now() - interval '40 days'")
        )
    assert (await desk.ws.ok("GET", "/broadcasts/availability"))["used_this_period"] == 0
    await desk.ws.ok("POST", f"/broadcasts/{second['id']}/start", json={})


async def test_a_broadcast_pauses_when_the_months_recipients_run_out(
    desk: Shop, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(throttle, "BATCH_SIZE", 2)
    await three_and_one(desk)
    started = await desk.send_now()
    assert (await desk.batch(started["id"])).handed_over == 2
    # The plan shrinks (a downgrade) while it sends.
    monkeypatch.setitem(plans.ENTITLEMENTS["broadcast_recipients_monthly"], "pro", 2)
    stopped = await desk.batch(started["id"])
    assert stopped.state == "paused"
    paused = await get(desk, started["id"])
    assert (paused["status"], paused["paused_code"]) == ("paused", "limit")
    assert "used up" in paused["paused_reason"]
    resume = await desk.ws.call("POST", f"/broadcasts/{started['id']}/resume")
    assert resume.status_code == 402


async def test_downgraded_to_free_a_sending_broadcast_pauses(
    desk: Shop, engine: AsyncEngine
) -> None:
    await three_and_one(desk)
    started = await desk.send_now()
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE subscriptions SET plan = 'free'"))
    assert (await desk.batch(started["id"])).state == "paused"
    paused = await get(desk, started["id"])
    assert (paused["paused_code"], paused["paused_reason"]) == (
        "plan",
        "Your plan no longer includes broadcasts.",
    )


# ---------------------------------------------------------------- failures, Activity, the timeline


async def test_failures_reach_activity_and_the_timeline_shows_the_broadcast(
    desk: Shop,
) -> None:
    (asha, ben, _), _ = await three_and_one(desk)
    started = await desk.send_now()
    await desk.batch(started["id"])
    await desk.deliver_queued(send_tasks)
    await settle(
        desk,
        kind="status",
        from_id=ben.wa_id,
        delivery_status="failed",
        error_code=131026,
        error_text="Message undeliverable",
    )
    feed = await desk.ws.ok("GET", "/activity", params={"kind": "message"})
    [item] = feed["items"]
    assert item["title"] == "A broadcast message to Ben Cole wasn't sent"
    assert item["reason"]

    await settle(desk, kind="status", from_id=asha.wa_id, delivery_status="read")
    timeline = await desk.ws.ok("GET", f"/contacts/{asha.contact_id}/timeline")
    [received] = [i for i in timeline["items"] if i["kind"] == "broadcast"]
    assert received["title"] == "Received broadcast Diwali sale"
    assert received["detail"] == "Read"


async def test_a_failed_sandbox_send_is_a_failed_recipient(desk: Shop) -> None:
    await desk.customer("Asha Rao")
    started = await desk.send_now(
        variables=[
            {"source": "field", "field": "first_name", "fallback": "there"},
            {"source": "fixed", "value": "[sandbox:fail=platform_rejected]"},
        ]
    )
    await desk.batch(started["id"])
    await desk.deliver_queued(send_tasks)
    [row] = await recipients(desk, started["id"])
    assert row["status"] == "failed"
    assert row["reason"]


# ---------------------------------------------------------------- roles


async def test_agents_cannot_open_broadcasts(desk: Shop, engine: AsyncEngine) -> None:
    draft = await desk.broadcast()
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w"),
            {"w": desk.ws.wid},
        )
    for method, path in (
        ("GET", "/broadcasts/availability"),
        ("GET", "/broadcasts"),
        ("GET", f"/broadcasts/{draft['id']}"),
        ("POST", "/broadcasts"),
        ("POST", f"/broadcasts/{draft['id']}/start"),
        ("POST", f"/broadcasts/{draft['id']}/pause"),
        ("DELETE", f"/broadcasts/{draft['id']}"),
    ):
        response = await desk.ws.call(method, path, json={} if method == "POST" else None)
        assert response.status_code == 403, f"{method} {path}"


# ---------------------------------------------------------------- the job


async def test_the_minutely_job_queues_a_batch_for_every_sending_broadcast(
    desk: Shop, monkeypatch: pytest.MonkeyPatch
) -> None:
    await three_and_one(desk)
    started = await desk.send_now()
    from socialhood.jobs.runtime import Runtime

    rt = Runtime(
        settings=desk.app.state.settings,
        sessionmaker=desk.app.state.sessionmaker,
        redis=desk.app.state.redis,
        http=desk.app.state.http,
    )
    monkeypatch.setattr(broadcast_tasks, "runtime", lambda: rt)
    await broadcast_tasks.run_broadcasts(0)
    queued = await jobs("dispatch_broadcast")
    assert [j["queueing_lock"] for j in queued] == [f"broadcast:{started['id']}"]
    # Another tick does not stack a second job.
    await broadcast_tasks.run_broadcasts(0)
    assert len(await jobs("dispatch_broadcast")) == 1
