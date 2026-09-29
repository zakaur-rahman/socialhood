"""suggest_reply (T5.4; TR-AI-06) and decide_auto_reply (T5.6; TR-AI-07). Thin tasks: the work
is in services/suggestions/service.py and auto.py.

suggest_reply(workspace_id, conversation_id, message_id, regeneration=0): 2 tries (job
catalogue); only a retryable AI error (timeout, 429, 5xx) is retried, after 5 s, and the last
failure stores a failed suggestion. Analysis enqueues it by name with the first three arguments
(key ``suggest:{message_id}:0``); Regenerate passes ``regeneration`` = n (``suggest:{id}:{n}``).
decide_auto_reply(workspace_id, suggestion_id): 1 try (key ``auto:{suggestion_id}``).
"""

from __future__ import annotations

import uuid

from procrastinate import BaseRetryStrategy, JobContext, RetryDecision
from procrastinate.jobs import Job

from socialhood.ai.provider import AIError
from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.runtime import runtime
from socialhood.platforms.deps import deps_from
from socialhood.services.suggestions import auto, service

RETRY_AFTER_S = 5


class AIRetry(BaseRetryStrategy):
    """Retry retryable AIErrors only (TR-AI-03's provider already retried invalid output)."""

    def __init__(self, max_attempts: int) -> None:
        self.max_attempts = max_attempts

    def get_retry_decision(self, *, exception: BaseException, job: Job) -> RetryDecision | None:
        if not isinstance(exception, AIError) or not exception.retryable:
            return None
        if job.attempts + 1 >= self.max_attempts:
            return None
        return RetryDecision(retry_in={"seconds": RETRY_AFTER_S})


SUGGEST_RETRY = AIRetry(max_attempts=2)


@app.task(name="suggest_reply", queue=INTERACTIVE, retry=SUGGEST_RETRY, pass_context=True)
async def suggest_reply(
    context: JobContext,
    workspace_id: str,
    conversation_id: str,
    message_id: str,
    regeneration: int = 0,
) -> None:
    rt = runtime()
    job = context.job

    def will_retry(error: AIError) -> bool:
        return SUGGEST_RETRY.get_retry_decision(exception=error, job=job) is not None

    wid = uuid.UUID(workspace_id)
    with workspace_scope(wid):
        await service.generate(
            rt.sessionmaker,
            rt.redis,
            workspace_id=wid,
            conversation_id=uuid.UUID(conversation_id),
            message_id=uuid.UUID(message_id),
            regeneration=regeneration,
            will_retry=will_retry,
        )


@app.task(name="decide_auto_reply", queue=INTERACTIVE)
async def decide_auto_reply(workspace_id: str, suggestion_id: str) -> None:
    rt = runtime()
    with workspace_scope(uuid.UUID(workspace_id)):
        await auto.decide(
            rt.sessionmaker,
            rt.redis,
            deps_from(rt.http, rt.settings),
            suggestion_id=uuid.UUID(suggestion_id),
        )
