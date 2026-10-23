"""Outbound webhooks (GR-04): a workspace's endpoints and their deliveries.

- webhook_endpoints: the address, the events it receives, its status (active, paused, disabled),
  its encrypted signing secret and its failure count;
- webhook_deliveries: one event to one endpoint, with its last attempt (status code, duration,
  reason) and when it's tried next.

Expand-only: two new tables.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-24 10:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common(table: str) -> list[object]:
    return [
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
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f(f"fk_{table}_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
    ]


def upgrade() -> None:
    op.create_table(
        "webhook_endpoints",
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("events", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("secret_enc", sa.LargeBinary(), nullable=False),
        sa.Column(
            "failing_deliveries", sa.SmallInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_common("webhook_endpoints"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_webhook_endpoints_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'disabled')", name=op.f("ck_webhook_endpoints_status")
        ),
        sa.CheckConstraint(
            "char_length(url) BETWEEN 8 AND 2000", name=op.f("ck_webhook_endpoints_url_length")
        ),
        sa.CheckConstraint(
            "cardinality(events) BETWEEN 1 AND 20", name=op.f("ck_webhook_endpoints_events")
        ),
    )
    op.create_index(
        op.f("ix_webhook_endpoints_workspace_id"), "webhook_endpoints", ["workspace_id"]
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("endpoint_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("replay_of_id", sa.Uuid(), nullable=True),
        *_common("webhook_deliveries"),
        sa.ForeignKeyConstraint(
            ["endpoint_id"],
            ["webhook_endpoints.id"],
            name=op.f("fk_webhook_deliveries_endpoint_id_webhook_endpoints"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["replay_of_id"],
            ["webhook_deliveries.id"],
            name=op.f("fk_webhook_deliveries_replay_of_id_webhook_deliveries"),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name=op.f("ck_webhook_deliveries_status"),
        ),
    )
    op.create_index(
        op.f("ix_webhook_deliveries_workspace_id"), "webhook_deliveries", ["workspace_id"]
    )
    op.create_index(
        "ix_webhook_deliveries_endpoint_created",
        "webhook_deliveries",
        ["endpoint_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_endpoints")
