"""Website crawl into knowledge (GR-35): site sources, their pages and their crawl state.

- knowledge_sources.type accepts ``site`` (a whole website) and ``page`` (one crawled page, a
  source of its own); the check is re-created;
- knowledge_sources.parent_source_id: a page's site (ON DELETE CASCADE, so deleting a site
  removes its pages and their chunks);
- site_crawls: one row per site source (re-crawl setting, excluded paths, crawl state);
- site_pages: one row per address found (status, hash, ETag and Last-Modified for change
  detection), unique per site and address.

Expand-only: a nullable column, a wider check and two new tables; nothing is rewritten.

Revision ID: 0031
Revises: 0027
Create Date: 2026-10-24 18:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPE_CHECK = "ck_knowledge_sources_type"
OLD_TYPES = ("faq", "text", "url", "file")
NEW_TYPES = (*OLD_TYPES, "site", "page")
CRAWL_STATUSES = ("idle", "queued", "running", "done", "failed")
PAGE_STATUSES = ("queued", "done", "failed", "skipped", "gone", "excluded", "removed")


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _common_columns() -> list[sa.Column]:
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


def upgrade() -> None:
    op.drop_constraint(op.f(TYPE_CHECK), "knowledge_sources", type_="check")
    op.create_check_constraint(op.f(TYPE_CHECK), "knowledge_sources", _in("type", NEW_TYPES))
    op.add_column("knowledge_sources", sa.Column("parent_source_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_knowledge_sources_parent_source_id_knowledge_sources"),
        "knowledge_sources",
        "knowledge_sources",
        ["parent_source_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_knowledge_sources_parent_source_id"), "knowledge_sources", ["parent_source_id"]
    )

    op.create_table(
        "site_crawls",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("recrawl", sa.Text(), server_default=sa.text("'weekly'"), nullable=False),
        sa.Column(
            "excluded_paths",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'idle'"), nullable=False),
        sa.Column("seeded", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("truncated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("page_cap", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_crawl_at", sa.DateTime(timezone=True), nullable=True),
        *_common_columns(),
        sa.CheckConstraint(_in("status", CRAWL_STATUSES), name=op.f("ck_site_crawls_status")),
        sa.CheckConstraint("recrawl IN ('weekly', 'off')", name=op.f("ck_site_crawls_recrawl")),
        sa.CheckConstraint(
            "cardinality(excluded_paths) <= 50", name=op.f("ck_site_crawls_excluded_paths_count")
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["knowledge_sources.id"],
            name=op.f("fk_site_crawls_source_id_knowledge_sources"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_site_crawls_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_crawls")),
        sa.UniqueConstraint("source_id", name=op.f("uq_site_crawls_source_id")),
    )
    op.create_index(op.f("ix_site_crawls_workspace_id"), "site_crawls", ["workspace_id"])
    op.create_index("ix_site_crawls_due", "site_crawls", ["next_crawl_at"])

    op.create_table(
        "site_pages",
        sa.Column("site_source_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("depth", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        *_common_columns(),
        sa.CheckConstraint(_in("status", PAGE_STATUSES), name=op.f("ck_site_pages_status")),
        sa.CheckConstraint("char_length(url) <= 1000", name=op.f("ck_site_pages_url_length")),
        sa.ForeignKeyConstraint(
            ["site_source_id"],
            ["knowledge_sources.id"],
            name=op.f("fk_site_pages_site_source_id_knowledge_sources"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["knowledge_sources.id"],
            name=op.f("fk_site_pages_source_id_knowledge_sources"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_site_pages_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_pages")),
        sa.UniqueConstraint("site_source_id", "url", name=op.f("uq_site_pages_site_source_id_url")),
    )
    op.create_index(op.f("ix_site_pages_workspace_id"), "site_pages", ["workspace_id"])
    op.create_index(
        "ix_site_pages_queue", "site_pages", ["site_source_id", "status", "depth", "ordinal"]
    )
    op.create_index("ix_site_pages_source", "site_pages", ["source_id"])


def downgrade() -> None:
    op.drop_table("site_pages")
    op.drop_table("site_crawls")
    # Sites and their pages can't stay under the old check: they are deleted first.
    op.execute("DELETE FROM knowledge_sources WHERE type IN ('site', 'page')")
    op.drop_index(op.f("ix_knowledge_sources_parent_source_id"), table_name="knowledge_sources")
    op.drop_constraint(
        op.f("fk_knowledge_sources_parent_source_id_knowledge_sources"),
        "knowledge_sources",
        type_="foreignkey",
    )
    op.drop_column("knowledge_sources", "parent_source_id")
    op.drop_constraint(op.f(TYPE_CHECK), "knowledge_sources", type_="check")
    op.create_check_constraint(op.f(TYPE_CHECK), "knowledge_sources", _in("type", OLD_TYPES))
