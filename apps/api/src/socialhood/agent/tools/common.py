"""What the tool modules share (TR-AGT-03, FR-AGT-05, FR-AGT-06, TA.4): registration with the
role bound, time arguments resolved by agent/timeparse.py, capped lists, short labels for
citations (AnswerRef), accounts by handle, and the caveats every area uses.

Errors: a tool raises ``ApiError`` like the services it calls, so the step stores a code and a
plain message the model can explain. Another workspace's ids are ``not_found``, exactly like ids
that don't exist (the session is in the run's workspace scope), so nothing reveals a row exists.
A time phrase the resolver can't read is ``validation_error`` naming the argument, and the model
asks the member (FR-AGT-06).
"""

from __future__ import annotations

import functools
import uuid
from collections.abc import Callable, Sequence
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from socialhood.agent.registry import (
    Release,
    ToolContext,
    ToolHandler,
    ToolResult,
    ToolSpec,
    registry,
)
from socialhood.agent.timeparse import (
    MONTH_ABBR,
    ResolvedInstant,
    ResolvedRange,
    TimeParseError,
    calendar_days,
    instant_label,
    resolve_instant,
    resolve_range,
    span_label,
)
from socialhood.auth.deps import ROLE_RANK
from socialhood.errors import ApiError, FieldError
from socialhood.models.agent import RiskTier
from socialhood.models.connections import SocialAccount
from socialhood.models.identity import Role
from socialhood.models.inbox import Contact
from socialhood.models.media import MediaItem
from socialhood.repositories import social_accounts
from socialhood.schemas.agent import AnswerRef, AnswerRefKind
from socialhood.services.analytics.ages import format_of
from socialhood.services.analytics.common import View, capabilities_from

LIST_DEFAULT = 10
LIST_MAX = 25
LABEL_CHARS = 60
TEXT_CHARS = 280  # a message, comment or caption in a result
ADMIN_ONLY = "Only owners and admins can use this, as in the app."
FACEBOOK_NOT_CONNECTED = (
    "Facebook isn't connected: Facebook Pages arrive in a later release, so only Instagram "
    "(and WhatsApp for messages) is covered."
)

PlatformName = Literal["instagram", "whatsapp", "facebook"]


def limit_field(default: int = LIST_DEFAULT, maximum: int = LIST_MAX) -> Any:
    """The ``limit`` argument of a list tool."""
    return Field(
        default=default, ge=1, le=maximum, description=f"How many to list (at most {maximum})."
    )


# ---------------------------------------------------------------- registration


def tool[I: BaseModel, R: ToolResult](
    *,
    name: str,
    label: str,
    description: str,
    input_model: type[I],
    result_model: type[R],
    tier: RiskTier = RiskTier.READ,
    min_role: Role = Role.AGENT,
) -> Callable[[ToolHandler[I, R]], ToolSpec[I, R]]:
    """Register an R1 tool (read or draft). The handler also refuses a principal below
    ``min_role`` itself (``forbidden``), so the bound holds whoever calls it (§8)."""

    def register(handler: ToolHandler[I, R]) -> ToolSpec[I, R]:
        @functools.wraps(handler)
        async def bounded(ctx: ToolContext, args: I) -> R:
            if ROLE_RANK[ctx.principal.role] < ROLE_RANK[min_role]:
                raise ApiError("forbidden", ADMIN_ONLY)
            return await handler(ctx, args)

        return registry.register(
            ToolSpec(
                name=name,
                label=label,
                description=description,
                input_model=input_model,
                result_model=result_model,
                tier=tier,
                release=Release.R1,
                min_role=min_role,
                handler=bounded,
            )
        )

    return register


# ---------------------------------------------------------------- time (FR-AGT-05)


class Period(BaseModel):
    """A resolved range as the answer states it (UTC ends, label in the workspace's zone)."""

    start: datetime
    end: datetime
    label: str
    rule: str | None = None  # the rule applied to an ambiguous phrase

    @classmethod
    def of(cls, resolved: ResolvedRange) -> Period:
        return cls(start=resolved.start, end=resolved.end, label=resolved.label, rule=resolved.rule)


class Days(BaseModel):
    """Calendar days in the workspace's zone, both included (analytics)."""

    since: date
    until: date
    label: str
    rule: str | None = None


def _bad_time(argument: str, error: TimeParseError) -> ApiError:
    return ApiError("validation_error", str(error), errors=[FieldError(argument, str(error))])


def period(
    ctx: ToolContext,
    phrase: str | None,
    *,
    default: str | None,
    upcoming: bool = False,
    argument: str = "range",
) -> ResolvedRange | None:
    """``phrase`` (or ``default`` when there is none) resolved in the workspace's zone."""
    text = (phrase or "").strip() or default
    if text is None:
        return None
    try:
        return resolve_range(text, now=ctx.now, tz=ctx.timezone, upcoming=upcoming)
    except TimeParseError as error:
        raise _bad_time(argument, error) from error


def days(ctx: ToolContext, resolved: ResolvedRange) -> Days:
    """The analytics days for a resolved range (timeparse.calendar_days)."""
    since, until = calendar_days(resolved, ctx.timezone)
    return Days(since=since, until=until, label=span_label(since, until), rule=resolved.rule)


def instant(ctx: ToolContext, phrase: str, *, argument: str = "when") -> ResolvedInstant:
    try:
        return resolve_instant(phrase, now=ctx.now, tz=ctx.timezone)
    except TimeParseError as error:
        raise _bad_time(argument, error) from error


def when(ctx: ToolContext, at: datetime | None) -> str | None:
    """A stored time as the answer states it, in the workspace's zone."""
    return instant_label(at, ctx.timezone, ctx.now) if at is not None else None


# ---------------------------------------------------------------- lists and text


def capped[T](items: Sequence[T], limit: int) -> tuple[list[T], int]:
    """The first ``limit`` items and how many more there are."""
    return list(items[:limit]), max(len(items) - limit, 0)


def clip(text: str | None, chars: int = TEXT_CHARS) -> str | None:
    """Text for a result, on one line and at most ``chars`` characters."""
    if text is None:
        return None
    compact = " ".join(text.split())
    return compact if len(compact) <= chars else compact[: chars - 1].rstrip() + "…"


def more_words(shown: int, more: int, noun: str) -> str:
    """ "3 posts", or "10 posts (12 more)"."""
    plural = noun if shown == 1 else f"{noun}s"
    return f"{shown} {plural}" + (f" ({more} more)" if more else "")


# ---------------------------------------------------------------- citations (FR-AGT-01)


def ref(
    kind: AnswerRefKind, record_id: uuid.UUID, label: str, parent_id: uuid.UUID | None = None
) -> AnswerRef:
    """``parent_id`` is where the record is shown: a comment's post, a scheduled message's
    conversation."""
    return AnswerRef(
        kind=kind, id=record_id, label=clip(label, LABEL_CHARS) or kind, parent_id=parent_id
    )


def quoted(text: str | None) -> str:
    """ "“Too expensive for me”" for a comment or message label."""
    return f"“{clip(text, LABEL_CHARS - 2) or ''}”"


def contact_name(contact: Contact | None) -> str:
    if contact is None:
        return "a customer"
    if contact.display_name:
        return contact.display_name
    return f"@{contact.username}" if contact.username else "a customer"


FORMAT_WORDS = {"feed": "Post", "reel": "Reel", "story": "Story"}


def post_label_of(media_type: str, posted_at: datetime, ctx: ToolContext) -> str:
    """ "Reel of 26 Sep", "Post of 3 Jan 2025" (the year when it isn't this one)."""
    local = posted_at.astimezone(ctx.timezone)
    year = "" if local.year == ctx.now.astimezone(ctx.timezone).year else f" {local.year}"
    kind = FORMAT_WORDS[format_of(media_type)]
    return f"{kind} of {local.day} {MONTH_ABBR[local.month - 1]}{year}"


def post_label(item: MediaItem, ctx: ToolContext) -> str:
    return post_label_of(item.media_type, item.posted_at, ctx)


def post_ref(item: MediaItem, ctx: ToolContext) -> AnswerRef:
    return ref("post", item.id, post_label(item, ctx))


# ---------------------------------------------------------------- accounts


def handle(acct: SocialAccount) -> str:
    if acct.username:
        return f"@{acct.username}"
    return acct.display_name or acct.phone_number or acct.platform.capitalize()


async def find_account(ctx: ToolContext, account: str | None) -> SocialAccount | None:
    """A connected account of the workspace by id, @handle, name or platform ("instagram" when
    there is one Instagram account); None when ``account`` is empty. Anything else is
    ``not_found``."""
    text = (account or "").strip()
    if not text:
        return None
    accounts = await social_accounts.list_all(ctx.session)
    try:
        wanted = uuid.UUID(text)
    except ValueError:
        wanted = None
    if wanted is not None:
        matches = [a for a in accounts if a.id == wanted]
    else:
        name = text.lstrip("@").casefold()
        matches = [
            a
            for a in accounts
            if name in ((a.username or "").casefold(), (a.display_name or "").casefold())
        ] or [a for a in accounts if a.platform == name]
    if len(matches) == 1:
        return matches[0]
    if matches:
        names = ", ".join(handle(a) for a in matches)
        raise ApiError("conflict", f"Several accounts match “{text}”: {names}. Which one?")
    raise ApiError("not_found", f"No connected account matches “{text}”.")


def facebook_asked(*values: str | None) -> bool:
    """Whether the member asked about Facebook, which isn't connected in R1 (FR-AGT-06)."""
    return any((v or "").strip().lower() in ("facebook", "fb", "facebook page") for v in values)


def analytics_view(ctx: ToolContext) -> View:
    """The analytics services' view: the workspace's zone, the run's clock and what each account
    can do (insights granted or not)."""
    return View(
        timezone=ctx.timezone.key, now=ctx.now, capabilities=capabilities_from(ctx.platform)
    )
