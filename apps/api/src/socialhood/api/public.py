"""The public API (GR-25, GR-26), all under /public/v1 and authenticated by a workspace API key
(auth/api_key.py): contacts, tags, conversations, messages and automation runs.

These handlers call the same services as the app's own routes (contacts, conversations, sending,
automation queries), so the rules and the errors are the same: a message is refused with
``reply_window_closed`` outside the platform's window, a contact field that doesn't fit is a 422,
an unknown id is a 404. Responses use the app's schemas where they fit (``ContactRecord``,
``MessageList``) and are listed in their own OpenAPI document, ``GET /public/v1/openapi.json``
(api/public_openapi.py), which the docs page renders. The app's own OpenAPI document leaves these
routes out.

Every route needs one scope (``/me`` excepted: any valid key); a key without it gets 403. Lists
are cursor-paged like the app's. The REST hooks are in api/public_hooks.py.

A key has scopes, not a role, so nothing here moves to require_permission when GR-19 lands.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse

from socialhood.api import ratelimit as route_limits
from socialhood.auth.api_key import ApiKeyContext, api_key_ctx, require_scope
from socialhood.auth.deps import Session
from socialhood.errors import ApiError
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.realtime import events
from socialhood.repositories import inbox
from socialhood.repositories import social_accounts as accounts
from socialhood.schemas.automations import AutomationRunList, RunResultName
from socialhood.schemas.contacts import (
    ContactCreate,
    ContactList,
    ContactPatch,
    ContactRecord,
    ContactTagsUpdate,
    FieldDefinitionList,
    FieldMatch,
    LeadStageName,
    TagList,
)
from socialhood.schemas.inbox import Conversation as ConversationOut
from socialhood.schemas.inbox import (
    ConversationList,
    ConversationListItem,
    InboxView,
    Message,
    MessageList,
    PlatformName,
)
from socialhood.schemas.public_api import (
    PublicAccount,
    PublicAccountList,
    PublicConversation,
    PublicKeyInfo,
    PublicSendMessage,
)
from socialhood.security import ratelimit
from socialhood.services import contacts as contact_service
from socialhood.services import conversations as conversation_service
from socialhood.services import idempotency, sending
from socialhood.services.automations import queries as automation_queries
from socialhood.services.contacts import ContactFilter
from socialhood.services.inbox_views import message_out

PREFIX = "/public/v1"
router = APIRouter(prefix=PREFIX)

ReadContacts = Annotated[ApiKeyContext, Depends(require_scope("contacts:read"))]
WriteContacts = Annotated[ApiKeyContext, Depends(require_scope("contacts:write"))]
ReadTags = Annotated[ApiKeyContext, Depends(require_scope("tags:read"))]
WriteTags = Annotated[ApiKeyContext, Depends(require_scope("tags:write"))]
ReadConversations = Annotated[ApiKeyContext, Depends(require_scope("conversations:read"))]
SendMessages = Annotated[ApiKeyContext, Depends(require_scope("messages:send"))]
ReadRuns = Annotated[ApiKeyContext, Depends(require_scope("automations:read"))]

IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        description="Send the same key again to retry a send without sending twice.",
    ),
]


def _deps(request: Request) -> PlatformDeps:
    return deps_from(request.app.state.http, request.app.state.settings)


def _human_agent_enabled(request: Request) -> bool:
    return bool(request.app.state.settings.ig_human_agent_enabled)


# ---------------------------------------------------------------- the document


@router.get("/openapi.json", include_in_schema=False, dependencies=[route_limits.PUBLIC])
async def public_openapi_document(request: Request) -> JSONResponse:
    from socialhood.api.public_openapi import public_openapi

    return JSONResponse(public_openapi(request.app))


# ---------------------------------------------------------------- the key itself


@router.get("/me", operation_id="get_key", tags=["Key"])
async def get_key(ctx: Annotated[ApiKeyContext, Depends(api_key_ctx)]) -> PublicKeyInfo:
    """The workspace the key belongs to and its scopes. Any valid key can call it; it is how a tool
    (the Zapier app) checks a key and names the connection."""
    return PublicKeyInfo(
        workspace_id=ctx.workspace_id,
        workspace_name=ctx.workspace.name,
        key_id=ctx.key_id,
        scopes=sorted(ctx.scopes),
    )


# ---------------------------------------------------------------- accounts


@router.get("/accounts", operation_id="list_accounts", tags=["Accounts"])
async def list_accounts(ctx: ReadContacts, session: Session) -> PublicAccountList:
    """The connected accounts: a new contact is added to one of them by its id."""
    return PublicAccountList(
        items=[PublicAccount.model_validate(a) for a in await accounts.list_all(session)]
    )


# ---------------------------------------------------------------- contacts


@router.get("/contacts", operation_id="list_contacts", tags=["Contacts"])
async def list_contacts(
    ctx: ReadContacts,
    session: Session,
    q: Annotated[str | None, Query(max_length=100)] = None,
    tag_id: Annotated[list[uuid.UUID] | None, Query(max_length=10)] = None,
    platform: Annotated[Literal["instagram", "whatsapp"] | None, Query()] = None,
    account_id: uuid.UUID | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    stage: Annotated[list[LeadStageName] | None, Query(max_length=5)] = None,
    field: Annotated[list[FieldMatch] | None, Query(max_length=5)] = None,
    sort: Annotated[
        Literal["activity", "created"],
        Query(description="Latest activity first (the default), or newest contact first."),
    ] = "activity",
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ContactList:
    """``tag_id`` repeats: a contact must carry every one. ``q`` matches part of the name,
    @username, email or phone. ``field`` repeats: ``city:pune`` matches a custom field's value
    ignoring case, ``city:*`` any value. ``stage`` repeats: any of those lead stages."""
    filt = ContactFilter(
        q=q,
        tag_ids=tuple(tag_id or ()),
        platform=platform,
        account_id=account_id,
        has_email=has_email,
        has_phone=has_phone,
        stages=tuple(stage or ()),
        fields=tuple(contact_service.parse_field_match(match) for match in field or ()),
    )
    await contact_service.check_filter(session, filt)
    return await contact_service.list_contacts(session, filt, cursor=cursor, limit=limit, sort=sort)


@router.post("/contacts", status_code=201, operation_id="create_contact", tags=["Contacts"])
async def create_contact(
    body: ContactCreate, ctx: WriteContacts, session: Session
) -> ContactRecord:
    """Add a customer to a WhatsApp account by phone number. 409 when the number is already a
    contact there; 422 for a number, email or field that doesn't fit."""
    contact_id = await contact_service.create_contact(session, body)
    out = await contact_service.get_record(session, contact_id)
    await session.commit()
    return out


@router.get("/contacts/{contact_id}", operation_id="get_contact", tags=["Contacts"])
async def get_contact(contact_id: uuid.UUID, ctx: ReadContacts, session: Session) -> ContactRecord:
    return await contact_service.get_record(session, contact_id)


@router.patch("/contacts/{contact_id}", operation_id="update_contact", tags=["Contacts"])
async def update_contact(
    contact_id: uuid.UUID, body: ContactPatch, ctx: WriteContacts, session: Session
) -> ContactRecord:
    """Change a contact's email, phone or custom fields; only what is sent changes. ``fields``
    merges and a key set to null is removed. 422 lists each value that doesn't fit (an email's
    shape, a phone without a country code, a field's type or an unknown field)."""
    await contact_service.update_contact(session, contact_id, body)
    out = await contact_service.get_record(session, contact_id)
    await session.commit()
    return out


@router.get("/contact-fields", operation_id="list_contact_fields", tags=["Contacts"])
async def list_contact_fields(ctx: ReadContacts, session: Session) -> FieldDefinitionList:
    """The custom fields a contact can hold: their keys, types and choices."""
    return await contact_service.list_fields(session)


# ---------------------------------------------------------------- tags


@router.get("/tags", operation_id="list_tags", tags=["Tags"])
async def list_tags(ctx: ReadTags, session: Session) -> TagList:
    """Every tag, by name, with how many contacts carry it."""
    return await contact_service.list_tags(session)


@router.post("/contacts/{contact_id}/tags", operation_id="change_contact_tags", tags=["Tags"])
async def change_contact_tags(
    contact_id: uuid.UUID, body: ContactTagsUpdate, ctx: WriteTags, session: Session
) -> ContactRecord:
    """Add and remove tags by id. 404 for a tag or contact that isn't there."""
    if not await contact_service.change_tags(
        session, [contact_id], add=body.add, remove=body.remove, user_id=None
    ):
        await contact_service.get_record(session, contact_id)  # 404
    out = await contact_service.get_record(session, contact_id)
    await session.commit()
    return out


# ---------------------------------------------------------------- conversations and messages


@router.get("/conversations", operation_id="list_conversations", tags=["Conversations"])
async def list_conversations(
    request: Request,
    ctx: ReadConversations,
    session: Session,
    view: Annotated[InboxView, Query()] = "all",
    platform: Annotated[PlatformName | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ConversationList:
    """Newest message first."""
    return await conversation_service.list_conversations(
        session,
        conversation_service.ListFilters(view=view, platform=platform, account_id=account_id, q=q),
        cursor=cursor,
        limit=limit,
        ig_human_agent_enabled=_human_agent_enabled(request),
        now=datetime.now(UTC),
    )


@router.get(
    "/conversations/{conversation_id}", operation_id="get_conversation", tags=["Conversations"]
)
async def get_conversation(
    request: Request, conversation_id: uuid.UUID, ctx: ReadConversations, session: Session
) -> PublicConversation:
    """The conversation and its reply window: whether a message can be sent now."""
    conv = await conversation_service.get_or_404(session, conversation_id)
    detail: ConversationOut = await conversation_service.conversation_detail(
        session, conv, ig_human_agent_enabled=_human_agent_enabled(request), now=datetime.now(UTC)
    )
    keep = set(ConversationListItem.model_fields) | {"reply_window", "last_inbound_at"}
    return PublicConversation.model_validate(detail.model_dump(include=keep))


@router.get(
    "/conversations/{conversation_id}/messages",
    operation_id="list_messages",
    tags=["Conversations"],
)
async def list_messages(
    conversation_id: uuid.UUID,
    ctx: ReadConversations,
    session: Session,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessageList:
    """Newest first; ``next_cursor`` loads older messages."""
    conv = await conversation_service.get_or_404(session, conversation_id)
    return await conversation_service.list_messages(session, conv, cursor=cursor, limit=limit)


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=202,
    operation_id="send_message",
    tags=["Conversations"],
)
async def send_message(
    request: Request,
    conversation_id: uuid.UUID,
    body: PublicSendMessage,
    ctx: SendMessages,
    session: Session,
    idempotency_key: IdempotencyKey = None,
) -> Message:
    """Queue a text message; the worker sends it. The platform's rules apply as in the app:
    409 ``reply_window_closed`` outside the reply window (24 hours from the customer's last
    message), 409 when the account needs reconnecting, 402 for an account the plan made
    read-only. Counts against the workspace's 60 sends a minute. With an ``Idempotency-Key``,
    the same key and body again returns the first response and sends nothing more."""
    await ratelimit.enforce(request, "sends", str(ctx.workspace_id))
    conv = await inbox.get_conversation(session, conversation_id)
    if conv is None:
        raise ApiError("not_found")
    redis = request.app.state.redis
    claim = None
    if idempotency_key is not None:
        claim = idempotency.IdempotencyKey(
            redis,
            workspace_id=ctx.workspace_id,
            user_id=ctx.key_id,
            key=idempotency_key,
            fingerprint=idempotency.fingerprint(
                "POST", request.url.path, body.model_dump(mode="json")
            ),
        )
        stored = await claim.begin()
        if stored is not None:
            return Message.model_validate(stored.body)
    client_id = body.client_id or (
        uuid.uuid5(uuid.NAMESPACE_URL, f"{conv.id}:{idempotency_key}")
        if idempotency_key is not None
        else uuid.uuid4()
    )
    try:
        msg = await sending.queue_outbound(
            session,
            conv,
            source="human",
            client_id=client_id,
            text=body.text,
            deps=_deps(request),
        )
        await events.commit_and_publish(session, redis)
    except BaseException:
        if claim is not None:
            await claim.release()
        raise
    out = message_out(msg)
    if claim is not None:
        await claim.complete(202, out.model_dump(mode="json"))
    return out


# ---------------------------------------------------------------- automation runs


@router.get("/automation-runs", operation_id="list_automation_runs", tags=["Automation runs"])
async def list_automation_runs(
    ctx: ReadRuns,
    session: Session,
    automation_id: uuid.UUID | None = None,
    result: Annotated[RunResultName | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AutomationRunList:
    """Every automation's runs, newest first; ``automation_id`` keeps one automation's."""
    return await automation_queries.list_runs(
        session, automation_id, result=result, cursor=cursor, limit=limit
    )
