#!/usr/bin/env python3
"""Per-sample ellipsoid analysis for stamp 174 (Pasteur).

This is the richer counterpart to ``pilot_ellipsoid_4_stamps.py``. The
combined 4-stamp sheet held one *averaged* row per named tone, so the
previous pilot was effectively measuring "spread of named tone means".
This script consumes the per-sample sheet for stamp 174:

* 4 cluster centroid metadata rows at the top (cluster #, centroid
  position in normalized space, tone name in the trailing column)
* ~40 per-sample rows below, each tagged with cluster, sample DataID,
  L*, C*, h, and an Exclude flag for sampling outliers

With many points per tone we can fit a *real* ellipsoid per tone — i.e.
the actual measurement variance — and then ask:

* How tight is each tone? (intra-tone σ in Lab)
* Are any samples Mahalanobis-outliers within their assigned cluster?
* What does the whole-stamp ellipsoid look like with real samples vs.
  the named-tone-averaged version we used in the 4-stamp pilot?
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from utils.color_ellipsoid import (
    EllipsoidFit,
    axis_alignment,
    compare_ellipsoids,
    fit_ellipsoid,
    is_member,
    mahalanobis_distance,
    membership_probability,
    principal_axes,
)


ODS_PATH = os.path.expanduser("~/Desktop/174_Pasteur.ods")
SHEET = "Sheet1"

# Column names from the sheet (note the trailing space on "Lightness (L*) ")
L_COL = "Lightness (L*) "
C_COL = "Chroma (C*)"
H_COL = "Hue (h)"
TONE_COL = "Unnamed: 18"   # the trailing column on centroid metadata rows


# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #

def lch_to_lab(L: float, C: float, h_deg: float) -> Tuple[float, float, float]:
    h_rad = np.deg2rad(h_deg)
    return (float(L), float(C * np.cos(h_rad)), float(C * np.sin(h_rad)))


def load_174(path: str, sheet: str) -> Tuple[pd.DataFrame, Dict[int, str]]:
    """Return (samples_df, cluster_to_tone).

    samples_df has one row per included sample, with columns:
        DataID, cluster (int), L, a, b, excluded (bool), note (Optional[str])
    cluster_to_tone is built from the metadata rows at the top of the sheet.
    """
    raw = pd.read_excel(path, engine="odf", sheet_name=sheet)

    # Cluster → tone mapping comes from rows where DataID is empty but Cluster
    # and the trailing tone column are populated.
    meta = raw[raw["DataID"].isna() & raw["Cluster"].notna()]
    cluster_to_tone: Dict[int, str] = {}
    for _, row in meta.iterrows():
        c = int(row["Cluster"])
        t = str(row.get(TONE_COL, "")).strip()
        if t and t.lower() != "nan":
            # Some entries have trailing dashes ("Green-"); tidy them.
            cluster_to_tone[c] = t.rstrip("-").strip() or f"cluster {c}"
    # Sample rows: have a DataID and L*/C*/h.
    samples = raw[raw["DataID"].notna() & raw[L_COL].notna()].copy()

    lab = samples.apply(
        lambda r: lch_to_lab(r[L_COL], r[C_COL], r[H_COL]),
        axis=1,
    )
    samples["L"] = [v[0] for v in lab]
    samples["a"] = [v[1] for v in lab]
    samples["b"] = [v[2] for v in lab]

    # Excluded rows: any non-empty Exclude flag.
    samples["excluded"] = samples["Exclude"].notna() & (
        samples["Exclude"].astype(str).str.strip() != ""
    )
    samples["cluster_int"] = samples["Cluster"].apply(
        lambda v: int(v) if pd.notna(v) else -1
    )

    return samples.reset_index(drop=True), cluster_to_tone


# --------------------------------------------------------------------------- #
# Per-tone ellipsoids
# --------------------------------------------------------------------------- #

def fit_per_cluster(
    samples: pd.DataFrame,
    cluster_to_tone: Dict[int, str],
) -> Dict[int, EllipsoidFit]:
    fits: Dict[int, EllipsoidFit] = {}
    for c, sub in samples[~samples["excluded"]].groupby("cluster_int"):
        if c < 0:
            continue
        labs = sub[["L", "a", "b"]].to_numpy()
        if labs.shape[0] < 2:
            print(f"[skip] cluster {c} ({cluster_to_tone.get(c, '?')}): "
                  f"only {labs.shape[0]} sample(s)")
            continue
        fits[c] = fit_ellipsoid(labs)
    return fits


def report_per_cluster(
    fits: Dict[int, EllipsoidFit],
    cluster_to_tone: Dict[int, str],
) -> None:
    print("\n=== Per-tone (cluster) ellipsoid fits ===\n")
    print(f"{'Cl':>3} {'Tone':<14} {'n':>3} {'reg':>5}   "
          f"{'L*':>6} {'a*':>7} {'b*':>7}   "
          f"{'C*':>6} {'h°':>7}   "
          f"{'σL':>5} {'σa':>5} {'σb':>5}   "
          f"{'major axes (L|a|b)':<22}")
    print("-" * 110)
    for c in sorted(fits.keys()):
        fit = fits[c]
        L, a, b = fit.centroid_lab
        Lc, Cc, Hc = fit.centroid_lch
        sds = np.sqrt(np.diag(fit.covariance))
        align = axis_alignment(fit)
        tone = cluster_to_tone.get(c, f"cluster {c}")
        print(f"{c:>3} {tone:<14} {fit.n_samples:>3} {str(fit.regularized):>5}   "
              f"{L:6.2f} {a:+7.2f} {b:+7.2f}   "
              f"{Cc:6.2f} {Hc:7.2f}   "
              f"{sds[0]:5.2f} {sds[1]:5.2f} {sds[2]:5.2f}   "
              f"{align['L']:.2f} | {align['a']:.2f} | {align['b']:.2f}")


def find_outliers_within_cluster(
    samples: pd.DataFrame,
    fits: Dict[int, EllipsoidFit],
    cluster_to_tone: Dict[int, str],
    sigma_threshold: float = 2.5,
) -> None:
    """Flag samples whose Mahalanobis distance from their own cluster centre
    exceeds the threshold. Useful for catching mis-clustered samples or
    measurement glitches the user hasn't excluded yet."""
    print(f"\n=== Mahalanobis outliers within each cluster (>{sigma_threshold}σ) ===\n")
    found = False
    for c, fit in sorted(fits.items()):
        sub = samples[(samples["cluster_int"] == c) & (~samples["excluded"])]
        for _, row in sub.iterrows():
            d = mahalanobis_distance((row["L"], row["a"], row["b"]), fit)
            if d > sigma_threshold:
                tone = cluster_to_tone.get(c, f"cluster {c}")
                print(f"  cluster {c} ({tone:<12}) {row['DataID']:<10} "
                      f"  d={d:.2f}σ   "
                      f"L={row['L']:.2f} a={row['a']:+.2f} b={row['b']:+.2f}")
                found = True
    if not found:
        print(f"  (none — all samples within {sigma_threshold}σ of their cluster centre)")


# --------------------------------------------------------------------------- #
# Whole-stamp ellipsoid: per-sample vs. previous named-tone-averaged
# --------------------------------------------------------------------------- #

def report_whole_stamp(samples: pd.DataFrame) -> Optional[EllipsoidFit]:
    """Fit one ellipsoid to all (non-excluded) samples of stamp 174.

    Compares to the named-tone-averaged result from the earlier pilot:
        174 averaged: centroid (54.54, -15.83, +6.35), C*≈17.06, h°≈158.15
    """
    included = samples[~samples["excluded"]]
    labs = included[["L", "a", "b"]].to_numpy()
    if labs.shape[0] < 2:
        print("[skip] whole-stamp fit: not enough samples")
        return None
    fit = fit_ellipsoid(labs)
    L, a, b = fit.centroid_lab
    Lc, Cc, Hc = fit.centroid_lch
    sds = np.sqrt(np.diag(fit.covariance))
    align = axis_alignment(fit)

    print("\n=== Whole-stamp 174 ellipsoid (per-sample) ===\n")
    print(f"  n={fit.n_samples}, regularized={fit.regularized}")
    print(f"  centroid (Lab): L={L:.2f}  a={a:+.2f}  b={b:+.2f}")
    print(f"  centroid (LCh): L={Lc:.2f}  C={Cc:.2f}  h={Hc:.2f}°")
    print(f"  axis stddev:    σL={sds[0]:.2f}  σa={sds[1]:.2f}  σb={sds[2]:.2f}")
    print(f"  major axis cosines: L={align['L']:.2f}  a={align['a']:.2f}  b={align['b']:.2f}")

    # Comparison snapshot vs. the averaged-tone fit from the previous pilot
    prev = (54.54, -15.83, 6.35)
    diff = np.array([L - prev[0], a - prev[1], b - prev[2]])
    print("\n  vs. averaged-tone fit from previous pilot:")
    print(f"    avg centroid (Lab): L={prev[0]:.2f}  a={prev[1]:+.2f}  b={prev[2]:+.2f}")
    print(f"    Δcentroid:          ΔL={diff[0]:+.2f}  Δa={diff[1]:+.2f}  Δb={diff[2]:+.2f}   "
          f"|Δ|={np.linalg.norm(diff):.2f}")
    return fit


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    print(f"Loading {ODS_PATH} (sheet={SHEET!r}) ...")
    samples, cluster_to_tone = load_174(ODS_PATH, SHEET)

    n_total = len(samples)
    n_excluded = int(samples["excluded"].sum())
    print(f"Loaded {n_total} sample rows ({n_excluded} marked Exclude).")
    print(f"Cluster → tone map: {cluster_to_tone}\n")

    counts = samples[~samples["excluded"]].groupby("cluster_int").size()
    print("Included sample counts per cluster:")
    for c, n in counts.items():
        tone = cluster_to_tone.get(c, f"cluster {c}")
        print(f"  cluster {c} ({tone:<14}) n={n}")

    if n_excluded:
        print("\nExcluded samples:")
        for _, row in samples[samples["excluded"]].iterrows():
            note = ""
            try:
                u18 = row.get("Unnamed: 18", "")
                if pd.notna(u18) and str(u18).strip():
                    note = f"  — {str(u18).strip()}"
            except Exception:
                pass
            print(f"  {row['DataID']:<10}  cluster {row['cluster_int']:>2}  "
                  f"L={row['L']:.2f}  a={row['a']:+.2f}  b={row['b']:+.2f}{note}")

    fits = fit_per_cluster(samples, cluster_to_tone)
    report_per_cluster(fits, cluster_to_tone)
    find_outliers_within_cluster(samples, fits, cluster_to_tone)
    report_whole_stamp(samples)

    print("\nInterpretation guide")
    print("--------------------")
    print("• σL/σa/σb are the per-axis standard deviations within each tone:")
    print("  small values mean the printer/sampler hit that colour very consistently.")
    print("• A cluster's major-axis cosines tell you the *direction* of variance —")
    print("  e.g. L-dominant means \"density variation\", a-dominant means \"hue drift\".")
    print("• Mahalanobis-outlier samples are candidates for re-sampling or exclusion;")
    print("  the user-marked Exclude rows already show one such case (174-H).")
    print("• The whole-stamp Δcentroid line shows how much the named-tone average")
    print("  misrepresents the per-sample mean — usually small, but worth confirming.")


if __name__ == "__main__":
    main()
