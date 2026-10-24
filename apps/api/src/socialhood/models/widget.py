"""The website chat widget's settings (GR-28).

A workspace's widget is one ``social_accounts`` row of platform ``web`` (its public widget id is
the row's ``platform_account_id``) and one ``widget_settings`` row beside it. Visitors are
contacts of that account and their chats are ordinary conversations, so nothing else needs a
table. ``allowed_domains`` are host names without scheme or port (``example.com``,
``*.example.com``); the widget refuses to load anywhere else (services/widget/origin.py).
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class WidgetPosition(StrEnum):
    RIGHT = "right"
    LEFT = "left"


class EmailCapture(StrEnum):
    OFF = "off"  # never asks
    OPTIONAL = "optional"  # asks after the first message; the visitor can skip
    REQUIRED = "required"  # asks before the first message


class WidgetSettings(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "widget_settings"

    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=sql("true"))
    allowed_domains: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sql("'{}'"))
    accent_color: Mapped[str] = mapped_column(Text, server_default=sql("'#4467E6'"))
    title: Mapped[str] = mapped_column(Text, server_default=sql("'Chat with us'"))
    greeting: Mapped[str] = mapped_column(Text, server_default=sql("'Hi! How can we help?'"))
    position: Mapped[str] = mapped_column(Text, server_default=sql("'right'"))
    email_capture: Mapped[str] = mapped_column(Text, server_default=sql("'optional'"))
    email_prompt: Mapped[str] = mapped_column(
        Text, server_default=sql("'Leave your email so we can reply if you leave this page.'")
    )
    marketing_consent_enabled: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    marketing_consent_text: Mapped[str] = mapped_column(
        Text,
        server_default=sql("'Email me news and offers. You can unsubscribe at any time.'"),
    )
    # "Powered by Social Hood". Free always shows it; Pro and Max can turn it off (PD-7).
    show_branding: Mapped[bool] = mapped_column(Boolean, server_default=sql("true"))

    __table_args__ = (
        UniqueConstraint("social_account_id"),
        CheckConstraint(_in("position", WidgetPosition), name="position"),
        CheckConstraint(_in("email_capture", EmailCapture), name="email_capture"),
        CheckConstraint("accent_color ~ '^#[0-9A-Fa-f]{6}$'", name="accent_color"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 40", name="title_length"),
        CheckConstraint("char_length(greeting) BETWEEN 1 AND 300", name="greeting_length"),
        CheckConstraint("char_length(email_prompt) BETWEEN 1 AND 200", name="email_prompt_length"),
        CheckConstraint(
            "char_length(marketing_consent_text) BETWEEN 1 AND 300",
            name="marketing_consent_text_length",
        ),
        CheckConstraint("cardinality(allowed_domains) <= 20", name="allowed_domains_count"),
    )
