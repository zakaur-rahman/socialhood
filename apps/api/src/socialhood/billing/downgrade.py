"""Downgrade effects (T8.3; FR-BIL-07, F-15 "Expired").

When a workspace moves to Free (or any plan with lower limits): accounts in Auto move to Suggest;
AI-reply automations pause; automations of read-only accounts pause; automations still over the
active_automations limit pause, keeping the most recently updated active; connected accounts
beyond accounts_per_platform become read-only (billing/entitlements.read_only_accounts: each
platform's earliest connected accounts keep the plan's slots; the others refuse scheduled
messages and automation activations with 402). Nothing is deleted, and nothing comes back on its
own after an upgrade.
The report feeds the plan_downgraded notification ("2 accounts switched from Auto to Suggest. 4
automations paused.").
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import allows, read_only_accounts
from socialhood.billing.plans import entitlement
from socialhood.models.automations import Automation, AutomationStatus
from socialhood.models.connections import AiMode, SocialAccount
from socialhood.services.automations.definitions import pause_rows


@dataclass(frozen=True)
class DowngradeReport:
    accounts_to_suggest: list[uuid.UUID] = field(default_factory=list)
    automations_paused: list[uuid.UUID] = field(default_factory=list)
    accounts_read_only: list[uuid.UUID] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.accounts_to_suggest or self.automations_paused or self.accounts_read_only)

    def summary(self) -> str:
        """The notification's list of what changed (F-15)."""
        parts: list[str] = []
        if n := len(self.accounts_to_suggest):
            parts.append(f"{n} account{'' if n == 1 else 's'} switched from Auto to Suggest.")
        if n := len(self.automations_paused):
            parts.append(f"{n} automation{'' if n == 1 else 's'} paused.")
        if n := len(self.accounts_read_only):
            parts.append(f"{n} account{'' if n == 1 else 's'} can no longer send.")
        return " ".join(parts) or "Nothing needed to change."


async def apply_downgrade(session: AsyncSession, *, plan: str, now: datetime) -> DowngradeReport:
    """Apply ``plan``'s limits to the current workspace (idempotent)."""
    to_suggest: list[uuid.UUID] = []
    if not allows(plan, "ai_modes", AiMode.AUTO):
        fallback = AiMode.SUGGEST if allows(plan, "ai_modes", AiMode.SUGGEST) else AiMode.OFF
        accounts = await session.scalars(
            select(SocialAccount).where(SocialAccount.ai_mode == AiMode.AUTO).with_for_update()
        )
        for account in accounts:
            account.ai_mode = fallback
            to_suggest.append(account.id)

    read_only = await read_only_accounts(session, plan=plan)
    active = list(
        await session.scalars(
            select(Automation)
            .where(Automation.status == AutomationStatus.ACTIVE)
            .order_by(Automation.updated_at.desc(), Automation.id)
            .with_for_update()
        )
    )
    ai_replies = allows(plan, "ai_reply_automations")
    stopped = [
        a
        for a in active
        if (a.action == "ai_reply" and not ai_replies) or a.social_account_id in read_only
    ]
    keep = [a for a in active if a not in stopped]
    limit = entitlement(plan, "active_automations")
    if limit is not None:
        stopped += keep[limit:]
    paused = pause_rows(stopped, now)
    await session.flush()
    return DowngradeReport(
        accounts_to_suggest=to_suggest,
        automations_paused=paused,
        accounts_read_only=sorted(read_only),
    )
