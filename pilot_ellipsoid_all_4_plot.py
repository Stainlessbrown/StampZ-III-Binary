#!/usr/bin/env python3
"""All-4 stamps ellipsoid visualization.

Renders two views in a single figure:

* **Left panel (3D):** all four stamps' whole-stamp ellipsoids overlaid
  in CIE Lab space, with each stamp's included samples as scatter
  points. Designed to answer the central question — "does 174's
  ellipsoid sit offset-but-parallel to 170/171, or is something
  structurally different?" — at a glance.
* **Right panel (3D):** the same scene but with per-tone (k-means)
  ellipsoids drawn instead of the whole-stamp shells. Useful for
  seeing where the lightness tiers line up across stamps.

Consumes the clustered CSV produced by ``pilot_ellipsoid_all_4_samples.py``.
"""

from __future__ import annotations

import os
import sys
import warnings
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from utils.color_ellipsoid import (
    EllipsoidFit,
    ellipsoid_mesh,
    fit_ellipsoid,
)

CSV_PATH = os.path.expanduser("~/Desktop/All_Green_Pasteur_clustered.csv")

# Stamp → distinct plotting colour. Chosen for visual contrast, not
# colorimetric accuracy — the data carries the actual measured colours.
STAMP_COLOURS: Dict[str, str] = {
    "170": "#1f77b4",   # blue
    "171": "#2ca02c",   # green
    "172": "#d62728",   # red
    "174": "#ff7f0e",   # orange
}


def stamp_colour(stamp: str) -> str:
    return STAMP_COLOURS.get(stamp, "#777777")


def fit_whole(samples: pd.DataFrame) -> Dict[str, EllipsoidFit]:
    fits: Dict[str, EllipsoidFit] = {}
    for stamp, sub in samples[~samples["excluded"]].groupby("stamp"):
        fits[str(stamp)] = fit_ellipsoid(sub[["L", "a", "b"]].to_numpy())
    return fits


def fit_per_tone(
    samples: pd.DataFrame,
) -> Dict[Tuple[str, int], EllipsoidFit]:
    fits: Dict[Tuple[str, int], EllipsoidFit] = {}
    sub = samples[(~samples["excluded"]) & (samples["tone_cluster"] >= 0)]
    for (stamp, c), grp in sub.groupby(["stamp", "tone_cluster"]):
        labs = grp[["L", "a", "b"]].to_numpy()
        if labs.shape[0] < 2:
            continue
        fits[(str(stamp), int(c))] = fit_ellipsoid(labs)
    return fits


def draw_scatter(ax, samples: pd.DataFrame) -> None:
    for stamp, sub in samples.groupby("stamp"):
        col = stamp_colour(str(stamp))
        included = sub[~sub["excluded"]]
        excluded = sub[sub["excluded"]]
        ax.scatter(
            included["L"], included["a"], included["b"],
            c=col, s=20, edgecolors="black", linewidths=0.3, depthshade=True,
        )
        if not excluded.empty:
            ax.scatter(
                excluded["L"], excluded["a"], excluded["b"],
                facecolors="none", edgecolors=col, s=24, linewidths=0.5,
                alpha=0.6,
            )


def draw_ellipsoid(
    ax,
    fit: EllipsoidFit,
    colour: str,
    *,
    sigma_solid: float = 1.0,
    sigma_wire: float = 2.0,
    surface_alpha: float = 0.10,
    wire_alpha: float = 0.25,
) -> None:
    """Draw 1σ surface + 2σ wireframe for one ellipsoid.

    ``np.errstate`` silences the divide/overflow warnings matplotlib's
    surface-shading code emits when a small-n ellipsoid is highly
    eccentric. The render itself is correct; the warnings are noise.
    """
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        Xs, Ys, Zs = ellipsoid_mesh(fit, sigma=sigma_solid)
        ax.plot_surface(
            Xs, Ys, Zs,
            color=colour, alpha=surface_alpha, linewidth=0, antialiased=True,
        )
        Xw, Yw, Zw = ellipsoid_mesh(fit, sigma=sigma_wire, n_u=22, n_v=12)
        ax.plot_wireframe(
            Xw, Yw, Zw,
            color=colour, alpha=wire_alpha, linewidth=0.5,
        )


def style_axes(ax, title: str) -> None:
    ax.set_xlabel("L*  (lightness)")
    ax.set_ylabel("a*  (green − / red +)")
    ax.set_zlabel("b*  (blue − / yellow +)")
    ax.set_title(title)
    ax.view_init(elev=18, azim=-58)


def build_legend(stamps, *, with_excluded: bool = True):
    handles = []
    for s in stamps:
        col = stamp_colour(s)
        handles.append(Line2D(
            [0], [0],
            marker="o", color="none", markerfacecolor=col,
            markeredgecolor="black", markersize=9,
            label=f"stamp {s}",
        ))
    if with_excluded:
        handles.append(Line2D(
            [0], [0],
            marker="o", color="none", markerfacecolor="none",
            markeredgecolor="#888888", markersize=9,
            label="excluded sample",
        ))
    return handles


def plot_all(samples: pd.DataFrame, save_to: str = "") -> None:
    fig = plt.figure(figsize=(17, 8))

    # Left: whole-stamp ellipsoids
    ax_w = fig.add_subplot(1, 2, 1, projection="3d")
    whole = fit_whole(samples)
    draw_scatter(ax_w, samples)
    for stamp, fit in sorted(whole.items()):
        # Centroid marker.
        L, a, b = fit.centroid_lab
        ax_w.scatter([L], [a], [b],
                     c=stamp_colour(stamp), s=140, marker="X",
                     edgecolors="black", linewidths=1.0)
        draw_ellipsoid(ax_w, fit, stamp_colour(stamp))
    style_axes(ax_w, "Whole-stamp ellipsoids\n(1σ surface, 2σ wireframe)")
    ax_w.legend(handles=build_legend(sorted(whole.keys())),
                loc="upper left", fontsize=9, framealpha=0.9)

    # Right: per-tone ellipsoids (smaller, nested inside each stamp's shell)
    ax_t = fig.add_subplot(1, 2, 2, projection="3d")
    per_tone = fit_per_tone(samples)
    draw_scatter(ax_t, samples)
    for (stamp, _tone), fit in sorted(per_tone.items()):
        col = stamp_colour(stamp)
        # Per-tone shells get a slightly stronger fill so they pop
        # against the scatter, and a thinner wireframe.
        draw_ellipsoid(
            ax_t, fit, col,
            surface_alpha=0.13, wire_alpha=0.30,
        )
        L, a, b = fit.centroid_lab
        ax_t.scatter([L], [a], [b],
                     c=col, s=60, marker="X",
                     edgecolors="black", linewidths=0.6)
    style_axes(ax_t, "Per-tone ellipsoids (k-means k=4)\nrelabelled by lightness")
    ax_t.legend(handles=build_legend(sorted({s for s, _ in per_tone.keys()})),
                loc="upper left", fontsize=9, framealpha=0.9)

    fig.suptitle(
        "Pasteur greens — stamps 170 / 171 / 172 / 174 in CIE Lab",
        fontsize=13, y=0.995,
    )
    fig.tight_layout()

    if save_to:
        fig.savefig(save_to, dpi=140, bbox_inches="tight")
        print(f"Saved figure → {save_to}")
    else:
        print("Showing interactive figure (close the window to exit) ...")
        plt.show()


def main() -> None:
    save_to = ""
    if "--save" in sys.argv:
        idx = sys.argv.index("--save")
        if idx + 1 < len(sys.argv):
            save_to = os.path.expanduser(sys.argv[idx + 1])
        else:
            save_to = os.path.expanduser("~/Desktop/all_green_pasteur_ellipsoids.png")

    if not os.path.exists(CSV_PATH):
        print(f"ERROR: {CSV_PATH} not found.")
        print("Run pilot_ellipsoid_all_4_samples.py first to generate it.")
        sys.exit(1)

    print(f"Loading {CSV_PATH} ...")
    samples = pd.read_csv(CSV_PATH)
    samples["stamp"] = samples["stamp"].astype(str)
    print(f"  {len(samples)} rows; "
          f"{int((~samples['excluded']).sum())} included, "
          f"{int(samples['excluded'].sum())} excluded")

    plot_all(samples, save_to=save_to)


if __name__ == "__main__":
    main()
