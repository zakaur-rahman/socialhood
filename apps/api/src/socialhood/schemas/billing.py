"""Billing state (§5.10 BillingState; TR-BIL-04). P5 serves plan, entitlements and usage for the
AI credit banner (FR-AI-05); prices, checkout and trials arrive with P8."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from socialhood.schemas.common import ResponseModel

PlanName = Literal["free", "pro", "max"]


class BillingPrice(ResponseModel):
    plan: Literal["pro", "max"]
    amount_minor: int
    currency: str
    interval: Literal["month"]


class EntitlementValue(ResponseModel):
    key: str
    value: int | bool | list[str] | None  # None = unlimited


class UsageMeter(ResponseModel):
    metric: str  # ai_credits, scheduled_posts, knowledge_characters, …
    used: int
    limit: int | None = None
    period_end: date | None = None  # when counted credits reset


class BillingState(ResponseModel):
    plan: PlanName
    status: Literal["free", "trialing", "active", "on_hold", "expired"]
    current_period_end: datetime | None = None
    trial_ends_at: datetime | None = None
    cancel_at_period_end: bool
    grace_until: datetime | None = None
    trial_eligible: bool
    prices: list[BillingPrice]
    entitlements: list[EntitlementValue]
    usage: list[UsageMeter]
