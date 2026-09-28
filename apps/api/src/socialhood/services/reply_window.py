"""Reply-window rules (FR-INB-10, TR-PL-04). Pure functions: the read API shows the state and the
send pipeline enforces it, from the same code.

Instagram: open for 24 h after the contact's last message; then, when Human Agent is enabled,
human replies (only) are allowed for 7 days with the HUMAN_AGENT tag; then closed.
WhatsApp: open for 24 h; then only an approved template can be sent.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from socialhood.schemas.inbox import ReplyWindow

STANDARD_WINDOW = timedelta(hours=24)
HUMAN_AGENT_WINDOW = timedelta(days=7)

SendKind = Literal["human", "ai_auto", "automation", "template"]


def reply_window(
    platform: str, last_inbound_at: datetime | None, *, human_agent: bool, now: datetime
) -> ReplyWindow:
    closed = "template_only" if platform == "whatsapp" else "closed"
    if last_inbound_at is None:
        return ReplyWindow(state=closed)
    open_until = last_inbound_at + STANDARD_WINDOW
    if now < open_until:
        return ReplyWindow(state="open", closes_at=open_until)
    if platform == "instagram" and human_agent:
        agent_until = last_inbound_at + HUMAN_AGENT_WINDOW
        if now < agent_until:
            return ReplyWindow(state="human_agent", closes_at=agent_until)
    return ReplyWindow(state=closed)


def may_send(window: ReplyWindow, kind: SendKind) -> bool:
    """Whether a send of this kind is allowed now. AI and automations never use Human Agent."""
    if window.state == "open":
        return True
    if window.state == "human_agent":
        return kind == "human"
    if window.state == "template_only":
        return kind == "template"
    return False


def needs_human_agent_tag(window: ReplyWindow, kind: SendKind) -> bool:
    return window.state == "human_agent" and kind == "human"
