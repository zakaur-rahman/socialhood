"""Facebook Reels (C-131): a scheduled post's kind may be ``reel``.

The composer's Reel choice publishes a Facebook Page's single video as a Reel instead of a normal
video. The kind check is re-created with the new value. Expand-only: a wider check, no rows
change.

Revision ID: 0052
Revises: 0051
Create Date: 2026-10-25 11:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KIND_CHECK = "ck_scheduled_posts_kind"
OLD_KINDS = ("post", "story")
NEW_KINDS = (*OLD_KINDS, "reel")


def _condition(values: Sequence[str]) -> str:
    listed = ", ".join(f"'{v}'" for v in values)
    return f"kind IN ({listed})"


def upgrade() -> None:
    op.drop_constraint(op.f(KIND_CHECK), "scheduled_posts", type_="check")
    op.create_check_constraint(op.f(KIND_CHECK), "scheduled_posts", _condition(NEW_KINDS))


def downgrade() -> None:
    # A Reel choice can't stay under the old check: it goes back to a normal post.
    op.execute("UPDATE scheduled_posts SET kind = 'post' WHERE kind = 'reel'")
    op.drop_constraint(op.f(KIND_CHECK), "scheduled_posts", type_="check")
    op.create_check_constraint(op.f(KIND_CHECK), "scheduled_posts", _condition(OLD_KINDS))
