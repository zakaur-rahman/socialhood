"""Facebook Pages (GR-29): webhook_events.provider accepts ``facebook``.

The Page webhook (``/webhooks/facebook``) stores its events like Instagram's and WhatsApp's, so
the provider check is re-created with the new value. Facebook accounts are ``social_accounts``
rows with ``platform = 'facebook'``, which that table's check already allows; no other table
changes.

Expand-only: a wider check; nothing is rewritten.

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-25 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_CHECK = "ck_webhook_events_provider"
OLD_PROVIDERS = ("instagram", "whatsapp", "dodo", "clerk")
NEW_PROVIDERS = ("instagram", "whatsapp", "facebook", "dodo", "clerk")


def _provider_condition(values: Sequence[str]) -> str:
    return f"provider IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.drop_constraint(op.f(PROVIDER_CHECK), "webhook_events", type_="check")
    op.create_check_constraint(
        op.f(PROVIDER_CHECK), "webhook_events", _provider_condition(NEW_PROVIDERS)
    )


def downgrade() -> None:
    op.execute("DELETE FROM webhook_events WHERE provider = 'facebook'")
    op.drop_constraint(op.f(PROVIDER_CHECK), "webhook_events", type_="check")
    op.create_check_constraint(
        op.f(PROVIDER_CHECK), "webhook_events", _provider_condition(OLD_PROVIDERS)
    )
