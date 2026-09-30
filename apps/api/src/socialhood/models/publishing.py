"""Publishing (§5.7; FR-PUB-01…14, F-13): scheduled posts with their media and target accounts,
weekly posting times (FR-PUB-09) and saved hashtag groups (FR-PUB-12).

The P7 contract. The limits below are shared: the composer's checklist (FR-PUB-10), the
scheduling rules (T7.1), the publish jobs (T7.3) and the database checks all read them.

Lifecycle (F-13): a post starts as a ``draft``; its accounts are its target rows, ``pending``
while the post is a draft or scheduled. Schedule, queue and publish now make it ``scheduled``;
the dispatcher claims each pending target of a due post (target ``publishing``, post
``publishing``), publish_target creates the containers (``container_created``) and poll_container
publishes them (``published``) or gives up (``failed``). The post's status then derives from its
targets: all published → ``published``, some → ``partially_published``, none → ``failed``.
``canceled`` targets will never run (for example, the account was disconnected before the publish
time); a post whose targets are all canceled is ``canceled``.
"""

from __future__ import annotations

import datetime as dt
import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in

# ---------------------------------------------------------------- limits (FR-PUB-01, FR-PUB-10)

CAPTION_MAX_CHARS = 2200  # Instagram's caption limit; also each per-account override
MAX_HASHTAGS = 30  # per caption, hashtag groups included (FR-PUB-12)
MAX_MENTIONS = 20
FIRST_COMMENT_MAX_CHARS = 2200  # FR-PUB-11
CAROUSEL_MIN_ASSETS = 2
CAROUSEL_MAX_ASSETS = 10
MAX_ASSETS = CAROUSEL_MAX_ASSETS
# Schedule, reschedule and calendar moves refuse a time closer than this (F-13, FR-PUB-08).
MIN_SCHEDULE_LEAD = dt.timedelta(minutes=5)
# A posting time is free when no scheduled or publishing target of the account is this close
# to it (FR-PUB-09).
SLOT_BUSY_WITHIN = dt.timedelta(minutes=30)
HASHTAG_GROUP_NAME_MAX_CHARS = 40
SUGGESTED_HASHTAGS_MAX = 20  # FR-PUB-02
CALENDAR_MAX_DAYS = 42  # six weeks: a month grid (§2.15 …/calendar)
# Instagram's rolling 24 h limit on API-published posts (a carousel counts once). The account's
# content_publishing_limit (quota_total) is authoritative; this is the fallback when it can't be
# read. Verify at T0.9.
DEFAULT_PUBLISHING_LIMIT = 100

# ---------------------------------------------------------------- publish job timing (T7.3)

PUBLISH_ATTEMPTS = 3  # FR-PUB-05: transient failures are retried up to 3 times
# poll_container: every 60 s for polls 1 to 5, then every 5 minutes for polls 6 to 10 (Meta asks
# for at most one status call per minute); still IN_PROGRESS after poll 10 (30 minutes): failed.
POLL_FAST_COUNT = 5
POLL_FAST_DELAY = dt.timedelta(seconds=60)
POLL_SLOW_DELAY = dt.timedelta(minutes=5)
POLL_MAX = 10
PROCESSING_TIMEOUT_MESSAGE = "Instagram took too long to process the video"


class ScheduledPostStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PARTIALLY_PUBLISHED = "partially_published"
    FAILED = "failed"
    CANCELED = "canceled"


class PostFormat(StrEnum):
    """Derived from the assets on every save (§5.7 format rules)."""

    IMAGE = "image"  # exactly 1 image
    CAROUSEL = "carousel"  # 2 to 10 images and videos
    REEL = "reel"  # exactly 1 video (Instagram publishes single videos as Reels)


class TargetStatus(StrEnum):
    PENDING = "pending"  # a draft's or scheduled post's account, not claimed yet
    PUBLISHING = "publishing"  # claimed by the dispatcher; publish_target is creating containers
    CONTAINER_CREATED = "container_created"  # poll_container is waiting for Instagram
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELED = "canceled"


class ScheduledPost(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "scheduled_posts"

    status: Mapped[str] = mapped_column(Text, server_default=sql("'draft'"))
    format: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str] = mapped_column(Text, server_default=sql("''"))
    first_comment: Mapped[str | None] = mapped_column(Text)
    # A draft may hold the time it was started at (a calendar click); a scheduled post always has
    # one (the ``schedulable`` check).
    publish_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # When the post last counted against scheduled_posts_monthly: a post counts once per billing
    # period, so unscheduling and scheduling again in the same period costs nothing (C-043).
    counted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        # The calendar and list range queries (…/calendar, FR-PUB-08).
        Index("ix_scheduled_posts_workspace_publish_at", "workspace_id", "publish_at"),
        # The publish dispatcher: due posts across workspaces (TR-JOB-03).
        Index(
            "ix_scheduled_posts_due",
            "publish_at",
            postgresql_where=sql("status IN ('scheduled', 'publishing')"),
        ),
        CheckConstraint(_in("status", ScheduledPostStatus), name="status"),
        CheckConstraint(f"format IS NULL OR {_in('format', PostFormat)}", name="format"),
        CheckConstraint(f"char_length(caption) <= {CAPTION_MAX_CHARS}", name="caption_length"),
        CheckConstraint(
            "first_comment IS NULL OR char_length(first_comment) BETWEEN 1 AND "
            f"{FIRST_COMMENT_MAX_CHARS}",
            name="first_comment_length",
        ),
        # Everything past draft has a time and a valid set of media.
        CheckConstraint(
            "status = 'draft' OR (publish_at IS NOT NULL AND format IS NOT NULL)",
            name="schedulable",
        ),
    )


class ScheduledPostAsset(IdMixin, TimestampMixin, TenantScoped, Base):
    """One image or video of a post, in order. Replaced as a whole on every save.

    P7b: ``edit_spec`` is the item's EditSpec (media/editor/spec.py; null: unedited) and
    ``render_id`` the render of exactly that edit (media_renders, same asset and spec hash) once
    one is asked for. A save keeps an item's edit when the body leaves ``edits`` out. Publishing
    uses the render's file; a video edit without a ready render blocks scheduling (FR-PUB-24)."""

    __tablename__ = "scheduled_post_assets"

    scheduled_post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scheduled_posts.id", ondelete="CASCADE")
    )
    # RESTRICT: an asset in a post can't be deleted from the library.
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)  # 0-based
    # none_as_null: an unedited item is SQL NULL, not JSON null (the render_has_edit check).
    edit_spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    # SET NULL: a render deleted with its asset's derived files leaves the edit to render again.
    render_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_renders.id", ondelete="SET NULL"), index=True
    )

    __table_args__ = (
        UniqueConstraint("scheduled_post_id", "position"),
        CheckConstraint(f"position BETWEEN 0 AND {MAX_ASSETS - 1}", name="position"),
        CheckConstraint("render_id IS NULL OR edit_spec IS NOT NULL", name="render_has_edit"),
    )


class ScheduledPostTarget(IdMixin, TimestampMixin, TenantScoped, Base):
    """One account a post publishes to, and how that went."""

    __tablename__ = "scheduled_post_targets"

    scheduled_post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scheduled_posts.id", ondelete="CASCADE")
    )
    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    caption_override: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=sql("'pending'"))
    claimed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=sql("0"))
    poll_count: Mapped[int] = mapped_column(SmallInteger, server_default=sql("0"))
    container_id: Mapped[str | None] = mapped_column(Text)  # the parent container
    child_container_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=sql("'{}'")
    )  # carousel children in order
    platform_media_id: Mapped[str | None] = mapped_column(Text)
    permalink: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    # FR-PUB-11: set once post_first_comment has run; neither set while it is pending.
    first_comment_platform_id: Mapped[str | None] = mapped_column(Text)
    first_comment_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("scheduled_post_id", "social_account_id"),
        # The dispatcher's join from due posts to their unclaimed targets.
        Index(
            "ix_scheduled_post_targets_pending",
            "scheduled_post_id",
            postgresql_where=sql("status = 'pending'"),
        ),
        # An account's targets: free posting times (FR-PUB-09), posts published in the last 24 h
        # against the publishing limit (FR-PUB-10, UX-SCR-04).
        Index("ix_scheduled_post_targets_account_status", "social_account_id", "status"),
        CheckConstraint(_in("status", TargetStatus), name="status"),
        CheckConstraint(
            f"caption_override IS NULL OR char_length(caption_override) <= {CAPTION_MAX_CHARS}",
            name="caption_override_length",
        ),
        CheckConstraint("attempts >= 0 AND poll_count >= 0", name="counters"),
        CheckConstraint(
            f"cardinality(child_container_ids) <= {CAROUSEL_MAX_ASSETS}", name="children"
        ),
        CheckConstraint(
            "status <> 'published' OR platform_media_id IS NOT NULL", name="published_media"
        ),
    )


class PostingSlot(IdMixin, TimestampMixin, TenantScoped, Base):
    """A weekly posting time of an account (FR-PUB-09), in the workspace time zone. Replaced as a
    whole by PUT …/posting-slots; changing them never moves posts already scheduled."""

    __tablename__ = "posting_slots"

    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    weekday: Mapped[int] = mapped_column(SmallInteger)  # 0 = Monday … 6 = Sunday
    local_time: Mapped[dt.time] = mapped_column(Time)  # whole minutes

    __table_args__ = (
        UniqueConstraint("social_account_id", "weekday", "local_time"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday"),
        CheckConstraint("date_trunc('minute', local_time) = local_time", name="whole_minute"),
    )


class HashtagGroup(IdMixin, TimestampMixin, TenantScoped, Base):
    """A named set of hashtags (FR-PUB-12), inserted into a caption or first comment with a
    click. Stored without "#", lowercase."""

    __tablename__ = "hashtag_groups"

    name: Mapped[str] = mapped_column(Text)
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(Text))

    __table_args__ = (
        Index(
            "uq_hashtag_groups_workspace_id_lower_name",
            "workspace_id",
            sql("lower(name)"),
            unique=True,
        ),
        CheckConstraint(
            f"char_length(name) BETWEEN 1 AND {HASHTAG_GROUP_NAME_MAX_CHARS}", name="name_length"
        ),
        CheckConstraint(
            f"cardinality(hashtags) BETWEEN 1 AND {MAX_HASHTAGS}", name="hashtags_count"
        ),
        CheckConstraint(
            "array_to_string(hashtags, ' ') = lower(array_to_string(hashtags, ' '))"
            " AND strpos(array_to_string(hashtags, ' '), '#') = 0",
            name="hashtags_normalized",
        ),
    )
