# Security

This is a local research tool. It does not run a public service or accept remote uploads. Keep the preview bound to the provided loopback address. It checks the Host header, serves a fixed set of exported filenames, rejects symlinks and traversal, and provides no write API. Do not put this development server behind a public proxy.

Acquisition permits only the fixed public HTTPS asset host and paths. It rejects redirects, credentials, changed ETags, unexpected byte ranges, and source/crop checksum mismatches. Downloads have byte, request, operation-time, and overall-time limits. No source archives are extracted. Offline inputs have file, pixel, band, CRS, timestamp, and scaling bounds. Raster processing still uses native GDAL code: keep the pinned dependency set under review and process only files you trust. These checks are not a general hostile-file sandbox.

Do not include private study imagery or precise sensitive locations in a public bug report. For a vulnerability, use this repository's GitHub private vulnerability reporting feature if available. If it is unavailable, open a minimal issue asking for a private contact, without exploitation details or sensitive data.
