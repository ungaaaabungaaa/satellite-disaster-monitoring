import json
import tempfile
import unittest
from pathlib import Path

from satellite_monitoring.acquire import load_items


class AcquireTests(unittest.TestCase):
    def test_fixed_historical_items_have_verified_scaling_and_dates(self):
        items = load_items()
        self.assertEqual(
            [i["id"] for i in items], ["S2B_45RYJ_20200214_0_L2A", "S2B_45RYJ_20200802_0_L2A"]
        )
        self.assertTrue(all(i["properties"]["s2:processing_baseline"] == "02.14" for i in items))
        self.assertEqual(items[0]["assets"]["green"]["raster:bands"][0]["offset"], 0)

    def test_changed_catalog_metadata_fails_closed_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            (path / "before-item.json").write_text(
                json.dumps({"assets": {"green": {"href": "http://private"}}})
            )
            with self.assertRaisesRegex(ValueError, "checksum"):
                load_items(path)


if __name__ == "__main__":
    unittest.main()
