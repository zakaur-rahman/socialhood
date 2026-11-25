"""The daily storage check: Cloudinary's credit usage, alerted once per level per month."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr
from redis.asyncio import Redis

from socialhood.jobs.tasks.maintenance import check_storage_usage
from socialhood.notify.email import EmailError
from socialhood.notify.email_fake import FakeEmail
from socialhood.settings import Settings

NOW = datetime(2026, 11, 25, 6, 15, tzinfo=UTC)


@pytest.fixture
def settings(api_settings: Settings) -> Settings:
    return api_settings.model_copy(
        update={
            "cloudinary_cloud_name": "demo",
            "cloudinary_api_key": "key",
            "cloudinary_api_secret": SecretStr("secret"),
            "ops_alert_email": "ops@example.com",
            "cloudinary_alert_percent": 70.0,
        }
    )


def usage(body: dict[str, object]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1_1/demo/usage"
        return httpx.Response(200, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_below_the_level_nothing_is_sent(
    settings: Settings, redis: Redis, fake_email: FakeEmail
) -> None:
    async with usage({"credits": {"usage": 10, "limit": 25, "used_percent": 40.0}}) as http:
        assert await check_storage_usage(http, redis, settings, NOW) == 40.0
    assert fake_email.outbox == []


async def test_each_level_alerts_once_a_month(
    settings: Settings, redis: Redis, fake_email: FakeEmail
) -> None:
    async with usage({"credits": {"used_percent": 72.4}}) as http:
        await check_storage_usage(http, redis, settings, NOW)
        await check_storage_usage(http, redis, settings, NOW)  # the next day: no second email
    assert len(fake_email.sent_to("ops@example.com")) == 1
    assert "72%" in fake_email.outbox[0].subject

    async with usage({"credits": {"used_percent": 91.0}}) as http:  # the louder level still alerts
        await check_storage_usage(http, redis, settings, NOW)
    assert len(fake_email.outbox) == 2


async def test_usage_over_limit_when_no_percent(
    settings: Settings, redis: Redis, fake_email: FakeEmail
) -> None:
    async with usage({"credits": {"usage": 20, "limit": 25}}) as http:
        assert await check_storage_usage(http, redis, settings, NOW) == pytest.approx(80.0)
    assert len(fake_email.outbox) == 1


async def test_a_failed_email_tries_again_next_time(
    settings: Settings, redis: Redis, fake_email: FakeEmail
) -> None:
    fake_email.fail_next(EmailError("down", retryable=True))
    async with usage({"credits": {"used_percent": 75.0}}) as http:
        await check_storage_usage(http, redis, settings, NOW)
        assert fake_email.outbox == []
        await check_storage_usage(http, redis, settings, NOW)
    assert len(fake_email.outbox) == 1


async def test_unconfigured_cloudinary_is_skipped(settings: Settings, redis: Redis) -> None:
    async with usage({}) as http:
        assert (
            await check_storage_usage(
                http, redis, settings.model_copy(update={"cloudinary_cloud_name": None}), NOW
            )
            is None
        )
