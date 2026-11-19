"""No automatic replies for one contact (GR-44).

- contacts.auto_replies_off: when true, automations, the away message, AI Auto, sequences and
  the follow nudge send nothing to this contact. People still reply.

Expand-only: a column with a default.

Revision ID: 0062
Revises: 0061
Create Date: 2026-11-19 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column(
            "auto_replies_off", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("contacts", "auto_replies_off")
