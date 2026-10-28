"""Bounded local six-band GeoTIFF input and explicit alignment to the first grid."""

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import numpy as np

from .analysis import MAX_PIXELS, pixel_area


@dataclass
class Scene:
    data: np.ndarray
    transform: object
    crs: object
    date: datetime
    source_id: str
    scale: float
    offset: float
    sha256: str


def load_scene(path: Path) -> Scene:
    import rasterio

    if path.stat().st_size > 32_000_000:
        raise ValueError("Scene file exceeds the 32 MB bound.")
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", PROJ_NETWORK="OFF"):
        with rasterio.open(path, driver="GTiff") as dataset:
            if (
                dataset.count != 6
                or max(dataset.shape) > 2000
                or dataset.width * dataset.height > MAX_PIXELS
            ):
                raise ValueError("Scene must have six bands and at most two million pixels.")
            if not dataset.crs or not dataset.crs.is_projected:
                raise ValueError(
                    "A projected CRS is required; geographic degrees are not area units."
                )
            if not np.isclose(dataset.crs.linear_units_factor[1], 1.0, rtol=0, atol=1e-12):
                raise ValueError(
                    "Scene inputs require projected metre units; reproject other units explicitly."
                )
            pixel_area(dataset.transform, True, dataset.crs.linear_units_factor[1])
            t = dataset.transform
            if t.b != 0 or t.d != 0 or t.a <= 0 or t.e >= 0 or not np.isfinite(tuple(t)).all():
                raise ValueError("Scene grid must be finite, north-up, and unrotated.")
            tags = dataset.tags()
            try:
                date = datetime.fromisoformat(tags["acquisition_datetime"].replace("Z", "+00:00"))
                scale, offset = float(tags["reflectance_scale"]), float(tags["reflectance_offset"])
                source_id = tags["source_id"]
            except (KeyError, ValueError) as exc:
                raise ValueError(
                    "Scene is missing valid timestamp, source, or reflectance tags."
                ) from exc
            if (
                date.tzinfo is None
                or not 0 < scale <= 1
                or not np.isfinite(offset)
                or abs(offset) > 1
                or not 0 < len(source_id) <= 200
                or dataset.nodata != 0
            ):
                raise ValueError(
                    "Invalid timestamp, scale/offset, source ID, or nodata convention."
                )
            data = dataset.read(out_dtype="float32")
            if not np.isfinite(data[3:]).all() or ((data[3:] < 0) | (data[3:] > 255)).any():
                raise ValueError("Display RGB bands must be finite values from zero to 255.")
            return Scene(
                data,
                t,
                dataset.crs,
                date.astimezone(UTC),
                source_id,
                scale,
                offset,
                sha256(path.read_bytes()).hexdigest(),
            )


def align_scene(scene: Scene, reference: Scene):
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    if (
        scene.crs == reference.crs
        and scene.transform == reference.transform
        and scene.data.shape == reference.data.shape
    ):
        return scene.data, False
    aligned = np.zeros(reference.data.shape, dtype="float32")
    for index in range(6):
        reproject(
            scene.data[index],
            aligned[index],
            src_transform=scene.transform,
            src_crs=scene.crs,
            dst_transform=reference.transform,
            dst_crs=reference.crs,
            src_nodata=0,
            dst_nodata=0,
            resampling=Resampling.average if index < 2 else Resampling.nearest,
            num_threads=1,
            warp_mem_limit=32,
        )
    return aligned, True


def grid_diagnostics(scene: Scene, reference: Scene):
    """Describe validated input grids before resampling, without image matching."""
    same_crs = scene.crs == reference.crs
    report = {
        "same_crs": same_crs,
        "same_grid": same_crs
        and scene.transform == reference.transform
        and scene.data.shape == reference.data.shape,
        "origin_offset_reference_pixels": None,
        "pixel_size_ratio": None,
        "reference_grid_overlap_fraction": None,
        "interpretation": "Geometric grid comparison only; not image coregistration or a cloud-valid overlap measurement. Different CRS requires explicit coordinate transformation, so offsets and overlap are not reported.",
    }
    if not same_crs:
        return report
    source, target = scene.transform, reference.transform
    report["origin_offset_reference_pixels"] = [
        (source.c - target.c) / target.a,
        (source.f - target.f) / target.e,
    ]
    report["pixel_size_ratio"] = [source.a / target.a, source.e / target.e]
    source_height, source_width = scene.data.shape[1:]
    target_height, target_width = reference.data.shape[1:]
    width = max(
        0,
        min(source.c + source_width * source.a, target.c + target_width * target.a)
        - max(source.c, target.c),
    )
    height = max(
        0,
        min(source.f, target.f)
        - max(source.f + source_height * source.e, target.f + target_height * target.e),
    )
    reference_area = target_width * target.a * target_height * -target.e
    report["reference_grid_overlap_fraction"] = min(1.0, width * height / reference_area)
    return report
