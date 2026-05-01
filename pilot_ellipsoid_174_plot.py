#!/usr/bin/env python3
"""Visualize stamp 174's per-tone ellipsoids in Lab space.

Companion to ``pilot_ellipsoid_174_samples.py``: same data, same fits,
but rendered as a 3D matplotlib scene. Each cluster is drawn as

* a scatter of its included samples,
* the cluster centroid as a marker,
* a translucent 1σ ellipsoid (~68% contour),
* a wireframe 2σ ellipsoid (~95% contour).

The axes are L*, a*, b* — same coordinate system as the underlying
maths. Once the StampZ Plot_3D integration is built, the same
``ellipsoid_mesh`` helper can be plugged into ``sphere_manager.py``
alongside the existing sphere rendering.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

# Reuse the loader so this script stays in lock-step with the analysis pilot.
from pilot_ellipsoid_174_samples import (
    ODS_PATH,
    SHEET,
    fit_per_cluster,
    load_174,
)
from utils.color_ellipsoid import (
    EllipsoidFit,
    ellipsoid_mesh,
)


# Tone → matplotlib colour. Picked for visual contrast against a white axis,
# not for any colorimetric meaning — the data carries the actual colours.
TONE_COLOURS: Dict[str, str] = {
    "Green-Yellow": "#b8c918",
    "Green":        "#1f8f3d",
    "Green-Grey":   "#6e8a78",
    "Dark Green":   "#0e3d1d",
}


def colour_for(tone: str) -> str:
    """Look up plotting colour, falling back to a deterministic default."""
    return TONE_COLOURS.get(tone, "#444444")


def plot_174(
    samples: pd.DataFrame,
    cluster_to_tone: Dict[int, str],
    fits: Dict[int, EllipsoidFit],
    save_to: str = "",
) -> None:
    fig = plt.figure(figsize=(11, 9))
    ax = fig.add_subplot(111, projection="3d")

    legend_handles = []

    for cluster, fit in sorted(fits.items()):
        tone = cluster_to_tone.get(cluster, f"cluster {cluster}")
        col = colour_for(tone)

        # 1σ surface (translucent) — matches sphere_manager's ALPHA = 0.15.
        X1, Y1, Z1 = ellipsoid_mesh(fit, sigma=1.0)
        ax.plot_surface(
            X1, Y1, Z1,
            color=col, alpha=0.15, linewidth=0, antialiased=True,
        )

        # 2σ surface as a sparse wireframe — visible "outer envelope".
        X2, Y2, Z2 = ellipsoid_mesh(fit, sigma=2.0, n_u=20, n_v=12)
        ax.plot_wireframe(
            X2, Y2, Z2,
            color=col, alpha=0.30, linewidth=0.5,
        )

        # Sample scatter (included samples only).
        sub = samples[(samples["cluster_int"] == cluster) & (~samples["excluded"])]
        ax.scatter(
            sub["L"], sub["a"], sub["b"],
            c=col, s=22, edgecolors="black", linewidths=0.4, depthshade=True,
        )

        # Centroid marker, same colour, larger and outlined for emphasis.
        L, a, b = fit.centroid_lab
        ax.scatter(
            [L], [a], [b],
            c=col, s=120, marker="X", edgecolors="black", linewidths=1.0,
        )

        legend_handles.append(
            Line2D(
                [0], [0],
                marker="o", color="none", markerfacecolor=col,
                markeredgecolor="black", markersize=9,
                label=f"{tone}  (n={fit.n_samples})",
            )
        )

    # Excluded samples: hollow grey markers, so they're visible but clearly
    # set apart from the included data.
    excluded = samples[samples["excluded"]]
    if not excluded.empty:
        ax.scatter(
            excluded["L"], excluded["a"], excluded["b"],
            facecolors="none", edgecolors="#888888", s=28, linewidths=0.7,
        )
        legend_handles.append(
            Line2D(
                [0], [0],
                marker="o", color="none", markerfacecolor="none",
                markeredgecolor="#888888", markersize=9,
                label=f"excluded  (n={len(excluded)})",
            )
        )

    ax.set_xlabel("L*  (lightness)")
    ax.set_ylabel("a*  (green − / red +)")
    ax.set_zlabel("b*  (blue − / yellow +)")
    ax.set_title("Stamp 174 — per-tone ellipsoids in CIE Lab\n"
                 "translucent surface = 1σ contour,  wireframe = 2σ contour")
    ax.legend(handles=legend_handles, loc="upper left", fontsize=9, framealpha=0.9)

    # A consistent viewing angle so screenshots are reproducible.
    ax.view_init(elev=18, azim=-58)
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
            save_to = os.path.expanduser("~/Desktop/174_ellipsoids.png")

    print(f"Loading {ODS_PATH} (sheet={SHEET!r}) ...")
    samples, cluster_to_tone = load_174(ODS_PATH, SHEET)
    fits = fit_per_cluster(samples, cluster_to_tone)
    print(f"Plotting {len(fits)} cluster ellipsoids over "
          f"{int((~samples['excluded']).sum())} included samples "
          f"({int(samples['excluded'].sum())} excluded)")
    plot_174(samples, cluster_to_tone, fits, save_to=save_to)


if __name__ == "__main__":
    main()
