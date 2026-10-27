import unittest
from pathlib import Path
from unittest.mock import patch

from satellite_monitoring.cli import main


class CliTests(unittest.TestCase):
    def test_download_is_explicit_and_errors_are_controlled(self):
        with patch(
            "satellite_monitoring.cli.acquire", return_value={"transferred_range_bytes": 20}
        ) as acquire:
            self.assertEqual(main(["acquire", "--output", "new-folder"]), 0)
            acquire.assert_called_once_with(Path("new-folder"))
        with patch("satellite_monitoring.cli.export_study", side_effect=ValueError("invalid grid")):
            self.assertEqual(
                main(["analyze", "--before", "a.tif", "--after", "b.tif", "--output", "out"]), 1
            )

    def test_demo_uses_only_bundled_local_inputs(self):
        with patch(
            "satellite_monitoring.cli.export_study",
            return_value={"thresholds": [{}, {"gain_km2": 1.0, "loss_km2": 0.0}]},
        ) as export:
            self.assertEqual(main(["demo", "--output", "out"]), 0)
            self.assertEqual(export.call_args.args[-1], Path("out"))


if __name__ == "__main__":
    unittest.main()
