"""Instagram Reel options (FR-PUB-07 follow-up, C-134): cover, feed sharing and audio name.

A post keeps a Reel's cover (an uploaded image or a frame offset in milliseconds), whether it also
shows in the feed (on, as before) and an optional audio name. Expand-only: new columns with
defaults, no rows change.

Revision ID: 0052
Revises: 0051
Create Date: 2026-10-25 14:30:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("scheduled_posts", sa.Column("cover_asset_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_scheduled_posts_cover_asset_id_media_assets"),
        "scheduled_posts",
        "media_assets",
        ["cover_asset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("scheduled_posts", sa.Column("cover_offset_ms", sa.Integer(), nullable=True))
    op.add_column(
        "scheduled_posts",
        sa.Column("share_to_feed", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column("scheduled_posts", sa.Column("audio_name", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_scheduled_posts_cover_offset"),
        "scheduled_posts",
        "cover_offset_ms IS NULL OR cover_offset_ms >= 0",
    )
    op.create_check_constraint(
        op.f("ck_scheduled_posts_audio_name_length"),
        "scheduled_posts",
        "audio_name IS NULL OR char_length(audio_name) BETWEEN 1 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_scheduled_posts_audio_name_length"), "scheduled_posts", type_="check")
    op.drop_constraint(op.f("ck_scheduled_posts_cover_offset"), "scheduled_posts", type_="check")
    op.drop_column("scheduled_posts", "audio_name")
    op.drop_column("scheduled_posts", "share_to_feed")
    op.drop_column("scheduled_posts", "cover_offset_ms")
    op.drop_constraint(
        op.f("fk_scheduled_posts_cover_asset_id_media_assets"), "scheduled_posts", type_="foreignkey"
    )
    op.drop_column("scheduled_posts", "cover_asset_id")
