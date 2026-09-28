"""Inbox rows for tests: a contact with a conversation and messages, scheduled messages, assets.

Rows are written through the ORM inside the workspace's scope, committed, and returned as ids,
so API tests (which use their own sessions) can read them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import Contact, Conversation, Message, ScheduledMessage
from socialhood.models.media import MediaAsset
from socialhood.services.inbox_views import conversation_touch


async def make_workspace(engine: AsyncEngine) -> uuid.UUID:
    """A bare workspace with an owner user, for tests below the API (no Clerk, no provisioning)."""
    suffix = uuid.uuid4().hex[:10]
    async with engine.begin() as conn:
        user_id = (
            await conn.execute(
                sql_text("INSERT INTO users (clerk_user_id, email) VALUES (:c, :e) RETURNING id"),
                {"c": f"user_{suffix}", "e": f"{suffix}@example.com"},
            )
        ).scalar_one()
        return (  # type: ignore[no-any-return]
            await conn.execute(
                sql_text(
                    "INSERT INTO workspaces (name, slug, owner_user_id)"
                    " VALUES (:n, :s, :o) RETURNING id"
                ),
                {"n": f"Workspace {suffix}", "s": f"ws-{suffix}", "o": user_id},
            )
        ).scalar_one()


async def make_account(
    engine: AsyncEngine,
    workspace_id: uuid.UUID | str,
    *,
    platform: str = "instagram",
    platform_account_id: str | None = None,
    username: str = "maple.bakery",
) -> uuid.UUID:
    """A connected account row (no token); a sandbox id unless one is given."""
    with workspace_scope(uuid.UUID(str(workspace_id))):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            acct = SocialAccount(
                platform=platform,
                platform_account_id=platform_account_id or f"sandbox_{uuid.uuid4().hex[:8]}",
                username=username,
                status="active",
                connected_at=datetime.now(UTC),
            )
            session.add(acct)
            await session.commit()
            return acct.id


@dataclass
class Thread:
    contact_id: uuid.UUID
    conversation_id: uuid.UUID
    message_ids: list[uuid.UUID] = field(default_factory=list)


async def make_thread(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    account_id: uuid.UUID | str,
    platform: str = "instagram",
    contact_ref: str | None = None,
    username: str | None = "priya.shah",
    display_name: str | None = "Priya Shah",
    texts: tuple[str, ...] = ("Do you ship to Pune?",),
    direction: str = "inbound",
    last_inbound_at: datetime | None = None,
    unread: int | None = None,
) -> Thread:
    """One contact, one conversation and ``texts`` as messages one minute apart (oldest first)."""
    wid = uuid.UUID(str(workspace_id))
    aid = uuid.UUID(str(account_id))
    now = datetime.now(UTC)
    with workspace_scope(wid):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            contact = Contact(
                social_account_id=aid,
                platform_user_id=contact_ref or f"igsid_{uuid.uuid4().hex[:12]}",
                username=username,
                display_name=display_name,
                first_seen_at=now - timedelta(minutes=len(texts)),
                last_seen_at=now,
            )
            session.add(contact)
            await session.flush()
            conv = Conversation(
                social_account_id=aid, contact_id=contact.id, platform=platform, status="open"
            )
            session.add(conv)
            await session.flush()
            thread = Thread(contact_id=contact.id, conversation_id=conv.id)
            last: Message | None = None
            for i, body in enumerate(texts):
                at = now - timedelta(minutes=len(texts) - i)
                msg = Message(
                    conversation_id=conv.id,
                    social_account_id=aid,
                    direction=direction,
                    source="customer" if direction == "inbound" else "human",
                    kind="text",
                    text=body,
                    occurred_at=at,
                    platform_message_id=f"mid_{uuid.uuid4().hex}",
                    status="received" if direction == "inbound" else "sent",
                )
                session.add(msg)
                await session.flush()
                thread.message_ids.append(msg.id)
                last = msg
            if last is not None:
                for key, value in conversation_touch(last).items():
                    setattr(conv, key, value)
            if direction == "inbound" and texts:
                conv.last_inbound_at = last_inbound_at or (last.occurred_at if last else now)
                conv.awaiting_reply = True
                conv.unread_count = len(texts) if unread is None else unread
            await session.commit()
    return thread


async def make_scheduled(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    conversation_id: uuid.UUID,
    text: str = "Following up on your order",
    send_at: datetime | None = None,
    status: str = "scheduled",
) -> uuid.UUID:
    with workspace_scope(uuid.UUID(str(workspace_id))):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = ScheduledMessage(
                conversation_id=conversation_id,
                text=text,
                send_at=send_at or datetime.now(UTC) + timedelta(hours=2),
                status=status,
            )
            session.add(row)
            await session.commit()
            return row.id


async def make_asset(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    purpose: str = "message",
    resource_type: str = "image",
) -> uuid.UUID:
    wid = uuid.UUID(str(workspace_id))
    with workspace_scope(wid):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = MediaAsset(
                public_id=f"ws/{wid}/{purpose}/{uuid.uuid4().hex}",
                resource_type=resource_type,
                purpose=purpose,
                format="jpg",
                secure_url="https://res.cloudinary.com/demo/image/upload/sample.jpg",
                bytes=120_000,
                width=1080,
                height=1080,
            )
            session.add(row)
            await session.commit()
            return row.id
