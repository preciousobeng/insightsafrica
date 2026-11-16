"""Proposed owner-operated retention runner. Default is a read-only count.

Uses psql/libpq PG* environment or PGSERVICE/PGPASSFILE. Never pass credentials
on the command line. No scheduler is installed by this script.
"""

import argparse
import json
import subprocess

COUNT = "SELECT count(*) FROM public.download_events WHERE created_at < transaction_timestamp() - interval '90 days';"


def query(sql, *, readonly=False):
    prefix = "BEGIN READ ONLY;" if readonly else "BEGIN;"
    result = subprocess.run(
        ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1"],
        input=prefix
        + "SET LOCAL statement_timeout='60s'; SET LOCAL lock_timeout='5s';"
        + sql
        + "COMMIT;",
        text=True,
        capture_output=True,
        timeout=70,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Database operation failed; no database details are logged.")
    return int(result.stdout.strip())


def bounded(value):
    number = int(value)
    if not 1 <= number <= 100000:
        raise argparse.ArgumentTypeError("must be 1..100000")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="OWNER REVIEW REQUIRED: aggregate and delete eligible records",
    )
    parser.add_argument("--batch-size", type=bounded, default=10000)
    parser.add_argument("--max-batches", type=bounded, default=10)
    args = parser.parse_args(argv)
    removed = 0
    if args.execute:
        for _ in range(args.max_batches):
            count = query(f"SELECT public.retain_download_events({args.batch_size});")
            removed += count
            if count < args.batch_size:
                break
    remaining = query(COUNT, readonly=True)
    print(
        json.dumps(
            {
                "mode": "execute" if args.execute else "dry-run",
                "deleted": removed,
                "eligible_remaining": remaining,
            }
        )
    )
    return 2 if args.execute and remaining else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.TimeoutExpired):
        raise SystemExit(
            "Retention operation failed; inspect privately with the database administrator."
        )
