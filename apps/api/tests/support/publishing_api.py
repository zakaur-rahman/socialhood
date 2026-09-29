"""The publishing API under test (T7.1, T7.4): a signed-in owner's workspace with one connected
Instagram account (sandbox), and helpers to call the routes, make post uploads and read rows."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.api import Clerk, sign_in
from tests.support.inbox import make_account, make_asset
from tests.support.ingest import stream


def iso(at: datetime) -> str:
    return at.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def later(**delta: float) -> datetime:
    return datetime.now(UTC) + timedelta(**delta)


@dataclass
class Shop:
    app: FastAPI
    client: httpx.AsyncClient
    engine: AsyncEngine
    redis: Redis
    clerk: Clerk
    clerk_id: str
    wid: str
    account_id: uuid.UUID
    headers: dict[str, str]

    def url(self, path: str) -> str:
        return f"/v1/w/{self.wid}{path}"

    async def call(self, method: str, path: str, body: Any = None, **params: Any) -> httpx.Response:
        return await self.client.request(
            method, self.url(path), json=body, params=params or None, headers=self.headers
        )

    async def ok(
        self, method: str, path: str, body: Any = None, *, status: int = 200, **params: Any
    ) -> Any:
        response = await self.call(method, path, body, **params)
        assert response.status_code == status, f"{method} {path}: {response.text}"
        return response.json() if response.content else None

    async def problem(
        self, method: str, path: str, body: Any = None, *, status: int, **params: Any
    ) -> dict[str, Any]:
        response = await self.call(method, path, body, **params)
        assert response.status_code == status, f"{method} {path}: {response.text}"
        problem: dict[str, Any] = response.json()
        return problem

    async def fields(self, method: str, path: str, body: Any = None) -> dict[str, str]:
        """A 422's field errors as {field: message}."""
        problem = await self.problem(method, path, body, status=422)
        assert problem["code"] == "validation_error"
        return {e["field"]: e["message"] for e in problem["errors"]}

    # ---- rows

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), params)]

    async def one(self, sql: str, **params: Any) -> dict[str, Any]:
        [row] = await self.rows(sql, **params)
        return row

    async def execute(self, sql: str, **params: Any) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(sql), params)

    # ---- uploads and accounts

    async def image(self, *, width: int = 1080, height: int = 1350, **values: Any) -> uuid.UUID:
        return await make_asset(
            self.engine,
            workspace_id=self.wid,
            purpose="post",
            width=width,
            height=height,
            **values,
        )

    async def video(self, *, duration_s: float = 15.0, **values: Any) -> uuid.UUID:
        asset = await make_asset(
            self.engine,
            workspace_id=self.wid,
            purpose="post",
            resource_type="video",
            fmt="mp4",
            width=1080,
            height=1920,
            **values,
        )
        await self.execute(
            "UPDATE media_assets SET duration_s = :d WHERE id = :id", d=duration_s, id=asset
        )
        return asset

    async def account(self, username: str, **values: Any) -> uuid.UUID:
        return await make_account(self.engine, self.wid, username=username, **values)

    # ---- posts

    async def draft(self, **body: Any) -> dict[str, Any]:
        """POST …/scheduled-posts; ids and times may be given as objects."""
        post: dict[str, Any] = await self.ok("POST", "/scheduled-posts", jsonable(body), status=201)
        return post

    async def ready_draft(self, **body: Any) -> dict[str, Any]:
        """A draft that passes the checklist: the account, one 4:5 image, a caption."""
        body.setdefault("targets", [{"social_account_id": self.account_id}])
        if "asset_ids" not in body:
            body["asset_ids"] = [await self.image()]
        body.setdefault("caption", "Linen shirts are back #summer")
        return await self.draft(**body)

    async def scheduled(self, at: datetime | None = None, **body: Any) -> dict[str, Any]:
        post = await self.ready_draft(**body)
        out: dict[str, Any] = await self.ok(
            "POST",
            f"/scheduled-posts/{post['id']}/schedule",
            {"publish_at": iso(at or later(days=1))},
        )
        return out

    async def events(self, event_type: str = "scheduled_post.updated") -> list[dict[str, Any]]:
        return [data for kind, data in await stream(self.redis, self.wid) if kind == event_type]

    async def set_timezone(self, tz: str) -> None:
        await self.execute("UPDATE workspaces SET timezone = :tz WHERE id = :w", tz=tz, w=self.wid)


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return iso(value)
    return value


async def open_shop(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> Shop:
    clerk_id, me = await sign_in(client, clerk, email="owner@example.com", first_name="Asha")
    wid = me["workspaces"][0]["id"]
    account_id = await make_account(engine, wid, username="maple.bakery")
    return Shop(
        app,
        client,
        engine,
        app.state.redis,
        clerk,
        clerk_id,
        wid,
        account_id,
        clerk.headers(clerk_id),
    )


def by_key(checklist: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return [item for item in checklist if item["key"] == key]


def failing(post: dict[str, Any]) -> dict[str, str]:
    """The failing checklist items as {field: key}."""
    return {item["field"]: item["key"] for item in post["checklist"] if not item["ok"]}
