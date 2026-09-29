"""Scheduled posts and their lifecycle (T7.1; F-13, FR-PUB-01, FR-PUB-04, FR-PUB-08, FR-PUB-09,
FR-PUB-10, FR-PUB-14; C-043).

- A post is created as a draft; its accounts are its targets, ``pending`` from the start. PUT
  replaces the editable post (autosave, Update schedule, Edit and retry); the format is derived
  from the assets on every save (§5.7). Accounts must be this workspace's and assets its post
  uploads, else 422 on ``targets.{i}`` / ``asset_ids.{i}``; everything else a draft may lack is
  the checklist's business.
- Schedule, Add to queue and Publish now run the checklist (FR-PUB-10) at the time they set and
  refuse with every failing item as a field error (so an invalid format is a 422 naming
  ``asset_ids``); then the post counts once per billing period against scheduled_posts_monthly
  (``counted_at``, 402 quota_exceeded past it) and becomes ``scheduled``.
- A post can be edited, unscheduled or moved while it is a draft or scheduled; once a target is
  claimed the post is ``publishing`` and those are 409 conflict. PUT on a failed or canceled post
  makes it a draft again, its targets pending. Delete works in any status but publishing; links of
  automations that already have their published post are kept (C-043).
- Publish now sets ``publish_at`` to now and hands the pending targets to the publishing jobs
  (``publish_target`` by name, T7.3) after the commit.

Every change queues ``scheduled_post.updated`` (views.publish_updated); nothing here commits.
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.billing import UsageMetric
from socialhood.models.connections import SocialAccount
from socialhood.models.media import AssetPurpose, MediaAsset
from socialhood.models.publishing import (
    MIN_SCHEDULE_LEAD,
    ScheduledPostAsset,
    ScheduledPostStatus,
    ScheduledPostTarget,
    TargetStatus,
)
from socialhood.models.publishing import ScheduledPost as PostRow
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.repositories import scheduled_posts as repo
from socialhood.repositories import usage
from socialhood.schemas.publishing import (
    BulkScheduledPostRequest,
    BulkScheduledPostResult,
    BulkSkipped,
    ScheduledPost,
    ScheduledPostDraft,
    ScheduledPostList,
    ScheduledPostView,
    TargetIn,
)
from socialhood.services.conversations import decode_cursor, encode_cursor
from socialhood.services.scheduled_posts import rules, slots, views

log = get_logger(__name__)

P = ScheduledPostStatus
EDITABLE = (P.DRAFT, P.SCHEDULED)
RETRYABLE = (P.FAILED, P.CANCELED)  # PUT makes them drafts again (Edit and retry)
PUBLISHED = (P.PUBLISHED, P.PARTIALLY_PUBLISHED)
DIDNT_PUBLISH = "This post didn't publish. Edit it to try again."
DRAFT_NOT_MOVED = "This post is a draft. Schedule it instead."
NO_TIME = "Pick a time at least 5 minutes from now."


@dataclass(frozen=True)
class Env:
    """What every change needs besides the session."""

    deps: PlatformDeps
    now: datetime
    timezone: str = "UTC"


def _conflict(status: str, *, draft: str = rules.NOT_SCHEDULED) -> ApiError:
    if status == P.PUBLISHING:
        return ApiError("conflict", rules.PUBLISHING_STARTED)
    if status in PUBLISHED:
        return ApiError("conflict", rules.ALREADY_PUBLISHED)
    if status in RETRYABLE:
        return ApiError("conflict", DIDNT_PUBLISH)
    return ApiError("conflict", draft)


def utc(at: datetime) -> datetime:
    """A time without a zone is UTC (TR-API-02)."""
    return at.replace(tzinfo=UTC) if at.tzinfo is None else at.astimezone(UTC)


async def _locked(session: AsyncSession, scheduled_post_id: uuid.UUID) -> PostRow:
    post = await repo.get(session, scheduled_post_id, for_update=True)
    if post is None:
        raise ApiError("not_found")
    return post


async def _reload(session: AsyncSession, posts: Sequence[PostRow]) -> None:
    """Server-set columns (defaults, timestamps) back onto the loaded posts."""
    if posts:
        await session.flush()
        await session.execute(
            select(PostRow)
            .where(PostRow.id.in_([p.id for p in posts]))
            .execution_options(populate_existing=True)
        )


async def _changed(session: AsyncSession, post: PostRow, env: Env) -> ScheduledPost:
    await _reload(session, [post])
    [out] = await views.publish_updated(session, [post], deps=env.deps, now=env.now)
    return out


# ---------------------------------------------------------------- reads


async def list_posts(
    session: AsyncSession,
    *,
    view: ScheduledPostView,
    account_ids: Sequence[uuid.UUID] | None,
    cursor: str | None,
    limit: int,
) -> ScheduledPostList:
    """The List view's tabs (UX-SCR-04): scheduled soonest first; drafts by last edit; published
    and failed newest first."""
    rows = await repo.list_view(
        session,
        view=view,
        account_ids=account_ids,
        after=decode_cursor(cursor) if cursor else None,
        limit=limit + 1,
    )
    page = rows[:limit]
    return ScheduledPostList(
        items=await views.summaries(session, page),
        next_cursor=(
            encode_cursor(repo.view_time(view, page[-1]), page[-1].id)
            if len(rows) > limit
            else None
        ),
    )


async def get(session: AsyncSession, scheduled_post_id: uuid.UUID, env: Env) -> ScheduledPost:
    post = await repo.get(session, scheduled_post_id)
    if post is None:
        raise ApiError("not_found")
    return await views.post_out(session, post, deps=env.deps, now=env.now)


# ---------------------------------------------------------------- saving a draft


@dataclass(frozen=True)
class _Checked:
    accounts: dict[uuid.UUID, SocialAccount]
    assets: list[MediaAsset]


async def _check_body(session: AsyncSession, body: ScheduledPostDraft) -> _Checked:
    """Accounts are this workspace's and appear once; assets are its post uploads (images and
    videos) and appear once. Every problem is reported at once."""
    errors: list[FieldError] = []
    accounts = await repo.accounts_by_id(session, [t.social_account_id for t in body.targets])
    seen_accounts: set[uuid.UUID] = set()
    for i, target in enumerate(body.targets):
        if target.social_account_id not in accounts:
            errors.append(FieldError(f"targets.{i}", "Account not found."))
        elif target.social_account_id in seen_accounts:
            errors.append(FieldError(f"targets.{i}", "This account is already selected."))
        seen_accounts.add(target.social_account_id)
    found = await repo.assets_by_id(session, body.asset_ids)
    seen_assets: set[uuid.UUID] = set()
    for i, asset_id in enumerate(body.asset_ids):
        asset = found.get(asset_id)
        if asset is None:
            errors.append(FieldError(f"asset_ids.{i}", "This file wasn't found. Upload it again."))
        elif asset.purpose != AssetPurpose.POST or asset.resource_type not in ("image", "video"):
            errors.append(FieldError(f"asset_ids.{i}", "This file wasn't uploaded for a post."))
        elif asset_id in seen_assets:
            errors.append(FieldError(f"asset_ids.{i}", "This file is already in the post."))
        seen_assets.add(asset_id)
    if errors:
        raise ApiError("validation_error", errors=errors)
    return _Checked(accounts, [found[a] for a in body.asset_ids])


def _reset(target: ScheduledPostTarget) -> None:
    """A failed or canceled target, pending again (Edit and retry)."""
    target.status = TargetStatus.PENDING
    target.claimed_at = None
    target.attempts = 0
    target.poll_count = 0
    target.container_id = None
    target.child_container_ids = []
    target.platform_media_id = None
    target.permalink = None
    target.published_at = None
    target.error_code = None
    target.error_message = None
    target.first_comment_platform_id = None
    target.first_comment_error = None


async def _write_targets(
    session: AsyncSession, post: PostRow, targets: Sequence[TargetIn], *, reset: bool
) -> None:
    """The post's targets become the body's: kept accounts keep their row (new caption), others
    are removed or added."""
    existing = {t.social_account_id: t for t, _ in await repo.targets_for(session, [post.id])}
    wanted = {t.social_account_id: t for t in targets}
    await repo.delete_targets(
        session, [row.id for account, row in existing.items() if account not in wanted]
    )
    for account_id, target in wanted.items():
        override = target.caption_override or None
        row = existing.get(account_id)
        if row is None:
            session.add(
                ScheduledPostTarget(
                    scheduled_post_id=post.id,
                    social_account_id=account_id,
                    caption_override=override,
                    status=TargetStatus.PENDING,
                )
            )
            continue
        row.caption_override = override
        if reset and row.status != TargetStatus.PENDING:
            _reset(row)
    await session.flush()


async def _write(
    session: AsyncSession,
    post: PostRow,
    body: ScheduledPostDraft,
    checked: _Checked,
    *,
    now: datetime,
    reset: bool = False,
) -> None:
    post.caption = body.caption
    post.first_comment = body.first_comment or None
    post.publish_at = utc(body.publish_at) if body.publish_at else None
    post.format = rules.derive_format([a.resource_type for a in checked.assets])
    post.updated_at = now
    current = [row.media_asset_id for row, _ in await repo.assets_for(session, [post.id])]
    if current != list(body.asset_ids):
        await repo.replace_assets(session, post.id, body.asset_ids)
    await _write_targets(session, post, body.targets, reset=reset)


async def create(
    session: AsyncSession, body: ScheduledPostDraft, env: Env, *, user_id: uuid.UUID
) -> ScheduledPost:
    """F-13 New post: a draft, empty or pre-filled (a calendar click sends ``publish_at``)."""
    checked = await _check_body(session, body)
    post = PostRow(status=P.DRAFT, caption="", created_by_user_id=user_id)
    session.add(post)
    await session.flush()
    await _write(session, post, body, checked, now=env.now)
    return await _changed(session, post, env)


async def replace(
    session: AsyncSession, scheduled_post_id: uuid.UUID, body: ScheduledPostDraft, env: Env
) -> ScheduledPost:
    """PUT: autosave a draft; Update schedule (a scheduled post must still pass the checklist at
    its time, which must be set and at least 5 minutes away); Edit and retry (a failed or
    canceled post becomes a draft, its targets pending)."""
    post = await _locked(session, scheduled_post_id)
    if post.status not in EDITABLE and post.status not in RETRYABLE:
        raise _conflict(post.status)
    checked = await _check_body(session, body)
    if post.status == P.SCHEDULED:  # Update schedule: checked before anything is written
        draft = views.Draft(
            post_id=post.id,
            caption=body.caption,
            first_comment=body.first_comment or None,
            publish_at=utc(body.publish_at) if body.publish_at else None,
            targets=[
                (checked.accounts[t.social_account_id], t.caption_override or None)
                for t in body.targets
            ],
            assets=checked.assets,
        )
        await _require_ready(session, draft, env)
    retry = post.status in RETRYABLE
    if retry:  # a draft may lack a time or media (the schedulable check)
        post.status = P.DRAFT
        post.published_at = None
    await _write(session, post, body, checked, now=env.now, reset=retry)
    return await _changed(session, post, env)


async def _require_ready(
    session: AsyncSession, draft: views.Draft, env: Env, *, check_time: bool = True
) -> None:
    """422 with every failing checklist item, checked at the draft's time; a missing time is a
    failure too."""
    items = await views.check(session, draft, deps=env.deps, now=env.now, check_time=check_time)
    errors = rules.field_errors(items)
    if check_time and draft.publish_at is None:
        errors.append(FieldError("publish_at", NO_TIME))
    if errors:
        raise ApiError("validation_error", errors=errors)


# ---------------------------------------------------------------- lifecycle


async def _count(session: AsyncSession, post: PostRow, now: datetime) -> None:
    """scheduled_posts_monthly (§1.7): a post counts once per billing period (C-043), so
    unscheduling and scheduling again in the same period costs nothing. 402 quota_exceeded
    when the period's posts are used up."""
    metric = UsageMetric.SCHEDULED_POSTS
    limit = entitlement(await current_plan(session), "scheduled_posts_monthly")
    start, _ = await usage.ensure_counter(session, today=now.date(), limit=limit, metric=metric)
    if post.counted_at is not None and post.counted_at >= datetime.combine(
        start, time(0), tzinfo=UTC
    ):
        return
    if await usage.reserve(session, period_start=start, cost=1, metric=metric) is None:
        row = await usage.counter(session, start, metric=metric)
        allowed = row.limit if row is not None and row.limit is not None else limit
        raise ApiError("quota_exceeded", f"Your plan includes {allowed} scheduled posts a month.")
    post.counted_at = now


async def _schedule(
    session: AsyncSession, post: PostRow, at: datetime, env: Env, *, check_time: bool = True
) -> None:
    [loaded] = await views.load(session, [post])
    draft = dataclasses.replace(views.Draft.of(loaded), publish_at=at)
    await _require_ready(session, draft, env, check_time=check_time)
    await _count(session, post, env.now)
    post.publish_at = at
    post.status = P.SCHEDULED
    post.updated_at = env.now


async def schedule(
    session: AsyncSession, scheduled_post_id: uuid.UUID, publish_at: datetime, env: Env
) -> ScheduledPost:
    """F-13 Schedule (also a draft dropped on the calendar, and a scheduled post's new time)."""
    post = await _locked(session, scheduled_post_id)
    if post.status not in EDITABLE:
        raise _conflict(post.status)
    await _schedule(session, post, utc(publish_at), env)
    return await _changed(session, post, env)


async def queue(session: AsyncSession, scheduled_post_id: uuid.UUID, env: Env) -> ScheduledPost:
    """Add to queue (FR-PUB-09): the earliest free posting time shared by the post's accounts,
    then as Schedule."""
    post = await _locked(session, scheduled_post_id)
    if post.status not in EDITABLE:
        raise _conflict(post.status)
    [loaded] = await views.load(session, [post])
    at = await slots.queue_time(
        session,
        [account for _, account in loaded.targets],
        timezone=env.timezone,
        now=env.now,
        post_id=post.id,
    )
    await _schedule(session, post, at, env)
    return await _changed(session, post, env)


@dataclass(frozen=True)
class HandOver:
    """Targets to give the publishing jobs once the change is committed."""

    workspace_id: uuid.UUID
    target_ids: list[uuid.UUID]


async def publish_now(
    session: AsyncSession, scheduled_post_id: uuid.UUID, env: Env
) -> tuple[ScheduledPost, HandOver]:
    """F-13 Publish now: Schedule's checks without the 5-minute rule and ``publish_at`` = now.
    The caller commits, then calls ``hand_over``."""
    post = await _locked(session, scheduled_post_id)
    if post.status not in EDITABLE:
        raise _conflict(post.status)
    await _schedule(session, post, env.now, env, check_time=False)
    out = await _changed(session, post, env)
    pending = [
        t.id
        for t, _ in await repo.targets_for(session, [post.id])
        if t.status == TargetStatus.PENDING
    ]
    return out, HandOver(post.workspace_id, pending)


async def hand_over(handover: HandOver) -> int:
    """Enqueue ``publish_target`` (T7.3) for each pending target, by name, under the job
    catalogue's ``pub:{target_id}``; publish_target claims a pending target of a due post itself.
    A failed enqueue is logged: the post is due, so the 30-second dispatcher claims its pending
    targets on its next run. Returns how many were queued."""
    from socialhood.jobs.app import INTERACTIVE
    from socialhood.jobs.enqueue import enqueue_named

    queued = 0
    for target_id in handover.target_ids:
        try:
            queued += await enqueue_named(
                "publish_target",
                lane=INTERACTIVE,
                key=f"pub:{target_id}",
                target_id=str(target_id),
                workspace_id=str(handover.workspace_id),
            )
        except Exception:
            log.warning("publish_enqueue_failed", target_id=str(target_id))
    return queued


async def unschedule(
    session: AsyncSession, scheduled_post_id: uuid.UUID, env: Env
) -> ScheduledPost:
    """Back to draft, keeping its time (FR-PUB-04); a draft is returned as it is."""
    post = await _locked(session, scheduled_post_id)
    if post.status == P.DRAFT:
        return await views.post_out(session, post, deps=env.deps, now=env.now)
    if post.status != P.SCHEDULED:
        raise _conflict(post.status)
    post.status = P.DRAFT
    post.updated_at = env.now
    return await _changed(session, post, env)


def _check_move(at: datetime, now: datetime) -> None:
    if at < now + MIN_SCHEDULE_LEAD:
        raise ApiError("validation_error", errors=[FieldError("publish_at", rules.TIME_TOO_SOON)])


async def reschedule(
    session: AsyncSession, scheduled_post_id: uuid.UUID, publish_at: datetime, env: Env
) -> ScheduledPost:
    """A calendar move or "Move to…" (FR-PUB-08): a scheduled post to a time at least 5 minutes
    away. Drafts are scheduled with Schedule (409)."""
    post = await _locked(session, scheduled_post_id)
    if post.status != P.SCHEDULED:
        raise _conflict(post.status, draft=DRAFT_NOT_MOVED)
    at = utc(publish_at)
    _check_move(at, env.now)
    post.publish_at = at
    post.updated_at = env.now
    return await _changed(session, post, env)


async def duplicate(
    session: AsyncSession, scheduled_post_id: uuid.UUID, env: Env, *, user_id: uuid.UUID
) -> ScheduledPost:
    """FR-PUB-14: a new draft with the same accounts, captions, media and first comment, without
    a time or automations."""
    source = await repo.get(session, scheduled_post_id)
    if source is None:
        raise ApiError("not_found")
    [loaded] = await views.load(session, [source])
    copy = PostRow(
        status=P.DRAFT,
        format=source.format,
        caption=source.caption,
        first_comment=source.first_comment,
        created_by_user_id=user_id,
    )
    session.add(copy)
    await session.flush()
    session.add_all(
        ScheduledPostAsset(
            scheduled_post_id=copy.id, media_asset_id=asset.id, position=row.position
        )
        for row, asset in loaded.assets
    )
    session.add_all(
        ScheduledPostTarget(
            scheduled_post_id=copy.id,
            social_account_id=target.social_account_id,
            caption_override=target.caption_override,
            status=TargetStatus.PENDING,
        )
        for target, _ in loaded.targets
    )
    return await _changed(session, copy, env)


async def delete(session: AsyncSession, scheduled_post_id: uuid.UUID) -> None:
    """Any status but publishing (409). A published post stays on Instagram and in Posts, and
    automations already answering its comments keep it (C-043)."""
    post = await _locked(session, scheduled_post_id)
    if post.status == P.PUBLISHING:
        raise ApiError("conflict", rules.PUBLISHING_STARTED)
    await _delete(session, post)


async def _delete(session: AsyncSession, post: PostRow) -> None:
    await repo.keep_published_links(session, post.id)
    await repo.delete_posts(session, [post.id])


# ---------------------------------------------------------------- bulk (FR-PUB-14)


def _skip(post: PostRow, code: str, message: str) -> BulkSkipped:
    return BulkSkipped(id=post.id, code=code, message=message)


def _conflict_skip(post: PostRow) -> BulkSkipped:
    error = _conflict(post.status)
    return _skip(post, error.code, error.detail or "")


async def bulk(
    session: AsyncSession, body: BulkScheduledPostRequest, env: Env
) -> BulkScheduledPostResult:
    """Shift, unschedule or delete several posts. An id that isn't this workspace's makes the
    whole request 404; each post the action can't apply to is skipped with the reason."""
    if body.action == "shift" and not body.shift_minutes:
        raise ApiError(
            "validation_error",
            errors=[FieldError("shift_minutes", "Say how many minutes to move the posts.")],
        )
    ids = list(dict.fromkeys(body.ids))
    locked = {p.id: p for p in await repo.lock_many(session, ids)}
    if len(locked) != len(ids):
        raise ApiError("not_found")
    changed: list[PostRow] = []
    untouched: list[PostRow] = []
    deleted: list[uuid.UUID] = []
    skipped: list[BulkSkipped] = []
    for post in (locked[i] for i in ids):
        if body.action == "delete":
            if post.status == P.PUBLISHING:
                skipped.append(_conflict_skip(post))
            else:
                await _delete(session, post)
                deleted.append(post.id)
        elif body.action == "unschedule":
            if post.status == P.DRAFT:
                untouched.append(post)
            elif post.status == P.SCHEDULED:
                post.status = P.DRAFT
                post.updated_at = env.now
                changed.append(post)
            else:
                skipped.append(_conflict_skip(post))
        elif post.status != P.SCHEDULED or post.publish_at is None:
            skipped.append(_conflict_skip(post))
        else:
            at = post.publish_at + timedelta(minutes=body.shift_minutes or 0)
            if at < env.now + MIN_SCHEDULE_LEAD:
                skipped.append(
                    _skip(
                        post,
                        "validation_error",
                        "The new time would be less than 5 minutes from now.",
                    )
                )
            else:
                post.publish_at = at
                post.updated_at = env.now
                changed.append(post)
    await _reload(session, changed)
    if changed:
        await views.publish_updated(session, changed, deps=env.deps, now=env.now)
    by_id = {p.id: p for p in changed + untouched}
    return BulkScheduledPostResult(
        updated=await views.summaries(session, [by_id[i] for i in ids if i in by_id]),
        deleted_ids=deleted,
        skipped=skipped,
    )
