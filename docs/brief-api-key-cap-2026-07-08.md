Brief: per-user API key cap (2026-07-08)

Problem
POST /api/keys in api/main.py lets any authenticated user create unlimited
API keys. There is no server-side limit. This is a low-severity but real gap
flagged during a security review of the InsightsAfrica API.

Task
Add a per-user cap on active (non-revoked) API keys, enforced server-side in
create_api_key (api/main.py).

Required changes (api/main.py only)
1. Add a module-level constant MAX_API_KEYS_PER_USER (int, pick a sensible
   default such as 5) near the existing _FREE_MONTHS / _FREE_RPD /
   _KEY_PREFIX constants around line 152.
2. In create_api_key, after resolving user (i.e. after the existing 401
   check) and before inserting the new key row:
   - Query Supabase for the user's current active key count: a GET request
     to the api_keys REST endpoint on _SUPA_URL, filtered by the user's id,
     with revoked_at is null, selecting just id (same header pattern as
     list_api_keys — reuse _supa_headers_service).
   - If the returned row count is at or above MAX_API_KEYS_PER_USER, raise
     HTTPException with status_code 429 and a clear message such as
     "API key limit reached (max N active keys). Revoke an existing key
     first." Do NOT proceed to the insert call in that case.
   - Otherwise proceed exactly as today.
3. Do not touch list_api_keys or revoke_api_key — they are correct as-is.
4. Do not change the revoked_at is null filter semantics: revoked keys must
   never count against the cap (a user who revokes down to zero active keys
   can always create a new one, even if their lifetime key count is high).

Constraints
- Only edit api/main.py. Do not edit tests/test_api_keys.py — it is
  frozen and defines the acceptance criteria.
- Do not change the CORS config, rate limiter, or any other endpoint.
- No new dependencies.
- Keep the existing 401-for-anonymous behaviour on POST /api/keys exactly
  as-is (see test_create_api_key_requires_auth_unaffected).

Verification
Run pytest against tests/test_api_keys.py — it must pass in full
(5 passed, 0 failed). This is the sole acceptance gate.

Golden rules from docs/AI-WORKING-AGREEMENT.md
- api/main.py is a Deep-review-tier file (auth/rate-limit change) — flag
  this explicitly if/when this goes into a PR.
- No secrets. No behaviour changes beyond what's specified above.
