#!/usr/bin/env python3
"""Color ellipsoid fitting and Mahalanobis-distance classification.

A single ΔE scalar is a *distance* metric: it tells you how far apart two
colours are, but it has no opinion about whether that distance is meaningful
for a particular group of stamps. A printing run with naturally tight ink
mixing might cluster within ΔE 1.5; a sloppy run might routinely span ΔE 5.
Calling the same numerical distance "the same" or "different" without
reference to the group's variance is misleading.

This module replaces the spherical assumption baked into k-means / raw ΔE
with an *ellipsoidal* one: every measured group is described by

* a **centroid** in Lab (the mean of the measurements), and
* a **covariance matrix** capturing the shape, size, and orientation of the
  cluster.

From those, two questions can be answered statistically:

1. *How likely is this stamp to belong to this printing's distribution?*
   → Mahalanobis distance + chi-squared survival function.
2. *Are two printings related (same design, different batch)?*
   → Compare centroids (offset) and principal axes (orientation similarity).

Design notes
------------
* Ellipsoids are fitted in **CIE Lab**, not LCh. Lab is a Cartesian space
  where covariance is well-defined; LCh's hue axis is circular and breaks
  covariance estimation whenever a cluster straddles the 0°/360° boundary.
  Results are reported with LCh decomposition (ΔL/ΔC/ΔH) for philatelic
  readability, but the underlying maths stays in Lab.
* Small-sample regularization (shrinkage toward an isotropic prior) keeps
  the inverse covariance well-conditioned when n is small — important for
  stamp issues where only a handful of suitable specimens exist.
* Tk- and DB-agnostic; consumes plain Lab tuples / numpy arrays so both
  Plot_3D, the analyzer, and ad-hoc scripts can call it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    from scipy.stats import chi2
    HAS_SCIPY = True
except ImportError:  # pragma: no cover — scipy ships with scikit-learn
    HAS_SCIPY = False

from .lab_difference import lab_to_lch


# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #

LabPoint = Tuple[float, float, float]


@dataclass
class EllipsoidFit:
    """Fitted ellipsoid in Lab space describing a group of measurements.

    Attributes:
        centroid:        Lab mean as a numpy array of shape (3,).
        covariance:      3x3 covariance matrix in Lab.
        inv_covariance:  3x3 precision matrix (cached inverse), used to
                         compute Mahalanobis distance without re-inverting.
        n_samples:       Number of points used to fit.
        regularized:     True if shrinkage / jitter was applied (small-sample
                         safety). Useful for the UI to flag low-confidence fits.
    """
    centroid: np.ndarray
    covariance: np.ndarray
    inv_covariance: np.ndarray
    n_samples: int
    regularized: bool = False

    @property
    def centroid_lab(self) -> LabPoint:
        return tuple(float(v) for v in self.centroid)

    @property
    def centroid_lch(self) -> Tuple[float, float, float]:
        return lab_to_lch(self.centroid_lab)


@dataclass
class EllipsoidComparison:
    """Result of comparing two ellipsoids."""
    centroid_offset_lab: np.ndarray             # vector from A → B (Lab)
    centroid_offset_distance: float             # Euclidean ΔE76 between centres
    centroid_offset_lch: Tuple[float, float, float]  # (ΔL, ΔC, ΔH°)
    orientation_similarity: float               # |cos θ| between major axes [0,1]
    a_centre_in_b_sigma: float                  # Mahalanobis(centre_A, fit_B)
    b_centre_in_a_sigma: float                  # Mahalanobis(centre_B, fit_A)


# --------------------------------------------------------------------------- #
# Fitting
# --------------------------------------------------------------------------- #

def fit_ellipsoid(
    lab_points: Sequence[LabPoint],
    *,
    regularize_below: int = 10,
    shrinkage_alpha: float = 0.1,
    prior_variance: float = 4.0,
) -> EllipsoidFit:
    """Fit a covariance ellipsoid to a set of Lab measurements.

    Args:
        lab_points:        Iterable of (L, a, b) tuples or shape-(N,3) array.
        regularize_below:  When ``n_samples < regularize_below``, blend the
                           covariance with an isotropic prior. Default 10.
        shrinkage_alpha:   Mixing weight ∈ [0, 1] applied when shrinkage
                           triggers. 0 = pure data, 1 = pure prior. Default 0.1.
        prior_variance:    Diagonal value of the isotropic prior, in Lab units².
                           Default 4.0, i.e. roughly ΔE 2 stddev per axis —
                           a generous "we don't know yet" prior.

    Returns:
        EllipsoidFit.

    Raises:
        ValueError: if fewer than 2 points are supplied or shape is wrong.
    """
    arr = np.asarray(lab_points, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError("lab_points must be shape (N, 3); got %r" % (arr.shape,))
    n = int(arr.shape[0])
    if n < 2:
        raise ValueError(f"Need at least 2 points to fit an ellipsoid; got {n}")

    centroid = arr.mean(axis=0)
    cov = np.cov(arr, rowvar=False, ddof=1)

    regularized = False
    if n < regularize_below:
        prior = np.eye(3) * prior_variance
        cov = (1.0 - shrinkage_alpha) * cov + shrinkage_alpha * prior
        regularized = True

    # Defensive: if covariance is still singular (e.g. all points colinear)
    # add a tiny diagonal jitter so the matrix can be inverted reliably.
    try:
        inv_cov = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        cov = cov + np.eye(3) * 1e-6
        inv_cov = np.linalg.inv(cov)
        regularized = True

    return EllipsoidFit(
        centroid=centroid,
        covariance=cov,
        inv_covariance=inv_cov,
        n_samples=n,
        regularized=regularized,
    )


# --------------------------------------------------------------------------- #
# Distances and membership
# --------------------------------------------------------------------------- #

def mahalanobis_distance(
    lab_point: LabPoint,
    ellipsoid: EllipsoidFit,
) -> float:
    """Mahalanobis distance from a Lab point to an ellipsoid's centre.

    Returned in units of "ellipsoid standard deviations": 1.0 means the
    point sits on the 1σ contour, 2.0 on the 2σ contour, etc. Independent
    of whether the underlying axes are stretched or rotated — that is the
    whole point of the metric.
    """
    diff = np.asarray(lab_point, dtype=float) - ellipsoid.centroid
    d2 = float(diff @ ellipsoid.inv_covariance @ diff)
    return math.sqrt(max(0.0, d2))


def membership_probability(
    lab_point: LabPoint,
    ellipsoid: EllipsoidFit,
) -> float:
    """Probability that a point belongs to the ellipsoid's distribution.

    Uses the chi-squared survival function with 3 degrees of freedom
    (Lab is 3D). Returns ~1.0 at the centre and decays toward 0.0 as the
    point moves outward; a point on the 2σ contour returns ~0.05 — the
    classic "outside the 95% region" mark.

    Falls back to a coarse exp(-d²/2) approximation if scipy is missing.
    """
    diff = np.asarray(lab_point, dtype=float) - ellipsoid.centroid
    d2 = float(diff @ ellipsoid.inv_covariance @ diff)
    d2 = max(0.0, d2)
    if HAS_SCIPY:
        return float(chi2.sf(d2, df=3))
    # Lightweight fallback: monotone in d² but not chi-squared-accurate.
    return math.exp(-0.5 * d2)


def is_member(
    lab_point: LabPoint,
    ellipsoid: EllipsoidFit,
    sigma: float = 2.0,
) -> bool:
    """Convenience predicate: is the point within ``sigma`` of the centre?

    The default of 2σ corresponds to ~95% of a multivariate normal
    distribution — a reasonable working definition of "consistent with
    this printing's variance".
    """
    return mahalanobis_distance(lab_point, ellipsoid) <= sigma


# --------------------------------------------------------------------------- #
# Shape / orientation
# --------------------------------------------------------------------------- #

def principal_axes(ellipsoid: EllipsoidFit) -> Tuple[np.ndarray, np.ndarray]:
    """Return the ellipsoid's principal axes, sorted longest first.

    Returns:
        eigenvalues:  shape (3,), variance along each principal axis.
                      Standard deviation along axis k = sqrt(eigenvalues[k]).
        eigenvectors: shape (3, 3), columns are unit vectors in Lab. The
                      first column is the *longest* axis of the ellipsoid.
    """
    eigvals, eigvecs = np.linalg.eigh(ellipsoid.covariance)
    # eigh returns ascending; flip so [0] is the longest axis.
    order = np.argsort(eigvals)[::-1]
    return eigvals[order], eigvecs[:, order]


def axis_alignment(ellipsoid: EllipsoidFit) -> Dict[str, float]:
    """Describe how well the longest principal axis aligns with L, a, b.

    Returns absolute cosines (0..1) of the angle between the major axis and
    each Lab basis vector. Useful for human-readable reporting like
    "this printing's variance is dominated by lightness drift".
    """
    _, vecs = principal_axes(ellipsoid)
    major = vecs[:, 0]
    return {
        "L": abs(float(major[0])),
        "a": abs(float(major[1])),
        "b": abs(float(major[2])),
    }


def ellipsoid_mesh(
    ellipsoid: EllipsoidFit,
    *,
    sigma: float = 1.0,
    n_u: int = 28,
    n_v: int = 16,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a parametric (X, Y, Z) mesh for plotting an ellipsoid surface.

    The mesh is the ``sigma``-σ contour of the fitted distribution, suitable
    for ``matplotlib`` ``ax.plot_surface`` / ``ax.plot_wireframe`` (the same
    API ``plot3d.sphere_manager`` uses for spheres).

    Args:
        ellipsoid: A fitted EllipsoidFit.
        sigma:     Mahalanobis radius of the surface to draw. 1.0 = 1σ
                   contour (~68% of a Gaussian); 2.0 = 2σ (~95%).
        n_u, n_v:  Mesh resolution. Defaults match plot3d.sphere_manager.

    Returns:
        (X, Y, Z) each of shape (n_u, n_v) in the same Lab coordinate frame
        as the ellipsoid's centroid.
    """
    # Eigendecomposition: covariance = vecs · diag(vals) · vecs.T
    # Stretching a unit sphere by sqrt(vals) along each eigenvector gives
    # the 1σ ellipsoid; multiplying by ``sigma`` rescales to other contours.
    vals, vecs = np.linalg.eigh(ellipsoid.covariance)
    radii = sigma * np.sqrt(np.maximum(vals, 0.0))

    u = np.linspace(0.0, 2.0 * np.pi, n_u)
    v = np.linspace(0.0, np.pi, n_v)
    # Unit-sphere parametric mesh
    xu = np.outer(np.cos(u), np.sin(v))
    yu = np.outer(np.sin(u), np.sin(v))
    zu = np.outer(np.ones_like(u), np.cos(v))

    # Stack into (3, n_u*n_v), scale by radii, rotate by eigenvectors,
    # then reshape back to mesh form and translate to the centroid.
    pts = np.stack([xu.ravel(), yu.ravel(), zu.ravel()], axis=0)
    pts = (vecs * radii) @ pts                       # (3, N)
    pts = pts + ellipsoid.centroid.reshape(3, 1)
    X = pts[0].reshape(xu.shape)
    Y = pts[1].reshape(yu.shape)
    Z = pts[2].reshape(zu.shape)
    return X, Y, Z


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #

def compare_ellipsoids(
    a: EllipsoidFit,
    b: EllipsoidFit,
) -> EllipsoidComparison:
    """Compare two ellipsoids: position offset, orientation, mutual fit.

    Designed for the "parallel printing" diagnostic: if two ellipsoids have
    similar shape and orientation but offset centres, they likely represent
    the same design / printing process at different ink-or-paper batches.
    """
    offset = b.centroid - a.centroid
    offset_distance = float(np.linalg.norm(offset))

    # Decompose the centroid offset into LCh-aligned ΔL, ΔC, ΔH° for humans.
    Ll, Cl, Hl = lab_to_lch(tuple(a.centroid))
    Lr, Cr, Hr = lab_to_lch(tuple(b.centroid))
    dL = Lr - Ll
    dC = Cr - Cl
    dH = Hr - Hl
    if dH > 180.0:
        dH -= 360.0
    elif dH < -180.0:
        dH += 360.0

    # Orientation similarity: |cos θ| between the major axes. 1.0 = parallel,
    # 0.0 = perpendicular. Absolute value because eigenvector sign is
    # arbitrary; only the line direction is meaningful.
    _, vecs_a = principal_axes(a)
    _, vecs_b = principal_axes(b)
    cos_major = abs(float(np.dot(vecs_a[:, 0], vecs_b[:, 0])))

    return EllipsoidComparison(
        centroid_offset_lab=offset,
        centroid_offset_distance=offset_distance,
        centroid_offset_lch=(dL, dC, dH),
        orientation_similarity=cos_major,
        a_centre_in_b_sigma=mahalanobis_distance(tuple(a.centroid), b),
        b_centre_in_a_sigma=mahalanobis_distance(tuple(b.centroid), a),
    )


# --------------------------------------------------------------------------- #
# Self-test (run with: python -m utils.color_ellipsoid)
# --------------------------------------------------------------------------- #

def _self_test() -> None:
    """Synthetic sanity check: build two known clusters, verify the maths."""
    rng = np.random.default_rng(42)

    # "Printing A": green-ish cluster around L=40, a=-20, b=15
    centre_a = np.array([40.0, -20.0, 15.0])
    cov_true = np.diag([4.0, 1.5, 1.5])  # most variance on L axis
    pts_a = rng.multivariate_normal(centre_a, cov_true, size=20)

    # "Printing B": same shape, parallel-shifted to lighter / less saturated
    centre_b = np.array([46.0, -18.0, 16.0])
    pts_b = rng.multivariate_normal(centre_b, cov_true, size=20)

    fit_a = fit_ellipsoid(pts_a.tolist())
    fit_b = fit_ellipsoid(pts_b.tolist())

    print("--- Fits ---")
    print(f"A: centroid={tuple(round(v, 2) for v in fit_a.centroid_lab)}, "
          f"n={fit_a.n_samples}, regularized={fit_a.regularized}")
    print(f"B: centroid={tuple(round(v, 2) for v in fit_b.centroid_lab)}, "
          f"n={fit_b.n_samples}, regularized={fit_b.regularized}")

    print("\n--- Membership ---")
    p_a_in_a = membership_probability(tuple(centre_a), fit_a)
    p_a_in_b = membership_probability(tuple(centre_a), fit_b)
    print(f"P(centre_A ∈ A) = {p_a_in_a:.4f}  (expect ~1.0)")
    print(f"P(centre_A ∈ B) = {p_a_in_b:.6f}  (expect ~0)")

    print("\n--- Comparison ---")
    cmp_ = compare_ellipsoids(fit_a, fit_b)
    print(f"Centroid offset (Lab):  {tuple(round(v, 2) for v in cmp_.centroid_offset_lab)}")
    print(f"Centroid offset ΔE76:   {cmp_.centroid_offset_distance:.2f}")
    print(f"Centroid offset (LCh):  ΔL {cmp_.centroid_offset_lch[0]:+.2f}  "
          f"ΔC {cmp_.centroid_offset_lch[1]:+.2f}  "
          f"ΔH {cmp_.centroid_offset_lch[2]:+.2f}°")
    print(f"Major-axis similarity:  {cmp_.orientation_similarity:.3f}  (expect close to 1)")
    print(f"centre_A is {cmp_.a_centre_in_b_sigma:.2f}σ from centre_B")
    print(f"centre_B is {cmp_.b_centre_in_a_sigma:.2f}σ from centre_A")

    print("\n--- Axis alignment of A ---")
    align = axis_alignment(fit_a)
    print(f"Major axis cosines:  L={align['L']:.2f}  a={align['a']:.2f}  b={align['b']:.2f}")
    print("(expect L dominant, since the synthetic covariance was diag(4, 1.5, 1.5))")


if __name__ == "__main__":
    _self_test()
