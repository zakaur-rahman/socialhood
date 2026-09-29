"""T5.8: the AI reply action for automations (FR-AUT-01, TR-AI-06, F-11 runtime).

An ai_reply automation drafts with the suggest prompt plus the business's instructions (2
credits, automation_ai_reply) and sends like the message action, with the disclosure line: a DM
through the send pipeline, or a comment's private reply through the account's queue. When the
answer is not in knowledge it sends nothing and escalates (the run is "escalated", the
conversation needs a human, the owners are notified, the question becomes a knowledge gap).

Done when: instructions reach the prompt; out-of-knowledge escalates instead of sending.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeCall, FakeProvider
from socialhood.ai.provider import AIError
from socialhood.platforms.sandbox import outbox
from socialhood.services.automations.runtime import Outcome
from socialhood.services.sending import Delivery
from socialhood.settings import Settings
from tests.support.ai import make_source
from tests.support.automations import make_automation
from tests.support.inbox import make_thread
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox
from tests.support.suggestions import answer, cannot

DISCLOSURE = "Sent automatically"
INSTRUCTIONS = "Mention the Diwali sale on every cake."
REPLY = "Shipping is free over ₹999."


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def world(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    clean_db: None,
    queue: None,
) -> AsyncIterator[World]:
    """A Pro workspace with an owner (for notifications), the disclosure line on, and the
    shipping FAQ."""
    async with platform_deps(api_settings, monkeypatch) as deps:
        world = await make_world(engine, redis, deps)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO subscriptions (workspace_id, plan, status, billing_anchor_day)"
                    " VALUES (:w, 'pro', 'active', 1)"
                ),
                {"w": world.wid},
            )
            await conn.execute(
                text(
                    "INSERT INTO workspace_members (workspace_id, user_id, role)"
                    " SELECT id, owner_user_id, 'owner' FROM workspaces WHERE id = :w"
                ),
                {"w": world.wid},
            )
            await conn.execute(
                text("UPDATE workspaces SET automation_disclosure = :d WHERE id = :w"),
                {"d": DISCLOSURE, "w": world.wid},
            )
        await make_source(
            engine, workspace_id=world.wid, question="How much is shipping?", body="Free over 999."
        )
        yield world


async def ai_automation(world: World, **values: Any) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "action": "ai_reply",
        "message_text": None,
        "ai_instructions": INSTRUCTIONS,
    }
    return await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=("shipping",),
        **{**defaults, **values},
    )


async def outbound(world: World) -> list[dict[str, Any]]:
    return await world.rows("SELECT * FROM messages WHERE direction = 'outbound'")


def the_call(fake: FakeProvider) -> FakeCall:
    [call] = fake.calls_for("suggest")
    return call


# ---------------------------------------------------------------- DMs


async def test_an_ai_dm_reply_follows_the_instructions(world: World, fake_ai: FakeProvider) -> None:
    automation_id = await ai_automation(world)
    thread = await make_thread(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        texts=("How much is shipping?",),
    )
    fake_ai.respond("suggest", answer(REPLY))

    assert await world.run("dm", thread.message_ids[0]) is Outcome.FIRED

    call = the_call(fake_ai)
    assert f"Instructions from the business for this reply: {INSTRUCTIONS}" in call.system
    assert "Customer [TARGET]: How much is shipping?" in call.contents[0].text
    assert "[k1] (How much is shipping?)" in call.contents[0].text
    run = await world.run_row()
    [dm] = await outbound(world)
    assert (run["result"], run["private_reply_message_id"]) == ("sent", dm["id"])
    assert (dm["source"], dm["automation_run_id"], dm["status"]) == (
        "automation",
        run["id"],
        "queued",
    )
    assert dm["text"] == f"{REPLY}\n\n{DISCLOSURE}"
    [trigger] = await world.rows(
        "SELECT automation_handled FROM messages WHERE id = :id", id=thread.message_ids[0]
    )
    assert trigger["automation_handled"] is True
    [draft] = await world.rows("SELECT * FROM reply_suggestions")
    assert (draft["automation_run_id"], draft["status"], draft["sent_message_id"]) == (
        run["id"],
        "sent",
        dm["id"],
    )
    [usage] = await world.rows("SELECT feature, credits, ref_id FROM ai_usage_events")
    assert usage == {"feature": "automation_ai_reply", "credits": 2, "ref_id": run["id"]}
    [automation] = await world.rows(
        "SELECT last_run_at FROM automations WHERE id = :id", id=automation_id
    )
    assert automation["last_run_at"] is not None

    assert await world.send(dm["id"]) is Delivery.SENT
    [sent] = outbox.SENT
    assert sent.message.text == f"{REPLY}\n\n{DISCLOSURE}"
    assert (await world.run_row())["result"] == "sent"
    # The inbox AI leaves the handled message alone; the run is not repeated.
    assert await world.run("dm", thread.message_ids[0]) is Outcome.ALREADY_RAN


async def test_out_of_knowledge_escalates_instead_of_sending(
    world: World, fake_ai: FakeProvider
) -> None:
    """Done-when: the automation sends nothing and the conversation needs a human."""
    await ai_automation(world)
    thread = await make_thread(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        texts=("Is shipping to Dubai possible?",),
    )
    fake_ai.respond("suggest", cannot())

    assert await world.run("dm", thread.message_ids[0]) is Outcome.FIRED

    run = await world.run_row()
    assert (run["result"], run["error_code"]) == ("escalated", "out_of_knowledge")
    assert run["error_message"] == (
        "Not sent: the answer isn't in your knowledge (whether you ship to Dubai)."
    )
    assert run["private_reply_message_id"] is None
    assert await outbound(world) == []
    assert not outbox.SENT
    [conv] = await world.rows("SELECT needs_human, needs_human_reason FROM conversations")
    assert conv == {"needs_human": True, "needs_human_reason": "out_of_knowledge"}
    [note] = await world.rows("SELECT type, body, link FROM notifications")
    assert note == {
        "type": "ai_escalated",
        "body": "AI didn't reply: the answer isn't in your knowledge.",
        "link": f"/inbox/{thread.conversation_id}",
    }
    [gap] = await world.rows("SELECT topic, example_message_ids FROM knowledge_gaps")
    assert gap == {"topic": "shipping to uae", "example_message_ids": [thread.message_ids[0]]}
    [draft] = await world.rows("SELECT status, can_answer FROM reply_suggestions")
    assert draft == {"status": "dismissed", "can_answer": False}


async def test_an_invented_link_escalates_as_blocked_output(
    world: World, fake_ai: FakeProvider
) -> None:
    """Sent without a person reading it, so only knowledge and brand settings may be quoted."""
    await ai_automation(world)
    thread = await make_thread(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        texts=("shipping cost?",),
    )
    fake_ai.respond("suggest", answer("Free over ₹999, see https://maple.example/shipping"))
    await world.run("dm", thread.message_ids[0])
    run = await world.run_row()
    assert (run["result"], run["error_code"]) == ("escalated", "output_blocked")
    assert await outbound(world) == []


async def test_a_retried_job_finishes_a_draft_it_started(
    world: World, fake_ai: FakeProvider
) -> None:
    await ai_automation(world)
    thread = await make_thread(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        texts=("How much is shipping?",),
    )

    def crash(call: FakeCall) -> Any:
        raise RuntimeError("the worker died mid-call")

    fake_ai.respond("suggest", crash, answer(REPLY))
    with pytest.raises(RuntimeError):
        await world.run("dm", thread.message_ids[0])
    assert (await world.run_row())["result"] == "queued"
    assert await outbound(world) == []

    assert await world.run("dm", thread.message_ids[0]) is Outcome.FIRED
    assert (await world.run_row())["result"] == "sent"
    assert len(await outbound(world)) == 1


async def test_a_failed_draft_fails_the_run_and_frees_the_message(
    world: World, fake_ai: FakeProvider
) -> None:
    await ai_automation(world)
    thread = await make_thread(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        texts=("How much is shipping?",),
    )
    fake_ai.respond("suggest", AIError("provider_error", retryable=True))
    await world.run("dm", thread.message_ids[0])
    run = await world.run_row()
    assert (run["result"], run["error_code"]) == ("failed", "ai_error")
    [trigger] = await world.rows("SELECT automation_handled FROM messages")
    assert trigger["automation_handled"] is False
    assert await world.rows("SELECT used FROM usage_counters") == [{"used": 0}]


# ---------------------------------------------------------------- comments (private replies)


async def comment_automation(world: World, **values: Any) -> uuid.UUID:
    return await ai_automation(
        world,
        trigger="comment_keyword",
        public_reply_texts=["Sent you a DM!"],
        **values,
    )


async def test_an_ai_private_reply_goes_through_the_queue(
    world: World, fake_ai: FakeProvider
) -> None:
    await comment_automation(world)
    comment_id = await world.comment("shipping price?", username="curious.cat")
    assert comment_id is not None
    fake_ai.respond("suggest", answer(REPLY))

    assert await world.run("comment", comment_id) is Outcome.FIRED
    assert (await world.run_row())["result"] == "queued"
    assert fake_ai.calls_for("suggest") == []  # drafted by the queue, just before sending
    [public] = outbox.COMMENT_REPLIES
    assert public.text == "Sent you a DM!"

    result = await world.drain()

    assert (result.sent, result.failed, result.escalated, result.remaining) == (1, 0, 0, 0)
    [private] = outbox.PRIVATE_REPLIES
    assert private.message.text == f"{REPLY}\n\n{DISCLOSURE}"
    call = the_call(fake_ai)
    assert f"Instructions from the business for this reply: {INSTRUCTIONS}" in call.system
    assert "Customer [TARGET]: shipping price?" in call.contents[0].text
    run = await world.run_row()
    [dm] = await outbound(world)
    assert (run["result"], run["private_reply_message_id"]) == ("sent", dm["id"])
    assert (dm["source"], dm["text"]) == ("automation", f"{REPLY}\n\n{DISCLOSURE}")
    [usage] = await world.rows("SELECT feature, ref_id FROM ai_usage_events")
    assert usage == {"feature": "automation_ai_reply", "ref_id": run["id"]}


async def test_an_ai_private_reply_that_cannot_answer_escalates(
    world: World, fake_ai: FakeProvider
) -> None:
    automation_id = await comment_automation(world)
    comment_id = await world.comment("shipping to Dubai?")
    assert comment_id is not None
    fake_ai.respond("suggest", cannot())
    await world.run("comment", comment_id)

    result = await world.drain()

    assert (result.sent, result.escalated, result.remaining, result.next_in_s) == (0, 1, 0, None)
    assert not outbox.PRIVATE_REPLIES
    run = await world.run_row()
    assert (run["result"], run["error_code"]) == ("escalated", "out_of_knowledge")
    assert run["error_message"].startswith("DM: Not sent: the answer isn't in your knowledge")
    # The commenter has no conversation yet: the owners are told about the automation.
    [note] = await world.rows("SELECT title, link FROM notifications")
    assert note == {"title": "An automation needs you", "link": f"/automations/{automation_id}"}
    [gap] = await world.rows("SELECT topic, occurrences FROM knowledge_gaps")
    assert gap == {"topic": "shipping to uae", "occurrences": 1}
    assert (await world.drain()).escalated == 0  # settled once
