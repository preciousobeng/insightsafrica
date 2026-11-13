# Homepage vendor bundle

homepage-vendor.js contains official pinned minified UMD builds in provenance.json order. It exposes window.d3 and window.topojson. No runtime CDN is needed. Individual ISC licences and source/tarball SHA/integrity are retained beside the bundle.

The production browser does not need npm or a new bundler. Rebuild only by fetching the exact recorded official tarballs, verifying npm integrity, extracting dist/<package>.min.js and concatenating with newline/semicolon separators. Include only these browser members, not package CLI files. Measured gzip size is recorded in provenance.json.
