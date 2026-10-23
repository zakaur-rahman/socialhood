"""Leads (GR-18): a lead stage on the contact, its history, and when a lead goes cold.

- contacts.lead_stage (new, qualified, follow_up, won, lost; default new), lead_stage_at,
  lead_stage_reason and lead_cold_at, with an index on (workspace, stage);
- lead_stage_changes: one row per move (from, to, who or what, and why);
- workspaces.lead_cold_days: days without a customer message before a lead goes cold (7).

Expand-only: columns with defaults (no table rewrite on PostgreSQL 11 and later) and a new table.
Existing contacts stay ``new``; nothing is backfilled.

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-24 20:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAGES = "'new', 'qualified', 'follow_up', 'won', 'lost'"


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column("lead_stage", sa.Text(), server_default=sa.text("'new'"), nullable=False),
    )
    op.add_column("contacts", sa.Column("lead_stage_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contacts", sa.Column("lead_stage_reason", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("lead_cold_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f("ck_contacts_lead_stage"), "contacts", f"lead_stage IN ({STAGES})"
    )
    op.create_check_constraint(
        op.f("ck_contacts_lead_stage_reason_length"),
        "contacts",
        "lead_stage_reason IS NULL OR char_length(lead_stage_reason) <= 300",
    )
    op.create_index("ix_contacts_lead_stage", "contacts", ["workspace_id", "lead_stage"])

    op.add_column(
        "workspaces",
        sa.Column("lead_cold_days", sa.SmallInteger(), server_default=sa.text("7"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_workspaces_lead_cold_days"), "workspaces", "lead_cold_days BETWEEN 1 AND 90"
    )

    op.create_table(
        "lead_stage_changes",
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("from_stage", sa.Text(), nullable=False),
        sa.Column("to_stage", sa.Text(), nullable=False),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("rule", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(f"from_stage IN ({STAGES})", name=op.f("ck_lead_stage_changes_from_stage")),
        sa.CheckConstraint(f"to_stage IN ({STAGES})", name=op.f("ck_lead_stage_changes_to_stage")),
        sa.CheckConstraint(
            "actor_kind IN ('member', 'automation', 'rule', 'system')",
            name=op.f("ck_lead_stage_changes_actor_kind"),
        ),
        sa.CheckConstraint(
            "reason IS NULL OR char_length(reason) <= 300",
            name=op.f("ck_lead_stage_changes_reason_length"),
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            name=op.f("fk_lead_stage_changes_contact_id_contacts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_lead_stage_changes_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_lead_stage_changes_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_stage_changes")),
    )
    op.create_index(
        op.f("ix_lead_stage_changes_workspace_id"), "lead_stage_changes", ["workspace_id"]
    )
    op.create_index(
        "ix_lead_stage_changes_contact",
        "lead_stage_changes",
        ["contact_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("lead_stage_changes")
    op.drop_constraint(op.f("ck_workspaces_lead_cold_days"), "workspaces", type_="check")
    op.drop_column("workspaces", "lead_cold_days")
    op.drop_index("ix_contacts_lead_stage", table_name="contacts")
    op.drop_constraint(op.f("ck_contacts_lead_stage_reason_length"), "contacts", type_="check")
    op.drop_constraint(op.f("ck_contacts_lead_stage"), "contacts", type_="check")
    for column in ("lead_cold_at", "lead_stage_reason", "lead_stage_at", "lead_stage"):
        op.drop_column("contacts", column)
