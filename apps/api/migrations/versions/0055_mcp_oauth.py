"""The MCP server (C-165, phase C): OAuth for AI app connections.

- oauth_clients: the apps that may ask to connect (Client ID Metadata Documents and Dynamic
  Client Registration), across workspaces;
- mcp_connections: one member's consent for one client in one workspace;
- oauth_codes: single-use authorization codes (hashed, PKCE S256, resource-bound);
- oauth_tokens: hashed access (sho_) and rotating refresh (shr_) tokens;
- mcp_tool_calls.connection_id now references mcp_connections (phase A left it without a key).

Expand-only: four new tables, an index and a foreign key on a column that is still empty.

Revision ID: 0055
Revises: 0054
Create Date: 2026-10-31 18:13:25.318923+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("client_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("client_name", sa.Text(), nullable=False),
        sa.Column("client_uri", sa.Text(), nullable=True),
        sa.Column("logo_uri", sa.Text(), nullable=True),
        sa.Column("redirect_uris", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("token_endpoint_auth_method", sa.Text(), nullable=False),
        sa.Column("client_secret_hash", sa.Text(), nullable=True),
        sa.Column("software_id", sa.Text(), nullable=True),
        sa.Column("software_version", sa.Text(), nullable=True),
        sa.Column("metadata_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("kind IN ('cimd', 'dcr')", name=op.f("ck_oauth_clients_kind")),
        sa.CheckConstraint(
            "token_endpoint_auth_method IN ('none', 'client_secret_post', 'client_secret_basic')",
            name=op.f("ck_oauth_clients_auth_method"),
        ),
        sa.CheckConstraint(
            "cardinality(redirect_uris) BETWEEN 1 AND 10",
            name=op.f("ck_oauth_clients_redirect_uris"),
        ),
        sa.CheckConstraint(
            "char_length(client_name) BETWEEN 1 AND 100", name=op.f("ck_oauth_clients_name_length")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_clients")),
        sa.UniqueConstraint("client_id", name=op.f("uq_oauth_clients_client_id")),
    )
    op.create_table(
        "mcp_connections",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("oauth_client_id", sa.Uuid(), nullable=False),
        sa.Column("client_name", sa.Text(), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "revoke_reason IS NULL OR revoke_reason IN ('member', 'client', 'refresh_reuse', 'code_reuse', 'all')",
            name=op.f("ck_mcp_connections_revoke_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["oauth_client_id"],
            ["oauth_clients.id"],
            name=op.f("fk_mcp_connections_oauth_client_id_oauth_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["users.id"],
            name=op.f("fk_mcp_connections_revoked_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_mcp_connections_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_mcp_connections_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_connections")),
    )
    op.create_index(
        "ix_mcp_connections_oauth_client_id", "mcp_connections", ["oauth_client_id"], unique=False
    )
    op.create_index("ix_mcp_connections_user_id", "mcp_connections", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_mcp_connections_workspace_id"), "mcp_connections", ["workspace_id"], unique=False
    )
    op.create_table(
        "oauth_codes",
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("oauth_client_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("client_name", sa.Text(), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("code_challenge", sa.Text(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["mcp_connections.id"],
            name=op.f("fk_oauth_codes_connection_id_mcp_connections"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["oauth_client_id"],
            ["oauth_clients.id"],
            name=op.f("fk_oauth_codes_oauth_client_id_oauth_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_oauth_codes_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_oauth_codes_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_codes")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_oauth_codes_code_hash")),
    )
    op.create_index(
        op.f("ix_oauth_codes_workspace_id"), "oauth_codes", ["workspace_id"], unique=False
    )
    op.create_table(
        "oauth_tokens",
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("kind IN ('access', 'refresh')", name=op.f("ck_oauth_tokens_kind")),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["mcp_connections.id"],
            name=op.f("fk_oauth_tokens_connection_id_mcp_connections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_oauth_tokens_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_oauth_tokens_token_hash")),
    )
    op.create_index(
        "ix_oauth_tokens_connection_id", "oauth_tokens", ["connection_id"], unique=False
    )
    op.create_index(
        op.f("ix_oauth_tokens_workspace_id"), "oauth_tokens", ["workspace_id"], unique=False
    )
    op.create_index(
        "ix_mcp_tool_calls_connection_id_created_at",
        "mcp_tool_calls",
        ["connection_id", "created_at"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_mcp_tool_calls_connection_id_mcp_connections"),
        "mcp_tool_calls",
        "mcp_connections",
        ["connection_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_mcp_tool_calls_connection_id_mcp_connections"),
        "mcp_tool_calls",
        type_="foreignkey",
    )
    op.drop_index("ix_mcp_tool_calls_connection_id_created_at", table_name="mcp_tool_calls")
    op.drop_index(op.f("ix_oauth_tokens_workspace_id"), table_name="oauth_tokens")
    op.drop_index("ix_oauth_tokens_connection_id", table_name="oauth_tokens")
    op.drop_table("oauth_tokens")
    op.drop_index(op.f("ix_oauth_codes_workspace_id"), table_name="oauth_codes")
    op.drop_table("oauth_codes")
    op.drop_index(op.f("ix_mcp_connections_workspace_id"), table_name="mcp_connections")
    op.drop_index("ix_mcp_connections_user_id", table_name="mcp_connections")
    op.drop_index("ix_mcp_connections_oauth_client_id", table_name="mcp_connections")
    op.drop_table("mcp_connections")
    op.drop_table("oauth_clients")
