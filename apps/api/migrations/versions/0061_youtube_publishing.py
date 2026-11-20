"""YouTube publishing (C-196).

- scheduled_post_targets.upload_expires_at: when a direct YouTube upload session (opened, not
  finished) runs out; NULL otherwise. Partial index for the expiry job.
- scheduled_post_targets.sent_metadata: what was last sent to YouTube for the target's video
  (title, description, privacy, publish time...), so an edit calls videos.update only when
  something YouTube holds changed.
- mcp_uploads.kind allows ``youtube`` (the AI-app upload page sends the file straight to YouTube),
  and mcp_uploads.scheduled_post_target_id ties such a ticket to its post's YouTube target.

Expand-only: a wider check and nullable columns.

Revision ID: 0061
Revises: 0060
Create Date: 2026-11-14 18:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0061"
down_revision: str | None = "0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_KINDS = "kind IN ('image', 'video')"
NEW_KINDS = "kind IN ('image', 'video', 'youtube')"


def upgrade() -> None:
    op.add_column(
        "scheduled_post_targets",
        sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "scheduled_post_targets",
        sa.Column("sent_metadata", postgresql.JSONB(), nullable=True),
    )
    op.create_index(
        "ix_scheduled_post_targets_upload_expires_at",
        "scheduled_post_targets",
        ["upload_expires_at"],
        unique=False,
        postgresql_where=sa.text("upload_expires_at IS NOT NULL"),
    )
    op.drop_constraint(op.f("ck_mcp_uploads_kind"), "mcp_uploads", type_="check")
    op.create_check_constraint(op.f("ck_mcp_uploads_kind"), "mcp_uploads", NEW_KINDS)
    op.add_column("mcp_uploads", sa.Column("scheduled_post_target_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_mcp_uploads_scheduled_post_target_id_scheduled_post_targets"),
        "mcp_uploads",
        "scheduled_post_targets",
        ["scheduled_post_target_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_mcp_uploads_scheduled_post_target_id"),
        "mcp_uploads",
        ["scheduled_post_target_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mcp_uploads_scheduled_post_target_id"), table_name="mcp_uploads")
    op.drop_constraint(
        op.f("fk_mcp_uploads_scheduled_post_target_id_scheduled_post_targets"),
        "mcp_uploads",
        type_="foreignkey",
    )
    op.drop_column("mcp_uploads", "scheduled_post_target_id")
    op.execute("DELETE FROM mcp_uploads WHERE kind = 'youtube'")
    op.drop_constraint(op.f("ck_mcp_uploads_kind"), "mcp_uploads", type_="check")
    op.create_check_constraint(op.f("ck_mcp_uploads_kind"), "mcp_uploads", OLD_KINDS)
    op.drop_index(
        "ix_scheduled_post_targets_upload_expires_at", table_name="scheduled_post_targets"
    )
    op.drop_column("scheduled_post_targets", "sent_metadata")
    op.drop_column("scheduled_post_targets", "upload_expires_at")
