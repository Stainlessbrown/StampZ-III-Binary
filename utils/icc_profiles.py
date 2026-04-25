"""ICC profile helpers for StampZ.

We always normalise loaded images to sRGB inside the app (see
``utils/image_processor.load_image``), so any image we *write* — a
cropped/aligned export, a comparison-image composite, etc. — has sRGB
pixel coordinates. Tagging those files with an sRGB ICC profile means
colour-managed viewers (macOS Preview, modern browsers, Photoshop)
render the bytes the same way Windows users see them, instead of
each platform guessing.

This module exposes:

* ``get_srgb_icc_bytes()`` — cached bytes blob ready to pass as the
  ``icc_profile=`` keyword to ``PIL.Image.save`` for PNG/TIFF, or as
  ``iccprofile=`` to ``tifffile.imwrite``.
* ``get_save_icc_profile(image)`` — returns the ICC bytes that should
  be embedded when saving ``image``. Preserves any profile already
  attached to ``image.info`` (rare in our pipeline, but possible if a
  caller attaches one explicitly), otherwise falls back to sRGB.

Both helpers are silent fall-throughs: if Pillow's ``ImageCms`` cannot
build an sRGB profile on this platform (e.g. an unusual Pillow build
without LittleCMS), they return ``None`` and callers should skip the
``icc_profile`` kwarg rather than fail the save.
"""

from __future__ import annotations

import logging
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

_srgb_bytes_cache: Optional[bytes] = None
_srgb_bytes_attempted: bool = False


def get_srgb_icc_bytes() -> Optional[bytes]:
    """Return a cached sRGB ICC profile as raw bytes, or ``None`` if unavailable.

    The bytes are suitable for ``PIL.Image.save(..., icc_profile=...)``
    and for ``tifffile.imwrite(..., iccprofile=...)``.
    """
    global _srgb_bytes_cache, _srgb_bytes_attempted
    if _srgb_bytes_cache is not None:
        return _srgb_bytes_cache
    if _srgb_bytes_attempted:
        # We already tried and failed once; don't keep retrying on every save.
        return None

    _srgb_bytes_attempted = True
    try:
        from PIL import ImageCms

        srgb_profile = ImageCms.createProfile("sRGB")
        # ImageCmsProfile.tobytes() exists in modern Pillow; older builds
        # expose the bytes only through a roundtrip via ImageCmsProfile.
        if hasattr(srgb_profile, "tobytes"):
            data = srgb_profile.tobytes()
        else:  # pragma: no cover - very old Pillow
            cms_profile = ImageCms.ImageCmsProfile(srgb_profile)
            data = cms_profile.tobytes()
        if data:
            _srgb_bytes_cache = bytes(data)
            return _srgb_bytes_cache
    except Exception as exc:  # noqa: BLE001 — we want to never break a save
        logger.warning("Could not build sRGB ICC profile bytes: %s", exc)
    return None


def get_save_icc_profile(image: Optional[Image.Image] = None) -> Optional[bytes]:
    """Return the ICC profile bytes to embed when saving ``image``.

    Behaviour:
    * If ``image`` already has an ICC profile attached (``image.info``),
      preserve it — the caller knows something we don't.
    * Otherwise, fall back to sRGB (the canonical colour space for every
      image inside StampZ once it has been loaded).
    * Returns ``None`` if no profile is available so callers can simply
      skip the ``icc_profile`` save kwarg.
    """
    try:
        if image is not None and getattr(image, "info", None):
            existing = image.info.get("icc_profile")
            if existing:
                return existing
    except Exception:  # pragma: no cover
        pass
    return get_srgb_icc_bytes()
