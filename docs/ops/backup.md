# Backup and restore (T9.5, §2.13)

The target (§2.13) is Render Postgres point-in-time recovery with at least 7 days of history, and
a restore rehearsed once before launch.

## Production: Render point-in-time recovery [owner account]

- **What it is:** Render keeps continuous backups (base backups plus WAL) of paid Postgres
  instances, and restores to any moment in the recovery window. The window is 7 days on a Pro (or
  higher) workspace plan and 3 days on Hobby; free databases have none. Check the database's
  **Recovery** tab to confirm it after creating `socialhood-db`.
- **How a restore works:** a restore always creates a **new** database instance at the chosen
  time. The original keeps running untouched. Then you either:
  1. copy what you need out of the restored instance (a table, some rows), or
  2. switch the services to it: change `DATABASE_URL` and `DATABASE_URL_DIRECT` on
     `socialhood-api` and `socialhood-worker` to the restored instance's internal URL (or rename
     databases in `infra/render.yaml` and sync), deploy, then retire the old one.
- **Steps:** Render → `socialhood-db` → Recovery → **Restore** → pick the time (UTC) → name the new
  instance (e.g. `socialhood-db-restore-YYYYMMDD`) → Create. Wait for it to be available, then
  check it (below) before switching anything.
- **Exports:** Render also offers logical exports (`pg_dump` files) from the same tab, kept for 7
  days. Download one monthly and keep it somewhere the business controls, for disasters that take
  the Render workspace with them.
- **What is not backed up:** Valkey holds only non-durable data (streams, rate limits, locks,
  metrics counters), so a lost Key Value instance is simply recreated. The job queue lives in
  Postgres and is restored with the data. Media lives in Cloudinary.

### Checking a restored instance

From the restored instance's Render shell, or `psql` with its external URL (allow your IP first):

```sql
SELECT version_num FROM alembic_version;                  -- matches the running code
SELECT extname, extversion FROM pg_extension;             -- vector, pg_trgm, pgcrypto
SELECT count(*) FROM workspaces;                          -- and a few other tables you know
SELECT max(occurred_at) FROM messages;                    -- close to the restore time
SELECT status, count(*) FROM procrastinate_jobs GROUP BY 1;
```

After switching, `/readyz` must say `ready`, the worker must pick up jobs, and the dashboard's
dispatcher lag shows whether scheduled rows from the gap are going out.

### Rehearsing on Render before launch

Once production exists: restore `socialhood-db` to 10 minutes ago as a new instance, run the checks
above, time it, then delete the restored instance. Record it below. The launch checklist (§6.4)
wants "Point-in-time recovery on; restore rehearsed".

## Local rehearsal script

[`infra/scripts/backup-restore-rehearsal.sh`](../../infra/scripts/backup-restore-rehearsal.sh)
exercises the dump-and-restore path locally and shows the schema restores cleanly, with every
extension:

```sh
infra/scripts/backup-restore-rehearsal.sh          # Linux, macOS, or Windows Git Bash
```

It runs `pg_dump --format=custom` of the dev database `socialhood` inside the Docker Postgres
(read-only on the source), restores into a scratch database `socialhood_restore_check`, compares
the migration version, the extensions and the row count of every table against the source, and
drops the scratch database. It refuses any scratch name that does not end in `_restore_check`.
`--keep` keeps the scratch database for inspection. Tables written while the dump runs (a local
worker's queue tables) are reported as "changed during dump" rather than as failures.

## Results

### Local rehearsal, 30 Sep 2026: passed

| | |
|---|---|
| Source | `socialhood` (local Docker, `pgvector/pgvector:pg18`, pg_dump 18.6), read-only |
| Scratch database | `socialhood_restore_check`, dropped afterwards |
| Dump | custom format, 898,499 bytes, 8 s |
| Restore | `pg_restore --no-owner --exit-on-error`, 12 s, no errors |
| Migration version | source `0014`, restored `0014` |
| Extensions restored | pg_trgm 1.6, pgcrypto 1.4, plpgsql 1.0, vector 0.8.6 |
| Tables | 49, including the job queue's `procrastinate_*` tables |
| Rows | 56,827 in the source; every table's count matched after the restore |
| Changed during the dump | none |
| Result | `RESULT: PASSED` |

Largest tables: `procrastinate_events` 41,998, `procrastinate_jobs` 13,985, `messages` 509,
`webhook_events` 54. The full per-table output is printed by the script.

### Render point-in-time recovery rehearsal

| Date | Restored to | Time to available | Checks | By |
|---|---|---|---|---|
| | | | | |
