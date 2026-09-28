"""Operational endpoints (SEC-12).

/healthz says only that the process is up. /readyz checks Postgres and Valkey; outside local and
test environments it needs ``Authorization: Bearer {METRICS_TOKEN}`` so it is not public.
"""

from __future__ import annotations

import hmac
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text

from socialhood.errors import ApiError
from socialhood.settings import Settings

router = APIRouter(include_in_schema=False)


class Health(BaseModel):
    status: Literal["ok"]


class Ready(BaseModel):
    status: Literal["ready"]
    checks: dict[str, str]


@router.get("/healthz")
async def healthz() -> Health:
    return Health(status="ok")


@router.get("/readyz")
async def readyz(request: Request) -> Ready:
    settings: Settings = request.app.state.settings
    if not settings.is_local:
        expected = settings.metrics_token.get_secret_value() if settings.metrics_token else ""
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not expected or not hmac.compare_digest(expected, supplied):
            raise ApiError("not_found")

    checks: dict[str, str] = {}
    try:
        async with request.app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "failed"
    try:
        await request.app.state.redis.ping()
        checks["valkey"] = "ok"
    except Exception:
        checks["valkey"] = "failed"

    if any(v != "ok" for v in checks.values()):
        failed = ", ".join(k for k, v in checks.items() if v != "ok")
        raise ApiError("service_unavailable", f"Not ready: {failed}")
    return Ready(status="ready", checks=checks)
