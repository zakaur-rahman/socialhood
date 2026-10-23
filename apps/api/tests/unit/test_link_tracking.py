"""GR-15: tracked link codes, the bot rule, which addresses may be followed, the base address, and
the funnel's step order and path maths."""

from __future__ import annotations

import re

import pytest

from socialhood.schemas.flows import FlowDefinition
from socialhood.services.automations import funnel, links
from socialhood.settings import Settings

PERSON = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148"
)
INSTAGRAM_IN_APP = PERSON + " Instagram 330.0.0.34.89 (iPhone15,2; iOS 17_5; en_IN)"
FACEBOOK_IN_APP = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 [FBAN/FB4A;FBAV/450.0.0]"


def test_codes_are_long_unique_and_url_safe() -> None:
    codes = {links.new_code() for _ in range(500)}
    assert len(codes) == 500
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{16}", code) for code in codes)


@pytest.mark.parametrize(
    ("agent", "method", "bot"),
    [
        (PERSON, "GET", False),
        (INSTAGRAM_IN_APP, "GET", False),
        (FACEBOOK_IN_APP, "GET", False),
        (PERSON, "HEAD", True),
        (None, "GET", True),
        ("", "GET", True),
        ("facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)", "GET", True),
        (
            "meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)",
            "GET",
            True,
        ),
        ("WhatsApp/2.24.8.80 A", "GET", True),
        ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "GET", True),
        ("Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)", "GET", True),
        ("TelegramBot (like TwitterBot)", "GET", True),
        ("curl/8.5.0", "GET", True),
        ("python-requests/2.32.0", "GET", True),
        ("Mozilla/5.0 AppleWebKit/537.36 (compatible; SomeSpider/1.0)", "GET", True),
        ("Mozilla/5.0 Link Preview Fetcher", "GET", True),
    ],
)
def test_the_bot_rule(agent: str | None, method: str, bot: bool) -> None:
    assert links.is_bot(agent, method) is bot


@pytest.mark.parametrize(
    ("url", "safe"),
    [
        ("https://maple.example/shop?a=1#top", True),
        ("http://maple.example/shop", True),
        ("javascript:alert(1)", False),
        ("data:text/html;base64,AAAA", False),
        ("ftp://maple.example/x", False),
        ("//maple.example/x", False),
        ("https://", False),
        ("https://maple.example/a b", False),
        ("https://maple.example/\r\nSet-Cookie: x=1", False),
        ("", False),
    ],
)
def test_only_http_and_https_addresses_are_followed(url: str, safe: bool) -> None:
    assert (links.safe_target(url) is not None) is safe


def settings(**kw: str | None) -> Settings:
    return Settings(  # type: ignore[call-arg]
        database_url="postgresql+asyncpg://x:x@127.0.0.1/x",
        database_url_direct="postgresql://x:x@127.0.0.1/x",
        redis_url="redis://127.0.0.1:6379/14",
        **kw,
    )


def test_the_base_address_is_the_link_domain_else_the_api() -> None:
    assert links.base_url(settings()) is None
    assert links.base_url(settings(api_base_url="https://api.socialhood.in/")) == (
        "https://api.socialhood.in"
    )
    assert links.base_url(
        settings(api_base_url="https://api.socialhood.in", link_base_url="https://shl.in")
    ) == ("https://shl.in")


def flow(*steps: dict[str, object]) -> FlowDefinition:
    return FlowDefinition.model_validate({"start": steps[0]["id"], "steps": list(steps)})


SPLIT = flow(
    {"type": "send", "id": "hello", "text": "Hi", "next": "split"},
    {
        "type": "randomize",
        "id": "split",
        "paths": [{"weight": 1, "next": "a"}, {"weight": 3, "next": "b"}],
    },
    {"type": "send", "id": "a", "text": "A", "next": "thanks"},
    {"type": "send", "id": "b", "text": "B", "next": "thanks"},
    {"type": "send", "id": "thanks", "text": "Thanks"},
    {"type": "end", "id": "unused"},
)


def test_steps_come_in_the_order_a_walk_meets_them() -> None:
    assert [s.id for s in funnel.order(SPLIT)] == ["hello", "split", "a", "thanks", "b", "unused"]


def test_a_path_reaches_its_steps_and_where_the_paths_meet() -> None:
    assert funnel.reachable(SPLIT, "a") == {"a", "thanks"}
    assert funnel.reachable(SPLIT, "b") == {"b", "thanks"}
    assert funnel.reachable(SPLIT, None) == set()


@pytest.mark.parametrize(
    ("part", "whole", "share"), [(1, 4, 0.25), (1, 3, 0.3333), (0, 5, 0.0), (3, 0, 0.0)]
)
def test_rates(part: int, whole: int, share: float) -> None:
    assert funnel.rate(part, whole) == share
