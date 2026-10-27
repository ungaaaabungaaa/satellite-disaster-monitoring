# Satellite Monitoring implementation plan

The user approved rebuilding `GeoMapper` as `satellite-disaster-monitoring`, preserving its identity and history. Original main `fde2271e5c1ef8bf022a465d1a562aba74b3c2e6` is verified remotely on `archive/before-satellite-monitoring-2026-10-27`. Repository ID `R_kgDOLKP_ug` and 20 stars were preserved. Keep the legacy MIT notice. MyPortfolio stays unchanged. The user approved the v3 line-art cover for the repository README; keep it labeled as a generated concept.

## First usable scope

A bounded, reproducible historical surface-water change study and an offline geospatial viewer. Use original Sentinel-2B Level2A processing-baseline02.14 products from tile45RYJ, 14February2020 and2August2020. These products explicitly declare reflectance scale0.0001/offset0; this avoids the known post2022 offset ambiguity in legacy Earth Search products. NASA's August2020 Bangladesh article supplies event context, not ground-truth labels for this crop. A dry-season/monsoon pair includes ordinary seasonal differences; report candidate water changes rather than confirmed flood damage.

## Steps

1. `docs/legacy-license.txt`, `docs/data.md`, and pinned STAC item JSON: preserve attribution and record public provider URLs, acquisition timestamps, processing convention, legal notice, crop, hashes, and selection reasons. Dependencies: verified archive. Risk: medium.
2. `src/satellite_monitoring/http_range.py` and tests: implement read-only fixed-asset HTTP range access, explicit byte/request/time bounds, response-range/length checks, stable ETag checks, no redirects or arbitrary destinations, and per-range SHA256 provenance. This keeps downloads small. Risk: high. Start with controlled HTTP fixtures.
3. `acquire.py` and tests: fetch only the pinned green/SWIR/SCL/true-color assets, crop to a bounded WGS84 AOI on a shared20m UTM grid, average green readings, retain nearest SCL classes, and verify derived array digests. Save two small six-band GeoTIFF crops with CRS, affine, scale/offset, nodata, source ID and acquisition tags. Risk: high.
4. `analysis.py` and tests: validate bounded GeoTIFF input and meter-based projected grids, align the second date explicitly, mask nodata/invalid optical data and SCL classes other than4/5/6 on both dates, compute MNDWI only with positive denominator, and count water gains/losses/persistence on the shared valid footprint. Use affine pixel area, clear denominators, fixed thresholds and sensitivity results. No failure/disaster probability or accuracy claims. Risk: high.
5. `export.py`, `resources/viewer/`, and tests: export actual pixels and metadata to a browser viewer. Provide before/after/split/change modes, threshold selection, measured area and valid-footprint counts, coordinate inspection, geographic bounds and a scale indication. The view is a UTM raster grid, not a guessed geographic map. Default demo works offline with bundled derived data. Risk: medium.
6. Add CLI, README, method/data/verification notes, MIT license, contribution/security notes, package build and cross-platform CI. No accounts, paid keys, training claims, real-time warning claim or portfolio edits; only the approved labeled concept cover is used. Risk: low.
7. Run behavior tests, coverage/lint, exact installed-package and CLI checks, a fresh real acquisition, deterministic historical analysis, and browser visual/interaction QA. Save actual outputs. Commit/push/PR after checks; root independently reviews and merges only after CI passes. Remove task-only dependencies/cache after verified remote backup and review. Risk: high.

## Interfaces

- `satellite-lab acquire --output NEW_DIR`: explicit network request for pinned historical scenes; refuse existing nonempty outputs. Result: two GeoTIFF crops and acquisition provenance.
- `satellite-lab analyze --before PATH --after PATH --output NEW_DIR`: bounded local GeoTIFF inputs with documented band/timestamp/reflectance tags; no network. Result: measured JSON, classification GeoTIFF, browser data and static viewer.
- `satellite-lab serve --directory PATH --port 8790`: loopback-only static preview of an existing exported viewer. No write API or remote control.
- Exit0 success,2 argument syntax,1 controlled input/runtime failure. Do not overwrite existing result directories.

## Evidence

Success requires hash-pinned real source/crop data, documented scaling and quality masking, correct metric area/denominators, useful synthetic edge-case tests, an actual historical run and working georeferenced viewer, public reviewable code and preserved original history. A water index does not establish flood attribution, ground-truth accuracy or operational readiness.

## Execution evidence

The real fixed-asset acquisition completed with mandatory crop checksums: 27,000,832 bytes in 77 requests, 322.596 seconds on the final verification run. Both derived TIFF byte hashes match the bundled crops. Acquisition limits are 64 MB, 256 requests, and a 600-second budget (20-second per-operation timeout). Direct same-CRS window reads use COG overviews, average green and nearest SWIR/SCL/RGB; source integer DN averaging rounds before float32 output. No bootstrap checksum bypass remains.

The study grid is 1031 × 1129 at 20 m, EPSG:32645. Only 427,550 of 1,163,999 pixels are valid on both dates: 171.02 km² / 36.73%. At threshold 0.00, candidate gain is 103.6828 km² and loss is 2.9048 km². Excluded area is not extrapolated. Source metadata, effective scale/offset, nodata, both-date SCL masks, input/code hashes, area denominators, sensitivity presets, and actual outputs are retained. These are candidate spectral-water changes, not confirmed flood attribution or accuracy.

Independent review requested exact scale/offset binding for the pinned-study label, Host checks on the loopback server, raw-DN nodata before offsets, and installed-wheel resource checks. These are included with focused regressions. Final packaging, full verification, PR/CI, independent final review, merge, and storage cleanup are tracked in the project verification record.
