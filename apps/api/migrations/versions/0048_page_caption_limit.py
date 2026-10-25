"""A longer caption for Facebook Pages (C-131): the caption checks hold up to 63,206 characters.

Instagram's 2,200 characters is still enforced, per platform, by the composer's checklist and the
scheduling rules; the database only holds the longest any platform takes. Both checks are
re-created with the wider limit. Expand-only: nothing that fit before stops fitting.

Revision ID: 0048
Revises: 0047
Create Date: 2026-10-25 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0048"
down_revision: str | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_MAX = 2200
NEW_MAX = 63_206

CHECKS = (
    ("ck_scheduled_posts_caption_length", "scheduled_posts", "char_length(caption) <= {limit}"),
    (
        "ck_scheduled_post_targets_caption_override_length",
        "scheduled_post_targets",
        "caption_override IS NULL OR char_length(caption_override) <= {limit}",
    ),
)


def _swap(limit: int) -> None:
    for name, table, condition in CHECKS:
        op.drop_constraint(op.f(name), table, type_="check")
        op.create_check_constraint(op.f(name), table, condition.format(limit=limit))


def upgrade() -> None:
    _swap(NEW_MAX)


def downgrade() -> None:
    # A caption past the old limit can't stay under the old check: it is cut to fit.
    op.execute(f"UPDATE scheduled_posts SET caption = left(caption, {OLD_MAX})")
    op.execute(
        "UPDATE scheduled_post_targets SET caption_override = left(caption_override, "
        f"{OLD_MAX}) WHERE caption_override IS NOT NULL"
    )
    _swap(OLD_MAX)
