"""What the API and ``scheduled_post.updated`` show of a post (§5.10 ScheduledPost as extended by
C-043; FR-PUB-06, FR-PUB-10, FR-PUB-11, FR-AUT-18, TR-RT-03).

``summaries`` builds the List view's, the calendar's and bulk results' ScheduledPostSummary;
``posts_out`` / ``post_out`` the composer's ScheduledPost with its assets, linked automations and
checklist. ``publish_updated`` builds posts and queues ``scheduled_post.updated`` with each for
the caller's commit (``realtime.events.commit_and_publish``). The publish jobs (T7.3) can build
their events with ``post_out(session, post)`` / ``publish_updated(session, posts)``: without
``deps`` the worker's are used (capabilities read settings only). Every function reads in the
caller's workspace scope and writes nothing.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.media.editor.spec import EditSpec
from socialhood.models.connections import SocialAccount
from socialhood.models.media import MediaAsset
from socialhood.models.publishing import (
    DEFAULT_PUBLISHING_LIMIT,
    ScheduledPostAsset,
    ScheduledPostTarget,
    TargetStatus,
)
from socialhood.models.publishing import ScheduledPost as PostRow
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.realtime import events
from socialhood.repositories import scheduled_posts as repo
from socialhood.schemas.inbox import ErrorInfo
from socialhood.schemas.publishing import (
    ChecklistItem,
    FirstCommentResult,
    LinkedAutomation,
    PostAsset,
    ScheduledPost,
    ScheduledPostSummary,
)
from socialhood.schemas.publishing import ScheduledPostTarget as TargetOut
from socialhood.services.scheduled_posts import rules

# Instagram's 24-hour limit on published posts. The account's own quota needs a platform call
# (T7.3 reads it before publishing); the checklist and the right rail use the documented default
# (C-043). A module name, so tests can lower it.
PUBLISHING_LIMIT = DEFAULT_PUBLISHING_LIMIT
DAY = timedelta(hours=24)
THUMBNAIL = "c_limit,w_480,q_auto"  # the List view's 48 px and the calendar's 24 px thumbnails


@dataclass(frozen=True)
class Loaded:
    post: PostRow
    assets: list[tuple[ScheduledPostAsset, MediaAsset]]
    targets: list[tuple[ScheduledPostTarget, SocialAccount]]


async def load(session: AsyncSession, posts: Sequence[PostRow]) -> list[Loaded]:
    ids = [p.id for p in posts]
    assets: dict[uuid.UUID, list[tuple[ScheduledPostAsset, MediaAsset]]] = defaultdict(list)
    for asset_row, asset in await repo.assets_for(session, ids):
        assets[asset_row.scheduled_post_id].append((asset_row, asset))
    targets: dict[uuid.UUID, list[tuple[ScheduledPostTarget, SocialAccount]]] = defaultdict(list)
    for target, account in await repo.targets_for(session, ids):
        targets[target.scheduled_post_id].append((target, account))
    return [Loaded(p, assets[p.id], targets[p.id]) for p in posts]


# ---------------------------------------------------------------- pieces


def thumbnail_url(asset: MediaAsset) -> str | None:
    """A small JPEG of the upload: the image itself, or a video's first frame (Cloudinary makes
    one when a video is asked for as .jpg)."""
    url = asset.secure_url
    if not url:
        return None
    head, sep, tail = url.partition("/upload/")
    if not sep:
        return url if asset.resource_type == "image" else None
    last = tail.rsplit("/", 1)[-1]
    stem = tail[: -(len(last.rsplit(".", 1)[-1]) + 1)] if "." in last else tail
    transformation = THUMBNAIL if asset.resource_type == "image" else f"so_0,{THUMBNAIL}"
    return f"{head}/upload/{transformation}/{stem}.jpg"


def asset_out(row: ScheduledPostAsset, asset: MediaAsset) -> PostAsset:
    """The item with its edit (P7b); its render is filled by TB.4 (the post's renders load in one
    query with the assets)."""
    return PostAsset(
        id=asset.id,
        public_id=asset.public_id,
        resource_type="video" if asset.resource_type == "video" else "image",
        url=asset.secure_url or "",
        thumbnail_url=thumbnail_url(asset),
        width=asset.width,
        height=asset.height,
        duration_s=asset.duration_s,
        position=row.position,
        edit=EditSpec.model_validate(row.edit_spec) if row.edit_spec is not None else None,
    )


def _first_comment(target: ScheduledPostTarget, first_comment: str | None) -> FirstCommentResult:
    if target.first_comment_platform_id:
        return FirstCommentResult(
            status="posted", platform_comment_id=target.first_comment_platform_id
        )
    if target.first_comment_error:
        return FirstCommentResult(status="failed", error=target.first_comment_error)
    return FirstCommentResult(status="pending")


def target_out(
    target: ScheduledPostTarget, first_comment: str | None, post_id: uuid.UUID | None
) -> TargetOut:
    published = target.status == TargetStatus.PUBLISHED
    return TargetOut.model_validate(
        {
            "social_account_id": target.social_account_id,
            "caption_override": target.caption_override,
            "status": target.status,
            "platform_media_id": target.platform_media_id,
            "permalink": target.permalink,
            "post_id": post_id,
            "published_at": target.published_at,
            "error": (
                ErrorInfo(code=target.error_code, message=target.error_message or "")
                if target.error_code
                else None
            ),
            "first_comment": (
                _first_comment(target, first_comment) if first_comment and published else None
            ),
        }
    )


def _summary(loaded: Loaded, items: dict[uuid.UUID, uuid.UUID]) -> ScheduledPostSummary:
    post = loaded.post
    first = loaded.assets[0] if loaded.assets else None
    return ScheduledPostSummary.model_validate(
        {
            "id": post.id,
            "status": post.status,
            "format": post.format,
            "caption": post.caption,
            "publish_at": post.publish_at,
            "published_at": post.published_at,
            "thumbnail_url": thumbnail_url(first[1]) if first else None,
            "asset_count": len(loaded.assets),
            "targets": [
                target_out(t, post.first_comment, items.get(t.id)) for t, _ in loaded.targets
            ],
            "created_at": post.created_at,
            "updated_at": post.updated_at,
        }
    )


async def _items(session: AsyncSession, loaded: Sequence[Loaded]) -> dict[uuid.UUID, uuid.UUID]:
    published = [
        t.id for one in loaded for t, _ in one.targets if t.status == TargetStatus.PUBLISHED
    ]
    return await repo.published_items(session, published)


async def summaries(session: AsyncSession, posts: Sequence[PostRow]) -> list[ScheduledPostSummary]:
    loaded = await load(session, posts)
    items = await _items(session, loaded)
    return [_summary(one, items) for one in loaded]


# ---------------------------------------------------------------- the checklist's inputs


def can_publish(account: SocialAccount, deps: PlatformDeps) -> bool:
    """Capability.PUBLISH (TR-PL-11); an account no adapter serves can't."""
    try:
        return Capability.PUBLISH in adapter_for(account, deps).capabilities_for(account)
    except PlatformError:
        return False


@dataclass(frozen=True)
class Draft:
    """What the checklist looks at: a saved post (``of``) or the body about to replace it
    (Update schedule is checked before anything is written)."""

    post_id: uuid.UUID
    caption: str
    first_comment: str | None
    publish_at: datetime | None
    targets: Sequence[tuple[SocialAccount, str | None]]  # the account and its own caption
    assets: Sequence[MediaAsset]

    @classmethod
    def of(cls, loaded: Loaded) -> Draft:
        post = loaded.post
        return cls(
            post_id=post.id,
            caption=post.caption,
            first_comment=post.first_comment,
            publish_at=post.publish_at,
            targets=[(account, target.caption_override) for target, account in loaded.targets],
            assets=[asset for _, asset in loaded.assets],
        )


async def recent_posts(
    session: AsyncSession, drafts: Sequence[Draft], *, now: datetime
) -> dict[tuple[uuid.UUID, uuid.UUID], int]:
    """(post id, account id) -> the account's other posts published or due in the 24 hours up to
    the post's time (now for a post without one): FR-PUB-10's publishing limit."""
    at = {d.post_id: d.publish_at or now for d in drafts}
    accounts = {a.id for d in drafts for a, _ in d.targets}
    if not accounts:
        return {}
    rows = await repo.planned(
        session, list(accounts), start=min(at.values()) - DAY, end=max(at.values())
    )
    counts: dict[tuple[uuid.UUID, uuid.UUID], int] = defaultdict(int)
    for draft in drafts:
        when = at[draft.post_id]
        mine = {a.id for a, _ in draft.targets}
        for row in rows:
            if (
                row.social_account_id in mine
                and row.scheduled_post_id != draft.post_id
                and when - DAY < row.at <= when
            ):
                counts[(draft.post_id, row.social_account_id)] += 1
    return counts


def facts(
    draft: Draft, *, deps: PlatformDeps, recent: dict[tuple[uuid.UUID, uuid.UUID], int]
) -> rules.PostFacts:
    return rules.PostFacts(
        targets=[
            rules.TargetFacts(
                handle=rules.handle(account.username, account.display_name),
                status=account.status,
                can_publish=can_publish(account, deps),
                caption_override=override,
                recent_posts=recent.get((draft.post_id, account.id), 0),
            )
            for account, override in draft.targets
        ],
        assets=[
            rules.asset_facts(
                asset.resource_type,
                asset.format,
                asset.public_id,
                asset.bytes,
                asset.width,
                asset.height,
                asset.duration_s,
            )
            for asset in draft.assets
        ],
        caption=draft.caption,
        first_comment=draft.first_comment,
        publish_at=draft.publish_at,
    )


async def check(
    session: AsyncSession,
    draft: Draft,
    *,
    deps: PlatformDeps,
    now: datetime,
    check_time: bool = True,
) -> list[ChecklistItem]:
    """The checklist of ``draft`` at its ``publish_at`` (Schedule, Queue and Publish now check
    the time they are about to set)."""
    recent = await recent_posts(session, [draft], now=now)
    return rules.checklist(
        facts(draft, deps=deps, recent=recent),
        now=now,
        publishing_limit=PUBLISHING_LIMIT,
        check_time=check_time,
    )


# ---------------------------------------------------------------- the composer's post


def _worker_deps() -> PlatformDeps:
    """The worker's (jobs/runtime), as services/sending does: the publish jobs build a post
    without passing their own. Capabilities read settings only; no request is made."""
    from socialhood.jobs.runtime import runtime
    from socialhood.platforms.deps import deps_from

    rt = runtime()
    return deps_from(rt.http, rt.settings)


async def posts_out(
    session: AsyncSession,
    posts: Sequence[PostRow],
    *,
    deps: PlatformDeps | None = None,
    now: datetime | None = None,
) -> list[ScheduledPost]:
    """The composer's posts, in the order given. ``deps`` defaults to the worker's and ``now``
    to the current time (the publish jobs' events)."""
    deps = deps or _worker_deps()
    now = now or datetime.now(UTC)
    loaded = await load(session, posts)
    items = await _items(session, loaded)
    drafts = [Draft.of(one) for one in loaded]
    recent = await recent_posts(session, drafts, now=now)
    automations: dict[uuid.UUID, list[LinkedAutomation]] = defaultdict(list)
    for post_id, automation in await repo.linked_automations(session, [p.id for p in posts]):
        automations[post_id].append(
            LinkedAutomation.model_validate(
                {
                    "id": automation.id,
                    "name": automation.name,
                    "status": automation.status,
                    "trigger": automation.trigger,
                }
            )
        )
    out: list[ScheduledPost] = []
    for one, draft in zip(loaded, drafts, strict=True):
        post = one.post
        checklist = rules.checklist(
            facts(draft, deps=deps, recent=recent), now=now, publishing_limit=PUBLISHING_LIMIT
        )
        summary = _summary(one, items)
        out.append(
            ScheduledPost(
                **summary.model_dump(),
                first_comment=post.first_comment,
                assets=[asset_out(row, asset) for row, asset in one.assets],
                automations=automations[post.id],
                checklist=checklist,
                ready=all(item.ok for item in checklist),
                created_by_user_id=post.created_by_user_id,
            )
        )
    return out


async def post_out(
    session: AsyncSession,
    post: PostRow,
    *,
    deps: PlatformDeps | None = None,
    now: datetime | None = None,
) -> ScheduledPost:
    """One post as GET …/scheduled-posts/{id} and ``scheduled_post.updated`` show it (C-043):
    assets, targets with their results, linked automations and the checklist."""
    [out] = await posts_out(session, [post], deps=deps, now=now)
    return out


def queue_updated(session: AsyncSession, workspace_id: uuid.UUID, out: ScheduledPost) -> None:
    """``scheduled_post.updated`` with the post, published when the caller commits."""
    events.queue(
        session,
        workspace_id,
        "scheduled_post.updated",
        {"scheduled_post": out.model_dump(mode="json")},
    )


async def publish_updated(
    session: AsyncSession,
    posts: Sequence[PostRow],
    *,
    deps: PlatformDeps | None = None,
    now: datetime | None = None,
) -> list[ScheduledPost]:
    """Build each post and queue its ``scheduled_post.updated``; returns the posts built."""
    await session.flush()
    out = await posts_out(session, posts, deps=deps, now=now)
    for post, one in zip(posts, out, strict=True):
        queue_updated(session, post.workspace_id, one)
    return out
