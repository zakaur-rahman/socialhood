"""What an automation sends (T4.4, T4.8; FR-AUT-11, FR-AUT-13, FR-AUT-14, FR-AUT-21,
FR-AUT-22): the DM text with personal fields and the disclosure line, its link buttons, the
public reply variation, the tap-first opening with its quick reply, and the follow nudge with its
"View profile" button.

The disclosure line is added to DMs and private replies (messages), not to public comment
replies. Commenters are known only by username until they write a DM, so ``{first_name}`` in a
private or public reply (and in a tap-first opening) usually takes its fallback; the message
that follows their answer has their real name.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.errors import ERROR_CODES, ApiError
from socialhood.models.automations import Automation, AutomationAction
from socialhood.models.connections import SocialAccount
from socialhood.models.identity import Workspace
from socialhood.models.inbox import Contact
from socialhood.platforms.base import OutboundButton, OutboundQuickReply
from socialhood.platforms.errors import PlatformError
from socialhood.services.automations import render

# A stable client_id per run: queueing the same run's DM twice returns the first message.
CLIENT_ID_NAMESPACE = uuid.UUID("5f0c7c6e-4d0a-4c1e-9a55-6f8b0c2d1a47")
COMMENT_TRIGGERS = frozenset({"comment_keyword", "comment_any"})
TAP_PREFIX = "shr:"  # a tap-first quick reply's payload: "shr:{run_id}"
NUDGE_BUTTON = "View profile"
PROFILE_URL = "https://www.instagram.com/{}/"

# (error_code, error_message) for runs that send nothing.
# Tap first opens only automations that send a message (FR-AUT-21); an AI reply never waits.
NOT_A_MESSAGE = (
    "nothing_to_send",
    "Only automations that send a message can wait for an answer.",
)
NO_MESSAGE = ("nothing_to_send", "The automation has no message to send.")


def client_id_for(run_id: uuid.UUID, part: str | None = None) -> uuid.UUID:
    """The run's DM (or private reply, or opening); ``part`` names a later message of the same
    run in the same conversation: "message" after a tap-first answer, "nudge" for the nudge."""
    name = f"automation-run:{run_id}" if part is None else f"automation-run:{run_id}:{part}"
    return uuid.uuid5(CLIENT_ID_NAMESPACE, name)


def personal_fields(
    contact: Contact | None, *, username: str | None = None
) -> tuple[str | None, str | None]:
    """(first name, username) for {first_name} and {username}."""
    first_name = render.first_name_of(contact.display_name) if contact else None
    return first_name, (contact.username if contact and contact.username else username)


async def disclosure(session: AsyncSession) -> str | None:
    """The workspace's automation disclosure line (FR-AUT-11), or None when it is off."""
    return await session.scalar(
        select(Workspace.automation_disclosure).where(Workspace.id == require_workspace())
    )


async def message_text(
    session: AsyncSession,
    automation: Automation,
    contact: Contact | None,
    *,
    username: str | None = None,
) -> str | None:
    """The DM as sent: personal fields filled, disclosure appended. None when there is none."""
    return render_message(
        automation, contact, username=username, disclosure_line=await disclosure(session)
    )


def render_message(
    automation: Automation,
    contact: Contact | None,
    *,
    username: str | None,
    disclosure_line: str | None,
) -> str | None:
    if not automation.message_text or not automation.message_text.strip():
        return None
    first_name, name = personal_fields(contact, username=username)
    text = render.render(automation.message_text, first_name=first_name, username=name)
    return render.with_disclosure(text, disclosure_line)


def opens_first(automation: Automation) -> bool:
    """Tap first (FR-AUT-21): a comment automation's private reply is its opening, with one
    quick reply; its message follows the commenter's answer."""
    return bool(
        automation.confirm_first
        and automation.trigger in COMMENT_TRIGGERS
        and automation.action == AutomationAction.SEND_MESSAGE
        and (automation.opening_text or "").strip()
        and (automation.opening_button or "").strip()
    )


def render_opening(
    automation: Automation,
    contact: Contact | None,
    *,
    username: str | None,
    disclosure_line: str | None,
) -> str | None:
    """The opening as sent: personal fields filled, disclosure appended."""
    if not (automation.opening_text or "").strip():
        return None
    first_name, name = personal_fields(contact, username=username)
    text = render.render(automation.opening_text or "", first_name=first_name, username=name)
    return render.with_disclosure(text, disclosure_line)


def opening_quick_reply(automation: Automation, run_id: uuid.UUID) -> OutboundQuickReply:
    return OutboundQuickReply(
        title=(automation.opening_button or "").strip(), payload=tap_payload(run_id)
    )


def tap_payload(run_id: uuid.UUID) -> str:
    """The quick reply's payload, which names the run it answers."""
    return f"{TAP_PREFIX}{run_id}"


def tapped_run_id(payload: str | None) -> uuid.UUID | None:
    if not payload or not payload.startswith(TAP_PREFIX):
        return None
    try:
        return uuid.UUID(payload[len(TAP_PREFIX) :])
    except ValueError:
        return None


def render_nudge(
    automation: Automation,
    contact: Contact | None,
    *,
    username: str | None = None,
    disclosure_line: str | None,
) -> str | None:
    """The follow nudge as sent (FR-AUT-22), or None when it is off or empty. AI replies ignore
    it."""
    if (
        not automation.follow_nudge
        or automation.action != AutomationAction.SEND_MESSAGE
        or not (automation.follow_nudge_text or "").strip()
    ):
        return None
    first_name, name = personal_fields(contact, username=username)
    text = render.render(automation.follow_nudge_text or "", first_name=first_name, username=name)
    return render.with_disclosure(text, disclosure_line)


def nudge_buttons(account_username: str | None) -> tuple[OutboundButton, ...]:
    """The nudge's "View profile" button, to the account's Instagram profile."""
    if not account_username:
        return ()
    return (OutboundButton(title=NUDGE_BUTTON, url=PROFILE_URL.format(account_username)),)


def buttons(automation: Automation) -> tuple[OutboundButton, ...]:
    return tuple(
        OutboundButton(title=str(b["title"]), url=str(b["url"]))
        for b in automation.message_buttons or []
        if isinstance(b, dict) and b.get("title") and b.get("url")
    )


def choose_variant(count: int, last: int | None) -> int:
    """FR-AUT-14: a random variation, never the one used last on the post (when there is a
    choice)."""
    choices = [i for i in range(count) if i != last] or list(range(count))
    return secrets.choice(choices)


def public_reply(
    automation: Automation, variant: int, contact: Contact | None, *, username: str | None
) -> str:
    first_name, name = personal_fields(contact, username=username)
    return render.render(
        automation.public_reply_texts[variant], first_name=first_name, username=name
    )


def api_error_reason(error: ApiError) -> str:
    """A run log reason for a send the pipeline refused."""
    if error.errors:
        return " ".join(e.message for e in error.errors)
    return error.detail or ERROR_CODES[error.code].title


def platform_error_reason(error: PlatformError, acct: SocialAccount) -> str:
    from socialhood.services.sending import readable_error

    return readable_error(
        error.code, acct.platform, platform_message=error.message, username=acct.username
    )


def run_values(**values: Any) -> dict[str, Any]:
    """Run columns, dropping unset ones (the table's defaults apply)."""
    return {k: v for k, v in values.items() if v is not None}
