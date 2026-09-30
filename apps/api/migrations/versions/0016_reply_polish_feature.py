"""AI Polish (C-063): ai_usage_events.feature takes reply_polish, the composer's rewrite of a
member's draft (1 credit, billing/plans.CREDIT_COSTS).

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-01 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ai_usage_events.feature before this revision (0012).
FEATURES = (
    "'message_analysis', 'reply_suggestion', 'auto_reply', 'conversation_summary', "
    "'comment_analysis', 'post_summary', 'caption_generation', 'knowledge_test', "
    "'automation_ai_reply', 'agent_turn'"
)
CONSTRAINT = "ck_ai_usage_events_feature"


def upgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT), "ai_usage_events", type_="check")
    op.create_check_constraint(
        op.f(CONSTRAINT), "ai_usage_events", f"feature IN ({FEATURES}, 'reply_polish')"
    )


def downgrade() -> None:
    # The events are history, but the old constraint can't hold them; their credits stay counted
    # in the period's counter.
    op.execute("DELETE FROM ai_usage_events WHERE feature = 'reply_polish'")
    op.drop_constraint(op.f(CONSTRAINT), "ai_usage_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "ai_usage_events", f"feature IN ({FEATURES})")
