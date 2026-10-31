"""FastAPI application factory (TR-ARC-01). Run with ``uvicorn socialhood.main:app``."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from socialhood import __version__
from socialhood.api import health, public, public_hooks
from socialhood.api import v1 as api_v1
from socialhood.api.middleware import BodyLimitMiddleware, RequestContextMiddleware
from socialhood.api.openapi_errors import problem_openapi
from socialhood.api.problems import install_problem_handlers
from socialhood.db.engine import make_engine, make_sessionmaker
from socialhood.jobs.app import app as jobs_app
from socialhood.jobs.runtime import make_http_client
from socialhood.kv import make_redis
from socialhood.mcp import server as mcp_server
from socialhood.observability import http as observability_http
from socialhood.observability.logging import configure_logging, get_logger
from socialhood.observability.metrics import Flusher
from socialhood.observability.sentry import init_sentry, instrument_running_loop
from socialhood.settings import Settings, get_settings
from socialhood.webhooks import clerk as clerk_webhook
from socialhood.webhooks import dodo as dodo_webhook
from socialhood.webhooks import facebook as facebook_webhook
from socialhood.webhooks import instagram as instagram_webhook
from socialhood.webhooks import links as links_redirect
from socialhood.webhooks import meta_privacy
from socialhood.webhooks import razorpay as razorpay_webhook
from socialhood.webhooks import shopify as shopify_webhook
from socialhood.webhooks import whatsapp as whatsapp_webhook
from socialhood.widget import routes as widget_files

log = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    # Before the routers are added, so Sentry's FastAPI integration wraps them (no DSN: no-op).
    init_sentry(settings, component="api")
    if not settings.billing_enabled:
        # C-149: no Dodo settings. Every workspace stays on Free; checkout answers 503.
        log.warning("billing_off", detail="Dodo isn't configured: paid plans aren't on sale")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        instrument_running_loop()
        flusher = Flusher(app.state.redis)  # metrics buffer → Valkey (observability/metrics.py)
        flusher.start()
        # The API only defers jobs; workers run them (TR-ARC-02).
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(jobs_app.open_async())
            if app.state.mcp is not None:  # C-165: the MCP transport's task group
                await stack.enter_async_context(app.state.mcp.session_manager.run())
            yield
        await flusher.stop()
        await app.state.http.aclose()
        await app.state.redis.aclose()
        await app.state.engine.dispose()

    app = FastAPI(
        title="Amplychat API",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.settings = settings
    app.state.engine = make_engine(settings)
    app.state.sessionmaker = make_sessionmaker(app.state.engine)
    app.state.redis = make_redis(settings)
    app.state.http = make_http_client()

    install_problem_handlers(app)
    # The public API (GR-25) has its own document, api/public_openapi.py.
    app.openapi = lambda: problem_openapi(app, (public.router, public_hooks.router))  # type: ignore[method-assign]
    app.include_router(health.router)
    app.include_router(observability_http.router)  # /metrics behind METRICS_TOKEN (SEC-12)
    for router in api_v1.ROUTERS:
        app.include_router(router)
    app.include_router(public.router)  # GR-25: /public/v1, authenticated by an API key
    app.include_router(public_hooks.router)  # GR-26: the REST hooks Zapier triggers use
    app.include_router(clerk_webhook.router)
    app.include_router(dodo_webhook.router)
    app.include_router(instagram_webhook.router)
    app.include_router(facebook_webhook.router)
    app.include_router(shopify_webhook.router)  # GR-31: Shopify product webhooks
    app.include_router(razorpay_webhook.router)  # GR-32: Razorpay payment link webhooks
    app.include_router(meta_privacy.router)
    app.include_router(whatsapp_webhook.router)
    app.include_router(links_redirect.router)  # GR-15: /l/<code>, the tracked link redirect
    app.include_router(widget_files.router)  # GR-28: /widget.js and the chat frame
    # C-165: the MCP server at /mcp (an API key or, from phase C, an OAuth token).
    app.state.mcp = mcp_server.install(app, settings)

    # SEC-05: exact origins only, no credentials (bearer tokens, not cookies).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "Last-Event-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )
    app.add_middleware(BodyLimitMiddleware)
    # Request metrics and unhandled-error capture, just inside the request context (T9.3).
    app.add_middleware(observability_http.MetricsMiddleware)
    # Added last, so it is the outermost middleware.
    app.add_middleware(RequestContextMiddleware)
    return app


def __getattr__(name: str) -> FastAPI:
    # ``socialhood.main:app`` is built on first access, so importing this module (tests, the
    # OpenAPI script) does not need a full environment.
    if name == "app":
        application = create_app()
        globals()["app"] = application
        return application
    raise AttributeError(name)
