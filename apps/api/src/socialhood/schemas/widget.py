"""Website chat widget shapes (GR-28): the settings routes (owners and admins) and the public
widget API (/v1/widget/*, not in the OpenAPI document: only the widget's own frame calls it).

The public shapes avoid the words token, secret and password in field names (SEC-02): the bearer
the widget sends is ``session_key`` and the random value it keeps in its own storage is
``visitor_key``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

WidgetPositionName = Literal["right", "left"]
EmailCaptureName = Literal["off", "optional", "required"]
AiModeName = Literal["off", "suggest", "auto"]
HEX_COLOR = r"^#[0-9A-Fa-f]{6}$"


# ---- settings (owners and admins)


class WidgetSettingsOut(ResponseModel):
    account_id: uuid.UUID
    widget_id: str  # the public id the embed uses
    enabled: bool
    allowed_domains: list[str]
    accent_color: str
    title: str
    greeting: str
    position: WidgetPositionName
    email_capture: EmailCaptureName
    email_prompt: str
    marketing_consent_enabled: bool
    marketing_consent_text: str
    # What the visitor sees: false only on Pro and Max with the setting turned off.
    show_branding: bool
    # Free cannot turn the branding off; the settings page shows the switch locked.
    can_remove_branding: bool
    ai_mode: AiModeName
    script_url: str  # https://…/widget.js
    embed_snippet: str
    conversations_today: int
    conversations_daily_limit: int
    updated_at: datetime


class WidgetSettingsUpdate(RequestModel):
    enabled: bool | None = None
    allowed_domains: list[Annotated[str, Field(max_length=253)]] | None = Field(
        default=None, max_length=20
    )
    accent_color: str | None = Field(default=None, pattern=HEX_COLOR, max_length=7)
    title: str | None = Field(default=None, min_length=1, max_length=40)
    greeting: str | None = Field(default=None, min_length=1, max_length=300)
    position: WidgetPositionName | None = None
    email_capture: EmailCaptureName | None = None
    email_prompt: str | None = Field(default=None, min_length=1, max_length=200)
    marketing_consent_enabled: bool | None = None
    marketing_consent_text: str | None = Field(default=None, min_length=1, max_length=300)
    show_branding: bool | None = None


# ---- the public widget API


class WidgetConfig(ResponseModel):
    title: str
    greeting: str
    accent_color: str
    position: WidgetPositionName
    email_capture: EmailCaptureName
    email_prompt: str
    marketing_consent_enabled: bool
    marketing_consent_text: str
    show_branding: bool
    email_known: bool  # they already gave an email: do not ask again


class WidgetMessage(ResponseModel):
    id: uuid.UUID
    author: Literal["visitor", "team", "assistant"]
    text: str
    created_at: datetime


class WidgetSessionRequest(RequestModel):
    widget_id: str = Field(min_length=8, max_length=64)
    host: str = Field(min_length=1, max_length=253)  # the embedding page's host name
    visitor_key: str | None = Field(default=None, max_length=100)


class WidgetSession(ResponseModel):
    session_key: str
    expires_in: int
    visitor_key: str
    config: WidgetConfig
    messages: list[WidgetMessage]
    version: str


class WidgetMessages(ResponseModel):
    messages: list[WidgetMessage]
    version: str


class WidgetSend(RequestModel):
    text: str = Field(min_length=1, max_length=2000)
    client_id: uuid.UUID


class WidgetEmail(RequestModel):
    email: str = Field(min_length=3, max_length=254)
    name: str | None = Field(default=None, max_length=80)
    marketing_consent: bool = False


class WidgetEmailOut(ResponseModel):
    email_known: bool
