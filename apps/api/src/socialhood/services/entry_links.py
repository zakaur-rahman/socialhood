"""Entry links (GR-08): ``https://ig.me/m/<username>?ref=<code>`` opens a DM with the account and
Instagram sends the code back as a referral (GR-01 records it as the conversation's entry; the
runtime starts the link's automation, services/automations/entry). Admins only; nothing here
commits.

Rules:
- A link belongs to an Instagram account; its code is unique per account and never changes, so a
  printed QR code keeps working. Without a typed code, an 8-character one is made.
- Its automation must be an entry link automation of the same account (or none: opening the link
  then only records where the conversation came from). Deleting the automation keeps the link.
- Stats: conversations that began from the link, and the automation runs on them.
- WhatsApp has no ref parameter and its numbers don't run automations, so there are no WhatsApp
  links (C-084).
- The QR code (segno) holds the link's address, as SVG or PNG.
"""

from __future__ import annotations

import io
import secrets
import uuid

import segno
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.automations import EntryLink
from socialhood.models.connections import SocialAccount
from socialhood.repositories import automations as automations_repo
from socialhood.repositories import entry_links as repo
from socialhood.repositories import social_accounts as accounts
from socialhood.schemas.entry_links import EntryLink as EntryLinkOut
from socialhood.schemas.entry_links import (
    EntryLinkCreate,
    EntryLinkList,
    EntryLinkUpdate,
    QrFormat,
)

IG_ME = "https://ig.me/m"
MESSENGER_ME = "https://m.me"  # GR-29: a Facebook Page's chat, with the same ?ref=
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alikes
CODE_LENGTH = 8
CODE_TRIES = 5
QR_SCALE = 10  # pixels per module
QR_BORDER = 4  # the quiet zone the QR standard asks for, in modules
MEDIA_TYPES = {"svg": "image/svg+xml", "png": "image/png"}


def link_url(acct: SocialAccount, code: str) -> str:
    handle = acct.username or acct.platform_account_id
    if acct.platform == "facebook":
        return f"{MESSENGER_ME}/{handle}?ref={code}"
    return f"{IG_ME}/{handle}?ref={code}"


def _new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def _invalid(field: str, message: str) -> ApiError:
    return ApiError("validation_error", errors=[FieldError(field, message)])


async def _instagram_account(session: AsyncSession, account_id: uuid.UUID) -> SocialAccount:
    acct = await accounts.get(session, account_id)
    if acct is None:
        # Another workspace's account looks the same as none at all (tests/tenancy).
        raise ApiError("not_found", "That account wasn't found.")
    if acct.platform not in ("instagram", "facebook"):
        raise _invalid(
            "social_account_id",
            "Entry links open Instagram and Messenger chats. Choose an Instagram or Facebook "
            "account.",
        )
    return acct


async def _check_automation(
    session: AsyncSession, automation_id: uuid.UUID | None, account_id: uuid.UUID
) -> None:
    """The automation a link starts must be an entry link automation of the link's account."""
    if automation_id is None:
        return
    automation = await automations_repo.get(session, automation_id)
    if automation is None or automation.social_account_id != account_id:
        raise _invalid("automation_id", "That automation wasn't found on this account.")
    if automation.trigger != "entry_link":
        raise _invalid("automation_id", "Choose an automation that starts from an entry link.")


async def get_or_404(session: AsyncSession, link_id: uuid.UUID) -> EntryLink:
    link = await repo.get(session, link_id)
    if link is None:
        raise ApiError("not_found")
    return link


async def _project(session: AsyncSession, links: list[EntryLink]) -> list[EntryLinkOut]:
    """The links with their account, automation name and counts."""
    by_account: dict[uuid.UUID, list[str]] = {}
    for link in links:
        by_account.setdefault(link.social_account_id, []).append(link.code)
    opened: dict[tuple[uuid.UUID, str], int] = {}
    runs: dict[tuple[uuid.UUID, str], int] = {}
    for account_id, codes in by_account.items():
        for code, count in (await repo.opened_counts(session, account_id, codes)).items():
            opened[(account_id, code)] = count
        for code, count in (await repo.run_counts(session, account_id, codes)).items():
            runs[(account_id, code)] = count
    names = await repo.automation_names(
        session, [link.automation_id for link in links if link.automation_id is not None]
    )
    out: list[EntryLinkOut] = []
    for link in links:
        acct = await accounts.get(session, link.social_account_id)
        if acct is None:
            continue
        key = (link.social_account_id, link.code)
        out.append(
            EntryLinkOut(
                id=link.id,
                social_account_id=link.social_account_id,
                account_username=acct.username,
                name=link.name,
                code=link.code,
                url=link_url(acct, link.code),
                automation_id=link.automation_id,
                automation_name=names.get(link.automation_id) if link.automation_id else None,
                opened_conversations=opened.get(key, 0),
                runs=runs.get(key, 0),
                created_at=link.created_at,
            )
        )
    return out


async def list_links(session: AsyncSession, *, account_id: uuid.UUID | None) -> EntryLinkList:
    links = await repo.list_links(session, account_id=account_id)
    return EntryLinkList(items=await _project(session, links))


async def one(session: AsyncSession, link_id: uuid.UUID) -> EntryLinkOut:
    link = await get_or_404(session, link_id)
    return (await _project(session, [link]))[0]


async def create(session: AsyncSession, body: EntryLinkCreate) -> EntryLinkOut:
    acct = await _instagram_account(session, body.social_account_id)
    await _check_automation(session, body.automation_id, acct.id)
    created: EntryLink | None = None
    for _ in range(1 if body.code else CODE_TRIES):
        created = await repo.insert_link(
            session,
            {
                "social_account_id": acct.id,
                "automation_id": body.automation_id,
                "code": body.code or _new_code(),
                "name": body.name,
            },
        )
        if created is not None:
            break
    if created is None:
        if body.code:
            raise _invalid("code", "This account already has a link with that code.")
        raise ApiError("conflict", "Couldn't make a free code. Try again.")
    return (await _project(session, [created]))[0]


async def update(session: AsyncSession, link_id: uuid.UUID, body: EntryLinkUpdate) -> EntryLinkOut:
    link = await get_or_404(session, link_id)
    await _check_automation(session, body.automation_id, link.social_account_id)
    await repo.update_link(session, link.id, name=body.name, automation_id=body.automation_id)
    await session.refresh(link)
    return (await _project(session, [link]))[0]


async def delete(session: AsyncSession, link_id: uuid.UUID) -> None:
    link = await get_or_404(session, link_id)
    await repo.delete_link(session, link.id)


async def qr_code(session: AsyncSession, link_id: uuid.UUID, fmt: QrFormat) -> tuple[bytes, str]:
    """The link's QR code and its media type."""
    link = await get_or_404(session, link_id)
    acct = await accounts.get(session, link.social_account_id)
    if acct is None:
        raise ApiError("not_found")
    code = segno.make(link_url(acct, link.code), error="m")
    buffer = io.BytesIO()
    if fmt == "svg":
        code.save(buffer, kind="svg", scale=QR_SCALE, border=QR_BORDER, xmldecl=False)
    else:
        code.save(buffer, kind="png", scale=QR_SCALE, border=QR_BORDER)
    return buffer.getvalue(), MEDIA_TYPES[fmt]
