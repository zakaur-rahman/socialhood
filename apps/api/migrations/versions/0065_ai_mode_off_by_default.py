"""AI replies are off until the business turns them on (C-204).

- social_accounts.ai_mode: the default for a newly connected account is 'off' instead of
  'suggest'. Existing accounts keep their mode; sandbox accounts set 'suggest' themselves.

Revision ID: 0065
Revises: 0064
Create Date: 2026-11-25 10:00:00.000000+00:00
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
    op.alter_column("social_accounts", "ai_mode", server_default=sa.text("'off'"))


def downgrade() -> None:
    op.alter_column("social_accounts", "ai_mode", server_default=sa.text("'suggest'"))
