"""T9.3, SEC-12, TR-OPS-01: /metrics behind the token, the shared Valkey registry, and the
metrics each alert in infra/prometheus/alerts.yml reads (a forced failure moves its metric)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from socialhood.ai.metering import metered
from socialhood.ai.provider import AIError
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.tasks.maintenance import ping
from socialhood.observability.metrics import BUFFER, JOB_RUNS, flush
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.inbox import make_account, make_scheduled, make_thread, make_workspace
from tests.support.sending import (
    clean_outbox,
    post_message,
    run_send,
    use_app_runtime,
    workspace_with_thread,
)

TOKEN = "metrics-token-for-tests"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return api_settings.model_copy(update={"metrics_token": SecretStr(TOKEN)})


@pytest.fixture(autouse=True)
def empty_buffer() -> Iterator[None]:
    BUFFER.clear()
    yield
    BUFFER.clear()


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


async def scrape(client: httpx.AsyncClient) -> str:
    response = await client.get("/metrics", headers=AUTH)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    return response.text


def value(body: str, series: str) -> float:
    """The value of one exact series line, e.g. 'socialhood_x{a="b"}'; 0 when absent."""
    match = re.search(rf"^{re.escape(series)} (\S+)$", body, re.M)
    return float(match.group(1)) if match else 0.0


# ---------------------------------------------------------------- the endpoint


async def test_metrics_needs_the_bearer_token(client: httpx.AsyncClient, redis: Redis) -> None:
    assert (await client.get("/metrics")).status_code == 401
    wrong = await client.get("/metrics", headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401
    basic = await client.get("/metrics", headers={"Authorization": f"Basic {TOKEN}"})
    assert basic.status_code == 401
    assert (await client.get("/metrics", headers=AUTH)).status_code == 200


async def test_metrics_does_not_exist_without_a_token(
    api_settings: Settings, clean_db: None, redis: Redis
) -> None:
    from socialhood.main import create_app

    app = create_app(api_settings.model_copy(update={"metrics_token": None}))
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
            response = await client.get("/metrics", headers=AUTH)
        assert response.status_code == 404
    finally:
        await app.state.http.aclose()
        await app.state.redis.aclose()
        await app.state.engine.dispose()


async def test_requests_are_counted_by_route_template(
    client: httpx.AsyncClient, redis: Redis
) -> None:
    workspace = str(uuid.uuid4())
    await client.get("/healthz")
    await client.get(f"/v1/w/{workspace}/conversations")  # 401: matched, not signed in
    await client.get("/no/such/route")
    body = await scrape(client)
    assert (
        value(body, 'socialhood_http_requests_total{method="GET",route="/healthz",status="200"}')
        == 1
    )
    assert (
        value(
            body,
            'socialhood_http_requests_total{method="GET",route="/v1/w/{wid}/conversations",'
            'status="401"}',
        )
        == 1
    )
    assert (
        value(body, 'socialhood_http_requests_total{method="GET",route="unmatched",status="404"}')
        == 1
    )
    assert (
        value(body, 'socialhood_http_request_duration_seconds_count{method="GET",route="/healthz"}')
        == 1
    )
    # Raw paths and ids never become labels.
    assert workspace not in body
    assert "/no/such/route" not in body


async def test_unsigned_webhooks_count_as_failed_deliveries(
    client: httpx.AsyncClient, redis: Redis
) -> None:
    """How staging forces the webhook-failure alert (docs/ops/alerts.md)."""
    for _ in range(3):
        response = await client.post("/webhooks/instagram", content=b"{}")
        assert response.status_code == 401
    body = await scrape(client)
    assert (
        value(
            body,
            'socialhood_webhook_deliveries_total{provider="instagram",outcome="signature_invalid"}',
        )
        == 3
    )


# ---------------------------------------------------------------- the shared registry


async def test_counts_from_another_process_reach_the_scrape_through_valkey(
    client: httpx.AsyncClient, redis: Redis
) -> None:
    JOB_RUNS.inc(task="send_message", lane="interactive", status="failed")
    assert await flush(redis) == 1  # what the worker's flusher does
    JOB_RUNS.inc(task="send_message", lane="interactive", status="failed")
    await flush(redis)  # a second worker, or the same one later: totals add up
    body = await scrape(client)
    series = 'socialhood_job_runs_total{task="send_message",lane="interactive",status="failed"}'
    assert value(body, series) == 2
    assert value(await scrape(client), series) == 2  # a scrape does not double-count


async def test_a_failed_flush_keeps_the_counts() -> None:
    down = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    JOB_RUNS.inc(task="ping", lane="interactive", status="succeeded")
    try:
        assert await flush(down) == 0
    finally:
        await down.aclose()
    assert len(BUFFER.drain()) == 1


# ---------------------------------------------------------------- scrape-time gauges


async def test_queue_depth_and_oldest_ready_job_per_lane(
    client: httpx.AsyncClient, redis: Redis, queue: None
) -> None:
    await enqueue(ping, key="ping:metrics-1", timestamp=1)
    await enqueue(ping, key="ping:metrics-2", timestamp=2)
    await enqueue(ping, key="ping:metrics-3", lane="bulk", delay_s=600, timestamp=3)
    await ping.configure().defer_async(timestamp=4)  # a plain defer counts too
    body = await scrape(client)
    assert value(body, 'socialhood_queue_ready_jobs{lane="interactive"}') == 3
    assert value(body, 'socialhood_queue_ready_jobs{lane="bulk"}') == 0
    assert value(body, 'socialhood_queue_scheduled_jobs{lane="bulk"}') == 1
    assert value(body, 'socialhood_queue_oldest_ready_seconds{lane="interactive"}') >= 0
    assert 'socialhood_queue_oldest_ready_seconds{lane="bulk"} 0' in body
    assert value(body, 'socialhood_collector_up{collector="queue"}') == 1


async def test_an_old_ready_job_shows_its_age(
    client: httpx.AsyncClient, redis: Redis, queue: None, engine: AsyncEngine
) -> None:
    await enqueue(ping, key="ping:old", timestamp=1)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE procrastinate_events SET at = now() - interval '45 seconds'"
                " WHERE type = 'deferred'"
            )
        )
    body = await scrape(client)
    assert value(body, 'socialhood_queue_oldest_ready_seconds{lane="interactive"}') >= 44


async def test_dispatcher_lag_is_the_oldest_due_row(
    client: httpx.AsyncClient, redis: Redis, engine: AsyncEngine
) -> None:
    """How staging forces the dispatcher-lag alert: stop the worker while a message is due."""
    body = await scrape(client)
    assert value(body, 'socialhood_dispatcher_lag_seconds{kind="message"}') == 0

    wid = await make_workspace(engine)
    account = await make_account(engine, wid)
    thread = await make_thread(engine, workspace_id=wid, account_id=account)
    now = datetime.now(UTC)
    await make_scheduled(
        engine,
        workspace_id=wid,
        conversation_id=thread.conversation_id,
        send_at=now - timedelta(minutes=3),
    )
    await make_scheduled(
        engine,
        workspace_id=wid,
        conversation_id=thread.conversation_id,
        send_at=now + timedelta(hours=1),
    )
    body = await scrape(client)
    assert 175 <= value(body, 'socialhood_dispatcher_lag_seconds{kind="message"}') < 600
    assert value(body, 'socialhood_dispatcher_lag_seconds{kind="post"}') == 0


async def test_sse_connections_and_build_info_are_exported(
    client: httpx.AsyncClient, redis: Redis
) -> None:
    body = await scrape(client)
    assert "socialhood_sse_connections 0" in body
    assert 'socialhood_build_info{version="' in body
    assert 'environment="test"} 1' in body


# ---------------------------------------------------------------- sends and AI calls


async def test_send_failures_are_counted(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    queue: None,
    redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """How staging forces the send-failure alert: sandbox sends with a failure directive."""
    use_app_runtime(app, monkeypatch)
    setup = await workspace_with_thread(client, clerk, engine)
    ok = (await post_message(client, setup, text="Yes, we ship")).json()
    bad = (await post_message(client, setup, text="Price [sandbox:fail=platform_rejected]")).json()
    await run_send(setup, ok)
    await run_send(setup, bad)

    body = await scrape(client)
    assert value(body, 'socialhood_sends_total{platform="instagram",outcome="sent",code=""}') == 1
    assert (
        value(
            body,
            'socialhood_sends_total{platform="instagram",outcome="failed",code="platform_rejected"}',
        )
        == 1
    )


async def test_ai_errors_are_counted(
    client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    """How staging forces the AI-error alert: a model id the provider rejects."""
    wid = await make_workspace(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with metered(maker, workspace_id=wid, feature="message_analysis"):
        pass
    with pytest.raises(AIError):
        async with metered(maker, workspace_id=wid, feature="message_analysis"):
            raise AIError("provider_error", "HTTP 404 NOT_FOUND")

    body = await scrape(client)
    ok = 'socialhood_ai_calls_total{feature="message_analysis",model="unknown",outcome="ok"}'
    error = 'socialhood_ai_calls_total{feature="message_analysis",model="unknown",outcome="error"}'
    assert (value(body, ok), value(body, error)) == (1, 1)
