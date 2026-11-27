"""The WhatsApp catalogue by scheduled feed (C-215): ``catalogue_connections.feed_token`` and
``feed_fetched_at``.

Meta's WhatsApp sign-up never gives an app access to a catalogue, so pushing items with the
Catalog Batch API can't work. Instead Meta fetches the products from a secret link Amplychat
publishes (a scheduled data feed in Commerce Manager). Expand-only: two nullable columns and a
unique constraint on the token; the push sync's columns stay, unused.

Revision ID: 0068
Revises: 0067
Create Date: 2026-11-28 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0068"
down_revision: str | None = "0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("catalogue_connections", sa.Column("feed_token", sa.Text(), nullable=True))
    op.add_column(
        "catalogue_connections",
        sa.Column("feed_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_catalogue_connections_feed_token", "catalogue_connections", ["feed_token"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_catalogue_connections_feed_token", "catalogue_connections")
    op.drop_column("catalogue_connections", "feed_fetched_at")
    op.drop_column("catalogue_connections", "feed_token")
