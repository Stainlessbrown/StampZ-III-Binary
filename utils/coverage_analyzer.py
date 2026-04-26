"""Coverage-ratio + effective-tone analyzer for cropped stamp images.

This module operates on a *user-cropped* stamp image. There is no
auto-crop — the caller is responsible for trimming the image down to
just the design region (perforated margins excluded). Behaviour:

1. Every visible pixel is classified into one of four buckets, using a
   known paper Lab as the only reference colour:
       * **paper** — within ``paper_tolerance`` ΔE (CIE76) of paper Lab.
       * **edge** — between ``paper_tolerance`` and
         ``edge_band_factor`` × ``paper_tolerance`` ΔE (anti-aliased
         ink/paper boundary). Excluded from both colour averages and
         counted half-and-half in the coverage ratio.
       * **cancel** (a.k.a. neutral-dark) — L\\* below
         ``dark_l_threshold`` AND chroma C\\* below
         ``dark_c_threshold``. These pixels are excluded from the ink
         colour average (cancellation marks would drag it black) but
         counted as "ink" for the coverage ratio (they used to be ink
         before being cancelled).
       * **ink** — everything else.

2. ``ink_lab`` is the pixel-mean Lab of the ink class.

3. ``coverage_ratio`` = ``(n_ink + n_cancel + 0.5·n_edge) / n_visible``
   — the share of the cropped design that is "covered" by ink.

4. ``effective_tone_lab`` is the perceptual fusion the eye sees:
   ``coverage·ink + (1 − coverage)·paper`` blended in **linear RGB**
   (not sRGB), then converted back to Lab. Doing the blend in sRGB
   directly is noticeably wrong for greens and blues.

5. ``classification_image`` is a flat-coloured PIL image you can show
   alongside the original to sanity-check whether the segmentation
   looks representative.

The analyzer requires ``numpy`` (already a hard dependency) and
``colorspacious`` (recommended; falls back to an internal sRGB↔Lab
approximation if missing).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np
from PIL import Image

try:
    from colorspacious import cspace_convert  # type: ignore[import-not-found]
    HAS_COLORSPACIOUS = True
except Exception:  # pragma: no cover
    HAS_COLORSPACIOUS = False


# --------------------------------------------------------------------------- #
# Defaults
# --------------------------------------------------------------------------- #
# Defaults tuned against real stamp scans: ΔE 3 turned out to be
# *much* too tight — paper texture + scan noise routinely produces
# pixel-to-pixel ΔE of 5–10 on a healthy paper substrate, so a tolerance
# of 3 wrongly drops most of the paper area into the "edge" or "ink"
# class. ΔE 5 is a more forgiving starting point; the GUI exposes a
# spinbox that lets the user dial it per-stamp.
DEFAULT_PAPER_TOLERANCE = 5.0
DEFAULT_EDGE_BAND_FACTOR = 2.0
DEFAULT_DARK_L_THRESHOLD = 20.0
DEFAULT_DARK_C_THRESHOLD = 8.0
DEFAULT_ALPHA_THRESHOLD = 16  # 0..255

# Tint targets for the classification preview. The preview blends each
# pixel of the original image *toward* the class tint instead of
# replacing it, so the printed design stays visible (key for visually
# checking whether the classifier boundary matches the eye's boundary).
# Ink pixels are passed through untouched; everything else fades toward
# a neutral.
PREVIEW_PAPER_TINT = (240, 240, 240)   # near-white wash
PREVIEW_EDGE_TINT = (200, 200, 200)    # mid grey wash (uncertain band)
PREVIEW_CANCEL_TINT = (40, 40, 40)     # near-black wash
PREVIEW_BG_COLOR = (255, 255, 255)     # invisible / alpha=0 pixels
PREVIEW_PAPER_BLEND = 0.6              # 60% tint, 40% original
PREVIEW_EDGE_BLEND = 0.5
PREVIEW_CANCEL_BLEND = 0.6


# --------------------------------------------------------------------------- #
# Result dataclass
# --------------------------------------------------------------------------- #

@dataclass
class CoverageResult:
    """Numerical and visual outputs of a coverage analysis pass."""

    paper_lab: Tuple[float, float, float]
    ink_lab: Tuple[float, float, float]
    effective_tone_lab: Tuple[float, float, float]
    effective_tone_rgb: Tuple[int, int, int]

    coverage_ratio: float  # 0.0–1.0

    # Per-class pixel counts (also useful for the classifier UI).
    n_total: int
    n_visible: int
    n_paper: int
    n_ink: int
    n_cancel: int
    n_edge: int

    classification_image: Image.Image  # RGB preview, same shape as input

    # Tuning knobs that produced this result; useful when the UI wants
    # to display "(tolerance 3.0 ΔE)" alongside the numbers.
    paper_tolerance: float
    edge_band_factor: float
    dark_l_threshold: float
    dark_c_threshold: float


# --------------------------------------------------------------------------- #
# Vectorised colour conversions
# --------------------------------------------------------------------------- #

def _srgb_to_linear(srgb: np.ndarray) -> np.ndarray:
    """sRGB (0..1) → linear RGB (0..1), elementwise."""
    a = 0.055
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + a) / (1 + a)) ** 2.4)


def _linear_to_srgb(linear: np.ndarray) -> np.ndarray:
    """Linear RGB (0..1) → sRGB (0..1), elementwise."""
    a = 0.055
    return np.where(linear <= 0.0031308, linear * 12.92,
                    (1 + a) * np.power(np.clip(linear, 0.0, None), 1 / 2.4) - a)


def _rgb_to_lab_array(rgb_uint8: np.ndarray) -> np.ndarray:
    """Convert an ``(H, W, 3)`` uint8 sRGB array to Lab (D65).

    Uses ``colorspacious`` when available (faster, more accurate),
    otherwise the same sRGB→XYZ→Lab approximation that
    ``ColorAnalyzer._rgb_to_lab_approximation`` uses, vectorised.
    """
    rgb = rgb_uint8.astype(np.float64) / 255.0  # (H, W, 3) in 0..1

    if HAS_COLORSPACIOUS:
        # cspace_convert handles any array shape so long as the last
        # axis is the colour channel.
        return np.asarray(cspace_convert(rgb, "sRGB1", "CIELab"))

    # ---- Fallback: vectorised sRGB → XYZ (D65) → Lab --------------------- #
    rgb_lin = _srgb_to_linear(rgb)
    # sRGB → XYZ matrix (D65)
    M = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ])
    xyz = rgb_lin @ M.T
    # Normalise by D65 reference white
    xyz /= np.array([0.95047, 1.0, 1.08883])
    # f(t)
    delta = 6.0 / 29.0
    delta3 = delta ** 3
    f = np.where(xyz > delta3,
                 np.cbrt(np.clip(xyz, 0.0, None)),
                 xyz / (3 * delta * delta) + 4.0 / 29.0)
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return np.stack([L, a, b], axis=-1)


def _lab_to_linear_rgb(lab: Sequence[float]) -> np.ndarray:
    """Single Lab tuple → linear RGB (0..1) numpy array of length 3."""
    if HAS_COLORSPACIOUS:
        srgb = np.asarray(cspace_convert(np.asarray(lab), "CIELab", "sRGB1"))
        srgb = np.clip(srgb, 0.0, 1.0)
        return _srgb_to_linear(srgb)

    # Fallback: do a coarse round-trip via the inverse of the simple
    # approximation. Less accurate but only used when colorspacious is
    # absent, which is rare.
    L, a, b = lab
    # Lab → XYZ
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0
    delta = 6.0 / 29.0

    def f_inv(t: float) -> float:
        return t ** 3 if t > delta else 3 * delta * delta * (t - 4.0 / 29.0)

    x = 0.95047 * f_inv(fx)
    y = 1.0 * f_inv(fy)
    z = 1.08883 * f_inv(fz)
    M_inv = np.array([
        [3.2404542, -1.5371385, -0.4985314],
        [-0.9692660, 1.8760108, 0.0415560],
        [0.0556434, -0.2040259, 1.0572252],
    ])
    rgb_lin = M_inv @ np.array([x, y, z])
    return np.clip(rgb_lin, 0.0, 1.0)


def _linear_rgb_to_lab(rgb_lin: np.ndarray) -> Tuple[float, float, float]:
    """Single linear RGB triple → Lab tuple."""
    srgb = _linear_to_srgb(np.clip(rgb_lin, 0.0, 1.0))
    rgb_uint8 = (np.clip(srgb, 0.0, 1.0) * 255.0).astype(np.uint8)
    arr = rgb_uint8.reshape(1, 1, 3)
    lab = _rgb_to_lab_array(arr)[0, 0]
    return float(lab[0]), float(lab[1]), float(lab[2])


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def analyze_coverage(
    image: Image.Image,
    paper_lab: Sequence[float],
    paper_tolerance: float = DEFAULT_PAPER_TOLERANCE,
    edge_band_factor: float = DEFAULT_EDGE_BAND_FACTOR,
    dark_l_threshold: float = DEFAULT_DARK_L_THRESHOLD,
    dark_c_threshold: float = DEFAULT_DARK_C_THRESHOLD,
    alpha_threshold: int = DEFAULT_ALPHA_THRESHOLD,
) -> CoverageResult:
    """Classify every pixel of ``image`` against ``paper_lab`` and report.

    See the module docstring for the algorithmic details.

    Args:
        image: A PIL image. RGB or RGBA (alpha cropped). The caller is
            responsible for cropping out perforated margins beforehand.
        paper_lab: ``(L*, a*, b*)`` of the paper, e.g. the group average
            of the user's "P"-tagged samples.
        paper_tolerance: ΔE radius around ``paper_lab`` that counts as
            paper. Common values: 3 for single-ink work, 4–5 for fine
            line engraving.
        edge_band_factor: Outer ΔE radius for the anti-aliased
            ink/paper boundary, expressed as a multiple of
            ``paper_tolerance``. Pixels in this band are split
            half-and-half in the coverage ratio.
        dark_l_threshold: L\\* below which a pixel is *eligible* for the
            cancellation class.
        dark_c_threshold: C\\* below which a pixel is *eligible* for the
            cancellation class. Both L\\* and C\\* gates must be satisfied.
        alpha_threshold: For RGBA inputs, pixels with α below this are
            considered invisible and excluded from every count.

    Returns:
        A ``CoverageResult`` with per-class pixel counts, paper/ink/
        effective-tone Lab triples, the coverage ratio, and a
        recoloured classification preview image.

    Raises:
        ValueError: ``image`` is empty, has no visible pixels, or
            ``paper_lab`` is malformed.
    """
    if image is None or image.size[0] == 0 or image.size[1] == 0:
        raise ValueError("analyze_coverage: image is empty")
    paper_lab_t = tuple(float(c) for c in paper_lab)
    if len(paper_lab_t) != 3:
        raise ValueError("analyze_coverage: paper_lab must be (L, a, b)")

    # ---- normalise input mode + extract alpha ---------------------------- #
    if image.mode == "RGBA":
        rgba = np.asarray(image)
        rgb = rgba[..., :3]
        alpha = rgba[..., 3]
        visible = alpha >= alpha_threshold
    elif image.mode == "RGB":
        rgb = np.asarray(image)
        visible = np.ones(rgb.shape[:2], dtype=bool)
    else:
        # LA, P, L, etc. — convert through RGBA so alpha is preserved
        # if the source had any.
        converted = image.convert("RGBA")
        rgba = np.asarray(converted)
        rgb = rgba[..., :3]
        alpha = rgba[..., 3]
        visible = alpha >= alpha_threshold

    n_total = rgb.shape[0] * rgb.shape[1]
    n_visible = int(visible.sum())
    if n_visible == 0:
        raise ValueError("analyze_coverage: image has no visible pixels "
                         "(alpha mask hides everything)")

    # ---- vectorised RGB → Lab -------------------------------------------- #
    lab = _rgb_to_lab_array(rgb)  # (H, W, 3) float64
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    chroma = np.sqrt(a * a + b * b)

    pL, pa, pb = paper_lab_t
    # CIE76 ΔE: cheap, vectorised, and the philatelic ΔE thresholds we
    # use (3, 5, 6) are calibrated against this metric anyway.
    delta_e_paper = np.sqrt((L - pL) ** 2 + (a - pa) ** 2 + (b - pb) ** 2)

    inner_tol = float(paper_tolerance)
    outer_tol = float(paper_tolerance) * float(edge_band_factor)

    paper_mask = visible & (delta_e_paper <= inner_tol)
    edge_mask = visible & (delta_e_paper > inner_tol) & (delta_e_paper <= outer_tol)
    not_paper_or_edge = visible & ~paper_mask & ~edge_mask
    cancel_mask = (
        not_paper_or_edge
        & (L < float(dark_l_threshold))
        & (chroma < float(dark_c_threshold))
    )
    ink_mask = not_paper_or_edge & ~cancel_mask

    n_paper = int(paper_mask.sum())
    n_ink = int(ink_mask.sum())
    n_cancel = int(cancel_mask.sum())
    n_edge = int(edge_mask.sum())

    # ---- ink Lab (mean over the ink class) ------------------------------- #
    if n_ink > 0:
        ink_L = float(L[ink_mask].mean())
        ink_a = float(a[ink_mask].mean())
        ink_b = float(b[ink_mask].mean())
    else:
        # Degenerate case: nothing classified as ink. Report paper as
        # the ink fallback so downstream maths doesn't blow up; coverage
        # will be 0 and the dialog can flag the situation.
        ink_L, ink_a, ink_b = paper_lab_t
    ink_lab = (ink_L, ink_a, ink_b)

    # ---- coverage ratio -------------------------------------------------- #
    # Edge pixels are physically half ink and half paper; counting them
    # at 0.5 prevents both undercount (ignoring edges) and overcount
    # (treating every anti-aliased pixel as ink).
    coverage_ratio = (n_ink + n_cancel + 0.5 * n_edge) / float(n_visible)
    coverage_ratio = float(np.clip(coverage_ratio, 0.0, 1.0))

    # ---- effective-tone Lab (linear-RGB blend) --------------------------- #
    paper_lin = _lab_to_linear_rgb(paper_lab_t)
    ink_lin = _lab_to_linear_rgb(ink_lab)
    eff_lin = coverage_ratio * ink_lin + (1.0 - coverage_ratio) * paper_lin
    effective_tone_lab = _linear_rgb_to_lab(eff_lin)

    # sRGB triple for the swatch (rounded to int for Tk colour codes).
    eff_srgb01 = _linear_to_srgb(np.clip(eff_lin, 0.0, 1.0))
    effective_tone_rgb = tuple(int(round(c * 255.0)) for c in eff_srgb01)

    # ---- classification preview (tinted overlay) ------------------------ #
    # Each non-ink class blends the original pixel toward a neutral tint
    # so the printed design stays visually readable. Ink pixels are kept
    # at their original colour so any "this should be paper" or "this
    # should be ink" misclassification is obvious to the eye.
    preview = np.empty(rgb.shape, dtype=np.uint8)
    preview[...] = PREVIEW_BG_COLOR  # invisible / out-of-mask pixels
    
    rgb_f = rgb.astype(np.float32)
    
    def _blend_into(mask, tint, blend):
        if not mask.any():
            return
        tint_arr = np.asarray(tint, dtype=np.float32)
        blended = rgb_f[mask] * (1.0 - blend) + tint_arr * blend
        preview[mask] = np.clip(blended, 0.0, 255.0).astype(np.uint8)
    
    # Paint in this order so ink ends up *unblended* (it overwrites any
    # bleed from masks that don't actually fire here, but ink_mask is
    # always disjoint from the others by construction).
    _blend_into(paper_mask, PREVIEW_PAPER_TINT, PREVIEW_PAPER_BLEND)
    _blend_into(edge_mask, PREVIEW_EDGE_TINT, PREVIEW_EDGE_BLEND)
    _blend_into(cancel_mask, PREVIEW_CANCEL_TINT, PREVIEW_CANCEL_BLEND)
    preview[ink_mask] = rgb[ink_mask]  # ink: pass through original colour
    
    preview_image = Image.fromarray(preview, mode="RGB")

    return CoverageResult(
        paper_lab=paper_lab_t,
        ink_lab=ink_lab,
        effective_tone_lab=effective_tone_lab,
        effective_tone_rgb=effective_tone_rgb,
        coverage_ratio=coverage_ratio,
        n_total=n_total,
        n_visible=n_visible,
        n_paper=n_paper,
        n_ink=n_ink,
        n_cancel=n_cancel,
        n_edge=n_edge,
        classification_image=preview_image,
        paper_tolerance=inner_tol,
        edge_band_factor=float(edge_band_factor),
        dark_l_threshold=float(dark_l_threshold),
        dark_c_threshold=float(dark_c_threshold),
    )
