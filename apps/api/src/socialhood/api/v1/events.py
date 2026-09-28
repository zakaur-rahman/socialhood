"""GET /v1/w/{wid}/events: the workspace's real-time stream as Server-Sent Events (T3.4,
TR-RT-02). Resumes from Last-Event-ID; sends a resync event when that id has been trimmed.

Authenticated like any route (Bearer). Browsers read it with fetch streaming, because EventSource
cannot send an Authorization header. The protocol is in ``realtime/stream.py``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from redis.exceptions import RedisError

from socialhood.auth.deps import AnyMember, Session
from socialhood.errors import ApiError
from socialhood.realtime import stream
from socialhood.realtime.events import stream_key

router = APIRouter(prefix="/v1/w/{wid}", tags=["realtime"])


@router.get(
    "/events",
    operation_id="stream_events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Event stream"}},
)
async def stream_events(
    request: Request,
    ctx: AnyMember,
    session: Session,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID", max_length=64)] = None,
) -> StreamingResponse:
    try:
        start = await stream.start_position(
            request.app.state.redis, stream_key(ctx.workspace_id), last_event_id
        )
    except RedisError as error:
        raise ApiError("service_unavailable", "Live updates are unavailable right now.") from error
    # The stream stays open for minutes: give the database connection back now.
    await session.close()
    reader = stream.connect(request.app.state.settings.redis_url, ctx.workspace_id)
    return StreamingResponse(
        stream.event_stream(
            reader, ctx.workspace_id, start, is_disconnected=request.is_disconnected
        ),
        media_type="text/event-stream",
        headers=stream.HEADERS,
    )
