"""Automation reads (T4.3; FR-AUT-03, 04, 10, 15, 16, 19; UX-SCR-02, 03, 12): the API projection
with its overlaps, queue, 7-day figures and what activation still needs; the list with filters,
search and sort; the run log; posts for the picker.

The list returns every matching automation (a workspace has at most a few hundred); the web
groups the rows by account. Sorts: recent runs (most runs in 7 days first, then the latest run),
name, or creation date (newest first). Cursors are the inbox's opaque (time, id) pairs.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast

from sqlalchemy import (
    ColumnElement,
    ColumnExpressionArgument,
    DateTime,
    Uuid,
    literal,
    select,
    tuple_,
)
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError
from socialhood.models.automations import Automation, AutomationRun, Comment
from socialhood.models.inbox import Contact, Message
from socialhood.models.media import MediaItem, MediaType
from socialhood.repositories import automations as repo
from socialhood.repositories.automations import Keyword, PostRow, escape_like
from socialhood.schemas.automations import (
    ActionName,
    AutomationList,
    AutomationListStats,
    AutomationRunList,
    LinkButton,
    MatchModeName,
    OverlapWarning,
    PostList,
    PostRef,
    PostScopeName,
    PostSummary,
    RunContact,
    RunError,
    RunResultName,
    StatusName,
    SurgeOrderName,
    TriggerName,
)
from socialhood.schemas.automations import Automation as AutomationOut
from socialhood.schemas.automations import AutomationRun as AutomationRunOut
from socialhood.services.automations import matching, stats, validation, windows
from socialhood.services.automations.definitions import definition_of
from socialhood.services.conversations import decode_cursor, encode_cursor

SortName = Literal["recent_runs", "name", "created"]
EXCERPT_CHARS = 200
_TIMESTAMP = DateTime(timezone=True)
_UUID = Uuid()


@dataclass(frozen=True)
class View:
    """What the projection needs from the workspace and the clock."""

    disclosure: str | None
    timezone: str
    now: datetime


# ---------------------------------------------------------------- the projection


def candidate(automation: Automation, keywords: Sequence[Keyword]) -> matching.Candidate:
    return matching.Candidate(
        id=automation.id,
        trigger=cast(TriggerName, automation.trigger),
        match_mode=cast(MatchModeName, automation.match_mode),
        keywords=tuple(k.normalized for k in keywords),
        priority=automation.priority,
        created_at=automation.created_at,
    )


async def _overlaps(
    session: AsyncSession,
    automations: Sequence[Automation],
    keywords: dict[uuid.UUID, list[Keyword]],
) -> dict[uuid.UUID, list[OverlapWarning]]:
    """FR-AUT-15: keywords shared with other active automations of the same account and
    trigger, naming the other automation and which one runs first."""
    accounts = {a.social_account_id for a in automations if a.social_account_id and a.trigger}
    actives = await repo.active_for_accounts(session, [a for a in accounts if a is not None])
    missing = [x.id for x in actives if x.id not in keywords]
    known = {**keywords, **await repo.keywords_for(session, missing)}
    found: dict[uuid.UUID, list[OverlapWarning]] = {}
    for a in automations:
        found[a.id] = []
        if a.social_account_id is None or a.trigger is None:
            continue
        others = [
            (x, candidate(x, known[x.id]))
            for x in actives
            if x.social_account_id == a.social_account_id and x.id != a.id and x.trigger
        ]
        names = {x.id: x.name for x, _ in others}
        typed = {k.normalized: k.keyword for k in keywords[a.id]}
        for o in matching.overlaps(candidate(a, keywords[a.id]), [c for _, c in others]):
            found[a.id].append(
                OverlapWarning(
                    keyword=typed.get(o.keyword, o.keyword),
                    automation_id=o.other_id,
                    automation_name=names[o.other_id],
                    this_runs_first=o.this_runs_first,
                )
            )
    return found


def _post_ref(row: PostRow) -> PostRef:
    item = row.item
    return PostRef(
        media_item_id=row.link.media_item_id,
        scheduled_post_id=row.link.scheduled_post_id,
        caption=item.caption if item else None,
        thumbnail_url=(item.thumbnail_url or item.media_url) if item else None,
        media_type=item.media_type if item else None,
        posted_at=item.posted_at if item else None,
    )


async def project(
    session: AsyncSession, automations: Sequence[Automation], view: View
) -> list[AutomationOut]:
    ids = [a.id for a in automations]
    keywords = await repo.keywords_for(session, ids)
    posts = await repo.posts_for(session, ids)
    accounts = await repo.accounts(session)
    asset_ids = [a.message_media_asset_id for a in automations if a.message_media_asset_id]
    urls = await repo.asset_urls(session, asset_ids)
    figures = await stats.list_stats(session, automations, timezone=view.timezone, now=view.now)
    queue = await stats.queued_counts(session, now=view.now)
    overlaps = await _overlaps(session, automations, keywords)
    out: list[AutomationOut] = []
    for a in automations:
        account = accounts.get(a.social_account_id) if a.social_account_id else None
        definition = definition_of(a, keywords=keywords[a.id], posts=posts[a.id], account=account)
        errors = validation.activation_errors(definition, disclosure=view.disclosure, now=view.now)
        out.append(
            _automation_out(
                a,
                keywords=keywords[a.id],
                posts=posts[a.id],
                media_url=urls.get(a.message_media_asset_id) if a.message_media_asset_id else None,
                figures=figures[a.id],
                queue=queue,
                overlaps=overlaps[a.id],
                missing=validation.missing_fields(errors),
                now=view.now,
            )
        )
    return out


def _automation_out(
    a: Automation,
    *,
    keywords: Sequence[Keyword],
    posts: Sequence[PostRow],
    media_url: str | None,
    figures: AutomationListStats,
    queue: stats.QueueCounts,
    overlaps: list[OverlapWarning],
    missing: list[str],
    now: datetime,
) -> AutomationOut:
    return AutomationOut(
        id=a.id,
        name=a.name,
        status=cast(StatusName, a.status),
        display_status=windows.display_status(a, now),
        social_account_id=a.social_account_id,
        trigger=cast(TriggerName | None, a.trigger),
        keywords=[k.keyword for k in keywords],
        match_mode=cast(MatchModeName, a.match_mode),
        action=cast(ActionName | None, a.action),
        message_text=a.message_text,
        message_buttons=[
            LinkButton(title=str(b.get("title", "")), url=str(b.get("url", "")))
            for b in a.message_buttons or []
        ],
        message_media_asset_id=a.message_media_asset_id,
        message_media_url=media_url,
        ai_instructions=a.ai_instructions,
        public_reply_texts=list(a.public_reply_texts or []),
        post_scope=cast(PostScopeName, a.post_scope),
        posts=[_post_ref(r) for r in posts],
        cooldown_hours=a.cooldown_hours,
        starts_at=a.starts_at,
        ends_at=a.ends_at,
        surge_order=cast(SurgeOrderName, a.surge_order),
        confirm_first=a.confirm_first,
        opening_text=a.opening_text,
        opening_button=a.opening_button,
        follow_nudge=a.follow_nudge,
        follow_nudge_text=a.follow_nudge_text,
        priority=a.priority,
        template_key=a.template_key,
        activated_at=a.activated_at,
        paused_at=a.paused_at,
        last_run_at=figures.last_run_at,
        created_at=a.created_at,
        updated_at=a.updated_at,
        stats=figures,
        queue=queue.info(a),
        missing_for_activation=missing,
        overlaps=overlaps,
    )


async def one(session: AsyncSession, automation_id: uuid.UUID, view: View) -> AutomationOut:
    """The automation as stored now (reloaded, so values the database set are current)."""
    automation = await repo.get(session, automation_id, fresh=True)
    if automation is None:
        raise ApiError("not_found")
    return (await project(session, [automation], view))[0]


# ---------------------------------------------------------------- the list (FR-AUT-03, 19)


async def list_automations(
    session: AsyncSession,
    *,
    account_id: uuid.UUID | None,
    status: str | None,
    trigger: str | None,
    q: str | None,
    sort: SortName,
    view: View,
) -> AutomationList:
    query = (q or "").strip()
    automations = await repo.list_filtered(
        session,
        account_id=account_id,
        status=status,
        trigger=trigger,
        q=query or None,
        q_normalized=matching.normalize(query) if query else None,
    )
    items = await project(session, automations, view)
    return AutomationList(items=sort_items(items, sort))


def sort_items(items: list[AutomationOut], sort: SortName) -> list[AutomationOut]:
    if sort == "name":
        return sorted(items, key=lambda o: (o.name.casefold(), o.created_at))
    if sort == "created":
        return sorted(items, key=lambda o: o.created_at, reverse=True)
    # Most runs in 7 days first, then the latest run; ties keep the runtime order.
    return sorted(
        items,
        key=lambda o: (
            -o.stats.runs_7d,
            -(o.stats.last_run_at.timestamp() if o.stats.last_run_at else 0.0),
            o.priority,
            o.created_at,
        ),
    )


# ---------------------------------------------------------------- the run log (FR-AUT-04)


def _excerpt(text: str | None) -> str | None:
    if text is None:
        return None
    return text if len(text) <= EXCERPT_CHARS else text[: EXCERPT_CHARS - 1].rstrip() + "…"


def _after_cursor(
    at: ColumnExpressionArgument[Any], row_id: ColumnExpressionArgument[Any], cursor: str
) -> ColumnElement[bool]:
    """Rows after the cursor in (at DESC, id DESC) order, as one row comparison."""
    cursor_at, cursor_id = decode_cursor(cursor)
    return tuple_(at, row_id) < tuple_(literal(cursor_at, _TIMESTAMP), literal(cursor_id, _UUID))


async def list_runs(
    session: AsyncSession,
    automation_id: uuid.UUID,
    *,
    result: RunResultName | None,
    cursor: str | None,
    limit: int,
) -> AutomationRunList:
    """Newest first: time, contact, the triggering text, the result and any error."""
    statement = (
        select(AutomationRun, Contact, Message.text, Comment.text)
        .outerjoin(Contact, Contact.id == AutomationRun.contact_id)
        .outerjoin(Message, Message.id == AutomationRun.trigger_message_id)
        .outerjoin(Comment, Comment.id == AutomationRun.trigger_comment_id)
        .where(AutomationRun.automation_id == automation_id)
    )
    if result is not None:
        statement = statement.where(AutomationRun.result == result)
    if cursor:
        statement = statement.where(
            _after_cursor(AutomationRun.created_at, AutomationRun.id, cursor)
        )
    statement = statement.order_by(AutomationRun.created_at.desc(), AutomationRun.id.desc())
    rows = (await session.execute(statement.limit(limit + 1))).all()
    page = rows[:limit]
    items = [
        AutomationRunOut(
            id=run.id,
            created_at=run.created_at,
            trigger_kind="dm" if run.trigger_message_id else "comment",
            trigger_text=_excerpt(message_text if run.trigger_message_id else comment_text),
            matched_keyword=run.matched_keyword,
            result=cast(RunResultName, run.result),
            contact=(
                RunContact(
                    id=contact.id,
                    display_name=contact.display_name,
                    username=contact.username,
                    profile_picture_url=contact.profile_picture_url,
                )
                if contact
                else None
            ),
            conversation_id=run.conversation_id,
            private_reply_message_id=run.private_reply_message_id,
            public_reply_platform_id=run.public_reply_platform_id,
            contact_replied_at=run.contact_replied_at,
            confirmed_at=run.confirmed_at,
            follows_business=run.follows_business,
            nudge_message_id=run.nudge_message_id,
            error=(
                RunError(code=run.error_code, message=run.error_message or "")
                if run.error_code
                else None
            ),
        )
        for run, contact, message_text, comment_text in page
    ]
    last = page[-1][0] if page else None
    more = len(rows) > limit and last is not None
    return AutomationRunList(
        items=items, next_cursor=encode_cursor(last.created_at, last.id) if more and last else None
    )


# ---------------------------------------------------------------- posts for the picker


async def list_posts(
    session: AsyncSession,
    *,
    account_id: uuid.UUID | None,
    q: str | None,
    cursor: str | None,
    limit: int,
) -> PostList:
    """The account's posts (not stories, which take no comments), newest first; ``q`` searches
    captions."""
    statement = select(MediaItem).where(MediaItem.media_type != MediaType.STORY)
    if account_id is not None:
        statement = statement.where(MediaItem.social_account_id == account_id)
    query = (q or "").strip()
    if query:
        statement = statement.where(MediaItem.caption.ilike(f"%{escape_like(query)}%", escape="\\"))
    if cursor:
        statement = statement.where(_after_cursor(MediaItem.posted_at, MediaItem.id, cursor))
    statement = statement.order_by(MediaItem.posted_at.desc(), MediaItem.id.desc())
    items = list((await session.scalars(statement.limit(limit + 1))).all())
    page = items[:limit]
    return PostList(
        items=[
            PostSummary(
                id=item.id,
                social_account_id=item.social_account_id,
                platform_media_id=item.platform_media_id,
                media_type=item.media_type,
                caption=item.caption,
                media_url=item.media_url,
                thumbnail_url=item.thumbnail_url,
                permalink=item.permalink,
                posted_at=item.posted_at,
                like_count=item.like_count,
                comments_count=item.comments_count,
            )
            for item in page
        ],
        next_cursor=(
            encode_cursor(page[-1].posted_at, page[-1].id) if len(items) > limit else None
        ),
    )
