# Owner review required — prepared only

Nothing here is applied or scheduled. The draft 90-day policy remains [CONFIRM]. Do not publish it as operational until the owner approves, backups and recovery are checked, and a database administrator reviews permissions, capacity and scheduling.

The migration creates a RLS-protected aggregate table and invoker function. It does not purge. The function takes at most 100,000 old rows per atomic batch, increments country/product/UTC-month counts and deletes exactly those raw rows. Aggregate records contain no IP, account ID, dates of requested data or other identifiers. Counts remain potentially commercially sensitive and are not public. Existing aggregate counts must be checked before any historical backfill to avoid double counting.

The runner defaults to a read-only eligible count. After separate owner approval, a DBA would apply the migration, reuse SUPABASE_URL and SUPABASE_SERVICE_KEY (the API configuration name SUPABASE_SERVICE_ROLE_KEY is also accepted; never command-line secrets), inspect the dry run, and explicitly invoke scripts/retain_download_events.py --execute. Batches default to 10,000 rows with at most ten per invocation; exit 2 means eligible rows remain. A transaction advisory lock prevents concurrent batches; REST timeouts and database lock errors stop the job. Partial completion is safe to resume because only deleted records contribute counts. Confirm raw SELECT/DELETE and UPDATE(id) row-lock privileges for the intended service role; this migration does not broaden raw-log permissions.

No cron or timer is installed. Establish monitoring, failure alerts, backup expiry and a rollback/recovery procedure before scheduling. Deletions cannot be reversed from the aggregate counts. Backups and account/contact retention are separate policy decisions.

Tests create isolated UNIX-socket PostgreSQL 16 and 18 clusters with synthetic records, no configured database credentials, and destroy them afterward. They cover default read-only mode, bounded batching, the exact 90-day boundary, retry/idempotency, rollback on aggregate failure and role permissions.

Implementation references: PostgreSQL [data-modifying CTEs](https://www.postgresql.org/docs/18/queries-with.html), [transaction advisory locks](https://www.postgresql.org/docs/18/functions-admin.html), and [function permissions](https://www.postgresql.org/docs/18/sql-createfunction.html).


## REST runner revision
The runner uses Supabase Data API only: HEAD download_events with Prefer: count=exact for the dry-run count, and POST /rest/v1/rpc/retain_download_events with batch_size for execution. No psql executable or direct database password is needed by the runner. PostgreSQL binaries remain development-test dependencies only. Tests intercept all HTTP requests with synthetic credentials.

The dry-run cutoff uses the runner's UTC clock and is advisory; actual deletion uses the database transaction clock and fixed 90-day predicate. Keep the host clock synchronized. HTTP timeout or connection loss after a POST can leave its outcome unknown: the runner stops without retries or printing response bodies. Inspect aggregate totals and remaining records before resuming. Each committed batch is still counted exactly once, but the interrupted runner cannot report a reliable deletion total. Supabase/PostgREST statement timeouts apply; no direct SQL timeout settings are sent by REST.

References: [PostgREST exact HEAD counts](https://docs.postgrest.org/en/stable/references/api/pagination_count.html), [Supabase database functions](https://supabase.com/docs/guides/database/functions).
