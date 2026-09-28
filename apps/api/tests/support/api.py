"""The API under test: an app wired to the test database, a mocked Clerk, and signed users."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
import respx
from fastapi import FastAPI

from socialhood.jobs.app import app as jobs_app
from socialhood.main import create_app
from socialhood.settings import AppEnv, Settings
from tests.support.identity import (
    ISSUER,
    PARTY,
    WEBHOOK_SECRET,
    Keys,
    clerk_user,
    make_keys,
    make_token,
)

CLERK_USERS_URL = "https://api.clerk.com/v1/users/"


@pytest.fixture(scope="session")
def keys() -> Keys:
    return make_keys()


@pytest.fixture
def api_settings(keys: Keys) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnv.TEST,
        clerk_jwt_key=keys.public_pem,
        clerk_issuer=ISSUER,
        clerk_authorized_parties=[PARTY],
        clerk_secret_key="fake-clerk-secret-for-tests",
        clerk_webhook_secret=WEBHOOK_SECRET,
    )


@pytest.fixture
async def app(api_settings: Settings, clean_db: None) -> AsyncIterator[FastAPI]:
    application = create_app(api_settings)
    yield application
    await application.state.http.aclose()
    await application.state.redis.aclose()
    await application.state.engine.dispose()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as c:
        yield c


@pytest.fixture
async def queue() -> AsyncIterator[None]:
    """Open the job queue (the API defers jobs) and empty it around the test."""
    async with jobs_app.open_async():
        await _clear_queue()
        yield
        await _clear_queue()


async def _clear_queue() -> None:
    await jobs_app.connector.execute_query_async(
        "TRUNCATE procrastinate_periodic_defers, procrastinate_events, procrastinate_jobs CASCADE"
    )


@dataclass
class Clerk:
    """A fake Clerk Backend API plus a token factory for its users."""

    keys: Keys
    router: respx.MockRouter
    users: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, clerk_id: str | None = None, **profile: Any) -> str:
        clerk_id = clerk_id or f"user_{uuid.uuid4().hex[:12]}"
        self.users[clerk_id] = clerk_user(clerk_id, **profile)
        return clerk_id

    def headers(self, clerk_id: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(self.keys, clerk_id)}"}

    def _respond(self, request: httpx.Request) -> httpx.Response:
        clerk_id = request.url.path.rsplit("/", 1)[-1]
        if clerk_id not in self.users:
            return httpx.Response(404, json={"errors": [{"code": "resource_not_found"}]})
        return httpx.Response(200, json=self.users[clerk_id])


@pytest.fixture
def clerk(keys: Keys) -> Iterator[Clerk]:
    with respx.mock(assert_all_called=False) as router:
        fake = Clerk(keys=keys, router=router)
        router.get(url__startswith=CLERK_USERS_URL).mock(side_effect=fake._respond)
        yield fake


async def sign_in(
    client: httpx.AsyncClient, clerk: Clerk, **profile: Any
) -> tuple[str, dict[str, Any]]:
    """Create a Clerk user, make the first request as them, and return (clerk id, /v1/me)."""
    clerk_id = clerk.add(**profile)
    response = await client.get("/v1/me", headers=clerk.headers(clerk_id))
    assert response.status_code == 200, response.text
    return clerk_id, response.json()
