"""Real-time events (TR-RT-01, TR-RT-03): published after commit to a per-workspace Redis Stream.

Services queue events on the session while they work and call ``commit_and_publish`` instead of
``session.commit``: nothing is published for a transaction that rolls back, and a client never
hears about a row it cannot read yet. Publishing never fails the caller; a lost event is healed
by the client's resync (TR-RT-02).
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.inbox import Contact, Conversation, Message
from socialhood.observability.logging import get_logger
from socialhood.services.inbox_views import list_item, message_out

log = get_logger(__name__)

STREAM_MAXLEN = 10_000
MAX_EVENT_BYTES = 64 * 1024
_QUEUE_KEY = "realtime_events"
_AUTOMATION_RUN = "_automation_run_id"  # set by queue_message, removed before publishing

EventType = Literal[
    "message.created",
    "message.updated",
    "conversation.updated",
    "analysis.created",
    "suggestion.created",
    "suggestion.updated",
    "scheduled_message.updated",
    "scheduled_post.updated",  # {scheduled_post: ScheduledPost} (schemas/publishing.py, P7)
    "comment.created",  # {comment: Comment} (schemas/posts.py)
    "comment.updated",  # {comment: Comment}: analysis, hidden, reply, deleted
    "post.updated",  # {post: PostDetail}: comment counts, sentiment split, summary or topics (P6)
    "social_account.updated",
    "usage.updated",
    "notification.created",
    # Ask Social Hood (schemas/agent.py, PA): ids, statuses and plain-word steps, never the
    # request or answer (runs are the requester's; the stream is the workspace's).
    "agent.run.updated",  # {run: AgentRunEvent}: status or step progress
    "agent.step",  # AgentStepEvent: a step started (running) or ended
    "agent.completed",  # {run: AgentRunEvent}: a final status; the panel fetches the run
    "resync",
]


def stream_key(workspace_id: uuid.UUID) -> str:
    return f"events:{workspace_id}"


async def publish(
    redis: Redis, workspace_id: uuid.UUID, event_type: EventType, payload: dict[str, Any]
) -> str | None:
    """Append one event; returns its stream id, or None if it was not published."""
    data = json.dumps(payload, separators=(",", ":"), default=str)
    if len(data.encode()) > MAX_EVENT_BYTES:
        log.warning("realtime_event_too_large", event_type=event_type, bytes=len(data))
        return None
    try:
        event_id = await redis.xadd(
            stream_key(workspace_id),
            {"type": event_type, "data": data},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
    except Exception:
        log.warning("realtime_publish_failed", event_type=event_type)
        return None
    return event_id.decode() if isinstance(event_id, bytes) else str(event_id)


def queue(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    event_type: EventType,
    payload: dict[str, Any],
) -> None:
    """Queue an event to publish once this session's transaction commits."""
    session.info.setdefault(_QUEUE_KEY, []).append((workspace_id, event_type, payload))


def discard(session: AsyncSession) -> None:
    session.info.pop(_QUEUE_KEY, None)


async def commit_and_publish(session: AsyncSession, redis: Redis) -> None:
    try:
        await session.commit()
    except Exception:
        discard(session)
        raise
    pending = session.info.pop(_QUEUE_KEY, [])
    await _name_automations(session, pending)
    for workspace_id, event_type, payload in pending:
        await publish(redis, workspace_id, event_type, payload)


async def _name_automations(
    session: AsyncSession, pending: list[tuple[uuid.UUID, str, dict[str, Any]]]
) -> None:
    """Fill ``message.automation`` for messages an automation sent, one query per workspace, in
    that workspace's scope (webhook handlers publish after leaving theirs). An event without the
    name still says "Automation", so a failed lookup never stops publishing."""
    marked: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for workspace_id, _, payload in pending:
        if _AUTOMATION_RUN in payload:
            marked.setdefault(workspace_id, []).append(payload)
    if not marked:
        return
    from socialhood.repositories.automation_runs import automation_names

    for workspace_id, payloads in marked.items():
        try:
            with workspace_scope(workspace_id):
                names = await automation_names(session, [p[_AUTOMATION_RUN] for p in payloads])
        except Exception:
            log.warning("realtime_automation_names_failed", exc_info=True)
            names = {}
        for p in payloads:
            found = names.get(p.pop(_AUTOMATION_RUN))
            if found:
                p["message"]["automation"] = {"id": str(found[0]), "name": found[1]}


# ---- builders for the inbox events every producer emits


def queue_message(
    session: AsyncSession,
    msg: Message,
    *,
    created: bool,
    sent_by_name: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "conversation_id": str(msg.conversation_id),
        "message": message_out(msg, sent_by_name=sent_by_name).model_dump(mode="json"),
    }
    if msg.automation_run_id:  # named in commit_and_publish ("Automation · {name}")
        payload[_AUTOMATION_RUN] = msg.automation_run_id
    queue(session, msg.workspace_id, "message.created" if created else "message.updated", payload)


async def queue_conversation(
    session: AsyncSession,
    conv: Conversation,
    *,
    now: Any,
    human_agent: bool = False,
    contact: Contact | None = None,
) -> None:
    contact = contact or await session.get(Contact, conv.contact_id)
    if contact is None:
        return
    item = list_item(conv, contact, now=now, human_agent=human_agent)
    queue(
        session,
        conv.workspace_id,
        "conversation.updated",
        {"conversation": item.model_dump(mode="json")},
    )
