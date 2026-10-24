"""The widget's files, served by the API (GR-28). Public, not in the OpenAPI document.

- ``GET /widget.js``: the embed script (assets/loader.js, about 3 KB). A site adds it with
  ``<script src="https://…/widget.js" data-widget="wgt_…" async></script>``; it puts one iframe on
  the page and sizes it. No framework, nothing stored on the host page.
- ``GET /widget/frame?w=<widget id>&h=<host>``: the page inside the iframe. Served only when the
  widget exists, is switched on, its workspace is active and ``h`` (the embedding page's host
  name, sent by the loader) is on the allowed-domains list; the answer carries a
  ``Content-Security-Policy`` whose ``frame-ancestors`` names the allowed sites, so the browser
  refuses to show it on any other. Anything else is a small refusal page that cannot be framed.
- ``GET /widget/frame.js`` and ``/widget/frame.css``: the chat (about 16 KB and 6 KB, 5 KB and
  2 KB compressed).

The frame's own policy allows scripts, styles and requests from this server only, no inline code,
no forms to elsewhere and no base tag. Each visitor's chat is isolated from the host page by the
iframe and from the app's CSS by having its own stylesheet.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, Response

from socialhood.api import ratelimit
from socialhood.auth.deps import Session
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.repositories import widget as repo
from socialhood.services.widget import chat, origin
from socialhood.webhooks.routing import resolve_account

router = APIRouter(include_in_schema=False)

ASSETS = Path(__file__).parent / "assets"
LOADER = (ASSETS / "loader.js").read_bytes()
FRAME_JS = (ASSETS / "frame.js").read_bytes()
FRAME_CSS = (ASSETS / "frame.css").read_bytes()

STATIC_HEADERS = {
    "Cache-Control": "public, max-age=300",
    "Cross-Origin-Resource-Policy": "cross-origin",
    "X-Content-Type-Options": "nosniff",
}
FRAME_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors {ancestors}"
)
FRAME_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
DEFAULT_BRAND_URL = "https://socialhood.com"
REFUSAL = (
    '<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">'
    "<title>Chat</title><p>{message}</p>"
)

WidgetId = Annotated[str, Query(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
HostName = Annotated[str, Query(min_length=1, max_length=253)]


def _script(body: bytes) -> Response:
    return Response(body, media_type="text/javascript; charset=utf-8", headers=STATIC_HEADERS)


@router.get("/widget.js")
async def widget_script() -> Response:
    return _script(LOADER)


@router.get("/widget/frame.js")
async def frame_script() -> Response:
    return _script(FRAME_JS)


@router.get("/widget/frame.css")
async def frame_styles() -> Response:
    return Response(FRAME_CSS, media_type="text/css; charset=utf-8", headers=STATIC_HEADERS)


def _refusal(status: int, message: str) -> HTMLResponse:
    headers = {**FRAME_HEADERS, "Content-Security-Policy": FRAME_POLICY.format(ancestors="'none'")}
    return HTMLResponse(REFUSAL.format(message=html.escape(message)), status, headers)


def _page(widget_id: str, host: str, brand_url: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex"><title>Chat</title>'
        '<link rel="stylesheet" href="/widget/frame.css"></head>'
        f'<body data-widget="{html.escape(widget_id)}" data-host="{html.escape(host)}" '
        f'data-brand-url="{html.escape(brand_url)}">'
        '<div id="root"></div><script src="/widget/frame.js"></script></body></html>'
    )


@router.get("/widget/frame", dependencies=[ratelimit.WIDGET_FRAME])
async def frame(request: Request, session: Session, w: WidgetId, h: HostName) -> Response:
    host = origin.clean_host(h)
    routed = await resolve_account(session, "web", w)
    if routed is None or host is None:
        return _refusal(404, "This chat isn't available.")
    with workspace_scope(routed.workspace_id):
        try:
            widget = await chat.load(session, routed, host)
        except ApiError as error:
            return _refusal(error.status, error.detail or chat.NOT_AVAILABLE)
        row = await repo.get_settings(session, widget.acct.id)
    assert row is not None  # load() found it
    settings = request.app.state.settings
    headers = {
        **FRAME_HEADERS,
        "Content-Security-Policy": FRAME_POLICY.format(
            ancestors=origin.frame_ancestors(list(row.allowed_domains or []))
        ),
    }
    page = _page(w, host, settings.web_base_url or DEFAULT_BRAND_URL)
    return HTMLResponse(page, 200, headers)
