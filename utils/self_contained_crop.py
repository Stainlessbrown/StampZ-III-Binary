"""StampZ self-contained derived crop TIFF, version 1.

Page 0 is authoritative native RGB16 + straight alpha16, page 1 is the
8-bit display preview.  Paths in the manifest are descriptive only.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import tifffile
from PIL import Image

SCHEMA = 'stampz.self_contained_crop_tiff'
VERSION = 1
SOFTWARE = 'StampZ-Crop-TIFF-v1'

class CropTiffError(ValueError):
    pass

def _hash(array):
    array = np.ascontiguousarray(array)
    if array.dtype == np.uint16:
        array = np.ascontiguousarray(array.astype('<u2', copy=False))
    return hashlib.sha256(memoryview(array).cast('B')).hexdigest()

def _digest(manifest):
    data = {k: v for k, v in manifest.items() if k != 'manifest_sha256'}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode('ascii')).hexdigest()

def is_self_contained_crop(path):
    path = Path(path)
    if path.suffix.lower() not in ('.tif', '.tiff'):
        return False
    try:
        with tifffile.TiffFile(path) as tif:
            if not tif.pages:
                return False
            software = tif.pages[0].tags.get(305)
            if software is not None and str(software.value) == SOFTWARE:
                return True
            return SCHEMA in (tif.pages[0].description or '')
    except (OSError, ValueError, tifffile.TiffFileError):
        return False

def read_self_contained_crop(path, *, display_only=True):
    try:
        with tifffile.TiffFile(path) as tif:
            if len(tif.pages) != 2:
                raise CropTiffError('Expected exactly two TIFF pages')
            manifest = json.loads(tif.pages[0].description or '')
            if not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA or manifest.get('version') != VERSION:
                raise CropTiffError('Unknown crop schema/version')
            if manifest.get('manifest_sha256') != _digest(manifest):
                raise CropTiffError('Manifest integrity failure')
            pixels = tif.pages[0].asarray()
            preview = tif.pages[1].asarray()
            if pixels.dtype != np.uint16 or pixels.ndim != 3 or pixels.shape[2] != 4:
                raise CropTiffError('Native pixels must be RGBA16')
            if preview.dtype != np.uint8 or preview.shape != pixels.shape:
                raise CropTiffError('Preview must be same-sized RGBA8')
            for key, arr in (('native', pixels), ('preview', preview)):
                entry = manifest.get('pages', {}).get(key, {})
                if entry.get('sha256') != _hash(arr) or entry.get('shape') != list(arr.shape):
                    raise CropTiffError(f'{key} pixel integrity failure')
            if manifest.get('encoding') not in ('linear', 'srgb') or type(manifest.get('raw_derived')) is not bool:
                raise CropTiffError('Missing analytical encoding or RAW provenance')
            if manifest.get('display_encoding') not in ('linear', 'srgb'):
                raise CropTiffError('Missing display encoding')
            geom = manifest.get('crop_geometry', {})
            box = geom.get('bbox')
            original_size = geom.get('parent_size')
            if not isinstance(box, list) or len(box) != 4 or any(type(i) is not int for i in box):
                raise CropTiffError('Missing crop bounding box')
            if not isinstance(original_size, list) or len(original_size) != 2 or any(type(i) is not int or i <= 0 for i in original_size):
                raise CropTiffError('Missing parent dimensions')
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= original_size[0] and 0 <= y0 < y1 <= original_size[1]):
                raise CropTiffError('Invalid crop bounding box')
            if (x1-x0, y1-y0) != (pixels.shape[1], pixels.shape[0]):
                raise CropTiffError('Crop dimensions mismatch')
            if manifest.get('alpha') != 'straight-uint16':
                raise CropTiffError('Unsupported alpha representation')
            pixels = pixels.copy()
            preview = preview.copy()
        image = Image.fromarray(preview, 'RGBA')
        rgb = pixels[:, :, :3].copy()
        if not display_only and manifest['encoding'] == 'linear':
            from utils.image_processor import _apply_srgb_gamma_16bit
            rgb = _apply_srgb_gamma_16bit(rgb)
            analytic_encoding = 'srgb'
        else:
            analytic_encoding = manifest['encoding']
        image._stampz_16bit_data = rgb
        image._stampz_alpha_mask = np.round(pixels[:, :, 3].astype(np.float64) / 257.0).astype(np.uint8)
        image._stampz_16bit_encoding = analytic_encoding
        image._stampz_display_encoding = manifest['display_encoding']
        image._stampz_is_raw = manifest['raw_derived']
        image._stampz_crop_record = manifest['crop_geometry']
        image._stampz_authenticated_crop = True
        identity = manifest.get('source_identity', {})
        image._stampz_source_file = identity.get('parent_file', '')
        metadata = dict(format_info='Authenticated StampZ self-contained crop TIFF v1',
                        precision_preserved=True, original_bit_depth=16,
                        samples_per_pixel=4, is_raw=manifest['raw_derived'],
                        crop_authenticated=True)
        return image, metadata
    except CropTiffError:
        raise
    except Exception as exc:
        raise CropTiffError(f'Crop authentication failed: {exc}') from exc

def write_self_contained_crop(destination, image, *, overwrite=False):
    destination = Path(destination)
    if destination.suffix.lower() not in ('.tif', '.tiff'):
        raise CropTiffError('Crop output must be TIFF')
    if destination.exists() and not overwrite:
        raise FileExistsError(str(destination))
    rgb = getattr(image, '_stampz_16bit_data', None)
    alpha = getattr(image, '_stampz_alpha_mask', None)
    geometry = getattr(image, '_stampz_crop_record', None)
    encoding = getattr(image, '_stampz_16bit_encoding', None)
    display_encoding = getattr(image, '_stampz_display_encoding', encoding)
    raw = getattr(image, '_stampz_is_raw', None)
    if not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint16 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise CropTiffError('Crop must contain native RGB16 pixels')
    if not isinstance(alpha, np.ndarray) or alpha.dtype != np.uint8 or alpha.shape != rgb.shape[:2]:
        raise CropTiffError('Crop must contain native mask')
    if image.mode != 'RGBA' or image.size != (rgb.shape[1], rgb.shape[0]):
        raise CropTiffError('Invalid cropped display preview')
    if encoding not in ('linear', 'srgb') or display_encoding not in ('linear', 'srgb') or type(raw) is not bool:
        raise CropTiffError('Unknown analytical/display encoding or RAW provenance')
    if not isinstance(geometry, dict):
        raise CropTiffError('Crop geometry missing')
    native = np.dstack([rgb, alpha.astype(np.uint16)*257])
    preview = np.asarray(image).copy()
    # Enforce same alpha membership in display and analytical pixels.
    if not np.array_equal(preview[:, :, 3], alpha):
        raise CropTiffError('Display and analytical alpha mismatch')
    identity = {'parent_file': str(getattr(image, '_stampz_crop_parent_file', ''))}
    manifest = dict(schema=SCHEMA, version=VERSION, encoding=encoding,
                    display_encoding=display_encoding, raw_derived=raw,
                    alpha='straight-uint16', crop_geometry=geometry,
                    source_identity=identity,
                    pages={key: {'shape': list(arr.shape), 'sha256': _hash(arr)}
                           for key, arr in (('native', native), ('preview', preview))})
    manifest['manifest_sha256'] = _digest(manifest)
    descriptor = json.dumps(manifest, ensure_ascii=True, sort_keys=True, allow_nan=False)
    fd, name = tempfile.mkstemp(prefix='.stampz_crop_', suffix='.tif', dir=destination.parent)
    os.close(fd)
    stage = Path(name)
    try:
        with tifffile.TiffWriter(stage) as writer:
            writer.write(native, photometric='rgb', extrasamples='UNASSALPHA',
                         metadata=None, description=descriptor, software=SOFTWARE)
            writer.write(preview, photometric='rgb', extrasamples='UNASSALPHA', metadata=None)
        verified, _ = read_self_contained_crop(stage)
        if not np.array_equal(verified._stampz_16bit_data, rgb):
            raise CropTiffError('Roundtrip RGB16 mismatch')
        if overwrite:
            os.replace(stage, destination)
        else:
            os.link(stage, destination)
    finally:
        stage.unlink(missing_ok=True)
    return manifest
