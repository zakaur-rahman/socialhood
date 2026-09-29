"""What an automation sends (T4.4; FR-AUT-11, FR-AUT-13, FR-AUT-14): the DM text with personal
fields and the disclosure line, its link buttons, and the public reply variation.

The disclosure line is added to DMs and private replies (messages), not to public comment
replies. Commenters are known only by username until they write a DM, so ``{first_name}`` in a
private or public reply usually takes its fallback.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.errors import ERROR_CODES, ApiError
from socialhood.models.automations import Automation
from socialhood.models.connections import SocialAccount
from socialhood.models.identity import Workspace
from socialhood.models.inbox import Contact
from socialhood.platforms.base import OutboundButton
from socialhood.platforms.errors import PlatformError
from socialhood.services.automations import render

# A stable client_id per run: queueing the same run's DM twice returns the first message.
CLIENT_ID_NAMESPACE = uuid.UUID("5f0c7c6e-4d0a-4c1e-9a55-6f8b0c2d1a47")

# (error_code, error_message) for runs that send nothing.
AI_UNAVAILABLE = (
    "ai_reply_unavailable",
    "AI replies aren't available yet, so this automation sent nothing.",
)
NO_MESSAGE = ("nothing_to_send", "The automation has no message to send.")


def client_id_for(run_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(CLIENT_ID_NAMESPACE, f"automation-run:{run_id}")


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
