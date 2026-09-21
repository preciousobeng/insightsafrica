import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import check_data_freshness as freshness
from scripts import chirps_release as release
from scripts import update_all_monthly as updater


def archive(root, months):
    for country, month in months.items():
        folder = root / 'data/archive' / country / 'stats'
        folder.mkdir(parents=True)
        (folder / f'chirps-v2.0.2026.{month:02d}_{country}.json').write_text('{}')


@pytest.mark.parametrize('behind', [[], ['ghana'], ['ghana', 'nigeria']])
def test_current_and_behind_cli(tmp_path, monkeypatch, capsys, behind):
    archive(tmp_path, {c: 6 if c in behind else 8 for c in updater.COUNTRIES})
    monkeypatch.setattr(freshness, 'date', SimpleNamespace(today=lambda: date(2026, 9, 21)))
    monkeypatch.setattr(release, 'is_month_released', lambda y, m: (y, m) <= (2026, 8))
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert freshness.main(['--data-root', str(tmp_path)]) == (1 if behind else 0)
    output = capsys.readouterr().out
    for c in behind:
        assert f'FAIL {c}: processed=2026-06, behind=2 released month(s)' in output
    assert before == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_threshold_and_unreleased_months(tmp_path):
    archive(tmp_path, {c: 7 for c in updater.COUNTRIES})
    calls = []
    def probe(y, m):
        calls.append((y, m))
        return (y, m) <= (2026, 8)
    _, failures = freshness.check(tmp_path, 1, date(2026, 10, 1), probe)
    assert not failures
    assert calls == [(2026, 9), (2026, 8)]  # one global probe per month, no false September lag
    _, failures = freshness.check(tmp_path, 0, date(2026, 10, 1), probe)
    assert len(failures) == 6


def test_missing_archive_fails(tmp_path):
    _, failures = freshness.check(tmp_path, today=date(2026, 9, 21), probe=lambda *args: True)
    assert len(failures) == 6


@pytest.mark.parametrize('status, expected', [(200, True), (404, False)])
def test_probe_uses_head_only(monkeypatch, status, expected):
    response = MagicMock(status_code=status)
    response.__enter__.return_value = response
    head = MagicMock(return_value=response)
    monkeypatch.setattr(release.requests, 'head', head)
    assert release.is_month_released(2026, 8) is expected
    head.assert_called_once_with('https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs/chirps-v2.0.2026.08.tif.gz', allow_redirects=True, timeout=20)


def test_probe_outage_is_not_unreleased(monkeypatch):
    response = MagicMock(status_code=503)
    response.__enter__.return_value = response
    response.raise_for_status.side_effect = requests.HTTPError('503')
    monkeypatch.setattr(release.requests, 'head', lambda *a, **kw: response)
    with pytest.raises(requests.HTTPError):
        release.is_month_released(2026, 8)


def test_monitor_outage_exits_two_and_notifies(tmp_path, monkeypatch, capsys):
    def fail(*a):
        raise requests.Timeout('upstream timeout')
    monkeypatch.setattr(release, 'is_month_released', fail)
    notify = MagicMock(return_value=True)
    monkeypatch.setattr(updater, 'notify_failure', notify)
    assert freshness.main(['--data-root', str(tmp_path), '--notify']) == 2
    notify.assert_called_once()
    assert 'could not be determined' in capsys.readouterr().out


def test_two_runs_have_distinct_delimited_summaries(monkeypatch, capsys):
    monkeypatch.setattr(updater, 'update', lambda args: 0)
    assert updater.main(['--dry-run']) == 0
    assert updater.main(['--dry-run']) == 0
    text = capsys.readouterr().out
    assert text.count('=== RUN START ') == 2
    assert text.count('=== RUN END ') == 2
    assert text.count('outcome=DRY_RUN_OK exit=0') == 2


def test_unexpected_update_failure_has_summary(monkeypatch, capsys):
    def fail(args):
        raise RuntimeError('test failure')
    monkeypatch.setattr(updater, 'update', fail)
    notify = MagicMock()
    monkeypatch.setattr(updater, 'notify_failure', notify)
    assert updater.main([]) == 1
    notify.assert_called_once()
    assert 'outcome=FAILED exit=1 errors=1' in capsys.readouterr().out


def test_updater_uses_shared_probe(monkeypatch):
    probe = MagicMock(return_value=(2026, 8))
    monkeypatch.setattr(updater, 'newest_release', probe)
    layers = MagicMock()
    monkeypatch.setattr(updater, 'update_layers', layers)
    monkeypatch.setattr(updater, 'update_anomaly_archive', MagicMock())
    assert updater.main(['--dry-run']) == 0
    probe.assert_called_once()
    assert all(call.args[2] == (2026, 8) for call in layers.call_args_list)


def test_configured_smtp_channel_is_reused(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / '.config/insightsafrica/smtp.env'
    cfg.parent.mkdir(parents=True)
    cfg.write_text('SMTP_HOST=example.invalid\nSMTP_USER=test@example.invalid\nSMTP_PASS=test-only\nMAIL_TO=owner@example.invalid\n')
    monkeypatch.setattr(updater.Path, 'home', lambda: tmp_path)
    smtp = MagicMock()
    monkeypatch.setattr(updater.smtplib, 'SMTP', smtp)
    assert updater.notify_failure(['test'], ['test detail'], label='data freshness check')
    client = smtp.return_value.__enter__.return_value
    client.sendmail.assert_called_once()
    assert 'data freshness check FAILED' in client.sendmail.call_args.args[2]
    assert 'ALERT SENT' in capsys.readouterr().out
