"""What a sequence step may send right now, and the words for why it did not (GR-24). Pure.

Rules (C-118):
- **Instagram and Messenger** have no templates: a step sends its text while the 24-hour messaging
  window is open and is skipped, with a reason, otherwise. Human Agent never applies to an
  automated message.
- **WhatsApp** inside the 24-hour window sends the step's text. Outside it, only an approved
  template can go, and only to a contact whose latest WhatsApp marketing record is a grant (GR-23's
  consent rules): no record is "no consent", a withdrawal is "opted out", both skip the step. A
  step with only a template sends it whatever the window, with the same consent check. A step with
  only text, outside the window, is skipped. Templates are marketing messages, so they also wait on
  ``BROADCASTS_ENABLED`` (the O-11 legal check): off, such a step is skipped as "marketing_off".
- A skipped step is a finished step: the sequence moves on to the next one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Action = Literal["text", "template", "skip"]

REASONS: dict[str, str] = {
    "window_closed": (
        "The messaging window had closed. Instagram and Messenger only allow messages for 24 "
        "hours after the person last wrote."
    ),
    "window_closed_no_template": (
        "The 24-hour window had closed and this step has no template. WhatsApp only allows an "
        "approved template then."
    ),
    "no_consent": "They haven't agreed to WhatsApp marketing messages.",
    "opted_out": "They opted out of WhatsApp marketing messages.",
    "marketing_off": "WhatsApp marketing messages are switched off for now.",
    "missing_value": "A template variable had no value for this person and no fallback.",
    "no_text": "This step only has a template, and this channel can't send templates.",
    "no_conversation": "They have never written to this account, so there is nobody to reply to.",
}


@dataclass(frozen=True)
class Decision:
    action: Action
    code: str | None = None  # why it is skipped

    @property
    def reason(self) -> str | None:
        return REASONS.get(self.code or "")


def decide(
    *,
    platform: str,
    window_open: bool,
    has_conversation: bool,
    has_text: bool,
    has_template: bool,
    consent_skip: str | None,
    marketing_enabled: bool,
) -> Decision:
    """What to send. ``consent_skip`` is GR-23's answer for the contact: None when the latest
    WhatsApp marketing record is a grant, else ``opted_out`` or ``no_consent``."""
    if platform != "whatsapp":
        if not has_text:
            return Decision("skip", "no_text")
        if not has_conversation:
            return Decision("skip", "no_conversation")
        if not window_open:
            return Decision("skip", "window_closed")
        return Decision("text")
    if window_open and has_text:
        return Decision("text")
    if not has_template:
        return Decision("skip", "window_closed_no_template")
    if not marketing_enabled:
        return Decision("skip", "marketing_off")
    if consent_skip is not None:
        return Decision("skip", consent_skip)
    return Decision("template")


STOP_WORDS: dict[str, str] = {
    "reply": "They replied",
    "tag": "A stop tag was added",
    "tag_removed": "A tag they needed was taken off",
    "stage": "Their lead stage changed",
    "member": "Taken out by your team",
    "ended": "The sequence has no more steps",
}


def stop_text(reason: str | None, detail: str | None) -> str | None:
    """A stop reason in words: "A stop tag was added: VIP"."""
    if reason is None:
        return None
    base = STOP_WORDS.get(reason, reason)
    return f"{base}: {detail}" if detail else base
