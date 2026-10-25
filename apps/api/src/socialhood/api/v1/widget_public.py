"""The website chat widget's public API (GR-28): ``/v1/widget/*``, called only by the widget's own
frame (served from this same server, so there is no cross-origin access and no CORS). Not in the
OpenAPI document.

No sign-in. A call is allowed by the signed visitor session the frame got from ``POST
/session`` (the widget id and the embedding page's host are checked there) and by being
same-origin: a browser call that carries an ``Origin`` other than this server's own is refused,
so another site's script cannot use a visitor's session. The routes check the widget, its
workspace and its allowed domains again on every call, so switching the widget off or removing a
domain takes effect within one poll. Limits are per IP (api/ratelimit.py) and per visitor
(security/ratelimit.py); over one is 429 ``rate_limited``.

``GET /messages`` is a long poll: with the ``version`` the widget already has it waits up to
``wait`` seconds (at most 20) for the thread to change.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Query, Request, Response

from socialhood.api import ratelimit
from socialhood.auth.deps import Session
from socialhood.errors import ApiError
from socialhood.schemas.widget import (
    WidgetEmail,
    WidgetEmailOut,
    WidgetMessages,
    WidgetSend,
    WidgetSession,
    WidgetSessionRequest,
)
from socialhood.security import ratelimit as limits
from socialhood.security.widget_tokens import VisitorClaim
from socialhood.services.widget import chat

router = APIRouter(prefix="/v1/widget", tags=["widget"], include_in_schema=False)

NO_STORE = {"Cache-Control": "no-store"}


def same_origin(request: Request) -> None:
    """403 when a browser says the call comes from another site. No ``Origin`` (a same-origin GET,
    or a script that is not a browser) passes: the session decides those."""
    origin = request.headers.get("origin")
    if origin is None:
        return
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    if urlsplit(origin).netloc.lower() != host.split(",")[0].strip().lower():
        raise ApiError("forbidden", chat.WRONG_SITE)


def claim_of(request: Request) -> VisitorClaim:
    same_origin(request)
    scheme, _, bearer = request.headers.get("authorization", "").partition(" ")
    token = bearer.strip() if scheme.lower() == "bearer" else None
    return chat.read_claim(token, request.app.state.settings)


async def _visitor_limit(request: Request, name: str, claim: VisitorClaim) -> None:
    await limits.enforce(request, name, claim.visitor_id)


@router.post("/session", dependencies=[ratelimit.WIDGET_SESSION])
async def open_session(
    request: Request, response: Response, body: WidgetSessionRequest, session: Session
) -> WidgetSession:
    """Check the widget id and the page's host; return a visitor session, the widget's look and
    the visitor's chat so far."""
    same_origin(request)
    response.headers.update(NO_STORE)
    return await chat.open_session(
        session,
        request.app.state.settings,
        widget_id=body.widget_id,
        host=body.host,
        visitor_key=body.visitor_key,
    )


@router.get("/messages", dependencies=[ratelimit.WIDGET_POLL])
async def read_messages(
    request: Request,
    response: Response,
    version: Annotated[str | None, Query(max_length=40)] = None,
    wait: Annotated[float, Query(ge=0, le=20)] = 0,
) -> WidgetMessages:
    """The visitor's chat; with ``version`` and ``wait``, held until it changes."""
    claim = claim_of(request)
    await _visitor_limit(request, "widget_poll_visitor", claim)
    response.headers.update(NO_STORE)
    return await chat.poll(request.app.state.sessionmaker, claim, version=version, wait_s=wait)


@router.post("/messages", dependencies=[ratelimit.WIDGET_SEND])
async def send_message(
    request: Request, response: Response, body: WidgetSend, session: Session
) -> WidgetMessages:
    """Send the visitor's message into the inbox. Repeating a ``client_id`` sends nothing more."""
    claim = claim_of(request)
    await _visitor_limit(request, "widget_send_visitor", claim)
    await _visitor_limit(request, "widget_send_day", claim)
    response.headers.update(NO_STORE)
    return await chat.send(
        session, request.app.state.redis, claim, text=body.text, client_id=body.client_id
    )


@router.post("/email", dependencies=[ratelimit.WIDGET_EMAIL])
async def give_email(
    request: Request, response: Response, body: WidgetEmail, session: Session
) -> WidgetEmailOut:
    """Identify the visitor by email (and consent to marketing when the widget asks)."""
    claim = claim_of(request)
    await _visitor_limit(request, "widget_send_visitor", claim)
    response.headers.update(NO_STORE)
    return await chat.save_email(session, request.app.state.redis, claim, body)
