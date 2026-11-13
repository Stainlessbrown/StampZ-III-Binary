"""Standalone StampZ self-contained aligned TIFF v1 prototype.

No changes to StampZ's existing loader, sampling, or alignment pipeline.
This is a *prototype file format*, not yet integrated into StampZ.

Three TIFF pages are intentional:
  0 - aligned display pixels (RGB/RGBA, uint8 or uint16)
  1 - original-grid analytical pixels (RGB/RGBA, uint8 or uint16)
  2 - original-grid source preview (RGB/RGBA, uint8)

Page 2 matters for the current R50 pipeline: its source preview may be
linear for display while its analytical RGB16 pixels are gamma encoded.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

import numpy as np
import tifffile

SCHEMA = "stampz.self_contained_aligned_tiff"
VERSION = 1
PORTABLE_SOFTWARE = "StampZ-Portable-TIFF-v1"
PAGE_ROLES = ("aligned_display", "native_analytical_source", "source_preview")


class PortableTiffError(ValueError):
    """Failed strict portable TIFF validation."""


def _fail(message: str):
    raise PortableTiffError(message)


def _pixels(value, role, *, preview=False):
    array = np.asarray(value)
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        _fail(f"{role}: expected H x W x 3/4 pixels")
    if array.shape[0] <= 0 or array.shape[1] <= 0:
        _fail(f"{role}: empty image")
    if array.dtype not in (np.dtype('uint8'), np.dtype('uint16')):
        _fail(f"{role}: expected uint8 or uint16 pixels")
    if preview and array.dtype != np.dtype('uint8'):
        _fail(f"{role}: preview must be uint8")
    return np.ascontiguousarray(array)


def _hash_pixels(array):
    # Canonical little-endian representation, independent of machine byte order.
    if array.dtype.itemsize == 2:
        payload = array.astype('<u2', copy=False)
    else:
        payload = array
    return hashlib.sha256(memoryview(np.ascontiguousarray(payload)).cast('B')).hexdigest()


def _page_entry(role, array):
    return {
        "role": role,
        "shape": list(array.shape),
        "dtype": f"uint{array.dtype.itemsize * 8}",
        "sha256_pixels_le": _hash_pixels(array),
    }


def _validate_encoding(value, role):
    if value not in ("linear", "srgb"):
        _fail(f"{role}: encoding must be 'linear' or 'srgb'")


def _validate_geometry(geometry, source_wh, aligned_wh):
    if not isinstance(geometry, dict):
        _fail("geometry: expected an object")
    try:
        matrix = np.asarray(geometry["transform_matrix"], dtype=np.float64)
        box = geometry["crop_box"]
    except (KeyError, TypeError, ValueError) as exc:
        raise PortableTiffError(f"geometry: missing or invalid transform/crop box: {exc}") from exc
    if matrix.shape not in ((2, 3), (3, 3)) or not np.isfinite(matrix).all():
        _fail("geometry: invalid transform matrix")
    homography = np.vstack((matrix, [0, 0, 1])) if matrix.shape == (2, 3) else matrix
    if abs(float(np.linalg.det(homography))) < 1e-12:
        _fail("geometry: singular transform matrix")
    if not isinstance(box, (list, tuple)) or len(box) != 4 or any(type(v) is not int for v in box):
        _fail("geometry: crop_box must be four integers")
    left, top, right, bottom = box
    if not (0 <= left < right <= source_wh[0] and 0 <= top < bottom <= source_wh[1]):
        _fail("geometry: crop box outside source")
    if geometry.get("transform_direction", "cropped-source-to-reference") != "cropped-source-to-reference":
        _fail("geometry: unsupported transform direction")
    if geometry.get("coordinate_origin", "top-left") != "top-left":
        _fail("geometry: unsupported coordinate origin")
    return {
        "transform_matrix": matrix.tolist(),
        "crop_box": list(box),
        "transform_direction": "cropped-source-to-reference",
        "coordinate_origin": "top-left",
        "reference_size": list(aligned_wh),
        "source_size": list(source_wh),
    }


def _manifest_digest(manifest):
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    encoded = json.dumps(body, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode('ascii')
    return hashlib.sha256(encoded).hexdigest()


def _write_page(writer, array, description=None, icc_profile=None):
    kwargs = dict(photometric="rgb", metadata=None, description=description,
                  contiguous=False)
    if array.shape[2] == 4:
        kwargs["extrasamples"] = "UNASSALPHA"
    if icc_profile is not None:
        kwargs["iccprofile"] = icc_profile
    if description is not None:
        kwargs["software"] = PORTABLE_SOFTWARE
    writer.write(array, **kwargs)


def write_self_contained_tiff(
    destination,
    *,
    aligned_display,
    native_source,
    source_preview,
    geometry,
    analytical_encoding,
    aligned_display_encoding,
    source_display_encoding,
    raw_derived,
    source_identity=None,
    icc_profile=None,
    overwrite=False,
):
    """Write and strictly verify a single TIFF, then publish atomically.

    Arrays MUST be taken from the current authenticated StampZ objects,
    not regenerated or re-decoded. ``source_preview`` is the original-grid
    PIL display representation (not the aligned display).

    Existing files are never replaced unless ``overwrite=True``.
    Returns verified manifest. Failure leaves destination unchanged.
    """
    destination = Path(destination)
    if destination.suffix.lower() not in (".tif", ".tiff"):
        _fail("destination: expected .tif or .tiff")
    if not destination.parent.is_dir():
        _fail("destination: parent directory does not exist")
    if not overwrite and destination.exists():
        raise FileExistsError(str(destination))
    aligned = _pixels(aligned_display, "aligned_display")
    native = _pixels(native_source, "native_source")
    preview = _pixels(source_preview, "source_preview", preview=True)
    if native.shape[:2] != preview.shape[:2]:
        _fail("source preview and native analytical dimensions differ")
    if native.dtype == np.uint8 and analytical_encoding == "linear":
        _fail("uint8 native analytical data cannot be declared linear in v1")
    for role, value in (
        ("analytical", analytical_encoding),
        ("aligned display", aligned_display_encoding),
        ("source display", source_display_encoding),
    ):
        _validate_encoding(value, role)
    if type(raw_derived) is not bool:
        _fail("raw_derived: expected true/false")
    if source_identity is None:
        source_identity = {}
    if not isinstance(source_identity, dict):
        _fail("source_identity must be an object")
    if icc_profile is not None and not isinstance(icc_profile, bytes):
        _fail("icc_profile must be bytes")
    source_wh = (native.shape[1], native.shape[0])
    aligned_wh = (aligned.shape[1], aligned.shape[0])
    geom = _validate_geometry(geometry, source_wh, aligned_wh)
    manifest = {
        "schema": SCHEMA,
        "version": VERSION,
        "pages": [_page_entry(role, array) for role, array in zip(PAGE_ROLES, (aligned, native, preview))],
        "geometry": geom,
        "encoding": {
            "analytical": analytical_encoding,
            "aligned_display": aligned_display_encoding,
            "source_display": source_display_encoding,
        },
        "raw_derived": raw_derived,
        "source_identity": source_identity,
        "icc_sha256": hashlib.sha256(icc_profile).hexdigest() if icc_profile else None,
    }
    manifest["manifest_sha256"] = _manifest_digest(manifest)
    description = json.dumps(manifest, ensure_ascii=True, sort_keys=True, allow_nan=False)

    # Same directory enables same-filesystem atomic publication.
    fd, tmp = tempfile.mkstemp(prefix=".stampz_portable_", suffix=".tmp", dir=destination.parent)
    tmp_path = Path(tmp)
    os.close(fd)
    try:
        with open(tmp_path, 'w+b') as handle:
            projected_bytes = sum(a.nbytes for a in (aligned, native, preview))
            with tifffile.TiffWriter(handle, bigtiff=projected_bytes >= 3_800_000_000) as writer:
                _write_page(writer, aligned, description, icc_profile)
                _write_page(writer, native)
                _write_page(writer, preview)
            handle.flush()
            os.fsync(handle.fileno())
        verified = verify_self_contained_tiff(tmp_path)
        if not overwrite:
            # Atomic, exclusive publish. Never accidentally overwrite a race winner.
            os.link(tmp_path, destination)
        else:
            os.replace(tmp_path, destination)
        try:
            dir_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass  # Directory fsync not uniformly supported by every filesystem.
        return verified
    finally:
        tmp_path.unlink(missing_ok=True)


def is_self_contained_tiff(path):
    """Recognize a portable TIFF before any general-purpose TIFF decoding.

    New files carry an independent TIFF Software marker. The schema check
    additionally recognizes existing v1 prototypes written before this tag.
    This is classification, not authentication: loading always verifies all
    three pages and the manifest.
    """
    path = Path(path)
    if path.suffix.lower() not in (".tif", ".tiff"):
        return False
    try:
        with tifffile.TiffFile(path) as tif:
            if not tif.pages:
                return False
            page = tif.pages[0]
            tag = page.tags.get(305)
            if tag is not None and str(tag.value) == PORTABLE_SOFTWARE:
                return True
            description = page.description or ""
            return isinstance(description, str) and (
                '"schema": "' + SCHEMA + '"' in description
                or '"schema":"' + SCHEMA + '"' in description
            )
    except (OSError, ValueError, KeyError, IndexError, tifffile.TiffFileError):
        return False


def read_self_contained_tiff(path):
    """Return (page0, page1, page2, manifest) only after strict verification."""
    path = Path(path)
    try:
        with tifffile.TiffFile(path) as tif:
            if len(tif.pages) != 3:
                _fail(f"page count: expected 3, found {len(tif.pages)}")
            desc = tif.pages[0].description
            try:
                manifest = json.loads(desc)
            except (TypeError, json.JSONDecodeError) as exc:
                raise PortableTiffError("manifest: missing or invalid JSON") from exc
            if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
                _fail("manifest: not a StampZ self-contained TIFF")
            if type(manifest.get("version")) is not int or manifest["version"] != VERSION:
                _fail(f"manifest: unsupported version {manifest.get('version')!r}")
            if manifest.get("manifest_sha256") != _manifest_digest(manifest):
                _fail("manifest: checksum mismatch")
            enc = manifest.get("encoding")
            if not isinstance(enc, dict):
                _fail("manifest: encoding missing")
            for field in ("analytical", "aligned_display", "source_display"):
                _validate_encoding(enc.get(field), field)
            if type(manifest.get("raw_derived")) is not bool:
                _fail("manifest: RAW provenance missing")
            pages_meta = manifest.get("pages")
            if not isinstance(pages_meta, list) or len(pages_meta) != 3:
                _fail("manifest: page records missing")
            arrays = []
            for idx, role in enumerate(PAGE_ROLES):
                array = _pixels(tif.pages[idx].asarray(), role, preview=(idx == 2))
                entry = pages_meta[idx]
                if not isinstance(entry, dict) or entry.get("role") != role:
                    _fail(f"page {idx}: wrong role")
                if entry.get("shape") != list(array.shape):
                    _fail(f"page {idx}: shape mismatch")
                if entry.get("dtype") != f"uint{array.dtype.itemsize * 8}":
                    _fail(f"page {idx}: dtype mismatch")
                if entry.get("sha256_pixels_le") != _hash_pixels(array):
                    _fail(f"page {idx}: pixel checksum mismatch")
                arrays.append(array)
            aligned, native, preview = arrays
            if native.shape[:2] != preview.shape[:2]:
                _fail("preview/source dimensions mismatch")
            geom = _validate_geometry(manifest.get("geometry"),
                                      (native.shape[1], native.shape[0]),
                                      (aligned.shape[1], aligned.shape[0]))
            if geom != manifest["geometry"]:
                _fail("geometry: source/aligned size mismatch")
            if native.dtype == np.uint8 and enc["analytical"] == "linear":
                _fail("unsupported 8-bit linear analytical encoding")
            icc = tif.pages[0].tags.get(34675)
            icc_data = bytes(icc.value) if icc is not None else None
            icc_hash = hashlib.sha256(icc_data).hexdigest() if icc_data else None
            if manifest.get("icc_sha256") != icc_hash:
                _fail("ICC profile checksum mismatch")
            return aligned, native, preview, manifest
    except PortableTiffError:
        raise
    except Exception as exc:
        raise PortableTiffError(f"TIFF read failed: {type(exc).__name__}: {exc}") from exc


def verify_self_contained_tiff(path):
    """Return manifest on success; raise PortableTiffError on failure."""
    return read_self_contained_tiff(path)[3]
