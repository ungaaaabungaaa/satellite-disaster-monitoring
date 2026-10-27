"""Acquire one pinned, small historical Sentinel-2 study; no general remote URL input."""

import json
from datetime import datetime
from hashlib import sha256
from importlib.resources import files
from pathlib import Path

from .http_range import AssetFilesystem, Budget, RangeSource

RESOURCE_DIR = Path(str(files("satellite_monitoring").joinpath("resources")))
ITEM_HASHES = [
    "f8eb37a21a686339ca12667959774482f7347ef2090d5582f2d4acdd76c5ff84",
    "7913e8f83bd8b529eabf6a83bb538c8847abde5048bfd60126fefb10081aa276",
]
AOI_WGS84 = [89.6, 25.25, 89.8, 25.45]
BANDS = ["green", "swir16", "scl", "visual"]


def load_items(directory=None):
    directory = directory or RESOURCE_DIR / "provenance"
    items = []
    for side, expected in zip(["before", "after"], ITEM_HASHES, strict=True):
        payload = (directory / f"{side}-item.json").read_bytes()
        if sha256(payload).hexdigest() != expected:
            raise ValueError("Pinned STAC metadata checksum does not match.")
        item = json.loads(payload)
        if item["properties"]["s2:processing_baseline"] != "02.14":
            raise ValueError("This study requires the original pre-offset processing baseline.")
        for name in ["green", "swir16"]:
            band = item["assets"][name]["raster:bands"][0]
            if band["scale"] != 0.0001 or band["offset"] != 0 or band["nodata"] != 0:
                raise ValueError("Unexpected source reflectance convention.")
        items.append(item)
    dates = [
        datetime.fromisoformat(i["properties"]["datetime"].replace("Z", "+00:00")) for i in items
    ]
    if dates[0] >= dates[1]:
        raise ValueError("Before acquisition must precede after acquisition.")
    return items


def array_digest(array):
    return sha256(str(array.shape).encode() + array.astype("<f4").tobytes()).hexdigest()


def acquire(output: Path):
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.warp import transform_bounds
    from rasterio.windows import Window, from_bounds

    if output.exists():
        raise FileExistsError(f"Choose a new output folder: {output}")
    items = load_items()
    pins = json.loads((RESOURCE_DIR / "source-pins.json").read_text())
    left, bottom, right, top = transform_bounds("EPSG:4326", "EPSG:32645", *AOI_WGS84)
    left, bottom = np.floor(np.array([left, bottom]) / 20) * 20
    right, top = np.ceil(np.array([right, top]) / 20) * 20
    width, height = int(round((right - left) / 20)), int(round((top - bottom) / 20))
    if width * height > 2_000_000 or max(width, height) > 2000:
        raise ValueError("Study crop exceeds the pixel limit.")
    transform = from_origin(left, top, 20, 20)
    budget = Budget()
    scenes, provenance = [], []
    for side, item in zip(["before", "after"], items, strict=True):
        values, sources = [], {}
        for band in BANDS:
            source = RangeSource(item["assets"][band]["href"], budget, expected=pins[side][band])
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_CACHEMAX=32_000_000):
                with rasterio.open(source.url, opener=AssetFilesystem(source)) as dataset:
                    if dataset.crs.to_epsg() != 32645:
                        raise ValueError("Pinned source CRS differs from EPSG:32645.")
                    method = Resampling.average if band == "green" else Resampling.nearest
                    # All pinned assets already use the target CRS. A direct
                    # windowed RasterIO read can use their COG overviews instead
                    # of forcing native-resolution reads through a warper.
                    window = from_bounds(left, bottom, right, top, dataset.transform)
                    params = [window.col_off, window.row_off, window.width, window.height]
                    rounded = [round(value) for value in params]
                    if not np.allclose(params, rounded, rtol=0, atol=1e-6):
                        raise ValueError("Target grid does not align with pinned source pixels.")
                    window = Window(*rounded)
                    if (
                        window.col_off < 0
                        or window.row_off < 0
                        or window.col_off + window.width > dataset.width
                        or window.row_off + window.height > dataset.height
                    ):
                        raise ValueError("Pinned crop falls outside the source grid.")
                    try:
                        array = dataset.read(
                            window=window,
                            out_shape=(dataset.count, height, width),
                            out_dtype="float32",
                            resampling=method,
                        )
                    except rasterio.errors.RasterioIOError:
                        if source.failure is not None:
                            raise OSError(
                                f"Cannot acquire {side} {band}: {source.failure}; "
                                f"{budget.bytes} bytes in {budget.requests} requests"
                            ) from None
                        raise
            if source.failure is not None:
                raise OSError(f"Cannot acquire {side} {band}: {source.failure}")
            if band != "visual" and array.shape[0] != 1:
                raise ValueError("Analytic source must be one band.")
            if band == "visual" and array.shape[0] != 3:
                raise ValueError("Visual source must have three RGB bands.")
            values.extend(array)
            sources[band] = {
                "url": source.url,
                "size": source.size,
                "etag": source.etag,
                "ranges": source.ranges,
            }
        scene = np.stack(values).astype("float32")
        checksum = array_digest(scene)
        if checksum != pins[side]["array_sha256"]:
            raise ValueError("Derived crop pixels differ from the pinned study.")
        scenes.append(scene)
        provenance.append(
            {
                "side": side,
                "id": item["id"],
                "datetime": item["properties"]["datetime"],
                "array_sha256": checksum,
                "sources": sources,
            }
        )
    output.mkdir(parents=True, exist_ok=False)
    for side, item, scene in zip(["before", "after"], items, scenes, strict=True):
        with rasterio.open(
            output / f"{side}.tif",
            "w",
            driver="GTiff",
            count=6,
            width=width,
            height=height,
            dtype="float32",
            crs="EPSG:32645",
            transform=transform,
            nodata=0,
            compress="deflate",
            predictor=3,
            tiled=True,
            blockxsize=256,
            blockysize=256,
        ) as dst:
            dst.write(scene)
            dst.descriptions = (
                "green_dn",
                "swir16_dn",
                "scl",
                "red_display",
                "green_display",
                "blue_display",
            )
            dst.update_tags(
                acquisition_datetime=item["properties"]["datetime"],
                source_id=item["id"],
                reflectance_scale="0.0001",
                reflectance_offset="0",
                attribution="Contains modified Copernicus Sentinel data 2020",
            )
    record = {
        "aoi_wgs84": AOI_WGS84,
        "crs": "EPSG:32645",
        "transform": list(transform)[:6],
        "width": width,
        "height": height,
        "resolution_m": 20,
        "transferred_range_bytes": budget.bytes,
        "http_requests": budget.requests,
        "elapsed_seconds": __import__("time").monotonic() - budget.started,
        "scenes": provenance,
    }
    (output / "acquisition.json").write_text(json.dumps(record, indent=2) + "\n")
    return record
