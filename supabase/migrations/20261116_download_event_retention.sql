-- PROPOSAL ONLY: owner review required; migration never purges or schedules work.
BEGIN;
CREATE TABLE IF NOT EXISTS public.download_event_monthly_counts (
 country text NOT NULL, product text NOT NULL, month date NOT NULL,
 download_count bigint NOT NULL CHECK (download_count > 0),
 PRIMARY KEY (country, product, month)
);
ALTER TABLE public.download_event_monthly_counts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.download_event_monthly_counts FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.download_event_monthly_counts TO service_role;
CREATE OR REPLACE FUNCTION public.retain_download_events(batch_size integer DEFAULT 10000)
RETURNS bigint LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public AS $$
DECLARE removed bigint;
BEGIN
 IF batch_size < 1 OR batch_size > 100000 OR batch_size IS NULL THEN
  RAISE EXCEPTION 'batch_size must be 1..100000';
 END IF;
 IF NOT pg_try_advisory_xact_lock(73284, 9001) THEN
  RAISE EXCEPTION 'retention batch already running' USING ERRCODE = '55P03';
 END IF;
 WITH eligible AS (
  SELECT id FROM public.download_events
  WHERE created_at < transaction_timestamp() - interval '90 days'
  ORDER BY created_at, id LIMIT batch_size FOR UPDATE SKIP LOCKED
 ), deleted AS (
  DELETE FROM public.download_events d USING eligible e WHERE d.id = e.id
  RETURNING d.country, d.product, d.created_at
 ), counts AS (
  INSERT INTO public.download_event_monthly_counts AS existing
   (country, product, month, download_count)
  SELECT country, product, date_trunc('month', created_at AT TIME ZONE 'UTC')::date, count(*)
  FROM deleted GROUP BY 1,2,3
  ON CONFLICT (country, product, month) DO UPDATE
   SET download_count = existing.download_count + EXCLUDED.download_count
  RETURNING download_count
 ) SELECT count(*) INTO removed FROM deleted;
 RETURN removed;
END;
$$;
REVOKE ALL ON FUNCTION public.retain_download_events(integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.retain_download_events(integer) TO service_role;
COMMIT;
