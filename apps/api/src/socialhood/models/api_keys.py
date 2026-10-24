"""Workspace API keys (GR-25): the credential of the public API (api/public.py).

A key is shown once, when it's made. Only its SHA-256 is stored, with the first characters
(``key_prefix``) so the list can tell keys apart. Keys are never edited: a revoked key stays as a
row (``revoked_at``), so the list still says what it was. ``scopes`` are the permissions it
carries (schemas/api_keys.py has the catalogue).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped


class ApiKey(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "api_keys"

    name: Mapped[str] = mapped_column(Text)
    key_prefix: Mapped[str] = mapped_column(Text)  # what the list shows: "shk_live_ab12"
    key_hash: Mapped[str] = mapped_column(Text)  # SHA-256 of the whole key, hex
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("key_hash"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="name_length"),
        CheckConstraint("cardinality(scopes) BETWEEN 1 AND 20", name="scopes"),
    )
