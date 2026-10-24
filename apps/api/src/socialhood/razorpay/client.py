"""The Razorpay interface the orders use (GR-32), and the shapes it speaks in.

Errors are ``RazorpayError`` with a ``kind``: ``auth`` (the keys don't work), ``rate_limited`` and
``unavailable`` (try again later) and ``rejected`` (Razorpay refused what was sent).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

ErrorKind = Literal["auth", "rate_limited", "unavailable", "rejected"]

# The events the business turns on for its Razorpay webhook (shown on the connect card).
WEBHOOK_EVENTS = (
    "payment_link.paid",
    "payment_link.partially_paid",
    "payment_link.expired",
    "payment_link.cancelled",
    "refund.processed",
    "refund.failed",
)
MIN_EXPIRY_S = 16 * 60  # Razorpay needs a link to last at least 15 minutes


class RazorpayError(Exception):
    def __init__(self, kind: ErrorKind, message: str = "", *, status: int | None = None) -> None:
        super().__init__(message or kind)
        self.kind: ErrorKind = kind
        self.status = status


@dataclass(frozen=True)
class Credentials:
    key_id: str
    key_secret: str

    @property
    def test_mode(self) -> bool:
        return self.key_id.startswith("rzp_test_")


@dataclass(frozen=True)
class PaymentLink:
    id: str  # "plink_..."
    short_url: str  # https only


RefundState = Literal["pending", "processed", "failed"]


@dataclass(frozen=True)
class Refund:
    id: str  # "rfnd_..."
    status: RefundState


class RazorpayClient(Protocol):
    async def verify(self, creds: Credentials) -> None:
        """Raises ``RazorpayError("auth")`` when the keys don't work."""
        ...

    async def create_payment_link(
        self,
        creds: Credentials,
        *,
        amount_minor: int,
        currency: str,
        reference_id: str,
        description: str,
        customer_name: str | None,
        customer_phone: str | None,
        expire_by: int,
        accept_partial: bool = False,
    ) -> PaymentLink: ...

    async def cancel_payment_link(self, creds: Credentials, link_id: str) -> None: ...

    async def refund_payment(
        self,
        creds: Credentials,
        payment_id: str,
        *,
        amount_minor: int,
        reason: str,
        receipt: str,
    ) -> Refund:
        """Refund ``amount_minor`` of the payment (a part or all of it) back to the customer."""
        ...
