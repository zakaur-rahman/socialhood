"""Sandbox live counts and insights (T6.5; TR-PL-07, FR-ANL-01): deterministic made-up figures that
grow with a post's age, so snapshots and comparisons can be developed without Meta. The adapter's
``get_media_counts``, ``get_media_insights`` and ``get_account_insights`` delegate here."""

from __future__ import annotations

from datetime import date

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import AccountInsights, MediaCounts, MediaInsights


def media_counts(acct: SocialAccount, media_ref: str) -> MediaCounts | None:
    raise NotImplementedError("T6.5")


def media_insights(acct: SocialAccount, media_ref: str, *, media_type: str) -> MediaInsights:
    raise NotImplementedError("T6.5")


def account_insights(acct: SocialAccount, day: date, *, tz: str) -> AccountInsights:
    raise NotImplementedError("T6.5")
