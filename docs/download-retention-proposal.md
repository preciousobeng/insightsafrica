# Owner review required — prepared only

Nothing here is applied or scheduled. The draft 90-day policy remains [CONFIRM]. Do not publish it as operational until the owner approves, backups and recovery are checked, and a database administrator reviews permissions, capacity and scheduling.

The migration creates a RLS-protected aggregate table and invoker function. It does not purge. The function takes at most 100,000 old rows per atomic batch, increments country/product/UTC-month counts and deletes exactly those raw rows. Aggregate records contain no IP, account ID, dates of requested data or other identifiers. Counts remain potentially commercially sensitive and are not public. Existing aggregate counts must be checked before any historical backfill to avoid double counting.

The runner defaults to a read-only eligible count. After separate owner approval, a DBA would apply the migration, configure libpq using PGSERVICE/PGPASSFILE (never command-line secrets), inspect the dry run, and explicitly invoke scripts/retain_download_events.py --execute. Batches default to 10,000 rows with at most ten per invocation; exit 2 means eligible rows remain. A transaction advisory lock prevents concurrent batches; timeouts and lock errors stop the job. Partial completion is safe to resume because only deleted records contribute counts. Confirm raw SELECT/DELETE and UPDATE(id) row-lock privileges for the intended service role; this migration does not broaden raw-log permissions.

No cron or timer is installed. Establish monitoring, failure alerts, backup expiry and a rollback/recovery procedure before scheduling. Deletions cannot be reversed from the aggregate counts. Backups and account/contact retention are separate policy decisions.

Tests create isolated UNIX-socket PostgreSQL 16 and 18 clusters with synthetic records, no configured database credentials, and destroy them afterward. They cover default read-only mode, bounded batching, the exact 90-day boundary, retry/idempotency, rollback on aggregate failure and role permissions.

Implementation references: PostgreSQL [data-modifying CTEs](https://www.postgresql.org/docs/18/queries-with.html), [transaction advisory locks](https://www.postgresql.org/docs/18/functions-admin.html), and [function permissions](https://www.postgresql.org/docs/18/sql-createfunction.html).
