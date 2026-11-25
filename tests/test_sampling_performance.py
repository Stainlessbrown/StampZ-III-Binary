"""Regression tests for full and lightweight native sampling."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from utils.self_contained_tiff import write_self_contained_tiff
from utils.portable_alignment_adapter import load_portable_aligned_image
from utils.color_analyzer import ColorAnalyzer
from utils.coordinate_db import SampleAreaType
from utils.delta_e_00 import delta_e_00
from utils import scanner_calibration as sc


class TestSamplingPerformance(unittest.TestCase):

    def test_native_sampling_equivalence(self):
        rng = np.random.default_rng(20261125)

        native = rng.integers(
            0, 65536, (18, 20, 3), dtype=np.uint16
        )
        aligned = rng.integers(
            0, 65536, (9, 12, 3), dtype=np.uint16
        )
        preview = (native // 257).astype(np.uint8)

        geometry = {
            "transform_matrix": [[0.6, 0, 0], [0, 0.5, 0]],
            "crop_box": [0, 0, 20, 18],
        }

        # Avoid opening or modifying the coordinate database.
        analyzer = ColorAnalyzer.__new__(ColorAnalyzer)

        class TestCalibration:
            is_valid = True

            def apply_to_lab(self, rgb):
                rgb01 = np.asarray(rgb).reshape(1, 3) / 255.0
                lab = sc.srgb_to_lab(rgb01)[0]
                return tuple(lab + [0.5, -0.25, 0.75])

        with TemporaryDirectory() as folder:
            for encoding in ("srgb", "linear"):
                path = Path(folder) / f"{encoding}.tif"

                write_self_contained_tiff(
                    path,
                    aligned_display=aligned,
                    native_source=native,
                    source_preview=preview,
                    geometry=geometry,
                    analytical_encoding=encoding,
                    aligned_display_encoding="linear",
                    source_display_encoding="linear",
                    raw_derived=True,
                    source_identity={
                        "original_file": "synthetic.CR3",
                        "source_sha256": "0" * 64,
                    },
                )

                image, metadata = load_portable_aligned_image(path)
                self.assertTrue(metadata["alignment_authenticated"])

                for calibration in (None, TestCalibration()):
                    for shape in (
                        SampleAreaType.CIRCLE,
                        SampleAreaType.RECTANGLE,
                    ):
                        with self.subTest(
                            encoding=encoding,
                            calibrated=calibration is not None,
                            shape=shape,
                        ):
                            coord = SimpleNamespace(
                                x=6,
                                y=4,
                                sample_type=shape,
                                sample_size=(4, 4),
                                anchor_position="center",
                            )

                            with patch.object(
                                sc, "_active_calibration", calibration
                            ):
                                with patch.object(
                                    analyzer,
                                    "rgb_to_lab_batch",
                                    wraps=analyzer.rgb_to_lab_batch,
                                ) as conversion:

                                    full = analyzer._sample_area_color(
                                        image, coord
                                    )

                                    self.assertGreater(
                                        conversion.call_count, 0
                                    )
                                    self.assertIsNotNone(full[1])
                                    self.assertIsNotNone(full[2])
                                    self.assertTrue(
                                        np.isfinite(full[1]).all()
                                    )
                                    self.assertTrue(
                                        np.isfinite(full[2]).all()
                                    )

                                    conversion.reset_mock()

                                    live = analyzer._sample_area_color(
                                        image,
                                        coord,
                                        compute_stddev=False,
                                    )

                                    conversion.assert_not_called()

                                self.assertEqual(full[0], live[0])
                                self.assertIsNone(live[1])
                                self.assertIsNone(live[2])

                                full_lab = analyzer.rgb_to_lab(full[0][0])
                                live_lab = analyzer.rgb_to_lab(live[0][0])

                                self.assertEqual(full_lab, live_lab)
                                self.assertAlmostEqual(
                                    delta_e_00(full_lab, live_lab),
                                    0.0,
                                    places=12,
                                )

                                self.assertEqual(
                                    analyzer.last_sampling_bit_depth, 16
                                )
                                self.assertEqual(
                                    analyzer.last_sampling_channels, 3
                                )


if __name__ == "__main__":
    unittest.main()
