#!/usr/bin/env python3
"""All-4-stamps per-sample ellipsoid analysis (Pasteur greens).

Loads ``~/Desktop/All_Green_Pasteur.ods`` containing per-sample rows
for stamps 170, 171, 172, 174 with user-curated Exclude flags. Each
stamp is processed identically:

1. Drop excluded rows.
2. Re-cluster the included samples with KMeans(k=4); rename clusters
   so ``cluster 0`` is always the lightest tone, ``cluster 3`` the
   darkest. This gives stamp-to-stamp comparability without depending
   on whatever order each stamp's original k-means happened to use.
3. Fit one ellipsoid for the whole stamp and one per tone.
4. Pairwise comparison of whole-stamp ellipsoids → the central
   "is 174 a parallel printing of 170/171/172?" diagnostic.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from utils.color_ellipsoid import (
    EllipsoidFit,
    axis_alignment,
    compare_ellipsoids,
    fit_ellipsoid,
    mahalanobis_distance,
)

ODS_PATH = os.path.expanduser("~/Desktop/All_Green_Pasteur.ods")
SHEET = "Sheet1"

L_COL = "Lightness (L*) "
C_COL = "Chroma (C*)"
H_COL = "Hue (h)"

K_TONES = 4         # one cluster per named tone
RANDOM_SEED = 0     # KMeans determinism


def lch_to_lab(L: float, C: float, h_deg: float) -> Tuple[float, float, float]:
    h = np.deg2rad(h_deg)
    return (float(L), float(C * np.cos(h)), float(C * np.sin(h)))


def load_all(path: str, sheet: str) -> pd.DataFrame:
    """Return a tidy frame with one row per sample, including Lab + flags."""
    raw = pd.read_excel(path, engine="odf", sheet_name=sheet)
    mask = raw["DataID"].notna() & raw[L_COL].notna()
    samples = raw[mask].copy()

    # Stamp number = leading segment of DataID before the first "-".
    samples["stamp"] = samples["DataID"].astype(str).str.split("-").str[0]

    # Lab from L*/C*/h.
    lab = samples.apply(lambda r: lch_to_lab(r[L_COL], r[C_COL], r[H_COL]), axis=1)
    samples["L"] = [v[0] for v in lab]
    samples["a"] = [v[1] for v in lab]
    samples["b"] = [v[2] for v in lab]

    samples["excluded"] = samples["Exclude"].notna() & (
        samples["Exclude"].astype(str).str.strip() != ""
    )
    return samples.reset_index(drop=True)


def cluster_per_stamp(
    samples: pd.DataFrame,
    k: int = K_TONES,
) -> pd.DataFrame:
    """Run KMeans(k) within each stamp's *included* samples, then
    relabel clusters so 0 = lightest, k-1 = darkest. Excluded samples
    keep cluster = -1."""
    samples = samples.copy()
    samples["tone_cluster"] = -1
    for stamp, sub in samples[~samples["excluded"]].groupby("stamp"):
        if len(sub) < k:
            print(f"[skip] stamp {stamp}: only {len(sub)} included samples (need ≥{k})")
            continue
        labs = sub[["L", "a", "b"]].to_numpy()
        km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_SEED)
        raw_labels = km.fit_predict(labs)
        # Relabel by lightness of each cluster centre.
        centres_L = km.cluster_centers_[:, 0]
        order = np.argsort(-centres_L)         # lightest first
        relabel = {old: new for new, old in enumerate(order)}
        new_labels = np.array([relabel[l] for l in raw_labels])
        samples.loc[sub.index, "tone_cluster"] = new_labels
    return samples


# --------------------------------------------------------------------------- #
# Fits and reporting
# --------------------------------------------------------------------------- #

def fit_whole_stamp(samples: pd.DataFrame) -> Dict[str, EllipsoidFit]:
    out: Dict[str, EllipsoidFit] = {}
    for stamp, sub in samples[~samples["excluded"]].groupby("stamp"):
        out[stamp] = fit_ellipsoid(sub[["L", "a", "b"]].to_numpy())
    return out


def fit_per_tone(samples: pd.DataFrame) -> Dict[Tuple[str, int], EllipsoidFit]:
    out: Dict[Tuple[str, int], EllipsoidFit] = {}
    sub = samples[(~samples["excluded"]) & (samples["tone_cluster"] >= 0)]
    for (stamp, c), grp in sub.groupby(["stamp", "tone_cluster"]):
        labs = grp[["L", "a", "b"]].to_numpy()
        if labs.shape[0] < 2:
            continue
        out[(stamp, int(c))] = fit_ellipsoid(labs)
    return out


def report_whole_stamp(fits: Dict[str, EllipsoidFit]) -> None:
    print("\n=== Whole-stamp ellipsoids ===\n")
    print(f"{'Stamp':<6} {'n':>3}   "
          f"{'L*':>6} {'a*':>7} {'b*':>7}   "
          f"{'C*':>6} {'h°':>6}   "
          f"{'σL':>5} {'σa':>5} {'σb':>5}   "
          f"{'major axis (L|a|b)':<22}")
    print("-" * 100)
    for stamp in sorted(fits.keys()):
        fit = fits[stamp]
        L, a, b = fit.centroid_lab
        Lc, Cc, Hc = fit.centroid_lch
        sds = np.sqrt(np.diag(fit.covariance))
        align = axis_alignment(fit)
        print(f"{stamp:<6} {fit.n_samples:>3}   "
              f"{L:6.2f} {a:+7.2f} {b:+7.2f}   "
              f"{Cc:6.2f} {Hc:6.2f}   "
              f"{sds[0]:5.2f} {sds[1]:5.2f} {sds[2]:5.2f}   "
              f"{align['L']:.2f} | {align['a']:.2f} | {align['b']:.2f}")


def report_pairwise(fits: Dict[str, EllipsoidFit]) -> None:
    print("\n=== Pairwise whole-stamp comparison ===\n")
    print(f"{'A':<5} {'B':<5}   "
          f"{'ΔE76':>6}   "
          f"{'ΔL':>6} {'ΔC':>6} {'ΔH°':>6}   "
          f"{'orient':>6}   "
          f"{'A→B σ':>6} {'B→A σ':>6}")
    print("-" * 78)
    stamps = sorted(fits.keys())
    for i, sa in enumerate(stamps):
        for sb in stamps[i + 1:]:
            cmp_ = compare_ellipsoids(fits[sa], fits[sb])
            dL, dC, dH = cmp_.centroid_offset_lch
            print(f"{sa:<5} {sb:<5}   "
                  f"{cmp_.centroid_offset_distance:6.2f}   "
                  f"{dL:+6.2f} {dC:+6.2f} {dH:+6.2f}   "
                  f"{cmp_.orientation_similarity:6.3f}   "
                  f"{cmp_.a_centre_in_b_sigma:6.2f} {cmp_.b_centre_in_a_sigma:6.2f}")


def report_per_tone(
    fits: Dict[Tuple[str, int], EllipsoidFit],
) -> None:
    print("\n=== Per-tone (k-means) ellipsoids — clusters relabelled so 0=lightest ===\n")
    print(f"{'Stamp':<6} {'tone':>4} {'n':>3}   "
          f"{'L*':>6} {'a*':>7} {'b*':>7}   "
          f"{'C*':>6} {'h°':>6}   "
          f"{'σL':>5} {'σa':>5} {'σb':>5}")
    print("-" * 80)
    for (stamp, tone) in sorted(fits.keys()):
        fit = fits[(stamp, tone)]
        L, a, b = fit.centroid_lab
        Lc, Cc, Hc = fit.centroid_lch
        sds = np.sqrt(np.diag(fit.covariance))
        print(f"{stamp:<6} {tone:>4} {fit.n_samples:>3}   "
              f"{L:6.2f} {a:+7.2f} {b:+7.2f}   "
              f"{Cc:6.2f} {Hc:6.2f}   "
              f"{sds[0]:5.2f} {sds[1]:5.2f} {sds[2]:5.2f}")


def report_per_tone_alignment(
    fits: Dict[Tuple[str, int], EllipsoidFit],
) -> None:
    """Cross-stamp comparison at the same lightness-tier (tone index).

    For each tone index, compare every pair of stamps that have it.
    This isolates whether stamps differ at the *same conceptual tone*.
    """
    print("\n=== Same-tone comparison across stamps ===\n")
    tones = sorted({t for (_, t) in fits.keys()})
    for tone in tones:
        present = sorted([s for (s, t) in fits.keys() if t == tone])
        if len(present) < 2:
            continue
        print(f"\n-- tone {tone} (lightest=0, darkest={K_TONES - 1}) --")
        print(f"   {'A':<5} {'B':<5}   "
              f"{'ΔE76':>6}   "
              f"{'ΔL':>6} {'ΔC':>6} {'ΔH°':>6}   "
              f"{'orient':>6}")
        for i, sa in enumerate(present):
            for sb in present[i + 1:]:
                cmp_ = compare_ellipsoids(fits[(sa, tone)], fits[(sb, tone)])
                dL, dC, dH = cmp_.centroid_offset_lch
                print(f"   {sa:<5} {sb:<5}   "
                      f"{cmp_.centroid_offset_distance:6.2f}   "
                      f"{dL:+6.2f} {dC:+6.2f} {dH:+6.2f}   "
                      f"{cmp_.orientation_similarity:6.3f}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    print(f"Loading {ODS_PATH} (sheet={SHEET!r}) ...")
    samples = load_all(ODS_PATH, SHEET)
    n_total = len(samples)
    n_excl = int(samples["excluded"].sum())
    print(f"Loaded {n_total} sample rows ({n_excl} excluded)\n")

    print("Per-stamp counts (after exclusions):")
    for stamp, sub in samples.groupby("stamp"):
        inc = int((~sub["excluded"]).sum())
        exc = int(sub["excluded"].sum())
        print(f"  {stamp}: included={inc}, excluded={exc}")

    samples = cluster_per_stamp(samples, k=K_TONES)

    whole = fit_whole_stamp(samples)
    report_whole_stamp(whole)
    report_pairwise(whole)

    per_tone = fit_per_tone(samples)
    report_per_tone(per_tone)
    report_per_tone_alignment(per_tone)

    # Persist the clustered frame for the plotting script to consume.
    out_path = os.path.expanduser("~/Desktop/All_Green_Pasteur_clustered.parquet")
    try:
        samples.to_parquet(out_path)
        print(f"\nClustered samples written → {out_path}")
    except Exception as e:
        # Parquet requires pyarrow/fastparquet; fall back to CSV silently.
        out_path = out_path.replace(".parquet", ".csv")
        samples.to_csv(out_path, index=False)
        print(f"\nClustered samples written → {out_path} (csv fallback: {e})")

    print("\nInterpretation guide")
    print("--------------------")
    print("• Whole-stamp ellipsoids answer 'is 174 a parallel printing?': look at the")
    print("  pairwise table — high orientation similarity (>0.9) with a non-trivial")
    print("  ΔE offset signals a parallel batch shift; low orientation means a")
    print("  structurally different printing.")
    print("• Same-tone comparison strips out the tonal-set differences. If the same")
    print("  conceptual tone (e.g. tone 0 = lightest) is consistent across 170/171/172")
    print("  but offset on 174, that's the cleanest evidence of the parallel shift.")


if __name__ == "__main__":
    main()
