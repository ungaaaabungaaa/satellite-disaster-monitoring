import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from test_http_range import Opener

from satellite_monitoring.acquire import RESOURCE_DIR, acquire, array_digest, load_items
from satellite_monitoring.http_range import RangeSource


def source_bytes(band):
    count = 3 if band == "visual" else 1
    small = band in ["swir16", "scl"]
    size = 4 if small else 8
    resolution = 20 if small else 10
    values = np.full((count, size, size), 200, dtype="uint16")
    if band == "green":
        values[0] = np.arange(64).reshape(8, 8) + 200
    if band == "scl":
        values[0] = 5
    if band == "visual":
        values[:] = np.array([60, 80, 100])[:, None, None]
    with MemoryFile() as file:
        with file.open(
            driver="GTiff",
            width=size,
            height=size,
            count=count,
            dtype="uint16",
            crs="EPSG:32645",
            transform=from_origin(760000, 2810080, resolution, resolution),
            nodata=0,
        ) as dst:
            dst.write(values)
        return file.read()


class AcquisitionIntegrationTests(unittest.TestCase):
    def run_fixture(self, root, corrupt=False):
        resources = root / "resources"
        (resources / "provenance").mkdir(parents=True)
        for side in ["before", "after"]:
            shutil.copyfile(
                RESOURCE_DIR / "provenance" / f"{side}-item.json",
                resources / "provenance" / f"{side}-item.json",
            )
        bands = ["green", "swir16", "scl", "visual"]
        payloads = {band: source_bytes(band) for band in bands}
        expected = np.zeros((6, 4, 4), dtype="float32")
        # RasterIO averages this integer-DN source at source integer precision.
        expected[0] = np.floor(np.arange(64).reshape(4, 2, 4, 2).mean(axis=(1, 3)) + 200.5)
        expected[1] = 200
        expected[2] = 5
        expected[3:] = np.array([60, 80, 100])[:, None, None]
        pins = {
            side: {band: {"size": len(payloads[band]), "etag": '"pinned"'} for band in bands}
            for side in ["before", "after"]
        }
        for side in pins:
            pins[side]["array_sha256"] = "wrong" if corrupt else array_digest(expected)
        (resources / "source-pins.json").write_text(json.dumps(pins))
        items = load_items()
        lookup = {item["assets"][band]["href"]: payloads[band] for item in items for band in bands}

        def transport(url, budget, expected=None):
            return RangeSource(url, budget, expected=expected, opener=Opener(content=lookup[url]))

        with (
            patch("satellite_monitoring.acquire.RESOURCE_DIR", resources),
            patch("satellite_monitoring.acquire.RangeSource", transport),
            patch(
                "rasterio.warp.transform_bounds", return_value=(760000, 2810000, 760080, 2810080)
            ),
        ):
            return acquire(root / "output"), expected

    def test_known_pixels_are_averaged_aligned_and_pinned_before_writing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report, expected = self.run_fixture(root)
            self.assertEqual((report["width"], report["height"]), (4, 4))
            with rasterio.open(root / "output" / "before.tif") as scene:
                np.testing.assert_array_equal(scene.read(), expected)
                self.assertEqual(scene.transform.a, 20)
                self.assertEqual(scene.tags()["reflectance_offset"], "0")
            self.assertLess(report["transferred_range_bytes"], 100000)

    def test_pixel_pin_failure_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaisesRegex(ValueError, "pixels differ"):
                self.run_fixture(root, corrupt=True)
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
