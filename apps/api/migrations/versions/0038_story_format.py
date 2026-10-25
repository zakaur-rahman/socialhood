"""Instagram Story scheduling (GR-39): a scheduled post's format may be ``story``, and the post
keeps what the owner chose (``kind``: post or story), so a Story draft with the wrong media is
still checked as a Story.

The format check is re-created with the new value; ``kind`` is added with the default ``post``,
which every existing row is. Expand-only.

Revision ID: 0038
Revises: 0037
Create Date: 2026-10-24 20:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FORMAT_CHECK = "ck_scheduled_posts_format"
OLD_FORMATS = ("image", "carousel", "reel")
NEW_FORMATS = (*OLD_FORMATS, "story")


def _condition(values: Sequence[str]) -> str:
    listed = ", ".join(f"'{v}'" for v in values)
    return f"format IS NULL OR format IN ({listed})"


def upgrade() -> None:
    op.drop_constraint(op.f(FORMAT_CHECK), "scheduled_posts", type_="check")
    op.create_check_constraint(op.f(FORMAT_CHECK), "scheduled_posts", _condition(NEW_FORMATS))
    op.add_column(
        "scheduled_posts",
        sa.Column("kind", sa.Text(), server_default=sa.text("'post'"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_scheduled_posts_kind"), "scheduled_posts", "kind IN ('post', 'story')"
    )
    op.create_check_constraint(
        op.f("ck_scheduled_posts_story_kind"),
        "scheduled_posts",
        "format IS DISTINCT FROM 'story' OR kind = 'story'",
    )


def downgrade() -> None:
    # A story can't stay under the old check: it becomes a draft with no format.
    op.execute("UPDATE scheduled_posts SET format = NULL, status = 'draft' WHERE format = 'story'")
    op.drop_constraint(op.f("ck_scheduled_posts_story_kind"), "scheduled_posts", type_="check")
    op.drop_constraint(op.f("ck_scheduled_posts_kind"), "scheduled_posts", type_="check")
    op.drop_column("scheduled_posts", "kind")
    op.drop_constraint(op.f(FORMAT_CHECK), "scheduled_posts", type_="check")
    op.create_check_constraint(op.f(FORMAT_CHECK), "scheduled_posts", _condition(OLD_FORMATS))
