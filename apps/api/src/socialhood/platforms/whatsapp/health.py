"""A WhatsApp number's quality rating and messaging tier (GR-23). Pure parsing, no I/O.

Two sources, both *unverified against a live number*:

- ``GET /{phone_number_id}?fields=quality_rating,messaging_limit_tier``: ``quality_rating`` is
  GREEN, YELLOW, RED or UNKNOWN (NA); ``messaging_limit_tier`` is TIER_50, TIER_250, TIER_1K,
  TIER_10K, TIER_100K or TIER_UNLIMITED.
- The ``phone_number_quality_update`` webhook field: ``value.event`` is ONBOARDING, UPGRADE,
  DOWNGRADE, FLAGGED or UNFLAGGED and ``value.current_limit`` the tier after it. FLAGGED means the
  number was flagged for low quality (rating Red), UNFLAGGED that it recovered (we only know it is
  no longer Red, so it is taken as Medium until the rating is read again from the API).

This webhook field has no ``metadata.phone_number_id``: it arrives under the WhatsApp Business
Account id (``entry[].id``) with the number as ``display_phone_number``, so it is routed by the
account's ``waba_id`` (webhooks/routing.resolve_waba_accounts).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RATINGS = {"GREEN": "green", "YELLOW": "yellow", "RED": "red"}
# FLAGGED: rated Low. UNFLAGGED: no longer Low; we do not know whether Medium or High until the
# rating is read again, so it is Medium (the cautious one) for now.
EVENT_RATINGS = {"FLAGGED": "red", "UNFLAGGED": "yellow"}


@dataclass(frozen=True)
class NumberHealth:
    quality_rating: str  # green, yellow, red or unknown
    messaging_tier: str | None = None


@dataclass(frozen=True)
class QualityEvent:
    event: str  # ONBOARDING, UPGRADE, DOWNGRADE, FLAGGED or UNFLAGGED
    messaging_tier: str | None
    display_phone_number: str | None
    quality_rating: str | None  # what the event says: red for FLAGGED, yellow for UNFLAGGED


def parse_health(body: Any) -> NumberHealth:
    """The API's answer as a NumberHealth (unknown values become ``unknown`` and None)."""
    data = body if isinstance(body, dict) else {}
    rating = RATINGS.get(str(data.get("quality_rating") or "").upper(), "unknown")
    tier = data.get("messaging_limit_tier") or data.get("current_limit")
    return NumberHealth(rating, str(tier) if tier else None)


def parse_quality_event(value: Any) -> QualityEvent | None:
    """A ``phone_number_quality_update`` change's value, or None when it is not one."""
    data = value if isinstance(value, dict) else {}
    event = str(data.get("event") or "").upper()
    if not event:
        return None
    tier = data.get("current_limit")
    display = data.get("display_phone_number")
    return QualityEvent(
        event=event,
        messaging_tier=str(tier) if tier else None,
        display_phone_number=str(display) if display else None,
        quality_rating=EVENT_RATINGS.get(event),
    )
