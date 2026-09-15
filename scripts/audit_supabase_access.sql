-- Run in the Supabase SQL editor. Read-only catalog inspection; no user rows.
BEGIN TRANSACTION READ ONLY;

SELECT n.nspname AS schema, c.relname AS table_name,
       c.relrowsecurity AS rls_enabled, c.relforcerowsecurity AS rls_forced
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname IN ('api_keys', 'profiles', 'download_events');

SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies
WHERE schemaname = 'public' AND tablename IN ('api_keys', 'profiles', 'download_events')
ORDER BY tablename, policyname;

SELECT table_name, grantee, privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public' AND table_name IN ('api_keys', 'profiles', 'download_events')
ORDER BY table_name, grantee, privilege_type;

SELECT table_name, column_name, grantee, privilege_type
FROM information_schema.column_privileges
WHERE table_schema = 'public' AND table_name IN ('api_keys', 'profiles', 'download_events')
ORDER BY table_name, column_name, grantee, privilege_type;

SELECT p.oid::regprocedure AS function_signature, p.prosecdef AS security_definer,
       p.proacl AS explicit_acl, pg_get_functiondef(p.oid) AS definition
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public' AND p.proname IN ('handle_new_user', 'verify_and_consume_api_key');

SELECT p.oid::regprocedure AS function_signature, r.rolname,
       has_function_privilege(r.oid, p.oid, 'EXECUTE') AS can_execute
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
CROSS JOIN pg_roles r
WHERE n.nspname = 'public'
  AND p.proname IN ('handle_new_user', 'verify_and_consume_api_key')
  AND r.rolname IN ('anon', 'authenticated', 'service_role');

ROLLBACK;
