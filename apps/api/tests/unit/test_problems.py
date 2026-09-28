from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel, Field

from socialhood.errors import ERROR_CODES, ERROR_TYPE_BASE, ApiError, FieldError
from socialhood.main import create_app
from socialhood.settings import get_settings


class Body(BaseModel):
    text: str = Field(max_length=5)


def build_app() -> FastAPI:
    app = create_app(get_settings())

    @app.get("/_raise/{code}")
    async def raise_code(code: str) -> None:
        raise ApiError(code, "detail text", errors=[FieldError("text", "bad")])

    @app.post("/_validate")
    async def validate(body: Body) -> Body:
        return body

    @app.get("/_crash")
    async def crash() -> None:
        raise RuntimeError("boom")

    return app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=build_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.parametrize("code", sorted(ERROR_CODES))
async def test_each_error_code_renders_problem_json(client: httpx.AsyncClient, code: str) -> None:
    response = await client.get(f"/_raise/{code}")
    spec = ERROR_CODES[code]
    assert response.status_code == spec.status
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == ERROR_TYPE_BASE + code
    assert body["title"] == spec.title
    assert body["status"] == spec.status
    assert body["code"] == code
    assert body["detail"] == "detail text"
    assert body["errors"] == [{"field": "text", "message": "bad"}]
    assert body["request_id"] == response.headers["x-request-id"]


async def test_unknown_route_is_problem_not_found(client: httpx.AsyncClient) -> None:
    response = await client.get("/nope")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_validation_errors_name_the_field(client: httpx.AsyncClient) -> None:
    response = await client.post("/_validate", json={"text": "too long"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["errors"][0]["field"] == "text"


async def test_unhandled_error_is_internal_problem_with_headers(client: httpx.AsyncClient) -> None:
    response = await client.get("/_crash")
    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "internal"
    assert "boom" not in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.json()["request_id"] == response.headers["x-request-id"]


async def test_security_headers_and_request_id(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz", headers={"X-Request-ID": "trace-12345678"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"] == "trace-12345678"
    assert response.headers["strict-transport-security"].startswith("max-age=")
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["content-security-policy"] == "frame-ancestors 'none'"


async def test_malformed_request_id_is_replaced(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz", headers={"X-Request-ID": "bad id\n"})
    assert response.headers["x-request-id"] != "bad id\n"
    assert len(response.headers["x-request-id"]) == 26


def test_unknown_error_code_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="unknown error code"):
        ApiError("no_such_code")
