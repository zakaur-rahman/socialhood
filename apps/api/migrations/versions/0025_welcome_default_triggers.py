"""Welcome and default replies (GR-12): the ``first_message`` and ``default_reply`` triggers.

- automations.trigger accepts ``first_message`` (a contact's first DM to the account) and
  ``default_reply`` (a DM no automation answered, while AI is off); the check is re-created.

Expand-only: a wider check; no column or row changes.

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-25 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
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
    "ice_breaker",
)
NEW_TRIGGERS = (*OLD_TRIGGERS, "first_message", "default_reply")


def _trigger_condition(values: Sequence[str]) -> str:
    listed = ", ".join(f"'{v}'" for v in values)
    return f"trigger IS NULL OR trigger IN ({listed})"


def upgrade() -> None:
    op.drop_constraint(op.f(TRIGGER_CHECK), "automations", type_="check")
    op.create_check_constraint(op.f(TRIGGER_CHECK), "automations", _trigger_condition(NEW_TRIGGERS))


def downgrade() -> None:
    # Automations on the new triggers can't stay under the old check: they are made drafts
    # without a trigger first.
    op.execute(
        "UPDATE automations SET trigger = NULL, status = 'draft'"
        " WHERE trigger IN ('first_message', 'default_reply')"
    )
    op.drop_constraint(op.f(TRIGGER_CHECK), "automations", type_="check")
    op.create_check_constraint(op.f(TRIGGER_CHECK), "automations", _trigger_condition(OLD_TRIGGERS))
