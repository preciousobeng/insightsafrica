-- InsightsAfrica Supabase migration
-- Adds profile tiers, API key storage, and atomic API key verification.

CREATE TABLE IF NOT EXISTS public.profiles (
  id             UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name      TEXT        NOT NULL,
  email          TEXT        UNIQUE NOT NULL,
  tier           TEXT        NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'premium')),
  date_of_birth  DATE,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'free';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'profiles_tier_check'
  ) THEN
    ALTER TABLE public.profiles
      ADD CONSTRAINT profiles_tier_check
      CHECK (tier IN ('free', 'premium'));
  END IF;
END;
$$;

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
CREATE POLICY "Users can view own profile"
  ON public.profiles
  FOR SELECT
  USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile"
  ON public.profiles
  FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, email, tier, date_of_birth)
  VALUES (
    NEW.id,
    NEW.raw_user_meta_data->>'full_name',
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'tier', 'free'),
    CASE
      WHEN NEW.raw_user_meta_data->>'date_of_birth' IS NOT NULL
      THEN (NEW.raw_user_meta_data->>'date_of_birth')::DATE
      ELSE NULL
    END
  )
  ON CONFLICT (id) DO UPDATE
  SET full_name = EXCLUDED.full_name,
      email = EXCLUDED.email,
      tier = COALESCE(public.profiles.tier, EXCLUDED.tier);
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

CREATE OR REPLACE FUNCTION public.check_duplicate_signup(
  check_name TEXT,
  check_dob  DATE
)
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.profiles
    WHERE LOWER(TRIM(full_name)) = LOWER(TRIM(check_name))
      AND date_of_birth = check_dob
  );
$$;

CREATE TABLE IF NOT EXISTS public.download_events (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  country     TEXT NOT NULL,
  product     TEXT NOT NULL,
  format      TEXT NOT NULL,
  user_id     UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  from_date   TEXT,
  to_date     TEXT,
  ip          TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_download_events_created_at ON public.download_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_download_events_country_product ON public.download_events(country, product);

CREATE TABLE IF NOT EXISTS public.api_keys (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  key_hash        TEXT NOT NULL UNIQUE,
  tier            TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'premium')),
  requests_today  INTEGER NOT NULL DEFAULT 0,
  last_reset      DATE NOT NULL DEFAULT CURRENT_DATE,
  revoked_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON public.api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON public.api_keys(key_hash) WHERE revoked_at IS NULL;

ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own API keys" ON public.api_keys;
CREATE POLICY "Users can view own API keys"
  ON public.api_keys
  FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create own API keys" ON public.api_keys;
CREATE POLICY "Users can create own API keys"
  ON public.api_keys
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can revoke own API keys" ON public.api_keys;
CREATE POLICY "Users can revoke own API keys"
  ON public.api_keys
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION public.verify_and_consume_api_key(
  key_hash_input TEXT,
  free_limit INTEGER DEFAULT 500
)
RETURNS TABLE (
  id UUID,
  user_id UUID,
  tier TEXT,
  requests_today INTEGER,
  last_reset DATE
)
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  key_row public.api_keys%ROWTYPE;
  next_count INTEGER;
  today DATE := CURRENT_DATE;
BEGIN
  SELECT *
  INTO key_row
  FROM public.api_keys
  WHERE key_hash = key_hash_input
    AND revoked_at IS NULL
  FOR UPDATE;

  IF NOT FOUND THEN
    RETURN;
  END IF;

  IF key_row.last_reset <> today THEN
    key_row.requests_today := 0;
    key_row.last_reset := today;
  END IF;

  next_count := key_row.requests_today + 1;

  IF key_row.tier = 'free' AND next_count > free_limit THEN
    RETURN;
  END IF;

  UPDATE public.api_keys
  SET requests_today = next_count,
      last_reset = key_row.last_reset
  WHERE public.api_keys.id = key_row.id;

  RETURN QUERY
  SELECT key_row.id, key_row.user_id, key_row.tier, next_count, key_row.last_reset;
END;
$$;
