import tempfile
import unittest
from pathlib import Path

import numpy as np

from satellite_monitoring.scene import align_scene, load_scene


def fixture(path, transform=None, crs="EPSG:32645", date="2020-02-14T04:51:23Z"):
    import rasterio
    from rasterio.transform import from_origin

    values = np.full((6, 4, 4), 120.0, dtype="float32")
    values[0], values[1], values[2] = 300.0, 200.0, 5
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        count=6,
        width=4,
        height=4,
        dtype="float32",
        crs=crs,
        transform=transform or from_origin(760000, 2810000, 20, 20),
        nodata=0,
    ) as dst:
        dst.write(values)
        dst.update_tags(
            acquisition_datetime=date,
            source_id="synthetic-test",
            reflectance_scale="0.0001",
            reflectance_offset="0",
        )


class SceneTests(unittest.TestCase):
    def test_loader_retains_crs_scale_time_and_pixels(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "scene.tif"
            fixture(path)
            scene = load_scene(path)
            self.assertEqual(scene.crs.to_epsg(), 32645)
            self.assertEqual(scene.scale, 0.0001)
            self.assertEqual(scene.data.shape, (6, 4, 4))
            self.assertEqual(align_scene(scene, scene)[1], False)

    def test_alignment_marks_nonoverlap_as_nodata(self):
        from rasterio.transform import from_origin

        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.tif", Path(d) / "b.tif"
            fixture(a)
            fixture(b, transform=from_origin(760020, 2810000, 20, 20), date="2020-08-02T04:51:30Z")
            aligned, changed = align_scene(load_scene(b), load_scene(a))
            self.assertTrue(changed)
            self.assertTrue((aligned[:, :, 0] == 0).all())
            self.assertTrue((aligned[2, :, 1:] == 5).all())

    def test_geographic_area_and_naive_time_are_rejected(self):
        from rasterio.transform import from_origin

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.tif"
            fixture(path, crs="EPSG:4326", transform=from_origin(89, 25, 0.001, 0.001))
            with self.assertRaisesRegex(ValueError, "projected"):
                load_scene(path)
            fixture(path, date="2020-02-14T04:51:23")
            with self.assertRaises(ValueError):
                load_scene(path)
            fixture(path, crs="EPSG:2263")
            with self.assertRaisesRegex(ValueError, "metre"):
                load_scene(path)


if __name__ == "__main__":
    unittest.main()
