"""Automation flows (GR-03): saved flow versions, and the version an automation and a run follow.

- automation_flows: an automation's flow as saved (schemas/flows.FlowDefinition as JSON), one row
  per version;
- automations.flow_version: the version it runs; NULL means its flow is compiled from its message
  settings, which is every automation today (services/automations/flows.compile_legacy);
- automation_runs: flow_version (the version a flow run follows), step_id, flow_state and
  wait_until (where it is and what it waits for), and an index for the runs waiting for a
  contact's answer;
- automation_run_steps: a flow run's step log.

Expand-only: new tables and nullable columns; nothing is rewritten.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-23 18:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_flows",
        sa.Column("automation_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_automation_flows_version")),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automations.id"],
            name=op.f("fk_automation_flows_automation_id_automations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_automation_flows_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_automation_flows_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation_flows")),
        sa.UniqueConstraint(
            "automation_id", "version", name=op.f("uq_automation_flows_automation_id_version")
        ),
    )
    op.create_index(op.f("ix_automation_flows_workspace_id"), "automation_flows", ["workspace_id"])
    op.add_column("automations", sa.Column("flow_version", sa.Integer(), nullable=True))
    op.add_column("automation_runs", sa.Column("flow_version", sa.Integer(), nullable=True))
    op.add_column("automation_runs", sa.Column("step_id", sa.Text(), nullable=True))
    op.add_column("automation_runs", sa.Column("flow_state", sa.Text(), nullable=True))
    op.add_column(
        "automation_runs", sa.Column("wait_until", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "flow_state",
        "automation_runs",
        "flow_state IS NULL OR flow_state IN ('sending', 'replying', 'next', 'delaying', 'done')",
    )
    op.create_index(
        "ix_automation_runs_flow_replying",
        "automation_runs",
        ["contact_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("flow_state = 'replying'"),
    )

    op.create_table(
        "automation_run_steps",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('sent', 'waiting', 'done', 'failed')",
            name=op.f("ck_automation_run_steps_status"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["automation_runs.id"],
            name=op.f("fk_automation_run_steps_run_id_automation_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_automation_run_steps_message_id_messages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_automation_run_steps_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation_run_steps")),
        sa.UniqueConstraint(
            "run_id", "step_id", name=op.f("uq_automation_run_steps_run_id_step_id")
        ),
    )
    op.create_index(
        op.f("ix_automation_run_steps_workspace_id"), "automation_run_steps", ["workspace_id"]
    )


def downgrade() -> None:
    op.drop_table("automation_run_steps")
    op.drop_index("ix_automation_runs_flow_replying", table_name="automation_runs")
    op.drop_constraint(op.f("ck_automation_runs_flow_state"), "automation_runs", type_="check")
    for column in ("wait_until", "flow_state", "step_id", "flow_version"):
        op.drop_column("automation_runs", column)
    op.drop_column("automations", "flow_version")
    op.drop_table("automation_flows")
