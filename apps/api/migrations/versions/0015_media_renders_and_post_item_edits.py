"""P7b media editor (§5.7; FR-PUB-20…27, TR-MED-04, TR-MED-05): media_renders (one edit of one
upload and its rendered file; unique per asset and spec hash, so the same edit renders once;
counted by kind and created_at for video_renders_monthly), scheduled_post_assets.edit_spec and
render_id (the item's edit and its render; a render needs an edit), and webhook_events.provider
takes cloudinary (render notifications).

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-30 04:49:00.246823+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDERS = "'instagram', 'whatsapp', 'dodo', 'clerk'"


def upgrade() -> None:
    op.create_table(
        "media_renders",
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("spec_hash", sa.Text(), nullable=False),
        sa.Column("transformation", sa.Text(), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("batch_id", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_s", sa.REAL(), nullable=True),
        sa.Column("bytes", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("poll_count", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
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
            "(kind = 'image' AND format = 'jpg') OR (kind = 'video' AND format = 'mp4')",
            name=op.f("ck_media_renders_format"),
        ),
        sa.CheckConstraint("kind IN ('image', 'video')", name=op.f("ck_media_renders_kind")),
        sa.CheckConstraint("spec_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_media_renders_spec_hash")),
        sa.CheckConstraint(
            "status <> 'failed' OR error IS NOT NULL", name=op.f("ck_media_renders_failed")
        ),
        sa.CheckConstraint(
            "status <> 'ready' OR (url IS NOT NULL AND ready_at IS NOT NULL)",
            name=op.f("ck_media_renders_ready"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'rendering', 'ready', 'failed')",
            name=op.f("ck_media_renders_status"),
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND poll_count >= 0", name=op.f("ck_media_renders_counters")
        ),
        sa.ForeignKeyConstraint(
            ["media_asset_id"],
            ["media_assets.id"],
            name=op.f("fk_media_renders_media_asset_id_media_assets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_media_renders_requested_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_media_renders_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_renders")),
        sa.UniqueConstraint(
            "media_asset_id", "spec_hash", name=op.f("uq_media_renders_media_asset_id_spec_hash")
        ),
    )
    op.create_index(
        "ix_media_renders_batch_id",
        "media_renders",
        ["batch_id"],
        unique=False,
        postgresql_where=sa.text("batch_id IS NOT NULL"),
    )
    op.create_index(
        "ix_media_renders_unfinished",
        "media_renders",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("status IN ('pending', 'rendering')"),
    )
    op.create_index(
        op.f("ix_media_renders_workspace_id"), "media_renders", ["workspace_id"], unique=False
    )
    op.create_index(
        "ix_media_renders_workspace_kind_created",
        "media_renders",
        ["workspace_id", "kind", "created_at"],
        unique=False,
    )

    op.add_column(
        "scheduled_post_assets",
        sa.Column("edit_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("scheduled_post_assets", sa.Column("render_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_scheduled_post_assets_render_id"),
        "scheduled_post_assets",
        ["render_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_scheduled_post_assets_render_id_media_renders"),
        "scheduled_post_assets",
        "media_renders",
        ["render_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        op.f("ck_scheduled_post_assets_render_has_edit"),
        "scheduled_post_assets",
        "render_id IS NULL OR edit_spec IS NOT NULL",
    )

    op.drop_constraint(op.f("ck_webhook_events_provider"), "webhook_events", type_="check")
    op.create_check_constraint(
        op.f("ck_webhook_events_provider"),
        "webhook_events",
        f"provider IN ({PROVIDERS}, 'cloudinary')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM webhook_events WHERE provider = 'cloudinary'")
    op.drop_constraint(op.f("ck_webhook_events_provider"), "webhook_events", type_="check")
    op.create_check_constraint(
        op.f("ck_webhook_events_provider"), "webhook_events", f"provider IN ({PROVIDERS})"
    )

    op.drop_constraint(
        op.f("ck_scheduled_post_assets_render_has_edit"), "scheduled_post_assets", type_="check"
    )
    op.drop_constraint(
        op.f("fk_scheduled_post_assets_render_id_media_renders"),
        "scheduled_post_assets",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_scheduled_post_assets_render_id"), table_name="scheduled_post_assets")
    op.drop_column("scheduled_post_assets", "render_id")
    op.drop_column("scheduled_post_assets", "edit_spec")

    op.drop_index("ix_media_renders_workspace_kind_created", table_name="media_renders")
    op.drop_index(op.f("ix_media_renders_workspace_id"), table_name="media_renders")
    op.drop_index(
        "ix_media_renders_unfinished",
        table_name="media_renders",
        postgresql_where=sa.text("status IN ('pending', 'rendering')"),
    )
    op.drop_index(
        "ix_media_renders_batch_id",
        table_name="media_renders",
        postgresql_where=sa.text("batch_id IS NOT NULL"),
    )
    op.drop_table("media_renders")
