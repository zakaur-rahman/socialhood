"""Reading a delivery address (C-218): ai_usage_events.feature takes address_read, the AI reading
a customer's reply into an order's address fields (1 credit, billing/plans.CREDIT_COSTS).
Expand-only: a wider check.

Revision ID: 0069
Revises: 0068
Create Date: 2026-11-28 18:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0069"
down_revision: str | None = "0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ai_usage_events.feature before this revision (0016).
FEATURES = (
    "'message_analysis', 'reply_suggestion', 'auto_reply', 'conversation_summary', "
    "'comment_analysis', 'post_summary', 'caption_generation', 'knowledge_test', "
    "'automation_ai_reply', 'agent_turn', 'reply_polish'"
)
CONSTRAINT = "ck_ai_usage_events_feature"


def upgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT), "ai_usage_events", type_="check")
    op.create_check_constraint(
        op.f(CONSTRAINT), "ai_usage_events", f"feature IN ({FEATURES}, 'address_read')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM ai_usage_events WHERE feature = 'address_read'")
    op.drop_constraint(op.f(CONSTRAINT), "ai_usage_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "ai_usage_events", f"feature IN ({FEATURES})")
