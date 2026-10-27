import unittest

import numpy as np

from satellite_monitoring.analysis import analyze_arrays, pixel_area


class AnalysisTests(unittest.TestCase):
    def test_gain_loss_and_persistence_use_only_common_valid_pixels(self):
        before_green = np.array([[3.0, 1.0, 3.0], [1.0, 3.0, 3.0]])
        after_green = np.array([[3.0, 3.0, 1.0], [1.0, 3.0, 3.0]])
        swir = np.full((2, 3), 2.0)
        before_scl = np.full((2, 3), 5)
        after_scl = np.array([[5, 6, 5], [5, 9, 0]])
        result, classes, _, _ = analyze_arrays(
            before_green, swir, before_scl, after_green, swir, after_scl, 400.0, 0.0
        )
        self.assertEqual(result["common_valid_pixels"], 4)
        self.assertEqual(result["gain_pixels"], 1)
        self.assertEqual(result["loss_pixels"], 1)
        self.assertEqual(result["persistent_water_pixels"], 1)
        self.assertEqual(result["stable_land_pixels"], 1)
        self.assertEqual(result["gain_km2"], 0.0004)
        np.testing.assert_array_equal(classes, [[2, 3, 4], [1, 0, 0]])

    def test_zero_negative_nodata_and_unclassified_are_excluded(self):
        green = np.array([[0.0, -1.0, np.nan, 2.0, 2.0, 2.0]])
        swir = np.array([[1.0, 2.0, 2.0, 0.0, 2.0, 2.0]])
        scl = np.array([[5, 5, 5, 5, 7, 6]])
        result, _, _, _ = analyze_arrays(green, swir, scl, green, swir, scl, 400.0, 0)
        self.assertEqual(result["common_valid_pixels"], 1)
        self.assertEqual(result["before_water_pixels"], 0)  # exact MNDWI zero is not > zero

    def test_no_common_data_and_invalid_bounds_fail_clearly(self):
        g, s, q = np.ones((2, 2)), np.ones((2, 2)), np.zeros((2, 2))
        for area, threshold in [(0, 0), (400, np.nan), (400, 2)]:
            with self.assertRaises(ValueError):
                analyze_arrays(g, s, q, g, s, q, area, threshold)
        with self.assertRaisesRegex(ValueError, "common"):
            analyze_arrays(g, s, q, g, s, q, 400, 0)
        with self.assertRaises(ValueError):
            analyze_arrays(g, s[:, :1], q, g, s, q, 400, 0)

    def test_projected_pixel_area_uses_affine_determinant_and_unit_factor(self):
        self.assertEqual(pixel_area((20, 0, 0, 0, -20, 0), True, 1), 400)
        self.assertEqual(pixel_area((20, 2, 0, 1, -20, 0), True, 1), 402)
        with self.assertRaisesRegex(ValueError, "projected"):
            pixel_area((0.001, 0, 89, 0, -0.001, 25), False, 1)
        with self.assertRaises(ValueError):
            pixel_area((20, 0, 0, 0, 0, 0), True, 1)


if __name__ == "__main__":
    unittest.main()
