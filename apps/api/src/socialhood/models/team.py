"""Team invitations and the audit log (GR-19).

- workspace_invitations: an email invited to a workspace with a role. Clerk sends the email and
  holds the secret link, so no token is stored here. Stored statuses are pending, accepted and
  revoked; "expired" is a pending invitation past ``expires_at`` and is worked out on read.
  One pending invitation per workspace and email.
- audit_events: who did what, in the workspace. Written from the service layer; the detail is a
  small JSON object with ids and names, never a message body or a secret.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"


def _in(column: str, enum: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(member.value) for member in enum)})"


class WorkspaceInvitation(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "workspace_invitations"

    email: Mapped[str] = mapped_column(Text)  # stored lower-case
    role: Mapped[str] = mapped_column(Text)  # admin or agent
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # Clerk's invitation id, to revoke it there; null when Clerk wasn't asked (the person
    # already has an account) or the call failed.
    clerk_invitation_id: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint(_in("status", InvitationStatus), name="status"),
        CheckConstraint("role IN ('admin', 'agent')", name="role"),
        CheckConstraint("char_length(email) BETWEEN 3 AND 254", name="email_length"),
        Index(
            "uq_workspace_invitations_pending_email",
            "workspace_id",
            func.lower(email),
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_workspace_invitations_lower_email", func.lower(email)),
    )


class AuditEvent(IdMixin, CreatedAtMixin, TenantScoped, Base):
    __tablename__ = "audit_events"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # The actor's name or email when it happened, so the row reads right after they are removed.
    actor_label: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)  # e.g. automation.created, member.role_changed
    target_type: Mapped[str] = mapped_column(Text)
    target_id: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        CheckConstraint("char_length(action) BETWEEN 1 AND 60", name="action_length"),
        Index("ix_audit_events_workspace_id_created_at", "workspace_id", "created_at"),
        Index("ix_audit_events_workspace_id_actor_user_id", "workspace_id", "actor_user_id"),
    )
