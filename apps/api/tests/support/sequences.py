"""Helpers for tests below the API that need sequence rows (GR-24): the isolation and account
deletion tests."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def make_sequence_rows(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    account_id: uuid.UUID | str,
    contact_id: uuid.UUID | str,
    message_id: uuid.UUID | str | None = None,
) -> tuple[str, str]:
    """A sequence with one step, the contact in it with one step run. Returns (sequence id,
    enrolment id)."""
    async with engine.begin() as conn:
        sequence = (
            await conn.execute(
                text(
                    "INSERT INTO sequences (workspace_id, social_account_id, name, status,"
                    " entry_type) VALUES (:w, :a, 'Follow up', 'paused', 'captured') RETURNING id"
                ),
                {"w": workspace_id, "a": account_id},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO sequence_steps (workspace_id, sequence_id, position, delay_seconds,"
                " delay_from, text) VALUES (:w, :s, 0, 60, 'entry', 'Hi')"
            ),
            {"w": workspace_id, "s": sequence},
        )
        enrolment = (
            await conn.execute(
                text(
                    "INSERT INTO sequence_enrolments (workspace_id, sequence_id, contact_id,"
                    " social_account_id, status, current_step, next_due_at, enrolled_at,"
                    " entry_event) VALUES (:w, :s, :c, :a, 'active', 1, now(), now(),"
                    " 'Gave their email') RETURNING id"
                ),
                {"w": workspace_id, "s": sequence, "c": contact_id, "a": account_id},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO sequence_step_runs (workspace_id, enrolment_id, sequence_id,"
                " social_account_id, contact_id, position, status, sent_as, message_id, ran_at)"
                " VALUES (:w, :e, :s, :a, :c, 0, 'sent', 'text', :m, now())"
            ),
            {
                "w": workspace_id,
                "e": enrolment,
                "s": sequence,
                "a": account_id,
                "c": contact_id,
                "m": message_id,
            },
        )
    return str(sequence), str(enrolment)
