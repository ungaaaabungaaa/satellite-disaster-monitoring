"""Two-date MNDWI candidates, measured only on their common clear footprint."""

import numpy as np

MAX_PIXELS = 2_000_000


def pixel_area(transform, projected, meters_per_unit):
    if not projected or not np.isfinite(meters_per_unit) or meters_per_unit <= 0:
        raise ValueError("Area requires a projected CRS with known linear units.")
    a, b, _, d, e, _ = transform[:6]
    area = abs(a * e - b * d) * meters_per_unit**2
    if not np.isfinite(area) or not 0 < area <= 1_000_000:
        raise ValueError("Pixel area is zero, nonfinite, or above the 1 km² bound.")
    return area


def water_index(green, swir, scl):
    valid = (
        np.isfinite(green) & np.isfinite(swir) & (green > 0) & (swir > 0) & np.isin(scl, [4, 5, 6])
    )
    denominator = green + swir
    valid &= np.isfinite(denominator) & (denominator > 1e-8)
    result = np.full(green.shape, np.nan, dtype=np.float32)
    np.divide(green - swir, denominator, out=result, where=valid)
    valid &= np.isfinite(result) & (np.abs(result) <= 1)
    result[~valid] = np.nan
    return result, valid


def analyze_arrays(
    before_green,
    before_swir,
    before_scl,
    after_green,
    after_swir,
    after_scl,
    area_m2,
    threshold=0.0,
):
    arrays = [before_green, before_swir, before_scl, after_green, after_swir, after_scl]
    shape = arrays[0].shape
    if (
        len(shape) != 2
        or min(shape) < 1
        or max(shape) > 2000
        or np.prod(shape) > MAX_PIXELS
        or any(a.shape != shape for a in arrays)
    ):
        raise ValueError("Aligned inputs must be nonempty 2D arrays within pixel/dimension bounds.")
    if not np.isfinite(threshold) or not -1 <= threshold <= 1:
        raise ValueError("MNDWI threshold must be finite and between -1 and 1.")
    if not np.isfinite(area_m2) or not 0 < area_m2 <= 1_000_000:
        raise ValueError("Pixel area must be positive and at most 1 km².")
    for scl in [before_scl, after_scl]:
        if not np.isfinite(scl).all() or ((scl < 0) | (scl > 11) | (scl != np.floor(scl))).any():
            raise ValueError("SCL values must be integer classes 0 through 11.")
    before, before_valid = water_index(before_green, before_swir, before_scl)
    after, after_valid = water_index(after_green, after_swir, after_scl)
    common = before_valid & after_valid
    valid_count = int(common.sum())
    if not valid_count:
        raise ValueError("No common valid pixels remain after both-date quality masking.")
    old_water, new_water = (before > threshold) & common, (after > threshold) & common
    classes = np.zeros(shape, dtype=np.uint8)
    classes[common] = 1
    classes[old_water & new_water] = 2
    classes[~old_water & new_water] = 3
    classes[old_water & ~new_water] = 4
    result = {
        "threshold": float(threshold),
        "pixel_area_m2": float(area_m2),
        "total_pixels": int(np.prod(shape)),
        "before_clear_pixels": int(before_valid.sum()),
        "after_clear_pixels": int(after_valid.sum()),
        "common_valid_pixels": valid_count,
        "excluded_pixels": int(np.prod(shape)) - valid_count,
        "common_valid_fraction": valid_count / int(np.prod(shape)),
        "before_water_pixels": int(old_water.sum()),
        "after_water_pixels": int(new_water.sum()),
        "stable_land_pixels": int((classes == 1).sum()),
        "persistent_water_pixels": int((classes == 2).sum()),
        "gain_pixels": int((classes == 3).sum()),
        "loss_pixels": int((classes == 4).sum()),
    }
    for key in [
        "total",
        "common_valid",
        "excluded",
        "before_water",
        "after_water",
        "stable_land",
        "persistent_water",
        "gain",
        "loss",
    ]:
        result[key + "_km2"] = result[key + "_pixels"] * area_m2 / 1_000_000
    result["net_candidate_water_change_km2"] = result["gain_km2"] - result["loss_km2"]
    return result, classes, before, after
