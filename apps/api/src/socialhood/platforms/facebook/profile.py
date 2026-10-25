"""The Page's messenger profile (GR-29): conversation starters, called ice breakers on Messenger
too.

``POST /me/messenger_profile`` with ``ice_breakers`` sets them: one entry for the default locale
holding up to 4 ``call_to_actions`` (``question`` and ``payload``). Setting replaces the list; an
empty list is a ``DELETE`` of the ``ice_breakers`` field. ``GET`` with ``fields=ice_breakers``
reads them back. The shapes are Instagram's without ``platform=instagram`` and are unverified for
Messenger until a real Page confirms them, with the question limit (80 characters) and that
starters show without a Get Started button (docs/verification.md). A tap comes back as a
postback with the payload.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from socialhood.platforms.base import IceBreaker
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram.profile import DEFAULT_LOCALE, parse_ice_breakers


async def set_ice_breakers(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    starters: Sequence[IceBreaker],
) -> list[IceBreaker]:
    if not starters:
        await http.request(
            "DELETE",
            graph("me/messenger_profile"),
            endpoint="me.messenger_profile.delete",
            token=token,
            json={"fields": ["ice_breakers"]},
        )
        return []
    await http.request(
        "POST",
        graph("me/messenger_profile"),
        endpoint="me.messenger_profile",
        token=token,
        json={
            "ice_breakers": [
                {
                    "call_to_actions": [
                        {"question": s.question, "payload": s.payload} for s in starters
                    ],
                    "locale": DEFAULT_LOCALE,
                }
            ],
        },
    )
    return await get_ice_breakers(http, graph, token)


async def get_ice_breakers(
    http: PlatformHttp, graph: Callable[[str], str], token: str
) -> list[IceBreaker]:
    body: Any = await http.request(
        "GET",
        graph("me/messenger_profile"),
        endpoint="me.messenger_profile.read",
        token=token,
        params={"fields": "ice_breakers"},
    )
    return parse_ice_breakers(body)
