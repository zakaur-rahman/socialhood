"""Sequence follow-ups (GR-24): start on a lead stage, stop when a tag is removed.

- sequences.entry_stage: the lead stage that starts a ``lead_stage`` sequence;
- sequences.stop_removed_tag_ids: tags whose removal stops the contact's enrolment;
- the entry_type and stop_reason checks gain ``lead_stage`` and ``tag_removed``.

Expand-only: two nullable or defaulted columns, and checks widened (every existing row still passes).

Revision ID: 0046
Revises: 0045
Create Date: 2026-10-26 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENTRY_OLD = "entry_type IN ('captured', 'tagged', 'broadcast_replied')"
ENTRY_NEW = "entry_type IN ('captured', 'tagged', 'broadcast_replied', 'lead_stage')"
STOP_OLD = "stop_reason IS NULL OR stop_reason IN ('reply', 'tag', 'stage', 'member', 'ended')"
STOP_NEW = (
    "stop_reason IS NULL OR stop_reason IN "
    "('reply', 'tag', 'tag_removed', 'stage', 'member', 'ended')"
)


def _swap(table: str, name: str, new: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, new)


def upgrade() -> None:
    op.add_column("sequences", sa.Column("entry_stage", sa.Text(), nullable=True))
    op.add_column(
        "sequences",
        sa.Column(
            "stop_removed_tag_ids",
            postgresql.ARRAY(sa.Uuid()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_sequences_entry_stage"),
        "sequences",
        "entry_stage IS NULL OR entry_stage IN ('new', 'qualified', 'follow_up', 'won', 'lost')",
    )
    op.create_check_constraint(
        op.f("ck_sequences_stop_removed_tag_ids_length"),
        "sequences",
        "cardinality(stop_removed_tag_ids) <= 20",
    )
    _swap("sequences", "entry_type", ENTRY_NEW)
    _swap("sequence_enrolments", "stop_reason", STOP_NEW)


def downgrade() -> None:
    _swap("sequence_enrolments", "stop_reason", STOP_OLD)
    _swap("sequences", "entry_type", ENTRY_OLD)
    op.drop_constraint(op.f("ck_sequences_stop_removed_tag_ids_length"), "sequences", type_="check")
    op.drop_constraint(op.f("ck_sequences_entry_stage"), "sequences", type_="check")
    op.drop_column("sequences", "stop_removed_tag_ids")
    op.drop_column("sequences", "entry_stage")
