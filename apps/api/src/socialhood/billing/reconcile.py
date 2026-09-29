"""Reconciliation (T8.3; TR-BIL-03): every 6 h, GET /subscriptions/{id} for each subscription
that isn't Free, correct drift through billing/lifecycle.apply_snapshot and log it; a
subscription past grace_until still on hold is set to Free. Runs from jobs/tasks/billing.py,
which finds the subscriptions across workspaces (the tenant bypass is allowed in jobs/) and calls
``reconcile_one`` in each workspace's scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.dodo import DodoClient


@dataclass(frozen=True)
class Reconciled:
    drift: bool
    detail: str | None = None


async def reconcile_one(session: AsyncSession, dodo: DodoClient, *, now: datetime) -> Reconciled:
    """The current workspace's subscription against Dodo."""
    raise NotImplementedError("T8.3")
