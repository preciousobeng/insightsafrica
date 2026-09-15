"""Exercise the telemetry migration in an isolated PostgreSQL cluster.

Requires PostgreSQL server binaries locally; never connects to Supabase.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def database(tmp_path_factory):
    candidates = [Path(p) for p in sorted(Path("/usr/lib/postgresql").glob("*/bin"))]
    if shutil.which("initdb"):
        candidates.append(Path(shutil.which("initdb")).parent)
    bins = next((p for p in reversed(candidates) if (p / "initdb").is_file()), None)
    if bins is None or (hasattr(os, "geteuid") and os.geteuid() == 0):
        pytest.skip("Requires PostgreSQL server binaries and a non-root user")
    tmp = tmp_path_factory.mktemp("telemetry-postgres")
    data = tmp / "db"
    subprocess.run([str(bins / "initdb"), "-D", str(data), "-U", "postgres",
                    "-A", "trust", "--no-locale"], check=True, capture_output=True)
    subprocess.run([str(bins / "pg_ctl"), "-D", str(data), "-l", str(tmp / "server.log"),
                    "-o", f"-F -h '' -k {tmp} -p 55439", "-w", "start"],
                   check=True, capture_output=True)
    def query(sql, check=True):
        return subprocess.run([str(bins / "psql"), "-X", "-qAt", "-h", str(tmp),
                               "-p", "55439", "-U", "postgres", "-d", "postgres",
                               "-v", "ON_ERROR_STOP=1", "-c", sql],
                              check=check, capture_output=True, text=True)
    try:
        query("""
            CREATE ROLE anon;
            CREATE ROLE authenticated;
            CREATE ROLE service_role BYPASSRLS;
            CREATE TABLE public.download_events (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(), country text,
                product text, format text, user_id uuid, from_date text,
                to_date text, ip text, created_at timestamptz DEFAULT now()
            );
            GRANT ALL ON public.download_events TO anon, authenticated, service_role;
            GRANT SELECT(id), UPDATE(ip) ON public.download_events TO anon, authenticated;
            CREATE POLICY legacy_open ON public.download_events FOR ALL TO PUBLIC
                USING (true) WITH CHECK (true);
            INSERT INTO public.download_events (country, ip) VALUES ('test', '192.0.2.1');
        """)
        migration = (ROOT / "supabase/migrations/20260915_download_events_server_only.sql").read_text()
        query(migration)
        query(migration)  # safe to reapply
        assert query("SELECT has_table_privilege('anon', 'public.download_events', 'SELECT')").stdout.strip() == "f"
        # Prove the restrictive policy also protects against a later accidental
        # column-level grant while a legacy permissive policy still exists.
        query("GRANT SELECT(id), UPDATE(ip) ON public.download_events TO anon, authenticated")
        yield query
    finally:
        subprocess.run([str(bins / "pg_ctl"), "-D", str(data), "-m", "fast", "-w", "stop"],
                       check=True, capture_output=True)


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_client_cannot_read_or_modify_events(database, role):
    # A retained column SELECT grant and permissive policy still expose no rows.
    assert database(f"SET ROLE {role}; SELECT id FROM public.download_events").stdout.strip() == ""
    assert database(f"SET ROLE {role}; INSERT INTO public.download_events (country) VALUES ('blocked')",
                    check=False).returncode != 0
    assert database(f"SET ROLE {role}; DELETE FROM public.download_events", check=False).returncode != 0
    database(f"SET ROLE {role}; UPDATE public.download_events SET ip = '192.0.2.99'")
    assert database("SELECT count(*) FROM public.download_events WHERE ip = '192.0.2.99'").stdout.strip() == "0"


def test_backend_can_still_log_and_existing_data_survives(database):
    assert database("SELECT count(*) FROM public.download_events WHERE ip = '192.0.2.1'").stdout.strip() == "1"
    database("SET ROLE service_role; INSERT INTO public.download_events (country, product, format, ip) "
             "VALUES ('test', 'flood', 'csv', '192.0.2.2')")
    assert database("SELECT count(*) FROM public.download_events WHERE ip = '192.0.2.2'").stdout.strip() == "1"
