"""Prices as integer minor units (GR-31): "799.00" INR is 79900, "1500" JPY is 1500.

Pure: no database, no clock. A currency has 0, 2 or 3 decimal places (ISO 4217's exponent); the
short tables below hold the ones that are not 2. Parsing is strict: a price is digits with an
optional decimal part, never a float, and never more places than the currency has.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

DEFAULT_CURRENCY = "INR"
ZERO_DECIMAL = frozenset(
    {"BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX", "VND", "VUV"}
)
THREE_DECIMAL = frozenset({"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"})
MAX_MINOR = 10**12  # a ceiling that fits a BIGINT and any real price
_CODE = re.compile(r"^[A-Z]{3}$")
_AMOUNT = re.compile(r"^\d{1,13}(?:\.\d{1,3})?$")


def exponent(currency: str) -> int:
    if currency in ZERO_DECIMAL:
        return 0
    return 3 if currency in THREE_DECIMAL else 2


def valid_currency(code: str) -> bool:
    return bool(_CODE.match(code))


def parse(text: str, currency: str) -> int:
    """ "799", "799.5" or "1,299.00" as minor units. Raises ValueError with a plain reason."""
    cleaned = text.strip().replace(",", "").replace(" ", "")
    if not cleaned:
        raise ValueError("Enter a price.")
    if not _AMOUNT.match(cleaned):
        raise ValueError("Enter the price as a number, like 799 or 799.50.")
    places = exponent(currency)
    amount = Decimal(cleaned)
    scaled = amount * (10**places)
    if scaled != scaled.to_integral_value():
        detail = "no decimal places" if places == 0 else f"at most {places} decimal places"
        raise ValueError(f"{currency} prices have {detail}.")
    minor = int(scaled)
    if minor > MAX_MINOR:
        raise ValueError("That price is too large.")
    return minor


def from_decimal(value: str | float | int | Decimal, currency: str) -> int | None:
    """A decimal from another system (Shopify's "799.00") as minor units; None when unreadable."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    minor = int((amount * (10 ** exponent(currency))).to_integral_value())
    return minor if minor <= MAX_MINOR else None


def to_decimal(minor: int, currency: str) -> Decimal:
    return Decimal(minor).scaleb(-exponent(currency))


def plain(minor: int, currency: str) -> str:
    """ "799.00" for the AI and the CSV (no symbol, no grouping)."""
    places = exponent(currency)
    return f"{to_decimal(minor, currency):.{places}f}"


def label(minor: int, currency: str) -> str:
    """ "INR 799.00": the text customers' messages are written from (the AI, a flow's message)."""
    return f"{currency} {plain(minor, currency)}"
