"""T4.8: tap first and the follow nudge through the sandbox (FR-AUT-21, FR-AUT-22).

Done when: a comment gets the opening; a tap or any reply sends the message once with the real
first name; a non-follower gets the nudge after it and a follower does not; nothing is ever
withheld for not following. Plus the text-only fallback when Instagram refuses the quick reply,
the 7-day limit on answers, cooldowns, a failed public reply, and DM keyword runs' nudges.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import OutboundMessage, SendResult
from socialhood.platforms.events import InboundMessage
from socialhood.platforms.sandbox import outbox
from socialhood.platforms.sandbox.adapter import SandboxAdapter
from socialhood.repositories import social_accounts as accounts
from socialhood.services.automations.runtime import Outcome
from socialhood.services.automations.templates import OPENING_TEXT
from socialhood.services.ingest import ingest
from socialhood.services.sending import Delivery
from socialhood.settings import Settings
from tests.support.automations import make_automation
from tests.support.inbox import make_asset, make_thread
from tests.support.ingest import jobs
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

OPENING = OPENING_TEXT.replace("{first_name|there}", "there")
MESSAGE = "Hi {first_name|there}! Here's the link."
SHOP = {"title": "Shop", "url": "https://maple.example/shop"}
NUDGE = "Enjoying this, {first_name|friend}? Follow us for more like it."


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


async def tap_first(world: World, **values: Any) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "trigger": "comment_keyword",
        "message_text": MESSAGE,
        "message_buttons": [SHOP],
        "public_reply_texts": ["Sent you a DM!"],
        "confirm_first": True,
        "opening_text": OPENING_TEXT,
        "opening_button": "Send me the link",
        "follow_nudge_text": NUDGE,
    }
    return await make_automation(
        world.engine, workspace_id=world.wid, account_id=world.account_id, **{**defaults, **values}
    )


def ref() -> str:
    return f"99{uuid.uuid4().int % 10**13:013d}"


async def opened(world: World, author: str, *, at: datetime | None = None) -> dict[str, Any]:
    """A LINK comment from ``author``, its run and its opening sent: the run row."""
    comment_id = await world.comment("LINK please", author=author, at=at)
    assert comment_id is not None
    assert await world.run("comment", comment_id, now=at) is Outcome.FIRED
    drained = await world.drain(now=at)
    assert drained.sent == 1
    [run] = await world.rows(
        "SELECT * FROM automation_runs WHERE trigger_comment_id = :c", c=comment_id
    )
    return run


async def outbound(world: World) -> list[dict[str, Any]]:
    return await world.rows(
        "SELECT * FROM messages WHERE direction = 'outbound' ORDER BY occurred_at, created_at"
    )


async def nudge_jobs() -> list[dict[str, Any]]:
    return [j for j in await jobs("run_automation") if j["args"]["kind"] == "nudge"]


# ---------------------------------------------------------------- the opening


async def test_a_comment_gets_the_opening_with_one_quick_reply(world: World) -> None:
    async with world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET automation_disclosure = 'Sent automatically'")
        )
    await tap_first(world)
    author = ref()
    run = await opened(world, author)

    [reply] = outbox.COMMENT_REPLIES  # the public reply works as before
    assert reply.text == "Sent you a DM!"
    [private] = outbox.PRIVATE_REPLIES
    assert private.message.text == f"{OPENING}\n\nSent automatically"
    assert [(q.title, q.payload) for q in private.message.quick_replies] == [
        ("Send me the link", f"shr:{run['id']}")
    ]
    assert private.message.buttons == ()  # the message's buttons come after the answer
    assert run["result"] == "awaiting_reply"
    assert run["confirmed_at"] is None
    [opening] = await outbound(world)
    assert opening["quick_replies"] == [
        {"title": "Send me the link", "payload": f"shr:{run['id']}"}
    ]
    assert (opening["status"], opening["buttons"]) == ("sent", [])
    assert run["private_reply_message_id"] == opening["id"]
    assert not outbox.SENT


async def test_a_refused_quick_reply_goes_again_as_text(world: World) -> None:
    await tap_first(world)
    outbox.reject_quick_replies()
    author = ref()
    run = await opened(world, author)

    [private] = outbox.PRIVATE_REPLIES  # the refused one never reached anyone
    assert private.message.text == OPENING
    assert private.message.quick_replies == ()
    [opening] = await outbound(world)
    assert (opening["status"], opening["quick_replies"]) == ("sent", [])
    assert run["result"] == "awaiting_reply"

    # The copy asks them to reply, and a reply releases the message.
    reply = await world.dm(author, "yes please")
    assert reply is not None
    assert await world.run("dm", reply) is Outcome.ANSWERED
    assert len(await outbound(world)) == 2


async def test_an_early_echo_of_the_opening_still_waits_for_the_answer(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The opening's echo can settle it before the queue does (C-011): the run still waits."""
    await tap_first(world)
    author = ref()
    original = SandboxAdapter.private_reply

    async def echoing(
        self: SandboxAdapter, acct: SocialAccount, comment_ref: str, message: OutboundMessage
    ) -> SendResult:
        result = await original(self, acct, comment_ref, message)
        echo = InboundMessage(
            account_ref="sandbox",
            occurred_at=datetime.now(UTC),
            contact_ref=author,
            contact_name=None,
            platform_message_id=result.platform_message_id or "mid_echo",
            kind="text",
            text=message.text,
            is_echo=True,
        )
        with workspace_scope(world.wid):
            async with world.maker() as session:
                stored = await accounts.get(session, world.account_id)
                assert stored is not None
                await ingest(session, stored, [echo])
                await session.commit()
        return result

    monkeypatch.setattr(SandboxAdapter, "private_reply", echoing)
    run = await opened(world, author)
    assert run["result"] == "awaiting_reply"
    [opening] = await outbound(world)
    assert (opening["status"], opening["platform_message_id"]) == (
        "sent",
        outbox.PRIVATE_REPLIES[0].platform_message_id,
    )


# ---------------------------------------------------------------- the answer


async def test_a_tap_sends_the_message_once_with_the_real_first_name(world: World) -> None:
    asset_id = await make_asset(world.engine, workspace_id=world.wid)
    await tap_first(world, message_media_asset_id=asset_id)
    author = ref()
    outbox.set_follows(author, True)
    run = await opened(world, author)
    [contact] = await world.rows("SELECT * FROM contacts WHERE platform_user_id = :r", r=author)
    assert contact["display_name"] is None  # a commenter is known by username only

    tap = await world.dm(author, "Send me the link", payload=f"shr:{run['id']}", mid="mid_tap")
    assert tap is not None
    assert await world.run("dm", tap) is Outcome.ANSWERED

    [contact] = await world.rows("SELECT * FROM contacts WHERE platform_user_id = :r", r=author)
    short = author[-4:]
    assert contact["display_name"] == f"Sandbox customer {short}"  # the fresh profile
    assert (contact["follows_business"], contact["follows_checked_at"] is not None) == (True, True)
    [handled] = await world.rows("SELECT * FROM messages WHERE id = :id", id=tap)
    assert handled["automation_handled"] is True
    assert handled["quick_reply_payload"] == f"shr:{run['id']}"
    run = await world.run_row(run["id"])
    assert run["confirmed_at"] is not None
    assert (run["result"], run["follows_business"]) == ("sent", True)
    opening, message = await outbound(world)
    assert run["private_reply_message_id"] == message["id"]
    assert message["automation_run_id"] == run["id"]
    assert (message["source"], message["status"]) == ("automation", "queued")
    assert message["text"] == "Hi Sandbox! Here's the link."
    assert message["buttons"] == [SHOP]
    assert [a["type"] for a in message["attachments"]] == ["image"]
    assert message["conversation_id"] == opening["conversation_id"]
    [comment] = await world.rows("SELECT private_reply_message_id FROM comments")
    assert comment["private_reply_message_id"] == opening["id"]  # the comment keeps its reply
    # Their tap counts as a reply to the private reply (FR-AUT-16).
    assert run["contact_replied_at"] is not None

    assert await world.send(message["id"]) is Delivery.SENT
    image, text_part = outbox.SENT
    assert image.message.attachment is not None
    assert text_part.message.text == "Hi Sandbox! Here's the link."
    assert [b.title for b in text_part.message.buttons] == ["Shop"]
    assert (await world.run_row(run["id"]))["result"] == "sent"
    assert await nudge_jobs() == []  # a follower: no nudge

    # A second tap, and the same webhook again, send nothing more.
    again = await world.dm(author, "Send me the link", payload=f"shr:{run['id']}")
    assert again is not None
    assert await world.run("dm", again) is Outcome.ANSWERED
    assert await world.dm(author, "Send me the link", mid="mid_tap") is None
    assert await world.run("dm", tap) is Outcome.ALREADY_RAN
    assert len(await outbound(world)) == 2
    assert len(outbox.SENT) == 2


async def test_a_typed_reply_releases_it_and_no_keyword_automation_fires(
    world: World,
) -> None:
    await tap_first(world)
    # A DM keyword automation that would match both the tap's text and the reply.
    await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=("link",),
        message_text="The DM keyword answer",
    )
    author = ref()
    run = await opened(world, author)

    reply = await world.dm(author, "the link please")
    assert reply is not None
    [job] = [j for j in await jobs("run_automation") if j["args"]["trigger_id"] == str(reply)]
    assert job["args"]["kind"] == "dm"
    assert await world.run("dm", reply) is Outcome.ANSWERED
    assert (await world.run_row(run["id"]))["result"] == "sent"
    texts = [m["text"] for m in await outbound(world)]
    assert texts == [OPENING, "Hi Sandbox! Here's the link."]
    runs = await world.rows("SELECT trigger_message_id FROM automation_runs")
    assert [r["trigger_message_id"] for r in runs] == [None]  # no DM keyword run

    # Their next message is theirs again: keyword automations answer it.
    later = await world.dm(author, "one more link?")
    assert later is not None
    assert await world.run("dm", later) is Outcome.FIRED


async def test_a_typed_reply_releases_every_waiting_opening_oldest_first(world: World) -> None:
    first = await tap_first(world, cooldown_hours=0, message_text="First {first_name}")
    second = await tap_first(world, cooldown_hours=0, message_text="Second", priority=200)
    author = ref()
    one = await opened(world, author)
    # The first pauses, so the second answers the next comment. An opening already sent is
    # still answered: the person was told the message would follow.
    async with world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE automations SET status = 'paused' WHERE id = :i"), {"i": first}
        )
    two = await opened(world, author)
    assert (one["automation_id"], two["automation_id"]) == (first, second)

    reply = await world.dm(author, "ok")
    assert reply is not None
    assert await world.run("dm", reply) is Outcome.ANSWERED
    released = [await world.run_row(run["id"]) for run in (one, two)]
    assert [r["result"] for r in released] == ["sent", "sent"]
    by_id = {m["id"]: m["text"] for m in await outbound(world)}
    assert [by_id[r["private_reply_message_id"]] for r in released] == ["First Sandbox", "Second"]
    # Queued oldest first: their sends go out in that order in the conversation.
    sends = [j["args"]["message_id"] for j in await jobs("send_message")]
    assert sends == [str(r["private_reply_message_id"]) for r in released]


async def test_a_tap_answers_only_its_own_run(world: World) -> None:
    await tap_first(world, cooldown_hours=0)
    author, other = ref(), ref()
    one = await opened(world, author)
    two = await opened(world, author)
    elsewhere = await opened(world, other)

    # Someone else's payload is no tap of theirs: it is read as a reply to their own openings.
    tap = await world.dm(author, "Send me the link", payload=f"shr:{two['id']}")
    assert tap is not None
    assert await world.run("dm", tap) is Outcome.ANSWERED
    results = {
        r["id"]: r["result"] for r in await world.rows("SELECT id, result FROM automation_runs")
    }
    assert results == {
        one["id"]: "awaiting_reply",
        two["id"]: "sent",
        elsewhere["id"]: "awaiting_reply",
    }

    stolen = await world.dm(author, "Send me the link", payload=f"shr:{elsewhere['id']}")
    assert stolen is not None
    assert await world.run("dm", stolen) is Outcome.ANSWERED
    results = {
        r["id"]: r["result"] for r in await world.rows("SELECT id, result FROM automation_runs")
    }
    assert results == {one["id"]: "sent", two["id"]: "sent", elsewhere["id"]: "awaiting_reply"}


async def test_openings_older_than_seven_days_are_not_released(world: World) -> None:
    await tap_first(world)
    author = ref()
    long_ago = datetime.now(UTC) - timedelta(days=8)
    run = await opened(world, author, at=long_ago)
    assert run["result"] == "awaiting_reply"

    reply = await world.dm(author, "is it still there?")
    assert reply is not None
    assert all(j["args"]["trigger_id"] != str(reply) for j in await jobs("run_automation"))
    assert await world.run("dm", reply) is Outcome.NO_MATCH
    assert (await world.run_row(run["id"]))["result"] == "awaiting_reply"
    [msg] = await world.rows("SELECT automation_handled FROM messages WHERE id = :i", i=reply)
    assert msg["automation_handled"] is False


async def test_a_waiting_run_counts_toward_the_cooldown(world: World) -> None:
    await tap_first(world)
    author = ref()
    await opened(world, author)
    again = await world.comment("LINK again", author=author)
    assert again is not None
    assert await world.run("comment", again) is Outcome.SKIPPED
    [skipped] = await world.rows(
        "SELECT result FROM automation_runs WHERE trigger_comment_id = :c", c=again
    )
    assert skipped["result"] == "skipped_cooldown"


async def test_a_failed_public_reply_makes_the_answered_run_partial(world: World) -> None:
    await tap_first(world)
    outbox.fail_next("platform_rejected", kind="comment_reply")
    author = ref()
    run = await opened(world, author)
    assert (run["result"], run["error_code"]) == ("awaiting_reply", "platform_rejected")

    reply = await world.dm(author, "yes")
    assert reply is not None
    assert await world.run("dm", reply) is Outcome.ANSWERED
    run = await world.run_row(run["id"])
    assert run["result"] == "partial"
    assert run["error_message"].startswith("Public reply: ")
    message = (await outbound(world))[-1]

    outbox.fail_next("recipient_unavailable", kind="send")
    assert await world.send(message["id"]) is Delivery.FAILED
    run = await world.run_row(run["id"])
    assert run["result"] == "failed"
    assert "Public reply: " in run["error_message"]
    assert "DM: This person can't receive messages right now." in run["error_message"]

    async with world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE messages SET status = 'queued' WHERE id = :id"), {"id": message["id"]}
        )
    assert await world.send(message["id"]) is Delivery.SENT
    run = await world.run_row(run["id"])
    assert (run["result"], run["error_code"]) == ("partial", "platform_rejected")
    assert "DM:" not in run["error_message"]


async def test_a_reply_to_an_opening_is_enqueued_without_dm_automations(world: World) -> None:
    await tap_first(world)
    author = ref()
    await opened(world, author)
    reply = await world.dm(author, "hi")
    assert reply is not None
    [job] = [j for j in await jobs("run_automation") if j["args"]["trigger_id"] == str(reply)]
    assert job["queueing_lock"] == f"automation:dm:{reply}"
    # Someone with nothing waiting: no DM automation, no job.
    stranger = await world.dm(ref(), "hello")
    assert all(j["args"]["trigger_id"] != str(stranger) for j in await jobs("run_automation"))


# ---------------------------------------------------------------- the follow nudge (FR-AUT-22)


@pytest.mark.parametrize(("follows", "nudged"), [(False, True), (True, False), (None, False)])
async def test_the_nudge_follows_the_message_for_non_followers_only(
    world: World, follows: bool | None, nudged: bool
) -> None:
    async with world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET automation_disclosure = 'Sent automatically'")
        )
    await tap_first(world, follow_nudge=True)
    author = ref()
    outbox.set_follows(author, follows)
    run = await opened(world, author)
    reply = await world.dm(author, "yes")
    assert reply is not None
    assert await world.run("dm", reply) is Outcome.ANSWERED
    run = await world.run_row(run["id"])
    assert run["follows_business"] is follows
    [_, message] = await outbound(world)
    # Nothing is held back: the message went to everyone, whatever they follow.
    assert message["text"] == "Hi Sandbox! Here's the link.\n\nSent automatically"
    assert await nudge_jobs() == []  # not before the message is sent

    assert await world.send(message["id"]) is Delivery.SENT
    jobs_now = await nudge_jobs()
    if not nudged:
        assert jobs_now == []
        assert (await world.run_row(run["id"]))["nudge_message_id"] is None
        return
    [job] = jobs_now
    assert job["queueing_lock"] == f"automation:nudge:{run['id']}"
    assert await world.run("nudge", run["id"]) is Outcome.FIRED
    run = await world.run_row(run["id"])
    [_, _, nudge] = await outbound(world)
    assert run["nudge_message_id"] == nudge["id"]
    assert (
        nudge["text"] == "Enjoying this, Sandbox? Follow us for more like it.\n\nSent automatically"
    )
    assert nudge["buttons"] == [
        {"title": "View profile", "url": "https://www.instagram.com/maple.bakery/"}
    ]
    assert (nudge["source"], nudge["automation_run_id"]) == ("automation", run["id"])
    assert nudge["occurred_at"] >= message["occurred_at"]
    assert await world.send(nudge["id"]) is Delivery.SENT
    assert [s.message.text for s in outbox.SENT] == [
        "Hi Sandbox! Here's the link.\n\nSent automatically",
        "Enjoying this, Sandbox? Follow us for more like it.\n\nSent automatically",
    ]
    assert (await world.run_row(run["id"]))["result"] == "sent"  # the nudge leaves the run alone

    # Once only.
    assert await world.run("nudge", run["id"]) is Outcome.ALREADY_RAN
    assert len(await outbound(world)) == 3


async def test_a_dm_keyword_run_checks_the_follow_status_after_its_message(world: World) -> None:
    await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=("price",),
        message_text="Prices are on maple.example",
        follow_nudge=True,
        follow_nudge_text="Follow us for new bakes!",
        cooldown_hours=0,
    )
    fan, stranger = f"igsid_follower_{uuid.uuid4().hex[:6]}", f"igsid_{uuid.uuid4().hex[:8]}"
    for contact_ref, expected in ((fan, True), (stranger, False)):
        thread = await make_thread(
            world.engine,
            workspace_id=world.wid,
            account_id=world.account_id,
            contact_ref=contact_ref,
            texts=("price?",),
        )
        assert await world.run("dm", thread.message_ids[0]) is Outcome.FIRED
        [dm] = await world.rows(
            "SELECT id FROM messages WHERE conversation_id = :c AND direction = 'outbound'",
            c=thread.conversation_id,
        )
        assert await world.send(dm["id"]) is Delivery.SENT
        [run] = await world.rows(
            "SELECT * FROM automation_runs WHERE trigger_message_id = :m", m=thread.message_ids[0]
        )
        assert run["follows_business"] is None  # read by the nudge job, after the message
        outcome = await world.run("nudge", run["id"])
        run = await world.run_row(run["id"])
        assert run["follows_business"] is expected
        texts = [
            m["text"]
            for m in await world.rows(
                "SELECT text FROM messages WHERE conversation_id = :c AND direction = 'outbound'"
                " ORDER BY occurred_at",
                c=thread.conversation_id,
            )
        ]
        if expected:
            assert outcome is Outcome.SKIPPED
            assert texts == ["Prices are on maple.example"]
        else:
            assert outcome is Outcome.FIRED
            assert texts == ["Prices are on maple.example", "Follow us for new bakes!"]


async def test_a_comment_without_tap_first_never_nudges(world: World) -> None:
    await tap_first(world, follow_nudge=True, confirm_first=False, cooldown_hours=0)
    author = ref()
    run = await opened(world, author)
    assert run["result"] == "sent"  # no tap first: the private reply is the message
    assert await nudge_jobs() == []
    # Nobody answered, so Instagram allows nothing more.
    assert await world.run("nudge", run["id"]) is Outcome.SKIPPED
    assert len(await outbound(world)) == 1
