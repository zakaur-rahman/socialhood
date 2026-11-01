"""Workspace API keys (GR-25): the credential of the public API (api/public.py).

A key is shown once, when it's made. Only its SHA-256 is stored, with the first characters
(``key_prefix``) so the list can tell keys apart. A revoked key stays as a row (``revoked_at``),
so the list still says what it was. ``scopes`` are the permissions it carries (schemas/
api_keys.py has the catalogue) and never change: make another key.

C-167 (0056):
- ``expires_at``: optional; an expired key is refused like a revoked one. ``expiry_notified_at``
  is when owners and admins were told it expires within 7 days (once per key).
- ``allowed_ips``: IPs and CIDRs (normalised, IPv4 and IPv6, at most 20); empty means any
  address. Only the name and this list can be edited after the key is made.
- A key is revoked when the member who made it leaves (services/api_keys.revoke_for_member).
  ``created_by_user_id`` is NULL only for a key whose maker's account was deleted before C-167:
  it keeps working on the public API and the list says "made by a former member".
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, text
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
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiry_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    allowed_ips: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))

    __table_args__ = (
        UniqueConstraint("key_hash"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="name_length"),
        CheckConstraint("cardinality(scopes) BETWEEN 1 AND 20", name="scopes"),
        CheckConstraint("cardinality(allowed_ips) <= 20", name="allowed_ips"),
    )
