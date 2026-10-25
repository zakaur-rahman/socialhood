"""The workspace's payment settings (GR-32): its own Razorpay keys and/or a UPI address.

Payments go to the business's own account, never through us. Razorpay Payment Links use the
business's key id and secret (the secret and the webhook secret are encrypted like platform
tokens, SEC-03, and never returned); Razorpay's partner OAuth is not used, because it needs
Technology Partner sign-up with Razorpay (C-120). A UPI address needs no keys at all, and has no
webhook: such an order is marked paid by hand.

- **Connecting** checks the keys with Razorpay before saving anything. The business then adds the
  webhook address shown on the card to its Razorpay dashboard (events ``payment_link.paid`` and
  the rest) with the same webhook secret it typed here. The address carries a random token, so
  nobody can guess which workspace it belongs to, and every post is also checked against the
  secret (razorpay/signatures.py).
- Both methods need the plan's ``commerce`` entitlement (PD-8) to be added; what exists is still
  shown after a downgrade.
- Unset means "not configured": asking for a payment link then says so in plain words.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import allows, check_entitlement
from socialhood.billing.plans import current_plan
from socialhood.errors import ApiError
from socialhood.models.orders import PaymentConnection
from socialhood.razorpay.client import (
    WEBHOOK_EVENTS,
    Credentials,
    RazorpayClient,
    RazorpayError,
)
from socialhood.schemas.orders import PaymentSettings, RazorpayConnect, UpiSave
from socialhood.security.crypto import TokenCipher

KEY = "commerce"
PLAN_COPY = "Orders and payment requests are part of Pro."
RAZORPAY_MISSING = "Razorpay isn't set up for this workspace. Add your keys in Integrations first."
UPI_MISSING = "A UPI address isn't set up for this workspace. Add it in Integrations first."
KEYS_REFUSED = "Razorpay doesn't accept these keys. Check them and try again."
RAZORPAY_DOWN = "Razorpay didn't respond. Try again."


async def get(session: AsyncSession, *, lock: bool = False) -> PaymentConnection | None:
    query = select(PaymentConnection)
    if lock:
        query = query.with_for_update()
    return (await session.scalars(query)).one_or_none()


def webhook_address(api_base_url: str | None, token: str) -> str | None:
    if not api_base_url:
        return None
    return f"{api_base_url.rstrip('/')}/webhooks/razorpay/{token}"


async def status(
    session: AsyncSession, *, api_base_url: str | None, plan: str | None = None
) -> PaymentSettings:
    entitled = allows(plan or await current_plan(session), KEY)
    conn = await get(session)
    if conn is None:
        return PaymentSettings(entitled=entitled, razorpay_connected=False)
    connected = bool(conn.razorpay_key_id and conn.razorpay_secret_enc)
    return PaymentSettings(
        entitled=entitled,
        razorpay_connected=connected,
        razorpay_key_id=conn.razorpay_key_id if connected else None,
        razorpay_test_mode=bool(
            conn.razorpay_key_id and conn.razorpay_key_id.startswith("rzp_test_")
        ),
        razorpay_error=conn.razorpay_last_error if connected else None,
        webhook_url=webhook_address(api_base_url, conn.webhook_token) if connected else None,
        webhook_events=list(WEBHOOK_EVENTS) if connected else [],
        webhook_seen_at=conn.webhook_seen_at if connected else None,
        upi_vpa=conn.upi_vpa,
        upi_name=conn.upi_name,
    )


async def _row(session: AsyncSession, user_id: uuid.UUID) -> PaymentConnection:
    conn = await get(session, lock=True)
    if conn is None:
        conn = PaymentConnection(
            webhook_token=secrets.token_urlsafe(24), connected_by_user_id=user_id
        )
        session.add(conn)
        await session.flush()
    return conn


async def connect_razorpay(
    session: AsyncSession,
    client: RazorpayClient,
    cipher: TokenCipher,
    body: RazorpayConnect,
    *,
    user_id: uuid.UUID,
) -> None:
    """Check the keys with Razorpay, then save them (encrypted). 402 without commerce on the
    plan, 422 for keys Razorpay refuses, 502 when Razorpay doesn't answer."""
    await check_entitlement(session, KEY, detail=PLAN_COPY)
    try:
        await client.verify(Credentials(body.key_id, body.private_key))
    except RazorpayError as error:
        if error.kind == "auth":
            raise ApiError("validation_error", KEYS_REFUSED) from error
        raise ApiError("platform_error", RAZORPAY_DOWN) from error
    conn = await _row(session, user_id)
    conn.razorpay_key_id = body.key_id
    conn.razorpay_secret_enc = cipher.encrypt(body.private_key)
    conn.razorpay_webhook_secret_enc = cipher.encrypt(body.webhook_key)
    conn.razorpay_last_error = None
    conn.webhook_seen_at = None
    conn.connected_by_user_id = user_id


async def disconnect_razorpay(session: AsyncSession) -> None:
    conn = await get(session, lock=True)
    if conn is None:
        return
    conn.razorpay_key_id = None
    conn.razorpay_secret_enc = None
    conn.razorpay_webhook_secret_enc = None
    conn.razorpay_last_error = None
    conn.webhook_seen_at = None


async def save_upi(session: AsyncSession, body: UpiSave, *, user_id: uuid.UUID) -> None:
    await check_entitlement(session, KEY, detail=PLAN_COPY)
    conn = await _row(session, user_id)
    conn.upi_vpa = body.vpa
    conn.upi_name = body.name.strip()


async def remove_upi(session: AsyncSession) -> None:
    conn = await get(session, lock=True)
    if conn is not None:
        conn.upi_vpa = None
        conn.upi_name = None


def credentials(conn: PaymentConnection | None, cipher: TokenCipher) -> Credentials:
    """The saved keys; ApiError (409) when Razorpay isn't set up."""
    if conn is None or not conn.razorpay_key_id or not conn.razorpay_secret_enc:
        raise ApiError("conflict", RAZORPAY_MISSING)
    return Credentials(conn.razorpay_key_id, cipher.decrypt(conn.razorpay_secret_enc))


def webhook_secret(conn: PaymentConnection, cipher: TokenCipher) -> str:
    if not conn.razorpay_webhook_secret_enc:
        return ""
    return cipher.decrypt(conn.razorpay_webhook_secret_enc)


def now() -> datetime:
    return datetime.now(UTC)
