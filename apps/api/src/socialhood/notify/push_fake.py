"""An in-memory push service for tests and for running without VAPID keys
(``PUSH_PROVIDER=fake``).

``sent`` lists (target, message) pairs. An endpoint in ``gone`` answers like a 410 (``PushGone``);
``fail_next(error)`` makes the next send raise ``error``. The payload is built on every send, so
an oversized message fails here as it would for real.
"""

from __future__ import annotations

from collections import deque

from socialhood.notify.push import PushGone, PushMessage, PushTarget


class FakePush:
    def __init__(self) -> None:
        self.sent: list[tuple[PushTarget, PushMessage]] = []
        self.gone: set[str] = set()
        self._failures: deque[BaseException] = deque()

    def fail_next(self, error: BaseException) -> None:
        self._failures.append(error)

    def sent_to(self, endpoint: str) -> list[PushMessage]:
        return [message for target, message in self.sent if target.endpoint == endpoint]

    async def send(self, target: PushTarget, message: PushMessage) -> None:
        message.payload()
        if self._failures:
            raise self._failures.popleft()
        if target.endpoint in self.gone:
            raise PushGone(target.endpoint, 410)
        self.sent.append((target, message))
