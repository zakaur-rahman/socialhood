"""API key hardening (C-167): expiry, an IP allowlist, and revoking the keys of members who left.

- api_keys.expires_at: optional; an expired key is refused (auth/api_key.py, auth/mcp_credentials.py);
- api_keys.expiry_notified_at: when owners and admins were told the key expires within 7 days, so
  the daily job tells them once;
- api_keys.allowed_ips: IPs and CIDRs the key may be used from; empty (the default) means any.

Data: from now on a member's keys are revoked when they leave. Keys made by someone who already
left (their user still exists but is no longer a member of the key's workspace) are revoked here
the same way: ``revoked_at`` set, their REST hooks deleted, one audit row each. Keys whose maker's
account was deleted (``created_by_user_id`` NULL) are kept, as before.

Revision ID: 0056
Revises: 0055
Create Date: 2026-11-01 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEPARTED = """
    revoked_at IS NULL
    AND created_by_user_id IS NOT NULL
    AND NOT EXISTS (
        SELECT 1 FROM workspace_members m
        WHERE m.workspace_id = api_keys.workspace_id AND m.user_id = api_keys.created_by_user_id
    )
"""


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "api_keys", sa.Column("expiry_notified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "api_keys",
        sa.Column(
            "allowed_ips",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_api_keys_allowed_ips"), "api_keys", "cardinality(allowed_ips) <= 20"
    )

    op.execute(
        f"""
        INSERT INTO audit_events
            (workspace_id, actor_user_id, actor_label, action, target_type, target_id, detail)
        SELECT workspace_id, NULL, 'Amplychat', 'api_key.revoked', 'api_key', id::text,
               jsonb_build_object(
                   'name', name, 'prefix', key_prefix,
                   'reason', 'revoked: the member who made it left the workspace'
               )
        FROM api_keys WHERE {DEPARTED}
        """
    )
    op.execute(
        f"""
        DELETE FROM webhook_endpoints
        WHERE api_key_id IN (SELECT id FROM api_keys WHERE {DEPARTED})
        """
    )
    op.execute(f"UPDATE api_keys SET revoked_at = now() WHERE {DEPARTED}")


def downgrade() -> None:
    # The revocations stay: a key that was off doesn't come back on.
    op.drop_constraint(op.f("ck_api_keys_allowed_ips"), "api_keys", type_="check")
    op.drop_column("api_keys", "allowed_ips")
    op.drop_column("api_keys", "expiry_notified_at")
    op.drop_column("api_keys", "expires_at")
