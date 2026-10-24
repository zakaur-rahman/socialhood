"""Google Sheets sync API (GR-27): connect Google, choose or create a sheet, map fields to columns,
send a test row, disconnect. Owners and admins. The rules are in services/sheets.py."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from socialhood.auth.deps import Admin, Session
from socialhood.google.client import GoogleClient
from socialhood.google.registry import configured, get_google
from socialhood.schemas.sheets import (
    GoogleConnectComplete,
    GoogleConnectStart,
    GoogleSheetsStatus,
    SheetCreate,
    SheetMappingPut,
    SheetSelect,
    SheetTestResult,
)
from socialhood.security.crypto import TokenCipher, cipher_for
from socialhood.services import sheets as service
from socialhood.settings import Settings

router = APIRouter(prefix="/v1/w/{wid}/integrations/google-sheets", tags=["integrations"])


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _cipher(request: Request) -> TokenCipher:
    return cipher_for(tuple(_settings(request).token_encryption_keys))


def _google(request: Request) -> GoogleClient:
    return get_google(request.app.state.http, _settings(request), request.app.state.redis)


async def _status(request: Request, session: Session) -> GoogleSheetsStatus:
    return await service.get_status(session, configured=configured(_settings(request)))


@router.get("", operation_id="get_google_sheets")
async def get_google_sheets(request: Request, ctx: Admin, session: Session) -> GoogleSheetsStatus:
    """The connection, its sheet and column mapping, the fields a column can hold and the latest
    rows with their results."""
    return await _status(request, session)


@router.post("/connect", operation_id="start_google_connect")
async def start_google_connect(
    request: Request, ctx: Admin, session: Session
) -> GoogleConnectStart:
    """Google's authorize URL (the narrow drive.file scope). 402 without Sheets sync on the plan,
    503 when Google isn't set up on this server."""
    url = await service.start_connect(
        session,
        request.app.state.redis,
        _google(request),
        configured=configured(_settings(request)),
        workspace_id=ctx.workspace_id,
        slug=ctx.workspace.slug,
        user_id=ctx.user.id,
    )
    return GoogleConnectStart(authorize_url=url)


@router.post("/complete", operation_id="complete_google_connect")
async def complete_google_connect(
    request: Request, body: GoogleConnectComplete, ctx: Admin, session: Session
) -> GoogleSheetsStatus:
    """Finish a connect with the nonce the OAuth callback redirected with. Only the member who
    started it, in the workspace they started it in, can finish it; the nonce works once and for 10
    minutes. 404 when it expired or was used, 403 when someone else started it, 502 when Google
    fails."""
    await service.finish_connect(
        session,
        request.app.state.redis,
        _google(request),
        _cipher(request),
        nonce=body.nonce,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user.id,
        now=datetime.now(UTC),
    )
    out = await _status(request, session)
    await session.commit()
    return out


@router.post("/sheet", status_code=201, operation_id="create_google_sheet")
async def create_google_sheet(
    request: Request, body: SheetCreate, ctx: Admin, session: Session
) -> GoogleSheetsStatus:
    """Make a new sheet in the connected Google account, with a header row from the mapping."""
    await service.create_sheet(
        session, _google(request), _cipher(request), title=body.title, now=datetime.now(UTC)
    )
    out = await _status(request, session)
    await session.commit()
    return out


@router.put("/sheet", operation_id="select_google_sheet")
async def select_google_sheet(
    request: Request, body: SheetSelect, ctx: Admin, session: Session
) -> GoogleSheetsStatus:
    """Use a sheet by its link. With the narrow scope Google lets Social Hood open only sheets it
    made or was granted: any other gives 422 on ``link``."""
    await service.select_sheet(
        session, _google(request), _cipher(request), link=body.link, now=datetime.now(UTC)
    )
    out = await _status(request, session)
    await session.commit()
    return out


@router.put("/mapping", operation_id="save_google_sheet_mapping")
async def save_google_sheet_mapping(
    request: Request, body: SheetMappingPut, ctx: Admin, session: Session
) -> GoogleSheetsStatus:
    """Which field goes in which column, in order. A sheet Social Hood made gets its header row
    updated; a sheet that was already yours is not touched."""
    await service.save_mapping(session, _google(request), _cipher(request), columns=body.columns)
    out = await _status(request, session)
    await session.commit()
    return out


@router.post("/test", operation_id="send_google_sheet_test")
async def send_google_sheet_test(request: Request, ctx: Admin, session: Session) -> SheetTestResult:
    """Add a sample row now. 409 with the reason in plain words when Google refuses it."""
    await service.send_test(session, _google(request), _cipher(request), now=datetime.now(UTC))
    await session.commit()
    return SheetTestResult(ok=True)


@router.delete("", status_code=204, operation_id="disconnect_google_sheets")
async def disconnect_google_sheets(request: Request, ctx: Admin, session: Session) -> Response:
    """Revoke Google's access and remove the connection and the rows still waiting."""
    await service.disconnect(session, _google(request), _cipher(request))
    await session.commit()
    return Response(status_code=204)
