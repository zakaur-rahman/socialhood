"""Automation tools (FR-AGT-02, FR-AGT-03, TA.4; agent-architecture.html §5). Owners and admins,
as in the UI (``min_role`` admin).

R1:
- list_automations / get_automation / get_automation_stats: read; services/automations
  (definitions, runs and per-automation results, FR-AUT-17).
- test_automation(id, kind, text): read; the editor's test box (which automation would answer,
  and what), which sends nothing (services/automations/dry_run).
- prepare_automation(description): draft; a template and definition for the request, returned as
  an automation_draft action card that opens the editor unsaved and pre-filled (F-11); the
  member saves and activates it there. The model fills the fields; without a template, trigger
  or action the tool picks a template from words in the request (TEMPLATE_HINTS, stated in the
  result). Nothing is stored.

R2: create_automation_draft (low, create_automations), activate_automation (high) and
pause_automation (low) (create_automations), delete_automation (destructive,
delete_automations); services/automations/definitions.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from socialhood.agent.registry import DraftResult, ToolContext, ToolResult
from socialhood.agent.timeparse import span_label
from socialhood.agent.tools.common import (
    capped,
    clip,
    find_account,
    handle,
    limit_field,
    quoted,
    ref,
    tool,
)
from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.agent import RiskTier
from socialhood.models.connections import AccountStatus
from socialhood.models.identity import Role
from socialhood.repositories import comments as comments_repo
from socialhood.repositories import social_accounts, workspaces
from socialhood.schemas.agent import AutomationDraftAction, AutomationDraftPrefill
from socialhood.schemas.automations import (
    ActionName,
    AutomationTest,
    PostScopeName,
    StatusName,
    TriggerName,
)
from socialhood.services.automations import definitions, dry_run, queries, stats, templates
from socialhood.services.automations.validation import COMMENT_TRIGGERS

TRIGGER_WORDS = {
    "dm_keyword": "a DM with a keyword",
    "comment_keyword": "a comment with a keyword",
    "comment_any": "any comment",
}
ACTION_WORDS = {"send_message": "sends a message", "ai_reply": "replies with AI"}
# prepare_automation without a template, trigger or action: the first template whose words
# appear in the request.
TEMPLATE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("giveaway", ("giveaway", "contest")),
    ("send_link", ("link", "links")),
    ("price_on_request", ("price", "prices", "pricing", "cost", "rate")),
    ("catalogue_by_dm", ("catalogue", "catalog")),
    ("book_a_call", ("book", "booking", "appointment", "call")),
    ("answer_faqs", ("faq", "faqs", "question", "questions", "shipping", "delivery", "returns")),
)


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def _view(ctx: ToolContext, *, now: datetime | None = None) -> queries.View:
    workspace = await workspaces.get(ctx.session, ctx.workspace_id)
    return queries.View(
        disclosure=workspace.automation_disclosure if workspace else None,
        timezone=ctx.timezone.key,
        now=now or ctx.now,
    )


# ---------------------------------------------------------------- list_automations


class ListAutomationsInput(_Input):
    status: StatusName | None = None
    trigger: TriggerName | None = None
    account: str | None = Field(default=None, max_length=100)
    q: str | None = Field(default=None, max_length=100, description="Words in names or keywords.")
    limit: int = limit_field(default=20, maximum=50)


class AutomationItem(BaseModel):
    id: uuid.UUID
    name: str
    status: str  # draft, active, paused
    display_status: str  # also scheduled and ended (FR-AUT-17)
    trigger: str | None = None
    keywords: list[str]
    action: str | None = None
    account: str | None = None
    runs_7d: int
    last_run_at: datetime | None = None
    queued: int  # private replies waiting in the account's queue
    missing_for_activation: list[str]


class AutomationsResult(ToolResult):
    items: list[AutomationItem]
    total: int
    more: int


@tool(
    name="list_automations",
    label="Checking your automations",
    description=(
        "Automations with their status, trigger, keywords, action, account and runs in the last "
        "7 days, most active first."
    ),
    input_model=ListAutomationsInput,
    result_model=AutomationsResult,
    min_role=Role.ADMIN,
)
async def list_automations(ctx: ToolContext, args: ListAutomationsInput) -> AutomationsResult:
    acct = await find_account(ctx, args.account)
    found = await queries.list_automations(
        ctx.session,
        account_id=acct.id if acct else None,
        status=args.status,
        trigger=args.trigger,
        q=args.q,
        sort="recent_runs",
        view=await _view(ctx),
    )
    accounts = {a.id: a for a in await social_accounts.list_all(ctx.session)}
    shown, more = capped(found.items, args.limit)
    items = [
        AutomationItem(
            id=a.id,
            name=a.name,
            status=a.status,
            display_status=a.display_status,
            trigger=a.trigger,
            keywords=a.keywords[:8],
            action=a.action,
            account=(
                handle(accounts[a.social_account_id]) if a.social_account_id in accounts else None
            ),
            runs_7d=a.stats.runs_7d,
            last_run_at=a.stats.last_run_at,
            queued=a.queue.waiting,
            missing_for_activation=a.missing_for_activation,
        )
        for a in shown
    ]
    active = sum(1 for a in found.items if a.status == "active")
    noun = "automation" if len(found.items) == 1 else "automations"
    return AutomationsResult(
        summary=f"Found {len(found.items)} {noun}, {active} active",
        items=items,
        total=len(found.items),
        more=more,
        refs=[ref("automation", i.id, i.name) for i in items],
    )


# ---------------------------------------------------------------- get_automation


class GetAutomationInput(_Input):
    automation_id: uuid.UUID


class Overlap(BaseModel):
    keyword: str
    other: str  # the other automation's name
    this_runs_first: bool


class AutomationResult(ToolResult):
    id: uuid.UUID
    name: str
    status: str
    display_status: str
    account: str | None = None
    trigger: str | None = None
    keywords: list[str]
    match_mode: str
    action: str | None = None
    message_text: str | None = None
    ai_instructions: str | None = None
    public_reply_texts: list[str]
    post_scope: str
    post_count: int
    cooldown_hours: int
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    tap_first: bool
    follow_nudge: bool
    runs_7d: int
    last_run_at: datetime | None = None
    queued: int
    missing_for_activation: list[str]
    overlaps: list[Overlap]


@tool(
    name="get_automation",
    label="Reading the automation",
    description=(
        "One automation's definition: trigger, keywords, action and message, posts, cooldown, "
        "run window, runs in 7 days, what it still needs to be activated and keywords it shares "
        "with other automations."
    ),
    input_model=GetAutomationInput,
    result_model=AutomationResult,
    min_role=Role.ADMIN,
)
async def get_automation(ctx: ToolContext, args: GetAutomationInput) -> AutomationResult:
    a = await queries.one(ctx.session, args.automation_id, await _view(ctx))
    acct = (
        await social_accounts.get(ctx.session, a.social_account_id) if a.social_account_id else None
    )
    caveats = []
    if a.missing_for_activation:
        caveats.append(
            "Before it can be activated it needs: " + ", ".join(a.missing_for_activation) + "."
        )
    what = f"{TRIGGER_WORDS.get(a.trigger or '', 'no trigger yet')}"
    return AutomationResult(
        summary=clip(
            f"“{a.name}” is {a.display_status}: on {what}, {a.stats.runs_7d} runs in 7 days", 300
        )
        or a.name,
        id=a.id,
        name=a.name,
        status=a.status,
        display_status=a.display_status,
        account=handle(acct) if acct else None,
        trigger=a.trigger,
        keywords=a.keywords,
        match_mode=a.match_mode,
        action=a.action,
        message_text=clip(a.message_text, 500),
        ai_instructions=clip(a.ai_instructions, 500),
        public_reply_texts=a.public_reply_texts,
        post_scope=a.post_scope,
        post_count=len(a.posts),
        cooldown_hours=a.cooldown_hours,
        starts_at=a.starts_at,
        ends_at=a.ends_at,
        tap_first=a.confirm_first,
        follow_nudge=a.follow_nudge,
        runs_7d=a.stats.runs_7d,
        last_run_at=a.stats.last_run_at,
        queued=a.queue.waiting,
        missing_for_activation=a.missing_for_activation,
        overlaps=[
            Overlap(keyword=o.keyword, other=o.automation_name, this_runs_first=o.this_runs_first)
            for o in a.overlaps
        ],
        refs=[ref("automation", a.id, a.name)],
        caveats=caveats,
    )


# ---------------------------------------------------------------- get_automation_stats


class AutomationStatsInput(_Input):
    automation_id: uuid.UUID
    days: Literal[7, 30] = Field(default=7, description="The last 7 or 30 days.")


class Day(BaseModel):
    date: date
    runs: int
    failures: int


class AutomationStatsResult(ToolResult):
    automation_id: uuid.UUID
    name: str
    days: int
    label: str  # the days covered, e.g. "24-30 Sep 2026"
    runs: int
    dms_sent: int
    public_replies: int
    replied_24h: int  # people who wrote back within 24 hours of the DM
    failures: int
    skipped_cooldown: int
    skipped_expired: int
    queued_now: int
    tapped: int  # tap first: openings answered
    awaiting_now: int
    nudged: int
    daily: list[Day]  # oldest first


@tool(
    name="get_automation_stats",
    label="Reading the automation's results",
    description=(
        "An automation's results for the last 7 or 30 days: runs, DMs sent, public replies, "
        "people who replied, failures, skips, queue, tap-first answers and nudges, per day."
    ),
    input_model=AutomationStatsInput,
    result_model=AutomationStatsResult,
    min_role=Role.ADMIN,
)
async def get_automation_stats(
    ctx: ToolContext, args: AutomationStatsInput
) -> AutomationStatsResult:
    automation = await definitions.get_or_404(ctx.session, args.automation_id)
    figures = await stats.automation_stats(
        ctx.session, automation, days=args.days, timezone=ctx.timezone.key, now=ctx.now
    )
    label = (
        span_label(figures.daily[0].date, figures.daily[-1].date)
        if figures.daily
        else f"the last {args.days} days"
    )
    return AutomationStatsResult(
        summary=clip(
            f"“{automation.name}”, {label}: {figures.runs} runs, {figures.dms_sent} DMs sent, "
            f"{figures.failures} failed",
            300,
        )
        or automation.name,
        automation_id=automation.id,
        name=automation.name,
        days=args.days,
        label=label,
        runs=figures.runs,
        dms_sent=figures.dms_sent,
        public_replies=figures.public_replies,
        replied_24h=figures.replied_24h,
        failures=figures.failures,
        skipped_cooldown=figures.skipped.cooldown,
        skipped_expired=figures.skipped.expired,
        queued_now=figures.queued_now,
        tapped=figures.tapped,
        awaiting_now=figures.awaiting_now,
        nudged=figures.nudged,
        daily=[Day(date=d.date, runs=d.runs, failures=d.failures) for d in figures.daily],
        refs=[ref("automation", automation.id, automation.name)],
    )


# ---------------------------------------------------------------- test_automation


class AutomationTestInput(_Input):
    automation_id: uuid.UUID
    kind: Literal["dm", "comment"]
    text: str = Field(min_length=1, max_length=2000, description="The DM or comment to try.")
    post_id: uuid.UUID | None = Field(default=None, description="For a comment on this post.")


class AutomationTestOutcome(ToolResult):
    automation_id: uuid.UUID
    matched: bool
    matched_keyword: str | None = None
    winner: str | None = None  # the automation that would actually run
    winner_id: uuid.UUID | None = None
    reason: str | None = None  # why this one wouldn't run, in plain words
    message: str | None = None  # what it would send, rendered with a sample name
    public_reply: str | None = None
    opening: str | None = None
    nudge: str | None = None


@tool(
    name="test_automation",
    label="Testing the automation",
    description=(
        "What would happen if someone sent this DM or comment: whether this automation matches, "
        "which automation would actually answer and what it would send. Sends nothing."
    ),
    input_model=AutomationTestInput,
    result_model=AutomationTestOutcome,
    min_role=Role.ADMIN,
)
async def test_automation(ctx: ToolContext, args: AutomationTestInput) -> AutomationTestOutcome:
    automation = await definitions.get_or_404(ctx.session, args.automation_id)
    view = await _view(ctx)
    outcome = await dry_run.run(
        ctx.session,
        automation,
        AutomationTest(kind=args.kind, text=args.text, media_item_id=args.post_id),
        disclosure=view.disclosure,
        now=ctx.now,
    )
    refs = [ref("automation", automation.id, automation.name)]
    if outcome.winner is not None and outcome.winner.id != automation.id:
        refs.append(ref("automation", outcome.winner.id, outcome.winner.name))
    if outcome.matched and (outcome.winner is None or outcome.winner.id == automation.id):
        summary = f"“{automation.name}” would answer {quoted(args.text)}"
    elif outcome.winner is not None:
        summary = f"“{outcome.winner.name}” would answer {quoted(args.text)}, not this one"
    else:
        summary = f"No automation would answer {quoted(args.text)}"
    return AutomationTestOutcome(
        summary=clip(summary, 300) or "Tested the automation",
        automation_id=automation.id,
        matched=outcome.matched,
        matched_keyword=outcome.matched_keyword,
        winner=outcome.winner.name if outcome.winner else None,
        winner_id=outcome.winner.id if outcome.winner else None,
        reason=outcome.reason,
        message=outcome.rendered_message,
        public_reply=outcome.rendered_public_reply,
        opening=outcome.rendered_opening,
        nudge=outcome.rendered_nudge,
        refs=refs,
    )


# ---------------------------------------------------------------- prepare_automation


class PrepareAutomationInput(_Input):
    description: str = Field(
        min_length=1, max_length=500, description="What the automation should do, as asked."
    )
    template_key: str | None = Field(
        default=None,
        max_length=40,
        description=(
            "A template to start from: send_link, giveaway, price_on_request, catalogue_by_dm, "
            "answer_faqs or book_a_call."
        ),
    )
    name: str | None = Field(default=None, max_length=80)
    account: str | None = Field(default=None, max_length=100, description="@handle or id.")
    trigger: TriggerName | None = None
    keywords: list[str] = Field(default_factory=list, max_length=20)
    action: ActionName | None = None
    message_text: str | None = Field(default=None, max_length=1000)
    ai_instructions: str | None = Field(default=None, max_length=2000)
    public_reply_texts: list[str] = Field(default_factory=list, max_length=5)
    post_scope: PostScopeName | None = None
    post_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)


class PrepareAutomationResult(DraftResult):
    template_key: str | None = None
    template_rule: str | None = None  # why this template, when the tool chose it
    name: str
    account: str | None = None
    trigger: TriggerName | None = None
    keywords: list[str]
    action: ActionName | None = None
    missing_for_activation: list[str]


def _suggest(description: str) -> tuple[templates.Template | None, str | None]:
    words = set(re.findall(r"[a-z]+", description.casefold()))
    for key, hints in TEMPLATE_HINTS:
        hit = next((h for h in hints if h in words), None)
        template = templates.find(key)
        if hit and template is not None:
            return (
                template,
                f"started from the “{template.name}” template: the request says “{hit}”",
            )
    return None, None


def _keywords(typed: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for word in typed:
        clean = " ".join(word.split())[:50]
        if clean and clean.casefold() not in seen:
            seen[clean.casefold()] = clean
    return list(seen.values())


@tool(
    name="prepare_automation",
    label="Preparing an automation draft",
    description=(
        "Prepare a new automation from the request: fill the template, trigger (dm_keyword, "
        "comment_keyword, comment_any), keywords, action (send_message or ai_reply), message and "
        "posts you can tell from it. Returns a card that opens the automation editor filled in "
        "and unsaved; the member saves and activates it there. Nothing is created."
    ),
    input_model=PrepareAutomationInput,
    result_model=PrepareAutomationResult,
    tier=RiskTier.DRAFT,
    min_role=Role.ADMIN,
)
async def prepare_automation(
    ctx: ToolContext, args: PrepareAutomationInput
) -> PrepareAutomationResult:
    rule = None
    if args.template_key:
        template = templates.find(args.template_key)
        if template is None:
            keys = ", ".join(t.key for t in templates.TEMPLATES)
            raise ApiError(
                "validation_error",
                f"There's no template “{args.template_key}”; the templates are {keys}.",
                errors=[FieldError("template_key", "Pick one of the templates.")],
            )
    elif args.trigger is None and args.action is None:
        template, rule = _suggest(args.description)
    else:
        template = None

    acct = await find_account(ctx, args.account)
    if acct is None:
        live = [
            a
            for a in await social_accounts.list_all(ctx.session)
            if a.status != AccountStatus.DISCONNECTED and a.platform == "instagram"
        ]
        if len(live) == 1:
            acct = live[0]
    trigger = args.trigger or (template.trigger if template else None)
    action = args.action or (template.action if template else None)
    keywords = _keywords(args.keywords or list(template.keywords if template else ()))
    message_text = args.message_text or (template.message_text if template else None)
    ai_instructions = args.ai_instructions or (template.ai_instructions if template else None)
    public_replies = args.public_reply_texts or list(
        template.public_reply_texts if template else ()
    )
    if trigger not in COMMENT_TRIGGERS:
        public_replies = []
    scope = args.post_scope or (template.post_scope if template else "all")
    post_ids = list(dict.fromkeys(args.post_ids))
    for post_id in post_ids:
        item = await comments_repo.get_media_item(ctx.session, post_id)
        if item is None or (acct is not None and item.social_account_id != acct.id):
            raise ApiError(
                "validation_error",
                "A post wasn't found on this account.",
                errors=[FieldError("post_ids", "Pick posts of the automation's account.")],
            )
    if post_ids and scope == "all":
        scope = "selected"
    name = args.name or (template.name if template else None) or clip(args.description, 80)
    assert name is not None

    missing = []
    if acct is None:
        missing.append("an account")
    if trigger is None:
        missing.append("a trigger")
    elif trigger != "comment_any" and not keywords:
        missing.append("keywords")
    if action is None:
        missing.append("an action")
    elif action == "send_message" and not message_text:
        missing.append("the message")
    if scope == "selected" and not post_ids:
        missing.append("the posts")
    caveats = []
    if missing:
        caveats.append("Before it can be activated it needs: " + ", ".join(missing) + ".")
    if action == "ai_reply" and not entitlement(
        await current_plan(ctx.session), "ai_reply_automations"
    ):
        caveats.append("AI replies in automations are part of Pro; the editor asks to upgrade.")
    what = TRIGGER_WORDS.get(trigger or "", "a trigger to choose")
    return PrepareAutomationResult(
        summary=clip(f"Prepared a draft automation “{name}” on {what}", 300) or "Prepared a draft",
        template_key=template.key if template else None,
        template_rule=rule,
        name=name,
        account=handle(acct) if acct else None,
        trigger=trigger,
        keywords=keywords,
        action=action,
        missing_for_activation=missing,
        caveats=caveats,
        action_card=AutomationDraftAction(
            kind="automation_draft",
            label="Open the automation draft",
            route="automations/new?draft=1",
            note="Nothing is saved until you save it in the editor.",
            prefill=AutomationDraftPrefill(
                template_key=template.key if template else None,
                name=name,
                social_account_id=acct.id if acct else None,
                trigger=trigger,
                keywords=keywords,
                action=action,
                message_text=message_text,
                ai_instructions=ai_instructions,
                public_reply_texts=public_replies,
                post_scope=scope,
                media_item_ids=post_ids,
            ),
        ),
    )
