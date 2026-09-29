"""An in-memory email outbox for tests and for running without Resend (``EMAIL_PROVIDER=fake``).

``outbox`` lists what was sent. Like Resend, a repeated ``idempotency_key`` returns the first
send's id and sends nothing new, so "one email per event" can be asserted on ``outbox``.
``fail_next(error)`` makes the next send raise ``error``.
"""

from __future__ import annotations

import itertools
from collections import deque

from socialhood.notify.email import EmailMessage, SentEmail


class FakeEmail:
    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []
        self._ids: dict[str, str] = {}
        self._failures: deque[BaseException] = deque()
        self._counter = itertools.count(1)

    def fail_next(self, error: BaseException) -> None:
        self._failures.append(error)

    def sent_to(self, address: str) -> list[EmailMessage]:
        return [message for message in self.outbox if message.to == address]

    async def send(self, message: EmailMessage) -> SentEmail:
        if self._failures:
            raise self._failures.popleft()
        known = self._ids.get(message.idempotency_key)
        if known is not None:
            return SentEmail(provider_message_id=known)
        provider_id = f"email_fake_{next(self._counter)}"
        self._ids[message.idempotency_key] = provider_id
        self.outbox.append(message)
        return SentEmail(provider_message_id=provider_id)
