"""What a connected account can do (TR-PL-11). Services check capabilities, never platform names."""

from __future__ import annotations

from enum import StrEnum

from socialhood.errors import ApiError


class Capability(StrEnum):
    DM_SEND = "dm_send"
    DM_ATTACHMENTS = "dm_attachments"
    READ_RECEIPTS = "read_receipts"
    HUMAN_AGENT = "human_agent"  # 7-day window for human replies
    TEMPLATES = "templates"  # WhatsApp templates outside the window
    CONVERSATION_BACKFILL = "conversation_backfill"
    COMMENTS = "comments"  # receive, reply, hide, delete
    PRIVATE_REPLY = "private_reply"
    PUBLISH = "publish"
    POST_INSIGHTS = "post_insights"
    ACCOUNT_INSIGHTS = "account_insights"


def require(capabilities: frozenset[Capability], needed: Capability) -> None:
    if needed not in capabilities:
        raise ApiError("capability_unavailable")
