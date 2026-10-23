"""Saved segments for the contacts page (GR-17).

- contact_segments: a workspace's named, saved contact filters (the filter as JSON, a unique
  case-insensitive name per workspace).

Expand-only: one new table.

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-24 18:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contact_segments",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "filter",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 60", name=op.f("ck_contact_segments_name_length")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_contact_segments_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_contact_segments_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_segments")),
    )
    op.create_index(op.f("ix_contact_segments_workspace_id"), "contact_segments", ["workspace_id"])
    op.create_index(
        "uq_contact_segments_workspace_name",
        "contact_segments",
        ["workspace_id", sa.text("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("contact_segments")
