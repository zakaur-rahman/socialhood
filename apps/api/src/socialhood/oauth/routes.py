"""The authorization server's HTTP endpoints on the API's origin (C-165 phase C; 01-design.md
§2.1, §3.2):

- ``GET /.well-known/oauth-authorization-server`` (RFC 8414): the metadata.
- ``GET /oauth/authorize``: checks the request, then 302 to the dashboard's consent page
  (``/connect/authorize?request=…``), or back to the client with an error. A bad client or
  redirect URI is a small HTML page for the person, never a redirect.
- ``POST /oauth/token``: ``authorization_code`` and ``refresh_token`` grants (form body).
- ``POST /oauth/register``: Dynamic Client Registration (RFC 7591, JSON body). Deprecated by
  the MCP spec in favour of Client ID Metadata Documents, kept for older clients.
- ``POST /oauth/revoke``: RFC 7009.

They speak OAuth, not the app's problem+json: JSON ``{"error", "error_description"}`` with the
RFCs' statuses, ``Cache-Control: no-store`` on tokens, and ``WWW-Authenticate: Basic`` on a 401
for a client that sent Basic credentials. Not in the OpenAPI document (like /mcp). Rate limits
(§6.1): authorize 30 a minute per IP, register 10 an hour per IP, token and revoke 60 a minute
per client.
"""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from socialhood.errors import ApiError
from socialhood.oauth import clients, service
from socialhood.oauth.clients import ClientError
from socialhood.oauth.service import OAuthError
from socialhood.security import ratelimit
from socialhood.settings import Settings

router = APIRouter(include_in_schema=False)

NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}
NOINDEX = {"X-Robots-Tag": "noindex, nofollow"}


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _error(error: OAuthError, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        {"error": error.error, "error_description": error.description},
        status_code=error.status,
        headers={**NO_STORE, **NOINDEX, **(headers or {})},
    )


async def _limited(request: Request, name: str, subject: str) -> JSONResponse | None:
    try:
        await ratelimit.enforce(request, name, subject)
    except ApiError as error:
        return JSONResponse(
            {"error": "slow_down", "error_description": "Too many requests. Try again shortly."},
            status_code=429,
            headers={**NO_STORE, **error.headers},
        )
    return None


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata(request: Request) -> JSONResponse:
    return JSONResponse(
        service.metadata(_settings(request)), headers={"Cache-Control": "public, max-age=3600"}
    )


ERROR_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,
initial-scale=1"><meta name="robots" content="noindex"><title>Can't connect to Amplychat</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:32rem;margin:15vh auto;padding:0 1rem;
color:#1c1917;background:#fafaf9}}h1{{font-size:1.25rem}}p{{color:#57534e}}
@media (prefers-color-scheme:dark){{body{{color:#f5f5f4;background:#1c1917}}p{{color:#a8a29e}}}}
</style></head><body><main><h1>This app can't connect to Amplychat</h1><p>{message}</p>
<p>Start connecting again from your AI app. If it keeps happening, write to
support@amplychat.com.</p></main></body></html>"""


@router.get("/oauth/authorize")
async def authorize(request: Request) -> Response:
    settings = _settings(request)
    if limited := await _limited(request, "oauth_authorize", ratelimit.client_ip(request)):
        return limited
    params = {k: v for k, v in request.query_params.items()}
    # Each parameter once (RFC 6749 §3.1): a repeated one could mean different things to us and
    # to whoever checked it before.
    if len(request.query_params.multi_items()) != len(params):
        page = ERROR_PAGE.format(message="The request repeats a parameter.")
        return HTMLResponse(page, status_code=400, headers=NOINDEX)
    async with request.app.state.sessionmaker() as session:
        try:
            location = await service.start_authorization(
                session,
                request.app.state.redis,
                settings,
                params,
                datetime.now(UTC),
                fetch=getattr(request.app.state, "cimd_fetch", None),
            )
        except OAuthError as error:
            if error.redirect is None:
                page = ERROR_PAGE.format(message=html.escape(error.description))
                return HTMLResponse(page, status_code=400, headers=NOINDEX)
            return RedirectResponse(service.error_redirect(error, settings), status_code=302)
    return RedirectResponse(location, status_code=302, headers=NOINDEX)


async def _form(request: Request) -> dict[str, str] | None:
    """The form body, each field once; None when it isn't one."""
    if not request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
        return None
    form = await request.form()
    items = [(k, v) for k, v in form.multi_items() if isinstance(v, str)]
    out = dict(items)
    return out if len(out) == len(items) else None


@router.post("/oauth/token")
async def token(request: Request) -> Response:
    settings = _settings(request)
    form = await _form(request)
    if form is None:
        return _error(OAuthError("invalid_request", "Send a form body, each parameter once."))
    authorization = request.headers.get("authorization")
    now = datetime.now(UTC)
    async with request.app.state.sessionmaker() as session:
        try:
            client = await service.authenticate_client(session, form, authorization)
            if limited := await _limited(request, "oauth_token", client.client_id):
                return limited
            grant = form.get("grant_type")
            if grant == "authorization_code":
                body = await service.exchange_code(session, settings, client, form, now)
            elif grant == "refresh_token":
                body = await service.refresh(session, settings, client, form, now)
            else:
                raise OAuthError(
                    "unsupported_grant_type",
                    "Only authorization_code and refresh_token are supported.",
                )
        except OAuthError as error:
            await session.rollback()
            basic = (authorization or "").lower().startswith("basic ")
            extra = {"WWW-Authenticate": 'Basic realm="amplychat"'} if basic else {}
            return _error(error, extra if error.status == 401 else None)
    return JSONResponse(body, headers={**NO_STORE, **NOINDEX})


@router.post("/oauth/register")
async def register(request: Request) -> Response:
    if limited := await _limited(request, "oauth_register", ratelimit.client_ip(request)):
        return limited
    raw = await request.body()
    if len(raw) > clients.DCR_MAX_BYTES:
        return _error(OAuthError("invalid_client_metadata", "The registration is too large."))
    try:
        body: Any = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        body = None
    if not isinstance(body, dict):
        return _error(OAuthError("invalid_client_metadata", "Send the metadata as a JSON object."))
    now = datetime.now(UTC)
    async with request.app.state.sessionmaker() as session:
        try:
            registered = clients.register_dcr(session, body)
        except ClientError as error:
            return _error(OAuthError(error.code, error.description))
        await session.commit()
        out = clients.registration_response(registered, now)
    return JSONResponse(out, status_code=201, headers={**NO_STORE, **NOINDEX})


@router.post("/oauth/revoke")
async def revoke(request: Request) -> Response:
    form = await _form(request)
    if form is None:
        return _error(OAuthError("invalid_request", "Send a form body, each parameter once."))
    async with request.app.state.sessionmaker() as session:
        try:
            client = await service.authenticate_client(
                session, form, request.headers.get("authorization")
            )
            if limited := await _limited(request, "oauth_token", client.client_id):
                return limited
            await service.revoke(session, client, form, datetime.now(UTC))
        except OAuthError as error:
            return _error(error)
    return Response(status_code=200, headers={**NO_STORE, **NOINDEX})
