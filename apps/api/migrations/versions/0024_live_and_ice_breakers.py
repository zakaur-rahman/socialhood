"""Live comments trigger and ice breakers (GR-10, GR-11).

- automations.comment_surface: where a comment trigger listens: ``posts`` (today's behaviour),
  ``live`` (the account's Live broadcasts) or ``both``. Live comments ignore post_scope.
- automations.trigger accepts ``ice_breaker`` (the check is re-created).
- ice_breakers: an Instagram account's conversation starters (up to 4, by position), each mapped
  to an automation or to the AI, with how the last sync to Instagram went.

Expand-only: a column with a default and a check, a wider check and a new table.

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-24 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRIGGER_CHECK = "ck_automations_trigger"
OLD_TRIGGERS = (
    "dm_keyword",
    "comment_keyword",
    "comment_any",
    "story_reply",
    "story_mention",
    "entry_link",
    "ad_click",
)
NEW_TRIGGERS = (*OLD_TRIGGERS, "ice_breaker")


def _trigger_condition(values: Sequence[str]) -> str:
    listed = ", ".join(f"'{v}'" for v in values)
    return f"trigger IS NULL OR trigger IN ({listed})"


def upgrade() -> None:
    op.add_column(
        "automations",
        sa.Column("comment_surface", sa.Text(), server_default=sa.text("'posts'"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_automations_comment_surface"),
        "automations",
        "comment_surface IN ('posts', 'live', 'both')",
    )

    op.drop_constraint(op.f(TRIGGER_CHECK), "automations", type_="check")
    op.create_check_constraint(op.f(TRIGGER_CHECK), "automations", _trigger_condition(NEW_TRIGGERS))

    op.create_table(
        "ice_breakers",
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("automation_id", sa.Uuid(), nullable=True),
        sa.Column("answer_with_ai", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_error", sa.Text(), nullable=True),
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
            name=op.f("fk_ice_breakers_social_account_id_social_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automations.id"],
            name=op.f("fk_ice_breakers_automation_id_automations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_ice_breakers_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ice_breakers")),
        sa.UniqueConstraint(
            "social_account_id", "position", name=op.f("uq_ice_breakers_social_account_id_position")
        ),
        sa.CheckConstraint("position BETWEEN 0 AND 3", name=op.f("ck_ice_breakers_position")),
        sa.CheckConstraint(
            "char_length(question) BETWEEN 1 AND 80", name=op.f("ck_ice_breakers_question_length")
        ),
        sa.CheckConstraint(
            "automation_id IS NULL OR NOT answer_with_ai", name=op.f("ck_ice_breakers_one_target")
        ),
    )
    op.create_index(op.f("ix_ice_breakers_workspace_id"), "ice_breakers", ["workspace_id"])
    op.create_index("ix_ice_breakers_automation_id", "ice_breakers", ["automation_id"])


def downgrade() -> None:
    op.drop_table("ice_breakers")
    # Automations on the new trigger can't stay under the old check: they are made drafts without
    # a trigger first.
    op.execute(
        "UPDATE automations SET trigger = NULL, status = 'draft' WHERE trigger = 'ice_breaker'"
    )
    op.drop_constraint(op.f(TRIGGER_CHECK), "automations", type_="check")
    op.create_check_constraint(op.f(TRIGGER_CHECK), "automations", _trigger_condition(OLD_TRIGGERS))

    # A Live-only automation would start answering posts once the column is gone: draft it.
    op.execute(
        "UPDATE automations SET status = 'draft'"
        " WHERE comment_surface = 'live' AND status <> 'draft'"
    )
    op.drop_constraint(op.f("ck_automations_comment_surface"), "automations", type_="check")
    op.drop_column("automations", "comment_surface")
