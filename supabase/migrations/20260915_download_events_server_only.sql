-- Download telemetry contains user identifiers and IP addresses. Only backend
-- service-role requests may access it; no existing records are modified.
BEGIN;

ALTER TABLE public.download_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE public.download_events FROM PUBLIC, anon, authenticated;
GRANT INSERT ON TABLE public.download_events TO service_role;

-- Also deny client access if column grants or permissive policies exist from
-- an older deployment. The service role bypasses RLS for backend logging.
DROP POLICY IF EXISTS download_events_server_only ON public.download_events;
CREATE POLICY download_events_server_only
  ON public.download_events
  AS RESTRICTIVE
  FOR ALL
  TO anon, authenticated
  USING (false)
  WITH CHECK (false);

COMMIT;
