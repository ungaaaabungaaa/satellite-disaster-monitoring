import json
import shutil
import tempfile
import unittest
from pathlib import Path

from test_scene import fixture

from satellite_monitoring.acquire import RESOURCE_DIR, array_digest
from satellite_monitoring.export import export_study
from satellite_monitoring.scene import load_scene


class ExportTests(unittest.TestCase):
    def test_tag_only_reflectance_tampering_cannot_keep_the_pinned_label(self):
        import rasterio

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            tampered = root / "before.tif"
            original = RESOURCE_DIR / "study" / "before.tif"
            shutil.copyfile(original, tampered)
            with rasterio.open(tampered, "r+") as dst:
                dst.update_tags(reflectance_scale="0.0002", reflectance_offset="0.01")
            self.assertEqual(
                array_digest(load_scene(original).data), array_digest(load_scene(tampered).data)
            )
            result = export_study(tampered, RESOURCE_DIR / "study" / "after.tif", root / "out")
            self.assertEqual(result["study_status"], "custom-unverified")
            self.assertEqual(
                result["effective_reflectance"]["before"], {"scale": 0.0002, "offset": 0.01}
            )

    def test_nonzero_offset_does_not_turn_raw_nodata_into_valid_reflectance(self):
        import rasterio

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a, b = root / "a.tif", root / "b.tif"
            fixture(a)
            fixture(b, date="2020-08-02T04:51:30Z")
            with rasterio.open(a, "r+") as dst:
                band = dst.read(1)
                band[0, 0] = 0
                dst.write(band, 1)
                dst.update_tags(reflectance_offset="0.01")
            result = export_study(a, b, root / "out")
            self.assertEqual(result["thresholds"][1]["common_valid_pixels"], 15)

    def test_complete_local_workflow_and_saved_observation_counts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a, b = root / "a.tif", root / "b.tif"
            fixture(a)
            fixture(b, date="2020-08-02T04:51:30Z")
            result = export_study(a, b, root / "out")
            self.assertEqual(result["thresholds"][1]["common_valid_pixels"], 16)
            self.assertEqual(result["thresholds"][1]["persistent_water_pixels"], 16)
            self.assertEqual(result["thresholds"][1]["gain_km2"], 0)
            self.assertEqual(result["thresholds"][1]["pixel_area_m2"], 400)
            self.assertTrue((root / "out" / "index.html").is_file())
            self.assertEqual(json.loads((root / "out" / "data.json").read_text())["width"], 4)
            ring = json.loads((root / "out" / "footprint.geojson").read_text())["geometry"][
                "coordinates"
            ][0]
            self.assertGreater(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:])), 0)
            with self.assertRaises(FileExistsError):
                export_study(a, b, root / "out")

    def test_threshold_sensitivity_map_uses_only_common_valid_pixels(self):
        import rasterio

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a, b = root / "a.tif", root / "b.tif"
            fixture(a)
            fixture(b, date="2020-08-02T04:51:30Z")
            for path in [a, b]:
                with rasterio.open(path, "r+") as dst:
                    data = dst.read()
                    data[0], data[1] = 8000, 2000
                    data[0, 0, 0], data[1, 0, 0] = 6000, 4000
                    data[2, 0, 1] = 9
                    dst.write(data)
            result = export_study(a, b, root / "out")
            sensitivity = result["threshold_sensitivity"]
            self.assertEqual(sensitivity["thresholds"], [-0.1, 0.0, 0.1, 0.2, 0.3])
            self.assertEqual(sensitivity["common_valid_pixels"], 15)
            self.assertEqual(sensitivity["sensitive_pixels"], 1)
            self.assertEqual(sensitivity["stable_pixels"], 14)
            self.assertEqual(sensitivity["sensitive_km2"], 0.0004)
            self.assertEqual(sensitivity["sensitive_fraction"], 1 / 15)
            with rasterio.open(root / "out" / "threshold-sensitivity.tif") as src:
                classes = src.read(1)
                self.assertEqual(classes[0, 0], 2)
                self.assertEqual(classes[0, 1], 0)
                self.assertEqual((classes == 1).sum(), 14)
                self.assertEqual(src.nodata, 0)
                self.assertEqual(src.crs.to_epsg(), 32645)
                self.assertEqual(src.transform, load_scene(a).transform)
            manifest = json.loads((root / "out" / "data.json").read_text())
            self.assertIn("threshold-sensitivity.tif", manifest["asset_sha256"])

    def test_reversed_acquisition_dates_fail_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a, b = root / "a.tif", root / "b.tif"
            fixture(a, date="2020-08-02T04:51:30Z")
            fixture(b)
            with self.assertRaisesRegex(ValueError, "precede"):
                export_study(a, b, root / "out")
            self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main()
