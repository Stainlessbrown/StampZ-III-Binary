"""Run with: python3 -m unittest -v test_self_contained_tiff.py"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import tifffile

from self_contained_tiff import (
    PortableTiffError, read_self_contained_tiff,
    write_self_contained_tiff, verify_self_contained_tiff,
)


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'aligned.tif'
        rng = np.random.default_rng(20261113)
        self.aligned = rng.integers(0, 65536, (9, 12, 3), dtype=np.uint16)
        self.native = rng.integers(0, 65536, (18, 20, 3), dtype=np.uint16)
        self.preview = rng.integers(0, 256, (18, 20, 3), dtype=np.uint8)
        self.geometry = {
            'transform_matrix': [[0.6, 0, 0], [0, 0.5, 0]],
            'crop_box': [0, 0, 20, 18],
        }

    def write(self, **kwargs):
        return write_self_contained_tiff(
            self.path, aligned_display=self.aligned, native_source=self.native,
            source_preview=self.preview, geometry=self.geometry,
            analytical_encoding='srgb', aligned_display_encoding='linear',
            source_display_encoding='linear', raw_derived=True,
            source_identity={'original_file': 'IMG_0017.CR3', 'source_sha256': '0' * 64},
            **kwargs,
        )

    def test_round_trip_and_no_external_files(self):
        self.write()
        aligned, native, preview, manifest = read_self_contained_tiff(self.path)
        np.testing.assert_array_equal(self.aligned, aligned)
        np.testing.assert_array_equal(self.native, native)
        np.testing.assert_array_equal(self.preview, preview)
        self.assertEqual(manifest['encoding']['analytical'], 'srgb')
        self.assertEqual(manifest['encoding']['aligned_display'], 'linear')
        self.assertTrue(manifest['raw_derived'])

    def test_no_accidental_overwrite(self):
        self.write()
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.write()
        self.assertEqual(before, self.path.read_bytes())

    def test_reject_invalid_geometry_without_publishing(self):
        self.geometry['crop_box'] = [0, 0, 99, 18]
        with self.assertRaises(PortableTiffError):
            self.write()
        self.assertFalse(self.path.exists())

    def test_reject_page_pixel_change(self):
        self.write()
        # Construct an altered TIFF with the same manifest but modified payload.
        with tifffile.TiffFile(self.path) as tif:
            manifest_json = tif.pages[0].description
            pages = [page.asarray() for page in tif.pages]
        pages[1][0, 0, 0] ^= 1
        damaged = self.path.with_name('damaged.tif')
        with tifffile.TiffWriter(damaged) as writer:
            for idx, pixels in enumerate(pages):
                writer.write(pixels, photometric='rgb', metadata=None,
                             description=manifest_json if idx == 0 else None)
        with self.assertRaisesRegex(PortableTiffError, 'pixel checksum mismatch'):
            verify_self_contained_tiff(damaged)


    def test_rgba_and_8bit_source(self):
        self.aligned = np.zeros((9, 12, 4), dtype=np.uint8)
        self.native = np.zeros((18, 20, 4), dtype=np.uint8)
        self.preview = np.zeros((18, 20, 4), dtype=np.uint8)
        self.aligned[:, :, 3] = 255
        self.native[:, :, 3] = 255
        self.preview[:, :, 3] = 255
        self.write()
        aligned, native, preview, _ = read_self_contained_tiff(self.path)
        np.testing.assert_array_equal(self.aligned, aligned)
        np.testing.assert_array_equal(self.native, native)
        np.testing.assert_array_equal(self.preview, preview)

    def test_reject_missing_encoding(self):
        self.write()
        with tifffile.TiffFile(self.path) as tif:
            manifest = json.loads(tif.pages[0].description)
            pages = [page.asarray() for page in tif.pages]
        manifest['encoding'].pop('analytical')
        damaged = self.path.with_name('bad_encoding.tif')
        with tifffile.TiffWriter(damaged) as writer:
            for idx, pixels in enumerate(pages):
                writer.write(pixels, photometric='rgb', metadata=None,
                             description=json.dumps(manifest) if idx == 0 else None)
        with self.assertRaisesRegex(PortableTiffError, 'manifest: checksum mismatch'):
            verify_self_contained_tiff(damaged)

    def test_no_output_on_bad_encoding(self):
        with self.assertRaisesRegex(PortableTiffError, 'encoding'):
            write_self_contained_tiff(
                self.path, aligned_display=self.aligned, native_source=self.native,
                source_preview=self.preview, geometry=self.geometry,
                analytical_encoding='unknown', aligned_display_encoding='linear',
                source_display_encoding='linear', raw_derived=True,
            )
        self.assertFalse(self.path.exists())


if __name__ == '__main__':
    unittest.main()
