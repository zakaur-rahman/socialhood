"""Copilot write actions (GR-36): what an approval records, and the agent's audit trail.

- agent_approvals gains ``idempotency_key`` (the proposing step's key, unique per workspace, so a
  retried step finds its approval), ``outcome`` (what approving it did) and ``executed_at``;
- agent_approval_events: one row per proposal, approval, rejection, expiry and execution of a
  proposed write (who, when, what, outcome). Append-only.

Expand-only: nullable columns and a new table; nothing is rewritten.

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-24 18:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EVENTS = ("proposed", "approved", "rejected", "expired", "executed", "failed")


def upgrade() -> None:
    op.add_column("agent_approvals", sa.Column("idempotency_key", sa.Text(), nullable=True))
    op.add_column(
        "agent_approvals",
        sa.Column("outcome", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "agent_approvals", sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_unique_constraint(
        op.f("uq_agent_approvals_workspace_id_idempotency_key"),
        "agent_approvals",
        ["workspace_id", "idempotency_key"],
    )
    op.create_index(
        "ix_agent_approvals_pending_expiry",
        "agent_approvals",
        ["expires_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    listed = ", ".join(f"'{v}'" for v in EVENTS)
    op.create_table(
        "agent_approval_events",
        sa.Column("approval_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(f"event IN ({listed})", name=op.f("ck_agent_approval_events_event")),
        sa.CheckConstraint(
            "jsonb_typeof(detail) = 'object'", name=op.f("ck_agent_approval_events_detail")
        ),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["agent_approvals.id"],
            name=op.f("fk_agent_approval_events_approval_id_agent_approvals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_agent_approval_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_agent_approval_events_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_approval_events")),
    )
    op.create_index(
        op.f("ix_agent_approval_events_workspace_id"), "agent_approval_events", ["workspace_id"]
    )
    op.create_index(
        op.f("ix_agent_approval_events_approval_id"), "agent_approval_events", ["approval_id"]
    )


def downgrade() -> None:
    op.drop_table("agent_approval_events")
    op.drop_index("ix_agent_approvals_pending_expiry", table_name="agent_approvals")
    op.drop_constraint(
        op.f("uq_agent_approvals_workspace_id_idempotency_key"), "agent_approvals", type_="unique"
    )
    op.drop_column("agent_approvals", "executed_at")
    op.drop_column("agent_approvals", "outcome")
    op.drop_column("agent_approvals", "idempotency_key")
