"""Entry links and ad clicks (GR-08, GR-09): the entry_link and ad_click triggers, the ads an ad
click automation is scoped to, and the entry links table.

- automations.trigger accepts ``entry_link`` and ``ad_click`` (the check is re-created);
- automations.ad_ids: the ids of the chosen ads, typed by hand (empty: any ad);
- entry_links: one row per link (account, unique code, name, the automation it starts).

Expand-only: a column with a default, a wider check and a new table; nothing is rewritten.

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-24 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRIGGER_CHECK = "ck_automations_trigger"
OLD_TRIGGERS = (
    "dm_keyword",
    "comment_keyword",
    "comment_any",
    "story_reply",
    "story_mention",
)
NEW_TRIGGERS = (*OLD_TRIGGERS, "entry_link", "ad_click")


def _trigger_condition(values: Sequence[str]) -> str:
    listed = ", ".join(f"'{v}'" for v in values)
    return f"trigger IS NULL OR trigger IN ({listed})"


def upgrade() -> None:
    op.drop_constraint(op.f(TRIGGER_CHECK), "automations", type_="check")
    op.create_check_constraint(op.f(TRIGGER_CHECK), "automations", _trigger_condition(NEW_TRIGGERS))
    op.add_column(
        "automations",
        sa.Column(
            "ad_ids",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_automations_ad_ids"), "automations", "cardinality(ad_ids) <= 20"
    )

    op.create_table(
        "entry_links",
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("automation_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
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
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 80", name=op.f("ck_entry_links_name_length")
        ),
        sa.CheckConstraint(
            "code ~ '^[A-Za-z0-9_-]{3,40}$'", name=op.f("ck_entry_links_code_format")
        ),
        sa.ForeignKeyConstraint(
            ["social_account_id"],
            ["social_accounts.id"],
            name=op.f("fk_entry_links_social_account_id_social_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automations.id"],
            name=op.f("fk_entry_links_automation_id_automations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_entry_links_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entry_links")),
        sa.UniqueConstraint(
            "social_account_id", "code", name=op.f("uq_entry_links_social_account_id_code")
        ),
    )
    op.create_index(op.f("ix_entry_links_workspace_id"), "entry_links", ["workspace_id"])
    op.create_index(
        "ix_entry_links_listing",
        "entry_links",
        ["workspace_id", sa.text("created_at DESC"), "id"],
    )
    op.create_index(
        "ix_entry_links_automation_id",
        "entry_links",
        ["automation_id"],
        postgresql_where=sa.text("automation_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("entry_links")
    op.drop_constraint(op.f("ck_automations_ad_ids"), "automations", type_="check")
    op.drop_column("automations", "ad_ids")
    # Automations on the new triggers can't stay under the old check: they are made drafts
    # without a trigger first.
    op.execute(
        "UPDATE automations SET trigger = NULL, status = 'draft'"
        " WHERE trigger IN ('entry_link', 'ad_click')"
    )
    op.drop_constraint(op.f(TRIGGER_CHECK), "automations", type_="check")
    op.create_check_constraint(op.f(TRIGGER_CHECK), "automations", _trigger_condition(OLD_TRIGGERS))
