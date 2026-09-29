"""AI settings (T5.5; FR-KB-04 brand voice, FR-SUG-05 takeover period, FR-SUG-06 escalation
phrases). One row per workspace, created with it; a workspace that somehow has none gets the
defaults on first read. PUT replaces the whole object (lists are trimmed of blanks and
duplicates, ignoring case)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.ai import AiSettings
from socialhood.repositories import suggestions as repo
from socialhood.schemas.ai import AiSettings as AiSettingsOut
from socialhood.schemas.ai import AiSettingsUpdate


async def load(session: AsyncSession) -> AiSettings:
    row = await repo.settings_row(session)
    if row is None:
        row = AiSettings()
        session.add(row)
        await session.flush()
        await session.refresh(row)
    return row


def out(row: AiSettings) -> AiSettingsOut:
    return AiSettingsOut.model_validate(row, from_attributes=True)


def _clean(items: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for item in items:
        text = " ".join(item.split())
        if text and text.casefold() not in seen:
            seen[text.casefold()] = text
    return list(seen.values())


def _blank_to_none(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


async def replace(session: AsyncSession, body: AiSettingsUpdate) -> AiSettings:
    """PUT …/ai-settings; the caller commits."""
    await load(session)
    row = await repo.update_settings(
        session,
        business_name=_blank_to_none(body.business_name),
        business_description=_blank_to_none(body.business_description),
        tone=body.tone,
        emoji_policy=body.emoji_policy,
        do_list=_clean(body.do_list),
        dont_list=_clean(body.dont_list),
        escalation_phrases=_clean(body.escalation_phrases),
        sign_off=_blank_to_none(body.sign_off),
        takeover_minutes=body.takeover_minutes,
    )
    assert row is not None  # load() made sure there is one
    return row
