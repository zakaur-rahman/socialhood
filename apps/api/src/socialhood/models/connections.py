"""Connected social accounts (§5.4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    NEEDS_RECONNECT = "needs_reconnect"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class AiMode(StrEnum):
    OFF = "off"
    SUGGEST = "suggest"
    AUTO = "auto"


class SocialAccount(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "social_accounts"

    platform: Mapped[str] = mapped_column(Text)
    platform_account_id: Mapped[str] = mapped_column(Text)
    app_scoped_id: Mapped[str | None] = mapped_column(Text)
    waba_id: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    username: Mapped[str | None] = mapped_column(Text)
    profile_picture_url: Mapped[str | None] = mapped_column(Text)
    phone_number: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    last_error: Mapped[str | None] = mapped_column(Text)
    access_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    ai_mode: Mapped[str] = mapped_column(Text, server_default=text("'suggest'"))
    ai_analysis_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    auto_hide_spam: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    webhooks_subscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    media_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    backfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "platform", "platform_account_id"),
        # One live connection per platform account across all workspaces.
        Index(
            "uq_social_accounts_live_platform_account",
            "platform",
            "platform_account_id",
            unique=True,
            postgresql_where=text("status <> 'disconnected'"),
        ),
        Index("ix_social_accounts_platform_platform_account_id", "platform", "platform_account_id"),
        CheckConstraint(_in("platform", Platform), name="platform"),
        CheckConstraint(_in("status", AccountStatus), name="status"),
        CheckConstraint(_in("ai_mode", AiMode), name="ai_mode"),
    )
