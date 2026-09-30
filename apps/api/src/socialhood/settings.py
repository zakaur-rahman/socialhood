"""Application settings (§2.16).

Every variable comes from the environment. DATABASE_URL, DATABASE_URL_DIRECT and REDIS_URL are
always required (no hard-coded fallbacks). In production, every variable without a default is
required too, and startup fails with the full list of what is missing. SEC-14: production
refuses development features.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppEnv(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


CommaList = Annotated[list[str], NoDecode]

# Settings without a default that production must provide (§2.16). Checked together so the
# error lists everything at once.
REQUIRED_IN_PRODUCTION: tuple[str, ...] = (
    "api_base_url",
    "web_base_url",
    "cors_allowed_origins",
    "sentry_dsn",
    "metrics_token",
    "clerk_secret_key",
    "clerk_jwt_key",
    "clerk_issuer",
    "clerk_authorized_parties",
    "clerk_webhook_secret",
    "token_encryption_keys",
    "ig_app_id",
    "ig_app_secret",
    "ig_redirect_uri",
    "ig_webhook_verify_token",
    "meta_app_id",
    "meta_app_secret",
    "whatsapp_config_id",
    "whatsapp_webhook_verify_token",
    "gemini_api_key",
    "cloudinary_cloud_name",
    "cloudinary_api_key",
    "cloudinary_api_secret",
    "dodo_api_key",
    "dodo_webhook_secret",
    "dodo_product_pro_monthly",
    "resend_api_key",
    "vapid_public_key",
    "vapid_private_key",
    "client_ip_header",
)


class ConfigurationError(RuntimeError):
    """Raised at startup when settings are missing or unsafe."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_env: AppEnv = AppEnv.LOCAL
    api_base_url: str | None = None
    web_base_url: str | None = None
    cors_allowed_origins: CommaList = Field(default_factory=list)

    database_url: str
    database_url_direct: str
    bulk_concurrency_per_workspace: int = Field(default=4, ge=1, le=64)
    redis_url: str

    log_level: str = "INFO"
    sentry_dsn: str | None = None
    # Share of requests and jobs traced (0 = errors only); T9.3.
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    # Release tag on errors: SENTRY_RELEASE, else the commit Render deploys (RENDER_GIT_COMMIT).
    sentry_release: str | None = Field(
        default=None, validation_alias=AliasChoices("sentry_release", "render_git_commit")
    )
    metrics_token: SecretStr | None = None

    clerk_secret_key: SecretStr | None = None
    clerk_jwt_key: str | None = None
    clerk_issuer: str | None = None
    clerk_authorized_parties: CommaList = Field(default_factory=list)
    clerk_webhook_secret: SecretStr | None = None

    token_encryption_keys: CommaList = Field(default_factory=list)

    ig_app_id: str | None = None
    ig_app_secret: SecretStr | None = None
    ig_redirect_uri: str | None = None
    ig_webhook_verify_token: SecretStr | None = None
    ig_graph_version: str = "v25.0"
    meta_graph_version: str = "v25.0"
    ig_request_insights_scope: bool = False
    ig_human_agent_enabled: bool = False

    meta_app_id: str | None = None
    meta_app_secret: SecretStr | None = None
    whatsapp_config_id: str | None = None
    whatsapp_webhook_verify_token: SecretStr | None = None

    gemini_api_key: SecretStr | None = None
    ai_provider: Literal["gemini", "fake"] = "gemini"  # fake: run without a key (TR-AI-01)
    ai_model_analysis: str = "gemini-3.5-flash-lite"
    ai_model_reply: str = "gemini-3.5-flash-lite"
    ai_model_reply_complex: str = "gemini-3.8-flash"
    ai_model_embed: str = "gemini-embedding-2"
    # Ask Social Hood's planner and report (TR-AGT-02); unset: AI_MODEL_REPLY.
    ai_model_agent: str | None = None
    ai_embed_dim: int = 768
    # Thinking level per model id, JSON (TR-AI-03); unset: "minimal" for Flash-Lite, else "low".
    ai_thinking_levels: dict[str, str] = Field(default_factory=dict)
    ai_daily_spend_limit_usd: float = 100.0
    ai_retrieval_min_sim: float = 0.60
    auto_min_confidence: float = 0.75

    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: SecretStr | None = None

    dodo_api_key: SecretStr | None = None
    dodo_environment: str = "test"
    dodo_webhook_secret: SecretStr | None = None
    dodo_product_pro_monthly: str | None = None
    dodo_product_max_monthly: str | None = None
    # fake: run without Dodo (billing/dodo_fake.py); refused in production. Tests swap the client
    # with billing.registry.use_dodo whatever this says.
    dodo_provider: Literal["dodo", "fake"] = "dodo"

    resend_api_key: SecretStr | None = None
    email_from: str = "Social Hood <hello@socialhood.com>"
    # fake: keep emails in memory (notify/email_fake.py); refused in production.
    email_provider: Literal["resend", "fake"] = "resend"

    vapid_public_key: str | None = None
    vapid_private_key: SecretStr | None = None
    vapid_subject: str = "mailto:support@socialhood.com"
    # fake: keep pushes in memory (notify/push_fake.py); refused in production.
    push_provider: Literal["webpush", "fake"] = "webpush"

    sandbox_platform_enabled: bool = False

    # TR-API-07 (security/ratelimit.py). Off only for local load or end-to-end runs; refused in
    # production. CLIENT_IP_HEADER names the header that carries the caller's address; required
    # in production, where the socket peer is the proxy. On Render it is x-forwarded-for, read
    # from the right past the proxies (security/client_ip.py), because its first entry is
    # whatever the client sent. Any other header is taken as it is.
    rate_limits_enabled: bool = True
    client_ip_header: str | None = None

    @field_validator(
        "cors_allowed_origins", "clerk_authorized_parties", "token_encryption_keys", mode="before"
    )
    @classmethod
    def _split_commas(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _asyncpg_driver(cls, value: str) -> str:
        # Render hands out postgresql://… (infra/render.yaml links it); the engine needs asyncpg.
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+asyncpg://" + value[len(prefix) :]
        return value

    @field_validator("clerk_jwt_key")
    @classmethod
    def _pem_newlines(cls, value: str | None) -> str | None:
        # Hosts often store a PEM on one line with literal backslash-n sequences.
        return value.replace("\\n", "\n").strip() if value else value

    @field_validator("log_level")
    @classmethod
    def _upper_level(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _production_rules(self) -> Settings:
        if self.app_env is not AppEnv.PRODUCTION:
            return self
        missing = [
            name.upper() for name in REQUIRED_IN_PRODUCTION if _is_empty(getattr(self, name))
        ]
        unsafe = []
        if self.sandbox_platform_enabled:
            unsafe.append("SANDBOX_PLATFORM_ENABLED must be false in production")
        if self.log_level == "DEBUG":
            unsafe.append("LOG_LEVEL must not be DEBUG in production")
        if not self.rate_limits_enabled:
            unsafe.append("RATE_LIMITS_ENABLED must be true in production")
        for name in ("ai_provider", "dodo_provider", "email_provider", "push_provider"):
            if getattr(self, name) == "fake":
                unsafe.append(f"{name.upper()} must not be fake in production")
        problems = []
        if missing:
            problems.append("missing: " + ", ".join(missing))
        problems.extend(unsafe)
        if problems:
            raise ConfigurationError("Invalid production settings: " + "; ".join(problems))
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.PRODUCTION

    @property
    def is_local(self) -> bool:
        return self.app_env in (AppEnv.LOCAL, AppEnv.TEST)


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, SecretStr):
        return value.get_secret_value() == ""
    if isinstance(value, str | list):
        return len(value) == 0
    return False


@lru_cache
def get_settings() -> Settings:
    return Settings()  # required values come from the environment
