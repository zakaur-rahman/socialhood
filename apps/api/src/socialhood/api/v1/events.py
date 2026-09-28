"""GET /v1/w/{wid}/events: the workspace's real-time stream as Server-Sent Events (T3.4,
TR-RT-02). Resumes from Last-Event-ID; sends a resync event when that id has been trimmed.

The signature below is the P3 contract; T3.4 implements the body.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from socialhood.auth.deps import AnyMember

router = APIRouter(prefix="/v1/w/{wid}", tags=["realtime"])


# Stub until T3.4 lands: the tenancy suite skips x-pending routes. Delete this and the
# openapi_extra arguments when implementing.
PENDING = {"x-pending": "T3.4"}


@router.get(
    "/events",
    operation_id="stream_events",
    openapi_extra=PENDING,
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Event stream"}},
)
async def stream_events(
    ctx: AnyMember,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID", max_length=64)] = None,
) -> StreamingResponse:
    raise NotImplementedError("T3.4")
