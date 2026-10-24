"""Facebook text and link posts (GR-30): a scheduled post's format may be ``text``.

A text post has no media, only a caption, and publishes to Facebook Pages. The format check is
re-created with the new value. Expand-only: a wider check, no rows change.

Revision ID: 0039
Revises: 0038
Create Date: 2026-10-24 21:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FORMAT_CHECK = "ck_scheduled_posts_format"
OLD_FORMATS = ("image", "carousel", "reel", "story")
NEW_FORMATS = (*OLD_FORMATS, "text")


def _condition(values: Sequence[str]) -> str:
    listed = ", ".join(f"'{v}'" for v in values)
    return f"format IS NULL OR format IN ({listed})"


def upgrade() -> None:
    op.drop_constraint(op.f(FORMAT_CHECK), "scheduled_posts", type_="check")
    op.create_check_constraint(op.f(FORMAT_CHECK), "scheduled_posts", _condition(NEW_FORMATS))


def downgrade() -> None:
    # A text post can't stay under the old check: it becomes a draft with no format.
    op.execute("UPDATE scheduled_posts SET format = NULL, status = 'draft' WHERE format = 'text'")
    op.drop_constraint(op.f(FORMAT_CHECK), "scheduled_posts", type_="check")
    op.create_check_constraint(op.f(FORMAT_CHECK), "scheduled_posts", _condition(OLD_FORMATS))
