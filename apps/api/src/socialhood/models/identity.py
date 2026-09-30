"""Users, workspaces and memberships (§5.3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped

SLUG_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{1,46}[a-z0-9])$"


class WorkspaceStatus(StrEnum):
    ACTIVE = "active"
    DELETING = "deleting"


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    AGENT = "agent"


DEFAULT_NOTIFICATION_PREFS: dict[str, Any] = {
    "email_digest": True,
    "push": {"needs_you": True, "new_lead": True, "window_closing": True, "account": True},
}


def _in(column: str, enum: type[StrEnum]) -> str:
    values = ", ".join(f"'{member.value}'" for member in enum)
    return f"{column} IN ({values})"


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    clerk_user_id: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    last_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL", use_alter=True)
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_users_lower_email", func.lower(email)),)


class Workspace(IdMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    timezone: Mapped[str] = mapped_column(Text, server_default=text("'UTC'"))
    reply_language: Mapped[str] = mapped_column(Text, server_default=text("'auto'"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    # Null only while deleting: Clerk's user.deleted removes the owner before the purge (0015).
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    trial_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    checklist_dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    automation_disclosure: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(_in("status", WorkspaceStatus), name="status"),
        CheckConstraint("owner_user_id IS NOT NULL OR status = 'deleting'", name="owner"),
        CheckConstraint(f"slug ~ '{SLUG_PATTERN}'", name="slug"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="name"),
        CheckConstraint(
            "automation_disclosure IS NULL OR char_length(automation_disclosure) <= 60",
            name="automation_disclosure",
        ),
    )


class WorkspaceMember(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "workspace_members"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(Text, server_default=text("'owner'"))
    notification_prefs: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text(
            '\'{"email_digest": true, "push": {"needs_you": true, "new_lead": true, '
            '"window_closing": true, "account": true}}\'::jsonb'
        ),
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id"),
        CheckConstraint(_in("role", Role), name="role"),
    )
