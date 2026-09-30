"""WhatsApp connect and template shapes (F-04, FR-INB-10)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel


class EmbeddedSignup(RequestModel):
    """What the page receives from Meta's Embedded Signup v4: the FB.login code, and the ids from
    the session-info message when it arrived. A missing id is looked up with the business token
    (the shared WhatsApp Business Account from debug_token, its number from phone_numbers)."""

    code: str = Field(min_length=1, max_length=2048)
    waba_id: str | None = Field(default=None, min_length=1, max_length=64)
    phone_number_id: str | None = Field(default=None, min_length=1, max_length=64)


class WhatsAppTemplate(ResponseModel):
    name: str
    language: str
    category: Literal["marketing", "utility", "authentication"]
    status: str  # approved templates only are sendable
    body: str  # the body text with {{1}}-style placeholders
    param_count: int


class WhatsAppTemplateList(ResponseModel):
    items: list[WhatsAppTemplate]
