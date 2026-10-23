"""GR-03: flow runs through the sandbox. Done when a two-branch flow with a question runs end to
end, from a DM and from a comment; plus branches and actions, the follow status, delays, the
reply window, stale taps, a run keeping its version, and the hand-off."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.platforms.sandbox import outbox
from socialhood.services.automations.runtime import Outcome
from socialhood.services.sending import Delivery
from socialhood.settings import Settings
from tests.support.automations import make_automation
from tests.support.ingest import jobs
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

LINK = "https://maple.example/catalogue"


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
    async with platform_deps(api_settings, monkeypatch) as deps:
        yield await make_world(engine, redis, deps)


def ref() -> str:
    return f"99{uuid.uuid4().int % 10**13:013d}"


def send(id: str, text_: str, **kw: Any) -> dict[str, Any]:
    return {"type": "send", "id": id, "text": text_, **kw}


def two_branch() -> dict[str, Any]:
    """Catalogue (after asking for their email) or prices, picked by a quick reply."""
    return {
        "start": "hello",
        "steps": [
            send(
                "hello",
                "Hi {first_name|there}! Catalogue or prices?",
                quick_replies=[
                    {"title": "Catalogue", "next": "email"},
                    {"title": "Prices", "next": "prices"},
                ],
            ),
            {
                "type": "ask",
                "id": "email",
                "text": "What's your email?",
                "expect": "email",
                "next": "catalogue",
            },
            send("catalogue", "Here it is.", buttons=[{"title": "Open", "url": LINK}]),
            send("prices", "Prices start at 499."),
        ],
    }


async def with_flow(
    world: World, definition: dict[str, Any], *, version: int = 1, **values: Any
) -> uuid.UUID:
    """An active automation saved as ``definition`` (keyword "link")."""
    automation_id = await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        **{"message_text": None, **values},
    )
    await save_flow(world, automation_id, definition, version=version)
    return automation_id


async def save_flow(
    world: World, automation_id: uuid.UUID, definition: dict[str, Any], *, version: int
) -> None:
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO automation_flows (workspace_id, automation_id, version, definition)"
                " VALUES (:w, :a, :v, CAST(:d AS jsonb))"
            ),
            {"w": world.wid, "a": automation_id, "v": version, "d": json.dumps(definition)},
        )
        await conn.execute(
            text("UPDATE automations SET flow_version = :v WHERE id = :a"),
            {"v": version, "a": automation_id},
        )


async def outbound(world: World) -> list[dict[str, Any]]:
    return await world.rows(
        "SELECT * FROM messages WHERE direction = 'outbound' ORDER BY occurred_at, created_at"
    )


async def steps(world: World, run_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    found = await world.rows(
        "SELECT step_id, status, detail FROM automation_run_steps WHERE run_id = :r", r=run_id
    )
    return {row["step_id"]: row for row in found}


async def flow_jobs() -> list[dict[str, Any]]:
    return [j for j in await jobs("run_automation") if j["args"]["kind"] == "flow"]


async def deliver_last(world: World, *, now: datetime | None = None) -> dict[str, Any]:
    """Send the newest outbound message (the send job) and return it."""
    message = (await outbound(world))[-1]
    assert await world.send(message["id"], now=now) is Delivery.SENT
    return message


async def started(world: World, author: str) -> dict[str, Any]:
    """A "link" DM from ``author`` fires the flow; its first message is delivered."""
    dm = await world.dm(author, "link please")
    assert dm is not None
    assert await world.run("dm", dm) is Outcome.FIRED
    await deliver_last(world)
    return await world.run_row()


# ---------------------------------------------------------------- the two-branch flow


async def test_a_dm_runs_the_flow_through_a_question(world: World) -> None:
    await with_flow(world, two_branch())
    author = ref()
    run = await started(world, author)
    [hello] = await outbound(world)
    assert hello["text"] == "Hi there! Catalogue or prices?"
    assert hello["quick_replies"] == [
        {"title": "Catalogue", "payload": f"shf:{run['id']}:hello:0"},
        {"title": "Prices", "payload": f"shf:{run['id']}:hello:1"},
    ]
    assert run["private_reply_message_id"] == hello["id"]
    assert (run["result"], run["flow_state"], run["step_id"]) == (
        "awaiting_reply",
        "replying",
        "hello",
    )

    tap = await world.dm(author, "Catalogue", payload=f"shf:{run['id']}:hello:0")
    assert tap is not None
    assert await world.run("dm", tap) is Outcome.ANSWERED
    [handled] = await world.rows("SELECT automation_handled FROM messages WHERE id = :id", id=tap)
    assert handled["automation_handled"] is True
    run = await world.run_row(run["id"])
    assert (run["result"], run["flow_state"], run["step_id"]) == ("sent", "next", "email")
    assert run["confirmed_at"] is not None
    assert len(await flow_jobs()) == 1

    assert await world.run("flow", run["id"]) is Outcome.FIRED
    question = await deliver_last(world)
    assert question["text"] == "What's your email?"
    assert (await world.run_row(run["id"]))["flow_state"] == "replying"

    # A wrong answer gets the retry prompt; the next one is saved to the contact.
    wrong = await world.dm(author, "not sure")
    assert wrong is not None
    assert await world.run("dm", wrong) is Outcome.ANSWERED
    retry = (await outbound(world))[-1]
    assert retry["text"] == "That doesn't look like an email address. Could you send it again?"
    assert (await world.run_row(run["id"]))["flow_state"] == "replying"
    right = await world.dm(author, "Priya@Example.com")
    assert right is not None
    assert await world.run("dm", right) is Outcome.ANSWERED
    [contact] = await world.rows(
        "SELECT email, email_source FROM contacts WHERE platform_user_id = :r", r=author
    )
    assert (contact["email"], contact["email_source"]) == ("priya@example.com", "flow")

    assert await world.run("flow", run["id"]) is Outcome.FIRED
    catalogue = await deliver_last(world)
    assert (catalogue["text"], catalogue["buttons"]) == (
        "Here it is.",
        [{"title": "Open", "url": LINK}],
    )
    run = await world.run_row(run["id"])
    assert (run["result"], run["flow_state"], run["step_id"]) == ("sent", "done", None)
    log = await steps(world, run["id"])
    assert {k: v["status"] for k, v in log.items()} == {
        "hello": "done",
        "email": "done",
        "catalogue": "done",
    }
    assert log["hello"]["detail"] == {"answer": "Catalogue", "option": 0}
    assert log["email"]["detail"] == {"tries": 2, "answer": "priya@example.com"}


async def test_the_other_branch(world: World) -> None:
    await with_flow(world, two_branch())
    author = ref()
    run = await started(world, author)
    tap = await world.dm(author, "Prices", payload=f"shf:{run['id']}:hello:1")
    assert tap is not None
    assert await world.run("dm", tap) is Outcome.ANSWERED
    assert await world.run("flow", run["id"]) is Outcome.FIRED
    prices = await deliver_last(world)
    assert prices["text"] == "Prices start at 499."
    assert set(await steps(world, run["id"])) == {"hello", "prices"}


async def test_a_comment_runs_the_flow_from_its_private_reply(world: World) -> None:
    await with_flow(
        world,
        two_branch(),
        trigger="comment_keyword",
        public_reply_texts=["Sent you a DM!"],
    )
    author = ref()
    comment = await world.comment("LINK please", author=author)
    assert comment is not None
    assert await world.run("comment", comment) is Outcome.FIRED
    assert (await world.drain()).sent == 1
    run = await world.run_row()
    [private] = outbox.PRIVATE_REPLIES
    assert private.message.text == "Hi there! Catalogue or prices?"
    assert [q.payload for q in private.message.quick_replies] == [
        f"shf:{run['id']}:hello:0",
        f"shf:{run['id']}:hello:1",
    ]
    assert (run["result"], run["flow_state"]) == ("awaiting_reply", "replying")
    assert (await steps(world, run["id"]))["hello"]["status"] == "waiting"

    tap = await world.dm(author, "Prices", payload=f"shf:{run['id']}:hello:1")
    assert tap is not None
    assert await world.run("dm", tap) is Outcome.ANSWERED
    assert await world.run("flow", run["id"]) is Outcome.FIRED
    prices = await deliver_last(world)
    assert prices["text"] == "Prices start at 499."
    run = await world.run_row(run["id"])
    assert (run["result"], run["flow_state"]) == ("sent", "done")


# ---------------------------------------------------------------- branches and actions


async def make_tag(world: World, name: str) -> uuid.UUID:
    async with world.engine.begin() as conn:
        found = await conn.execute(
            text("INSERT INTO tags (workspace_id, name) VALUES (:w, :n) RETURNING id"),
            {"w": world.wid, "n": name},
        )
        return found.scalar_one()


async def test_actions_and_a_branch_run_before_the_first_message(world: World) -> None:
    vip = await make_tag(world, "VIP")
    await with_flow(
        world,
        {
            "start": "tag",
            "steps": [
                {
                    "type": "action",
                    "id": "tag",
                    "action": {"kind": "add_tag", "tag_id": str(vip)},
                    "next": "check",
                },
                {
                    "type": "branch",
                    "id": "check",
                    "rules": [{"when": {"kind": "tag", "tag_id": str(vip)}, "next": "vip"}],
                    "otherwise": "regular",
                },
                send("vip", "Welcome back, VIP!"),
                send("regular", "Hello!"),
            ],
        },
    )
    author = ref()
    run = await started(world, author)
    [message] = await outbound(world)
    assert message["text"] == "Welcome back, VIP!"
    [tagged] = await world.rows("SELECT tag_id FROM contact_tags")
    assert tagged["tag_id"] == vip
    log = await steps(world, run["id"])
    assert log["check"]["detail"] == {"rule": "0"}
    assert (await world.run_row(run["id"]))["flow_state"] == "done"


async def test_a_branch_on_following_reads_it_fresh(world: World) -> None:
    flow = {
        "start": "message",
        "steps": [
            send("message", "Here's the link.", next="follows"),
            {
                "type": "branch",
                "id": "follows",
                "rules": [
                    {"when": {"kind": "follows_business", "follows": False}, "next": "nudge"}
                ],
            },
            send(
                "nudge", "Follow us for more!", buttons=[{"title": "View profile", "profile": True}]
            ),
        ],
    }
    await with_flow(world, flow)
    stranger, fan = ref(), ref()
    outbox.set_follows(stranger, False)
    outbox.set_follows(fan, True)

    run = await started(world, stranger)
    assert (run["flow_state"], run["step_id"]) == ("next", "follows")
    assert await world.run("flow", run["id"]) is Outcome.FIRED
    nudge = (await outbound(world))[-1]
    assert nudge["text"] == "Follow us for more!"
    assert nudge["buttons"][0]["title"] == "View profile"
    assert (await world.run_row(run["id"]))["follows_business"] is False

    before = len(await outbound(world))
    dm = await world.dm(fan, "link")
    assert dm is not None
    assert await world.run("dm", dm) is Outcome.FIRED
    await deliver_last(world)
    [fan_run] = await world.rows(
        "SELECT * FROM automation_runs WHERE trigger_message_id = :m", m=dm
    )
    assert await world.run("flow", fan_run["id"]) is Outcome.FIRED
    assert len(await outbound(world)) == before + 1  # their message only
    assert (await world.run_row(fan_run["id"]))["flow_state"] == "done"


async def test_a_delay_waits_and_the_window_is_kept(world: World) -> None:
    flow = {
        "start": "a",
        "steps": [
            send("a", "First.", next="wait"),
            {"type": "delay", "id": "wait", "seconds": 3600, "next": "b"},
            send("b", "An hour later."),
        ],
    }
    await with_flow(world, flow)
    run = await started(world, ref())
    now = datetime.now(UTC)
    assert await world.run("flow", run["id"], now=now) is Outcome.FIRED
    run = await world.run_row(run["id"])
    assert (run["flow_state"], run["step_id"]) == ("delaying", "b")
    assert run["wait_until"] is not None
    assert [j["deferred"] for j in await flow_jobs()][-1] is True
    # Early: nothing yet.
    assert await world.run("flow", run["id"], now=now + timedelta(minutes=5)) is Outcome.ALREADY_RAN
    assert len(await outbound(world)) == 1
    assert await world.run("flow", run["id"], now=now + timedelta(hours=1)) is Outcome.FIRED
    assert (await outbound(world))[-1]["text"] == "An hour later."


async def test_a_closed_window_ends_the_run(world: World) -> None:
    flow = {
        "start": "a",
        "steps": [
            send("a", "First.", next="wait"),
            {"type": "delay", "id": "wait", "seconds": 23 * 3600, "next": "b"},
            send("b", "Too late."),
        ],
    }
    await with_flow(world, flow)
    run = await started(world, ref())
    now = datetime.now(UTC)
    assert await world.run("flow", run["id"], now=now) is Outcome.FIRED
    later = now + timedelta(hours=25)
    assert await world.run("flow", run["id"], now=later) is Outcome.FIRED
    run = await world.run_row(run["id"])
    assert run["flow_state"] == "done"
    failed = (await steps(world, run["id"]))["b"]
    assert (failed["status"], failed["detail"]["error_code"]) == ("failed", "reply_window_closed")
    assert len(await outbound(world)) == 1


# ---------------------------------------------------------------- answers


async def test_a_tap_on_a_step_left_behind_sends_nothing(world: World) -> None:
    await with_flow(world, two_branch())
    author = ref()
    run = await started(world, author)
    first = await world.dm(author, "Prices", payload=f"shf:{run['id']}:hello:1")
    assert first is not None
    assert await world.run("dm", first) is Outcome.ANSWERED
    again = await world.dm(author, "Catalogue", payload=f"shf:{run['id']}:hello:0")
    assert again is not None
    assert await world.run("dm", again) is Outcome.ANSWERED
    assert (await world.run_row(run["id"]))["step_id"] == "prices"
    assert len(await flow_jobs()) == 1


async def test_typed_text_answers_only_where_it_leads_somewhere(world: World) -> None:
    await with_flow(world, two_branch())  # "hello" has no on_text
    author = ref()
    run = await started(world, author)
    typed = await world.dm(author, "hmm")
    assert typed is not None
    assert await world.run("dm", typed) is Outcome.NO_MATCH  # keyword matching as usual
    assert (await world.run_row(run["id"]))["flow_state"] == "replying"


async def test_a_run_keeps_the_version_it_started_on(world: World) -> None:
    automation_id = await with_flow(world, two_branch())
    author = ref()
    run = await started(world, author)
    assert run["flow_version"] == 1
    changed = two_branch()
    changed["steps"][3]["text"] = "New prices!"
    await save_flow(world, automation_id, changed, version=2)
    tap = await world.dm(author, "Prices", payload=f"shf:{run['id']}:hello:1")
    assert tap is not None
    assert await world.run("dm", tap) is Outcome.ANSWERED
    assert await world.run("flow", run["id"]) is Outcome.FIRED
    assert (await outbound(world))[-1]["text"] == "Prices start at 499."


async def test_a_hand_off_puts_it_in_needs_you(world: World) -> None:
    await with_flow(
        world,
        {
            "start": "a",
            "steps": [
                send("a", "Someone from the team will reply soon.", next="handoff"),
                {"type": "action", "id": "handoff", "action": {"kind": "hand_off"}},
            ],
        },
    )
    run = await started(world, ref())
    assert await world.run("flow", run["id"]) is Outcome.FIRED
    [conv] = await world.rows("SELECT needs_human, ai_paused_until FROM conversations")
    assert conv["needs_human"] is True
    assert conv["ai_paused_until"] is not None
    assert (await world.run_row(run["id"]))["flow_state"] == "done"
