"""Regression tests for vectorized analytical Lab conversion."""

import unittest
import warnings
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from utils import scanner_calibration as sc
from utils.color_analyzer import ColorAnalyzer


class TestBatchCalibration(unittest.TestCase):

    def setUp(self):
        rng = np.random.default_rng(20261125)

        self.rgb = np.vstack([
            rng.uniform(0, 255, (2000, 3)),
            rng.integers(0, 65536, (2000, 3))
            * (255.0 / 65535.0),
            np.repeat(
                np.linspace(0, 255, 256)[:, None],
                3, axis=1
            ),
            [[0, 0, 0], [255, 255, 255]]
        ])

        neutral = np.column_stack([
            np.linspace(0, 100, 5),
            np.zeros(5),
            np.zeros(5)
        ])

        chromatic = np.column_stack([
            rng.uniform(15, 85, 15),
            rng.uniform(15, 65, 15),
            rng.uniform(-65, 65, 15)
        ])

        anchors = np.vstack([neutral, chromatic])

        self.calibration = sc.ScannerCalibration()
        self.calibration.is_valid = True
        self.calibration.patch_results = [
            SimpleNamespace(
                scanned_lab=tuple(lab),
                reference_lab=tuple(
                    lab + rng.uniform(-5, 5, 3)
                )
            )
            for lab in anchors
        ]

    def test_calibrated_equivalence(self):
        for variant in (
            "standard",
            "neutral_dominant_c_lt_3",
            "smooth_neutral_1_to_6"
        ):
            with self.subTest(variant=variant):
                self.calibration.correction_variant = variant

                scalar = np.asarray([
                    self.calibration.apply_to_lab(tuple(p))
                    for p in self.rgb
                ])

                batch = self.calibration.apply_to_lab_batch(
                    self.rgb
                )

                np.testing.assert_allclose(
                    scalar, batch, rtol=0, atol=1e-9
                )

                np.testing.assert_allclose(
                    scalar.std(axis=0),
                    batch.std(axis=0),
                    rtol=0, atol=1e-9
                )

    def test_uncalibrated_equivalence(self):
        analyzer = ColorAnalyzer.__new__(ColorAnalyzer)

        with patch.object(sc, "_active_calibration", None):
            scalar = np.asarray([
                analyzer.rgb_to_lab(tuple(p))
                for p in self.rgb
            ])

            batch = analyzer.rgb_to_lab_batch(self.rgb)

        np.testing.assert_allclose(
            scalar, batch, rtol=0, atol=1e-9
        )

    def test_large_batch_without_warnings(self):
        rng = np.random.default_rng(20261125)
        rgb = rng.uniform(0, 255, (196349, 3))

        self.calibration.correction_variant = "standard"

        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            lab = self.calibration.apply_to_lab_batch(rgb)

        self.assertEqual(lab.shape, rgb.shape)
        self.assertTrue(np.isfinite(lab).all())
        self.assertTrue(np.isfinite(lab.std(axis=0)).all())

        scalar = np.asarray([
            self.calibration.apply_to_lab(tuple(p))
            for p in rgb[::997]
        ])

        np.testing.assert_allclose(
            scalar, lab[::997], rtol=0, atol=1e-9
        )


if __name__ == "__main__":
    unittest.main()
