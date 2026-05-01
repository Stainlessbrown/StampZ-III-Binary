#!/usr/bin/env python3
"""Pilot: fit ellipsoids to the 4 Pasteur green stamps and compare them.

This is a one-shot research script for Step 2 of the ellipsoid-classification
work. It is *not* part of the packaged StampZ app — it lives at the repo root
alongside the other development utilities.

Data source
-----------
~/Desktop/170-174_Pasteur.ods, single sheet, layout:

* DataID:   "<stamp#>-<tone name>" (e.g. "170-Green", "174-Dark Green")
* Lightness (L*), Chroma (C*), Hue (h):  per-row LCh values
* Xnorm/Ynorm/Znorm:  normalized Lab (not used here; we recompute Lab
                       directly from L*, C*, h to avoid round-trip loss)

Two analyses
------------
A. **Per-stamp ellipsoid:** fit one ellipsoid to each stamp's set of tones
   and compare them pairwise. Tests the "parallel printing" hypothesis:
   if stamp 174 is parallel to 170/171/172, its ellipsoid should be
   similarly oriented but offset.

B. **Anchor-vector analysis:** for each stamp, treat "Green" as the
   anchor and compute Lab offset vectors from it to each other tone.
   Compares those vectors across stamps. A truly parallel printing has
   matching internal vectors regardless of absolute position.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from utils.color_ellipsoid import (
    EllipsoidFit,
    axis_alignment,
    compare_ellipsoids,
    fit_ellipsoid,
    mahalanobis_distance,
    membership_probability,
)


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

ODS_PATH = os.path.expanduser("~/Desktop/170-174_Pasteur.ods")
SHEET_NAME = "Sheet1"
ANCHOR_TONE = "green"   # case-insensitive match for the anchor tone


# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #

def lch_to_lab(L: float, C: float, h_deg: float) -> Tuple[float, float, float]:
    """Convert L*, C*, h° → L, a, b. Inverse of utils.lab_difference.lab_to_lch."""
    h_rad = np.deg2rad(h_deg)
    return (float(L), float(C * np.cos(h_rad)), float(C * np.sin(h_rad)))


def parse_stamp_and_tone(data_id: str) -> Tuple[str, str]:
    """Split '<stamp>-<tone>' on the first hyphen."""
    if "-" not in data_id:
        return (data_id, "")
    head, tail = data_id.split("-", 1)
    return (head.strip(), tail.strip())


def load_data(path: str, sheet: str) -> pd.DataFrame:
    """Read the .ods, drop empty rows, parse stamp/tone, compute Lab."""
    df = pd.read_excel(path, engine="odf", sheet_name=sheet)
    df = df.dropna(subset=["DataID", "Lightness (L*) ", "Chroma (C*)", "Hue (h)"]).copy()

    parsed = df["DataID"].apply(parse_stamp_and_tone)
    df["stamp"] = [p[0] for p in parsed]
    df["tone"] = [p[1] for p in parsed]

    lab = df.apply(
        lambda r: lch_to_lab(r["Lightness (L*) "], r["Chroma (C*)"], r["Hue (h)"]),
        axis=1,
    )
    df["L"] = [v[0] for v in lab]
    df["a"] = [v[1] for v in lab]
    df["b"] = [v[2] for v in lab]

    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Analysis A: per-stamp ellipsoids and pairwise comparison
# --------------------------------------------------------------------------- #

def fit_per_stamp(df: pd.DataFrame) -> Dict[str, EllipsoidFit]:
    fits: Dict[str, EllipsoidFit] = {}
    for stamp, sub in df.groupby("stamp"):
        labs = sub[["L", "a", "b"]].to_numpy()
        if labs.shape[0] < 2:
            print(f"[skip] stamp {stamp!r}: only {labs.shape[0]} point(s)")
            continue
        fits[stamp] = fit_ellipsoid(labs)
    return fits


def report_fits(fits: Dict[str, EllipsoidFit]) -> None:
    print("\n=== Analysis A: per-stamp ellipsoid fits ===\n")
    print(f"{'Stamp':<8} {'n':>3} {'reg':>4}   "
          f"{'L*':>6} {'a*':>7} {'b*':>7}   "
          f"{'C*':>6} {'h°':>6}   "
          f"major-axis cosines (L|a|b)")
    print("-" * 92)
    for stamp, fit in fits.items():
        L, a, b = fit.centroid_lab
        Lc, Cc, Hc = fit.centroid_lch
        align = axis_alignment(fit)
        print(f"{stamp:<8} {fit.n_samples:>3} {str(fit.regularized):>4}   "
              f"{L:6.2f} {a:+7.2f} {b:+7.2f}   "
              f"{Cc:6.2f} {Hc:6.2f}   "
              f"{align['L']:.2f} | {align['a']:.2f} | {align['b']:.2f}")


def report_pairwise(fits: Dict[str, EllipsoidFit]) -> None:
    print("\n=== Analysis A: pairwise ellipsoid comparison ===\n")
    print(f"{'A':<6} {'B':<6}   "
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
            print(f"{sa:<6} {sb:<6}   "
                  f"{cmp_.centroid_offset_distance:6.2f}   "
                  f"{dL:+6.2f} {dC:+6.2f} {dH:+6.2f}   "
                  f"{cmp_.orientation_similarity:6.3f}   "
                  f"{cmp_.a_centre_in_b_sigma:6.2f} {cmp_.b_centre_in_a_sigma:6.2f}")


# --------------------------------------------------------------------------- #
# Analysis B: anchor-vector analysis
# --------------------------------------------------------------------------- #

def anchor_vectors(df: pd.DataFrame, anchor_tone: str) -> Dict[str, Dict[str, np.ndarray]]:
    """Return {stamp: {tone: lab_offset_from_anchor}} for non-anchor tones.

    Tone matching is case-insensitive and uses the anchor's lower-cased name.
    """
    anchor_lc = anchor_tone.lower()
    out: Dict[str, Dict[str, np.ndarray]] = {}
    for stamp, sub in df.groupby("stamp"):
        sub_lc = sub.assign(tone_lc=sub["tone"].str.lower())
        anchor_rows = sub_lc[sub_lc["tone_lc"] == anchor_lc]
        if anchor_rows.empty:
            print(f"[skip] stamp {stamp!r}: no anchor tone {anchor_tone!r} found")
            continue
        anchor_lab = anchor_rows[["L", "a", "b"]].to_numpy()[0]
        offsets: Dict[str, np.ndarray] = {}
        for _, row in sub_lc.iterrows():
            if row["tone_lc"] == anchor_lc:
                continue
            lab = np.array([row["L"], row["a"], row["b"]])
            offsets[row["tone"]] = lab - anchor_lab
        out[stamp] = offsets
    return out


def report_anchor_vectors(vecs: Dict[str, Dict[str, np.ndarray]]) -> None:
    print(f"\n=== Analysis B: anchor-relative offsets (anchor = '{ANCHOR_TONE}') ===\n")
    # Print each stamp's offset vectors, tone by tone.
    all_tones = sorted({tone for s in vecs.values() for tone in s})
    print(f"{'Tone':<24} " + "  ".join(f"{s:>22}" for s in vecs.keys()))
    print("-" * (24 + 24 * len(vecs)))
    for tone in all_tones:
        cells = []
        for s in vecs.keys():
            if tone in vecs[s]:
                v = vecs[s][tone]
                cells.append(f"ΔL{v[0]:+5.1f} Δa{v[1]:+5.1f} Δb{v[2]:+5.1f}")
            else:
                cells.append("—")
        print(f"{tone:<24} " + "  ".join(f"{c:>22}" for c in cells))


def compare_anchor_vectors(
    vecs: Dict[str, Dict[str, np.ndarray]],
    reference_stamps: List[str],
    test_stamp: str,
) -> None:
    """For each tone shared between the reference group and the test stamp,
    compare the test stamp's offset vector to the reference group's mean
    offset vector. Reports magnitude and direction differences.
    """
    print(f"\n=== Analysis B: '{test_stamp}' offsets vs mean of {reference_stamps} ===\n")
    print(f"{'Tone':<24} {'ref n':>5}  "
          f"{'|ref|':>6} {'|test|':>6}   "
          f"{'cos':>5}   "
          f"{'mag ratio':>9}   "
          f"{'Δvec ΔE':>8}")
    print("-" * 78)

    if test_stamp not in vecs:
        print(f"  test stamp {test_stamp!r} has no anchor-relative data")
        return

    test_offsets = vecs[test_stamp]
    # Tones present in the test stamp AND in at least one reference stamp.
    tones = sorted(test_offsets.keys())
    for tone in tones:
        ref_vecs = []
        # Match tone case-insensitively across reference stamps.
        for s in reference_stamps:
            if s not in vecs:
                continue
            for rt, rv in vecs[s].items():
                if rt.lower() == tone.lower():
                    ref_vecs.append(rv)
                    break
        if not ref_vecs:
            continue
        ref_mean = np.mean(ref_vecs, axis=0)
        test_v = test_offsets[tone]
        mag_ref = float(np.linalg.norm(ref_mean))
        mag_test = float(np.linalg.norm(test_v))
        cos = float(
            np.dot(ref_mean, test_v) / (mag_ref * mag_test)
        ) if mag_ref > 0 and mag_test > 0 else float("nan")
        ratio = mag_test / mag_ref if mag_ref > 0 else float("nan")
        delta_vec = float(np.linalg.norm(test_v - ref_mean))
        print(f"{tone:<24} {len(ref_vecs):>5}  "
              f"{mag_ref:6.2f} {mag_test:6.2f}   "
              f"{cos:5.2f}   "
              f"{ratio:9.2f}   "
              f"{delta_vec:8.2f}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    print(f"Loading {ODS_PATH} (sheet={SHEET_NAME!r}) ...")
    df = load_data(ODS_PATH, SHEET_NAME)
    print(f"Loaded {len(df)} non-empty rows.\n")

    print("Detected stamps and tone counts:")
    counts = df.groupby("stamp")["tone"].count().sort_index()
    for s, c in counts.items():
        marker = "  ⚠ check spelling" if not re.fullmatch(r"\d{3}", s) else ""
        print(f"  {s:<8} {c} tones{marker}")
    print()

    fits = fit_per_stamp(df)
    report_fits(fits)
    report_pairwise(fits)

    vecs = anchor_vectors(df, ANCHOR_TONE)
    report_anchor_vectors(vecs)

    # Test the "parallel printing" hypothesis: 174 vs the {170, 171, 172} group.
    # Use whatever subset of the reference group actually has data.
    reference_stamps = [s for s in ("170", "171", "172") if s in vecs]
    if "174" in vecs and reference_stamps:
        compare_anchor_vectors(vecs, reference_stamps, "174")

    print("\nInterpretation guide")
    print("--------------------")
    print("• Analysis A: a high orientation score (>0.9) with non-trivial centroid offset")
    print("  is the hallmark of a parallel printing — same design intent, batch-shifted.")
    print("• Analysis B: cos ≈ 1.0 and mag ratio ≈ 1.0 per tone means stamp 174's")
    print("  internal tone-vectors match the reference group → same design,")
    print("  even though absolute colours differ.")
    print("• Where Analysis B's |ref| or mag ratio look anomalous on a single tone,")
    print("  that tone is the one diverging — a clue about which colour shifted.")


if __name__ == "__main__":
    main()
