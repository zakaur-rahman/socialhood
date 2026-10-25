"""Entry links API (GR-08): the ig.me links that open a DM with an account and start an entry link
automation, with their QR codes and counts. Owners and admins only. The rules are in
services/entry_links.py. Another workspace's link or account is 404 not_found or a field error."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from socialhood.auth.deps import Admin, CanManageAutomations, Session
from socialhood.schemas.entry_links import (
    EntryLink,
    EntryLinkCreate,
    EntryLinkList,
    EntryLinkUpdate,
    QrFormat,
)
from socialhood.services import entry_links as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["entry-links"])


@router.get("/entry-links", operation_id="list_entry_links")
async def list_entry_links(
    ctx: Admin,
    session: Session,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
) -> EntryLinkList:
    """The links, newest first, with the conversations and automation runs each has led to."""
    return await service.list_links(session, account_id=account_id)


@router.post("/entry-links", status_code=201, operation_id="create_entry_link")
async def create_entry_link(
    body: EntryLinkCreate, ctx: CanManageAutomations, session: Session
) -> EntryLink:
    """A link on an Instagram account. Leave ``code`` out and one is made; it can't change later."""
    link = await service.create(session, body)
    await session.commit()
    return link


@router.get("/entry-links/{link_id}", operation_id="get_entry_link")
async def get_entry_link(link_id: uuid.UUID, ctx: Admin, session: Session) -> EntryLink:
    return await service.one(session, link_id)


@router.put("/entry-links/{link_id}", operation_id="update_entry_link")
async def update_entry_link(
    link_id: uuid.UUID, body: EntryLinkUpdate, ctx: CanManageAutomations, session: Session
) -> EntryLink:
    """Rename the link or change the automation it starts. The account and code stay."""
    link = await service.update(session, link_id, body)
    await session.commit()
    return link


@router.delete("/entry-links/{link_id}", status_code=204, operation_id="delete_entry_link")
async def delete_entry_link(
    link_id: uuid.UUID, ctx: CanManageAutomations, session: Session
) -> Response:
    """Deleting a link stops its automation starting from it. Conversations it opened keep
    their entry."""
    await service.delete(session, link_id)
    await session.commit()
    return Response(status_code=204)


@router.get(
    "/entry-links/{link_id}/qr",
    operation_id="download_entry_link_qr",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}, "image/png": {}}}},
)
async def download_entry_link_qr(
    link_id: uuid.UUID,
    ctx: Admin,
    session: Session,
    format: Annotated[QrFormat, Query()] = "svg",
) -> Response:
    """The link's QR code as an image to download."""
    body, media_type = await service.qr_code(session, link_id, format)
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="entry-link.{format}"'},
    )
