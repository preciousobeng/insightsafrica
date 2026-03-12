-- =============================================================
-- InsightsAfrica — profiles table + duplicate signup protection
-- Run in: Supabase Dashboard → SQL Editor → New Query
-- =============================================================


-- 1. Profiles table
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
  id             UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name      TEXT        NOT NULL,
  email          TEXT        UNIQUE NOT NULL,
  date_of_birth  DATE,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);


-- 2. Row Level Security
-- ---------------------------------------------------------
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Users can only read their own profile
CREATE POLICY "Users can view own profile"
  ON public.profiles
  FOR SELECT
  USING (auth.uid() = id);


-- 3. Trigger function — auto-creates profile on every new signup
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, email, date_of_birth)
  VALUES (
    NEW.id,
    NEW.raw_user_meta_data->>'full_name',
    NEW.email,
    CASE
      WHEN NEW.raw_user_meta_data->>'date_of_birth' IS NOT NULL
      THEN (NEW.raw_user_meta_data->>'date_of_birth')::DATE
      ELSE NULL
    END
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

-- Attach trigger to auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- 4. RPC — duplicate check (name + DOB combination)
-- Called from the frontend BEFORE sb.auth.signUp()
-- Returns true if that name+DOB combo is already registered
-- SECURITY DEFINER so unauthenticated users can call it
-- without being able to query the profiles table directly
-- ---------------------------------------------------------
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
    WHERE LOWER(TRIM(full_name))  = LOWER(TRIM(check_name))
    AND   date_of_birth           = check_dob
  );
$$;
