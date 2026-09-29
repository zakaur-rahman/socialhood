"""Publishing (§2.15; F-13, FR-PUB-01, FR-PUB-04, FR-PUB-08…12, FR-PUB-14, UX-SCR-04, UX-SCR-13,
UX-SCR-14): scheduled posts and their lifecycle, the content calendar, weekly posting times and
hashtag groups. Owners and admins.

Every change to a post publishes scheduled_post.updated with the ``ScheduledPost`` (TR-RT-03). An
unknown or another workspace's post, account or group is 404 not_found. Validation failures are
422 validation_error with one FieldError per problem, named as in schemas/publishing.py (the
checklist uses the same names). A post that is publishing, published or partly published can't be
edited, moved or unscheduled, and one that is publishing can't be deleted: 409 conflict
("Publishing started"). Scheduling (schedule, queue, publish now) is gated by
scheduled_posts_monthly: 402 quota_exceeded ("Your plan includes N scheduled posts a month."); a
post counts once per billing period.

The rules are in services/scheduled_posts/ (T7.1); publishing itself (the dispatcher and the
publish jobs) is T7.3.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from socialhood.auth.deps import Admin, Session, WorkspaceContext
from socialhood.platforms.deps import deps_from
from socialhood.realtime.events import commit_and_publish
from socialhood.schemas.publishing import (
    BulkScheduledPostRequest,
    BulkScheduledPostResult,
    Calendar,
    CalendarLayer,
    HashtagGroup,
    HashtagGroupCreate,
    HashtagGroupList,
    HashtagGroupPatch,
    PostingSlots,
    PostingSlotsUpdate,
    ScheduledPost,
    ScheduledPostDraft,
    ScheduledPostList,
    ScheduledPostView,
    ScheduleRequest,
)
from socialhood.services.scheduled_posts import calendar as calendar_service
from socialhood.services.scheduled_posts import hashtag_groups, posts, slots

router = APIRouter(prefix="/v1/w/{wid}", tags=["publishing"])


def _env(request: Request, ctx: WorkspaceContext) -> posts.Env:
    return posts.Env(
        deps=deps_from(request.app.state.http, request.app.state.settings),
        now=datetime.now(UTC),
        timezone=ctx.workspace.timezone,
    )


# ---------------------------------------------------------------- scheduled posts


@router.get("/scheduled-posts", operation_id="list_scheduled_posts")
async def list_scheduled_posts(
    ctx: Admin,
    session: Session,
    view: Annotated[ScheduledPostView, Query()] = "scheduled",
    account_ids: Annotated[list[uuid.UUID] | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ScheduledPostList:
    """The List view's tabs (UX-SCR-04; orders in ``ScheduledPostView``). ``account_ids`` keeps
    posts with a target on any of those accounts."""
    return await posts.list_posts(
        session, view=view, account_ids=account_ids, cursor=cursor, limit=limit
    )


@router.post("/scheduled-posts", status_code=201, operation_id="create_scheduled_post")
async def create_scheduled_post(
    request: Request, body: ScheduledPostDraft, ctx: Admin, session: Session
) -> ScheduledPost:
    """New post (F-13): a draft, empty or pre-filled (a calendar click sends ``publish_at``)."""
    out = await posts.create(session, body, _env(request, ctx), user_id=ctx.user.id)
    await commit_and_publish(session, request.app.state.redis)
    return out


@router.post("/scheduled-posts/bulk", operation_id="bulk_update_scheduled_posts")
async def bulk_update_scheduled_posts(
    request: Request, body: BulkScheduledPostRequest, ctx: Admin, session: Session
) -> BulkScheduledPostResult:
    """FR-PUB-14: shift, unschedule or delete several posts. Any id that is not this workspace's
    makes the whole request 404 and changes nothing. Otherwise each post the action can't apply to
    is reported in ``skipped`` and the rest are changed; 422 when ``shift`` comes without a
    non-zero ``shift_minutes``. Unscheduling a draft leaves it as it is (in ``updated``)."""
    out = await posts.bulk(session, body, _env(request, ctx))
    await commit_and_publish(session, request.app.state.redis)
    return out


@router.get("/scheduled-posts/{scheduled_post_id}", operation_id="get_scheduled_post")
async def get_scheduled_post(
    request: Request, scheduled_post_id: uuid.UUID, ctx: Admin, session: Session
) -> ScheduledPost:
    """The composer's post with its checklist (FR-PUB-10) and linked automations."""
    return await posts.get(session, scheduled_post_id, _env(request, ctx))


@router.put("/scheduled-posts/{scheduled_post_id}", operation_id="replace_scheduled_post")
async def replace_scheduled_post(
    request: Request,
    scheduled_post_id: uuid.UUID,
    body: ScheduledPostDraft,
    ctx: Admin,
    session: Session,
) -> ScheduledPost:
    """Replace the editable post (autosave, Update schedule, Edit and retry): the format is
    derived from the assets again and the checklist recomputed. Rules in ``ScheduledPostDraft``."""
    out = await posts.replace(session, scheduled_post_id, body, _env(request, ctx))
    await commit_and_publish(session, request.app.state.redis)
    return out


@router.delete(
    "/scheduled-posts/{scheduled_post_id}", status_code=204, operation_id="delete_scheduled_post"
)
async def delete_scheduled_post(
    scheduled_post_id: uuid.UUID, ctx: Admin, session: Session
) -> Response:
    """Delete a post in any status but publishing (409). A published post stays on Instagram and
    in Posts; automations linked to it keep their post (C-043)."""
    await posts.delete(session, scheduled_post_id)
    await session.commit()
    return Response(status_code=204)


@router.post("/scheduled-posts/{scheduled_post_id}/schedule", operation_id="schedule_post")
async def schedule_post(
    request: Request,
    scheduled_post_id: uuid.UUID,
    body: ScheduleRequest,
    ctx: Admin,
    session: Session,
) -> ScheduledPost:
    """F-13 Schedule (also a draft dropped on the calendar): the checklist must pass and
    ``publish_at`` be at least 5 minutes away (422 with every failing field); then the targets are
    pending and the post is scheduled. 402 quota_exceeded past scheduled_posts_monthly. A
    scheduled post takes the new time the same way."""
    out = await posts.schedule(session, scheduled_post_id, body.publish_at, _env(request, ctx))
    await commit_and_publish(session, request.app.state.redis)
    return out


@router.post("/scheduled-posts/{scheduled_post_id}/unschedule", operation_id="unschedule_post")
async def unschedule_post(
    request: Request, scheduled_post_id: uuid.UUID, ctx: Admin, session: Session
) -> ScheduledPost:
    """Back to draft, keeping its time (FR-PUB-04). A draft is returned as it is."""
    out = await posts.unschedule(session, scheduled_post_id, _env(request, ctx))
    await commit_and_publish(session, request.app.state.redis)
    return out


@router.post(
    "/scheduled-posts/{scheduled_post_id}/publish-now",
    status_code=202,
    operation_id="publish_post_now",
)
async def publish_post_now(
    request: Request, scheduled_post_id: uuid.UUID, ctx: Admin, session: Session
) -> ScheduledPost:
    """F-13 Publish now: the Schedule checks without the 5-minute rule, ``publish_at`` = now, and
    publish_target is enqueued for every target at once (202; scheduled_post.updated follows
    each step). 402 quota_exceeded past scheduled_posts_monthly."""
    out, handover = await posts.publish_now(session, scheduled_post_id, _env(request, ctx))
    await commit_and_publish(session, request.app.state.redis)
    await posts.hand_over(handover)
    return out


@router.post("/scheduled-posts/{scheduled_post_id}/reschedule", operation_id="reschedule_post")
async def reschedule_post(
    request: Request,
    scheduled_post_id: uuid.UUID,
    body: ScheduleRequest,
    ctx: Admin,
    session: Session,
) -> ScheduledPost:
    """A calendar move or "Move to…" (FR-PUB-08): a scheduled post to ``publish_at``, at least 5
    minutes away (422 on ``publish_at``: "Pick a time at least 5 minutes from now."). A draft is
    409 (drafts are scheduled with /schedule)."""
    out = await posts.reschedule(session, scheduled_post_id, body.publish_at, _env(request, ctx))
    await commit_and_publish(session, request.app.state.redis)
    return out


@router.post("/scheduled-posts/{scheduled_post_id}/queue", operation_id="queue_post")
async def queue_post(
    request: Request, scheduled_post_id: uuid.UUID, ctx: Admin, session: Session
) -> ScheduledPost:
    """Add to queue (FR-PUB-09): schedule at the earliest time that is a free posting time of
    every selected account (C-043), then as /schedule. 422 on ``targets.{i}`` when an account has
    no posting times, or on ``targets`` when the accounts share no free time in the next 8
    weeks."""
    out = await posts.queue(session, scheduled_post_id, _env(request, ctx))
    await commit_and_publish(session, request.app.state.redis)
    return out


@router.post(
    "/scheduled-posts/{scheduled_post_id}/duplicate",
    status_code=201,
    operation_id="duplicate_scheduled_post",
)
async def duplicate_scheduled_post(
    request: Request, scheduled_post_id: uuid.UUID, ctx: Admin, session: Session
) -> ScheduledPost:
    """FR-PUB-14: a new draft with the same accounts, captions, media and first comment, without a
    time or automations. Any post can be duplicated."""
    out = await posts.duplicate(session, scheduled_post_id, _env(request, ctx), user_id=ctx.user.id)
    await commit_and_publish(session, request.app.state.redis)
    return out


# ---------------------------------------------------------------- calendar


@router.get("/calendar", operation_id="get_calendar")
async def get_calendar(
    request: Request,
    ctx: Admin,
    session: Session,
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
    account_ids: Annotated[list[uuid.UUID] | None, Query()] = None,
    layers: Annotated[list[CalendarLayer] | None, Query()] = None,
) -> Calendar:
    """FR-PUB-08: posts, scheduled DMs (the Messages layer) and free posting times from ``from``
    to ``to`` (dates in the workspace time zone, both included, at most 42 days: else 422 on
    ``to``). ``account_ids`` narrows every layer; ``layers`` defaults to all three."""
    env = _env(request, ctx)
    return await calendar_service.calendar(
        session,
        start_day=start,
        end_day=end,
        account_ids=account_ids,
        layers=layers,
        deps=env.deps,
        timezone=env.timezone,
        now=env.now,
    )


# ---------------------------------------------------------------- posting times


@router.get("/social-accounts/{account_id}/posting-slots", operation_id="get_posting_slots")
async def get_posting_slots(account_id: uuid.UUID, ctx: Admin, session: Session) -> PostingSlots:
    """The account's weekly posting times and its next 5 free times (UX-SCR-14)."""
    return await slots.posting_slots(
        session, account_id, timezone=ctx.workspace.timezone, now=datetime.now(UTC)
    )


@router.put("/social-accounts/{account_id}/posting-slots", operation_id="replace_posting_slots")
async def replace_posting_slots(
    request: Request,
    account_id: uuid.UUID,
    body: PostingSlotsUpdate,
    ctx: Admin,
    session: Session,
) -> PostingSlots:
    """Replace the weekly times (FR-PUB-09). An account that can't publish (WhatsApp) is 409
    capability_unavailable; a time with seconds is 422 on ``slots.{i}.local_time``."""
    env = _env(request, ctx)
    out = await slots.replace_posting_slots(
        session, account_id, body, deps=env.deps, timezone=env.timezone, now=env.now
    )
    await session.commit()
    return out


# ---------------------------------------------------------------- hashtag groups


@router.get("/hashtag-groups", operation_id="list_hashtag_groups")
async def list_hashtag_groups(ctx: Admin, session: Session) -> HashtagGroupList:
    """FR-PUB-12: every group, by name."""
    return await hashtag_groups.list_groups(session)


@router.post("/hashtag-groups", status_code=201, operation_id="create_hashtag_group")
async def create_hashtag_group(
    body: HashtagGroupCreate, ctx: Admin, session: Session
) -> HashtagGroup:
    """Save a group (rules in ``HashtagGroupCreate``)."""
    out = await hashtag_groups.create(session, body)
    await session.commit()
    return out


@router.patch("/hashtag-groups/{hashtag_group_id}", operation_id="update_hashtag_group")
async def update_hashtag_group(
    hashtag_group_id: uuid.UUID, body: HashtagGroupPatch, ctx: Admin, session: Session
) -> HashtagGroup:
    """Rename a group or replace its hashtags."""
    out = await hashtag_groups.update(session, hashtag_group_id, body, now=datetime.now(UTC))
    await session.commit()
    return out


@router.delete(
    "/hashtag-groups/{hashtag_group_id}", status_code=204, operation_id="delete_hashtag_group"
)
async def delete_hashtag_group(
    hashtag_group_id: uuid.UUID, ctx: Admin, session: Session
) -> Response:
    """Delete a group; captions that used it keep their hashtags."""
    await hashtag_groups.delete(session, hashtag_group_id)
    await session.commit()
    return Response(status_code=204)
