"""Proposed owner-operated Supabase REST retention runner; dry-run by default.

Reuses SUPABASE_URL and SUPABASE_SERVICE_KEY (or the API's existing
SUPABASE_SERVICE_ROLE_KEY alias). Never logs secrets or raw download records.
No scheduler is installed and no database password is required.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from urllib.parse import urlsplit

import httpx


class RetentionClient:
    def __init__(self, url, key, transport=None):
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or parts.path not in ("", "/")
            or not key
        ):
            raise RuntimeError("Set a valid HTTPS SUPABASE_URL and service key.")
        self.client = httpx.Client(
            base_url=url.rstrip("/") + "/rest/v1/",
            headers={"apikey": key, "Authorization": "Bearer " + key},
            timeout=70,
            follow_redirects=False,
            transport=transport,
        )

    @classmethod
    def from_env(cls):
        return cls(
            os.getenv("SUPABASE_URL", ""),
            os.getenv("SUPABASE_SERVICE_KEY")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        )

    def request(self, method, path, **kwargs):
        try:
            response = self.client.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPError:
            # A timed-out POST may have committed. Never automatically retry it.
            raise RuntimeError(
                "Supabase request failed; batch outcome may be unknown. No automatic retry."
            ) from None

    def count_eligible(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        response = self.request(
            "HEAD",
            "download_events",
            params={"select": "id", "created_at": "lt." + cutoff},
            headers={"Prefer": "count=exact", "Range": "0-0"},
        )
        total = response.headers.get("Content-Range", "").rsplit("/", 1)[-1]
        if not total.isdecimal():
            raise RuntimeError("Supabase did not return an exact eligible count.")
        return int(total)

    def retain(self, batch_size):
        response = self.request(
            "POST", "rpc/retain_download_events", json={"batch_size": batch_size}
        )
        try:
            count = response.json()
        except ValueError:
            raise RuntimeError(
                "Invalid retention result; batch outcome may be unknown."
            ) from None
        if type(count) is not int or not 0 <= count <= batch_size:
            raise RuntimeError("Invalid retention count; batch outcome may be unknown.")
        return count


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
    client = RetentionClient.from_env()
    removed = 0
    if args.execute:
        for _ in range(args.max_batches):
            count = client.retain(args.batch_size)
            removed += count
            if count < args.batch_size:
                break
    remaining = client.count_eligible()
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
    except RuntimeError:
        raise SystemExit(
            "Retention operation failed; inspect privately with the database administrator."
        )
