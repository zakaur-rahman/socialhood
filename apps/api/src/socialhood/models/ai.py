"""AI settings per workspace (§5.5). Knowledge and analysis tables arrive in P5."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import CheckConstraint, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class Tone(StrEnum):
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    PLAYFUL = "playful"
    CONCISE = "concise"


class EmojiPolicy(StrEnum):
    NONE = "none"
    LIGHT = "light"
    LOTS = "lots"


TAKEOVER_MINUTES = (0, 30, 120, 1440)  # 0 = until resumed


class AiSettings(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "ai_settings"

    business_name: Mapped[str | None] = mapped_column(Text)
    business_description: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(Text, server_default=text("'friendly'"))
    emoji_policy: Mapped[str] = mapped_column(Text, server_default=text("'light'"))
    do_list: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    dont_list: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    escalation_phrases: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    sign_off: Mapped[str | None] = mapped_column(Text)
    takeover_minutes: Mapped[int] = mapped_column(Integer, server_default=text("120"))

    __table_args__ = (
        UniqueConstraint("workspace_id"),
        CheckConstraint(_in("tone", Tone), name="tone"),
        CheckConstraint(_in("emoji_policy", EmojiPolicy), name="emoji_policy"),
        CheckConstraint(
            f"takeover_minutes IN ({', '.join(str(m) for m in TAKEOVER_MINUTES)})",
            name="takeover_minutes",
        ),
    )
