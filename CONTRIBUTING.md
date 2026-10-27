# Contributing

Use Python 3.12 or 3.13 and the recorded dependency file. Run lint, Python behavior tests, Node viewer tests, and the package build commands in the README before opening a pull request. Explain the problem, the change, the verification evidence, and any limit that remains.

Add controlled geospatial fixtures for changes to alignment, nodata, quality masks, thresholds, or area denominators. Preserve projected coordinates and the common-footprint rule. Treat source or metadata pin changes as a new reviewed study: supply official provenance, data rights, exact timestamps, new hashes, and an actual run. Do not weaken checksum checks to make a new source pass.

Do not commit credentials, full scenes, private location data, caches, or virtual environments. The small documented historical crops and actual demo outputs are intentional. Use a new output directory for local experiments. No external download is needed for routine tests.

Do not describe index candidates as confirmed flood extent, causal event effects, calibrated probabilities, or measured accuracy without suitable independent evidence. Changes to the viewer must keep the map, measurement table, downloads, threshold labels, keyboard controls, and mobile layout consistent.
