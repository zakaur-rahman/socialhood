"""Scheduling tools (FR-AGT-02, FR-AGT-03, FR-AGT-05, TA.4; agent-architecture.html §5, §19).

R1:
- list_scheduled_messages(range) / list_scheduled_posts(range): read; services/scheduled and
  publishing (P7), in the workspace's time zone. Without a range: what is still to be sent or
  published, soonest first; with one (resolved looking forward: "this week" runs to Sunday): the
  messages or posts timed in it (canceled messages left out; posts of every status, drafts with
  a time included). Scheduled posts are for owners and admins, as on the Schedule page
  (``min_role`` admin).
- prepare_scheduled_message(contact, text, when): draft; resolves the contact, the time
  (agent/timeparse.py) and the reply window (services/scheduled.send_window, the popover's own
  rules), and returns a schedule_message action card: the conversation's schedule popover limited
  to the window. A time outside the window is not moved silently: the card has no time and its
  note gives the latest possible one ("Priya's window closes tomorrow at 8:12 AM"). A closed
  window (no cold DMs, §19) is refused with the reason.

R2: schedule_message / cancel_scheduled_message (low, schedule_messages) through
services/scheduled; schedule_post / reschedule_post / cancel_scheduled_post (high,
schedule_posts) through publishing, which checks the publishing limit and formats.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from socialhood.agent.registry import DraftResult, ToolContext, ToolResult
from socialhood.agent.tools.common import (
    Period,
    capped,
    clip,
    contact_name,
    find_account,
    handle,
    instant,
    limit_field,
    more_words,
    period,
    ref,
    tool,
    when,
)
from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.agent import RiskTier
from socialhood.models.identity import Role
from socialhood.models.inbox import Contact, Conversation, ScheduledMessage
from socialhood.repositories import inbox, social_accounts
from socialhood.repositories import scheduled as scheduled_repo
from socialhood.repositories import scheduled_posts as posts_repo
from socialhood.schemas.agent import ScheduleMessageAction, ScheduleMessagePrefill
from socialhood.services import conversations
from socialhood.services.reply_window import STANDARD_WINDOW
from socialhood.services.scheduled import WINDOW_CLOSED_COPY, send_window
from socialhood.services.scheduled_posts import views as post_views

MAX_ROWS = 500  # a list reads at most this many rows to count "n more"


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- list_scheduled_messages


class ListScheduledMessagesInput(_Input):
    range: str | None = Field(
        default=None,
        max_length=80,
        description="When they send, e.g. “tomorrow”, “this week”; omitted: every message "
        "still to be sent.",
    )
    limit: int = limit_field()


class ScheduledMessageItem(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    contact: str
    platform: str
    text: str | None = None
    send_at: datetime
    send_at_label: str | None = None
    status: str  # scheduled, sending, sent, failed, expired
    error: str | None = None


class ScheduledMessagesResult(ToolResult):
    period: Period | None = None
    items: list[ScheduledMessageItem]
    total: int
    more: int


def _message_item(
    ctx: ToolContext, s: ScheduledMessage, contact: Contact, platform: str
) -> ScheduledMessageItem:
    return ScheduledMessageItem(
        id=s.id,
        conversation_id=s.conversation_id,
        contact=contact_name(contact),
        platform=platform,
        text=clip(s.text, 200),
        send_at=s.send_at,
        send_at_label=when(ctx, s.send_at),
        status=s.status,
        error=s.error_message,
    )


@tool(
    name="list_scheduled_messages",
    label="Checking your scheduled messages",
    description=(
        "Scheduled DMs: without a period, every message still to be sent (soonest first); "
        "with one, the messages timed in it, with their status."
    ),
    input_model=ListScheduledMessagesInput,
    result_model=ScheduledMessagesResult,
)
async def list_scheduled_messages(
    ctx: ToolContext, args: ListScheduledMessagesInput
) -> ScheduledMessagesResult:
    span = period(ctx, args.range, default=None, upcoming=True)
    if span is None:
        pending = await scheduled_repo.list_pending(ctx.session, limit=args.limit)
        total = await scheduled_repo.count_pending(ctx.session)
        items = [_message_item(ctx, r.scheduled, r.contact, r.platform) for r in pending]
        summary = f"{more_words(total, 0, 'message')} still to be sent"
    else:
        rows = await posts_repo.scheduled_messages(
            ctx.session, start=span.start, end=span.end, account_ids=None, limit=MAX_ROWS
        )
        shown, _ = capped(rows, args.limit)
        total = len(rows)
        items = [_message_item(ctx, r.scheduled, r.contact, r.platform) for r in shown]
        summary = f"{more_words(total, 0, 'scheduled message')}, {span.label}"
    return ScheduledMessagesResult(
        summary=clip(summary[0].upper() + summary[1:], 300) or "Checked scheduled messages",
        period=Period.of(span) if span else None,
        items=items,
        total=total,
        more=max(total - len(items), 0),
        refs=[ref("scheduled_message", i.id, f"To {i.contact}, {i.send_at_label}") for i in items],
    )


# ---------------------------------------------------------------- list_scheduled_posts


class ListScheduledPostsInput(_Input):
    range: str | None = Field(
        default=None,
        max_length=80,
        description="When they publish, e.g. “next week”; omitted: every post still to be "
        "published.",
    )
    account: str | None = Field(default=None, max_length=100)
    limit: int = limit_field()


class Target(BaseModel):
    account: str
    status: str
    error: str | None = None


class ScheduledPostItem(BaseModel):
    id: uuid.UUID
    status: str  # draft, scheduled, publishing, published, partially_published, failed, canceled
    format: str | None = None
    caption: str | None = None
    publish_at: datetime | None = None
    publish_at_label: str | None = None
    published_at: datetime | None = None
    targets: list[Target]


class ScheduledPostsResult(ToolResult):
    period: Period | None = None
    items: list[ScheduledPostItem]
    total: int
    more: int


@tool(
    name="list_scheduled_posts",
    label="Checking your scheduled posts",
    description=(
        "Scheduled posts: without a period, every post still to be published (soonest first); "
        "with one, the posts timed in it, drafts with a time included, with each account's "
        "status."
    ),
    input_model=ListScheduledPostsInput,
    result_model=ScheduledPostsResult,
    min_role=Role.ADMIN,
)
async def list_scheduled_posts(
    ctx: ToolContext, args: ListScheduledPostsInput
) -> ScheduledPostsResult:
    acct = await find_account(ctx, args.account)
    account_ids = [acct.id] if acct else None
    span = period(ctx, args.range, default=None, upcoming=True)
    if span is None:
        rows = await posts_repo.list_view(
            ctx.session, view="scheduled", account_ids=account_ids, after=None, limit=MAX_ROWS
        )
    else:
        rows = await posts_repo.in_range(
            ctx.session, start=span.start, end=span.end, account_ids=account_ids, limit=MAX_ROWS
        )
    shown, more = capped(rows, args.limit)
    accounts = {a.id: a for a in await social_accounts.list_all(ctx.session)}
    items = []
    for post in await post_views.summaries(ctx.session, shown):
        items.append(
            ScheduledPostItem(
                id=post.id,
                status=post.status,
                format=post.format,
                caption=clip(post.caption, 160),
                publish_at=post.publish_at,
                publish_at_label=when(ctx, post.publish_at),
                published_at=post.published_at,
                targets=[
                    Target(
                        account=(
                            handle(accounts[t.social_account_id])
                            if t.social_account_id in accounts
                            else "a removed account"
                        ),
                        status=t.status,
                        error=t.error.message if t.error else None,
                    )
                    for t in post.targets
                ],
            )
        )
    noun = "post" if len(rows) == 1 else "posts"
    summary = (
        f"{len(rows)} {noun} still to be published"
        if span is None
        else f"{len(rows)} {noun} timed {span.label}"
    )
    return ScheduledPostsResult(
        summary=clip(summary, 300) or "Checked scheduled posts",
        period=Period.of(span) if span else None,
        items=items,
        total=len(rows),
        more=more,
        refs=[
            ref("scheduled_post", i.id, clip(i.caption, 40) or f"Post {i.publish_at_label}")
            for i in items
        ],
    )


# ---------------------------------------------------------------- prepare_scheduled_message


class PrepareScheduledMessageInput(_Input):
    conversation_id: uuid.UUID | None = Field(
        default=None, description="The conversation, when known (from find_contact)."
    )
    contact: str | None = Field(
        default=None,
        max_length=100,
        description="Otherwise the customer's name or @username; several matches are refused "
        "with the list so the member can choose.",
    )
    text: str = Field(min_length=1, max_length=2000, description="The message, as it will send.")
    when: str = Field(
        min_length=1,
        max_length=80,
        description="When to send, as the member said it: “tomorrow 10 AM”, “in 2 hours”.",
    )


class RequestedTime(BaseModel):
    phrase: str
    at: datetime
    label: str
    rule: str | None = None  # the rule applied to an ambiguous phrase; the answer states it


class PrepareScheduledMessageResult(DraftResult):
    conversation_id: uuid.UUID
    contact: str
    platform: str
    requested: RequestedTime
    fits: bool  # the requested time is inside the reply window
    send_at: datetime | None = None  # the prefilled time: the requested one when it fits
    send_at_label: str | None = None
    window_closes_at: datetime  # when the reply window itself closes
    window_closes_label: str
    latest_send_at: datetime  # the latest time the popover allows (5 minutes before)
    latest_send_label: str


async def _conversation(ctx: ToolContext, args: PrepareScheduledMessageInput) -> Conversation:
    if args.conversation_id is not None:
        return await conversations.get_or_404(ctx.session, args.conversation_id)
    term = (args.contact or "").strip()
    if not term:
        raise ApiError(
            "validation_error",
            "Say who the message is for.",
            errors=[FieldError("contact", "Name the customer or give the conversation.")],
        )
    rows, _ = await conversations.find_contacts(ctx.session, term, limit=6)
    with_conv = [(c, conv) for c, conv in rows if conv is not None]
    if not with_conv:
        if rows:
            raise ApiError(
                "conflict",
                f"{contact_name(rows[0][0])} hasn't messaged you, so there's no conversation to "
                "message: Instagram and WhatsApp don't allow the first message to come from you.",
            )
        raise ApiError("not_found", f"No customer matches “{clip(term, 40)}”.")
    if len(with_conv) > 1:
        names = "; ".join(
            f"{contact_name(c)}"
            + (f" (@{c.username})" if c.username and c.display_name else "")
            + f", {conv.platform}, conversation {conv.id}"
            for c, conv in with_conv
        )
        raise ApiError(
            "conflict", f"Several customers match “{clip(term, 40)}”: {names}. Which one?"
        )
    return with_conv[0][1]


@tool(
    name="prepare_scheduled_message",
    label="Preparing the scheduled message",
    description=(
        "Prepare a DM to send later: finds the customer's conversation, resolves the time and "
        "checks the reply window (messages only within 24 hours of the customer's last "
        "message). Returns a card that opens the conversation's schedule popover filled in; "
        "sends and schedules nothing. A time outside the window leaves the time empty and says "
        "the latest possible one."
    ),
    input_model=PrepareScheduledMessageInput,
    result_model=PrepareScheduledMessageResult,
    tier=RiskTier.DRAFT,
)
async def prepare_scheduled_message(
    ctx: ToolContext, args: PrepareScheduledMessageInput
) -> PrepareScheduledMessageResult:
    conv = await _conversation(ctx, args)
    name = contact_name(await inbox.get_contact(ctx.session, conv.contact_id))
    requested = instant(ctx, args.when)
    allowed = send_window(
        conv, human_agent_enabled=ctx.platform.settings.ig_human_agent_enabled, now=ctx.now
    )
    if allowed is None:
        closed = (
            f" It closed {when(ctx, conv.last_inbound_at + STANDARD_WINDOW)}."
            if conv.last_inbound_at is not None
            else ""
        )
        raise ApiError(
            "reply_window_closed",
            f"{name}'s reply window is closed, so nothing can be scheduled.{closed} "
            f"{WINDOW_CLOSED_COPY.get(conv.platform, '')}".strip(),
        )
    latest_label = when(ctx, allowed.latest) or ""
    closes_label = when(ctx, allowed.closes_at) or ""
    fits = allowed.earliest <= requested.at <= allowed.latest
    if fits:
        send_at = requested.at
        note = f"{name}'s reply window closes {closes_label}."
        summary = f"Prepared a message to {name} for {requested.label}"
    elif requested.at > allowed.latest:
        send_at = None
        note = f"{name}'s window closes {closes_label}, so the latest time is {latest_label}."
        summary = f"{requested.label} is after {name}'s reply window closes ({closes_label})"
    else:
        send_at = None
        note = f"Pick a time from {when(ctx, allowed.earliest)} to {latest_label}."
        summary = f"{requested.label} is too soon or has passed; the message needs a later time"
    caveats = []
    limit = entitlement(await current_plan(ctx.session), "pending_scheduled_messages")
    if limit is not None and await scheduled_repo.count_pending(ctx.session) >= limit:
        caveats.append(
            f"Your plan's {limit} scheduled messages are all in use: one has to send or be "
            "canceled before this one can be scheduled."
        )
    return PrepareScheduledMessageResult(
        summary=clip(summary, 300) or "Prepared a scheduled message",
        conversation_id=conv.id,
        contact=name,
        platform=conv.platform,
        requested=RequestedTime(
            phrase=args.when, at=requested.at, label=requested.label, rule=requested.rule
        ),
        fits=fits,
        send_at=send_at,
        send_at_label=when(ctx, send_at),
        window_closes_at=allowed.closes_at,
        window_closes_label=closes_label,
        latest_send_at=allowed.latest,
        latest_send_label=latest_label,
        refs=[ref("conversation", conv.id, name)],
        caveats=caveats,
        action_card=ScheduleMessageAction(
            kind="schedule_message",
            label="Schedule this message",
            route=f"inbox/{conv.id}?schedule=1",
            note=clip(note, 200),
            prefill=ScheduleMessagePrefill(
                conversation_id=conv.id,
                text=args.text,
                send_at=send_at,
                window_closes_at=allowed.latest,
            ),
        ),
    )
