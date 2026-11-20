"""Contact import from CSV (GR-43): a preview, then the same file saved. WhatsApp accounts only.

**The file** has the columns of the contacts export (any order, any case): ``Phone`` (required),
``Name``, ``Email``, ``Tags`` (separated by ";"), ``WhatsApp marketing`` ("yes" means agreed) and
one column per custom field, by its label or key. Other export columns (Username, Platform, ...) are
ignored and listed in the preview. A cell the export made safe for spreadsheets (a leading quote)
is read back as it was.

- A contact is matched by account and phone number. A new number is created (``contact.created``
  goes out); an existing contact only gets blanks filled and tags added, never an overwritten value.
  A file that is the export of the same account therefore changes nothing.
- Tags are written straight to ``contact_tags``, not through ``contacts.change_tags``: an import
  must not start tag-triggered sequences or send ``contact.tagged`` (one file would set off
  thousands of template sends). Unknown tags are created.
- **Consent (D1).** "WhatsApp marketing = yes" grants consent only when the admin ticked that
  these people agreed (``grant_consent``); otherwise the column is ignored. Each grant is a
  ``ConsentSource.IMPORT`` record whose evidence holds who imported, when, the file name and the
  CSV line. A contact whose latest record is withdrawn (a STOP reply, a member) is never granted.
- 5,000 rows per file. A row with a problem is left out with its reason; the rest is saved.
- The database work is batched (a few queries per file, inserts in bulk), not per row.

Pure parsing (``parse``) is separate from the database work (``plan`` and ``apply``).
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import SocialAccount
from socialhood.models.contacts import (
    ConsentChannel,
    ConsentPurpose,
    ConsentSource,
    ConsentStatus,
    ContactConsent,
    ContactFieldDefinition,
    ContactTag,
    FieldType,
    NameSource,
    Tag,
)
from socialhood.models.inbox import Contact
from socialhood.schemas.contacts import (
    ContactImportPreview,
    ContactImportResult,
    ContactImportRowOut,
)
from socialhood.services import contact_names
from socialhood.services import contacts as service

MAX_ROWS = 5000
MAX_SHOWN = 500  # rows listed in a preview (the counts cover them all)
BOM = chr(0xFEFF)
YES = {"yes", "y", "true", "1"}
CHUNK = 2000
COLUMNS = ("Phone", "Name", "Email", "Tags", "WhatsApp marketing")

COPY = {
    "no_header": "The first line must be the header row, with at least a Phone column.",
    "missing_phone": "The header row has no Phone column.",
    "empty": "The file has no rows.",
    "too_many": "One import takes up to {cap:,} rows. Split the file.",
    "not_whatsapp": (
        "Contacts can only be imported to a WhatsApp account. "
        "Instagram contacts appear when they message or comment."
    ),
    "phone_twice": "Another line has the same phone number.",
    "tag_long": "A tag can have up to 40 characters.",
    "name_long": "A name can have up to 200 characters.",
    "withdrawn": "Marketing consent was withdrawn, so it stays withdrawn.",
}


@dataclass
class Row:
    line: int
    phone: str = ""
    name: str | None = None
    email: str | None = None
    tags: list[str] = field(default_factory=list)
    fields: dict[str, Any] = field(default_factory=dict)
    wants_consent: bool = False  # the file says "yes"
    errors: list[str] = field(default_factory=list)
    # Settled by plan():
    contact: Contact | None = None
    fill_name: str | None = None
    fill_email: str | None = None
    fill_fields: dict[str, Any] = field(default_factory=dict)
    add_tags: list[str] = field(default_factory=list)
    grant: bool = False
    blocked: bool = False  # said yes, but a withdrawal stands

    @property
    def wa_id(self) -> str:
        return self.phone.removeprefix("+")

    @property
    def changes(self) -> bool:
        return bool(
            self.contact is None
            or self.fill_name
            or self.fill_email
            or self.fill_fields
            or self.add_tags
            or self.grant
        )


@dataclass
class Parsed:
    rows: list[Row]
    columns: list[str]
    ignored: list[str]


@dataclass
class Plan:
    account: SocialAccount
    parsed: Parsed
    grant_consent: bool
    new_tags: dict[str, str] = field(default_factory=dict)  # casefold -> name, to be created
    consent_ignored: int = 0  # "yes" rows left alone because the box wasn't ticked

    @property
    def rows(self) -> list[Row]:
        return self.parsed.rows

    @property
    def valid(self) -> list[Row]:
        return [r for r in self.rows if not r.errors]


def invalid(message: str) -> ApiError:
    return ApiError("validation_error", errors=[FieldError("csv", message)])


def _unquote(cell: str) -> str:
    """Undo ``contacts.safe_cell``: the export quotes a cell that starts like a formula."""
    cell = cell.strip()
    if cell[:1] == "'" and cell[1:2] in ("=", "+", "-", "@"):
        return cell[1:]
    return cell


def _delimiter(first_line: str) -> str:
    counts = {d: first_line.count(d) for d in (",", ";", "\t")}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] else ","


def _field_cell(definition: ContactFieldDefinition, text: str) -> Any:
    value: Any = text
    if definition.type == FieldType.NUMBER:
        try:
            value = int(text) if text.lstrip("-").isdigit() else float(text)
        except ValueError as error:
            raise ValueError("Enter a number.") from error
    elif definition.type == FieldType.CHOICE:
        value = next((o for o in definition.options if o.casefold() == text.casefold()), text)
    return service.field_value(definition, value)


def parse(text: str, definitions: list[ContactFieldDefinition]) -> Parsed:
    """Read the file into rows with their own problems. Raises ApiError for a file that isn't a
    contact list at all (no rows, no header, no Phone column, too many rows)."""
    text = text.removeprefix(BOM)
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise invalid(COPY["no_header"])
    reader = csv.DictReader(io.StringIO(text), delimiter=_delimiter(lines[0]))
    header = [h.strip().casefold() for h in (reader.fieldnames or [])]
    if "phone" not in header:
        raise invalid(COPY["missing_phone"])
    reader.fieldnames = header
    fixed = {c.casefold() for c in COLUMNS}
    by_header: dict[str, ContactFieldDefinition] = {}
    for d in definitions:
        for name in (d.key.casefold(), d.label.casefold()):
            if name not in fixed:
                by_header.setdefault(name, d)
    rows: list[Row] = []
    for raw in reader:
        cells = {k: _unquote(v) for k, v in raw.items() if k is not None and isinstance(v, str)}
        if not any(cells.values()):
            continue  # a blank line
        if len(rows) >= MAX_ROWS:
            raise invalid(COPY["too_many"].format(cap=MAX_ROWS))
        rows.append(_row(cells, reader.line_num, by_header))
    if not rows:
        raise invalid(COPY["empty"])
    known = fixed | set(by_header)
    return Parsed(
        rows=rows,
        columns=[c for c in COLUMNS if c.casefold() in header],
        ignored=[h for h in header if h and h not in known],
    )


def _row(cells: dict[str, str], line: int, by_header: dict[str, ContactFieldDefinition]) -> Row:
    row = Row(line=line)
    try:
        row.phone = service.normalize_phone(cells.get("phone", ""))
    except ValueError as error:
        row.errors.append(str(error))
    name = contact_names.clean(cells.get("name"))
    if name and len(name) > 200:
        row.errors.append(COPY["name_long"])
    row.name = name
    if cells.get("email"):
        try:
            row.email = service.normalize_email(cells["email"])
        except ValueError as error:
            row.errors.append(str(error))
    seen: set[str] = set()
    for tag in (t.strip() for t in cells.get("tags", "").split(";")):
        if not tag or tag.casefold() in seen:
            continue
        seen.add(tag.casefold())
        if len(tag) > 40:
            row.errors.append(COPY["tag_long"])
        else:
            row.tags.append(tag)
    for header, definition in by_header.items():
        if cells.get(header):
            try:
                row.fields[definition.key] = _field_cell(definition, cells[header])
            except ValueError as error:
                row.errors.append(f"{definition.label}: {error}")
    row.wants_consent = cells.get("whatsapp marketing", "").casefold() in YES
    return row


def _chunks(items: list[Any]) -> list[list[Any]]:
    return [items[i : i + CHUNK] for i in range(0, len(items), CHUNK)]


async def plan(
    session: AsyncSession, text: str, *, account_id: uuid.UUID, grant_consent: bool
) -> Plan:
    """Read, check and match the file against the account's contacts: a handful of queries."""
    account = await session.get(SocialAccount, account_id)
    if account is None:
        raise ApiError("not_found", "That account wasn't found.")
    if account.platform != "whatsapp":
        raise ApiError("validation_error", errors=[FieldError("account_id", COPY["not_whatsapp"])])
    definitions = list((await session.scalars(select(ContactFieldDefinition))).all())
    planned = Plan(account, parse(text, definitions), grant_consent)
    seen: set[str] = set()
    for row in planned.valid:
        if row.phone in seen:
            row.errors.append(COPY["phone_twice"])
        seen.add(row.phone)
    valid = planned.valid
    existing = await _contacts(session, account.id, [r.wa_id for r in valid])
    ids = [c.id for c in existing.values()]
    tags = {t.name.casefold(): t for t in (await session.scalars(select(Tag))).all()}
    have_tags = await _contact_tags(session, ids)
    latest = await _latest_consent(session, ids)
    for row in valid:
        contact = row.contact = existing.get(row.wa_id)
        if row.wants_consent and not grant_consent:
            planned.consent_ignored += 1
        grants = row.wants_consent and grant_consent
        if contact is None:
            row.grant = grants
            row.add_tags = row.tags
        else:
            _fill(row, contact)
            owned = have_tags.get(contact.id, set())
            row.add_tags = [
                t
                for t in row.tags
                if t.casefold() not in tags or tags[t.casefold()].id not in owned
            ]
            state = latest.get(contact.id)
            row.blocked = grants and state == ConsentStatus.REVOKED
            row.grant = grants and state is None
        for t in row.add_tags:
            if t.casefold() not in tags:
                planned.new_tags.setdefault(t.casefold(), t)
    return planned


def _fill(row: Row, contact: Contact) -> None:
    """What the file can fill in on an existing contact: only what is blank."""
    if row.name and not contact.display_name and row.name != service.display_name(contact):
        row.fill_name = row.name  # the export shows "Customer" for a nameless contact
    if row.email and not contact.email:
        row.fill_email = row.email
    have = contact.fields or {}
    row.fill_fields = {k: v for k, v in row.fields.items() if have.get(k) in (None, "")}


async def _contacts(
    session: AsyncSession, account_id: uuid.UUID, wa_ids: list[str]
) -> dict[str, Contact]:
    found: dict[str, Contact] = {}
    for chunk in _chunks(wa_ids):
        rows = await session.scalars(
            select(Contact).where(
                Contact.social_account_id == account_id, Contact.platform_user_id.in_(chunk)
            )
        )
        found.update({c.platform_user_id: c for c in rows.all()})
    return found


async def _contact_tags(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, set[Any]]:
    owned: dict[uuid.UUID, set[Any]] = {}
    for chunk in _chunks(ids):
        rows = await session.execute(
            select(ContactTag.contact_id, ContactTag.tag_id).where(ContactTag.contact_id.in_(chunk))
        )
        for contact_id, tag_id in rows.all():
            owned.setdefault(contact_id, set()).add(tag_id)
    return owned


async def _latest_consent(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """The current WhatsApp marketing status of each contact that has any record."""
    latest: dict[uuid.UUID, str] = {}
    for chunk in _chunks(ids):
        rows = await session.execute(
            select(ContactConsent.contact_id, ContactConsent.status)
            .where(
                ContactConsent.contact_id.in_(chunk),
                ContactConsent.channel == ConsentChannel.WHATSAPP,
                ContactConsent.purpose == ConsentPurpose.MARKETING,
            )
            .distinct(ContactConsent.contact_id)
            .order_by(
                ContactConsent.contact_id,
                ContactConsent.occurred_at.desc(),
                ContactConsent.created_at.desc(),
            )
        )
        latest.update({contact_id: status for contact_id, status in rows.all()})
    return latest


# ---------------------------------------------------------------- the preview and the save


def _action(row: Row) -> str:
    if row.errors:
        return "skip"
    if row.contact is None:
        return "create"
    return "update" if row.changes else "unchanged"


def _reasons(row: Row) -> list[str]:
    if row.errors:
        return row.errors
    return [COPY["withdrawn"]] if row.blocked else []


def _counts(planned: Plan) -> dict[str, int]:
    valid = planned.valid
    return {
        "created": sum(1 for r in valid if r.contact is None),
        "updated": sum(1 for r in valid if r.contact is not None and r.changes),
        "unchanged": sum(1 for r in valid if r.contact is not None and not r.changes),
        "skipped": len(planned.rows) - len(valid),
        "consents_granted": sum(1 for r in valid if r.grant),
        "consents_kept_withdrawn": sum(1 for r in valid if r.blocked),
        "tags_created": len(planned.new_tags),
    }


def preview(planned: Plan) -> ContactImportPreview:
    shown = [
        ContactImportRowOut.model_validate(
            {"line": r.line, "phone": r.phone, "action": _action(r), "reasons": _reasons(r)}
        )
        for r in planned.rows[:MAX_SHOWN]
    ]
    return ContactImportPreview(
        rows=shown,
        total_rows=len(planned.rows),
        row_cap=MAX_ROWS,
        consent_ignored=planned.consent_ignored,
        columns=planned.parsed.columns,
        ignored_columns=planned.parsed.ignored,
        **_counts(planned),
    )


async def apply(
    session: AsyncSession, planned: Plan, *, user_id: uuid.UUID, file_name: str
) -> ContactImportResult:
    """Save every valid row; the caller commits."""
    from socialhood.services.webhooks import events

    now = datetime.now(UTC)
    counts = _counts(planned)  # before the new contacts are attached to their rows
    tags = {t.name.casefold(): t for t in (await session.scalars(select(Tag))).all()}
    for key, name in planned.new_tags.items():
        tags[key] = Tag(name=name, color=0)
        session.add(tags[key])
    created: list[Contact] = []
    for row in planned.valid:
        contact = row.contact
        if contact is None:
            contact = row.contact = Contact(
                social_account_id=planned.account.id,
                platform_user_id=row.wa_id,
                display_name=row.name,
                name_source=NameSource.TEAM if row.name else NameSource.PLATFORM,
                phone=row.phone,
                phone_source="import",
                phone_verified=False,
                email=row.email,
                email_source="import" if row.email else None,
                email_verified=False,
                first_seen_at=now,
                fields=dict(row.fields),
            )
            session.add(contact)
            created.append(contact)
            continue
        if row.fill_name:
            contact_names.set_team_name(contact, row.fill_name)
        if row.fill_email:
            contact.email, contact.email_source = row.fill_email, "import"
        if row.fill_fields:
            contact.fields = {**(contact.fields or {}), **row.fill_fields}
    await session.flush()  # batched inserts for the new contacts and tags
    for row in planned.valid:
        assert row.contact is not None
        session.add_all(
            ContactTag(
                contact_id=row.contact.id,
                tag_id=tags[name.casefold()].id,
                added_by_user_id=user_id,
            )
            for name in row.add_tags
        )
        if row.grant:
            session.add(
                ContactConsent(
                    contact_id=row.contact.id,
                    channel=ConsentChannel.WHATSAPP,
                    purpose=ConsentPurpose.MARKETING,
                    status=ConsentStatus.GRANTED,
                    source=ConsentSource.IMPORT,
                    evidence={
                        "imported_by": str(user_id),
                        "imported_at": now.isoformat(),
                        "file_name": file_name[:200],
                        "row": row.line,  # the CSV line, the header being 1
                    },
                    occurred_at=now,
                )
            )
    await session.flush()
    if created and await events.wanted(session, "contact.created"):
        await events.emit_many(
            session,
            "contact.created",
            [{"contact": events.contact_ref(c, planned.account.platform)} for c in created],
            now=now,
        )
    return ContactImportResult(**counts)
