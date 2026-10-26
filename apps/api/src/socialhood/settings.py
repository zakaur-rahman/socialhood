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
from urllib.parse import urlsplit

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
    # GR-15: the address tracked links (/l/<code>) are built on, if not the API's own, such as a
    # short domain pointed at the API. Neither set: link buttons are sent as written.
    link_base_url: str | None = None
    cors_allowed_origins: CommaList = Field(default_factory=list)

    database_url: str
    database_url_direct: str
    bulk_concurrency_per_workspace: int = Field(default=4, ge=1, le=64)
    # The largest video a post upload accepts, in MB (C-134). Cloudinary's free plan stops single
    # uploads at 100 MB; above that the browser sends the file in chunks and the plan must allow
    # large files. Instagram takes Reels up to 300 MB.
    post_video_max_mb: int = Field(default=100, ge=10, le=300)
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
    # fake: keep team invitations in memory (auth/invitations.py); refused in production. Tests
    # swap the sender with auth.invitations.use_invitation_sender whatever this says.
    clerk_invitations_provider: Literal["clerk", "fake"] = "clerk"

    token_encryption_keys: CommaList = Field(default_factory=list)

    ig_app_id: str | None = None
    ig_app_secret: SecretStr | None = None
    ig_redirect_uri: str | None = None
    ig_webhook_verify_token: SecretStr | None = None
    ig_graph_version: str = "v25.0"
    meta_graph_version: str = "v25.0"
    ig_request_insights_scope: bool = False
    # C-131: ask Facebook Pages for read_insights, which Page post insights need (a Meta App
    # Review item, O-10). Off: Pages connect without it and show no post insights.
    fb_request_insights_scope: bool = False
    ig_human_agent_enabled: bool = False

    meta_app_id: str | None = None
    meta_app_secret: SecretStr | None = None
    # GR-29 Facebook Pages: Facebook Login's redirect URI (api/v1/oauth/facebook/callback) and the
    # verify token of the Page webhook (/webhooks/facebook, signed with META_APP_SECRET). Neither
    # set: Facebook connections are off. Messenger's 7-day HUMAN_AGENT window follows
    # IG_HUMAN_AGENT_ENABLED: Meta approves Human Agent once for the app.
    fb_redirect_uri: str | None = None
    fb_webhook_verify_token: SecretStr | None = None
    whatsapp_config_id: str | None = None
    whatsapp_webhook_verify_token: SecretStr | None = None

    gemini_api_key: SecretStr | None = None
    ai_provider: Literal["gemini", "fake"] = "gemini"  # fake: run without a key (TR-AI-01)
    ai_model_analysis: str = "gemini-3.5-flash-lite"
    ai_model_reply: str = "gemini-3.5-flash-lite"
    ai_model_reply_complex: str = "gemini-3.8-flash"
    ai_model_embed: str = "gemini-embedding-2"
    # Ask Amplychat's planner and report (TR-AGT-02); unset: AI_MODEL_REPLY.
    ai_model_agent: str | None = None
    ai_embed_dim: int = 768
    # GR-38: Ask Amplychat's runs expose typed visuals (cards, ranked posts, sentiment) beside
    # the answer. Off: ``visuals`` is always empty and the prompt doesn't mention them.
    agent_visuals_enabled: bool = False
    # GR-23: WhatsApp broadcasts. Off by default until the legal check of marketing consent in
    # India (O-11) is done: off, the routes answer 404 "not available yet" (except the availability
    # check the web asks), nothing is dispatched and the web shows nothing.
    broadcasts_enabled: bool = False
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
    email_from: str = "Amplychat <support@amplychat.com>"
    # fake: keep emails in memory (notify/email_fake.py); refused in production.
    email_provider: Literal["resend", "fake"] = "resend"

    vapid_public_key: str | None = None
    vapid_private_key: SecretStr | None = None
    vapid_subject: str = "mailto:support@amplychat.com"
    # fake: keep pushes in memory (notify/push_fake.py); refused in production.
    push_provider: Literal["webpush", "fake"] = "webpush"

    # GR-27: Google Sheets sync. The OAuth client of the "drive.file" scope (not required: the
    # card says "not set up" without them). fake: keep sheets in memory, or in Redis where the API
    # and the worker are separate processes (google/fake.py); refused in production.
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str | None = None
    google_provider: Literal["google", "fake"] = "google"

    # GR-31: the Shopify app (owner track O-10: a Partner account and an app listing). All unset by
    # default: connecting Shopify then answers 503 "not configured" and the webhook route refuses.
    # The API key and secret are the app's client credentials (the secret also signs the webhooks
    # and the install redirect). fake: a built-in store for development and the end-to-end stack
    # (shopify/fake.py); refused in production.
    shopify_api_key: str | None = None
    shopify_api_secret: SecretStr | None = None
    shopify_redirect_uri: str | None = None
    shopify_scopes: str = "read_products"
    shopify_api_version: str = "2025-07"
    shopify_provider: Literal["shopify", "fake"] = "shopify"

    # GR-32: Razorpay payment links use each business's own keys (stored per workspace, encrypted),
    # so there are no app-wide credentials. fake: a sandbox that accepts rzp_test_ keys, for
    # development and the end-to-end stack (razorpay/fake.py); refused in production.
    razorpay_provider: Literal["razorpay", "fake"] = "razorpay"

    sandbox_platform_enabled: bool = False
    # GR-04: outbound webhooks may go to private and local addresses (development and e2e, which
    # receive them locally); refused in production (security/ssrf.py).
    webhooks_allow_private: bool = False
    # GR-35: a website crawl may read private and local addresses (development and e2e, which crawl
    # a local fixture site); refused in production (security/ssrf.py).
    crawl_allow_private: bool = False

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
        if self.webhooks_allow_private:
            unsafe.append("WEBHOOKS_ALLOW_PRIVATE must be false in production")
        if self.crawl_allow_private:
            unsafe.append("CRAWL_ALLOW_PRIVATE must be false in production")
        if self.log_level == "DEBUG":
            unsafe.append("LOG_LEVEL must not be DEBUG in production")
        if not self.rate_limits_enabled:
            unsafe.append("RATE_LIMITS_ENABLED must be true in production")
        unsafe.extend(self._origin_problems())
        for name in (
            "ai_provider",
            "dodo_provider",
            "email_provider",
            "push_provider",
            "clerk_invitations_provider",
            "google_provider",
            "shopify_provider",
            "razorpay_provider",
        ):
            if getattr(self, name) == "fake":
                unsafe.append(f"{name.upper()} must not be fake in production")
        problems = []
        if missing:
            problems.append("missing: " + ", ".join(missing))
        problems.extend(unsafe)
        if problems:
            raise ConfigurationError("Invalid production settings: " + "; ".join(problems))
        return self

    def _origin_problems(self) -> list[str]:
        # C-143: the browser-facing addresses are https, and the API trusts exact origins only
        # (no "*", no path), including the web app's own origin.
        problems = []
        for name in ("api_base_url", "web_base_url"):
            value = getattr(self, name)
            if value and _https_origin(value) is None:
                problems.append(f"{name.upper()} must be an https URL")
        for name in ("cors_allowed_origins", "clerk_authorized_parties"):
            values: list[str] = getattr(self, name)
            bad = [value for value in values if _https_origin(value) != value]
            if bad:
                problems.append(
                    f"{name.upper()} must list exact https origins (no path, no wildcard): "
                    + ", ".join(bad)
                )
            web = _https_origin(self.web_base_url or "")
            if web and values and web not in values:
                problems.append(f"{name.upper()} must include WEB_BASE_URL's origin {web}")
        return problems

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.PRODUCTION

    @property
    def is_local(self) -> bool:
        return self.app_env in (AppEnv.LOCAL, AppEnv.TEST)


def _https_origin(value: str) -> str | None:
    """'https://host[:port]' of an https URL, or None for anything else (http, '*', junk)."""
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return None
    if parts.scheme != "https" or not parts.hostname or "*" in parts.netloc:
        return None
    if parts.username or parts.password:
        return None
    return f"https://{parts.netloc.lower()}"


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
