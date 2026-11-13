"""Experimental StampZ portable-TIFF -> existing aligned-image adapter.

Stage-2 prototype: no changes to the existing StampZ application loader.
Always authenticate all embedded pages before returning any image.
"""
from pathlib import Path
import numpy as np
from PIL import Image

from utils.self_contained_tiff import read_self_contained_tiff, PortableTiffError


def _preview_from_array(array):
    """Match current StampZ TIFF uint16 -> PIL preview truncation."""
    if array.dtype == np.uint16:
        arr8 = (array.astype(np.float64) / 65535.0 * 255.0).astype(np.uint8)
    elif array.dtype == np.uint8:
        arr8 = array
    else:
        raise PortableTiffError("Unsupported display array dtype")
    return Image.fromarray(arr8)


def load_portable_aligned_image(path):
    """Return (aligned PIL image, metadata) with current StampZ native attributes.

    The returned source object holds the original unwarped analytical pixels;
    neither the aligned pixels nor the source preview is used for analysis.
    """
    aligned_data, native_data, source_preview, manifest = read_self_contained_tiff(path)
    enc = manifest['encoding']
    raw = manifest['raw_derived']
    identity = manifest.get('source_identity', {})
    geometry = manifest['geometry']
    source = Image.fromarray(source_preview)
    if native_data.dtype == np.uint16:
        source._stampz_16bit_data = native_data
        source._stampz_16bit_encoding = enc['analytical']
    source._stampz_display_encoding = enc['source_display']
    source._stampz_is_raw = raw
    source._stampz_source_file = identity.get('original_file', '')
    if source_preview.shape[2] == 4:
        source._stampz_alpha_mask = source_preview[:, :, 3].copy()

    aligned = _preview_from_array(aligned_data)
    if aligned_data.dtype == np.uint16:
        aligned._stampz_16bit_data = aligned_data
        aligned._stampz_16bit_encoding = enc['aligned_display']
    aligned._stampz_display_encoding = enc['aligned_display']
    aligned._stampz_is_raw = raw
    source_depth = 16 if native_data.dtype == np.uint16 else 8
    source_metadata = {
        'original_bit_depth': source_depth,
        'samples_per_pixel': native_data.shape[2],
        'is_raw': raw,
        'format_info': 'Embedded authenticated StampZ native source',
    }
    # Existing native sampling only requires these record fields. File paths
    # are descriptive provenance and are never dereferenced by this adapter.
    record = {
        'schema': 'stampz.alignment_provenance',
        'version': 1,
        'source': {
            'path': identity.get('original_file', ''),
            'size': geometry['source_size'],
            'sha256': identity.get('source_sha256', ''),
        },
        'aligned': {
            'path': str(Path(path)),
            'size': geometry['reference_size'],
        },
        'reference': {'path': ''},
        'geometry': geometry,
    }
    aligned._stampz_alignment_source_image = source
    aligned._stampz_alignment_source_metadata = source_metadata
    aligned._stampz_alignment_record = record
    metadata = {
        'original_bit_depth': int(aligned_data.dtype.itemsize * 8),
        'precision_preserved': aligned_data.dtype == np.uint16,
        'samples_per_pixel': aligned_data.shape[2],
        'is_raw': raw,
        'alignment_authenticated': True,
        'alignment_source': identity.get('original_file', ''),
        'format_info': 'StampZ self-contained TIFF v1',
    }
    return aligned, metadata
