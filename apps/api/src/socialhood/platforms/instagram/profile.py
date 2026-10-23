"""The account's messenger profile on Instagram (GR-11): conversation starters, called ice breakers.

``POST /me/messenger_profile`` with ``platform=instagram`` sets them: one ``ice_breakers`` entry
for the default locale holding up to 4 ``call_to_actions`` (``question`` and ``payload``). Setting
replaces the list; an empty list is a ``DELETE`` of the ``ice_breakers`` field. ``GET`` with
``fields=ice_breakers`` reads them back. Unverified until T0.9: the exact request shapes, that the
default locale is accepted without others, and the 80-character question limit. Starters show in
the mobile app only.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from socialhood.platforms.base import IceBreaker
from socialhood.platforms.http import PlatformHttp

DEFAULT_LOCALE = "default"


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
            params={"platform": "instagram"},
            json={"fields": ["ice_breakers"]},
        )
        return []
    await http.request(
        "POST",
        graph("me/messenger_profile"),
        endpoint="me.messenger_profile",
        token=token,
        params={"platform": "instagram"},
        json={
            "platform": "instagram",
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
    body = await http.request(
        "GET",
        graph("me/messenger_profile"),
        endpoint="me.messenger_profile.read",
        token=token,
        params={"platform": "instagram", "fields": "ice_breakers"},
    )
    return parse_ice_breakers(body)


def parse_ice_breakers(body: Any) -> list[IceBreaker]:
    """The default locale's starters from a ``GET /me/messenger_profile`` body."""
    found: list[IceBreaker] = []
    rows = body.get("data") if isinstance(body, dict) else None
    for row in rows if isinstance(rows, list) else []:
        groups = row.get("ice_breakers") if isinstance(row, dict) else None
        for group in groups if isinstance(groups, list) else []:
            if not isinstance(group, dict) or group.get("locale", DEFAULT_LOCALE) != DEFAULT_LOCALE:
                continue
            for action in group.get("call_to_actions") or []:
                question, payload = action.get("question"), action.get("payload")
                if isinstance(question, str) and isinstance(payload, str):
                    found.append(IceBreaker(question, payload))
    return found
