"""Saved replies (GR-21) and business hours (GR-22): the workspace's reusable messages and when it
answers.

- ``saved_replies``: a title, a shortcut typed after ``/`` in the composer, and a body that may use
  ``{first_name}``, ``{username}`` and the contact's custom fields. The shortcut is unique per
  workspace, lower case.
- ``business_hours``: one weekly schedule per workspace (``social_account_id`` null) and, when an
  account differs, one row for that account that replaces the workspace's. Times are wall-clock in
  the workspace time zone. ``away_enabled`` and ``away_message`` are the reply sent out of hours;
  ``auto_mode`` says whether Auto mode works always or only out of hours.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class AutoMode(StrEnum):
    ALWAYS = "always"  # Auto mode answers at any hour (today's behaviour)
    OUT_OF_HOURS = "out_of_hours"  # Auto mode answers only while closed


class SavedReply(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "saved_replies"

    title: Mapped[str] = mapped_column(Text)
    shortcut: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "shortcut"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 60", name="title_length"),
        CheckConstraint("shortcut ~ '^[a-z0-9][a-z0-9_-]{0,29}$'", name="shortcut_format"),
        CheckConstraint("char_length(body) BETWEEN 1 AND 1000", name="body_length"),
    )


class BusinessHours(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "business_hours"

    # Null: the workspace's schedule. Set: this account's own, which replaces the workspace's.
    social_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    # False on an account's row: this account has no hours (always open), whatever the
    # workspace has.
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=sql("true"))
    # [{"day": 0..6 (Monday 0), "ranges": [{"start": "09:00", "end": "17:00"}]}]; a day left out
    # is closed. ``end`` may be "24:00". Checked by services/business_hours.
    schedule: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=sql("'[]'::jsonb"))
    away_enabled: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    away_message: Mapped[str | None] = mapped_column(Text)
    auto_mode: Mapped[str] = mapped_column(Text, server_default=sql("'always'"))

    __table_args__ = (
        UniqueConstraint("workspace_id", "social_account_id"),
        # Nulls differ in a unique key, so the workspace's own row needs this one.
        Index(
            "uq_business_hours_workspace",
            "workspace_id",
            unique=True,
            postgresql_where=sql("social_account_id IS NULL"),
        ),
        CheckConstraint(_in("auto_mode", AutoMode), name="auto_mode"),
        CheckConstraint(
            "away_message IS NULL OR char_length(away_message) <= 1000", name="away_message_length"
        ),
    )
