"""Approved WhatsApp templates for the template picker (FR-INB-10, F-07 template_only).

Read from Meta on demand and cached for 5 minutes per account: the picker opens often, templates
change rarely, and a new approval shows up within minutes. A token Meta refuses marks the account
needs_reconnect (F-05).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import Protocol, runtime_checkable

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.capabilities import Capability, require
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.platforms.whatsapp.templates import MessageTemplate
from socialhood.schemas.whatsapp import WhatsAppTemplate
from socialhood.services.connections import mark_needs_reconnect

log = get_logger(__name__)

CACHE_TTL_S = 300
RECONNECT_REASON = "WhatsApp stopped accepting this connection."


@runtime_checkable
class TemplateSource(Protocol):
    """Adapters with the TEMPLATES capability (TR-PL-11)."""

    async def list_templates(self, acct: SocialAccount) -> list[MessageTemplate]: ...


def cache_key(account_id: uuid.UUID) -> str:
    return f"wa:templates:{account_id}"


async def _cached(redis: Redis, account_id: uuid.UUID) -> list[WhatsAppTemplate] | None:
    try:
        raw = await redis.get(cache_key(account_id))
    except Exception:  # a cache outage only costs a call to Meta
        return None
    if not raw:
        return None
    return [WhatsAppTemplate.model_validate(item) for item in json.loads(raw)]


async def _store(redis: Redis, account_id: uuid.UUID, items: list[WhatsAppTemplate]) -> None:
    try:
        payload = json.dumps([item.model_dump(mode="json") for item in items])
        await redis.set(cache_key(account_id), payload, ex=CACHE_TTL_S)
    except Exception:
        log.warning("template_cache_failed", account_id=str(account_id))


async def approved_templates(
    session: AsyncSession, redis: Redis, deps: PlatformDeps, acct: SocialAccount
) -> list[WhatsAppTemplate]:
    try:
        adapter = adapter_for(acct, deps)
    except PlatformError as error:
        raise ApiError("capability_unavailable") from error
    require(adapter.capabilities_for(acct), Capability.TEMPLATES)
    if not isinstance(adapter, TemplateSource):
        raise ApiError("capability_unavailable")
    if acct.status in (AccountStatus.NEEDS_RECONNECT, AccountStatus.DISCONNECTED):
        raise ApiError("account_needs_reconnect")

    cached = await _cached(redis, acct.id)
    if cached is not None:
        return cached
    try:
        found = await adapter.list_templates(acct)
    except PlatformError as error:
        log.warning(
            "template_list_failed",
            account_id=str(acct.id),
            error_code=error.code,
            platform_code=error.platform_code,
        )
        if error.code == "account_needs_reconnect":
            await mark_needs_reconnect(session, acct, RECONNECT_REASON)
            await session.commit()
            raise ApiError("account_needs_reconnect") from error
        raise ApiError("platform_error", "WhatsApp didn't return your templates. Try again.") from (
            error
        )
    items = [WhatsAppTemplate.model_validate(asdict(t)) for t in found]
    await _store(redis, acct.id, items)
    return items
