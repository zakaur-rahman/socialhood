"""In-app notifications (§5.9, FR-NOT-01): one row per recipient."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, CreatedAtMixin, IdMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Notification(IdMixin, CreatedAtMixin, TenantScoped, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text, server_default=text("'info'"))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(Text)
    channels: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{in_app}'"))
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_notifications_user_id_dedupe_key",
            "user_id",
            "dedupe_key",
            unique=True,
            postgresql_where=text("dedupe_key IS NOT NULL"),
        ),
        Index("ix_notifications_user_id_created_at", "user_id", text("created_at DESC")),
        CheckConstraint(_in("severity", Severity), name="severity"),
    )
