"""Instagram publishing extras (FR-PUB-07, C-134): collaborators, user tags and location.

A post keeps its collaborator usernames and its location (a Facebook Page id); each image keeps
its user tags; each target keeps the collaborators' invite status read after publishing.
Expand-only: new columns with defaults, no rows change.

Revision ID: 0051
Revises: 0050
Create Date: 2026-10-25 14:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0051"
down_revision: str | None = "0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scheduled_posts",
        sa.Column(
            "collaborators",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.add_column("scheduled_posts", sa.Column("location_id", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_scheduled_posts_collaborators"),
        "scheduled_posts",
        "cardinality(collaborators) <= 3",
    )
    op.add_column(
        "scheduled_post_assets",
        sa.Column(
            "user_tags",
            postgresql.JSONB(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column(
        "scheduled_post_targets",
        sa.Column(
            "collaborator_statuses",
            postgresql.JSONB(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column(
        "scheduled_post_targets",
        sa.Column("collaborators_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scheduled_post_targets", "collaborators_checked_at")
    op.drop_column("scheduled_post_targets", "collaborator_statuses")
    op.drop_column("scheduled_post_assets", "user_tags")
    op.drop_constraint(op.f("ck_scheduled_posts_collaborators"), "scheduled_posts", type_="check")
    op.drop_column("scheduled_posts", "location_id")
    op.drop_column("scheduled_posts", "collaborators")
