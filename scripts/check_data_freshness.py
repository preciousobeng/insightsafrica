"""Compare archive stats with released CHIRPS months; never download/write data."""
import argparse
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

if __package__:
    from . import chirps_release as release
    from . import update_all_monthly as updater
else:
    import chirps_release as release
    import update_all_monthly as updater


def check(root: Path, threshold: int = 1, today=None, probe=None):
    if threshold < 0:
        raise ValueError("threshold must be non-negative")
    today = today or date.today()
    cached_probe = lru_cache(maxsize=None)(probe or release.is_month_released)
    ceiling = release.previous_month(today.year, today.month)
    latest_release = release.newest_release(ceiling, cached_probe)
    lines = [f"CHIRPS newest release: {latest_release[0]}-{latest_release[1]:02d}; "
             f"allowed lag: {threshold} released month(s)"]
    failures = []
    for country in updater.COUNTRIES:
        latest = updater.latest_layer_month(root / "data/archive" / country / "stats", country)
        if latest is None:
            line = f"FAIL {country}: no processed monthly stats found"
            failures.append(line)
        elif latest > ceiling:
            line = f"FAIL {country}: processed month {latest[0]}-{latest[1]:02d} is in the future"
            failures.append(line)
        else:
            lag = sum(cached_probe(*month) for month in updater.next_months(latest, latest_release))
            failed = lag > threshold
            line = (f"{'FAIL' if failed else 'OK'} {country}: processed={latest[0]}-{latest[1]:02d}, "
                    f"behind={lag} released month(s)")
            if failed:
                failures.append(line)
        lines.append(line)
    return lines, failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--threshold', type=int, default=1,
                        help='Maximum allowed released-month lag (default 1; use 0 for any lag)')
    parser.add_argument('--data-root', type=Path, default=updater.BASE_DIR)
    parser.add_argument('--notify', action='store_true', help='Email failures using existing SMTP setup')
    args = parser.parse_args(argv)
    if args.threshold < 0:
        parser.error('--threshold must be non-negative')
    print(f"=== FRESHNESS {datetime.now(timezone.utc).isoformat()} ===", flush=True)
    try:
        lines, failures = check(args.data_root, args.threshold)
        code = 1 if failures else 0
    except Exception as exc:
        lines = failures = [f"FAIL freshness could not be determined: {type(exc).__name__}: {exc}"]
        code = 2
    for line in lines:
        print(line, flush=True)
    print(f"SUMMARY {'FAILED' if code else 'CURRENT'} exit={code}", flush=True)
    if failures and args.notify:
        updater.notify_failure(failures, lines, label='data freshness check')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
