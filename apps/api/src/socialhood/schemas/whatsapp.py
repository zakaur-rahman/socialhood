"""WhatsApp connect and template shapes (F-04, FR-INB-10)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel


class EmbeddedSignup(RequestModel):
    """What the page receives from Meta's Embedded Signup v4 (FB.login code + session info)."""

    code: str = Field(min_length=1, max_length=2048)
    waba_id: str = Field(min_length=1, max_length=64)
    phone_number_id: str = Field(min_length=1, max_length=64)


class WhatsAppTemplate(ResponseModel):
    name: str
    language: str
    category: Literal["marketing", "utility", "authentication"]
    status: str  # approved templates only are sendable
    body: str  # the body text with {{1}}-style placeholders
    param_count: int


class WhatsAppTemplateList(ResponseModel):
    items: list[WhatsAppTemplate]
