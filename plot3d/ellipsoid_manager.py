"""Ellipsoid manager for Plot_3D.

Peer of :mod:`plot3d.sphere_manager`. Renders translucent 1σ + 2σ
ellipsoid shells in normalized (Xnorm/Ynorm/Znorm) space for each
stamp present in the worksheet:

* **Whole-stamp mode** — one ellipsoid per stamp, fitted to all of
  that stamp's *included* (non-Excluded) samples.
* **Per-tone mode** — one ellipsoid per ``Cluster`` value within each
  stamp. Stamps with no populated ``Cluster`` are skipped in this
  mode (only whole-stamp is meaningful for them).

The manager intentionally **does not auto-cluster**. Tone counts vary
per stamp and the philatelic decision of how many tones a stamp has
belongs in StampZ's existing k-means manager, not here.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from utils.color_ellipsoid import (
    EllipsoidFit,
    ellipsoid_mesh,
    fit_ellipsoid,
    principal_axes,
)


# Default rendering parameters (translucent surfaces, no wireframe).
DEFAULT_SIGMA_INNER = 1.0
DEFAULT_ALPHA_INNER = 0.18
DEFAULT_SIGMA_OUTER = 2.0
DEFAULT_ALPHA_OUTER = 0.07

# Distinct colours for stamps. Cycled deterministically by sort order
# so the same stamp always gets the same colour across renders.
_STAMP_COLOUR_CYCLE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#17becf",
    "#bcbd22", "#7f7f7f",
]


class EllipsoidManager:
    """Render and toggle ellipsoid shells per stamp in a Plot_3D figure."""

    MODE_WHOLE = "whole"
    MODE_TONE = "tone"

    def __init__(self, ax, canvas, data_df: pd.DataFrame):
        self.ax = ax
        self.canvas = canvas
        self.data_df = data_df

        # Render state.
        self._artists: List = []                                      # mpl objects to clear on next render
        self._mode: str = self.MODE_WHOLE
        self._master_visible: bool = False                            # off by default
        self.visibility_states: Dict[str, bool] = {}                  # per-stamp on/off

        # Cached fits (lazy, invalidated by update_references()).
        self._fits_whole: Optional[Dict[str, EllipsoidFit]] = None
        self._fits_tone: Optional[Dict[Tuple[str, int], EllipsoidFit]] = None

        self.logger = logging.getLogger(__name__)

    # ----------------------------------------------------------------- #
    # Public API
    # ----------------------------------------------------------------- #

    def update_references(self, ax, canvas, data_df: pd.DataFrame) -> None:
        """Refresh axis/canvas/data references and invalidate fits."""
        self.ax = ax
        self.canvas = canvas
        self.data_df = data_df
        self._invalidate()
        # Stamps may have changed — preserve previous toggle state where possible.
        for stamp in self._discover_stamps():
            self.visibility_states.setdefault(stamp, True)

    def set_master_visible(self, visible: bool) -> None:
        self._master_visible = bool(visible)

    def is_master_visible(self) -> bool:
        return self._master_visible

    def set_mode(self, mode: str) -> None:
        if mode not in (self.MODE_WHOLE, self.MODE_TONE):
            raise ValueError(f"Unknown ellipsoid mode: {mode!r}")
        self._mode = mode

    def get_mode(self) -> str:
        return self._mode

    def toggle_visibility(self, stamp: str) -> None:
        self.visibility_states[stamp] = not self.visibility_states.get(stamp, True)

    def get_active_stamps(self) -> List[str]:
        """Stamps that currently have at least one fittable ellipsoid."""
        self._ensure_fits()
        if self._fits_whole is None:
            return []
        return sorted(self._fits_whole.keys())

    def stamp_has_tone_data(self, stamp: str) -> bool:
        """True if the stamp has any populated Cluster values."""
        self._ensure_fits()
        if self._fits_tone is None:
            return False
        return any(s == stamp for (s, _) in self._fits_tone.keys())

    def get_stamp_sample_counts(self) -> Dict[str, int]:
        """Sample-count per stamp after exclusion filter (for UI labels)."""
        self._ensure_fits()
        if not self._fits_whole:
            return {}
        return {s: f.n_samples for s, f in self._fits_whole.items()}

    def clear(self) -> None:
        """Remove all ellipsoid artists from the current axis."""
        for art in self._artists:
            try:
                art.remove()
            except Exception:
                pass
        self._artists = []

    def render(self) -> None:
        """Draw all visible ellipsoids on the current axis."""
        self.clear()
        if not self._master_visible:
            self._safe_draw()
            return
        self._ensure_fits()
        if self._fits_whole is None:
            self._safe_draw()
            return

        if self._mode == self.MODE_WHOLE:
            self._render_whole()
        else:
            self._render_tone()
        self._safe_draw()

    # ----------------------------------------------------------------- #
    # Internals: fitting
    # ----------------------------------------------------------------- #

    def _invalidate(self) -> None:
        self._fits_whole = None
        self._fits_tone = None

    def _ensure_fits(self) -> None:
        if self._fits_whole is None or self._fits_tone is None:
            self._fit_all()

    def _discover_stamps(self) -> List[str]:
        """Stamp identifiers present in data_df (parsed from DataID prefix)."""
        if self.data_df is None or "DataID" not in self.data_df.columns:
            return []
        ids = self.data_df["DataID"].dropna().astype(str)
        stamps = ids.str.split("-", n=1).str[0].str.strip().unique().tolist()
        return sorted(s for s in stamps if s)

    @staticmethod
    def _is_excluded(val) -> bool:
        if val is None:
            return False
        if isinstance(val, float) and np.isnan(val):
            return False
        return str(val).strip() != ""

    def _fit_all(self) -> None:
        """Build whole-stamp and per-tone fits from data_df."""
        self._fits_whole = {}
        self._fits_tone = {}

        df = self.data_df
        if df is None or len(df) == 0:
            return

        required = {"DataID", "Xnorm", "Ynorm", "Znorm"}
        if not required.issubset(df.columns):
            self.logger.warning(
                "EllipsoidManager: missing required columns (need %s)", required
            )
            return

        mask = (
            df["DataID"].notna()
            & df["Xnorm"].notna()
            & df["Ynorm"].notna()
            & df["Znorm"].notna()
        )
        sub = df[mask].copy()
        if len(sub) == 0:
            return

        sub["_stamp"] = sub["DataID"].astype(str).str.split("-", n=1).str[0].str.strip()
        if "Exclude" in sub.columns:
            sub["_excluded"] = sub["Exclude"].apply(self._is_excluded)
        else:
            sub["_excluded"] = False
        included = sub[~sub["_excluded"]]

        # Plot_3D plots in normalized [0, 1] space. The default `prior_variance`
        # in `fit_ellipsoid` is 4.0 — calibrated for Lab units (ΔE ~2 stddev),
        # which is 10000× too large here. With small per-tone clusters (n<10)
        # shrinkage kicks in and produces ellipsoids the size of the whole
        # plot. Use a normalized-space prior of ~(0.03)² per axis instead.
        norm_prior_variance = 0.001

        for stamp, group in included.groupby("_stamp"):
            pts = group[["Xnorm", "Ynorm", "Znorm"]].to_numpy(dtype=float)
            if pts.shape[0] < 2:
                continue
            try:
                self._fits_whole[stamp] = fit_ellipsoid(
                    pts, prior_variance=norm_prior_variance,
                )
            except Exception as e:
                self.logger.warning("Whole-stamp fit failed for %s: %s", stamp, e)

            if "Cluster" in group.columns:
                clustered = group[group["Cluster"].notna()]
                for cluster_val, cgroup in clustered.groupby("Cluster"):
                    cpts = cgroup[["Xnorm", "Ynorm", "Znorm"]].to_numpy(dtype=float)
                    if cpts.shape[0] < 2:
                        continue
                    try:
                        c_int = int(cluster_val)
                    except (TypeError, ValueError):
                        c_int = hash(str(cluster_val)) & 0xFFFF
                    try:
                        self._fits_tone[(stamp, c_int)] = fit_ellipsoid(
                            cpts, prior_variance=norm_prior_variance,
                        )
                    except Exception as e:
                        self.logger.warning(
                            "Per-tone fit failed for %s cluster %s: %s",
                            stamp, cluster_val, e,
                        )

    # ----------------------------------------------------------------- #
    # Internals: rendering
    # ----------------------------------------------------------------- #

    def _stamp_colour(self, stamp: str) -> str:
        stamps = sorted(self._fits_whole.keys()) if self._fits_whole else [stamp]
        try:
            idx = stamps.index(stamp)
        except ValueError:
            idx = 0
        return _STAMP_COLOUR_CYCLE[idx % len(_STAMP_COLOUR_CYCLE)]

    def _render_whole(self) -> None:
        for stamp, fit in (self._fits_whole or {}).items():
            if not self.visibility_states.get(stamp, True):
                continue
            self._draw_one(fit, self._stamp_colour(stamp))

    def _render_tone(self) -> None:
        for (stamp, _cluster), fit in (self._fits_tone or {}).items():
            if not self.visibility_states.get(stamp, True):
                continue
            self._draw_one(fit, self._stamp_colour(stamp))

    def _draw_one(self, fit: EllipsoidFit, colour: str) -> None:
        # Suppress matplotlib's divide/overflow warnings on near-degenerate
        # ellipsoids; render output is correct, the warnings are cosmetic.
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            try:
                Xi, Yi, Zi = ellipsoid_mesh(fit, sigma=DEFAULT_SIGMA_INNER)
                inner = self.ax.plot_surface(
                    Xi, Yi, Zi,
                    color=colour, alpha=DEFAULT_ALPHA_INNER,
                    linewidth=0, antialiased=True,
                )
                self._artists.append(inner)
            except Exception as e:
                self.logger.warning("Inner ellipsoid render failed: %s", e)
            try:
                Xo, Yo, Zo = ellipsoid_mesh(fit, sigma=DEFAULT_SIGMA_OUTER, n_u=22, n_v=12)
                outer = self.ax.plot_surface(
                    Xo, Yo, Zo,
                    color=colour, alpha=DEFAULT_ALPHA_OUTER,
                    linewidth=0, antialiased=True,
                )
                self._artists.append(outer)
            except Exception as e:
                self.logger.warning("Outer ellipsoid render failed: %s", e)

            # Centroid X marker — the mean coordinate ("middle tone" of the group).
            try:
                cx, cy, cz = fit.centroid_lab  # named for Lab but works for any 3D space
                marker = self.ax.scatter(
                    [cx], [cy], [cz],
                    c=colour, s=90, marker="X",
                    edgecolors="black", linewidths=0.8, depthshade=True,
                    zorder=40,
                )
                self._artists.append(marker)
            except Exception as e:
                self.logger.warning("Centroid marker failed: %s", e)

            # Major-axis line: short segment through the centroid along the
            # ellipsoid's longest principal eigenvector, length = 2σ extent.
            # Makes the elongation direction unambiguous at any view angle.
            try:
                vals, vecs = principal_axes(fit)
                major = vecs[:, 0]
                half = DEFAULT_SIGMA_OUTER * float(np.sqrt(max(vals[0], 0.0)))
                centre = fit.centroid
                p0 = centre - half * major
                p1 = centre + half * major
                axis_line, = self.ax.plot3D(
                    [p0[0], p1[0]], [p0[1], p1[1]], [p0[2], p1[2]],
                    color=colour, linewidth=1.4, alpha=0.85,
                    solid_capstyle="round", zorder=35,
                )
                self._artists.append(axis_line)
            except Exception as e:
                self.logger.warning("Major-axis line failed: %s", e)

    def _safe_draw(self) -> None:
        try:
            if self.canvas is not None:
                self.canvas.draw_idle()
        except Exception:
            pass
