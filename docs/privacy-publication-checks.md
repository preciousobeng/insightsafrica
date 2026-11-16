# Privacy draft publication checks
16 November 2026. Proposed values remain [CONFIRM]; this is not an approved policy.

## Provider evidence
- Supabase auth/database: api/main.py uses configured SUPABASE_URL for auth,
  profiles, API-key RPCs and download_events; the login/hub client uses Supabase.
- Brevo contact delivery: api/main.py reads BREVO_SMTP_USER/BREVO_SMTP_PASS and
  connects to smtp-relay.brevo.com:587. No credential values were read.
- Cloudflare delivery/security: README Tech Stack documents Cloudflare Tunnel/proxy;
  api/main.py's ingress/rate-limit logic uses the Cloudflare client-IP header.
- Oracle Cloud hosting: README Tech Stack documents OCI ARM; a read-only cloud-id
  command on the hosting machine returned oracle. No instance identifiers,
  credentials, database contents or configuration were collected or changed.
Technical use does not establish contractual processor roles, regions or transfers;
those remain owner confirmations in the notice.

## Proposed retention versus implementation
- Contact: [CONFIRM: 24 months after last correspondence], then delete. Confirm the
  mailbox/provider handling and deletion procedure.
- Download logs: [CONFIRM: raw records 90 days], then country/product/month counts with no
  IPs. Repository searches of api/, scripts/ and supabase/ found inserts and schema/
  access-control migrations, but no versioned 90-day purge-and-aggregation job.
  External database schedulers were not inspected. The proposed migration and runner below are prepared for owner review; they have
  not been applied or scheduled. Reconcile the actual operation before publishing.
- Accounts/API keys: while the account exists, then [CONFIRM: 30 days] after a deletion
  request. Confirm the fulfilment and any relevant backup handling before publication.
  The draft does not claim automatic account deletion.

## Outstanding owner approvals
Confirm the controller proposal, ICO registration status, purposes/lawful bases,
retention values and working procedures, analytics/cookies, contractual provider
roles, international-transfer/hosting details and notice approval date.
No company number or ICO registration number has been invented.

Turnstile is deferred by explicit owner choice. Existing contact limits stay intact.
No merge, deployment, database operation, purge job or provider-setting change occurred.

## Review split and map/font providers
This privacy branch is rebased onto the approved maintenance/site-trust and contains the draft
and every link to it. Esri map tiles at services.arcgisonline.com are used in the
existing module templates. The parent site-trust revision self-hosts Google Fonts. Confirm the deployed release before removing
the conditional Google Fonts provider entry from the approved notice.

A proposed retention migration/script is now prepared here for owner review, not
applied or scheduled. Country/product/month counts contain no IP or account IDs.
The earlier finding of no versioned purge describes the pre-proposal codebase;
it does not claim a prepared job is already operating.
