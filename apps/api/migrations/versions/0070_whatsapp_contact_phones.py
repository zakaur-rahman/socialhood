"""WhatsApp contacts get their phone number (C-220).

A WhatsApp customer's id (``contacts.platform_user_id``) is their phone number in E.164 digits,
but ``contacts.phone`` stayed empty until a member typed it, so the contact panel showed no
phone. New WhatsApp contacts now get it on creation (repositories/ingest.whatsapp_phone); this
fills it for the existing ones that have none. Data only, no schema change; a phone someone
already entered is left as it is.

Revision ID: 0070
Revises: 0069
Create Date: 2026-11-28 20:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0070"
down_revision: str | None = "0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE contacts AS c SET phone = '+' || c.platform_user_id, phone_source = 'whatsapp',"
        " phone_verified = true FROM social_accounts AS a"
        " WHERE a.id = c.social_account_id AND a.platform = 'whatsapp' AND c.phone IS NULL"
        " AND c.platform_user_id ~ '^[1-9][0-9]{7,14}$'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE contacts SET phone = NULL, phone_source = NULL, phone_verified = false"
        " WHERE phone_source = 'whatsapp'"
    )
