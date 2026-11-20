"""Label automated messages by default (P-1).

- workspaces.automation_disclosure: new workspaces start with "Sent by an automated assistant",
  set where they are created (repositories/workspaces.new_workspace_rows), so there is no column
  default to change. Existing workspaces keep their value: those using Auto without a line are
  prompted in Settings → AI rules instead of being switched on silently.

No schema change; this revision marks the change in the chain.

Revision ID: 0064
Revises: 0063
Create Date: 2026-11-21 10:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0064"
down_revision: str | None = "0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
