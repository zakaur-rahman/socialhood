"""A sequence's numbers (GR-24 follow-up): who entered and how it went for them, per sequence and
per step. Computed on the server from the enrolments and step runs, cached a few minutes.

Definitions (C-124):
- enrolled, active, completed, stopped: enrolments by status; stopped is split by why.
- sent, skipped (by reason), failed: step runs by status. A skipped or failed step is a finished
  step (the sequence goes on), so the three add up to the steps that ran.
- replied: a *sent* run followed by a customer message in the contact's conversation on the same
  account within ``REPLY_WINDOW`` (24 hours) of the run. A person who answers two steps counts once
  for each.
- per step, ``reached`` is the runs at that step plus the people it is next for, and ``share`` is
  ``reached`` over everyone who entered: the funnel.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.observability.logging import get_logger
from socialhood.repositories import sequences as repo
from socialhood.schemas import sequences as schemas
from socialhood.services.sequences import rules
from socialhood.services.sequences import service as sequence_service

log = get_logger(__name__)

REPLY_WINDOW = timedelta(hours=24)
CACHE_TTL_S = 300


def cache_key(sequence_id: uuid.UUID) -> str:
    return f"seqstats:{require_workspace()}:{sequence_id}"


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def build(
    *,
    sequence_id: uuid.UUID,
    step_count: int,
    enrolments: Mapping[str, int],
    stop_reasons: Mapping[str, int],
    runs: Sequence[tuple[int, str, str | None, int]],
    replies: Mapping[int, int],
    waiting: Mapping[int, int],
    now: datetime,
) -> schemas.SequenceAnalytics:
    """Pure: the numbers from the grouped counts (positions are 0-based in, 1-based out)."""
    enrolled = sum(enrolments.values())
    sent = skipped = failed = 0
    skipped_by: dict[str, int] = {}
    per_step: dict[int, dict[str, int]] = {}
    for position, status, code, n in runs:
        step = per_step.setdefault(position, {"sent": 0, "skipped": 0, "failed": 0})
        step[status] = step.get(status, 0) + n
        if status == "sent":
            sent += n
        elif status == "skipped":
            skipped += n
            skipped_by[code or "unknown"] = skipped_by.get(code or "unknown", 0) + n
        elif status == "failed":
            failed += n
    positions = sorted({*range(step_count), *per_step, *waiting})
    steps: list[schemas.StepStats] = []
    for position in positions:
        counts = per_step.get(position, {})
        reached = sum(counts.values()) + waiting.get(position, 0)
        replied = replies.get(position, 0)
        steps.append(
            schemas.StepStats(
                position=position + 1,
                reached=reached,
                waiting=waiting.get(position, 0),
                sent=counts.get("sent", 0),
                skipped=counts.get("skipped", 0),
                failed=counts.get("failed", 0),
                replied=replied,
                reply_rate=_rate(replied, counts.get("sent", 0)),
                share=round(reached / enrolled, 4) if enrolled else 0.0,
            )
        )
    replied_total = sum(replies.values())
    return schemas.SequenceAnalytics(
        sequence_id=sequence_id,
        window_hours=int(REPLY_WINDOW.total_seconds() // 3600),
        computed_at=now,
        enrolled=enrolled,
        active=enrolments.get("active", 0),
        completed=enrolments.get("completed", 0),
        stopped=enrolments.get("stopped", 0),
        stopped_by=[
            schemas.ReasonCount(code=code, text=rules.stop_text(code, None) or code, count=n)
            for code, n in sorted(stop_reasons.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        sent=sent,
        skipped=skipped,
        skipped_by=[
            schemas.ReasonCount(code=code, text=rules.REASONS.get(code, code), count=n)
            for code, n in sorted(skipped_by.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        failed=failed,
        replied=replied_total,
        reply_rate=_rate(replied_total, sent),
        steps=steps,
    )


async def get(
    session: AsyncSession, redis: Redis, sequence_id: uuid.UUID, *, now: datetime
) -> schemas.SequenceAnalytics:
    """GET .../sequences/{id}/analytics. 404 for a sequence of another workspace."""
    await sequence_service.get(session, sequence_id)
    key = cache_key(sequence_id)
    try:
        cached = await redis.get(key)
        if cached:
            return schemas.SequenceAnalytics.model_validate_json(cached)
    except Exception:
        log.warning("sequence_analytics_cache_unreadable", sequence_id=str(sequence_id))
    out = build(
        sequence_id=sequence_id,
        step_count=(await repo.step_counts(session, [sequence_id])).get(sequence_id, 0),
        enrolments=(await repo.enrolment_counts(session, [sequence_id])).get(sequence_id, {}),
        stop_reasons=await repo.stop_reason_counts(session, sequence_id),
        runs=await repo.run_counts(session, sequence_id),
        replies=await repo.replies_per_step(session, sequence_id, REPLY_WINDOW),
        waiting=await repo.waiting_per_step(session, sequence_id),
        now=now,
    )
    try:
        await redis.set(key, out.model_dump_json(), ex=CACHE_TTL_S)
    except Exception:
        log.warning("sequence_analytics_cache_unwritable", sequence_id=str(sequence_id))
    return out
