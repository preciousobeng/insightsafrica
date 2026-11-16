"""Synthetic disposable PostgreSQL only; never connects to configured databases."""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "retention", ROOT / "scripts/retain_download_events.py"
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_runner_defaults_to_read_only(monkeypatch, capsys):
    calls = []

    def fake(sql, *, readonly=False):
        calls.append((sql, readonly))
        return 7

    monkeypatch.setattr(runner, "query", fake)
    assert runner.main([]) == 0
    assert calls == [(runner.COUNT, True)]
    assert '"deleted": 0' in capsys.readouterr().out


def test_runner_bounds_and_batches(monkeypatch):
    with pytest.raises(SystemExit):
        runner.main(["--batch-size", "0"])
    replies = iter([2, 1, 0])
    calls = []

    def fake(sql, *, readonly=False):
        calls.append((sql, readonly))
        return next(replies)

    monkeypatch.setattr(runner, "query", fake)
    assert runner.main(["--execute", "--batch-size", "2"]) == 0
    assert len(calls) == 3 and calls[-1][1]


@pytest.mark.parametrize("version", ["16", "18"])
def test_atomic_retention_on_disposable_postgres(version):
    binaries = Path("/usr/lib/postgresql") / version / "bin"
    if not (binaries / "initdb").exists():
        pytest.skip("PostgreSQL binaries unavailable")
    with tempfile.TemporaryDirectory(prefix="ia-retention-") as directory:
        base = Path(directory)
        data = base / "db"
        env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}

        def command(name, *args, **kwargs):
            return subprocess.run(
                [str(binaries / name), *args],
                env=env,
                text=True,
                capture_output=True,
                check=True,
                **kwargs,
            )

        command("initdb", "-D", str(data), "-A", "trust", "--no-locale")
        command(
            "pg_ctl",
            "-D",
            str(data),
            "-l",
            str(base / "log"),
            "-o",
            f"-h '' -k {base} -p 55447",
            "-w",
            "start",
        )

        def sql(text):
            return command(
                "psql",
                "-h",
                str(base),
                "-p",
                "55447",
                "-d",
                "postgres",
                "-XqAt",
                "-v",
                "ON_ERROR_STOP=1",
                input=text,
            ).stdout.strip()

        try:
            sql(
                "CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS; CREATE TABLE public.download_events(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),country text NOT NULL,product text NOT NULL,ip text,user_id uuid,created_at timestamptz NOT NULL);"
            )
            migration = (
                ROOT / "supabase/migrations/20261116_download_event_retention.sql"
            ).read_text()
            sql(migration)
            sql(migration)
            assert sql("SELECT count(*) FROM download_events") == "0"
            assert sql(
                "BEGIN; SET TIME ZONE 'Pacific/Honolulu'; INSERT INTO download_events(country,product,created_at) VALUES ('SN','heat','2000-02-01 00:30:00+00'); SELECT retain_download_events(100); SELECT month FROM download_event_monthly_counts; ROLLBACK;"
            ).splitlines() == ["1", "2000-02-01"]
            with pytest.raises(subprocess.CalledProcessError):
                sql("SELECT retain_download_events(0)")
            with pytest.raises(subprocess.CalledProcessError):
                sql("SET ROLE anon; SELECT * FROM download_event_monthly_counts")
            output = sql("""BEGIN; SET TIME ZONE 'Pacific/Honolulu';
              INSERT INTO download_events(country,product,ip,created_at) VALUES
              ('GH','rain','192.0.2.1',transaction_timestamp()-interval '91 days'),
              ('GH','rain','192.0.2.2',transaction_timestamp()-interval '91 days'),
              ('GH','rain','192.0.2.3',transaction_timestamp()-interval '90 days');
              SELECT retain_download_events(1); SELECT retain_download_events(10);
              SELECT retain_download_events(10);
              SELECT count(*) FROM download_events;
              SELECT sum(download_count) FROM download_event_monthly_counts;
              ROLLBACK;""")
            assert output.splitlines() == ["1", "1", "0", "1", "2"]
            sql(
                "INSERT INTO download_events(country,product,ip,created_at) VALUES ('GH','rain','192.0.2.1',now()-interval '91 days'); CREATE FUNCTION reject_counts() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic failure'; END $$; CREATE TRIGGER fail_counts BEFORE INSERT ON download_event_monthly_counts FOR EACH ROW EXECUTE FUNCTION reject_counts();"
            )
            with pytest.raises(subprocess.CalledProcessError):
                sql("SELECT retain_download_events(100)")
            assert sql("SELECT count(*) FROM download_events") == "1"
            sql(
                "DROP TRIGGER fail_counts ON download_event_monthly_counts; GRANT SELECT,DELETE,UPDATE(id) ON download_events TO service_role;"
            )
            with pytest.raises(subprocess.CalledProcessError):
                sql("SET ROLE anon; SELECT retain_download_events(100)")
            assert (
                sql("SET ROLE service_role; SELECT retain_download_events(100)") == "1"
            )
            assert sql(
                "SELECT column_name FROM information_schema.columns WHERE table_name='download_event_monthly_counts' ORDER BY ordinal_position"
            ).splitlines() == ["country", "product", "month", "download_count"]
        finally:
            command("pg_ctl", "-D", str(data), "-m", "immediate", "-w", "stop")
