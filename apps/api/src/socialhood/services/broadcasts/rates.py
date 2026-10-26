"""Meta's rate card for WhatsApp template messages, as data (GR-23, PD-3). Pure.

The business pays Meta directly: each WhatsApp Business Account carries its own payment method
(set up in Embedded Signup), with no markup and no money through Amplychat. So the estimate on
a broadcast is information, never a charge.

**The figures are unverified.** They are India's rates in INR per delivered template message by
category, typed in by hand from Meta's published pricing, not read from Meta, and they change (Meta
revises its rates, and from 2027-01-01 Indian accounts are billed in INR only; plan item O-8).
Update ``RATE_CARD`` when Meta's pricing page changes; ``as_of`` says when it was last checked and
the pages show it next to every estimate.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class RateCard:
    currency: str
    country: str
    as_of: str  # the date the figures were typed in (ISO)
    source: str
    verified: bool
    rates: dict[str, Decimal]  # per message, by template category


RATE_CARD = RateCard(
    currency="INR",
    country="India",
    as_of="2026-10-24",
    source="Meta's WhatsApp Business Platform pricing for India, typed in by hand",
    verified=False,
    rates={
        "marketing": Decimal("0.7846"),
        "utility": Decimal("0.1150"),
        "authentication": Decimal("0.1150"),
    },
)


def rate_for(category: str, card: RateCard = RATE_CARD) -> Decimal:
    """The per-message rate for a template category (marketing if the category is unknown, the
    dearest, so an estimate is never too low)."""
    return card.rates.get(category, card.rates["marketing"])


def estimate(category: str, recipients: int, card: RateCard = RATE_CARD) -> Decimal:
    """What ``recipients`` messages of ``category`` cost on the card, to the paisa."""
    return (rate_for(category, card) * recipients).quantize(Decimal("0.01"), ROUND_HALF_UP)
