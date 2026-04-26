#!/usr/bin/env python3
"""Lab colour-difference decomposition: ΔL*, ΔC*, ΔH*.

The single ΔE scalar reported by ``ColorAnalyzer.calculate_delta_e`` is
useful as a "how close overall" number, but it's notoriously
uninformative in low-chroma blues — the area where philatelic blues
(slate, dull, milky, prussian, indigo, cobalt …) actually live and
where Lab's perceptual uniformity is worst. A 0.8 ΔE in a saturated
red and a 0.8 ΔE in a near-neutral slate blue are visually very
different things.

Decomposing the difference into ΔL* (lightness), ΔC* (chroma; distance
from the neutral axis) and ΔH* (hue rotation) gives the user the
*direction* of the disagreement, which usually matches what their eye
reports far better than a single scalar.

Sign conventions used here:

* ΔL  > 0  → sample is **lighter** than the reference
* ΔC  > 0  → sample is **more saturated** (further from neutral grey)
* ΔH° > 0  → sample's hue is rotated **counter-clockwise** in the a*b*
            plane relative to the reference. For a blue reference
            (negative b*), positive ΔH means the sample is rotated
            toward higher b*, i.e. *less* blue / shifted toward
            green-cyan; negative ΔH means *more* blue / toward purple.

This module is deliberately Tk- and analyzer-agnostic so both the
Results panel and the canvas live HUD can use it without dragging in
each other's dependencies.
"""

from __future__ import annotations

import math
from typing import Dict, Sequence, Tuple


# --------------------------------------------------------------------------- #
# Conversions
# --------------------------------------------------------------------------- #

def lab_to_lch(lab: Sequence[float]) -> Tuple[float, float, float]:
    """Convert a CIE Lab triple to LCH (lightness, chroma, hue°).
    
    Hue is returned in degrees in the [0, 360) range. Chroma is the
    Euclidean distance from the L* axis: ``sqrt(a*² + b*²)``.
    """
    L, a, b = lab
    C = math.sqrt(a * a + b * b)
    H_deg = math.degrees(math.atan2(b, a))
    if H_deg < 0.0:
        H_deg += 360.0
    return (L, C, H_deg)


# --------------------------------------------------------------------------- #
# Difference decomposition
# --------------------------------------------------------------------------- #

def lab_difference_components(
    lab_sample: Sequence[float],
    lab_ref: Sequence[float],
) -> Dict[str, float]:
    """Decompose ``lab_sample - lab_ref`` into perceptual components.
    
    Returns a dict with:
      * ``delta_l``        — ΔL* (Lab units, signed)
      * ``delta_c``        — ΔC* (Lab units, signed; chroma)
      * ``delta_h_deg``    — Hue rotation in degrees, in [-180, +180]
      * ``delta_h_metric`` — Signed metric ΔH* in Lab units, the value
                             that combines with ΔL/ΔC via Pythagoras to
                             give ΔE76. Sign matches ``delta_h_deg``.
      * ``delta_a``        — Δa* (Lab units, signed; raw axis difference)
      * ``delta_b``        — Δb* (Lab units, signed; raw axis difference)
      * ``delta_e_76``     — CIE76 ΔE for cross-checking; the
                             analyzer's CAM02-UCS / CIE2000 ΔE generally
                             won't match this value exactly.
    """
    L1, a1, b1 = lab_sample
    L2, a2, b2 = lab_ref
    
    dL = L1 - L2
    da = a1 - a2
    db = b1 - b2
    delta_e_76 = math.sqrt(dL * dL + da * da + db * db)
    
    _, C1, H1 = lab_to_lch(lab_sample)
    _, C2, H2 = lab_to_lch(lab_ref)
    dC = C1 - C2
    
    # Signed shortest-path hue rotation in [-180, +180]
    dH_deg = H1 - H2
    if dH_deg > 180.0:
        dH_deg -= 360.0
    elif dH_deg < -180.0:
        dH_deg += 360.0
    
    # Metric ΔH* in Lab units: sqrt(Δa² + Δb² - ΔC²), signed by the
    # rotation direction. The clamp protects against tiny negative
    # round-off when both a*b* points lie effectively on top of each
    # other.
    dH_metric_sq = max(0.0, da * da + db * db - dC * dC)
    dH_metric = math.sqrt(dH_metric_sq)
    if dH_deg < 0.0:
        dH_metric = -dH_metric
    
    return {
        'delta_l': dL,
        'delta_c': dC,
        'delta_h_deg': dH_deg,
        'delta_h_metric': dH_metric,
        'delta_a': da,
        'delta_b': db,
        'delta_e_76': delta_e_76,
    }


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #

def format_lab_components_compact(components: Dict[str, float]) -> str:
    """One-line ``ΔL +1.2  ΔC -0.5  ΔH +4.2°`` summary for HUD/labels.
    
    Two spaces between groups for readability; signs always shown so
    the direction (lighter vs darker, more saturated vs less, rotation
    sense) is unambiguous at a glance.
    """
    return (
        f"ΔL {components['delta_l']:+.1f}  "
        f"ΔC {components['delta_c']:+.1f}  "
        f"ΔH {components['delta_h_deg']:+.1f}°"
    )
