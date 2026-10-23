"""GR-18: the rules that move a lead by themselves. Done when an analysis with a lead score of 60 or
more (or a buying intent) qualifies a new lead and only a new lead, and the gone-cold job flags
qualified and follow-up leads that went quiet, once, in their own workspace."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import time_machine
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider
from socialhood.jobs.tasks.leads import mark_cold
from tests.support.analysis import Inbox, add_owner_member, make_inbox
from tests.support.inbox import make_account, make_workspace

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
CUSTOMER = "igsid_priya"


@pytest.fixture
async def inbox(engine: AsyncEngine, redis: Redis, clean_db: None, queue: None) -> Inbox:
    return await make_inbox(engine, redis)


def analysis(**values: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "intent": "other",
        "sentiment": "neutral",
        "sentiment_score": 0.1,
        "priority": "medium",
        "lead_score": 20,
        "language": "en",
        "topics": [],
        "needs_reply": False,
        "needs_human": False,
        "needs_human_reason": None,
    }
    return {**base, **values}


async def contact_row(inbox: Inbox, ref: str = CUSTOMER) -> dict[str, Any]:
    [row] = await inbox.rows(
        "SELECT * FROM contacts WHERE platform_user_id = :r AND workspace_id = :w",
        r=ref,
        w=inbox.wid,
    )
    return row


async def notes(inbox: Inbox) -> list[dict[str, Any]]:
    return await inbox.rows(
        "SELECT * FROM notifications WHERE workspace_id = :w ORDER BY created_at, id", w=inbox.wid
    )


async def changes(inbox: Inbox) -> list[dict[str, Any]]:
    return await inbox.rows(
        "SELECT * FROM lead_stage_changes WHERE workspace_id = :w ORDER BY created_at, id",
        w=inbox.wid,
    )


async def analysed(inbox: Inbox, fake_ai: FakeProvider, **values: Any) -> uuid.UUID:
    fake_ai.respond("analysis", analysis(**values))
    await inbox.dm(CUSTOMER, "Is the gold one still available?")
    conv_id = await inbox.conversation_id(CUSTOMER)
    await inbox.analyze(conv_id)
    return conv_id


# ---------------------------------------------------------------- qualification


async def test_a_high_lead_score_qualifies_a_new_lead(inbox: Inbox, fake_ai: FakeProvider) -> None:
    await analysed(inbox, fake_ai, lead_score=72)
    contact = await contact_row(inbox)
    assert contact["lead_stage"] == "qualified"
    assert contact["lead_stage_reason"] == "Lead score reached 72."
    assert contact["lead_stage_at"] is not None
    [change] = await changes(inbox)
    assert (change["from_stage"], change["to_stage"], change["actor_kind"]) == (
        "new",
        "qualified",
        "rule",
    )
    assert (change["rule"], change["actor_user_id"]) == ("lead_score", None)


async def test_a_buying_intent_qualifies_at_a_lower_score(
    inbox: Inbox, fake_ai: FakeProvider
) -> None:
    await analysed(inbox, fake_ai, intent="pricing", lead_score=45)
    contact = await contact_row(inbox)
    assert contact["lead_stage"] == "qualified"
    assert contact["lead_stage_reason"] == "They asked about pricing (lead score 45)."
    [change] = await changes(inbox)
    assert change["rule"] == "intent"


async def test_a_low_score_or_a_plain_intent_leaves_the_lead_new(
    inbox: Inbox, fake_ai: FakeProvider
) -> None:
    await analysed(inbox, fake_ai, intent="support", lead_score=55)
    assert (await contact_row(inbox))["lead_stage"] == "new"
    assert await changes(inbox) == []


@pytest.mark.parametrize("stage", ["qualified", "follow_up", "won", "lost"])
async def test_a_lead_that_has_moved_on_is_never_pulled_back(
    inbox: Inbox, fake_ai: FakeProvider, stage: str
) -> None:
    await inbox.dm(CUSTOMER, "hello")
    contact = await contact_row(inbox)
    await inbox.set("contacts", contact["id"], lead_stage=stage)
    fake_ai.respond("analysis", analysis(lead_score=90))
    await inbox.analyze(await inbox.conversation_id(CUSTOMER))
    assert (await contact_row(inbox))["lead_stage"] == stage
    assert await changes(inbox) == []


# ---------------------------------------------------------------- gone cold


async def quiet_lead(
    inbox: Inbox,
    *,
    stage: str,
    wrote: datetime = T0,
    ref: str = CUSTOMER,
    staged: datetime | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """A lead in ``stage`` whose customer last wrote at ``wrote``; (contact id, conversation id)."""
    with time_machine.travel(wrote, tick=False):
        await inbox.dm(ref, "Is the gold one still available?", at=wrote, name="Priya")
    contact = await contact_row(inbox, ref)
    await inbox.set("contacts", contact["id"], lead_stage=stage, lead_stage_at=staged or wrote)
    return contact["id"], await inbox.conversation_id(ref)


async def run_job(inbox: Inbox, at: datetime) -> list[uuid.UUID]:
    with time_machine.travel(at, tick=False):
        return await mark_cold(inbox.maker, inbox.redis, now=at)


async def test_a_qualified_lead_that_went_quiet_moves_to_follow_up_and_the_team_is_told(
    inbox: Inbox,
) -> None:
    contact_id, conv_id = await quiet_lead(inbox, stage="qualified")

    assert await run_job(inbox, T0 + timedelta(days=6, hours=23)) == []
    flagged = await run_job(inbox, T0 + timedelta(days=7, hours=1))
    assert flagged == [contact_id]

    contact = await contact_row(inbox)
    assert contact["lead_stage"] == "follow_up"
    assert contact["lead_cold_at"] == T0 + timedelta(days=7, hours=1)
    assert contact["lead_stage_reason"] == "No reply for 7 days."
    [change] = await changes(inbox)
    assert (change["from_stage"], change["to_stage"], change["actor_kind"], change["rule"]) == (
        "qualified",
        "follow_up",
        "rule",
        "gone_cold",
    )
    [note] = await notes(inbox)
    assert (note["type"], note["title"]) == ("lead_cold", "Priya has gone cold")
    assert note["link"] == f"/inbox/{conv_id}"
    assert note["channels"] == ["in_app"]


async def test_a_follow_up_lead_stays_in_follow_up_but_is_flagged(inbox: Inbox) -> None:
    contact_id, _ = await quiet_lead(inbox, stage="follow_up")
    assert await run_job(inbox, T0 + timedelta(days=8)) == [contact_id]
    contact = await contact_row(inbox)
    assert (contact["lead_stage"], contact["lead_cold_at"]) == ("follow_up", T0 + timedelta(days=8))
    assert await changes(inbox) == []  # no move, so no history row
    [note] = await notes(inbox)
    assert note["title"] == "Priya has gone cold"


async def test_the_job_is_idempotent_and_flags_again_after_a_new_message(inbox: Inbox) -> None:
    contact_id, _ = await quiet_lead(inbox, stage="follow_up")
    first = T0 + timedelta(days=8)
    assert await run_job(inbox, first) == [contact_id]
    assert await run_job(inbox, first + timedelta(hours=1)) == []
    assert len(await notes(inbox)) == 1

    # She writes again; a week later she is quiet again and is flagged a second time.
    wrote = first + timedelta(days=1)
    with time_machine.travel(wrote, tick=False):
        await inbox.dm(CUSTOMER, "Still thinking", at=wrote)
    assert await run_job(inbox, wrote + timedelta(days=3)) == []
    assert await run_job(inbox, wrote + timedelta(days=8)) == [contact_id]
    assert len(await notes(inbox)) == 2


@pytest.mark.parametrize("stage", ["new", "won", "lost"])
async def test_only_qualified_and_follow_up_leads_go_cold(inbox: Inbox, stage: str) -> None:
    await quiet_lead(inbox, stage=stage)
    assert await run_job(inbox, T0 + timedelta(days=30)) == []
    assert (await contact_row(inbox))["lead_cold_at"] is None


async def test_the_days_come_from_the_workspace_and_a_recent_move_counts(
    inbox: Inbox, engine: AsyncEngine
) -> None:
    await inbox.set("workspaces", inbox.wid, lead_cold_days=3)
    contact_id, _ = await quiet_lead(inbox, stage="qualified", staged=T0 + timedelta(days=5))
    # Quiet for 4 days, but a member moved the lead to qualified 1 day ago: not yet.
    assert await run_job(inbox, T0 + timedelta(days=6)) == []
    assert await run_job(inbox, T0 + timedelta(days=8, hours=1)) == [contact_id]
    [note] = await notes(inbox)
    assert "3 days" in note["body"]


async def test_each_workspace_is_judged_by_its_own_setting(
    inbox: Inbox, engine: AsyncEngine, redis: Redis
) -> None:
    other_id = await make_workspace(engine)
    await add_owner_member(engine, other_id)
    other_account = await make_account(engine, other_id)
    other = Inbox(engine, redis, other_id, other_account, inbox.settings)
    await other.set("workspaces", other_id, lead_cold_days=30)

    mine, _ = await quiet_lead(inbox, stage="follow_up")
    with time_machine.travel(T0, tick=False):
        await other.dm(CUSTOMER, "Hello", at=T0)
    theirs = (await contact_row(other))["id"]
    await other.set("contacts", theirs, lead_stage="follow_up", lead_stage_at=T0)

    assert await run_job(inbox, T0 + timedelta(days=10)) == [mine]
    assert (await contact_row(other))["lead_cold_at"] is None
    assert len(await notes(other)) == 0
    assert len(await notes(inbox)) == 1
    assert await run_job(inbox, T0 + timedelta(days=31)) == [theirs]
