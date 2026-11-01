"""Automations writes, part two (C-169): create_automation and update_automation.

They build the dashboard's simple shape: a comment or DM keyword that sends a DM (text, and
optionally one link button) and, for comments, optionally a public reply. They go through the
editor's own services: ``definitions.create`` then ``definitions.update`` (the autosave PUT), and
``definitions.activate`` to turn one on, so the validation, the plan's ``active_automations``
limit and the overlap check are the app's, never a second set of rules.

- **Confirmation.** Nothing changes until the call is repeated with ``confirmed: true`` and the
  preview's ``confirmation_token`` (mcp/confirmations.py), which the server checks; it also binds
  the post “latest” resolved to, so a post synced after the preview needs a new one. The first
  call runs the same services inside a savepoint and rolls it back, so the preview's errors are
  the real ones and it shows what the app would store: the resolved account and post, the tap
  first opening the app adds to new comment automations, overlaps with live automations, what
  would stop it going live, and the plan's active automations used and allowed. A preview is
  never stored for replay.
- **Off by default.** ``turn_on`` activates it through the app's activation, the dashboard's
  path. A full plan is a refusal that says to pause one or upgrade, and nothing is created.
  Turning on is the member's decision: the AI app asks, the member confirms, and only then does
  the automation (not the AI) message the people who match.
- **The team is told** (``ai_automation_change``, owners and admins), and the audit log gets the
  line ("Asha via Claude: automation.created").
- **update_automation** edits only that shape: a flow, an AI reply, an image or another trigger is
  refused with a link to the editor. It never turns one on or off (pause_automation and
  resume_automation do), and a live automation must stay complete, as in the editor.
- ``post`` takes the shared resolver (mcp/tools/common.resolve_post): a post id or “latest”, plus
  “next” (the next post published) and “any”.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSessionTransaction

from socialhood.agent.tools.common import find_account, handle
from socialhood.billing.entitlements import quota_error
from socialhood.billing.plans import entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.mcp import confirmations
from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import Access, ConfirmedInput, WriteOutput, registry, tool
from socialhood.mcp.tools.common import moment, resolve_post
from socialhood.mcp.tools.posts import POST_TYPES, caption_snippet
from socialhood.models.identity import Role, User
from socialhood.models.media import MediaItem, MediaType
from socialhood.models.notifications import NotificationType, Severity
from socialhood.realtime import events
from socialhood.repositories import automations as automations_repo
from socialhood.repositories import comments as comments_repo
from socialhood.repositories import social_accounts
from socialhood.schemas.automations import Automation as AutomationOut
from socialhood.schemas.automations import (
    AutomationCreate,
    AutomationDefinition,
    LinkButtonIn,
)
from socialhood.services import notifications
from socialhood.services.automations import definitions, flow_store, queries
from socialhood.services.automations.validation import (
    BUTTON_TITLE_CHARS,
    KEYWORD_CHARS,
    PUBLIC_REPLY_CHARS,
)

Trigger = Literal["comment_keyword", "dm_keyword"]
Match = Literal["word", "exact", "contains"]
SIMPLE_TRIGGERS: tuple[str, ...] = ("comment_keyword", "dm_keyword")
ANY, NEXT = "any", "next"
ACTIVE = "active"  # an automation that is on (the projection's status)
MAX_KEYWORDS = 20
DM_TEXT_CHARS = 2000  # a backstop: the app's checks give the real limit (1,000 bytes on Instagram)

POST = (
    "For a comment trigger: a post id from list_instagram_posts, “latest” for the newest post, "
    "“next” for the next post published, or “any” for every post (the default)."
)
MATCH = (
    "word (the default): the keyword as a whole word, so “price” matches “What's the price?” "
    "but not “priceless”. exact: the whole message is the keyword. contains: anywhere, even "
    "inside a word."
)
TRIGGER_WORDS = {"comment_keyword": "a comment with a keyword", "dm_keyword": "a DM with a keyword"}
NOT_SIMPLE = (
    "This automation {why}, which AI apps can't edit safely. Edit it in Amplychat's automation "
    "editor."
)
FULL = (
    "Your plan allows {limit} automations on at once and {used} are on. Pause one "
    "(pause_automation) or upgrade, or create this one turned off."
)
WHICH_ACCOUNT = "Several Instagram accounts could run this: {names}. Which one?"
NO_POST_ON_DM = "A DM keyword answers DMs, not a post. Leave post out."
NO_REPLY_ON_DM = "A public reply answers a comment. Leave public_reply out for DMs."

Keyword = Annotated[str, Field(min_length=1, max_length=KEYWORD_CHARS)]


class LinkButton(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=BUTTON_TITLE_CHARS, description="The label.")
    url: str = Field(min_length=1, max_length=2000, description="An https link.")


class CreateAutomationInput(ConfirmedInput):
    name: str = Field(min_length=1, max_length=80)
    account: str | None = Field(
        default=None,
        max_length=100,
        description="A connected account's id or @handle. Omitted: the post's account, else the "
        "only Instagram account.",
    )
    trigger: Trigger = Field(
        description="comment_keyword: a comment with a keyword; dm_keyword: a DM with one."
    )
    keywords: list[Keyword] = Field(
        min_length=1, max_length=MAX_KEYWORDS, description="1 to 20 keywords, e.g. “price”."
    )
    match: Match = Field(default="word", description=MATCH)
    post: str | None = Field(default=None, max_length=60, description=POST)
    dm_text: str = Field(
        min_length=1,
        max_length=DM_TEXT_CHARS,
        description="The DM to send. {first_name} puts in their first name.",
    )
    link_button: LinkButton | None = Field(
        default=None, description="Optional: one link button under the DM."
    )
    public_reply: str | None = Field(
        default=None,
        min_length=1,
        max_length=PUBLIC_REPLY_CHARS,
        description="Comment triggers: a public reply to the comment as well.",
    )
    turn_on: bool = Field(
        default=False,
        description="true: switch it on once created, so it starts messaging people who match. "
        "false (the default): it is saved off, as a draft.",
    )


class UpdateAutomationInput(ConfirmedInput):
    automation_id: uuid.UUID = Field(description="From list_automations.")
    name: str | None = Field(default=None, min_length=1, max_length=80)
    keywords: list[Keyword] | None = Field(
        default=None, min_length=1, max_length=MAX_KEYWORDS, description="Replaces the keywords."
    )
    match: Match | None = Field(default=None, description=MATCH)
    post: str | None = Field(default=None, max_length=60, description=POST)
    dm_text: str | None = Field(default=None, min_length=1, max_length=DM_TEXT_CHARS)
    link_button: LinkButton | None = Field(
        default=None, description="Replaces the link buttons with this one."
    )
    remove_link_button: bool = Field(default=False, description="Remove the link buttons.")
    public_reply: str | None = Field(
        default=None,
        max_length=PUBLIC_REPLY_CHARS,
        description="Comment triggers: replaces the public replies; an empty string removes them.",
    )


class PostOut(BaseModel):
    post_id: uuid.UUID
    type: str  # post, reel, carousel
    caption_start: str | None = None  # the workspace's own caption
    published_at: str | None = None  # local and UTC
    permalink: str | None = None


class OverlapOut(BaseModel):
    keyword: str
    automation_id: uuid.UUID
    automation_name: str
    this_runs_first: bool


class ActiveLimitOut(BaseModel):
    on_now: int  # automations on now, besides this one
    allowed: int | None = None  # None: no limit on this plan


class AutomationWriteResult(WriteOutput):
    automation_id: uuid.UUID | None = None  # None in a preview of one not yet created
    name: str
    status: str  # draft, active, paused (what it would be, in a preview)
    account: str | None = None
    trigger: str | None = None
    keywords: list[str]
    match: str
    posts: str  # "any post", "one post", "the next post published", "DMs, not posts"
    post: PostOut | None = None
    dm_text: str | None = None
    link_buttons: list[LinkButton]
    public_replies: list[str]
    # Comment triggers: the app first sends this opening with a button, and the DM after a tap
    # (tap first, on for new comment automations as in the editor).
    tap_first_opening: str | None = None
    tap_first_button: str | None = None
    overlaps: list[OverlapOut]  # the same keyword in another live automation of the account
    needs_before_on: list[str]  # what would stop it going live, in the app's words
    active_automations: ActiveLimitOut
    next_step: str
    dashboard_url: str | None = None


# ---------------------------------------------------------------- shared


@dataclass
class _Scope:
    post_scope: Literal["all", "selected", "next_post"]
    item: MediaItem | None = None


def _bad(field: str, message: str) -> ApiError:
    return ApiError("validation_error", message, errors=[FieldError(field, message)])


def _keywords(typed: list[str]) -> list[str]:
    clean = [" ".join(k.split()) for k in typed]
    for i, keyword in enumerate(clean):
        if not keyword:
            raise _bad(f"keywords.{i}", "A keyword can't be empty.")
        if len(keyword) > KEYWORD_CHARS:
            raise _bad(f"keywords.{i}", "Keep keywords to 100 characters.")
    return clean


async def _post_scope(
    call: ToolCall, post: str | None, *, account_id: uuid.UUID | None, account: str | None
) -> _Scope:
    text = (post or ANY).strip().casefold()
    if text == ANY:
        return _Scope("all")
    if text == NEXT:
        return _Scope("next_post")
    item = await resolve_post(call, post or "", account=account)
    if item.media_type == MediaType.STORY:
        raise _bad("post", "That's a Story, which takes no comments. Pick a post or a Reel.")
    if account_id is not None and item.social_account_id != account_id:
        raise _bad("post", "That post is on another account. Pick a post of this account.")
    return _Scope("selected", item)


async def _preview_end(call: ToolCall, savepoint: AsyncSessionTransaction) -> None:
    """End a preview: everything the call wrote is rolled back and its events dropped."""
    await savepoint.rollback()
    events.discard(call.session)


def _view(call: ToolCall) -> queries.View:
    return queries.View(
        disclosure=call.workspace.automation_disclosure,
        timezone=call.timezone.key,
        now=call.now,
    )


async def _activate(call: ToolCall, automation_id: uuid.UUID) -> None:
    """The app's activation; a full plan is the same 402, in words that say what to do."""
    try:
        await definitions.activate(
            call.session,
            automation_id,
            plan=call.plan,
            disclosure=call.workspace.automation_disclosure,
            now=call.now,
        )
    except ApiError as error:
        limit = error.plan_limit
        if error.code != "quota_exceeded" or limit is None:
            raise
        if limit.entitlement != "active_automations":
            raise
        used = await automations_repo.count_active(call.session, excluding=automation_id)
        raise quota_error(
            "active_automations", limit.limit, FULL.format(limit=limit.limit, used=used)
        ) from error


def _post_out(call: ToolCall, item: MediaItem) -> PostOut:
    return PostOut(
        post_id=item.id,
        type=POST_TYPES.get(item.media_type, "post"),
        caption_start=caption_snippet(item.caption),
        published_at=moment(call, item.posted_at),
        permalink=item.permalink,
    )


def _posts_words(out: AutomationOut) -> str:
    if out.trigger != "comment_keyword":
        return "DMs, not posts"
    if out.post_scope == "all":
        return "any post"
    if out.post_scope == "next_post":
        return "the next post published"
    return "one post" if len(out.posts) == 1 else f"{len(out.posts)} posts"


async def _result(
    call: ToolCall,
    out: AutomationOut,
    *,
    preview: bool,
    summary: str,
    next_step: str,
    stored: bool = True,
    token: str | None = None,
) -> AutomationWriteResult:
    """The automation as the app stores it (``queries.one``), with what activation would still
    find (``flow_store.problems``, the editor's checklist) and the plan's limit."""
    problems = []
    if out.status != ACTIVE:
        automation = await definitions.get_or_404(call.session, out.id)
        found = await flow_store.problems(
            call.session,
            [automation],
            disclosure=call.workspace.automation_disclosure,
            now=call.now,
        )
        problems = found[automation.id]
    account = (
        await social_accounts.get(call.session, out.social_account_id)
        if out.social_account_id
        else None
    )
    post = None
    media = [p.media_item_id for p in out.posts if p.media_item_id]
    if out.post_scope == "selected" and len(media) == 1:
        item = await comments_repo.get_media_item(call.session, media[0])
        post = _post_out(call, item) if item is not None else None
    tap_first = out.trigger == "comment_keyword" and out.confirm_first
    return AutomationWriteResult(
        summary=summary[:400],
        preview=preview,
        confirmation_token=token,
        automation_id=out.id if stored else None,
        name=out.name,
        status=out.status,
        account=handle(account) if account else None,
        trigger=out.trigger,
        keywords=out.keywords,
        match=out.match_mode,
        posts=_posts_words(out),
        post=post,
        dm_text=out.message_text,
        link_buttons=[LinkButton(title=b.title, url=b.url) for b in out.message_buttons],
        public_replies=out.public_reply_texts,
        tap_first_opening=out.opening_text if tap_first else None,
        tap_first_button=out.opening_button if tap_first else None,
        overlaps=[
            OverlapOut(
                keyword=o.keyword,
                automation_id=o.automation_id,
                automation_name=o.automation_name,
                this_runs_first=o.this_runs_first,
            )
            for o in out.overlaps
        ],
        needs_before_on=list(dict.fromkeys(e.message for e in problems)),
        active_automations=ActiveLimitOut(
            on_now=await automations_repo.count_active(call.session, excluding=out.id),
            allowed=entitlement(call.plan, "active_automations"),
        ),
        next_step=next_step,
        dashboard_url=call.dashboard_url(f"automations/{out.id}") if stored else None,
    )


async def _notify(call: ToolCall, automation: AutomationOut, did: str) -> None:
    """Tell the owners and admins that an AI app created or changed an automation, who asked,
    and where to review or pause it."""
    user = await call.session.get(User, call.principal.user_id)
    who = (user.name or user.email) if user is not None else "A member"
    app = call.client_name or "An AI app"
    live = automation.status == ACTIVE
    title = f"{app} {did} the automation “{automation.name}”" + (", which is on" if live else "")
    await notifications.notify_admins(
        call.session,
        type=NotificationType.AI_AUTOMATION_CHANGE.value,
        severity=Severity.INFO.value,
        title=title[:200],
        body=f"{who} asked {app} to do this. Open it to review it"
        + (" or pause it." if live else " and turn it on when it's ready."),
        link=f"/automations/{automation.id}",
        dedupe_key=f"mcp-automation:{automation.id}:{did}:{call.call_id}",
    )


def _confirm_step(then: str) -> str:
    return (
        "Nothing was changed. Show the member this. After they agree, call again with the same "
        f"arguments, confirmed: true and this confirmation_token to {then}."
    )


def _buttons(button: LinkButton | None) -> list[LinkButtonIn]:
    return [LinkButtonIn(title=button.title, url=button.url)] if button else []


def body_of(out: AutomationOut) -> AutomationDefinition:
    """The editor's whole definition of the automation as stored (its PUT replaces it all, so
    a change of one field sends every other one as it is)."""
    return AutomationDefinition(
        name=out.name,
        social_account_id=out.social_account_id,
        trigger=out.trigger,
        keywords=out.keywords,
        match_mode=out.match_mode,
        action=out.action,
        message_text=out.message_text,
        message_buttons=[LinkButtonIn(title=b.title, url=b.url) for b in out.message_buttons],
        message_media_asset_id=out.message_media_asset_id,
        ai_instructions=out.ai_instructions,
        public_reply_texts=out.public_reply_texts,
        post_scope=out.post_scope,
        media_item_ids=[p.media_item_id for p in out.posts if p.media_item_id],
        scheduled_post_ids=[p.scheduled_post_id for p in out.posts if p.scheduled_post_id],
        story_ids=out.story_ids,
        story_heart=out.story_heart,
        ad_ids=out.ad_ids,
        comment_surface=out.comment_surface,
        hours_condition=out.hours_condition,
        cooldown_hours=out.cooldown_hours,
        starts_at=out.starts_at,
        ends_at=out.ends_at,
        surge_order=out.surge_order,
        confirm_first=out.confirm_first,
        opening_text=out.opening_text,
        opening_button=out.opening_button,
        follow_nudge=out.follow_nudge,
        follow_nudge_text=out.follow_nudge_text,
        track_links=out.track_links,
    )


def _what(out: AutomationOut) -> str:
    words = ", ".join(f"“{k}”" for k in out.keywords[:5])
    return f"on {TRIGGER_WORDS.get(out.trigger or '', 'a keyword')} ({words})"


# ---------------------------------------------------------------- create_automation


@tool(
    registry,
    name="create_automation",
    title="Create an automation",
    description=(
        "Create a keyword automation: when someone comments a keyword on a post (one post, the "
        "latest, the next one, or any) or sends it in a DM, Amplychat sends them a DM, with an "
        "optional link button and, for comments, a public reply. It is checked as in the "
        "automation editor. The first call is a preview: the account and post, the messages, "
        "overlaps with live automations, what it still needs and the plan's limit. Show the "
        "member the preview and call again only after they agree, with confirmed true and its "
        "confirmation_token. It is created off unless turn_on is true; once on, it messages the "
        "people who match. The team is notified. Part of Creator and Business."
    ),
    input_model=CreateAutomationInput,
    output_model=AutomationWriteResult,
    scope="automations:create",
    access=Access.WRITE,
    min_role=Role.ADMIN,
    open_world=True,  # once on, it messages real customers
    dedupe_window_s=confirmations.TTL_S,  # as long as a confirmation token lasts
)
async def create_automation(call: ToolCall, args: CreateAutomationInput) -> AutomationWriteResult:
    comment = args.trigger == "comment_keyword"
    if not comment and args.post is not None:
        raise _bad("post", NO_POST_ON_DM)
    if not comment and args.public_reply is not None:
        raise _bad("public_reply", NO_REPLY_ON_DM)
    keywords = _keywords(args.keywords)
    acct = await find_account(call.agent_context(), args.account)
    scope = (
        await _post_scope(
            call, args.post, account_id=acct.id if acct else None, account=args.account
        )
        if comment
        else _Scope("all")
    )
    account_id = acct.id if acct else (scope.item.social_account_id if scope.item else None)
    if account_id is None:  # the service only picks an account when there is exactly one
        live = await automations_repo.live_instagram_accounts(call.session)
        if len(live) > 1:
            names = ", ".join(handle(a) for a in live)
            raise ApiError("conflict", WHICH_ACCOUNT.format(names=names))
    resolved = {"account": account_id, "post": scope.item.id if scope.item else None}
    if args.confirmed:
        confirmations.require(call, args, args.confirmation_token, **resolved)
    savepoint = None if args.confirmed else await call.session.begin_nested()
    automation = await definitions.create(
        call.session,
        AutomationCreate(name=args.name, social_account_id=account_id),
        user_id=call.principal.user_id,
        now=call.now,
    )
    await definitions.update(
        call.session,
        automation.id,
        AutomationDefinition(
            name=args.name,
            social_account_id=automation.social_account_id,
            trigger=args.trigger,
            keywords=keywords,
            match_mode=args.match,
            action="send_message",
            message_text=args.dm_text,
            message_buttons=_buttons(args.link_button),
            public_reply_texts=[args.public_reply] if comment and args.public_reply else [],
            post_scope=scope.post_scope,
            media_item_ids=[scope.item.id] if scope.item else [],
            # The new draft's defaults, as the editor starts it.
            cooldown_hours=automation.cooldown_hours,
            surge_order=automation.surge_order,
            comment_surface=automation.comment_surface,
            confirm_first=automation.confirm_first,
            opening_text=automation.opening_text,
            opening_button=automation.opening_button,
            follow_nudge=automation.follow_nudge,
            follow_nudge_text=automation.follow_nudge_text,
        ),
        disclosure=call.workspace.automation_disclosure,
        now=call.now,
    )
    if args.turn_on:
        await _activate(call, automation.id)
    out = await queries.one(call.session, automation.id, _view(call))
    on = "on" if args.turn_on else "off"
    if savepoint is not None:
        result = await _result(
            call,
            out,
            preview=True,
            summary=f"Preview: “{out.name}” would be created {_what(out)} and saved {on}. "
            "Nothing is created yet",
            next_step=_confirm_step("create it"),
            stored=False,
            token=confirmations.issue(call, args, **resolved),
        )
        await _preview_end(call, savepoint)
        return result
    call.note("automation.created", "automation", out.id, trigger=out.trigger, status=out.status)
    if args.turn_on:
        call.note("automation.activated", "automation", out.id)
    await _notify(call, out, "created")
    return await _result(
        call,
        out,
        preview=False,
        summary=f"Created “{out.name}” {_what(out)}. It is {on}"
        + ("" if args.turn_on else ", saved as a draft"),
        next_step="It now messages the people who match. Pause it with pause_automation."
        if args.turn_on
        else "It is off. Turn it on in Amplychat when it's ready.",
    )


# ---------------------------------------------------------------- update_automation


def _not_simple(out: AutomationOut) -> str | None:
    """Why update_automation can't edit this one safely, or None."""
    if out.flow_source == "flow":
        return "is a multi-step flow"
    if out.comment_surface != "posts":
        return "answers Live comments"
    if out.trigger not in SIMPLE_TRIGGERS:
        return "starts on something other than a comment or DM keyword"
    if out.action != "send_message":
        return "replies with AI rather than a set message"
    if out.message_media_asset_id is not None:
        return "sends an image"
    return None


@tool(
    registry,
    name="update_automation",
    title="Change an automation",
    description=(
        "Change a keyword automation that sends one DM (the kind create_automation makes): its "
        "name, keywords, matching, post, DM text, link button or public reply. Only the fields "
        "sent change. A multi-step flow, an AI reply or another trigger is refused with a link "
        "to the editor. It doesn't turn the automation on or off (pause_automation and "
        "resume_automation do), and a live automation has to stay complete. Previewed first: "
        "show the member the preview and call again only after they agree, with confirmed true "
        "and its confirmation_token. The team is notified. Part of Creator and Business."
    ),
    input_model=UpdateAutomationInput,
    output_model=AutomationWriteResult,
    scope="automations:create",
    access=Access.WRITE,
    min_role=Role.ADMIN,
    destructive=True,  # it overwrites what was there
    open_world=True,  # a live automation messages customers with the new text
)
async def update_automation(call: ToolCall, args: UpdateAutomationInput) -> AutomationWriteResult:
    await definitions.get_or_404(call.session, args.automation_id, for_update=True)
    current = await queries.one(call.session, args.automation_id, _view(call))
    url = call.dashboard_url(f"automations/{current.id}")
    if (why := _not_simple(current)) is not None:
        raise ApiError("conflict", NOT_SIMPLE.format(why=why) + (f" {url}" if url else ""))
    comment = current.trigger == "comment_keyword"
    if not comment and args.post is not None:
        raise _bad("post", NO_POST_ON_DM)
    if not comment and args.public_reply:
        raise _bad("public_reply", NO_REPLY_ON_DM)
    if args.link_button is not None and args.remove_link_button:
        raise _bad("remove_link_button", "Send link_button or remove_link_button, not both.")
    changes: dict[str, object] = {}
    resolved: dict[str, object] = {}
    if args.name is not None:
        changes["name"] = args.name
    if args.keywords is not None:
        changes["keywords"] = _keywords(args.keywords)
    if args.match is not None:
        changes["match_mode"] = args.match
    if args.dm_text is not None:
        changes["message_text"] = args.dm_text
    if args.link_button is not None or args.remove_link_button:
        changes["message_buttons"] = _buttons(args.link_button)
    if args.public_reply is not None:
        changes["public_reply_texts"] = [args.public_reply] if args.public_reply.strip() else []
    if args.post is not None:
        account = str(current.social_account_id) if current.social_account_id else None
        scope = await _post_scope(
            call, args.post, account_id=current.social_account_id, account=account
        )
        changes["post_scope"] = scope.post_scope
        changes["media_item_ids"] = [scope.item.id] if scope.item else []
        changes["scheduled_post_ids"] = []
        resolved["post"] = scope.item.id if scope.item else None
    if not changes:
        raise ApiError("validation_error", "Nothing to change: send at least one field to change.")
    if args.confirmed:
        confirmations.require(call, args, args.confirmation_token, **resolved)
    body = body_of(current).model_copy(update=changes)
    savepoint = None if args.confirmed else await call.session.begin_nested()
    await definitions.update(
        call.session,
        current.id,
        body,
        disclosure=call.workspace.automation_disclosure,
        now=call.now,
    )
    out = await queries.one(call.session, current.id, _view(call))
    if savepoint is not None:
        result = await _result(
            call,
            out,
            preview=True,
            summary=f"Preview: “{out.name}” would be changed as shown. Nothing is changed yet",
            next_step=_confirm_step("save the change"),
            token=confirmations.issue(call, args, **resolved),
        )
        await _preview_end(call, savepoint)
        return result
    call.note("automation.updated", "automation", out.id, fields=sorted(changes))
    await _notify(call, out, "changed")
    live = out.status == ACTIVE
    return await _result(
        call,
        out,
        preview=False,
        summary=f"Changed “{out.name}”" + ("; it is on, so the change applies now" if live else ""),
        next_step="Pause it with pause_automation."
        if live
        else "It is off. Turn it on in Amplychat when it's ready.",
    )
