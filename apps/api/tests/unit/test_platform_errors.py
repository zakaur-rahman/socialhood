"""TR-PL-03 error mapping and TR-PL-11 capabilities."""

from __future__ import annotations

import json
from typing import Any

import pytest

from socialhood.errors import ApiError
from socialhood.models.connections import SocialAccount
from socialhood.platforms.capabilities import Capability, require
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import map_graph_error
from socialhood.platforms.instagram import oauth
from socialhood.platforms.instagram.adapter import InstagramAdapter
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.settings import AppEnv, Settings
from tests.support.instagram import fixture


def graph_error(code: int, subcode: int | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"message": "m", "type": "OAuthException", "code": code}
    if subcode is not None:
        error["error_subcode"] = subcode
    return {"error": error}


@pytest.mark.parametrize(
    ("status", "body", "code", "retryable"),
    [
        (400, fixture("error_190_expired.json"), "account_needs_reconnect", False),
        (400, fixture("error_window_closed.json"), "reply_window_closed", False),
        (400, graph_error(551), "recipient_unavailable", False),
        (400, fixture("error_4_rate_limit.json"), "platform_rate_limited", True),
        (400, graph_error(17), "platform_rate_limited", True),
        (400, graph_error(613), "platform_rate_limited", True),
        (429, None, "platform_rate_limited", True),
        (400, graph_error(9007, 2207008), "platform_unavailable", True),
        (400, graph_error(9, 2207042), "platform_rejected", False),
        (500, graph_error(2), "platform_unavailable", True),
        (503, None, "platform_unavailable", True),
        (400, graph_error(100), "platform_rejected", False),
        (400, "not json", "platform_rejected", False),
    ],
)
def test_graph_errors_map_to_our_codes(status: int, body: Any, code: str, retryable: bool) -> None:
    error = map_graph_error(status, body)
    assert (error.code, error.retryable) == (code, retryable)


def test_the_platform_code_and_message_are_kept_for_the_log() -> None:
    error = map_graph_error(400, fixture("error_190_expired.json"))
    assert error.platform_code == "190/463"
    assert "Session has expired" in error.message


def test_a_rate_limit_reads_the_regain_time_from_the_usage_header() -> None:
    usage = {"17841400000000001": [{"type": "messenger", "estimated_time_to_regain_access": 3}]}
    error = map_graph_error(
        400,
        fixture("error_4_rate_limit.json"),
        {"X-Business-Use-Case-Usage": json.dumps(usage)},
    )
    assert error.is_rate_limit
    assert error.retry_after_s == 180


def _adapter(**settings: Any) -> InstagramAdapter:
    config = Settings(
        _env_file=None,
        app_env=AppEnv.TEST,
        database_url="postgresql+asyncpg://x/y",
        database_url_direct="postgresql://x/y",
        redis_url="redis://x",
        **settings,
    )
    return InstagramAdapter(
        PlatformDeps(http=None, cipher=TokenCipher([new_key()]), settings=config)
    )  # type: ignore[arg-type]


def test_insights_need_the_insights_scope() -> None:
    adapter = _adapter()
    without = SocialAccount(scopes=list(oauth.BASE_SCOPES))
    with_scope = SocialAccount(scopes=[*oauth.BASE_SCOPES, oauth.INSIGHTS_SCOPE])
    assert Capability.POST_INSIGHTS not in adapter.capabilities_for(without)
    assert Capability.ACCOUNT_INSIGHTS not in adapter.capabilities_for(without)
    assert Capability.POST_INSIGHTS in adapter.capabilities_for(with_scope)


def test_human_agent_follows_its_flag() -> None:
    acct = SocialAccount(scopes=list(oauth.BASE_SCOPES))
    assert Capability.HUMAN_AGENT not in _adapter().capabilities_for(acct)
    assert Capability.HUMAN_AGENT in _adapter(ig_human_agent_enabled=True).capabilities_for(acct)


def test_require_raises_capability_unavailable() -> None:
    require(frozenset({Capability.DM_SEND}), Capability.DM_SEND)
    with pytest.raises(ApiError) as caught:
        require(frozenset({Capability.DM_SEND}), Capability.PUBLISH)
    assert caught.value.code == "capability_unavailable"
