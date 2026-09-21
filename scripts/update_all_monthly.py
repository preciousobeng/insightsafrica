#!/usr/bin/env python3
"""
update_all_monthly.py — idempotent monthly CHIRPS refresh for all countries.

Keeps BOTH data paths current, for every country, up to the latest CHIRPS
release (publication lag varies):

  Path A — recent monthly flood layers (data/processed*/):
      fetch_chirps.py  ->  process_rainfall.py   (map JSON + PNG)
  Path B — anomaly archive (data/archive/<c>/stats/ + anomaly/):
      fetch_chirps_archive.py  ->  precompute_anomalies.py

Idempotent: skips months already present. A month CHIRPS has not released yet
is treated as a benign stop (not a failure). Any other error is collected,
reported, and — if SMTP creds are present — emailed, and the process exits
non-zero so cron surfaces it.

Designed to run unattended (cron) on the prod box where the country boundary
geojson and served data live. Run manually the same way:

    python scripts/update_all_monthly.py
    python scripts/update_all_monthly.py --dry-run   # show what it would do
"""
import argparse
import os
import smtplib
import subprocess
import sys
from datetime import date, datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

if __package__:
    from .chirps_release import newest_release
else:
    from chirps_release import newest_release

BASE_DIR = Path(__file__).parent.parent
SCRIPTS = BASE_DIR / "scripts"
PY = sys.executable

# country -> the processed dir holding its monthly flood layers
COUNTRIES = {
    "ghana":       "processed",
    "nigeria":     "processed_nigeria",
    "ivorycoast":  "processed_ivorycoast",
    "senegal":     "processed_senegal",
    "capeverde":   "processed_capeverde",
    "southafrica": "processed_southafrica",
}

log_lines: list[str] = []
errors: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)
    log_lines.append(msg)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))


_MONTH_RE = None


def latest_layer_month(processed_dir: Path, country: str) -> tuple[int, int] | None:
    import re
    pat = re.compile(rf"chirps-v2\.0\.(\d{{4}})\.(\d{{2}})_{re.escape(country)}\.json$")
    months = []
    for f in processed_dir.glob(f"chirps-v2.0.*_{country}.json"):
        m = pat.match(f.name)
        if m:
            months.append((int(m.group(1)), int(m.group(2))))
    return max(months) if months else None


def next_months(after: tuple[int, int], upto: tuple[int, int]):
    """Yield (year, month) strictly after `after`, up to and including `upto`."""
    y, m = after
    while True:
        m += 1
        if m > 12:
            m = 1
            y += 1
        if (y, m) > upto:
            return
        yield (y, m)


def is_not_released(proc: subprocess.CompletedProcess) -> bool:
    """A month CHIRPS hasn't published yet -> download 404s. Benign."""
    blob = (proc.stdout + proc.stderr).lower()
    return "404" in blob or "not found" in blob


def update_layers(country: str, processed_dir: Path, ceiling: tuple[int, int], dry: bool):
    latest = latest_layer_month(processed_dir, country)
    if latest is None:
        errors.append(f"{country}: no existing monthly layers found — skipping Path A")
        return
    advanced = 0
    for (y, m) in next_months(latest, ceiling):
        if dry:
            log(f"  [dry-run] would fetch+process {country} {y}-{m:02d}")
            continue
        fetch = run([PY, str(SCRIPTS / "fetch_chirps.py"),
                     "--year", str(y), "--month", str(m), "--country", country])
        if fetch.returncode != 0:
            if is_not_released(fetch):
                log(f"  {country}: {y}-{m:02d} not released yet — stopping (ok)")
                break
            errors.append(f"{country} Path A fetch {y}-{m:02d} FAILED:\n{fetch.stderr[-500:]}")
            break
        tif = BASE_DIR / "data" / "raw" / "chirps" / f"chirps-v2.0.{y}.{m:02d}_{country}.tif"
        proc = run([PY, str(SCRIPTS / "process_rainfall.py"),
                    "--input", str(tif), "--country", country])
        if proc.returncode != 0:
            errors.append(f"{country} Path A process {y}-{m:02d} FAILED:\n{proc.stderr[-500:]}")
            break
        advanced += 1
        log(f"  {country}: added monthly layer {y}-{m:02d}")
    if advanced:
        log(f"  {country}: Path A advanced by {advanced} month(s)")


def update_anomaly_archive(start_ym: str, dry: bool):
    if dry:
        log(f"  [dry-run] would fetch_chirps_archive --countries {' '.join(COUNTRIES)} --start {start_ym}")
        log(f"  [dry-run] would precompute_anomalies for each country")
        return
    arch = run([PY, str(SCRIPTS / "fetch_chirps_archive.py"),
                "--countries", *COUNTRIES.keys(), "--start", start_ym])
    if arch.returncode != 0 and not is_not_released(arch):
        errors.append(f"Path B fetch_chirps_archive FAILED:\n{arch.stderr[-500:]}")
    else:
        log("  Path B: archive stats refreshed")
    for country in COUNTRIES:
        pre = run([PY, str(SCRIPTS / "precompute_anomalies.py"), "--country", country])
        if pre.returncode != 0:
            errors.append(f"{country} Path B precompute_anomalies FAILED:\n{pre.stderr[-400:]}")
        else:
            tail = pre.stdout.strip().splitlines()[-1] if pre.stdout.strip() else ""
            log(f"  {country}: anomaly — {tail}")


def notify_failure(failures=None, detail=None, label="monthly data update") -> bool:
    """Reuse the configured SMTP channel; explicitly report unavailable delivery."""
    failures = errors if failures is None else failures
    detail = log_lines if detail is None else detail
    env_path = Path.home() / ".config" / "insightsafrica" / "smtp.env"
    if not env_path.exists():
        print("ALERT NOT SENT: SMTP configuration missing", flush=True)
        return False
    cfg = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    host = cfg.get("SMTP_HOST", "smtp.gmail.com")
    port = cfg.get("SMTP_PORT", "587")
    user = cfg.get("SMTP_USER")
    pw = cfg.get("SMTP_PASS")
    to = cfg.get("MAIL_TO", user)
    if not (user and pw and to):
        print("ALERT NOT SENT: SMTP configuration incomplete", flush=True)
        return False
    body = f"InsightsAfrica {label} reported errors:\n\n" + "\n\n".join(failures)
    body += "\n\n--- full log ---\n" + "\n".join(detail)
    msg = MIMEText(body)
    msg["Subject"] = f"[InsightsAfrica] {label} FAILED ({len(failures)} error(s))"
    msg["From"] = user
    msg["To"] = to
    try:
        with smtplib.SMTP(host, int(port), timeout=20) as s:
            s.starttls()
            s.login(user, pw)
            s.sendmail(user, [to], msg.as_string())
        print("ALERT SENT: configured SMTP recipient", flush=True)
        return True
    except Exception as e:
        print(f"ALERT NOT SENT: {type(e).__name__}", flush=True)
        return False


def update(args) -> int:
    today = date.today()
    # Attempt up to last month; CHIRPS lag means recent ones 404 and stop cleanly.
    ceiling = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    ceiling = newest_release(ceiling)
    # Path B start: re-check the last ~4 months (cheap, idempotent, self-heals gaps)
    sy, sm = ceiling
    for _ in range(3):
        sm -= 1
        if sm < 1:
            sm = 12
            sy -= 1
    start_ym = f"{sy}-{sm:02d}"

    log(f"# InsightsAfrica monthly update {today.isoformat()} "
        f"(ceiling {ceiling[0]}-{ceiling[1]:02d}, archive start {start_ym})"
        f"{' [DRY RUN]' if args.dry_run else ''}")

    log("## Path A — monthly flood layers")
    for country, sub in COUNTRIES.items():
        update_layers(country, BASE_DIR / "data" / sub, ceiling, args.dry_run)

    log("## Path B — anomaly archive")
    update_anomaly_archive(start_ym, args.dry_run)

    if errors:
        log(f"\nFAILED with {len(errors)} error(s):")
        for e in errors:
            log("  - " + e.splitlines()[0])
        if not args.dry_run:
            notify_failure()
        return 1
    log("\nDry-run completed; no data written." if args.dry_run else "\nAll countries current. No errors.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Check release availability and show planned actions; write no data")
    args = ap.parse_args(argv)
    log_lines.clear()
    errors.clear()
    start = datetime.now(timezone.utc)
    mode = "DRY_RUN" if args.dry_run else "UPDATE"
    log(f"=== RUN START {start.isoformat()} mode={mode} ===")
    code = 1
    try:
        code = update(args)
    except Exception as exc:
        errors.append(f"Updater failed: {type(exc).__name__}: {exc}")
        log(errors[-1])
        if not args.dry_run:
            notify_failure()
    finally:
        end = datetime.now(timezone.utc)
        outcome = "FAILED" if code else ("DRY_RUN_OK" if args.dry_run else "SUCCESS")
        log(f"=== RUN END {end.isoformat()} outcome={outcome} exit={code} "
            f"errors={len(errors)} duration_s={(end-start).total_seconds():.1f} ===")
    return code


if __name__ == "__main__":
    sys.exit(main())
