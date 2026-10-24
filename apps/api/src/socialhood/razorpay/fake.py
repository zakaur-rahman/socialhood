"""A Razorpay sandbox for tests, development and the end-to-end stack (``RAZORPAY_PROVIDER=fake``;
never in production).

Keys that start with ``rzp_test_`` work; anything else is refused as ``auth``. A created link is
``plink_fake_<n>`` at ``https://rzp.test/pay/<id>``. ``fail_next(error)`` raises on the next call;
every call is recorded in ``calls``. Nothing is paid here: a test or the end-to-end suite posts
the signed ``payment_link.paid`` webhook itself, as Razorpay would.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from socialhood.razorpay.client import Credentials, PaymentLink, RazorpayError


class FakeRazorpay:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.links: dict[str, dict[str, Any]] = {}
        self._failures: deque[RazorpayError] = deque()
        self._made = 0

    def fail_next(self, error: RazorpayError) -> None:
        self._failures.append(error)

    def _enter(self, name: str, creds: Credentials, **detail: Any) -> None:
        self.calls.append((name, {"key_id": creds.key_id, **detail}))
        if self._failures:
            raise self._failures.popleft()
        if not creds.key_id.startswith("rzp_test_") or not creds.key_secret:
            raise RazorpayError("auth", "Razorpay doesn't accept these keys.", status=401)

    async def verify(self, creds: Credentials) -> None:
        self._enter("verify", creds)

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
    ) -> PaymentLink:
        self._enter(
            "create_payment_link",
            creds,
            amount_minor=amount_minor,
            currency=currency,
            reference_id=reference_id,
            expire_by=expire_by,
        )
        self._made += 1
        link_id = f"plink_fake_{self._made}"
        self.links[link_id] = {"reference_id": reference_id, "amount": amount_minor}
        return PaymentLink(link_id, f"https://rzp.test/pay/{link_id}")

    async def cancel_payment_link(self, creds: Credentials, link_id: str) -> None:
        self._enter("cancel_payment_link", creds, link_id=link_id)
        self.links.pop(link_id, None)
