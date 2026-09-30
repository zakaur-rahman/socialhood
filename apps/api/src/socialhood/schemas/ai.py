"""AI shapes (§5.5, §5.10): brand voice and AI settings, analysis corrections, auto-reply
decisions. Analyses and suggestions themselves are in schemas/inbox.py (P3 contract)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.inbox import EscalationReason, IntentName

ToneName = Literal["friendly", "professional", "playful", "concise"]
EmojiPolicyName = Literal["none", "light", "lots"]
TakeoverMinutes = Literal[0, 30, 120, 1440]  # 0 = until resumed (FR-SUG-05)
SentimentName = Literal["positive", "neutral", "negative"]
DecisionOutcomeName = Literal["auto_sent", "escalated", "skipped"]
SkipReasonName = Literal[
    "mode_not_auto", "quota_exhausted", "paused", "automation_handled", "rate_capped", "not_needed"
]

ListItem = Annotated[str, Field(min_length=1, max_length=120)]


class AiSettings(ResponseModel):
    """FR-KB-04 brand voice, FR-SUG-06 escalation phrases, FR-SUG-05 takeover period."""

    business_name: str | None = None  # prompts fall back to the workspace name
    business_description: str | None = None
    tone: ToneName
    emoji_policy: EmojiPolicyName
    do_list: list[str]
    dont_list: list[str]
    escalation_phrases: list[str]
    sign_off: str | None = None
    takeover_minutes: TakeoverMinutes
    updated_at: datetime


class AiSettingsUpdate(RequestModel):
    """PUT …/ai-settings: the whole settings object."""

    business_name: str | None = Field(default=None, max_length=80)
    business_description: str | None = Field(default=None, max_length=1000)
    tone: ToneName = "friendly"
    emoji_policy: EmojiPolicyName = "light"
    do_list: list[ListItem] = Field(default_factory=list, max_length=20)
    dont_list: list[ListItem] = Field(default_factory=list, max_length=20)
    escalation_phrases: list[ListItem] = Field(default_factory=list, max_length=20)
    sign_off: str | None = Field(default=None, max_length=60)
    takeover_minutes: TakeoverMinutes = 120


class AnalysisCorrection(RequestModel):
    """PATCH …/message-analyses/{id} (FR-AI-04): at least one of the two."""

    intent: IntentName | None = None
    sentiment: SentimentName | None = None


class AiDecisionCheck(ResponseModel):
    n: int  # 1-13, TR-AI-07's order
    name: str
    passed: bool
    value: str | float | bool | None = None  # what was checked, e.g. the confidence


class AiDecision(ResponseModel):
    """Why the AI did or did not reply (FR-SUG-04): the popover on an AI-sent bubble and the
    escalation banner."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID  # the inbound message decided on
    suggestion_id: uuid.UUID | None = None
    sent_message_id: uuid.UUID | None = None
    outcome: DecisionOutcomeName
    reason: EscalationReason | SkipReasonName | None = None
    checks: list[AiDecisionCheck]
    user_feedback: Literal["bad"] | None = None
    created_at: datetime


class AiDecisionFeedback(RequestModel):
    """POST …/ai-decisions/{id}/feedback: "bad" = should not have sent; null clears it."""

    feedback: Literal["bad"] | None


PolishTone = Literal["friendly", "professional"]


class PolishRequest(RequestModel):
    """POST …/conversations/{id}/polish (C-063): the member's draft reply. ``tone`` overrides the
    brand voice's tone for this rewrite."""

    text: str = Field(min_length=1, max_length=4096)
    tone: PolishTone | None = None


class PolishResult(ResponseModel):
    """The polished draft: the same language, meaning and roughly the length, with no fact,
    number, link or promise the draft didn't have. Nothing is stored or sent."""

    text: str
