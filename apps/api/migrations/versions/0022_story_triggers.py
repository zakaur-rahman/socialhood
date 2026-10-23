"""Story triggers (GR-06, GR-07): the story reply and story mention triggers, the stories a story
reply automation is scoped to, and the mention records.

- automations.trigger accepts ``story_reply`` and ``story_mention`` (the check is re-created);
- automations.story_ids: the platform ids of the chosen stories (empty: any story) and
  automations.story_heart: also send the heart sticker to a story reply;
- story_mentions: one row per mention (who, when, the story link and when it expires). The link is
  Instagram's CDN address, never copied; it is cleared once it expires.

Expand-only: two columns with defaults, a wider check and a new table; nothing is rewritten.

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-24 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRIGGER_CHECK = "ck_automations_trigger"
OLD_TRIGGERS = ("dm_keyword", "comment_keyword", "comment_any")
NEW_TRIGGERS = (*OLD_TRIGGERS, "story_reply", "story_mention")


def _trigger_condition(values: Sequence[str]) -> str:
    listed = ", ".join(f"'{v}'" for v in values)
    return f"trigger IS NULL OR trigger IN ({listed})"


def upgrade() -> None:
    op.drop_constraint(op.f(TRIGGER_CHECK), "automations", type_="check")
    op.create_check_constraint(op.f(TRIGGER_CHECK), "automations", _trigger_condition(NEW_TRIGGERS))
    op.add_column(
        "automations",
        sa.Column(
            "story_ids",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.add_column(
        "automations",
        sa.Column("story_heart", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_automations_story_ids"), "automations", "cardinality(story_ids) <= 20"
    )

    op.create_table(
        "story_mentions",
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("mentioned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("media_url", sa.Text(), nullable=True),
        sa.Column("media_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["social_account_id"],
            ["social_accounts.id"],
            name=op.f("fk_story_mentions_social_account_id_social_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            name=op.f("fk_story_mentions_contact_id_contacts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_story_mentions_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_story_mentions_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_story_mentions")),
        sa.UniqueConstraint("message_id", name=op.f("uq_story_mentions_message_id")),
    )
    op.create_index(op.f("ix_story_mentions_workspace_id"), "story_mentions", ["workspace_id"])
    op.create_index(
        "ix_story_mentions_listing",
        "story_mentions",
        ["workspace_id", sa.text("mentioned_at DESC"), "id"],
    )
    op.create_index(
        "ix_story_mentions_account",
        "story_mentions",
        ["social_account_id", sa.text("mentioned_at DESC")],
    )
    op.create_index("ix_story_mentions_contact_id", "story_mentions", ["contact_id"])
    op.create_index(
        "ix_story_mentions_expiring",
        "story_mentions",
        ["media_expires_at"],
        postgresql_where=sa.text("media_url IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("story_mentions")
    op.drop_constraint(op.f("ck_automations_story_ids"), "automations", type_="check")
    op.drop_column("automations", "story_heart")
    op.drop_column("automations", "story_ids")
    # Automations on the new triggers can't stay under the old check: they are made drafts
    # without a trigger first.
    op.execute(
        "UPDATE automations SET trigger = NULL, status = 'draft'"
        " WHERE trigger IN ('story_reply', 'story_mention')"
    )
    op.drop_constraint(op.f(TRIGGER_CHECK), "automations", type_="check")
    op.create_check_constraint(op.f(TRIGGER_CHECK), "automations", _trigger_condition(OLD_TRIGGERS))
