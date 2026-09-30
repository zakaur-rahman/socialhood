"""Stored media (TR-MED-01), edited renders of it (P7b, TR-MED-04) and the account's platform
posts (§5.6)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    REAL,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class ResourceType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    RAW = "raw"


class AssetPurpose(StrEnum):
    POST = "post"
    MESSAGE = "message"
    KNOWLEDGE = "knowledge"
    INBOUND = "inbound"  # copies of platform media (TR-MED-03)


class MediaType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    REEL = "reel"
    STORY = "story"


class MediaAsset(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "media_assets"

    public_id: Mapped[str] = mapped_column(Text, unique=True)  # starts with ws/{workspace_id}/
    resource_type: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text)
    format: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(Text)
    secure_url: Mapped[str | None] = mapped_column(Text)
    bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(REAL)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint(_in("resource_type", ResourceType), name="resource_type"),
        CheckConstraint(_in("purpose", AssetPurpose), name="purpose"),
        CheckConstraint("public_id LIKE ('ws/' || workspace_id::text || '/%')", name="folder"),
    )


class RenderKind(StrEnum):
    IMAGE = "image"  # a transformation delivered on the fly: ready as soon as it is created
    VIDEO = "video"  # rendered eagerly by Cloudinary, finished by its notification or a poll


class RenderStatus(StrEnum):
    PENDING = "pending"  # stored; start_render has not sent it to Cloudinary yet
    RENDERING = "rendering"  # Cloudinary accepted the eager render (batch_id set)
    READY = "ready"  # url is the rendered file
    FAILED = "failed"  # error says why; asking for the same edit again retries it


# Render jobs (P7b, TB.4). Cloudinary's notification finishes a render; without one, poll_render
# checks the asset's derived files every RENDER_POLL_DELAY, and sweep_stuck_renders fails a render
# still unfinished after RENDER_TIMEOUT.
RENDER_POLL_DELAY = timedelta(seconds=15)
RENDER_POLL_MAX = 40  # 10 minutes of polls
RENDER_STUCK_AFTER = timedelta(minutes=2)  # pending this long: the start was lost; re-enqueue
RENDER_TIMEOUT = timedelta(minutes=30)
RENDER_START_ATTEMPTS = 3


class MediaRender(IdMixin, TimestampMixin, TenantScoped, Base):
    """One edit of one asset, rendered by Cloudinary as a derived file (FR-PUB-21). The asset is
    never changed. The same edit of the same asset is one row (``spec_hash``), so asking again
    reuses it. Video renders count against video_renders_monthly and photo edits are counted, both
    by ``created_at`` in the usage period (billing/usage.py); a failed render doesn't count."""

    __tablename__ = "media_renders"

    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text)
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)  # EditSpec (media/editor/spec.py)
    spec_hash: Mapped[str] = mapped_column(Text)  # media/editor/spec.spec_hash
    transformation: Mapped[str] = mapped_column(Text)  # what the builder made of the spec
    format: Mapped[str] = mapped_column(Text)  # jpg or mp4
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    url: Mapped[str | None] = mapped_column(Text)  # the rendered file
    cover_url: Mapped[str | None] = mapped_column(Text)  # a Reel's cover frame (cover_s)
    batch_id: Mapped[str | None] = mapped_column(Text)  # Cloudinary's eager batch
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(REAL)
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    poll_count: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("media_asset_id", "spec_hash"),
        # Renders created in a usage period, by kind (video_renders_monthly, photo edits).
        Index("ix_media_renders_workspace_kind_created", "workspace_id", "kind", "created_at"),
        # The sweeper: renders not finished yet, across workspaces.
        Index(
            "ix_media_renders_unfinished",
            "created_at",
            postgresql_where=text("status IN ('pending', 'rendering')"),
        ),
        # A Cloudinary notification names its batch.
        Index(
            "ix_media_renders_batch_id", "batch_id", postgresql_where=text("batch_id IS NOT NULL")
        ),
        CheckConstraint(_in("kind", RenderKind), name="kind"),
        CheckConstraint(_in("status", RenderStatus), name="status"),
        CheckConstraint(
            "(kind = 'image' AND format = 'jpg') OR (kind = 'video' AND format = 'mp4')",
            name="format",
        ),
        CheckConstraint("spec_hash ~ '^[0-9a-f]{64}$'", name="spec_hash"),
        CheckConstraint(
            "status <> 'ready' OR (url IS NOT NULL AND ready_at IS NOT NULL)", name="ready"
        ),
        CheckConstraint("status <> 'failed' OR error IS NOT NULL", name="failed"),
        CheckConstraint("attempts >= 0 AND poll_count >= 0", name="counters"),
    )


class MediaItem(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "media_items"

    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    platform_media_id: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    permalink: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    like_count: Mapped[int | None] = mapped_column(Integer)
    comments_count: Mapped[int | None] = mapped_column(Integer)
    # {total, analysed, positive, neutral, negative, spam}: schemas/posts.py CommentStats (P6).
    comment_stats: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    summary: Mapped[str | None] = mapped_column(Text)
    # [{label, count, positive, neutral, negative}], at most 6: schemas/posts.py PostTopic (P6).
    topics: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comments_since_summary: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    # The target that published this post, when Social Hood published it (T7.3). One post per
    # target; deleting the scheduled post keeps the post.
    published_target_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scheduled_post_targets.id", ondelete="SET NULL"), unique=True
    )

    __table_args__ = (
        UniqueConstraint("social_account_id", "platform_media_id"),
        Index("ix_media_items_workspace_posted", "workspace_id", text("posted_at DESC")),
        # An account's previous posts, the baseline of a comparison (TR-AGT-05).
        Index("ix_media_items_account_posted", "social_account_id", text("posted_at DESC")),
        CheckConstraint(_in("media_type", MediaType), name="media_type"),
    )
