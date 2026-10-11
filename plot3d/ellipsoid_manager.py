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
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from matplotlib.transforms import IdentityTransform

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

# How far the major-axis trend line extends from the centroid, expressed
# in sigmas of the longest principal axis. The 2σ outer shell ends at
# `DEFAULT_SIGMA_OUTER`; setting this higher (3.0) makes the line poke
# visibly *beyond* the ellipsoid surface so the elongation direction
# stays readable even when the ellipsoid is dense or viewed end-on.
DEFAULT_AXIS_EXTENT = 3.0

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

    def __init__(
        self,
        ax,
        canvas,
        data_df: pd.DataFrame,
        is_color_visible: Optional[Callable[[str], bool]] = None,
    ):
        self.ax = ax
        self.canvas = canvas
        self.data_df = data_df
        # Optional callback: given a raw colour name from the worksheet's
        # Color/Sphere column (e.g. 'red', 'green'), return True if it
        # should currently be rendered. Plot_3D wires this to the sphere
        # visibility panel so toggling a sphere colour hides the matching
        # ellipsoids too — unified per-colour visibility without adding
        # a second checkbox panel for ellipsoids.
        self.is_color_visible: Optional[Callable[[str], bool]] = is_color_visible

        # Render state.
        self._artists: List = []
        self._stats_artist = None
        self._corner_artists = {}
        self._corner_click_id = None
        # Remember the statistics panel position across plot refreshes.
        self._stats_corner = "upper_right"                                             
        # mpl objects to clear on next render
        self._mode: str = self.MODE_WHOLE
        self._master_visible: bool = False                            # off by default
        self.visibility_states: Dict[str, bool] = {}                  # per-stamp on/off

        # Cached fits (lazy, invalidated by update_references()).
        self._fits_whole: Optional[Dict[str, EllipsoidFit]] = None
        self._fits_tone: Optional[Dict[Tuple[str, int], EllipsoidFit]] = None
        # Per-tone sphere colour, harvested from the data rows' Color
        # column at fit time. None when no explicit colour is set in the
        # worksheet — callers fall back to the per-stamp cycling colour.
        self._tone_colour: Dict[Tuple[str, int], Optional[str]] = {}

        self.logger = logging.getLogger(__name__)

        # Connect corner selection once for this canvas.
        self._corner_click_id = self.canvas.mpl_connect(
            "pick_event", self._on_corner_pick
        )

    # ----------------------------------------------------------------- #
    # Public API
    # ----------------------------------------------------------------- #

    def update_references(self, ax, canvas, data_df: pd.DataFrame) -> None:
        """Refresh axis/canvas/data references and invalidate fits."""
        # Discard the old statistics panel when plot references refresh.
        if self._stats_artist is not None:
            try:
                self._stats_artist.remove()
            except (ValueError, AttributeError):
                pass
            self._stats_artist = None
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

    def get_render_traces(self) -> List[Dict]:
        """Return serializable trace specs for the currently visible ellipsoids.

        Each dict describes one ellipsoid in a renderer-agnostic form so that
        downstream code (matplotlib, Plotly, Plot_3D's exports, ad-hoc scripts)
        can lay it out however it likes. Reflects all current state: master
        toggle, mode (whole/per-tone), per-stamp toggles, and the optional
        ``is_color_visible`` callback.

        Keys per trace:
            ``label``       — human-readable name ("stamp 170", "stamp 174 cluster 2")
            ``colour``      — colour name / hex compatible with matplotlib & Plotly
            ``centroid``    — (x, y, z) tuple in plot space
            ``mesh_inner``  — (X, Y, Z) grids for the 1σ surface
            ``mesh_outer``  — (X, Y, Z) grids for the 2σ surface
            ``axis_line``   — ((x0,y0,z0), (x1,y1,z1)) for the major-axis segment
            ``n_samples``   — included-sample count for hover labels
        Returns an empty list when the master toggle is off or there are no
        ellipsoids to render in the current mode.
        """
        if not self._master_visible:
            return []
        self._ensure_fits()
        traces: List[Dict] = []
        if self._mode == self.MODE_WHOLE:
            for stamp, fit in (self._fits_whole or {}).items():
                if not self.visibility_states.get(stamp, True):
                    continue
                colour = self._stamp_colour(stamp)
                traces.append(self._make_trace_spec(
                    f"stamp {stamp}", fit, colour,
                ))
        else:
            for (stamp, cluster), fit in (self._fits_tone or {}).items():
                if not self.visibility_states.get(stamp, True):
                    continue
                raw_colour = self._tone_colour.get((stamp, cluster))
                if raw_colour and self.is_color_visible is not None:
                    try:
                        if not self.is_color_visible(raw_colour):
                            continue
                    except Exception:
                        pass
                colour = raw_colour or self._stamp_colour(stamp)
                traces.append(self._make_trace_spec(
                    f"stamp {stamp} cluster {cluster}", fit, colour,
                ))
        return traces

    def _make_trace_spec(self, label: str, fit: EllipsoidFit, colour: str) -> Dict:
        """Build the renderer-agnostic dict described in ``get_render_traces``."""
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            Xi, Yi, Zi = ellipsoid_mesh(fit, sigma=DEFAULT_SIGMA_INNER)
            Xo, Yo, Zo = ellipsoid_mesh(
                fit, sigma=DEFAULT_SIGMA_OUTER, n_u=22, n_v=12,
            )
            vals, vecs = principal_axes(fit)
            major = vecs[:, 0]
            half = DEFAULT_AXIS_EXTENT * float(np.sqrt(max(vals[0], 0.0)))
            centre = fit.centroid
            p0 = centre - half * major
            p1 = centre + half * major
        return {
            "label": label,
            "colour": colour,
            "centroid": tuple(float(v) for v in fit.centroid),
            "mesh_inner": (Xi, Yi, Zi),
            "mesh_outer": (Xo, Yo, Zo),
            "axis_line": (
                tuple(float(v) for v in p0),
                tuple(float(v) for v in p1),
            ),
            "n_samples": int(fit.n_samples),
        }

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
            self._update_stats_display()
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

        self._update_stats_display()
        self._safe_draw()

    # ----------------------------------------------------------------- #
    # Internals: fitting
    # ----------------------------------------------------------------- #

    def _invalidate(self) -> None:
        self._fits_whole = None
        self._fits_tone = None
        self._tone_colour = {}

    def _ensure_fits(self) -> None:
        if self._fits_whole is None or self._fits_tone is None:
            self._fit_all()

    def _discover_stamps(self) -> List[str]:
        """Stamp identifiers present in data_df (parsed from DataID prefix).

        Splits on "-" first (e.g. "170-001" → stamp "170").  When no
        hyphens are found anywhere, all valid data points are grouped
        under a single stamp called "all".
        """
        if self.data_df is None or "DataID" not in self.data_df.columns:
            return []
        ids = self.data_df["DataID"].dropna().astype(str)
        if ids.empty:
            return []
        # Try hyphen-based grouping first
        prefixes = ids.str.split("-", n=1).str[0].str.strip()
        stamps = prefixes.unique().tolist()
        stamps = sorted(s for s in stamps if s)
        # Use "all" grouping when this looks like averaged/combined data
        # (one or a few measurements per stamp) rather than individual-scan
        # data (many scans of the same stamp).  The heuristic: if no prefix
        # appears more than 3 times, it is averaged data and per-cluster
        # ellipsoids across the whole dataset are more meaningful than
        # per-stamp ellipsoids (most of which would have only 1 point).
        valid_count = len(ids)
        if valid_count >= 2:
            freq = ids.str.split("-", n=1).str[0].str.strip().value_counts()
            if freq.iloc[0] <= 3:          # max count of any single stamp prefix
                return ["all"]
        return stamps

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

        # Parse stamp prefix from DataID; use "all" for averaged/combined
        # data (no prefix appears more than 3 times) so per-cluster ellipsoids
        # span the whole dataset, matching what _discover_stamps() returns.
        prefixes = sub["DataID"].astype(str).str.split("-", n=1).str[0].str.strip()
        max_freq = prefixes.value_counts().iloc[0] if len(prefixes) > 0 else 0
        if max_freq <= 3 and len(prefixes) >= 2:
            sub["_stamp"] = "all"
        else:
            sub["_stamp"] = prefixes
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

        # Build cluster-id → Sphere colour from the centroid summary rows.
        # Those rows have valid Centroid_X/Y/Z but NaN Xnorm/Ynorm/Znorm, so
        # they were excluded from `sub` above.  We look them up in the full
        # df here so each ellipsoid gets the colour the user chose for that
        # cluster's sphere marker rather than the mode of the data-row Color
        # column (which colours individual scatter points, not clusters).
        centroid_sphere_map: Dict[Tuple[str, int], str] = {}
        if (
            "Sphere" in df.columns
            and "Centroid_X" in df.columns
            and "Cluster" in df.columns
        ):
            cen_mask = (
                df["Cluster"].notna()
                & df["Centroid_X"].notna()
                & df["Sphere"].notna()
                & df["Xnorm"].isna()      # centroid rows have no norm coords
            )
            for _, crow in df[cen_mask].iterrows():
                try:
                    c_id = int(float(crow["Cluster"]))
                    sph = str(crow["Sphere"]).strip()
                    if sph:
                        centroid_sphere_map[c_id] = sph
                except (TypeError, ValueError):
                    pass

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
                    self.logger.info(
                        "Ellipsoid fit: stamp=%s cluster=%s points=%d",
                        stamp, cluster_val, cpts.shape[0],
                    )
                    if cpts.shape[0] < 2:
                        self.logger.info("  Skipped (need ≥2 points)")
                        continue
                    try:
                        c_int = int(cluster_val)
                    except (TypeError, ValueError):
                        c_int = hash(str(cluster_val)) & 0xFFFF
                    try:
                        self._fits_tone[(stamp, c_int)] = fit_ellipsoid(
                            cpts, prior_variance=norm_prior_variance,
                        )
                        # Primary: use the Sphere colour the user set on the
                        # centroid row for this cluster.  Fall back to the
                        # mode of the data rows' Color column so legacy
                        # datasets without centroid Sphere values still work.
                        if c_int in centroid_sphere_map:
                            self._tone_colour[(stamp, c_int)] = (
                                centroid_sphere_map[c_int]
                            )
                        else:
                            try:
                                colours = (
                                    cgroup["Color"].dropna().astype(str).str.strip()
                                    if "Color" in cgroup.columns else None
                                )
                                if colours is not None and not colours.empty:
                                    mode_series = colours.mode()
                                    if not mode_series.empty:
                                        self._tone_colour[(stamp, c_int)] = (
                                            str(mode_series.iloc[0])
                                        )
                            except Exception as ce:
                                self.logger.debug(
                                    "Colour harvest failed for %s/%s: %s",
                                    stamp, cluster_val, ce,
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
        for (stamp, cluster), fit in (self._fits_tone or {}).items():
            if not self.visibility_states.get(stamp, True):
                continue
            raw_colour = self._tone_colour.get((stamp, cluster))
            # Honour the shared Sphere / Ellipsoid Visibility toggle: if the
            # colour assigned to this cluster has been toggled off in the
            # panel, skip the ellipsoid as well as the sphere.
            if raw_colour and self.is_color_visible is not None:
                try:
                    if not self.is_color_visible(raw_colour):
                        continue
                except Exception:
                    pass
            colour = raw_colour or self._stamp_colour(stamp)
            self._draw_one(fit, colour)

    def _draw_one(self, fit: EllipsoidFit, colour: str) -> None:
        # Suppress matplotlib's divide/overflow warnings on near-degenerate
        # ellipsoids; render output is correct, the warnings are cosmetic.
        #
        # Only draw the outer 2σ shell.  Drawing both 1σ and 2σ shells
        # causes a visually confusing “sphere inside another sphere” effect
        # when the cluster is approximately isotropic (especially in per-tone
        # mode where each cluster is tight and the two shells look identical).
        # A single semi-transparent 2σ shell conveys the cluster extent
        # clearly; the major-axis line below shows the elongation direction.
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            try:
                Xo, Yo, Zo = ellipsoid_mesh(fit, sigma=DEFAULT_SIGMA_OUTER, n_u=22, n_v=12)
                outer = self.ax.plot_surface(
                    Xo, Yo, Zo,
                    color=colour, alpha=DEFAULT_ALPHA_INNER,  # use inner alpha — slightly more opaque
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
            # ellipsoid's longest principal eigenvector, length controlled
            # by ``DEFAULT_AXIS_EXTENT`` (sigmas). With the default of 3σ
            # the line extends past the 2σ outer surface so the
            # elongation direction stays readable from any view angle.
            try:
                vals, vecs = principal_axes(fit)
                major = vecs[:, 0]
                half = DEFAULT_AXIS_EXTENT * float(np.sqrt(max(vals[0], 0.0)))
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

    def _update_stats_display(self) -> None:
        """Display geometric statistics for visible ellipsoids."""
        # Remove the previous corner-selector controls.
        for artist in self._corner_artists.values():
            try:
                artist.remove()
            except (ValueError, AttributeError):
                pass
        self._corner_artists = {}
        if self._stats_artist is not None:
            try:
                self._stats_artist.remove()
            except (ValueError, AttributeError):
                pass
            self._stats_artist = None

        if not self._master_visible:
            return

        self._ensure_fits()
        lines = [
            "ELLIPSOID STATISTICS",
            "",
            "Position:",
            "",
        ]

        if self._mode == self.MODE_WHOLE:
            candidates = [
                (f"All / {stamp}", fit)
                for stamp, fit in (self._fits_whole or {}).items()
                if self.visibility_states.get(stamp, True)
            ]
        else:
            candidates = []
            for (stamp, cluster), fit in (self._fits_tone or {}).items():
                if not self.visibility_states.get(stamp, True):
                    continue

                colour = self._tone_colour.get((stamp, cluster))
                if colour and self.is_color_visible is not None:
                    if not self.is_color_visible(colour):
                        continue

                candidates.append((f"Cluster {cluster}", fit))

        for label, fit in candidates:
            vals, _ = principal_axes(fit)
            diameters = 4.0 * np.sqrt(np.maximum(vals, 0.0))

            minor = float(diameters[2])
            elongation = (
                float(diameters[0]) / minor
                if minor > 0 else float("inf")
            )

            lines.extend([
                "",
                f"{label}  (N={fit.n_samples})",
                f"Major:  {diameters[0]:.4f}",
                f"Middle: {diameters[1]:.4f}",
                f"Minor:  {diameters[2]:.4f}",
                f"Ratio:  {elongation:.2f}:1",
            ])

        if not candidates:
            return

        corners = {
            "upper_right": (0.98, 0.98, "right", "top"),
            "lower_right": (0.98, 0.02, "right", "bottom"),
            "lower_left": (0.02, 0.02, "left", "bottom"),
            "upper_left": (0.02, 0.98, "left", "top"),
        }
        x, y, ha, va = corners[self._stats_corner]      

        self._stats_artist = self.ax.text2D(
            x, y,
            "\n".join(lines),
            transform=self.ax.transAxes,
            ha=ha,
            va=va,
            fontsize=10,
            fontfamily="sans-serif",
            color="black",
            bbox=dict(
                boxstyle="round,pad=0.5",
                facecolor="#FFFDF0",
                edgecolor="#555555",
                alpha=0.97,
            ),
            zorder=100,
        )

        # Measure the rendered statistics panel for selector alignment.
        renderer = self.canvas.get_renderer()
        stats_bbox = self._stats_artist.get_window_extent(renderer=renderer)

        # Position the four controls in one row inside the panel.
        # Coordinates are in display pixels.
        # Center the controls on the blank line following "Position:".
        line_height = self._stats_artist.get_fontsize() * self.ax.figure.dpi / 72 * 1.2
        row_y = stats_bbox.ymax - 3.5 * line_height

        labels = ("TL", "TR", "BL", "BR")
        spacing = 32
        row_width = (len(labels) - 1) * spacing
        start_x = (stats_bbox.xmin + stats_bbox.xmax - row_width) / 2

        positions = {
            label: (start_x + i * spacing, row_y)
            for i, label in enumerate(labels)
        }

        for label, (px, py) in positions.items():
            self._corner_artists[label] = self.ax.text2D(
                px, py,
                label,
                transform=IdentityTransform(),
                ha="center",
                va="center",
                fontsize=9,
                fontweight="bold",
                color="black",
                bbox=dict(
                    boxstyle="round,pad=0.2",
                    facecolor="#FFFDF0",
                    edgecolor="#777777",
                ),
                zorder=101,
            )

            self._corner_artists[label].set_picker(True)
            print(
                f"DEBUG CORNER CREATED: {label}, "
                f"picker={self._corner_artists[label].get_picker()}, "
                f"axes_active={self._corner_artists[label].axes is self.ax}"
            )

    def _on_corner_pick(self, event) -> None:
        """Move the statistics panel when a corner label is clicked."""
        print(f"DEBUG CORNER PICK: artist={event.artist!r}")
        if event.mouseevent.button != 1:
            return

        corners = {
            "TL": "upper_left",
            "TR": "upper_right",
            "BL": "lower_left",
            "BR": "lower_right",
        }

        for label, artist in self._corner_artists.items():
            if event.artist is artist:
                self._stats_corner = corners[label]
                self._update_stats_display()
                self._safe_draw()
                return

    def _safe_draw(self) -> None:
        try:
            if self.canvas is not None:
                self.canvas.draw_idle()
        except Exception:
            pass
