"""Data capture and consent (GR-14): what a question step (``ask``) checks, says and records.

- **Answers.** An email is trimmed and lower-cased whole (contacts.normalize_email);
  a phone is E.164 with +91 taken for a ten-digit Indian mobile (contacts.normalize_phone, a small
  normaliser rather than the ``phonenumbers`` library, which isn't a dependency: it knows +country
  codes of 8 to 15 digits and Indian mobiles, not every national format); free text is trimmed and
  capped at ``TEXT_MAX`` characters (an answer over it counts as not fitting, so it gets the retry).
- **Retry and skip.** An answer that doesn't fit gets the step's retry prompt (or the default copy
  here) until ``tries`` (1 to 3, default 2) run out; the flow then goes to the step's ``on_skip``.
  The editor sets ``on_skip`` to the step below by default, so a skipped question carries on.
- **Consent.** With ``consent`` on, a Yes or No question follows a saved answer. A tap on the
  quick reply or the words typed (``consent_answer``) are recorded in ``contact_consents`` for the
  conversation's channel, source ``flow``, with both messages as evidence. Yes records granted, No
  records revoked (an explicit refusal). Anything else is asked once more, then left unrecorded.
  Consent is for the channel they are chatting on; a captured email gives no email-channel consent.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.contacts import ConsentChannel, ConsentSource, ConsentStatus
from socialhood.schemas.flows import AskStep
from socialhood.services import contacts as contacts_service

TEXT_MAX = 500  # free-text answers

RETRY_COPY = {
    "email": "That doesn't look like an email address. Could you send it again?",
    "phone": "That doesn't look like a phone number. Could you send it with the country code?",
    "text": "Sorry, I didn't catch that. Could you send it again?",
}
CONSENT_COPY = (
    "Can we message you with offers and updates here? You can say no, and you can stop any time."
)
CONSENT_AGAIN_COPY = "Sorry, I need a yes or a no. Can we message you with offers and updates?"
CONSENT_YES = "Yes"
CONSENT_NO = "No thanks"
CONSENT_TRIES = 2  # the question, then one more

_YES = {"yes", "y", "yeah", "yep", "yup", "sure", "ok", "okay", "ya", "haan", "ha", "yes please"}
_NO = {
    "no",
    "n",
    "nope",
    "nah",
    "no thanks",
    "no thank you",
    "nahi",
    "stop",
    "dont",
    "dont message me",
}
_PUNCT = re.compile(r"[^\w\s]")


def retry_text(step: AskStep) -> str:
    return step.retry_text.strip() or RETRY_COPY[step.expect]


def consent_text(step: AskStep) -> str:
    return step.consent_text.strip() or CONSENT_COPY


def check_text(value: str) -> str:
    """A free-text answer as stored, or ValueError."""
    text = value.strip()
    if not text:
        raise ValueError("empty")
    if len(text) > TEXT_MAX:
        raise ValueError(f"Up to {TEXT_MAX} characters.")
    return text


def consent_answer(text: str | None, option: int | None) -> bool | None:
    """Whether a tap (0 Yes, 1 No) or typed words say yes (True), no (False) or neither (None)."""
    if option in (0, 1):
        return option == 0
    words = _PUNCT.sub("", (text or "").lower().replace("'", "")).strip()
    words = " ".join(words.split())
    if words in _YES:
        return True
    if words in _NO:
        return False
    return None


def consent_channel(platform: str) -> Literal["instagram", "whatsapp"] | None:
    if platform == ConsentChannel.INSTAGRAM:
        return "instagram"
    if platform == ConsentChannel.WHATSAPP:
        return "whatsapp"
    return None


async def record(
    session: AsyncSession,
    contact_id: uuid.UUID,
    *,
    platform: str,
    granted: bool,
    question_message_id: uuid.UUID | None,
    question_text: str,
    answer_message_id: uuid.UUID,
    answer_text: str | None,
    run_id: uuid.UUID,
    automation_id: uuid.UUID,
    step_id: str,
    at: datetime,
) -> bool:
    """Append the consent answer; False when the platform has no consent channel."""
    channel = consent_channel(platform)
    if channel is None:
        return False
    await contacts_service.record_consent(
        session,
        contact_id,
        channel=channel,
        status=ConsentStatus.GRANTED if granted else ConsentStatus.REVOKED,
        source=ConsentSource.FLOW,
        evidence={
            "message_id": str(answer_message_id),
            "text": (answer_text or "")[:200],
            "channel": channel,
            "question_message_id": str(question_message_id) if question_message_id else None,
            "question": question_text[:300],
            "run_id": str(run_id),
            "automation_id": str(automation_id),
            "step_id": step_id,
            "at": at.isoformat(),
        },
        at=at,
    )
    return True
