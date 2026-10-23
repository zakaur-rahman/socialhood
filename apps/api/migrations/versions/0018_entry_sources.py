"""Entry sources, Live comments and postback payloads (GR-01).

- conversations.entry_source (organic, link, ad, ice_breaker, other), entry_ref, entry_ad_id,
  entry_at: how the conversation began; null for conversations from before GR-01.
  conversations.last_referral: the latest entry link or ad seen in it.
- contacts.last_referral: the latest referral, applied to the conversation it starts;
  contacts.first_entry_source: how the contact first arrived.
- comments.is_live: a comment on a live broadcast.
- messages.postback_payload: the payload of a tapped ice breaker or button.

Expand-only: new nullable columns and one with a default; nothing is backfilled.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-22 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENTRY_CHECK = "ck_conversations_entry_source"
ENTRY_SOURCES = ("organic", "link", "ad", "ice_breaker", "other")


def upgrade() -> None:
    op.add_column("conversations", sa.Column("entry_source", sa.Text(), nullable=True))
    op.add_column("conversations", sa.Column("entry_ref", sa.Text(), nullable=True))
    op.add_column("conversations", sa.Column("entry_ad_id", sa.Text(), nullable=True))
    op.add_column("conversations", sa.Column("entry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("last_referral", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    values = ", ".join(f"'{v}'" for v in ENTRY_SOURCES)
    op.create_check_constraint(
        op.f(ENTRY_CHECK),
        "conversations",
        f"entry_source IS NULL OR entry_source IN ({values})",
    )
    op.add_column(
        "contacts",
        sa.Column("last_referral", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("contacts", sa.Column("first_entry_source", sa.Text(), nullable=True))
    op.add_column(
        "comments",
        sa.Column("is_live", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("messages", sa.Column("postback_payload", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "postback_payload")
    op.drop_column("comments", "is_live")
    op.drop_column("contacts", "first_entry_source")
    op.drop_column("contacts", "last_referral")
    op.drop_constraint(op.f(ENTRY_CHECK), "conversations", type_="check")
    op.drop_column("conversations", "last_referral")
    op.drop_column("conversations", "entry_at")
    op.drop_column("conversations", "entry_ad_id")
    op.drop_column("conversations", "entry_ref")
    op.drop_column("conversations", "entry_source")
