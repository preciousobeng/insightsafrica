-- Apply before deploying the RPC-backed key UI. Existing HTTP key endpoints
-- use service-role writes and remain compatible. Existing records are retained.
BEGIN;

ALTER TABLE public.download_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access on download_events" ON public.download_events;
DROP POLICY IF EXISTS download_events_server_only ON public.download_events;
DROP POLICY IF EXISTS download_events_service_role_only ON public.download_events;
CREATE POLICY download_events_service_role_only ON public.download_events
  FOR ALL TO service_role USING (true) WITH CHECK (true);
REVOKE ALL ON public.download_events FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.download_events TO service_role;

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, email, tier, date_of_birth)
  VALUES (NEW.id, NEW.raw_user_meta_data->>'full_name', NEW.email, 'free',
          nullif(NEW.raw_user_meta_data->>'date_of_birth', '')::date)
  ON CONFLICT (id) DO UPDATE
    SET full_name = EXCLUDED.full_name, email = EXCLUDED.email;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
REVOKE UPDATE ON public.profiles FROM PUBLIC, anon, authenticated;
-- Remove any explicit sensitive-column grants as well as table-level grants.
REVOKE UPDATE (tier, id, created_at) ON public.profiles FROM PUBLIC, anon, authenticated;
GRANT UPDATE (full_name, email, date_of_birth) ON public.profiles TO authenticated;

ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON public.api_keys FROM PUBLIC, anon, authenticated;
-- Remove the live ownership-only write policies as defense in depth.
DROP POLICY IF EXISTS "Users can create own API keys" ON public.api_keys;
DROP POLICY IF EXISTS "Users can revoke own API keys" ON public.api_keys;

-- Explicit column privileges can outlive table grants. Remove them too,
-- including grants issued through PUBLIC or outside the tracked migrations.
DO $$
DECLARE
  col record;
BEGIN
  FOR col IN SELECT table_name, column_name FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name IN ('api_keys', 'download_events')
  LOOP
    EXECUTE format('REVOKE INSERT (%I), UPDATE (%I), REFERENCES (%I) ON public.%I FROM PUBLIC, anon, authenticated',
                   col.column_name, col.column_name, col.column_name, col.table_name);
    IF col.table_name = 'download_events' THEN
      EXECUTE format('REVOKE SELECT (%I) ON public.download_events FROM PUBLIC, anon, authenticated', col.column_name);
    END IF;
  END LOOP;
END;
$$;

-- All inserts, including legacy service-role HTTP endpoints, share the same
-- validation and cap. Lock the owning profile to serialize concurrent inserts.
CREATE OR REPLACE FUNCTION public.enforce_api_key_creation()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
BEGIN
  PERFORM 1 FROM public.profiles WHERE id = NEW.user_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Profile required to create API keys' USING ERRCODE = '23503';
  END IF;
  IF NEW.name IS NULL OR length(btrim(NEW.name)) NOT BETWEEN 1 AND 80 THEN
    RAISE EXCEPTION 'Key name must contain 1 to 80 characters' USING ERRCODE = '22023';
  END IF;
  IF NEW.key_hash IS NULL OR NEW.key_hash !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'Invalid SHA-256 key hash' USING ERRCODE = '22023';
  END IF;
  IF (SELECT count(*) FROM public.api_keys
      WHERE user_id = NEW.user_id AND revoked_at IS NULL) >= 5 THEN
    RAISE EXCEPTION 'API key limit reached (max 5 active keys). Revoke an existing key first.'
      USING ERRCODE = 'P0001';
  END IF;
  NEW.name := btrim(NEW.name);
  NEW.tier := 'free';
  NEW.requests_today := 0;
  NEW.last_reset := CURRENT_DATE;
  NEW.revoked_at := NULL;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.enforce_api_key_creation() FROM PUBLIC, anon, authenticated;
DROP TRIGGER IF EXISTS enforce_api_key_creation ON public.api_keys;
CREATE TRIGGER enforce_api_key_creation BEFORE INSERT ON public.api_keys
  FOR EACH ROW EXECUTE FUNCTION public.enforce_api_key_creation();

CREATE OR REPLACE FUNCTION public.create_api_key(key_name text, key_hash_input text)
RETURNS public.api_keys LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  caller uuid := auth.uid();
  result public.api_keys;
BEGIN
  IF caller IS NULL THEN
    RAISE EXCEPTION 'Authentication required' USING ERRCODE = '42501';
  END IF;
  INSERT INTO public.api_keys (user_id, name, key_hash, tier, requests_today, last_reset)
  VALUES (caller, key_name, key_hash_input, 'free', 0, CURRENT_DATE)
  RETURNING * INTO result;
  RETURN result;
END;
$$;
REVOKE ALL ON FUNCTION public.create_api_key(text, text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.create_api_key(text, text) TO authenticated;

CREATE OR REPLACE FUNCTION public.revoke_api_key(key_id uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Authentication required' USING ERRCODE = '42501';
  END IF;
  UPDATE public.api_keys SET revoked_at = now()
  WHERE id = key_id AND user_id = auth.uid() AND revoked_at IS NULL;
END;
$$;
REVOKE ALL ON FUNCTION public.revoke_api_key(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.revoke_api_key(uuid) TO authenticated;

-- Clients must not invoke the quota-consumption routine with a custom limit.
REVOKE ALL ON FUNCTION public.verify_and_consume_api_key(text, integer)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.verify_and_consume_api_key(text, integer) TO service_role;

COMMIT;
