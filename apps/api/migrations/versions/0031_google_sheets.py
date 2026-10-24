"""Google Sheets sync (GR-27): a workspace's Google connection and the rows on their way to the sheet.

- google_connections: one per workspace; the connected account, Google's refresh credential
  (encrypted), the chosen sheet and the column mapping;
- sheet_rows: one captured lead to append, with its status, attempts and plain failure reason.

Expand-only: two new tables.

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-24 14:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031"
down_revision: str | None = "0030"
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
        "google_connections",
        sa.Column("google_email", sa.Text(), nullable=True),
        sa.Column("credential_enc", sa.LargeBinary(), nullable=False),
        sa.Column(
            "scopes",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("connected_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("spreadsheet_id", sa.Text(), nullable=True),
        sa.Column("spreadsheet_title", sa.Text(), nullable=True),
        sa.Column("spreadsheet_url", sa.Text(), nullable=True),
        sa.Column("sheet_tab", sa.Text(), nullable=True),
        sa.Column("sheet_created", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "mapping",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        *_common("google_connections"),
        sa.ForeignKeyConstraint(
            ["connected_by_user_id"],
            ["users.id"],
            name=op.f("fk_google_connections_connected_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'needs_reconnect')", name=op.f("ck_google_connections_status")
        ),
        sa.UniqueConstraint("workspace_id", name=op.f("uq_google_connections_workspace_id")),
    )
    op.create_index(
        op.f("ix_google_connections_workspace_id"), "google_connections", ["workspace_id"]
    )

    op.create_table(
        "sheet_rows",
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("source", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        *_common("sheet_rows"),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["google_connections.id"],
            name=op.f("fk_sheet_rows_connection_id_google_connections"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')", name=op.f("ck_sheet_rows_status")
        ),
        sa.UniqueConstraint(
            "connection_id", "event_id", name=op.f("uq_sheet_rows_connection_id_event_id")
        ),
    )
    op.create_index(op.f("ix_sheet_rows_workspace_id"), "sheet_rows", ["workspace_id"])
    op.create_index(
        "ix_sheet_rows_connection_created",
        "sheet_rows",
        ["connection_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("sheet_rows")
    op.drop_table("google_connections")
