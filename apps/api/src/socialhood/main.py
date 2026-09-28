"""FastAPI application factory (TR-ARC-01). Run with ``uvicorn socialhood.main:app``."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from socialhood import __version__
from socialhood.api import health
from socialhood.api import v1 as api_v1
from socialhood.api.middleware import RequestContextMiddleware
from socialhood.api.openapi_errors import problem_openapi
from socialhood.api.problems import install_problem_handlers
from socialhood.db.engine import make_engine, make_sessionmaker
from socialhood.jobs.app import app as jobs_app
from socialhood.jobs.runtime import make_http_client
from socialhood.kv import make_redis
from socialhood.observability.logging import configure_logging
from socialhood.settings import Settings, get_settings
from socialhood.webhooks import clerk as clerk_webhook


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # The API only defers jobs; workers run them (TR-ARC-02).
        async with jobs_app.open_async():
            yield
        await app.state.http.aclose()
        await app.state.redis.aclose()
        await app.state.engine.dispose()

    app = FastAPI(
        title="Social Hood API",
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
    app.openapi = lambda: problem_openapi(app)  # type: ignore[method-assign]
    app.include_router(health.router)
    for router in api_v1.ROUTERS:
        app.include_router(router)
    app.include_router(clerk_webhook.router)

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
