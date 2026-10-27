# Data, source pins, and rights

The default study is a fixed historical pair around the Jamuna River, Bangladesh. The requested WGS84 box is `[89.6, 25.25, 89.8, 25.45]` (west, south, east, north). Projecting and rounding outward to a 20 m grid gives EPSG:32645, width 1031, height 1129, and affine `[20, 0, 761440, 0, -20, 2817740]`. Each pixel covers 400 m². The exported GeoJSON describes the actual grid footprint in WGS84.

| Side | Earth Search item ID | Exact acquisition UTC |
| --- | --- | --- |
| Before | S2B_45RYJ_20200214_0_L2A | 2020-02-14T04:51:23.495000Z |
| After | S2B_45RYJ_20200802_0_L2A | 2020-08-02T04:51:30.972000Z |

Both are original Sentinel-2B Level-2A, tile 45RYJ, processing baseline 02.14. The pinned STAC band metadata declares scale 0.0001, offset 0, and nodata 0 for both green and SWIR. These pre-offset products avoid the legacy post-2022 scale/offset inconsistencies discussed by the catalog maintainer in [Earth Search issue 71](https://github.com/Element84/earth-search/issues/71) and [issue 66](https://github.com/Element84/earth-search/issues/66). The code verifies this convention instead of guessing from pixel magnitudes.

Official access points are the [Earth Search Sentinel-2 Level-2A collection](https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a) and [AWS dataset registry](https://registry.opendata.aws/sentinel-2-l2a-cogs/). Bundled `resources/provenance/before-item.json` and `after-item.json` retain the original catalog metadata, full asset URLs, CRS, transforms, nodata, quality information, and processing metadata. Their exact bytes are pinned in code:

| File | SHA256 |
| --- | --- |
| before-item.json | f8eb37a21a686339ca12667959774482f7347ef2090d5582f2d4acdd76c5ff84 |
| after-item.json | 7913e8f83bd8b529eabf6a83bb538c8847abde5048bfd60126fefb10081aa276 |
| study/before.tif | 5de252b7ce82a505c2cf12df2d6483f7504c5e16447f65a99182912a908e2603 |
| study/after.tif | a7696ca1574d519833f06015462000d2730c98b8eb0e68dc29379f5b53313db8 |

The canonical pixel-array hashes also include the array shape and little-endian float32 values, independent of TIFF compression:

- Before: `c7545644efb2f0c263811225b06c90a8b2cd523d48127f7f0b0b98e9bce6d2b7`.
- After: `d62fc9ef77f0023afd6e466baf1da673722600631923783f543df7c2e9e8a4c5`.

`resources/source-pins.json` records every allowed source-object size and ETag, these array hashes, and the grid. Acquisition uses bounded HTTP range reads from the fixed public S3 host. Each requested range, response byte count, and SHA256 is recorded in `resources/study/acquisition.json`. No full-scene hash is claimed: the entire objects were not downloaded. The final fresh verification read 27,000,832 bytes in 77 requests and took 322.596 seconds; a previous run was faster. The derived TIFF bytes matched the recorded checksums exactly.

The six output bands are green DN, SWIR DN, SCL, and three real display RGB bands. Acquisition reads aligned windows using COG overviews where available. Green is reduced to 20 m with RasterIO average resampling; SWIR, SCL, and RGB use nearest. RasterIO's integer-source averaging rounds the DN result at source precision before float32 output (a controlled 204.5-DN fixture returns 205). Therefore this is a pinned GDAL-processing result, not a claim of exact sub-DN averaging. The recorded dependency set and derived-array checksums make that convention explicit; changed processing must not silently replace the study.

**Contains modified Copernicus Sentinel data 2020.** The [Sentinel legal notice](https://cds.climate.copernicus.eu/licences/ec-sentinel) permits reuse and adaptation under its terms. Keep attribution and distinguish code licensing from data licensing. See [NOTICE.md](../NOTICE.md). Source data and classification have no guarantee of accuracy or fitness for an operational use.
