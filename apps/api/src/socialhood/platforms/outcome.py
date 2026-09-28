"""Platform writes whose outcome is unknown (TR-JOB-05).

A send that times out, or loses its connection, after the request went out may have been
delivered. Retrying it could reach the customer twice, so adapters turn those failures into
``delivery_unknown``, which is never retried automatically: the user checks the chat and retries
by hand. Failures before the request left (connect timeouts, a full pool, DNS) stay
``platform_unavailable`` and retry as usual.
"""

from __future__ import annotations

import httpx

from socialhood.platforms.errors import PlatformError

DELIVERY_UNKNOWN = "delivery_unknown"

# httpx raises these only once the request has been (at least partly) written.
_AFTER_SEND = (httpx.ReadTimeout, httpx.WriteTimeout, httpx.ReadError, httpx.RemoteProtocolError)


def sent_but_unconfirmed(error: PlatformError) -> bool:
    return isinstance(error.__cause__, _AFTER_SEND)


def for_write(error: PlatformError) -> PlatformError:
    """The error a platform write should raise: ``delivery_unknown`` when the platform may have
    received the request, otherwise the mapped error unchanged."""
    if not sent_but_unconfirmed(error):
        return error
    unknown = PlatformError(
        DELIVERY_UNKNOWN,
        retryable=False,
        message="The platform did not confirm the send",
    )
    unknown.__cause__ = error.__cause__
    return unknown
