# CHIRPS data cadence

The updater runs Monday at 04:00 in the server's timezone (production: UTC).
The independent freshness check runs Thursday at 04:00. Both use the shared
`scripts/chirps_release.py` HEAD probe and the fetcher's existing CHIRPS URL builder.
404 means unreleased; timeouts and other HTTP errors fail the check. No raster
content is downloaded by the freshness check, and it writes no archive data.

```cron
0 4 * * 1 cd $HOME/insightsafrica && $HOME/insightsafrica/venv/bin/python scripts/update_all_monthly.py >> $HOME/insightsafrica/data/logs/monthly_update.log 2>&1
0 4 * * 4 cd $HOME/insightsafrica && $HOME/insightsafrica/venv/bin/python -B scripts/check_data_freshness.py --notify >> $HOME/insightsafrica/data/logs/data_freshness.log 2>&1
```

Keep existing backup/keepalive entries. Back up crontab before editing.
Install `deploy/insightsafrica-data.logrotate` as
`/etc/logrotate.d/insightsafrica-data`, owned by root, mode 0644. The host's
enabled daily logrotate timer checks these logs: weekly rotation, earlier when
over 10 MiB, eight retained rotations, compression. The active file can exceed
10 MiB between timer checks; this is bounded retention, not a hard byte quota.
`copytruncate` preserves the updater's existing shell append redirection; a
small copy/truncate race is inherent in this rotation method.

## Freshness policy

Ground truth is the newest filename in `data/archive/<country>/stats/`.
Only released months newer than that month count toward lag. The default
`--threshold 1` allows one released month of lag and fails on two or more.
Use `--threshold 0` if every missed release should alert. Missing archives also
fail. This checks newest-month freshness, not completeness of every older month.
Discovery looks back at most 24 months; no release found is an error.

Exit codes: 0 within threshold, 1 stale/missing data, 2 availability or other
check error. `--notify` sends failures through the updater's existing
`~/.config/insightsafrica/smtp.env` channel. It does not send when current.
Delivery failure is reported explicitly and does not turn a failed check green.
Plain checks without `--notify` do not send mail.

## Update log

Each invocation emits UTC `RUN START` and `RUN END` lines containing mode,
outcome, exit status, error count, and elapsed seconds. Dry runs report
`DRY_RUN_OK`, never claim a successful data refresh, and do not send email.
An uncatchable termination can leave a start without an end, which indicates an
incomplete run. The updater still uses its existing two data-processing paths.

Validate formatting with two consecutive `--dry-run` invocations. Do not
re-fetch data merely to test logging. Tests mock the availability and SMTP
services; an actual successful freshness check does not prove email delivery.
