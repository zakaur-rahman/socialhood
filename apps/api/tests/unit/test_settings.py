from __future__ import annotations

import pytest

from socialhood.settings import REQUIRED_IN_PRODUCTION, ConfigurationError, Settings

BASE = {
    "database_url": "postgresql+asyncpg://u:p@db/x",
    "database_url_direct": "postgresql://u:p@db/x",
    "redis_url": "redis://kv:6379/0",
}


def complete_production() -> dict[str, object]:
    values: dict[str, object] = {**BASE, "app_env": "production"}
    for name in REQUIRED_IN_PRODUCTION:
        values[name] = "x"
    values["api_base_url"] = "https://api.amplychat.com"
    values["web_base_url"] = "https://amplychat.com"
    for name in ("cors_allowed_origins", "clerk_authorized_parties"):
        values[name] = "https://amplychat.com,https://staging.amplychat.com"
    values["token_encryption_keys"] = "a,b"
    return values


def make(**values: object) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def test_local_settings_need_only_the_connection_urls() -> None:
    settings = make(**BASE)
    assert settings.is_local
    assert settings.ig_graph_version == "v25.0"


def test_connection_urls_have_no_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(ValueError, match="redis_url"):
        make(database_url="x", database_url_direct="y")


def test_production_lists_every_missing_variable() -> None:
    with pytest.raises(ConfigurationError) as info:
        make(**BASE, app_env="production")
    message = str(info.value)
    for name in REQUIRED_IN_PRODUCTION:
        assert name.upper() in message


def test_production_refuses_the_sandbox() -> None:
    values = complete_production()
    values["sandbox_platform_enabled"] = True
    with pytest.raises(ConfigurationError, match="SANDBOX_PLATFORM_ENABLED"):
        make(**values)


def test_production_refuses_private_webhook_addresses() -> None:
    values = complete_production()
    values["webhooks_allow_private"] = True
    with pytest.raises(ConfigurationError, match="WEBHOOKS_ALLOW_PRIVATE"):
        make(**values)


def test_production_refuses_private_crawl_addresses() -> None:
    values = complete_production()
    values["crawl_allow_private"] = True
    with pytest.raises(ConfigurationError, match="CRAWL_ALLOW_PRIVATE"):
        make(**values)


def test_production_refuses_debug_logging() -> None:
    values = complete_production()
    values["log_level"] = "debug"
    with pytest.raises(ConfigurationError, match="LOG_LEVEL"):
        make(**values)


def test_complete_production_settings_load() -> None:
    settings = make(**complete_production())
    assert settings.is_production
    assert settings.cors_allowed_origins == [
        "https://amplychat.com",
        "https://staging.amplychat.com",
    ]
    assert settings.rate_limits_enabled


@pytest.mark.parametrize(
    "name",
    [
        "ai_provider",
        "dodo_provider",
        "email_provider",
        "push_provider",
        "clerk_invitations_provider",
    ],
)
def test_production_refuses_fake_providers(name: str) -> None:
    # SEC-14: the in-memory fakes are development features.
    values = complete_production()
    values[name] = "fake"
    with pytest.raises(ConfigurationError, match=name.upper()):
        make(**values)


def test_production_refuses_disabled_rate_limits() -> None:
    # SEC-14, TR-API-07: the switch exists for local load and end-to-end runs only.
    values = complete_production()
    values["rate_limits_enabled"] = False
    with pytest.raises(ConfigurationError, match="RATE_LIMITS_ENABLED"):
        make(**values)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("cors_allowed_origins", "*"),
        ("cors_allowed_origins", "https://amplychat.com,http://amplychat.com"),
        ("cors_allowed_origins", "https://amplychat.com,https://*.amplychat.com"),
        ("cors_allowed_origins", "https://amplychat.com/"),
        ("clerk_authorized_parties", "https://amplychat.com,https://amplychat.com/app"),
        ("clerk_authorized_parties", "https://user@amplychat.com"),
    ],
)
def test_production_refuses_origins_that_are_not_exact_https(name: str, value: str) -> None:
    # C-143: CORS and Clerk's azp check compare exact origins; anything else is a mistake that
    # either opens the API to every site or silently refuses the real one.
    values = complete_production()
    values[name] = value
    with pytest.raises(ConfigurationError, match=name.upper()):
        make(**values)


@pytest.mark.parametrize("name", ["api_base_url", "web_base_url", "site_base_url"])
def test_production_refuses_plain_http_base_urls(name: str) -> None:
    values = complete_production()
    values[name] = "http://amplychat.com"
    with pytest.raises(ConfigurationError, match=name.upper()):
        make(**values)


def test_production_needs_the_web_origin_among_the_allowed_origins() -> None:
    # The canonical move (C-142) from app.amplychat.com to amplychat.com changes all three at once.
    values = complete_production()
    values["web_base_url"] = "https://app.amplychat.com"
    with pytest.raises(ConfigurationError, match="must include WEB_BASE_URL's origin"):
        make(**values)


def dashboard_production() -> dict[str, object]:
    # C-146: the app on dashboard.amplychat.com, the public site on the apex.
    values = complete_production()
    values["web_base_url"] = "https://dashboard.amplychat.com"
    values["site_base_url"] = "https://amplychat.com"
    values["cors_allowed_origins"] = "https://dashboard.amplychat.com,https://amplychat.com"
    values["clerk_authorized_parties"] = "https://dashboard.amplychat.com"
    return values


def test_production_accepts_the_app_and_the_site_on_two_origins() -> None:
    settings = make(**dashboard_production())
    assert settings.site_url == "https://amplychat.com"
    assert settings.web_base_url == "https://dashboard.amplychat.com"


def test_production_needs_the_site_origin_among_the_cors_origins() -> None:
    # The site's unsubscribe and data deletion pages call the API from the browser.
    values = dashboard_production()
    values["cors_allowed_origins"] = "https://dashboard.amplychat.com"
    with pytest.raises(ConfigurationError, match="must include SITE_BASE_URL's origin"):
        make(**values)


def test_production_needs_the_app_origin_among_the_authorized_parties() -> None:
    values = dashboard_production()
    values["clerk_authorized_parties"] = "https://amplychat.com"
    with pytest.raises(ConfigurationError, match="CLERK_AUTHORIZED_PARTIES must include WEB_BASE"):
        make(**values)


def test_the_site_url_falls_back_to_the_web_url() -> None:
    settings = make(**BASE, web_base_url="http://localhost:3000")
    assert settings.site_url == "http://localhost:3000"
    assert make(**BASE).site_url is None


def test_staging_keeps_its_own_origins() -> None:
    values = {**complete_production(), "app_env": "staging", "cors_allowed_origins": "*"}
    assert make(**values).cors_allowed_origins == ["*"]


@pytest.mark.parametrize("scheme", ["postgresql", "postgres"])
def test_a_plain_database_url_gets_the_asyncpg_driver(scheme: str) -> None:
    # Render links its connection string (postgresql://…) straight into DATABASE_URL (T9.5).
    settings = make(**{**BASE, "database_url": f"{scheme}://u:p@db/x"})
    assert settings.database_url == "postgresql+asyncpg://u:p@db/x"
    assert settings.database_url_direct == "postgresql://u:p@db/x"
