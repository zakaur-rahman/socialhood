"""Team-saved contact names (C-135): who chose a contact's name, and the platform's own name.

- contacts.name_source: ``platform`` (default) or ``team``; a team name is never replaced by the
  profile name a platform sends later;
- contacts.platform_name: the latest profile name the platform sent.

Expand-only: new columns with a default, no rows change.

Revision ID: 0053
Revises: 0052
Create Date: 2026-10-25 16:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0053"
down_revision: str | None = "0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column("name_source", sa.Text(), server_default=sa.text("'platform'"), nullable=False),
    )
    op.add_column("contacts", sa.Column("platform_name", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_contacts_name_source"), "contacts", "name_source IN ('platform', 'team')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_contacts_name_source"), "contacts", type_="check")
    op.drop_column("contacts", "platform_name")
    op.drop_column("contacts", "name_source")
