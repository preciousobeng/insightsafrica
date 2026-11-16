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


def test_rest_dry_run_and_execute(monkeypatch, capsys):
    import httpx

    calls = []
    replies = iter([2, 1])

    def handle(request):
        calls.append(request)
        assert request.headers["apikey"] == "synthetic-key"
        assert request.headers["authorization"] == "Bearer synthetic-key"
        if request.method == "HEAD":
            assert request.url.path == "/rest/v1/download_events"
            assert request.url.params["select"] == "id"
            assert request.url.params["created_at"].startswith("lt.")
            assert request.headers["prefer"] == "count=exact"
            return httpx.Response(200, headers={"Content-Range": "*/0"})
        assert request.url.path == "/rest/v1/rpc/retain_download_events"
        assert request.content == b'{"batch_size":2}'
        return httpx.Response(200, json=next(replies))

    client = runner.RetentionClient(
        "https://synthetic.invalid", "synthetic-key", httpx.MockTransport(handle)
    )
    monkeypatch.setattr(runner.RetentionClient, "from_env", lambda: client)
    assert runner.main([]) == 0
    assert [r.method for r in calls] == ["HEAD"]
    assert runner.main(["--execute", "--batch-size", "2"]) == 0
    assert [r.method for r in calls] == ["HEAD", "POST", "POST", "HEAD"]
    assert "synthetic-key" not in capsys.readouterr().out


@pytest.mark.parametrize("status", [302, 401, 403, 500])
def test_rest_failures_are_sanitized_and_not_retried(status):
    import httpx

    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            status, headers={"location": "https://other.invalid"}, text="secret-or-IP"
        )

    client = runner.RetentionClient(
        "https://synthetic.invalid", "synthetic-key", httpx.MockTransport(handle)
    )
    with pytest.raises(RuntimeError) as error:
        client.retain(2)
    assert len(calls) == 1
    assert "secret-or-IP" not in str(error.value)
    assert "synthetic-key" not in str(error.value)


@pytest.mark.parametrize("payload", [True, -1, 3, {}, "2"])
def test_invalid_rpc_response_fails_closed(payload):
    import httpx

    client = runner.RetentionClient(
        "https://synthetic.invalid",
        "synthetic-key",
        httpx.MockTransport(lambda r: httpx.Response(200, json=payload)),
    )
    with pytest.raises(RuntimeError):
        client.retain(2)


def test_count_requires_exact_total():
    import httpx

    client = runner.RetentionClient(
        "https://synthetic.invalid",
        "synthetic-key",
        httpx.MockTransport(
            lambda r: httpx.Response(200, headers={"Content-Range": "0-0/*"})
        ),
    )
    with pytest.raises(RuntimeError):
        client.count_eligible()


def test_missing_config_and_argument_bounds(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(RuntimeError):
        runner.main([])
    with pytest.raises(SystemExit):
        runner.main(["--batch-size", "0"])


def test_timeout_does_not_retry_or_leak_secrets():
    import httpx

    calls = []

    def handle(request):
        calls.append(request)
        raise httpx.ReadTimeout("synthetic-secret", request=request)

    client = runner.RetentionClient(
        "https://synthetic.invalid", "synthetic-key", httpx.MockTransport(handle)
    )
    with pytest.raises(RuntimeError) as error:
        client.retain(2)
    assert len(calls) == 1
    assert "synthetic-secret" not in str(error.value)


def test_execute_stops_at_batch_limit(monkeypatch, capsys):
    class FakeClient:
        def __init__(self):
            self.calls = 0

        def retain(self, size):
            self.calls += 1
            return size

        def count_eligible(self):
            return 8

    client = FakeClient()
    monkeypatch.setattr(runner.RetentionClient, "from_env", lambda: client)
    assert runner.main(["--execute", "--max-batches", "2", "--batch-size", "1"]) == 2
    assert client.calls == 2
    assert '"eligible_remaining": 8' in capsys.readouterr().out


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
