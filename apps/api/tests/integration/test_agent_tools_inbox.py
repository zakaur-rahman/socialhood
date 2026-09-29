"""Ask Social Hood's conversation and scheduling tools against real data (TA.4; FR-AGT-02,
FR-AGT-03, FR-AGT-05, FR-AGT-06): search_conversations, get_conversation, find_contact,
get_customer, draft_reply, list_scheduled_messages, list_scheduled_posts and
prepare_scheduled_message, with their caps, caveats, action cards and another workspace's ids."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider
from socialhood.errors import ApiError
from socialhood.models.identity import Role
from socialhood.platforms.deps import PlatformDeps
from socialhood.schemas.agent import AnswerRef, ScheduleMessagePrefill
from socialhood.settings import Settings
from tests.support.agent_tools import Shop, make_shop, tool_platform
from tests.support.ai import make_analysis
from tests.support.automations import make_comment, make_media_item
from tests.support.inbox import Thread, make_scheduled, make_thread
from tests.support.publishing import make_scheduled_post


@pytest.fixture
async def platform(api_settings: Settings) -> AsyncIterator[PlatformDeps]:
    async with tool_platform(api_settings) as deps:
        yield deps


@pytest.fixture
async def shop(engine: AsyncEngine, clean_db: None, platform: PlatformDeps) -> Shop:
    return await make_shop(engine, platform)


@pytest.fixture
async def other(engine: AsyncEngine, shop: Shop, platform: PlatformDeps) -> Shop:
    return await make_shop(engine, platform)


async def thread(shop: Shop, name: str = "Priya Shah", **values: object) -> Thread:
    username = name.lower().replace(" ", ".")
    return await make_thread(
        shop.engine,
        workspace_id=shop.wid,
        account_id=shop.account_id,
        display_name=name,
        username=username,
        **values,
    )


async def refused(shop: Shop, name: str, args: dict[str, object], **kw: object) -> ApiError:
    with pytest.raises(ApiError) as caught:
        await shop.call(name, args, **kw)
    return caught.value


# ---------------------------------------------------------------- conversations


async def test_search_conversations_filters_caps_and_cites(shop: Shop) -> None:
    priya = await thread(shop, "Priya Shah", texts=("Do you ship to Pune?",))
    rahul = await thread(shop, "Rahul K", texts=("Price of the blue kurta?",))
    anita = await thread(shop, "Anita M", texts=("Thanks, got it!",), direction="outbound")

    everyone = await shop.call("search_conversations", {"limit": 2})
    assert (everyone.total, len(everyone.items), everyone.more) == (3, 2, 1)
    assert everyone.items[0].id == anita.conversation_id  # newest activity first
    assert everyone.refs == [
        AnswerRef(kind="conversation", id=i.id, label=i.contact) for i in everyone.items
    ]
    assert everyone.summary == "Found 3 open conversations (2 shown)"

    kurta = await shop.call("search_conversations", {"q": "kurta"})
    assert [(i.id, i.contact) for i in kurta.items] == [(rahul.conversation_id, "Rahul K")]
    assert kurta.items[0].last_message == "Price of the blue kurta?"
    assert kurta.items[0].last_from == "customer"

    waiting = await shop.call("search_conversations", {"view": "needs_reply"})
    assert {i.id for i in waiting.items} == {priya.conversation_id, rahul.conversation_id}

    recent = await shop.call("search_conversations", {"range": "the last 24 hours"})
    assert recent.total == 3
    assert recent.period is not None
    assert "last active" in recent.summary
    old = await shop.call("search_conversations", {"range": "between 1 and 15 Jan 2020"})
    assert (old.total, old.items) == (0, [])

    facebook = await shop.call("search_conversations", {"platform": "facebook"})
    assert facebook.total == 0
    assert facebook.caveats[0].startswith("Facebook isn't connected")

    error = await refused(shop, "search_conversations", {"range": "whenever"})
    assert error.code == "validation_error"


async def test_get_conversation_with_its_summary_analysis_and_window(shop: Shop) -> None:
    t = await thread(shop, texts=("Hi", "Do you ship to Pune?", "And how much is it?"))
    await make_analysis(
        shop.engine,
        workspace_id=shop.wid,
        conversation_id=t.conversation_id,
        message_id=t.message_ids[-1],
        intent="pricing",
        lead_score=72,
    )
    await shop.execute(
        "UPDATE conversations SET summary = 'Asks about shipping to Pune.',"
        " summary_next_step = 'Share the rates', summary_updated_at = now() WHERE id = :id",
        id=t.conversation_id,
    )
    got = await shop.call(
        "get_conversation", {"conversation_id": str(t.conversation_id), "last_n": 2}
    )
    assert [m.text for m in got.messages] == ["Do you ship to Pune?", "And how much is it?"]
    assert [m.sender for m in got.messages] == ["customer", "customer"]
    assert got.more_messages
    assert got.analysis is not None
    assert (got.analysis.intent, got.analysis.lead_score) == ("pricing", 72)
    assert (got.summary_text, got.next_step) == ("Asks about shipping to Pune.", "Share the rates")
    assert got.reply_window.state == "open"
    assert got.reply_window.closes_at is not None
    assert (got.contact, got.account) == ("Priya Shah", "@maple.bakery")
    assert got.refs == [AnswerRef(kind="conversation", id=t.conversation_id, label="Priya Shah")]
    assert got.caveats == []

    bare = await thread(shop, "Rahul K")
    plain = await shop.call("get_conversation", {"conversation_id": str(bare.conversation_id)})
    assert plain.caveats == [
        "This conversation has no AI summary yet.",
        "No message in this conversation has been analysed yet.",
    ]


async def test_find_contact_lists_every_match_for_the_member_to_choose(shop: Shop) -> None:
    shah = await thread(shop, "Priya Shah")
    one = await shop.call("find_contact", {"name_or_handle": "@priya.shah"})
    assert one.total == 1
    [match] = one.matches
    assert (match.conversation_id, match.account, match.platform) == (
        shah.conversation_id,
        "@maple.bakery",
        "instagram",
    )
    assert one.summary == "Found Priya Shah on Instagram (@maple.bakery)"

    await thread(shop, "Priya Nair")
    both = await shop.call("find_contact", {"name_or_handle": "priya"})
    assert both.total == 2
    assert {m.name for m in both.matches} == {"Priya Shah", "Priya Nair"}
    assert both.summary.endswith("ask which one")
    assert {r.kind for r in both.refs} == {"conversation"}

    capped = await shop.call("find_contact", {"name_or_handle": "priya", "limit": 1})
    assert (len(capped.matches), capped.more) == (1, 1)
    nobody = await shop.call("find_contact", {"name_or_handle": "zed"})
    assert (nobody.total, nobody.summary) == (0, "No contact matches “zed”")


async def test_get_customer_with_conversation_and_comments(shop: Shop) -> None:
    t = await thread(shop)
    post = await make_media_item(shop.engine, workspace_id=shop.wid, account_id=shop.account_id)
    comment = await make_comment(
        shop.engine,
        workspace_id=shop.wid,
        account_id=shop.account_id,
        media_item_id=post,
        text="Love the blue one",
        contact_id=t.contact_id,
    )
    got = await shop.call("get_customer", {"contact_id": str(t.contact_id)})
    assert (got.name, got.conversation_id, got.comment_count) == (
        "Priya Shah",
        t.conversation_id,
        1,
    )
    assert [c.id for c in got.recent_comments] == [comment]
    assert [(r.kind, r.id) for r in got.refs] == [
        ("conversation", t.conversation_id),
        ("comment", comment),
    ]
    assert got.caveats == ["None of their messages has been analysed yet."]


# ---------------------------------------------------------------- draft_reply


SUGGESTION = {
    "can_answer": True,
    "reply": "Yes! We ship to Pune in 3-4 days.",
    "missing_info": None,
    "missing_topic": None,
    "confidence": 0.9,
    "used_source_ids": [],
}


async def test_draft_reply_drafts_through_the_suggestion_path_and_sends_nothing(
    shop: Shop, fake_ai: FakeProvider
) -> None:
    t = await thread(shop, texts=("Do you ship to Pune?",))
    fake_ai.respond("suggest", SUGGESTION)
    got = await shop.call(
        "draft_reply",
        {"conversation_id": str(t.conversation_id), "instructions": "Mention 3-4 days"},
    )
    assert got.can_answer
    assert got.text == "Yes! We ship to Pune in 3-4 days."
    card = got.action_card
    assert (card.kind, card.route) == ("schedule_message", f"inbox/{t.conversation_id}?schedule=1")
    assert card.prefill.conversation_id == t.conversation_id
    assert card.prefill.text == got.text
    assert card.prefill.send_at is None
    assert card.prefill.window_closes_at is not None
    [call] = fake_ai.calls_for("suggest")
    assert "Mention 3-4 days" in call.system
    assert "Do you ship to Pune?" in call.contents[0].text
    # Metered like a suggestion (2 credits), against the run; nothing stored or sent.
    usage = await shop.rows("SELECT feature, credits, ref_type, ref_id FROM ai_usage_events")
    assert usage == [
        {
            "feature": "reply_suggestion",
            "credits": 2,
            "ref_type": "agent_run",
            "ref_id": shop.run_id,
        }
    ]
    assert await shop.rows("SELECT id FROM reply_suggestions") == []
    assert await shop.rows("SELECT id FROM messages WHERE direction = 'outbound'") == []


async def test_draft_reply_says_what_the_knowledge_lacks(shop: Shop) -> None:
    t = await thread(shop, texts=("Do you ship to Dubai?",))
    got = await shop.call("draft_reply", {"conversation_id": str(t.conversation_id)})
    assert not got.can_answer
    assert got.text is None
    assert got.missing_info == "the answer to this question"
    assert got.action_card.prefill.text == ""
    assert got.action_card.note is not None
    assert "couldn't draft" in got.action_card.note


async def test_draft_reply_refuses_a_closed_window_before_spending_credits(
    shop: Shop, fake_ai: FakeProvider
) -> None:
    t = await thread(shop, last_inbound_at=datetime.now(UTC) - timedelta(hours=30))
    error = await refused(shop, "draft_reply", {"conversation_id": str(t.conversation_id)})
    assert error.code == "reply_window_closed"
    assert fake_ai.calls_for("suggest") == []
    assert await shop.rows("SELECT id FROM ai_usage_events") == []


# ---------------------------------------------------------------- prepare_scheduled_message

NOW = datetime(2026, 9, 29, 14, 30, tzinfo=UTC)  # Tue 29 Sep, 8:00 PM in Kolkata
PRIYA_WROTE = datetime(2026, 9, 29, 2, 42, tzinfo=UTC)  # 8:12 AM: her window closes 30 Sep 8:12


async def test_a_time_inside_the_window_is_prefilled(shop: Shop) -> None:
    t = await thread(shop, last_inbound_at=PRIYA_WROTE)
    got = await shop.call(
        "prepare_scheduled_message",
        {"contact": "Priya", "text": "Your order ships Monday", "when": "tomorrow 7 AM"},
        now=NOW,
    )
    seven = datetime(2026, 9, 30, 1, 30, tzinfo=UTC)
    assert got.fits
    assert (got.send_at, got.send_at_label) == (seven, "Wed 30 Sep, 7:00 AM")
    assert got.requested.label == "Wed 30 Sep, 7:00 AM"
    assert got.window_closes_label == "Wed 30 Sep, 8:12 AM"
    card = got.action_card
    assert (card.kind, card.route, card.label) == (
        "schedule_message",
        f"inbox/{t.conversation_id}?schedule=1",
        "Schedule this message",
    )
    assert card.prefill == ScheduleMessagePrefill(
        conversation_id=t.conversation_id,
        text="Your order ships Monday",
        send_at=seven,
        window_closes_at=datetime(2026, 9, 30, 2, 36, tzinfo=UTC),  # 8:06 AM
    )
    assert card.note == "Priya Shah's reply window closes Wed 30 Sep, 8:12 AM."
    assert got.refs == [AnswerRef(kind="conversation", id=t.conversation_id, label="Priya Shah")]
    assert await shop.rows("SELECT id FROM scheduled_messages") == []  # nothing scheduled


async def test_a_time_after_the_window_is_not_moved_silently(shop: Shop) -> None:
    """agent-architecture §14: "Priya's window closes tomorrow at 8:12 AM"."""
    t = await thread(shop, last_inbound_at=PRIYA_WROTE)
    got = await shop.call(
        "prepare_scheduled_message",
        {
            "conversation_id": str(t.conversation_id),
            "text": "Your order ships Monday",
            "when": "tomorrow at 10 AM",
        },
        now=NOW,
    )
    assert not got.fits
    assert got.send_at is None
    assert got.requested.label == "Wed 30 Sep, 10:00 AM"
    assert got.latest_send_label == "Wed 30 Sep, 8:06 AM"
    assert got.action_card.prefill.send_at is None
    assert got.action_card.prefill.window_closes_at == datetime(2026, 9, 30, 2, 36, tzinfo=UTC)
    assert got.action_card.note == (
        "Priya Shah's window closes Wed 30 Sep, 8:12 AM, so the latest time is Wed 30 Sep, 8:06 AM."
    )
    assert got.summary == (
        "Wed 30 Sep, 10:00 AM is after Priya Shah's reply window closes (Wed 30 Sep, 8:12 AM)"
    )

    soon = await shop.call(
        "prepare_scheduled_message",
        {"conversation_id": str(t.conversation_id), "text": "Hi", "when": "now"},
        now=NOW,
    )
    assert soon.send_at is None
    assert soon.action_card.note is not None
    assert soon.action_card.note.startswith("Pick a time from Tue 29 Sep, 8:03 PM")


async def test_a_closed_window_and_unclear_contacts_are_refused(shop: Shop) -> None:
    closed = await thread(shop, last_inbound_at=NOW - timedelta(hours=25))
    error = await refused(
        shop,
        "prepare_scheduled_message",
        {"conversation_id": str(closed.conversation_id), "text": "Hi", "when": "in 1 hour"},
        now=NOW,
    )
    assert error.code == "reply_window_closed"
    assert error.detail is not None
    assert "It closed Tue 29 Sep, 7:00 PM." in error.detail

    await thread(shop, "Priya Nair", last_inbound_at=PRIYA_WROTE)
    await thread(shop, "Priya Rao", last_inbound_at=PRIYA_WROTE)
    error = await refused(
        shop,
        "prepare_scheduled_message",
        {"contact": "Priya", "text": "Hi", "when": "in 1 hour"},
        now=NOW,
    )
    assert error.code == "conflict"
    assert error.detail is not None
    assert "Priya Nair" in error.detail
    assert "Priya Rao" in error.detail
    error = await refused(
        shop,
        "prepare_scheduled_message",
        {"contact": "Zed", "text": "Hi", "when": "in 1 hour"},
        now=NOW,
    )
    assert error.code == "not_found"
    error = await refused(
        shop,
        "prepare_scheduled_message",
        {"contact": "Priya Nair", "text": "Hi", "when": "tomorrow"},
        now=NOW,
    )
    assert (error.code, error.detail) == (
        "validation_error",
        "Which time? For example “tomorrow 10 AM”.",
    )


# ---------------------------------------------------------------- lists


async def test_list_scheduled_messages_pending_and_by_range(shop: Shop) -> None:
    t = await thread(shop)
    now = datetime.now(UTC)
    on = {"workspace_id": shop.wid, "conversation_id": t.conversation_id}
    soon = await make_scheduled(shop.engine, send_at=now + timedelta(hours=2), **on)
    later = await make_scheduled(shop.engine, send_at=now + timedelta(hours=50), **on)
    await make_scheduled(shop.engine, send_at=now + timedelta(hours=3), status="canceled", **on)

    pending = await shop.call("list_scheduled_messages", {})
    assert [i.id for i in pending.items] == [soon, later]
    assert (pending.total, pending.more) == (2, 0)
    assert (pending.refs[0].kind, pending.refs[0].parent_id) == (
        "scheduled_message",
        t.conversation_id,
    )
    assert pending.refs[0].label.startswith("To Priya Shah, ")
    assert pending.summary == "2 messages still to be sent"

    day = await shop.call("list_scheduled_messages", {"range": "next 24 hours"})
    assert [i.id for i in day.items] == [soon]
    capped = await shop.call("list_scheduled_messages", {"limit": 1})
    assert (len(capped.items), capped.total, capped.more) == (1, 2, 1)


async def test_list_scheduled_posts_for_admins(shop: Shop) -> None:
    now = datetime.now(UTC)
    post = await make_scheduled_post(
        shop.engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id],
        status="scheduled",
        publish_at=now + timedelta(days=1),
        caption="Diwali collection drop",
    )
    await make_scheduled_post(shop.engine, workspace_id=shop.wid, account_ids=[shop.account_id])
    upcoming = await shop.call("list_scheduled_posts", {})
    assert [i.id for i in upcoming.items] == [post.id]
    [item] = upcoming.items
    assert (item.status, item.caption) == ("scheduled", "Diwali collection drop")
    assert [(t.account, t.status) for t in item.targets] == [("@maple.bakery", "pending")]
    assert upcoming.refs[0].kind == "scheduled_post"
    week = await shop.call("list_scheduled_posts", {"range": "next 7 days"})
    assert [i.id for i in week.items] == [post.id]

    error = await refused(shop, "list_scheduled_posts", {}, role=Role.AGENT)
    assert error.code == "forbidden"
    assert (await shop.call("list_scheduled_messages", {}, role=Role.AGENT)).total == 0


# ---------------------------------------------------------------- tenancy


async def test_another_workspaces_conversations_never_resolve(shop: Shop, other: Shop) -> None:
    theirs = await make_thread(
        other.engine, workspace_id=other.wid, account_id=other.account_id
    )  # Priya Shah too
    mine = await thread(shop)
    for name, args in [
        ("get_conversation", {"conversation_id": str(theirs.conversation_id)}),
        ("get_customer", {"contact_id": str(theirs.contact_id)}),
        ("draft_reply", {"conversation_id": str(theirs.conversation_id)}),
        (
            "prepare_scheduled_message",
            {"conversation_id": str(theirs.conversation_id), "text": "Hi", "when": "in 1 hour"},
        ),
    ]:
        error = await refused(shop, name, args)
        assert error.code == "not_found", name
    found = await shop.call("find_contact", {"name_or_handle": "Priya"})
    assert [m.conversation_id for m in found.matches] == [mine.conversation_id]
    listed = await shop.call("search_conversations", {})
    assert [i.id for i in listed.items] == [mine.conversation_id]
    await make_scheduled(
        other.engine, workspace_id=other.wid, conversation_id=theirs.conversation_id
    )
    assert (await shop.call("list_scheduled_messages", {})).total == 0
