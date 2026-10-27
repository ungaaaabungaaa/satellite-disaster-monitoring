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
