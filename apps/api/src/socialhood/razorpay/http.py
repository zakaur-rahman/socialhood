"""The real Razorpay client (GR-32): the Payment Links API over the shared httpx client, with the
business's own key id and secret as basic auth.

- ``verify`` lists one payment link: a 200 means the keys work.
- ``create_payment_link`` posts the amount in paise (or the currency's minor unit), our order id
  as ``reference_id``, an expiry, and the customer's name and phone; Razorpay's own SMS and email
  are off, because we send the link in the chat.
- ``cancel_payment_link`` posts to ``/payment_links/{id}/cancel``.
- ``refund_payment`` posts the amount to ``/payments/{id}/refund`` (normal speed) with our reason in
  the notes and our refund id as the receipt, and reads the refund's status from the answer.
- A link that takes part payments is created with ``accept_partial: true``.
- A response is classified into a ``RazorpayError`` kind; no body is logged or kept.

**Unverified against a real account** (C-120, C-125): written from Razorpay's documentation; no
test key has been used yet. In particular: that part payments on a link are for INR, and the refund
call and its statuses.
"""

from __future__ import annotations

from typing import Any, Literal

import httpx

from socialhood.razorpay.client import Credentials, PaymentLink, RazorpayError, Refund

API = "https://api.razorpay.com/v1"


def _kind(status: int) -> RazorpayError:
    if status in (401, 403):
        return RazorpayError("auth", "Razorpay doesn't accept these keys.", status=status)
    if status == 429:
        return RazorpayError("rate_limited", "Razorpay asked us to slow down.", status=status)
    if status >= 500:
        return RazorpayError("unavailable", "Razorpay isn't responding.", status=status)
    return RazorpayError("rejected", "Razorpay refused the request.", status=status)


class HttpRazorpayClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def _call(
        self,
        creds: Credentials,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._http.request(
                method,
                f"{API}{path}",
                json=json,
                params=params,
                auth=(creds.key_id, creds.key_secret),
            )
        except httpx.HTTPError as error:
            raise RazorpayError("unavailable", "Razorpay isn't responding.") from error
        if response.status_code >= 400:
            raise _kind(response.status_code)
        try:
            body: dict[str, Any] = response.json()
        except ValueError as error:
            raise RazorpayError("unavailable", "Razorpay sent an unreadable answer.") from error
        return body

    async def verify(self, creds: Credentials) -> None:
        await self._call(creds, "GET", "/payment_links", params={"count": 1})

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
    ) -> PaymentLink:
        customer: dict[str, str] = {}
        if customer_name:
            customer["name"] = customer_name
        if customer_phone:
            customer["contact"] = customer_phone
        body = await self._call(
            creds,
            "POST",
            "/payment_links",
            json={
                "amount": amount_minor,
                "currency": currency,
                "accept_partial": accept_partial,
                "reference_id": reference_id,
                "description": description[:2048],
                "customer": customer,
                "notify": {"sms": False, "email": False},
                "reminder_enable": False,
                "expire_by": expire_by,
            },
        )
        link_id, url = body.get("id"), body.get("short_url")
        if not link_id or not isinstance(url, str) or not url.startswith("https://"):
            raise RazorpayError("rejected", "Razorpay didn't give a payment link.")
        return PaymentLink(str(link_id), url)

    async def cancel_payment_link(self, creds: Credentials, link_id: str) -> None:
        await self._call(creds, "POST", f"/payment_links/{link_id}/cancel")

    async def refund_payment(
        self,
        creds: Credentials,
        payment_id: str,
        *,
        amount_minor: int,
        reason: str,
        receipt: str,
    ) -> Refund:
        body = await self._call(
            creds,
            "POST",
            f"/payments/{payment_id}/refund",
            json={
                "amount": amount_minor,
                "speed": "normal",
                "receipt": receipt[:40],
                "notes": {"reason": reason[:200]},
            },
        )
        refund_id, state = body.get("id"), str(body.get("status") or "")
        if not refund_id:
            raise RazorpayError("rejected", "Razorpay didn't confirm the refund.")
        status: Literal["pending", "processed", "failed"] = (
            "processed" if state == "processed" else "failed" if state == "failed" else "pending"
        )
        return Refund(str(refund_id), status)
