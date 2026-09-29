"""Which email and push senders this process uses: Resend and Web Push over the shared httpx
client, or the in-memory fakes with ``EMAIL_PROVIDER=fake`` / ``PUSH_PROVIDER=fake`` (never in
production). Tests swap them with ``use_email_sender`` and ``use_push_sender``
(tests/support/notify.py does for every test)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

import httpx

from socialhood.notify.email import EmailSender
from socialhood.notify.email_fake import FakeEmail
from socialhood.notify.push import PushSender
from socialhood.notify.push_fake import FakePush
from socialhood.settings import Settings

_email_override: list[EmailSender] = []
_push_override: list[PushSender] = []


@lru_cache
def _process_fake_email() -> FakeEmail:
    return FakeEmail()


@lru_cache
def _process_fake_push() -> FakePush:
    return FakePush()


def get_email_sender(http: httpx.AsyncClient, settings: Settings) -> EmailSender:
    if _email_override:
        return _email_override[-1]
    if settings.email_provider == "fake":
        return _process_fake_email()
    from socialhood.notify.email_resend import ResendEmailSender

    return ResendEmailSender(http, settings)


def get_push_sender(http: httpx.AsyncClient, settings: Settings) -> PushSender:
    if _push_override:
        return _push_override[-1]
    if settings.push_provider == "fake":
        return _process_fake_push()
    from socialhood.notify.push_webpush import WebPushSender

    return WebPushSender(http, settings)


@contextmanager
def use_email_sender(sender: EmailSender) -> Iterator[EmailSender]:
    """Tests: every get_email_sender() in the block returns ``sender``."""
    _email_override.append(sender)
    try:
        yield sender
    finally:
        _email_override.pop()


@contextmanager
def use_push_sender(sender: PushSender) -> Iterator[PushSender]:
    """Tests: every get_push_sender() in the block returns ``sender``."""
    _push_override.append(sender)
    try:
        yield sender
    finally:
        _push_override.pop()
