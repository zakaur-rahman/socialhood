"""Notification channels and delivery (T8.5, T8.6; FR-NOT-01…03, C-049).

Done when (T8.5): one email per event (dedupe key). Plus: which channels each type and role get,
the outbox and its retries, skips and sweeper, jobs deferred only after commit, push delivery to
every device (gone ones deleted, failures counted, disabled at five, retried only when no device
got it), and the new-lead notification at a lead score of 70."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider
from socialhood.jobs.tasks.emails import sweep_outbox
from socialhood.models.notifications import PUSH_MAX_FAILURES
from socialhood.notify.email import EmailError
from socialhood.notify.email_fake import FakeEmail
from socialhood.notify.push import MAX_PAYLOAD_BYTES, PushError, PushNotConfigured
from socialhood.notify.push_fake import FakePush
from socialhood.settings import Settings
from tests.support.analysis import Inbox, make_inbox
from tests.support.ingest import jobs
from tests.support.notify import make_push_subscription, push_endpoint
from tests.support.notify_team import Team, make_team

WEB = "http://web.test"  # api_settings' WEB_BASE_URL


@pytest.fixture
async def team(engine: AsyncEngine, clean_db: None) -> Team:
    return await make_team(engine)


@pytest.fixture
def settings(api_settings: Settings) -> Settings:
    return api_settings.model_copy(update={"api_base_url": "http://api.test"})


def channels(notes: list[dict[str, Any]]) -> dict[uuid.UUID, list[str]]:
    return {note["user_id"]: note["channels"] for note in notes}


# ---------------------------------------------------------------- channels


async def test_account_problems_email_and_push_the_owners_and_admins(team: Team) -> None:
    assert await team.notify(type="account_needs_reconnect") == 2

    notes = await team.notes()
    assert channels(notes) == {
        team.owner: ["in_app", "email", "push"],
        team.admin: ["in_app", "email", "push"],
    }
    deliveries = await team.deliveries()
    assert sorted(d["to_email"] for d in deliveries) == sorted(
        [team.emails[team.owner], team.emails[team.admin]]
    )
    by_note = {note["id"]: note for note in notes}
    for delivery in deliveries:
        note = by_note[delivery["notification_id"]]
        assert delivery["user_id"] == note["user_id"]
        assert delivery["template"] == "account_needs_reconnect"
        assert delivery["dedupe_key"] == f"notification:{note['id']}"
        assert delivery["status"] == "queued"
        assert delivery["data"] == {
            "title": "Reconnect @maple.bakery",
            "body": "@maple.bakery needs reconnecting to keep receiving messages.",
            "link": "/settings/connections",
            "workspace_name": "Maple Bakery",
            "workspace_slug": team.slug,
        }


async def test_emails_go_to_owners_and_admins_even_when_everyone_is_notified(team: Team) -> None:
    await team.notify(to="members", type="post_failed", title="Post didn't publish")

    assert channels(await team.notes()) == {
        team.owner: ["in_app", "email"],
        team.admin: ["in_app", "email"],
        team.agent: ["in_app"],
    }
    assert {d["user_id"] for d in await team.deliveries()} == {team.owner, team.admin}


@pytest.mark.parametrize("type_", ["payment_problem", "plan_activated", "plan_downgraded"])
async def test_billing_notifications_are_emailed_and_never_pushed(team: Team, type_: str) -> None:
    await team.notify(type=type_, title="Payment failed", link="/settings/billing")

    assert set(map(tuple, channels(await team.notes()).values())) == {("in_app", "email")}
    assert {d["template"] for d in await team.deliveries()} == {type_}


@pytest.mark.parametrize(
    "type_", ["ai_credits_80", "scheduled_message_expired", "automation_ended"]
)
async def test_other_types_stay_in_app(team: Team, type_: str) -> None:
    await team.notify(type=type_)

    assert set(map(tuple, channels(await team.notes()).values())) == {("in_app",)}
    assert await team.deliveries() == []


async def test_push_follows_each_members_switch(team: Team) -> None:
    await team.set_prefs(
        team.agent,
        {
            "email_digest": True,
            "push": {"needs_you": True, "new_lead": True, "window_closing": False, "account": True},
        },
    )
    await team.notify(to="members", type="window_closing", title="Follow up with Priya")

    assert channels(await team.notes()) == {
        team.owner: ["in_app", "push"],
        team.admin: ["in_app", "push"],
        team.agent: ["in_app"],
    }


async def test_one_event_notifies_and_emails_once(
    team: Team, fake_email: FakeEmail, settings: Settings
) -> None:
    for _ in range(3):
        await team.notify(dedupe_key="reconnect:acct-1:2026-09-01")

    assert len(await team.notes()) == 2
    deliveries = await team.deliveries()
    assert len(deliveries) == 2
    for delivery in deliveries:
        await team.send_email(delivery["id"], fake_email, settings)
    assert len(fake_email.outbox) == 2


# ---------------------------------------------------------------- after commit


async def test_jobs_are_deferred_after_commit_and_never_on_rollback(
    team: Team, engine: AsyncEngine, queue: None
) -> None:
    await make_push_subscription(engine, user_id=team.owner)

    assert await team.notify(commit=False) == 2
    assert await team.notes() == []
    assert await jobs("deliver_email") == []
    assert await jobs("deliver_push") == []

    await team.notify()

    deliveries = {d["id"]: d for d in await team.deliveries()}
    email_jobs = await jobs("deliver_email")
    assert len(email_jobs) == 2
    for job in email_jobs:
        delivery_id = uuid.UUID(job["args"]["delivery_id"])
        assert delivery_id in deliveries
        assert job["args"]["workspace_id"] == str(team.wid)
        assert (job["queue_name"], job["queueing_lock"]) == ("interactive", f"email:{delivery_id}")
    # Only the owner has a device, so only the owner's notification is pushed.
    [push_job] = await jobs("deliver_push")
    [owner_note] = [n for n in await team.notes() if n["user_id"] == team.owner]
    assert push_job["args"] == {
        "notification_id": str(owner_note["id"]),
        "workspace_id": str(team.wid),
    }
    assert push_job["queueing_lock"] == f"push:{owner_note['id']}"


# ---------------------------------------------------------------- the outbox


async def test_an_email_is_sent_once_under_its_idempotency_key(
    team: Team, fake_email: FakeEmail, settings: Settings
) -> None:
    await team.notify()
    at = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
    for delivery in await team.deliveries():
        assert await team.send_email(delivery["id"], fake_email, settings, now=at) == "sent"
        assert await team.send_email(delivery["id"], fake_email, settings, now=at) == "sent"

    assert len(fake_email.outbox) == 2
    notes = {note["id"]: note for note in await team.notes()}
    for delivery in await team.deliveries():
        [sent] = fake_email.sent_to(delivery["to_email"])
        assert sent.idempotency_key == f"{team.wid}:notification:{delivery['notification_id']}"
        assert sent.subject == "Reconnect @maple.bakery"
        assert sent.tags == {"template": "account_needs_reconnect"}
        assert sent.headers == {}  # List-Unsubscribe is for the digest only
        assert f"{WEB}/w/{team.slug}/settings/connections" in sent.html
        assert delivery["status"] == "sent"
        assert (delivery["sent_at"], delivery["attempts"]) == (at, 1)
        assert delivery["subject"] == "Reconnect @maple.bakery"
        assert delivery["provider_message_id"].startswith("email_fake_")
        assert notes[delivery["notification_id"]]["emailed_at"] == at


async def test_a_retryable_failure_retries_and_the_last_attempt_fails(
    team: Team, fake_email: FakeEmail, settings: Settings
) -> None:
    await team.notify()
    delivery_id = (await team.deliveries())[0]["id"]

    fake_email.fail_next(EmailError("Resend 503 application_error", status=503, retryable=True))
    with pytest.raises(EmailError):
        await team.send_email(delivery_id, fake_email, settings, will_retry=True)
    [row] = await team.rows("SELECT * FROM email_deliveries WHERE id = :d", d=delivery_id)
    assert (row["status"], row["attempts"]) == ("queued", 1)
    assert row["error"] == "Resend 503 application_error"

    fake_email.fail_next(EmailError("Resend 503 application_error", status=503, retryable=True))
    assert await team.send_email(delivery_id, fake_email, settings, will_retry=False) == "failed"
    [row] = await team.rows("SELECT * FROM email_deliveries WHERE id = :d", d=delivery_id)
    assert (row["status"], row["attempts"]) == ("failed", 2)
    assert fake_email.outbox == []


async def test_the_fifth_attempt_is_the_last(
    team: Team, fake_email: FakeEmail, settings: Settings
) -> None:
    await team.notify()
    delivery_id = (await team.deliveries())[0]["id"]
    await team.execute("UPDATE email_deliveries SET attempts = 4 WHERE id = :d", d=delivery_id)

    fake_email.fail_next(EmailError("timed out", retryable=True))
    status = await team.send_email(delivery_id, fake_email, settings)

    assert status == "failed"


async def test_a_refused_email_fails_at_once(
    team: Team, fake_email: FakeEmail, settings: Settings
) -> None:
    await team.notify()
    delivery_id = (await team.deliveries())[0]["id"]

    fake_email.fail_next(EmailError("Resend 422 validation_error: invalid `to`", status=422))
    status = await team.send_email(delivery_id, fake_email, settings, will_retry=True)

    assert status == "failed"
    [row] = await team.rows(
        "SELECT status, attempts FROM email_deliveries WHERE id = :d", d=delivery_id
    )
    assert (row["status"], row["attempts"]) == ("failed", 1)


async def test_an_email_to_someone_no_longer_in_the_workspace_is_skipped(
    team: Team, fake_email: FakeEmail, settings: Settings
) -> None:
    await team.notify()
    [delivery] = [d for d in await team.deliveries() if d["user_id"] == team.admin]
    await team.execute(
        "DELETE FROM workspace_members WHERE workspace_id = :w AND user_id = :u",
        w=team.wid,
        u=team.admin,
    )

    status = await team.send_email(delivery["id"], fake_email, settings)

    assert status == "skipped"
    assert fake_email.outbox == []
    [row] = await team.rows("SELECT error FROM email_deliveries WHERE id = :d", d=delivery["id"])
    assert row["error"] == "The recipient is no longer a member of the workspace"


async def test_the_sweeper_requeues_lost_emails_and_gives_up_after_a_day(
    team: Team, queue: None
) -> None:
    await team.notify()
    [late, old] = await team.deliveries()
    await team.notify()  # just queued: its job is still on its way
    from tests.support.api import _clear_queue

    await _clear_queue()  # the enqueues were lost
    now = datetime.now(UTC)
    await team.execute(
        "UPDATE email_deliveries SET created_at = :at WHERE id = :d",
        at=now - timedelta(minutes=5),
        d=late["id"],
    )
    await team.execute(
        "UPDATE email_deliveries SET created_at = :at WHERE id = :d",
        at=now - timedelta(days=2),
        d=old["id"],
    )

    assert await sweep_outbox(team.maker, now=now) == {"requeued": 1, "expired": 1}

    [job] = await jobs("deliver_email")
    assert job["args"] == {"delivery_id": str(late["id"]), "workspace_id": str(team.wid)}
    [row] = await team.rows("SELECT status, error FROM email_deliveries WHERE id = :d", d=old["id"])
    assert row == {"status": "failed", "error": "Not sent within a day"}
    # A second sweep finds the job still waiting (its queueing lock).
    assert await sweep_outbox(team.maker, now=now) == {"requeued": 0, "expired": 0}


# ---------------------------------------------------------------- push delivery


async def escalation(team: Team, conversation_id: uuid.UUID | None = None) -> uuid.UUID:
    """A "Needs you" notification for the owner and admin; returns the owner's."""
    conv = conversation_id or uuid.uuid4()
    key = f"ai_escalated:{uuid.uuid4()}"
    await team.notify(
        type="ai_escalated",
        severity="warning",
        title="Priya needs you",
        body="AI didn't reply: she asked for a refund.",
        link=f"/inbox/{conv}",
        dedupe_key=key,
    )
    [note] = await team.rows(
        "SELECT id FROM notifications WHERE dedupe_key = :k AND user_id = :u", k=key, u=team.owner
    )
    return note["id"]  # type: ignore[no-any-return]


async def test_a_push_reaches_every_device_and_forgets_gone_ones(
    team: Team, engine: AsyncEngine, fake_push: FakePush
) -> None:
    phone, old_laptop, disabled = push_endpoint(), push_endpoint(), push_endpoint()
    await make_push_subscription(engine, user_id=team.owner, endpoint=phone)
    gone = await make_push_subscription(engine, user_id=team.owner, endpoint=old_laptop)
    await make_push_subscription(
        engine, user_id=team.owner, endpoint=disabled, disabled_at=datetime.now(UTC)
    )
    fake_push.gone.add(old_laptop)
    conv = uuid.uuid4()
    note_id = await escalation(team, conv)
    at = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)

    assert await team.push(note_id, fake_push, now=at) == 1

    [message] = fake_push.sent_to(phone)
    assert (message.title, message.body) == (
        "Priya needs you",
        "AI didn't reply: she asked for a refund.",
    )
    assert message.url == f"/w/{team.slug}/inbox/{conv}"
    assert (message.tag, message.urgency) == (f"conversation:{conv}", "high")
    assert fake_push.sent_to(disabled) == []
    assert await team.rows("SELECT id FROM push_subscriptions WHERE id = :d", d=gone) == []
    [device] = await team.rows(
        "SELECT last_used_at, failure_count FROM push_subscriptions WHERE endpoint = :e", e=phone
    )
    assert device == {"last_used_at": at, "failure_count": 0}
    [note] = await team.rows("SELECT pushed_at FROM notifications WHERE id = :n", n=note_id)
    assert note["pushed_at"] == at

    # A retried job never pushes twice.
    assert await team.push(note_id, fake_push) == 0
    assert len(fake_push.sent) == 1


async def test_failures_count_up_and_disable_a_device(
    team: Team, engine: AsyncEngine, fake_push: FakePush
) -> None:
    endpoint = push_endpoint()
    device = await make_push_subscription(
        engine, user_id=team.owner, endpoint=endpoint, failure_count=PUSH_MAX_FAILURES - 2
    )
    for expected in (PUSH_MAX_FAILURES - 1, PUSH_MAX_FAILURES):
        fake_push.fail_next(PushError("push service answered 400", status=400))
        assert await team.push(await escalation(team), fake_push) == 0
        [row] = await team.rows(
            "SELECT failure_count, disabled_at FROM push_subscriptions WHERE id = :d", d=device
        )
        assert row["failure_count"] == expected
    assert row["disabled_at"] is not None

    # Disabled: the next escalation isn't even queued for this user's devices.
    note_id = await escalation(team)
    assert await team.push(note_id, fake_push) == 0
    assert fake_push.sent == []


async def test_a_success_resets_the_failure_count(
    team: Team, engine: AsyncEngine, fake_push: FakePush
) -> None:
    device = await make_push_subscription(engine, user_id=team.owner, failure_count=3)
    assert await team.push(await escalation(team), fake_push) == 1
    [row] = await team.rows("SELECT failure_count FROM push_subscriptions WHERE id = :d", d=device)
    assert row["failure_count"] == 0


async def test_a_push_no_device_got_is_retried(
    team: Team, engine: AsyncEngine, fake_push: FakePush
) -> None:
    device = await make_push_subscription(engine, user_id=team.owner)
    note_id = await escalation(team)

    fake_push.fail_next(PushError("push service answered 503", status=503, retryable=True))
    with pytest.raises(PushError):
        await team.push(note_id, fake_push, will_retry=True)
    [note] = await team.rows("SELECT pushed_at FROM notifications WHERE id = :n", n=note_id)
    assert note["pushed_at"] is None
    [row] = await team.rows("SELECT failure_count FROM push_subscriptions WHERE id = :d", d=device)
    assert row["failure_count"] == 0  # not the device's fault yet

    assert await team.push(note_id, fake_push, will_retry=True) == 1


async def test_the_last_attempt_settles_the_push(
    team: Team, engine: AsyncEngine, fake_push: FakePush
) -> None:
    device = await make_push_subscription(engine, user_id=team.owner)
    note_id = await escalation(team)

    fake_push.fail_next(PushError("push service answered 503", status=503, retryable=True))
    assert await team.push(note_id, fake_push, will_retry=False) == 0

    [row] = await team.rows("SELECT failure_count FROM push_subscriptions WHERE id = :d", d=device)
    assert row["failure_count"] == 1
    [note] = await team.rows("SELECT pushed_at FROM notifications WHERE id = :n", n=note_id)
    assert note["pushed_at"] is not None


async def test_a_switch_turned_off_since_stops_the_push(
    team: Team, engine: AsyncEngine, fake_push: FakePush
) -> None:
    await make_push_subscription(engine, user_id=team.owner)
    note_id = await escalation(team)
    await team.set_prefs(
        team.owner,
        {
            "email_digest": True,
            "push": {"needs_you": False, "new_lead": True, "window_closing": True, "account": True},
        },
    )

    assert await team.push(note_id, fake_push) == 0
    assert fake_push.sent == []


async def test_without_vapid_keys_no_device_is_blamed(
    team: Team, engine: AsyncEngine, fake_push: FakePush
) -> None:
    device = await make_push_subscription(engine, user_id=team.owner)
    note_id = await escalation(team)

    fake_push.fail_next(PushNotConfigured())
    assert await team.push(note_id, fake_push, will_retry=True) == 0

    [row] = await team.rows("SELECT failure_count FROM push_subscriptions WHERE id = :d", d=device)
    assert row["failure_count"] == 0


async def test_long_words_are_clipped_to_fit_a_push(
    team: Team, engine: AsyncEngine, fake_push: FakePush
) -> None:
    await make_push_subscription(engine, user_id=team.owner)
    await team.notify(
        type="ai_escalated",
        title="प्रिया " * 100,
        body="ग्राहक ने रिफंड माँगा " * 200,
        link=f"/inbox/{uuid.uuid4()}",
    )
    [note] = [n for n in await team.notes() if n["user_id"] == team.owner]

    assert await team.push(note["id"], fake_push) == 1
    [(_, message)] = fake_push.sent
    assert len(message.payload()) < MAX_PAYLOAD_BYTES
    assert message.title.endswith("…")


# ---------------------------------------------------------------- new lead (FR-NOT-03)


def analysis(**values: Any) -> dict[str, Any]:
    return {
        "intent": "pricing",
        "sentiment": "positive",
        "sentiment_score": 0.6,
        "priority": "high",
        "lead_score": 75,
        "language": "en",
        "topics": ["red dress"],
        "needs_reply": True,
        "needs_human": False,
        "needs_human_reason": None,
        **values,
    }


@pytest.fixture
async def inbox(engine: AsyncEngine, clean_db: None, redis: Any, queue: None) -> Inbox:
    return await make_inbox(engine, redis)


async def lead_notes(inbox: Inbox) -> list[dict[str, Any]]:
    return await inbox.rows(
        "SELECT title, body, link, channels, dedupe_key FROM notifications WHERE type = 'new_lead'"
    )


async def test_a_lead_score_reaching_70_is_a_new_lead_once(
    inbox: Inbox, fake_ai: FakeProvider
) -> None:
    await inbox.dm("igsid_priya", "How much is the red dress?", name="Priya")
    conv = await inbox.conversation_id("igsid_priya")
    fake_ai.respond("analysis", analysis(lead_score=75))
    await inbox.analyze(conv)

    assert await lead_notes(inbox) == [
        {
            "title": "New lead: Priya",
            "body": "Priya asked about prices. Lead score 75.",
            "link": f"/inbox/{conv}",
            "channels": ["in_app", "push"],
            "dedupe_key": f"new_lead:{conv}",
        }
    ]

    # A later, higher score in the same conversation is not a new lead again.
    await inbox.dm("igsid_priya", "Can I pay by UPI?", name="Priya")
    fake_ai.respond("analysis", analysis(lead_score=90, intent="purchase"))
    await inbox.analyze(conv)
    assert len(await lead_notes(inbox)) == 1


async def test_below_70_or_already_a_lead_is_not_announced(
    inbox: Inbox, fake_ai: FakeProvider
) -> None:
    await inbox.dm("igsid_arjun", "hi", name="Arjun")
    conv = await inbox.conversation_id("igsid_arjun")
    fake_ai.respond("analysis", analysis(lead_score=69, intent="greeting"))
    await inbox.analyze(conv)
    assert await lead_notes(inbox) == []

    # Scored 72 before this rule existed: crossing, not being high, makes a new lead.
    await inbox.set("conversations", conv, lead_score=72)
    await inbox.dm("igsid_arjun", "price of the blue one?", name="Arjun")
    fake_ai.respond("analysis", analysis(lead_score=85))
    await inbox.analyze(conv)
    assert await lead_notes(inbox) == []
