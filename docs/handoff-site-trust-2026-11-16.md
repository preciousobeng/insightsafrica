# Site trust review revision

Privacy draft and all links are removed from this branch and prepared independently on maintenance/privacy-notice based on main. No privacy draft is published by this branch.

Leaflet 1.9.4 and Chart.js 4.4.2 are exact npm tarball members with npm integrity verification, SHA256/SHA384 provenance, licences and SRI on generated HTML. Leaflet image dependencies are included. Syne and DM Mono WOFF2 fonts are self-hosted with OFL licences and source/hash provenance (109,508 font bytes). Supabase remains pinned at 2.119.0.

Removed unsupported open-source footer claims; corrected CI/SN/CV GADM wording without changing the boundaries or licensing exposure. Regenerated all 42 country pages from templates. The homepage stat says Open data and links source terms.

Measured header links after fonts loaded at every pixel from 850–1100: first collision-free width respecting 32px side padding is 987px. Hamburger applies through 986px; compact desktop controls hide the redundant Explore CTA through 1280px. Hero and mobile navigation retain that destination.

No merge, deployment or production write. Vendoring now overlaps public-surface Flood templates; review the combined patch rather than assuming the original no-overlap finding still holds.

Validation: 15 focused Python/build checks; 16 width/theme browser renders; 12 empty/error hub cases; six synthetic maps with real local Leaflet/Chart.js. Public-surface frontend diff passes git apply --3way --check; this is patch compatibility, not a combined runtime test.

Mocked acceptance: five password-recovery/login cases and key-management flows pass. Harnesses serve exact local font bytes to retain SRI verification.
