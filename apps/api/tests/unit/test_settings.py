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
    for name in ("cors_allowed_origins", "clerk_authorized_parties", "token_encryption_keys"):
        values[name] = "a,b"
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


def test_production_refuses_debug_logging() -> None:
    values = complete_production()
    values["log_level"] = "debug"
    with pytest.raises(ConfigurationError, match="LOG_LEVEL"):
        make(**values)


def test_complete_production_settings_load() -> None:
    settings = make(**complete_production())
    assert settings.is_production
    assert settings.cors_allowed_origins == ["a", "b"]
    assert settings.rate_limits_enabled


@pytest.mark.parametrize(
    "name", ["ai_provider", "dodo_provider", "email_provider", "push_provider"]
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


@pytest.mark.parametrize("scheme", ["postgresql", "postgres"])
def test_a_plain_database_url_gets_the_asyncpg_driver(scheme: str) -> None:
    # Render links its connection string (postgresql://…) straight into DATABASE_URL (T9.5).
    settings = make(**{**BASE, "database_url": f"{scheme}://u:p@db/x"})
    assert settings.database_url == "postgresql+asyncpg://u:p@db/x"
    assert settings.database_url_direct == "postgresql://u:p@db/x"
