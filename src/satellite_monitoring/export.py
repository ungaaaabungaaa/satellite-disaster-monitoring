"""Export reproducible measurements, georeferenced classifications, and a local viewer."""

import gzip
import json
import shutil
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

import numpy as np
from PIL import Image

from . import __version__
from .acquire import RESOURCE_DIR, array_digest, load_items
from .analysis import analyze_arrays, pixel_area
from .scene import align_scene, load_scene

THRESHOLDS = [-0.1, 0.0, 0.1, 0.2, 0.3]


def reflectance(raw, scale, offset):
    # Nodata is a raw-DN property; a nonzero offset must not make it valid.
    return np.where(raw != 0, raw * scale + offset, np.nan).astype("float32")


def export_study(before_path: Path, after_path: Path, output: Path):
    import rasterio
    from rasterio.warp import transform as convert_coordinates

    if output.exists():
        raise FileExistsError(f"Choose a new output folder: {output}")
    before, after = load_scene(before_path), load_scene(after_path)
    if before.date >= after.date:
        raise ValueError("Before acquisition must precede after acquisition.")
    aligned, changed = align_scene(after, before)
    area = pixel_area(before.transform, True, before.crs.linear_units_factor[1])
    args = [
        reflectance(before.data[0], before.scale, before.offset),
        reflectance(before.data[1], before.scale, before.offset),
        before.data[2],
        reflectance(aligned[0], after.scale, after.offset),
        reflectance(aligned[1], after.scale, after.offset),
        aligned[2],
    ]
    results = []
    for threshold in THRESHOLDS:
        result, classes, old_index, new_index = analyze_arrays(*args, area, threshold)
        results.append(result)
        if threshold == 0:
            default_classes = classes
    h, w = old_index.shape
    pins_path = RESOURCE_DIR / "source-pins.json"
    pins = json.loads(pins_path.read_text()) if pins_path.exists() else {}
    # Verify pixel values, both grids, timestamps and identities before using the
    # pinned-study label. Correctly formatted custom inputs remain unverified.
    pinned = "grid" in pins and all(
        array_digest(scene.data) == pins.get(side, {}).get("array_sha256")
        and scene.source_id == item["id"]
        and scene.date == datetime.fromisoformat(item["properties"]["datetime"])
        and scene.scale == item["assets"]["green"]["raster:bands"][0]["scale"]
        and scene.offset == item["assets"]["green"]["raster:bands"][0]["offset"]
        and scene.crs.to_epsg() == 32645
        and list(scene.transform)[:6] == pins["grid"]["transform"]
        and scene.data.shape[1:] == (pins["grid"]["height"], pins["grid"]["width"])
        for side, scene, item in zip(
            ["before", "after"], [before, after], load_items(), strict=True
        )
    )
    positions = [(0, 0), (0, h), (w, h), (w, 0), (0, 0)]
    t = before.transform
    projected = [(t.a * x + t.b * y + t.c, t.d * x + t.e * y + t.f) for x, y in positions]
    lon, lat = convert_coordinates(
        before.crs, "EPSG:4326", [p[0] for p in projected], [p[1] for p in projected]
    )
    if not np.isfinite(lon + lat).all():
        raise ValueError("Grid does not transform to finite geographic coordinates.")
    footprint = {
        "type": "Feature",
        "properties": {"crs_of_source_grid": before.crs.to_string()},
        "geometry": {
            "type": "Polygon",
            "coordinates": [list(map(list, zip(lon, lat, strict=True)))],
        },
    }
    modules = sorted(Path(__file__).parent.glob("*.py"))
    metrics = {
        "schema_version": 1,
        "created_utc": datetime.now(UTC).isoformat(),
        "package_version": __version__,
        "dependency_versions": {name: version(name) for name in ["numpy", "rasterio", "pillow"]},
        "gdal_version": rasterio.__gdal_version__,
        "source_sha256": sha256(
            b"".join(p.name.encode() + p.read_bytes() for p in modules)
        ).hexdigest(),
        "study_status": "pinned-historical-study" if pinned else "custom-unverified",
        "input_sha256": {"before": before.sha256, "after": after.sha256},
        "source_ids": [before.source_id, after.source_id],
        "acquisition_utc": [before.date.isoformat(), after.date.isoformat()],
        "crs": before.crs.to_string(),
        "transform": list(before.transform)[:6],
        "width": w,
        "height": h,
        "after_aligned_to_before": changed,
        "effective_reflectance": {
            side: {"scale": scene.scale, "offset": scene.offset}
            for side, scene in [("before", before), ("after", after)]
        },
        "quality_rule": "Both dates: finite positive optical reflectance and SCL4/5/6 only",
        "thresholds": results,
        "interpretation": "Candidate water change on the common valid footprint; no flood ground truth.",
    }
    output.mkdir(parents=True, exist_ok=False)
    for side, scene, index in [("before", before.data, old_index), ("after", aligned, new_index)]:
        rgb = np.moveaxis(np.clip(scene[3:], 0, 255).astype("uint8"), 0, -1)
        Image.fromarray(rgb).save(output / f"{side}.png")
        with (output / f"{side}.f32.gz").open("wb") as stream:
            with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
                compressed.write(index.astype("<f4").tobytes())
    with rasterio.open(
        output / "change.tif",
        "w",
        driver="GTiff",
        width=w,
        height=h,
        count=1,
        dtype="uint8",
        crs=before.crs,
        transform=before.transform,
        nodata=0,
        compress="deflate",
    ) as dst:
        dst.write(default_classes, 1)
        dst.update_tags(
            threshold="0", classes="0 excluded;1 stable land;2 persistent water;3 gain;4 loss"
        )
    palette = np.array(
        [[224, 227, 225], [226, 223, 212], [57, 94, 118], [28, 160, 168], [189, 124, 61]],
        dtype="uint8",
    )
    Image.fromarray(palette[default_classes]).save(output / "change.png")
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n")
    (output / "footprint.geojson").write_text(
        json.dumps(footprint, indent=2, allow_nan=False) + "\n"
    )
    manifest = {
        key: metrics[key]
        for key in [
            "schema_version",
            "study_status",
            "source_ids",
            "acquisition_utc",
            "crs",
            "transform",
            "width",
            "height",
            "thresholds",
            "effective_reflectance",
        ]
    }
    manifest["asset_sha256"] = {
        p.name: sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()
    }
    (output / "data.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    for name in ["index.html", "style.css", "app.js", "classification.mjs"]:
        shutil.copyfile(RESOURCE_DIR / "viewer" / name, output / name)
    return metrics
