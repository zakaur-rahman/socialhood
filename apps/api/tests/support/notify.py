"""Notification test support (P8): every test runs with a FakeEmail and a FakePush (never Resend
or a push service); request ``fake_email`` or ``fake_push`` to read what was sent or queue
failures. Factories write P8 notification rows through the ORM and return their ids."""

from __future__ import annotations

import base64
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.notifications import (
    EmailDelivery,
    Notification,
    PushSubscription,
    WeeklyDigest,
)
from socialhood.notify.email_fake import FakeEmail
from socialhood.notify.push_fake import FakePush
from socialhood.notify.registry import use_email_sender, use_push_sender


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


# A browser's subscription keys as PushManager gives them (base64url): an uncompressed P-256
# public point and a 16-byte auth secret, made fresh per test run so pywebpush can encrypt to them.
BROWSER_KEY = ec.generate_private_key(ec.SECP256R1())
P256DH = _b64url(
    BROWSER_KEY.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
)
AUTH = _b64url(os.urandom(16))

# The API's VAPID key pair for tests (api_settings): raw private scalar and uncompressed public
# point, both base64url, the formats py_vapid and PushManager.subscribe take.
_VAPID_KEY = ec.generate_private_key(ec.SECP256R1())
VAPID_PRIVATE_KEY = _b64url(_VAPID_KEY.private_numbers().private_value.to_bytes(32, "big"))
VAPID_PUBLIC_KEY = _b64url(
    _VAPID_KEY.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
)


@pytest.fixture(autouse=True)
def fake_email() -> Iterator[FakeEmail]:
    with use_email_sender(FakeEmail()) as sender:
        assert isinstance(sender, FakeEmail)
        yield sender


@pytest.fixture(autouse=True)
def fake_push() -> Iterator[FakePush]:
    with use_push_sender(FakePush()) as sender:
        assert isinstance(sender, FakePush)
        yield sender


def _wid(workspace_id: uuid.UUID | str) -> uuid.UUID:
    return uuid.UUID(str(workspace_id))


async def _add(engine: AsyncEngine, workspace_id: uuid.UUID | str | None, row: Any) -> uuid.UUID:
    async def save() -> uuid.UUID:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(row)
            await session.commit()
            return row.id  # type: ignore[no-any-return]

    if workspace_id is None:
        return await save()
    with workspace_scope(_wid(workspace_id)):
        return await save()


def push_endpoint() -> str:
    return f"https://fcm.googleapis.com/fcm/send/test-{uuid.uuid4().hex}"


async def make_push_subscription(
    engine: AsyncEngine, *, user_id: uuid.UUID | str, **values: Any
) -> uuid.UUID:
    """A browser subscription of ``user_id`` (user-scoped, no workspace)."""
    defaults: dict[str, Any] = {
        "endpoint": push_endpoint(),
        "p256dh": P256DH,
        "auth": AUTH,
        "user_agent": "Mozilla/5.0 (Linux; Android 15) Chrome/140.0 Mobile",
    }
    row = PushSubscription(user_id=uuid.UUID(str(user_id)), **{**defaults, **values})
    return await _add(engine, None, row)


async def make_notification(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
    **values: Any,
) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "type": "ai_escalated",
        "severity": "warning",
        "title": "Priya needs you",
        "body": "Auto handed this conversation to you.",
        "link": f"/inbox/{uuid.uuid4()}",
        "channels": ["in_app", "push"],
    }
    row = Notification(user_id=uuid.UUID(str(user_id)), **{**defaults, **values})
    return await _add(engine, workspace_id, row)


async def make_email_delivery(
    engine: AsyncEngine, *, workspace_id: uuid.UUID | str, **values: Any
) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "template": "post_failed",
        "to_email": "owner@example.com",
        "data": {"post_id": str(uuid.uuid4()), "reason": "Instagram rejected the image"},
        "dedupe_key": f"notification:{uuid.uuid4()}",
    }
    return await _add(engine, workspace_id, EmailDelivery(**{**defaults, **values}))


def last_monday(today: date | None = None) -> date:
    today = today or datetime.now(UTC).date()
    return today - timedelta(days=today.weekday())


async def make_weekly_digest(
    engine: AsyncEngine, *, workspace_id: uuid.UUID | str, **values: Any
) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "week_start": last_monday(),
        "status": "sent",
        "recipients": 1,
        "stats": {"messages_received": 42, "reply_rate": 88},
        "sent_at": datetime.now(UTC),
    }
    return await _add(engine, workspace_id, WeeklyDigest(**{**defaults, **values}))
