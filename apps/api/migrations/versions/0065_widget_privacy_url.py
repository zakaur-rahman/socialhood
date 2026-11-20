"""The website chat's privacy page (P-2).

- widget_settings.privacy_url: the business's privacy page, linked under the chat composer; NULL
  links Amplychat's own policy. http or https only, at most 2000 characters.

Expand-only: a nullable column.

Revision ID: 0065
Revises: 0064
Create Date: 2026-11-21 10:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0065"
down_revision: str | None = "0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("widget_settings", sa.Column("privacy_url", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_widget_settings_privacy_url"),
        "widget_settings",
        "privacy_url ~ '^https?://' AND char_length(privacy_url) <= 2000",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_widget_settings_privacy_url"), "widget_settings", type_="check")
    op.drop_column("widget_settings", "privacy_url")
