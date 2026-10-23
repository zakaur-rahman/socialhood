"""Link click tracking (GR-15): tracked links and their clicks, and the per-automation opt-out.

- tracked_links: one row per run, step and link button sent through our redirect, with an opaque
  unique code;
- link_clicks: one row per counted click (previews and bots are never stored);
- automations.track_links: on by default; off sends the raw link.

Expand-only: a column with a default and two new tables; nothing is rewritten.

Revision ID: 0029
Revises: 0024
Create Date: 2026-10-24 18:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column[object]:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _created() -> sa.Column[object]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _updated() -> sa.Column[object]:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        [f"{target}.id"],
        name=op.f(f"fk_{table}_{column}_{target}"),
        ondelete="CASCADE",
    )


def upgrade() -> None:
    op.add_column(
        "automations",
        sa.Column("track_links", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "tracked_links",
        sa.Column("automation_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Text(), nullable=False),
        sa.Column("button_index", sa.SmallInteger(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        _id(),
        _created(),
        _updated(),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "char_length(code) BETWEEN 16 AND 64", name=op.f("ck_tracked_links_code_length")
        ),
        _fk("tracked_links", "automation_id", "automations"),
        _fk("tracked_links", "run_id", "automation_runs"),
        _fk("tracked_links", "contact_id", "contacts"),
        _fk("tracked_links", "workspace_id", "workspaces"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tracked_links")),
        sa.UniqueConstraint("code", name=op.f("uq_tracked_links_code")),
        sa.UniqueConstraint(
            "run_id",
            "step_id",
            "button_index",
            name=op.f("uq_tracked_links_run_id_step_id_button_index"),
        ),
    )
    op.create_index(op.f("ix_tracked_links_workspace_id"), "tracked_links", ["workspace_id"])
    op.create_index("ix_tracked_links_automation_id", "tracked_links", ["automation_id"])

    op.create_table(
        "link_clicks",
        sa.Column("link_id", sa.Uuid(), nullable=False),
        sa.Column("automation_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Text(), nullable=False),
        _id(),
        _created(),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        _fk("link_clicks", "link_id", "tracked_links"),
        _fk("link_clicks", "automation_id", "automations"),
        _fk("link_clicks", "run_id", "automation_runs"),
        _fk("link_clicks", "contact_id", "contacts"),
        _fk("link_clicks", "workspace_id", "workspaces"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_link_clicks")),
    )
    op.create_index(op.f("ix_link_clicks_workspace_id"), "link_clicks", ["workspace_id"])
    op.create_index(
        "ix_link_clicks_automation_id_created_at", "link_clicks", ["automation_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("link_clicks")
    op.drop_table("tracked_links")
    op.drop_column("automations", "track_links")
