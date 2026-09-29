"""Comment intake (F-12, T4.4): a comment event becomes a stored comment and, when the account has
comment automations, a ``run_automation("comment", id)``.

Runs in the account's workspace scope, in the webhook's transaction; never commits.

- The account's own comments are skipped (its public replies come back as comment events): the
  author is the account by id (the Instagram user id or the app-scoped id) or by username.
- A post we have not synced is fetched and stored, and ``posts.on_new_media_item`` links "next
  post" automations to it (FR-AUT-18). A temporary platform error fails the event, so the webhook
  job retries it; if Instagram refuses, the post is stored from what the event says and is not
  offered to next-post automations (its publish time is unknown).
- The commenter becomes a contact by their IGSID (``from.id``, the same id their DMs carry; T0.9
  item 5), with the username the event gives.
- The comment is inserted once (a replayed event stores nothing and triggers nothing) with
  ``analysis_status`` pending; analyze_comments reads it (T6.2). Replies keep their parent
  comment's id.
- A new comment adds one to its post's ``comment_stats.total`` and queues comment.created and
  post.updated (T6.1, TR-RT-03), so the Comments grid counts it live.
- The backfill on connect (T6.1, FR-CMT-01) takes comments read from Instagram through this same
  intake with ``backfill=True``: stored the same way (with their like count and hidden state), but
  no automation runs on them and no per-comment event is queued; the backfill recounts each post
  and publishes post.updated instead.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.automations import Comment
from socialhood.models.connections import SocialAccount
from socialhood.models.media import MediaItem
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import PlatformComment, PlatformMedia
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.events import InboundComment
from socialhood.platforms.registry import adapter_for
from socialhood.repositories import comment_analyses as stats
from socialhood.repositories import comments as repo
from socialhood.repositories import ingest as rows
from socialhood.services.automations import posts, runtime
from socialhood.services.comments import views

log = get_logger(__name__)


@dataclass(frozen=True)
class Intake:
    comment: Comment | None
    ignored: str | None = None  # why nothing was stored


def is_own(acct: SocialAccount, event: InboundComment) -> bool:
    own_ids = {i for i in (acct.platform_account_id, acct.app_scoped_id) if i}
    if event.author_ref in own_ids:
        return True
    return bool(
        acct.username
        and event.author_username
        and acct.username.casefold() == event.author_username.casefold()
    )


async def intake(
    session: AsyncSession,
    acct: SocialAccount,
    event: InboundComment,
    *,
    deps: Callable[[], PlatformDeps],
    now: datetime | None = None,
    backfill: bool = False,
) -> Intake:
    """``deps`` is called only when a post has to be fetched. ``backfill``: a comment read from
    the platform after connect (no automation, no event; see the module docstring)."""
    now = now or datetime.now(UTC)
    if is_own(acct, event):
        return Intake(None, "the account's own comment")
    item = await repo.find_media_item(session, acct.id, event.media_id)
    if item is None:
        item = await _store_post(session, acct, event, deps=deps(), now=now)
    contact, _ = await rows.get_or_create_contact(
        session,
        social_account_id=acct.id,
        platform_user_id=event.author_ref,
        first_seen_at=event.occurred_at,
    )
    if event.author_username and contact.username != event.author_username:
        contact.username = event.author_username  # the newest we know
    values: dict[str, Any] = {
        "social_account_id": acct.id,
        "media_item_id": item.id,
        "contact_id": contact.id,
        "platform_comment_id": event.platform_comment_id,
        "parent_platform_comment_id": event.parent_id,
        "author_platform_user_id": event.author_ref,
        "author_username": event.author_username,
        "text": event.text,
        "commented_at": event.occurred_at,
    }
    if isinstance(event, PlatformComment):  # read from the platform: what only a read returns
        values["like_count"] = event.like_count
        values["hidden"] = event.hidden
    comment = await repo.insert_comment(session, values)
    if comment is None:
        await session.flush()
        return Intake(None, "comment already stored")
    await session.flush()
    if backfill:
        return Intake(comment)
    await runtime.enqueue_for_comment(session, comment)
    views.queue_comment(
        session,
        comment.workspace_id,
        views.comment_out(comment, None, profile_picture_url=contact.profile_picture_url),
        created=True,
    )
    # Last: the post's row lock is held until the caller commits.
    counted = await stats.bump_total(session, item.id)
    if counted is not None:
        views.queue_post(session, counted)
    return Intake(comment)


async def _store_post(
    session: AsyncSession,
    acct: SocialAccount,
    event: InboundComment,
    *,
    deps: PlatformDeps,
    now: datetime,
) -> MediaItem:
    fetched: PlatformMedia | None = None
    try:
        fetched = await adapter_for(acct, deps).get_media(acct, event.media_id)
    except PlatformError as error:
        if error.retryable:
            raise
        log.warning("comment_post_unavailable", account_id=str(acct.id), error_code=error.code)
    media = fetched or PlatformMedia(
        platform_media_id=event.media_id,
        media_type="image",
        caption=None,
        media_url=None,
        thumbnail_url=None,
        permalink=None,
        posted_at=event.occurred_at,
    )
    item = await repo.insert_media_item(
        session,
        social_account_id=acct.id,
        media=media,
        synced_at=now if fetched is not None else None,
    )
    if item is None:  # post sync stored it meanwhile
        stored = await repo.find_media_item(session, acct.id, event.media_id)
        assert stored is not None
        return stored
    if fetched is not None:
        await posts.on_new_media_item(session, item)
    return item
