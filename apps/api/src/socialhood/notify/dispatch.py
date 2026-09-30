"""Delivery jobs start after commit (T8.5, T8.6): an email or a push is recorded in the transaction
that caused it, and its job is deferred once that transaction commits, never for one that rolls
back.

``after_commit(session, task, id, workspace_id)`` records a job on the session. A SQLAlchemy
``after_commit`` listener defers the recorded jobs when the session's outermost transaction
commits. It runs inside ``AsyncSession.commit()``, so it awaits the defers through SQLAlchemy's
greenlet bridge and ``await session.commit()`` returns with the jobs queued; producers need no
extra call, whether they commit with ``session.commit()`` or ``events.commit_and_publish``. A
rollback of the outermost transaction drops the records.

A defer that fails (the queue is closed or unreachable) is logged and never fails the commit:
sweep_email_outbox re-enqueues emails still queued after a minute; a lost push stays an in-app
notification (a push is only worth sending while it is prompt).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction
from sqlalchemy.util import await_only
from sqlalchemy.util.concurrency import in_greenlet

from socialhood.observability.logging import get_logger

log = get_logger(__name__)

Task = Literal["deliver_email", "deliver_push"]
_KEY = "notify_after_commit"


@dataclass(frozen=True)
class PendingJob:
    task: Task
    id: uuid.UUID  # the email_deliveries row, or the notification to push
    workspace_id: uuid.UUID


def after_commit(
    session: AsyncSession | Session, task: Task, id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    """Defer ``task`` for ``id`` once this session's transaction commits."""
    pending: list[PendingJob] = session.info.setdefault(_KEY, [])
    pending.append(PendingJob(task, id, workspace_id))


def pending_jobs(session: AsyncSession | Session) -> list[PendingJob]:
    """The jobs waiting for this session's commit (tests)."""
    return list(session.info.get(_KEY, []))


def email_key(delivery_id: uuid.UUID) -> str:
    return f"email:{delivery_id}"


def push_key(notification_id: uuid.UUID) -> str:
    return f"push:{notification_id}"


async def defer(job: PendingJob) -> bool:
    """Queue one delivery job; False when one is already waiting (its queueing lock)."""
    from socialhood.jobs.app import INTERACTIVE
    from socialhood.jobs.enqueue import enqueue_named

    kwargs: dict[str, Any]
    if job.task == "deliver_email":
        key = email_key(job.id)
        kwargs = {"delivery_id": str(job.id)}
    else:
        key = push_key(job.id)
        kwargs = {"notification_id": str(job.id)}
    return await enqueue_named(
        job.task, lane=INTERACTIVE, key=key, workspace_id=str(job.workspace_id), **kwargs
    )


async def defer_quietly(job: PendingJob) -> bool:
    try:
        return await defer(job)
    except Exception:
        log.warning("notify_defer_failed", task=job.task, id=str(job.id))
        return False


@event.listens_for(Session, "after_commit")
def _defer_after_commit(session: Session) -> None:
    pending: list[PendingJob] | None = session.info.pop(_KEY, None)
    if not pending:
        return
    if not in_greenlet():  # a synchronous session: nothing here can await
        log.warning("notify_defer_skipped", jobs=len(pending))
        return
    for job in pending:
        await_only(defer_quietly(job))


@event.listens_for(Session, "after_soft_rollback")
def _drop_on_rollback(session: Session, previous_transaction: SessionTransaction) -> None:
    # Only the outermost transaction: a rolled-back savepoint leaves the rest of the
    # transaction's jobs in place (a job whose row went with the savepoint finds nothing).
    if previous_transaction.parent is None:
        session.info.pop(_KEY, None)
