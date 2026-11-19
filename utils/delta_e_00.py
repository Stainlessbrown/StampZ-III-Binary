"""Authoritative StampZ CIEDE2000 color difference for CIE L*a*b* values.

This measures differences between already-computed Lab triples. Do not feed
normalized RGB or XYZ directly. CIEDE2000 kL=kC=kH=1.
"""
from typing import Tuple

def delta_e_00(lab1: Tuple[float, float, float],
                      lab2: Tuple[float, float, float]) -> float:
    """Calculate color difference using CIEDE2000 (Delta E 00).

    Args:
        lab1: First Lab color (L, a, b)
        lab2: Second Lab color (L, a, b)

    Returns:
        CIEDE2000 (Delta E 00) color difference.
    """
    import math

    # Unpack L*a*b* values
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    # Standard CIEDE2000 weighting factors
    kL = 1.0
    kC = 1.0
    kH = 1.0

    # Initial chroma
    C1 = math.sqrt(a1**2 + b1**2)
    C2 = math.sqrt(a2**2 + b2**2)
    Cab = (C1 + C2) / 2.0

    # a* compensation
    G = 0.5 * (
        1.0 - math.sqrt(Cab**7 / (Cab**7 + 25**7))
    )

    a1p = (1.0 + G) * a1
    a2p = (1.0 + G) * a2

    # Corrected chroma
    C1p = math.sqrt(a1p**2 + b1**2)
    C2p = math.sqrt(a2p**2 + b2**2)

    # Corrected hue angles
    def calculate_h_prime(ap, b):
        if ap == 0 and b == 0:
            return 0.0
        h = math.degrees(math.atan2(b, ap))
        return h + 360.0 if h < 0 else h

    h1p = calculate_h_prime(a1p, b1)
    h2p = calculate_h_prime(a2p, b2)

    # Delta L', Delta C'
    deltaLp = L2 - L1
    deltaCp = C2p - C1p

    # Delta H'
    deltahp = h2p - h1p

    if C1p * C2p == 0:
        deltaHp_angle = 0.0
    elif abs(deltahp) <= 180:
        deltaHp_angle = deltahp
    elif deltahp > 180:
        deltaHp_angle = deltahp - 360.0
    else:
        deltaHp_angle = deltahp + 360.0

    deltaHp = (
        2.0
        * math.sqrt(C1p * C2p)
        * math.sin(math.radians(deltaHp_angle / 2.0))
    )

    # Mean lightness and chroma
    Lp = (L1 + L2) / 2.0
    Cp = (C1p + C2p) / 2.0

    # Mean hue
    if C1p * C2p == 0:
        hp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hp = (h1p + h2p) / 2.0
    elif h1p + h2p < 360:
        hp = (h1p + h2p + 360.0) / 2.0
    else:
        hp = (h1p + h2p - 360.0) / 2.0

    # Hue weighting term
    T = (
        1.0
        - 0.17 * math.cos(math.radians(hp - 30.0))
        + 0.24 * math.cos(math.radians(2.0 * hp))
        + 0.32 * math.cos(math.radians(3.0 * hp + 6.0))
        - 0.20 * math.cos(math.radians(4.0 * hp - 63.0))
    )

    # Rotation term
    deltaTheta = 30.0 * math.exp(-((hp - 275.0) / 25.0)**2)
    RC = 2.0 * math.sqrt(Cp**7 / (Cp**7 + 25**7))
    RT = -math.sin(math.radians(2.0 * deltaTheta)) * RC

    # Compensation terms
    SL = 1.0 + (
        0.015 * (Lp - 50.0)**2
        / math.sqrt(20.0 + (Lp - 50.0)**2)
    )
    SC = 1.0 + 0.045 * Cp
    SH = 1.0 + 0.015 * Cp * T

    # CIEDE2000
    deltaE = math.sqrt(
        (deltaLp / (kL * SL))**2
        + (deltaCp / (kC * SC))**2
        + (deltaHp / (kH * SH))**2
        + RT
        * (deltaCp / (kC * SC))
        * (deltaHp / (kH * SH))
    )

    return deltaE

