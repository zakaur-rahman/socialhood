"""Sequences (GR-24): timed follow-up messages after an entry event.

- sequences: one per follow-up plan (account, entry event, stop rules, status);
- sequence_steps: the messages in order, each with its delay and a text or a WhatsApp template;
- sequence_enrolments: a contact in a sequence (one active per contact and sequence);
- sequence_step_runs: what happened at each step (one row per enrolment and step position, the
  guard that makes a step send once).

Expand-only: four new tables; nothing is rewritten.

Revision ID: 0042
Revises: 0041
Create Date: 2026-10-25 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id_and_times() -> list[sa.Column[object]]:
    return [
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
    ]


def _fk(table: str, column: str, target: str, *, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        [f"{target}.id"],
        name=op.f(f"fk_{table}_{column}_{target}"),
        ondelete=ondelete,
    )


def upgrade() -> None:
    op.create_table(
        "sequences",
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("entry_type", sa.Text(), nullable=False),
        sa.Column("entry_tag_id", sa.Uuid(), nullable=True),
        sa.Column("entry_broadcast_id", sa.Uuid(), nullable=True),
        sa.Column("entry_capture_kind", sa.Text(), nullable=True),
        sa.Column("stop_on_reply", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "stop_tag_ids",
            postgresql.ARRAY(sa.Uuid()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "stop_stages",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("allow_reentry", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_id_and_times(),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'paused')", name=op.f("ck_sequences_status")
        ),
        sa.CheckConstraint(
            "entry_type IN ('captured', 'tagged', 'broadcast_replied')",
            name=op.f("ck_sequences_entry_type"),
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 80", name=op.f("ck_sequences_name_length")
        ),
        sa.CheckConstraint(
            "entry_capture_kind IS NULL OR entry_capture_kind IN ('email', 'phone', 'field')",
            name=op.f("ck_sequences_entry_capture_kind"),
        ),
        sa.CheckConstraint(
            "cardinality(stop_tag_ids) <= 20", name=op.f("ck_sequences_stop_tag_ids_length")
        ),
        sa.CheckConstraint(
            "cardinality(stop_stages) <= 5", name=op.f("ck_sequences_stop_stages_length")
        ),
        _fk("sequences", "social_account_id", "social_accounts", ondelete="CASCADE"),
        _fk("sequences", "entry_tag_id", "tags", ondelete="SET NULL"),
        _fk("sequences", "entry_broadcast_id", "broadcasts", ondelete="SET NULL"),
        _fk("sequences", "created_by_user_id", "users", ondelete="SET NULL"),
        _fk("sequences", "workspace_id", "workspaces", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sequences")),
    )
    op.create_index(op.f("ix_sequences_workspace_id"), "sequences", ["workspace_id"])
    op.create_index(
        "ix_sequences_listing", "sequences", ["workspace_id", sa.text("created_at DESC"), "id"]
    )
    op.create_index(
        "ix_sequences_active",
        "sequences",
        ["social_account_id"],
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "sequence_steps",
        sa.Column("sequence_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("delay_seconds", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("delay_from", sa.Text(), server_default=sa.text("'previous'"), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("template_name", sa.Text(), nullable=True),
        sa.Column("template_language", sa.Text(), nullable=True),
        sa.Column("template_category", sa.Text(), nullable=True),
        sa.Column("template_body", sa.Text(), nullable=True),
        sa.Column(
            "variables",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("respect_hours", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_id_and_times(),
        sa.CheckConstraint(
            "delay_from IN ('entry', 'previous')", name=op.f("ck_sequence_steps_delay_from")
        ),
        sa.CheckConstraint(
            "delay_seconds BETWEEN 0 AND 2592000", name=op.f("ck_sequence_steps_delay_seconds")
        ),
        sa.CheckConstraint(
            "text IS NOT NULL OR template_name IS NOT NULL",
            name=op.f("ck_sequence_steps_has_content"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(variables) = 'array'", name=op.f("ck_sequence_steps_variables_array")
        ),
        _fk("sequence_steps", "sequence_id", "sequences", ondelete="CASCADE"),
        _fk("sequence_steps", "workspace_id", "workspaces", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sequence_steps")),
        sa.UniqueConstraint(
            "sequence_id", "position", name=op.f("uq_sequence_steps_sequence_id_position")
        ),
    )
    op.create_index(op.f("ix_sequence_steps_workspace_id"), "sequence_steps", ["workspace_id"])

    op.create_table(
        "sequence_enrolments",
        sa.Column("sequence_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("current_step", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_step_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_event", sa.Text(), nullable=False),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column("stop_detail", sa.Text(), nullable=True),
        *_id_and_times(),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'stopped')",
            name=op.f("ck_sequence_enrolments_status"),
        ),
        sa.CheckConstraint(
            "stop_reason IS NULL OR stop_reason IN ('reply', 'tag', 'stage', 'member', 'ended')",
            name=op.f("ck_sequence_enrolments_stop_reason"),
        ),
        sa.CheckConstraint("current_step >= 0", name=op.f("ck_sequence_enrolments_current_step")),
        _fk("sequence_enrolments", "sequence_id", "sequences", ondelete="CASCADE"),
        _fk("sequence_enrolments", "contact_id", "contacts", ondelete="CASCADE"),
        _fk("sequence_enrolments", "social_account_id", "social_accounts", ondelete="CASCADE"),
        _fk("sequence_enrolments", "workspace_id", "workspaces", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sequence_enrolments")),
    )
    op.create_index(
        op.f("ix_sequence_enrolments_workspace_id"), "sequence_enrolments", ["workspace_id"]
    )
    op.create_index(
        "uq_sequence_enrolments_active",
        "sequence_enrolments",
        ["sequence_id", "contact_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_sequence_enrolments_due",
        "sequence_enrolments",
        ["next_due_at"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_sequence_enrolments_contact", "sequence_enrolments", ["contact_id"])
    op.create_index(
        "ix_sequence_enrolments_sequence",
        "sequence_enrolments",
        ["sequence_id", "status", sa.text("enrolled_at DESC")],
    )

    op.create_table(
        "sequence_step_runs",
        sa.Column("enrolment_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_id", sa.Uuid(), nullable=False),
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("sent_as", sa.Text(), nullable=True),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
        *_id_and_times(),
        sa.CheckConstraint(
            "status IN ('sent', 'skipped', 'failed')", name=op.f("ck_sequence_step_runs_status")
        ),
        sa.CheckConstraint(
            "sent_as IS NULL OR sent_as IN ('text', 'template')",
            name=op.f("ck_sequence_step_runs_sent_as"),
        ),
        _fk("sequence_step_runs", "enrolment_id", "sequence_enrolments", ondelete="CASCADE"),
        _fk("sequence_step_runs", "sequence_id", "sequences", ondelete="CASCADE"),
        _fk("sequence_step_runs", "social_account_id", "social_accounts", ondelete="CASCADE"),
        _fk("sequence_step_runs", "contact_id", "contacts", ondelete="CASCADE"),
        _fk("sequence_step_runs", "message_id", "messages", ondelete="SET NULL"),
        _fk("sequence_step_runs", "workspace_id", "workspaces", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sequence_step_runs")),
        sa.UniqueConstraint(
            "enrolment_id", "position", name=op.f("uq_sequence_step_runs_enrolment_id_position")
        ),
    )
    op.create_index(
        op.f("ix_sequence_step_runs_workspace_id"), "sequence_step_runs", ["workspace_id"]
    )
    op.create_index(
        "ix_sequence_step_runs_contact",
        "sequence_step_runs",
        ["contact_id", sa.text("ran_at DESC")],
    )
    op.create_index(
        "ix_sequence_step_runs_account_sent", "sequence_step_runs", ["social_account_id", "ran_at"]
    )


def downgrade() -> None:
    op.drop_table("sequence_step_runs")
    op.drop_table("sequence_enrolments")
    op.drop_table("sequence_steps")
    op.drop_table("sequences")
