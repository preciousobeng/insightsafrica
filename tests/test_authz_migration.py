"""Authorization acceptance tests against isolated PostgreSQL, never production."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import os
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALICE = '11111111-1111-1111-1111-111111111111'
BOB = '22222222-2222-2222-2222-222222222222'
CAROL = '33333333-3333-3333-3333-333333333333'


@pytest.fixture(scope='module')
def db(tmp_path_factory):
    candidates = sorted(Path('/usr/lib/postgresql').glob('*/bin'))
    if shutil.which('initdb'):
        candidates.append(Path(shutil.which('initdb')).parent)
    bins = next((p for p in reversed(candidates) if (p/'initdb').is_file()), None)
    if bins is None or (hasattr(os, 'geteuid') and os.geteuid() == 0):
        pytest.skip('Requires local PostgreSQL server binaries and a non-root user')
    tmp = tmp_path_factory.mktemp('authz-pg')
    data = tmp/'db'
    subprocess.run([str(bins/'initdb'), '-D', str(data), '-U', 'postgres', '-A', 'trust', '--no-locale'],
                   check=True, capture_output=True)
    subprocess.run([str(bins/'pg_ctl'), '-D', str(data), '-l', str(tmp/'server.log'),
                    '-o', f"-F -h '' -k {tmp} -p 55440", '-w', 'start'], check=True, capture_output=True)
    def query(sql, check=True):
        result = subprocess.run([str(bins/'psql'), '-X', '-qAt', '-h', str(tmp), '-p', '55440',
                                 '-U', 'postgres', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-c', sql],
                                capture_output=True, text=True)
        if check:
            assert result.returncode == 0, result.stderr
        return result
    try:
        query('''
            CREATE ROLE anon;
            CREATE ROLE authenticated;
            CREATE ROLE service_role BYPASSRLS;
            CREATE SCHEMA auth;
            GRANT USAGE ON SCHEMA auth TO PUBLIC;
            CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
              $$ SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
            CREATE TABLE auth.users (id uuid PRIMARY KEY, email text, raw_user_meta_data jsonb);
        ''')
        query((ROOT/'supabase/migrations/20260323_api_keys_and_profiles.sql').read_text())
        query('''
            GRANT ALL ON public.profiles, public.api_keys, public.download_events
              TO anon, authenticated, service_role;
            ALTER TABLE public.download_events ENABLE ROW LEVEL SECURITY;
            CREATE POLICY "Service role full access on download_events" ON public.download_events
              FOR ALL TO PUBLIC USING (true);
            INSERT INTO public.download_events(country, product, format, ip)
              VALUES ('test', 'flood', 'csv', '192.0.2.1');
            -- Explicit column grants independently of the table-level privileges.
            REVOKE UPDATE ON public.profiles FROM authenticated;
            GRANT UPDATE(tier, full_name) ON public.profiles TO authenticated;
            REVOKE INSERT, UPDATE ON public.api_keys FROM authenticated;
            GRANT INSERT(user_id, name, key_hash, tier), UPDATE(tier, requests_today, last_reset)
              ON public.api_keys TO authenticated;
        ''')
        migration = (ROOT/'supabase/migrations/20260915_lock_down_api_keys_downloads.sql').read_text()
        query(migration)
        query(migration)
        for uid, name in [(ALICE, 'Alice'), (BOB, 'Bob'), (CAROL, 'Carol')]:
            query(f"INSERT INTO auth.users VALUES ('{uid}', '{name}@example.invalid', "
                  f"'{{\"full_name\":\"{name}\",\"tier\":\"premium\",\"date_of_birth\":\"\"}}')")
        yield query
    finally:
        subprocess.run([str(bins/'pg_ctl'), '-D', str(data), '-m', 'fast', '-w', 'stop'],
                       check=True, capture_output=True)


def caller(uid=ALICE):
    return f"SET ROLE authenticated; SET request.jwt.claim.sub = '{uid}'; "


def hashed(label):
    return hashlib.sha256(label.encode()).hexdigest()


@pytest.mark.parametrize('role', ['anon', 'authenticated'])
def test_telemetry_is_backend_only(db, role):
    for command in ['SELECT * FROM public.download_events',
                    "INSERT INTO public.download_events(country,product,format) VALUES ('x','x','x')",
                    'DELETE FROM public.download_events']:
        result = db(f'SET ROLE {role}; {command}', check=False)
        assert result.returncode != 0 and 'permission denied' in result.stderr
    assert db("SELECT count(*) FROM public.download_events WHERE ip = '192.0.2.1'").stdout.strip() == '1'
    db("SET ROLE service_role; INSERT INTO public.download_events(country,product,format) VALUES ('ok','flood','csv')")


def test_signup_and_profile_tier_cannot_escalate(db):
    assert db(f"SELECT tier FROM public.profiles WHERE id='{ALICE}'").stdout.strip() == 'free'
    denied = db(caller()+f"UPDATE public.profiles SET tier='premium' WHERE id='{ALICE}'", check=False)
    assert denied.returncode != 0 and 'permission denied' in denied.stderr
    db(caller()+f"UPDATE public.profiles SET full_name='New name' WHERE id='{ALICE}'")
    assert db(f"SELECT full_name FROM public.profiles WHERE id='{ALICE}'").stdout.strip() == 'New name'


def test_direct_key_writes_are_denied(db):
    for sql in [f"INSERT INTO public.api_keys(user_id,name,key_hash,tier) VALUES ('{ALICE}','x','{hashed('bypass')}','premium')",
                "UPDATE public.api_keys SET tier='premium'",
                'UPDATE public.api_keys SET requests_today=0',
                'DELETE FROM public.api_keys']:
        result = db(caller()+sql, check=False)
        assert result.returncode != 0 and 'permission denied' in result.stderr


def test_create_revoke_ownership_and_quota(db):
    key_hash = hashed('rpc-key')
    key_id = db(caller()+f"SELECT id FROM public.create_api_key('test','{key_hash}')").stdout.strip()
    assert db(f"SELECT tier || ':' || requests_today FROM public.api_keys WHERE id='{key_id}'").stdout.strip() == 'free:0'
    # Verification RPC is server-only; caller cannot supply an inflated free limit.
    denied = db(caller()+f"SELECT * FROM public.verify_and_consume_api_key('{key_hash}',999999)", check=False)
    assert denied.returncode != 0 and 'permission denied' in denied.stderr
    for expected in ['1', '2', '']:
        result = db(f"SET ROLE service_role; SELECT requests_today FROM public.verify_and_consume_api_key('{key_hash}',2)")
        assert result.stdout.strip() == expected
    db(caller(BOB)+f"SELECT public.revoke_api_key('{key_id}')")
    assert db(f"SELECT revoked_at IS NULL FROM public.api_keys WHERE id='{key_id}'").stdout.strip() == 't'
    db(caller()+f"SELECT public.revoke_api_key('{key_id}')")
    assert db(f"SELECT revoked_at IS NOT NULL FROM public.api_keys WHERE id='{key_id}'").stdout.strip() == 't'
    assert db(f"SET ROLE service_role; SELECT id FROM public.verify_and_consume_api_key('{key_hash}',2)").stdout.strip() == ''


def test_rpc_authentication_and_input_validation(db):
    for function in [f"public.create_api_key('x','{hashed('anon')}')", f"public.revoke_api_key('{ALICE}')"]:
        denied = db('SET ROLE anon; SELECT '+function, check=False)
        assert denied.returncode != 0 and 'permission denied' in denied.stderr
    for name, key_hash in [(' ', hashed('blank')), ('x'*81, hashed('long')), ('good', 'bad-hash')]:
        assert db(caller(BOB)+f"SELECT public.create_api_key('{name}','{key_hash}')", check=False).returncode != 0


def test_concurrent_rpc_and_legacy_inserts_share_atomic_cap(db):
    def create(i):
        if i % 2:
            sql = caller(CAROL)+f"SELECT id FROM public.create_api_key('key{i}','{hashed(str(i))}')"
        else:
            sql = f"SET ROLE service_role; INSERT INTO public.api_keys(user_id,name,key_hash,tier,requests_today) " \
                  f"VALUES ('{CAROL}','key{i}','{hashed(str(i))}','premium',999) RETURNING id"
        return db(sql, check=False)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create, range(8)))
    assert sum(r.returncode == 0 for r in results) == 5
    assert all('API key limit reached' in r.stderr for r in results if r.returncode)
    assert db(f"SELECT count(*) FROM public.api_keys WHERE user_id='{CAROL}' AND revoked_at IS NULL").stdout.strip() == '5'
    assert db(f"SELECT count(*) FROM public.api_keys WHERE user_id='{CAROL}' AND (tier!='free' OR requests_today!=0)").stdout.strip() == '0'
    key_id = db(f"SELECT id FROM public.api_keys WHERE user_id='{CAROL}' LIMIT 1").stdout.strip()
    db(caller(CAROL)+f"SELECT public.revoke_api_key('{key_id}')")
    assert create(9).returncode == 0  # revoked keys do not consume an active slot
