"""The MCP server (C-165, phase A): the audit of tool calls, upload tickets and the workspace's
AI connections mode.

- mcp_tool_calls: one row per tools/call (who, which credential and client, the tool, redacted
  arguments, the outcome, latency);
- mcp_uploads: media upload tickets (written from phase B, read by get_media_upload);
- workspaces.ai_connections_mode: off, read_only, read_drafts or full (default full; the plan
  caps it).

Expand-only: two new tables and a column with a default; no rows change.

Revision ID: 0054
Revises: 0053
Create Date: 2026-10-31 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "ai_connections_mode", sa.Text(), server_default=sa.text("'full'"), nullable=False
        ),
    )
    op.create_check_constraint(
        op.f("ck_workspaces_ai_connections_mode"),
        "workspaces",
        "ai_connections_mode IN ('off', 'read_only', 'read_drafts', 'full')",
    )

    op.create_table(
        "mcp_tool_calls",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("credential_kind", sa.Text(), nullable=False),
        sa.Column("api_key_id", sa.Uuid(), nullable=True),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("credential_label", sa.Text(), nullable=False),
        sa.Column("client_name", sa.Text(), nullable=True),
        sa.Column("client_version", sa.Text(), nullable=True),
        sa.Column("tool", sa.Text(), nullable=False),
        sa.Column(
            "arguments",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("arguments_digest", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "credential_kind IN ('api_key', 'oauth')", name=op.f("ck_mcp_tool_calls_credential_kind")
        ),
        sa.CheckConstraint(
            "outcome IN ('ok', 'error', 'refused')", name=op.f("ck_mcp_tool_calls_outcome")
        ),
        sa.CheckConstraint(
            "char_length(tool) BETWEEN 1 AND 64", name=op.f("ck_mcp_tool_calls_tool_length")
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_mcp_tool_calls_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_mcp_tool_calls_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["api_key_id"],
            ["api_keys.id"],
            name=op.f("fk_mcp_tool_calls_api_key_id_api_keys"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_tool_calls")),
    )
    op.create_index(
        op.f("ix_mcp_tool_calls_workspace_id"), "mcp_tool_calls", ["workspace_id"], unique=False
    )
    op.create_index(
        "ix_mcp_tool_calls_workspace_id_created_at",
        "mcp_tool_calls",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_mcp_tool_calls_api_key_id", "mcp_tool_calls", ["api_key_id"], unique=False
    )

    op.create_table(
        "mcp_uploads",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'waiting'"), nullable=False),
        sa.Column("public_id", sa.Text(), nullable=True),
        sa.Column("media_asset_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("kind IN ('image', 'video')", name=op.f("ck_mcp_uploads_kind")),
        sa.CheckConstraint(
            "status IN ('waiting', 'uploaded', 'expired', 'rejected')",
            name=op.f("ck_mcp_uploads_status"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_mcp_uploads_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_mcp_uploads_user_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["media_asset_id"],
            ["media_assets.id"],
            name=op.f("fk_mcp_uploads_media_asset_id_media_assets"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_uploads")),
    )
    op.create_index(
        op.f("ix_mcp_uploads_workspace_id"), "mcp_uploads", ["workspace_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mcp_uploads_workspace_id"), table_name="mcp_uploads")
    op.drop_table("mcp_uploads")
    op.drop_index("ix_mcp_tool_calls_api_key_id", table_name="mcp_tool_calls")
    op.drop_index("ix_mcp_tool_calls_workspace_id_created_at", table_name="mcp_tool_calls")
    op.drop_index(op.f("ix_mcp_tool_calls_workspace_id"), table_name="mcp_tool_calls")
    op.drop_table("mcp_tool_calls")
    op.drop_constraint(
        op.f("ck_workspaces_ai_connections_mode"), "workspaces", type_="check"
    )
    op.drop_column("workspaces", "ai_connections_mode")
