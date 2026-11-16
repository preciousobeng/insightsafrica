# Owner actions before any current-site deployment

These are deployment/account decisions, not actions taken by Codex.

## Privacy draft
Complete the marked inputs in maintenance/site-trust before merging/publishing its
privacy notice: responsible person/organisation, contact details, purposes/lawful
bases, contact-enquiry retention, identifiable download-log retention, account
retention/deletion criteria, deployed analytics/cookies/providers, transfer/hosting
arrangements and approval date. The draft uses the existing public contact email
and describes only the information visible in the code. It is not a compliance claim.

## Supabase download telemetry
Existing branch codex/download-event-rls contains the reviewed migration. Its three
local PostgreSQL tests passed, including reapplication and retained permissive-policy/
column-grant edge cases. Check the live schema and migration history first; apply
the reviewed SQL through the normal owner/senior process. A Git merge does not apply
the migration. No live Supabase table/policy was inspected or changed here.

## Cloudflare HSTS
Main already sends a one-year HSTS header; the supplied live review saw max-age=0,
so check the edge override. Verify HTTPS/certificates for affected hostnames before
enabling an includeSubDomains policy. Use Cloudflare SSL/TLS → Edge Certificates →
HSTS to align the reviewed policy. Do not submit preload in this cleanup.
[Cloudflare HSTS guidance](https://developers.cloudflare.com/ssl/edge-certificates/additional-options/http-strict-transport-security/)

## Rate limiting and CAPTCHA
The origin already limits contact submissions to 3/hour and 10/day. The prepared
runtime branch tests that the fourth hourly request is rejected before SMTP.
Review Cloudflare rate rules against real map/API traffic; a broad API cap can
block legitimate archive/map exploration. No edge rule or limit was changed.

Turnstile implementation/configuration is deferred pending the owner's choice.
Contact tokens need server-side verification. Supabase auth CAPTCHA is a separate
provider configuration, and clients must supply captchaToken for the protected
auth flows. A rule on insightsafrica.org does not protect requests sent directly
to the separate Supabase auth host. Do not enable provider CAPTCHA before the
matching sign-in/sign-up/recovery clients are implemented and tested.
[Turnstile validation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/),
[Supabase CAPTCHA](https://supabase.com/docs/guides/auth/auth-captcha)

## CSP and account settings
Keep CSP report-only until inline-script migration/nonces are tested. The public
surface branch adds X-Frame-Options: DENY as an actual framing control meanwhile.
Inspect Supabase password/leaked-password settings separately; no guarantee about
their current dashboard state is made by this code audit.

## Data work remains separate
GADM geometry still reaches interactive maps. Restricting redundant public copies
and bulk-download links is not licence clearance. TD-3 needs licensed replacement
boundaries, stable crosswalks and recomputation. CHIRPS v3 likewise needs a consistent
historical archive and normals; it must not be spliced into v2 history. The redesign
is parked, not released.
