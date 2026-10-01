"""C-067: the account purge's tables come from the schema, so a new account-scoped table is
purged without a change there; these fail when a table could hold an account's rows without the
purge finding them, or would stop the account row from being deleted."""

from __future__ import annotations

from sqlalchemy import Table

from socialhood.db.base import Base
from socialhood.jobs.recovery import Recovery, recovery_for
from socialhood.repositories.account_deletion import ACCOUNTS, account_tables, owner_links
from socialhood.repositories.workspace_deletion import tenant_tables

# Columns holding a platform's account id as text, which no foreign key can cover: the account's
# own, and stored webhook payloads (the purge deletes those by it, repositories/account_deletion
# .delete_webhook_events).
PLATFORM_ID_COLUMNS = {"social_accounts.platform_account_id", "webhook_events.platform_account_id"}

# Today's account tables (a snapshot for the report; the purge doesn't read it).
EXPECTED = {
    "account_daily_metrics",
    "ai_decisions",
    "automation_keywords",
    "automation_posts",
    "automation_runs",
    "automations",
    "comment_analyses",
    "comments",
    "contacts",
    "conversations",
    "media_items",
    "message_analyses",
    "messages",
    "post_metric_snapshots",
    "posting_slots",
    "reply_suggestions",
    "scheduled_messages",
    "scheduled_post_targets",
}


def names(tables: list[Table]) -> set[str]:
    return {table.name for table in tables}


def test_every_table_pointing_at_an_account_is_purged() -> None:
    purged = names(account_tables())
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            if fk.column.table is ACCOUNTS and table is not ACCOUNTS:
                assert table.name in purged, f"{table.name}.{fk.parent.name}"


def test_every_account_column_is_a_foreign_key_to_the_account() -> None:
    """A column naming an account with no foreign key would escape the purge: give it one
    (ON DELETE CASCADE for the account's own rows), or delete it by hand in the purge and list it
    in PLATFORM_ID_COLUMNS."""
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if not column.name.endswith("account_id"):
                continue
            named = f"{table.name}.{column.name}"
            if named in PLATFORM_ID_COLUMNS:
                continue
            assert any(fk.column.table is ACCOUNTS for fk in column.foreign_keys), named


def test_nothing_blocks_deleting_an_account_or_its_rows() -> None:
    """Every foreign key into the account or its rows cascades (the row is the account's) or is
    set null (a reference, e.g. a comment's contact): a restrictive one would stop the purge."""
    doomed = names(account_tables()) | {ACCOUNTS.name}
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            if fk.column.table.name in doomed:
                rule = (fk.ondelete or "NO ACTION").upper()
                assert rule in {"CASCADE", "SET NULL"}, f"{table.name}.{fk.parent.name}: {rule}"


def test_account_tables_are_tenant_tables_with_an_owner() -> None:
    tenant = names(list(tenant_tables()))
    for table in account_tables():
        assert table.name in tenant, table.name
        assert owner_links(table), table.name


def test_children_are_purged_before_their_parents() -> None:
    tables = account_tables()
    position = {table.name: i for i, table in enumerate(tables)}
    for table in tables:
        for fk in table.foreign_keys:
            parent = fk.column.table.name
            if parent in position and parent != table.name and not fk.use_alter:
                assert position[table.name] < position[parent], f"{table.name} -> {parent}"


def test_workspace_level_data_is_never_an_account_table() -> None:
    purged = names(account_tables())
    kept = {
        "workspaces",
        "workspace_members",
        "subscriptions",
        "usage_counters",
        "payments",
        "ai_settings",
        "knowledge_sources",
        "knowledge_chunks",
        "knowledge_gaps",
        "media_assets",
        "scheduled_posts",
        "scheduled_post_assets",
        "hashtag_groups",
        "social_accounts",
    }
    assert purged.isdisjoint(kept), purged & kept


def test_todays_tables() -> None:
    assert names(account_tables()) == EXPECTED


def test_the_purge_is_retried_after_a_stalled_worker() -> None:
    assert recovery_for("purge_account_data") is Recovery.RETRY
