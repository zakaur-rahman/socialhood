"""Google Sheets sync (GR-27): the connection, the sheet and the column mapping."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

ConnectionStatusName = Literal["active", "needs_reconnect"]
RowStatusName = Literal["pending", "succeeded", "failed"]

MAX_COLUMNS = 30


class GoogleConnectStart(ResponseModel):
    authorize_url: str


class GoogleConnectComplete(RequestModel):
    """The nonce the OAuth callback put in the Integrations page's URL (?google=…)."""

    nonce: str = Field(min_length=8, max_length=128)


class SheetCreate(RequestModel):
    title: str = Field(default="Social Hood leads", min_length=1, max_length=100)


class SheetSelect(RequestModel):
    link: str = Field(min_length=1, max_length=300)  # the sheet's address, or just its id


class SheetColumn(RequestModel):
    field: str = Field(min_length=1, max_length=60)  # services/sheets.FIELDS or "field:<key>"
    header: str = Field(min_length=1, max_length=100)


class SheetMappingPut(RequestModel):
    columns: list[SheetColumn] = Field(min_length=1, max_length=MAX_COLUMNS)


class SheetColumnOut(ResponseModel):
    field: str
    header: str


class SheetFieldOption(ResponseModel):
    field: str
    label: str
    custom: bool  # a custom contact field


class SheetOut(ResponseModel):
    spreadsheet_id: str
    title: str
    url: str
    tab: str


class SheetRowOut(ResponseModel):
    id: uuid.UUID
    status: RowStatusName
    attempts: int
    error: str | None = None
    error_code: str | None = None
    created_at: datetime
    last_attempt_at: datetime | None = None
    next_attempt_at: datetime | None = None


class GoogleSheetsStatus(ResponseModel):
    available: bool  # Google is set up on this server
    entitled: bool  # the plan includes Sheets sync (PD-6)
    connected: bool
    status: ConnectionStatusName | None = None
    google_email: str | None = None
    sheet: SheetOut | None = None
    columns: list[SheetColumnOut] = Field(default_factory=list)
    fields: list[SheetFieldOption] = Field(default_factory=list)
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str | None = None
    pending_rows: int = 0
    failed_rows: int = 0
    recent: list[SheetRowOut] = Field(default_factory=list)


class SheetTestResult(ResponseModel):
    ok: bool
