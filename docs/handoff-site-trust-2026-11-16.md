# Current site trust maintenance
Base: c7a65e4. Redesign remains parked. No merge or deployment.

## Changes
- Login and Ghana hub use self-hosted @supabase/supabase-js 2.119.0, with browser
  SHA-384 integrity and SHA-256/source/licence provenance. No floating auth CDN.
- Privacy links now point to an explicit owner-review draft; the contact form has
  contextual notice text. There is no invented consent requirement.
- **Do not merge/publish the draft until owner inputs are completed:** controller,
  purpose/lawful-basis decisions, contact/log/account retention, deployed provider/
  analytics/cookie details, hosting/transfers and approval date.
- Current homepage metadata lists all six countries; CHIRPS attribution is corrected;
  archive wording says rainfall starts in 1981, and the universal open-source-data
  claim is replaced by source terms and methodology links.
- Sign-in is described as account/API-key access; anonymous recent-window downloads
  remain available. No auth, quota, CSV clamping or key-policy code changes.
- Monitor is labelled as an intelligence terminal. Tablet navigation uses the menu
  before links collide. Footer links wrap; contact grid/controls shrink properly.
- Browser QA found the existing empty-array reduce() crash in hubs. All six variants
  now handle empty arrays and error-object responses without leaving cards loading.
- Existing share image, favicon and structured data are retained. No homepage redesign.

## Verification
- 12 Python page-build/trust tests pass.
- Six generated hubs verify: Total 6 | identical 6 | differ 0.
- Ten responsive/theme renders: 375/800/1024/1280/1440, dark and light; no overflow.
- Actual pinned SDK loaded successfully on login/Ghana hub with SRI; no live auth
  request was made.
- Twelve empty-array/error-response hub renders pass across all six countries.
- Five existing password-recovery scenarios and the existing key-management browser
  acceptance check pass. Their controlled fixtures omit only the real SDK tag so
  injected mocked auth remains active; the real SDK is checked separately.
- Contact payload-field construction remains identical to c7a65e4.
- Browser screenshots/results are under ignored node_modules/maintenance-evidence
  and copied to the Windows handoff; no binary evidence enters Git.

Deep review: auth-client dependency and generated Ghana hub/login behavior.
No Supabase account, API key, password, SMTP message, database policy or Cloudflare
setting changed. The privacy notice is a draft, not a declaration of legal compliance.
This branch should be reviewed separately from maintenance/public-surface and
merged in a deliberate sequence because both regenerate shared page types.

## Owner privacy proposals and Turnstile decision
The owner supplied proposed values only, all still marked [CONFIRM]:
controller Precious Kweku Obeng operating InsightsAfrica; contact info@insightsafrica.org;
ICO registration remains a confirmation slot, with no company/registration number invented.
Contact enquiries: 24 months after last correspondence, then delete.
Download logs: raw records 90 days, then country/product counts with no IPs.
Accounts/API keys: while the account exists, then delete within 30 days of a request.

No versioned 90-day download-log purge/aggregation job was found. Deployed database
jobs were not inspected. The privacy draft explicitly marks the system/policy gap.
Do not publish it as an operating retention promise before matching implementation
and owner approval. No purge, deletion job or database change was added in this branch.

Provider usage evidence and publication follow-ups are in privacy-publication-checks.md.
Turnstile is deferred by the owner; existing contact rate limits remain unchanged.
