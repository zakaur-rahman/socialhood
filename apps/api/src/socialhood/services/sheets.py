"""Google Sheets sync (GR-27): connect Google, choose a sheet, map fields to columns, and add a row
for every captured lead.

- **Access.** The narrow ``drive.file`` scope only (google/client.py): Amplychat can use sheets
  it created, or ones Google has granted it. Google's refresh credential is stored encrypted like
  platform tokens (SEC-03) and never returned. Owners and admins; the plan must include
  ``sheets_sync`` (PD-6, decided).
- **Connecting.** Like Instagram (X-1) the public callback never connects anything: it parks the
  code under a one-time nonce bound to the member and workspace that started it, and the signed-in
  Integrations page finishes with POST …/complete.
- **The sheet.** Create a new one (Amplychat writes the header row) or give the link of one it
  can already see. A sheet the person already had is never given a header row.
- **Mapping.** An ordered list of columns, each a field and a header: the person's name,
  @username, platform, email, phone, the automation, when it was captured, their consent, or any
  custom contact field. A field appears once.
- **Rows.** ``lead.captured`` queues one ``sheet_rows`` row (queue_lead, in the transaction that
  caused the event) and the append_sheet_row job adds it with ``valueInputOption=RAW`` (a customer's
  text is never run as a formula). Retries use the webhook machinery's backoff (1 minute to 12
  hours, 7 attempts, services/webhooks/delivery.py). An answer that won't change on a retry fails
  at once with a plain reason: access removed (the connection then needs reconnecting), the sheet
  deleted, the sheet refused. Reconnecting or choosing a sheet again sends the rows that failed
  for that reason.
- **Consent.** The row carries the consent recorded when it is queued: a consent question comes
  after the answer it follows, so a row for the first answer usually has none yet.
"""

from __future__ import annotations

import json
import re
import secrets
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Literal

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.billing.entitlements import check_entitlement
from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.google.client import GoogleClient, GoogleError
from socialhood.models.contacts import ConsentStatus, ContactFieldDefinition
from socialhood.models.inbox import Contact
from socialhood.models.integrations import DeliveryStatus, GoogleConnection, GoogleStatus, SheetRow
from socialhood.models.notifications import NotificationType
from socialhood.observability.logging import get_logger
from socialhood.schemas.sheets import (
    MAX_COLUMNS,
    ConnectionStatusName,
    GoogleSheetsStatus,
    SheetColumn,
    SheetColumnOut,
    SheetFieldOption,
    SheetOut,
    SheetRowOut,
)
from socialhood.security.crypto import TokenCipher
from socialhood.services.sending import platform_name
from socialhood.services.webhooks.delivery import backoff

log = get_logger(__name__)

STATE_TTL_S = 600
HELD_TTL_S = 600
START_DELAY_S = 1.0  # the caller commits after queueing
NOT_FOUND_RETRIES = (
    5  # a row not visible yet (its transaction hasn't committed) is looked for again
)
RECENT_ROWS = 10
CUSTOM = "field:"

# The fixed fields a column can hold: field -> the header a new sheet starts with.
FIELDS: dict[str, str] = {
    "contact_name": "Name",
    "username": "Username",
    "platform": "Platform",
    "email": "Email",
    "phone": "Phone",
    "automation": "Automation",
    "captured_at": "Captured at",
    "consent": "Consent",
}
DEFAULT_COLUMNS = [SheetColumn(field=field, header=header) for field, header in FIELDS.items()]

# Why a row failed. The code is stored; the words are what the card shows.
ACCESS_REMOVED = "access_removed"
SHEET_GONE = "sheet_gone"
SHEET_REFUSED = "sheet_refused"
NO_SHEET = "no_sheet"
GOOGLE_BUSY = "google_busy"
GOOGLE_REFUSED = "google_refused"
REASONS: dict[str, str] = {
    ACCESS_REMOVED: "Access was removed: reconnect Google in Settings, under Integrations.",
    SHEET_GONE: "Google said the sheet was deleted. Pick or create a sheet again.",
    SHEET_REFUSED: (
        "Google won't let Amplychat write to that sheet. Pick or create a sheet again."
    ),
    NO_SHEET: "No sheet is chosen. Pick or create one in Settings, under Integrations.",
    GOOGLE_BUSY: "Google didn't take the row. It was tried again and still failed.",
    GOOGLE_REFUSED: "Google refused the row. Check the sheet and its columns.",
}
# Failures a reconnect, or choosing a sheet again, can fix: those rows are sent again then.
RECONNECT_FIXES = (ACCESS_REMOVED,)
SHEET_FIXES = (SHEET_GONE, SHEET_REFUSED, NO_SHEET)

NOT_CONFIGURED = "Google isn't set up on this server."
NOT_CONNECTED = "Connect Google first."
NEEDS_RECONNECT = "Reconnect Google first: access was removed."
NO_SHEET_YET = "Pick or create a sheet first."
CONNECT_EXPIRED = "That connection link expired. Connect Google again."
CONNECT_NOT_YOURS = (
    "This Google connection was started by someone else, so it wasn't added. To connect your own "
    "account, use Connect Google."
)
CONNECT_FAILED = "Google didn't respond. Try again."
LINK_INVALID = "That doesn't look like a Google Sheets link."
LINK_UNREADABLE = (
    "Amplychat can only use sheets it created or that Google has let it open. "
    "Create a new sheet instead."
)

_SHEET_LINK = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]{10,100})")
_SHEET_ID = re.compile(r"^[A-Za-z0-9_-]{10,100}$")

Outcome = Literal["missing", "done", "delivered", "retrying", "failed"]


# ---------------------------------------------------------------- reading


async def get_connection(session: AsyncSession, *, lock: bool = False) -> GoogleConnection | None:
    query = select(GoogleConnection)
    if lock:
        query = query.with_for_update()
    return await session.scalar(query)


async def field_options(session: AsyncSession) -> list[SheetFieldOption]:
    options = [SheetFieldOption(field=f, label=h, custom=False) for f, h in FIELDS.items()]
    rows = await session.scalars(
        select(ContactFieldDefinition).order_by(
            ContactFieldDefinition.position, ContactFieldDefinition.label
        )
    )
    options += [
        SheetFieldOption(field=CUSTOM + d.key, label=d.label, custom=True) for d in rows.all()
    ]
    return options


async def get_status(session: AsyncSession, *, configured: bool) -> GoogleSheetsStatus:
    plan = await current_plan(session)
    entitled = bool(entitlement(plan, "sheets_sync"))
    conn = await get_connection(session)
    fields = await field_options(session)
    if conn is None:
        return GoogleSheetsStatus(
            available=configured,
            entitled=entitled,
            connected=False,
            columns=[SheetColumnOut(field=c.field, header=c.header) for c in DEFAULT_COLUMNS],
            fields=fields,
        )
    counts = dict(
        (
            await session.execute(
                select(SheetRow.status, func.count())
                .where(SheetRow.connection_id == conn.id)
                .group_by(SheetRow.status)
            )
        ).all()
    )
    recent = await session.scalars(
        select(SheetRow)
        .where(SheetRow.connection_id == conn.id)
        .order_by(SheetRow.created_at.desc(), SheetRow.id.desc())
        .limit(RECENT_ROWS)
    )
    sheet = (
        SheetOut(
            spreadsheet_id=conn.spreadsheet_id,
            title=conn.spreadsheet_title or "",
            url=conn.spreadsheet_url or "",
            tab=conn.sheet_tab or "",
        )
        if conn.spreadsheet_id
        else None
    )
    return GoogleSheetsStatus(
        available=configured,
        entitled=entitled,
        connected=True,
        status=_status_name(conn),
        google_email=conn.google_email,
        sheet=sheet,
        columns=[SheetColumnOut(**c) for c in (conn.mapping or [])]
        or [SheetColumnOut(field=c.field, header=c.header) for c in DEFAULT_COLUMNS],
        fields=fields,
        last_success_at=conn.last_success_at,
        last_failure_at=conn.last_failure_at,
        last_error=conn.last_error,
        pending_rows=int(counts.get(DeliveryStatus.PENDING, 0)),
        failed_rows=int(counts.get(DeliveryStatus.FAILED, 0)),
        recent=[SheetRowOut.model_validate(r) for r in recent.all()],
    )


def _status_name(conn: GoogleConnection) -> ConnectionStatusName:
    return "needs_reconnect" if conn.status == GoogleStatus.NEEDS_RECONNECT else "active"


# ---------------------------------------------------------------- connecting


def _held_key(nonce: str) -> str:
    return f"oauth:held:google:{nonce}"


async def start_connect(
    session: AsyncSession,
    redis: Redis,
    google: GoogleClient,
    *,
    configured: bool,
    workspace_id: uuid.UUID,
    slug: str,
    user_id: uuid.UUID,
) -> str:
    """Store a single-use OAuth state and return Google's authorize URL."""
    await check_entitlement(session, "sheets_sync")
    if not configured:
        raise ApiError("service_unavailable", NOT_CONFIGURED)
    state = secrets.token_urlsafe(32)
    await redis.set(
        f"oauth:{state}",
        json.dumps(
            {
                "user_id": str(user_id),
                "workspace_id": str(workspace_id),
                "slug": slug,
                "platform": "google_sheets",
            }
        ),
        ex=STATE_TTL_S,
    )
    return google.authorize_url(state)


async def hold_code(redis: Redis, cipher: TokenCipher, state: dict[str, str], code: str) -> str:
    """Park the code (encrypted) for the signed-in page; returns the nonce the callback sends."""
    nonce = secrets.token_urlsafe(32)
    held = {
        "user_id": state["user_id"],
        "workspace_id": state["workspace_id"],
        "code": cipher.encrypt(code).decode(),
    }
    await redis.set(_held_key(nonce), json.dumps(held), ex=HELD_TTL_S)
    return nonce


async def finish_connect(
    session: AsyncSession,
    redis: Redis,
    google: GoogleClient,
    cipher: TokenCipher,
    *,
    nonce: str,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    now: datetime,
) -> None:
    """POST …/complete: take the held code (once, whatever happens next), exchange it and save the
    connection; only the member and workspace that started it can."""
    raw = await redis.getdel(_held_key(nonce))
    if raw is None:
        raise ApiError("not_found", CONNECT_EXPIRED)
    held = json.loads(raw)
    if held["user_id"] != str(user_id) or held["workspace_id"] != str(workspace_id):
        log.warning("google_connect_refused", reason="not_the_starter")
        raise ApiError("forbidden", CONNECT_NOT_YOURS)
    await check_entitlement(session, "sheets_sync")
    try:
        grant = await google.exchange_code(cipher.decrypt(held["code"].encode()))
    except GoogleError as error:
        log.warning("google_connect_failed", error_kind=error.kind)
        raise ApiError("platform_error", CONNECT_FAILED) from error
    conn = await get_connection(session, lock=True)
    credential = cipher.encrypt(grant.refresh_token)
    if conn is None:
        conn = GoogleConnection(
            google_email=grant.email,
            credential_enc=credential,
            scopes=list(grant.scopes),
            status=GoogleStatus.ACTIVE,
            connected_by_user_id=user_id,
            connected_at=now,
            mapping=[c.model_dump() for c in DEFAULT_COLUMNS],
            sheet_created=False,
        )
        session.add(conn)
    else:
        if conn.google_email and grant.email and conn.google_email != grant.email:
            _forget_sheet(conn)  # another Google account can't see the old sheet
        conn.google_email = grant.email
        conn.credential_enc = credential
        conn.scopes = list(grant.scopes)
        conn.status = GoogleStatus.ACTIVE
        conn.last_error = None
        conn.connected_by_user_id = user_id
        conn.connected_at = now
    await session.flush()
    await requeue(session, conn, RECONNECT_FIXES, now=now)


def _forget_sheet(conn: GoogleConnection) -> None:
    conn.spreadsheet_id = conn.spreadsheet_title = conn.spreadsheet_url = conn.sheet_tab = None
    conn.sheet_created = False


async def disconnect(session: AsyncSession, google: GoogleClient, cipher: TokenCipher) -> None:
    """Remove the connection and the rows still waiting. Google's access is revoked as well, as
    far as Google answers."""
    conn = await get_connection(session, lock=True)
    if conn is None:
        return
    try:
        await google.revoke(cipher.decrypt(conn.credential_enc))
    except (GoogleError, ValueError):
        log.warning("google_revoke_failed")
    await session.delete(conn)
    await session.flush()


# ---------------------------------------------------------------- the sheet and the mapping


def _api_error(error: GoogleError) -> ApiError:
    if error.kind == "auth":
        return ApiError("conflict", REASONS[ACCESS_REMOVED])
    if error.kind == "not_found":
        return ApiError("conflict", REASONS[SHEET_GONE])
    if error.kind == "forbidden":
        return ApiError("conflict", REASONS[SHEET_REFUSED])
    return ApiError("platform_error", CONNECT_FAILED)


async def _live_connection(session: AsyncSession, *, lock: bool = False) -> GoogleConnection:
    await check_entitlement(session, "sheets_sync")
    conn = await get_connection(session, lock=lock)
    if conn is None:
        raise ApiError("conflict", NOT_CONNECTED)
    if conn.status != GoogleStatus.ACTIVE:
        raise ApiError("conflict", NEEDS_RECONNECT)
    return conn


async def _access(
    session: AsyncSession, google: GoogleClient, cipher: TokenCipher, conn: GoogleConnection
) -> str:
    try:
        return await google.access_token(cipher.decrypt(conn.credential_enc))
    except GoogleError as error:
        if error.kind == "auth":
            conn.status = GoogleStatus.NEEDS_RECONNECT
            conn.last_error = REASONS[ACCESS_REMOVED]
            await session.commit()
        raise _api_error(error) from error


def headers_of(columns: list[dict[str, str]]) -> list[str]:
    return [c["header"] for c in columns]


async def create_sheet(
    session: AsyncSession,
    google: GoogleClient,
    cipher: TokenCipher,
    *,
    title: str,
    now: datetime,
) -> None:
    conn = await _live_connection(session, lock=True)
    access = await _access(session, google, cipher, conn)
    columns = list(conn.mapping or []) or [c.model_dump() for c in DEFAULT_COLUMNS]
    try:
        info = await google.create_spreadsheet(access, title, headers_of(columns))
    except GoogleError as error:
        raise _api_error(error) from error
    conn.spreadsheet_id, conn.spreadsheet_title = info.spreadsheet_id, info.title or title
    conn.spreadsheet_url, conn.sheet_tab = info.url, info.tab
    conn.sheet_created = True
    conn.mapping = columns
    conn.last_error = None
    await session.flush()
    await requeue(session, conn, SHEET_FIXES, now=now)


def sheet_id_of(link: str) -> str | None:
    found = _SHEET_LINK.search(link)
    if found:
        return found.group(1)
    bare = link.strip()
    return bare if _SHEET_ID.match(bare) else None


async def select_sheet(
    session: AsyncSession,
    google: GoogleClient,
    cipher: TokenCipher,
    *,
    link: str,
    now: datetime,
) -> None:
    spreadsheet_id = sheet_id_of(link)
    if spreadsheet_id is None:
        raise ApiError("validation_error", errors=[FieldError("link", LINK_INVALID)])
    conn = await _live_connection(session, lock=True)
    access = await _access(session, google, cipher, conn)
    try:
        info = await google.get_spreadsheet(access, spreadsheet_id)
    except GoogleError as error:
        if error.kind in ("not_found", "forbidden"):
            raise ApiError(
                "validation_error", errors=[FieldError("link", LINK_UNREADABLE)]
            ) from error
        raise _api_error(error) from error
    conn.spreadsheet_id, conn.spreadsheet_title = info.spreadsheet_id, info.title
    conn.spreadsheet_url, conn.sheet_tab = info.url, info.tab
    conn.sheet_created = False  # theirs: never given a header row
    conn.last_error = None
    await session.flush()
    await requeue(session, conn, SHEET_FIXES, now=now)


async def save_mapping(
    session: AsyncSession,
    google: GoogleClient,
    cipher: TokenCipher,
    *,
    columns: list[SheetColumn],
) -> None:
    conn = await _live_connection(session, lock=True)
    allowed = {o.field for o in await field_options(session)}
    seen: set[str] = set()
    for index, column in enumerate(columns):
        if column.field not in allowed:
            raise ApiError(
                "validation_error",
                errors=[FieldError(f"columns.{index}.field", "Choose one of the listed fields.")],
            )
        if column.field in seen:
            raise ApiError(
                "validation_error",
                errors=[FieldError(f"columns.{index}.field", "Each field can be in one column.")],
            )
        seen.add(column.field)
    if len(columns) > MAX_COLUMNS:
        raise ApiError(
            "validation_error", errors=[FieldError("columns", "Use 30 columns or fewer.")]
        )
    mapping = [c.model_dump() for c in columns]
    if conn.spreadsheet_id and conn.sheet_created:
        access = await _access(session, google, cipher, conn)
        try:
            await google.write_header(
                access, conn.spreadsheet_id, conn.sheet_tab or "", headers_of(mapping)
            )
        except GoogleError as error:
            raise _api_error(error) from error
    conn.mapping = mapping
    await session.flush()


# ---------------------------------------------------------------- the row


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(_text(v) for v in value)
    return str(value)


def row_values(mapping: list[dict[str, str]], source: dict[str, Any]) -> list[str]:
    """The cells of one row, in column order."""
    cells = []
    for column in mapping:
        field = column["field"]
        if field.startswith(CUSTOM):
            cells.append(_text((source.get("fields") or {}).get(field.removeprefix(CUSTOM))))
        else:
            cells.append(_text(source.get(field)))
    return cells


def _consent(consents: list[Any], channel: str | None) -> str:
    for consent in consents:
        if consent.channel == channel and consent.purpose == "marketing":
            return "Yes" if consent.status == ConsentStatus.GRANTED else "No"
    return ""


async def queue_lead(
    session: AsyncSession,
    contact: Contact,
    *,
    platform: str | None,
    automation_name: str,
    now: datetime | None = None,
) -> bool:
    """Queue a row for a captured lead, in the transaction that caused ``lead.captured``. Nothing
    happens without a connection, a sheet and a plan that includes Sheets sync."""
    from socialhood.services import contacts as contacts_service
    from socialhood.services.automations import capture

    conn = await get_connection(session)
    if conn is None or not conn.spreadsheet_id:
        return False
    if not entitlement(await current_plan(session), "sheets_sync"):
        return False
    now = now or datetime.now(UTC)
    mapping = list(conn.mapping or [])
    wanted = {c["field"].removeprefix(CUSTOM) for c in mapping if c["field"].startswith(CUSTOM)}
    consent = ""
    if any(c["field"] == "consent" for c in mapping):
        consent = _consent(
            await contacts_service.current_consents(session, contact.id),
            capture.consent_channel(platform or ""),
        )
    source = {
        "contact_name": contact.display_name or "",
        "username": contact.username or "",
        "platform": platform_name(platform) if platform else "",
        "email": contact.email or "",
        "phone": contact.phone or "",
        "fields": {k: v for k, v in (contact.fields or {}).items() if k in wanted},
        "automation": automation_name,
        "captured_at": now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "consent": consent,
    }
    row = SheetRow(
        connection_id=conn.id,
        event_id=uuid.uuid4(),
        source=source,
        status=DeliveryStatus.PENDING,
        attempts=0,
        next_attempt_at=now,
    )
    session.add(row)
    await session.flush()
    await enqueue_row(row.id)
    return True


async def requeue(
    session: AsyncSession, conn: GoogleConnection, codes: tuple[str, ...], *, now: datetime
) -> int:
    """Send the rows that failed for ``codes`` again, from the first attempt."""
    rows = list(
        (
            await session.scalars(
                select(SheetRow).where(
                    SheetRow.connection_id == conn.id,
                    SheetRow.status == DeliveryStatus.FAILED,
                    SheetRow.error_code.in_(codes),
                )
            )
        ).all()
    )
    for row in rows:
        row.status, row.attempts, row.error, row.error_code = (
            DeliveryStatus.PENDING,
            0,
            None,
            None,
        )
        row.next_attempt_at = now
    await session.flush()
    for row in rows:
        await enqueue_row(row.id)
    return len(rows)


async def enqueue_row(
    row_id: uuid.UUID, *, delay_s: float = START_DELAY_S, not_found: int = 0
) -> None:
    from socialhood.db.tenancy import require_workspace
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.outbound import append_sheet_row

    try:
        await enqueue(
            append_sheet_row,
            key=f"sheet:{row_id}",
            delay_s=delay_s,
            workspace_id=str(require_workspace()),
            row_id=str(row_id),
            not_found=not_found,
        )
    except Exception:  # never fail what raised the event; the row stays pending
        log.warning("sheet_enqueue_failed", row_id=str(row_id))


async def send_test(
    session: AsyncSession, google: GoogleClient, cipher: TokenCipher, *, now: datetime
) -> None:
    """Add a sample row now and say plainly if Google refuses it."""
    conn = await _live_connection(session, lock=True)
    if not conn.spreadsheet_id:
        raise ApiError("conflict", NO_SHEET_YET)
    access = await _access(session, google, cipher, conn)
    mapping = list(conn.mapping or [])
    sample = {
        "contact_name": "Test lead",
        "username": "test_lead",
        "platform": "Instagram",
        "email": "test@example.com",
        "phone": "+910000000000",
        "automation": "Test row from Amplychat",
        "captured_at": now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "consent": "Yes",
        "fields": {},
    }
    try:
        await google.append_row(
            access, conn.spreadsheet_id, conn.sheet_tab or "", row_values(mapping, sample)
        )
    except GoogleError as error:
        raise _api_error(error) from error
    conn.last_success_at = now
    await session.flush()


# ---------------------------------------------------------------- delivering


async def _fail(
    session: AsyncSession, row: SheetRow, code: str, *, now: datetime, conn: GoogleConnection | None
) -> None:
    row.status = DeliveryStatus.FAILED
    row.next_attempt_at = None
    row.error_code, row.error = code, REASONS[code]
    if conn is not None:
        conn.last_failure_at = now
        conn.last_error = REASONS[code]


async def _alert(session: AsyncSession, code: str, now: datetime) -> None:
    from socialhood.services.notifications import notify_admins

    await notify_admins(
        session,
        type=NotificationType.SHEETS_FAILING,
        severity="warning",
        title="Google Sheets sync needs attention",
        body=REASONS[code],
        link="/settings/integrations",
        dedupe_key=f"sheets:{code}:{now.date().isoformat()}",
    )


_KIND_CODE = {
    "auth": ACCESS_REMOVED,
    "not_found": SHEET_GONE,
    "forbidden": SHEET_REFUSED,
    "rejected": GOOGLE_REFUSED,
}

Enqueue = Callable[..., Awaitable[None]]


async def deliver(
    sessionmaker: async_sessionmaker[AsyncSession],
    cipher: TokenCipher,
    google: GoogleClient,
    *,
    row_id: uuid.UUID,
    now: datetime,
    enqueue: Enqueue = enqueue_row,
) -> Outcome:
    """One attempt at adding a row (the append_sheet_row job)."""
    async with sessionmaker() as session:
        row = await session.get(SheetRow, row_id)
        if row is None:
            return "missing"
        if row.status != DeliveryStatus.PENDING:
            return "done"
        conn = await session.get(GoogleConnection, row.connection_id)
        if conn is None:
            return "missing"
        if conn.status != GoogleStatus.ACTIVE:
            await _fail(session, row, ACCESS_REMOVED, now=now, conn=None)
            await session.commit()
            return "failed"
        if not conn.spreadsheet_id:
            await _fail(session, row, NO_SHEET, now=now, conn=None)
            await session.commit()
            return "failed"
        values = row_values(list(conn.mapping or []), row.source)
        spreadsheet_id, tab = conn.spreadsheet_id, conn.sheet_tab or ""
        credential = cipher.decrypt(conn.credential_enc)

    error: GoogleError | None = None
    try:
        access = await google.access_token(credential)
        await google.append_row(access, spreadsheet_id, tab, values)
    except GoogleError as failure:
        error = failure

    async with sessionmaker() as session:
        row = await session.get(SheetRow, row_id, with_for_update=True)
        if row is None or row.status != DeliveryStatus.PENDING:
            return "done"
        conn = await session.get(GoogleConnection, row.connection_id, with_for_update=True)
        row.attempts += 1
        row.last_attempt_at = now
        outcome: Outcome
        if error is None:
            row.status = DeliveryStatus.SUCCEEDED
            row.next_attempt_at = None
            row.error = row.error_code = None
            if conn is not None:
                conn.last_success_at = now
                conn.last_error = None
            outcome = "delivered"
        elif error.retryable and (wait := backoff(row.attempts)) is not None:
            row.next_attempt_at = now + wait
            row.error_code = GOOGLE_BUSY
            row.error = REASONS[GOOGLE_BUSY]
            await enqueue(row.id, delay_s=wait.total_seconds())
            outcome = "retrying"
        else:
            code = _KIND_CODE.get(error.kind, GOOGLE_BUSY)
            await _fail(session, row, code, now=now, conn=conn)
            if conn is not None and error.kind == "auth":
                conn.status = GoogleStatus.NEEDS_RECONNECT
            if error.kind in ("auth", "not_found", "forbidden"):
                await _alert(session, code, now)
            outcome = "failed"
        await session.commit()
    log.info(
        "sheet_row",
        row_id=str(row_id),
        outcome=outcome,
        error_kind=error.kind if error else None,
        attempts=row.attempts,
    )
    return outcome
