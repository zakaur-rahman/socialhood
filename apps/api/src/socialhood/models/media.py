"""Stored media (TR-MED-01) and the account's platform posts (§5.6)."""

from __future__ import annotations

import uuid
from datetime import datetime
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
