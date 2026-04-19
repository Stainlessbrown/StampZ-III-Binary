#!/usr/bin/env python3
"""
Window geometry persistence helper for StampZ-III.

Provides save/restore helpers so that Toplevel windows remember their
position and size across sessions, including across multiple monitors.

Geometry strings follow the standard Tk format: ``"WxH+X+Y"`` where X/Y
may be negative (for secondary monitors placed to the left/above the
primary display on some platforms).

Behavior:
    * On close, call :func:`save_window_geometry(root, key)` to persist
      the current position and size under ``key``.
    * On open, call :func:`apply_window_geometry(root, key, ...)` which
      will:
        1. If a saved geometry exists AND is still at least partially
           visible on some connected monitor, reuse it.
        2. Otherwise, center on the parent window's current monitor.
        3. Otherwise, fall back to the primary display using the
           supplied default size ratio.

The persisted values live in ``preferences.json`` under the top-level
``window_geometry`` dictionary (keyed by the caller-supplied name).
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

# Matches "WxH+X+Y" or "WxH-X-Y" or mixed signs, with optional whitespace.
_GEOMETRY_RE = re.compile(
    r"^\s*(\d+)x(\d+)([+-]\d+)([+-]\d+)\s*$"
)


def _parse_geometry(geom: str) -> Optional[Tuple[int, int, int, int]]:
    """Parse a Tk ``WxH+X+Y`` geometry string into ``(w, h, x, y)``.

    Returns ``None`` if the string does not match the expected format.
    """
    if not geom:
        return None
    m = _GEOMETRY_RE.match(geom)
    if not m:
        return None
    try:
        w = int(m.group(1))
        h = int(m.group(2))
        x = int(m.group(3))
        y = int(m.group(4))
        return w, h, x, y
    except ValueError:
        return None


def _is_rect_on_any_monitor(root, x: int, y: int, w: int, h: int) -> bool:
    """Return True if at least a reasonable slice of the rect is visible.

    Tk doesn't give us a per-monitor API directly, but ``winfo_vrootwidth``
    /``winfo_vrootheight`` and ``winfo_screenwidth``/``winfo_screenheight``
    together approximate the virtual desktop on most platforms. We require
    at least 100 px of the window (in each dimension) to lie within the
    virtual desktop rectangle so a disconnected monitor doesn't strand
    the window off-screen.
    """
    try:
        vx = root.winfo_vrootx()
        vy = root.winfo_vrooty()
        vw = root.winfo_vrootwidth() or root.winfo_screenwidth()
        vh = root.winfo_vrootheight() or root.winfo_screenheight()
    except Exception:
        return False

    # Virtual desktop rect
    vr_left, vr_top = vx, vy
    vr_right, vr_bottom = vx + vw, vy + vh

    # Window rect
    wr_left, wr_top = x, y
    wr_right, wr_bottom = x + w, y + h

    # Intersection
    ix = max(0, min(wr_right, vr_right) - max(wr_left, vr_left))
    iy = max(0, min(wr_bottom, vr_bottom) - max(wr_top, vr_top))

    # Require at least 100x100 px of visibility to consider the saved
    # geometry still usable.
    return ix >= 100 and iy >= 100


def _get_prefs_manager():
    """Return the shared PreferencesManager, or None if unavailable."""
    try:
        from utils.user_preferences import get_preferences_manager
        return get_preferences_manager()
    except Exception as e:
        print(f"window_geometry: could not load preferences manager: {e}")
        return None


def load_saved_geometry(key: str) -> Optional[str]:
    """Return the saved Tk geometry string for ``key`` or ``None``."""
    pm = _get_prefs_manager()
    if pm is None:
        return None
    try:
        return pm.get_window_geometry(key)
    except Exception as e:
        print(f"window_geometry: failed to load geometry for '{key}': {e}")
        return None


def save_window_geometry(root, key: str) -> bool:
    """Persist ``root``'s current geometry under ``key``.

    Safe to call in a ``WM_DELETE_WINDOW`` handler; silently no-ops on
    any error so window close isn't blocked.
    """
    if not key or root is None:
        return False
    try:
        # Ensure geometry reflects any recent size changes
        root.update_idletasks()
        geom = root.geometry()
    except Exception as e:
        print(f"window_geometry: could not read geometry for '{key}': {e}")
        return False

    parsed = _parse_geometry(geom)
    if parsed is None:
        # Some platforms can briefly report "1x1+0+0" while minimizing.
        return False
    w, h, _, _ = parsed
    if w < 50 or h < 50:
        return False

    pm = _get_prefs_manager()
    if pm is None:
        return False
    try:
        return pm.set_window_geometry(key, geom)
    except Exception as e:
        print(f"window_geometry: failed to save geometry for '{key}': {e}")
        return False


def apply_window_geometry(
    root,
    key: str,
    parent=None,
    default_size_ratio: float = 0.9,
    min_width: int = 800,
    min_height: int = 600,
) -> None:
    """Apply a sensible starting geometry to ``root``.

    Priority order:

    1. Saved geometry for ``key`` (if still on-screen).
    2. Centered on ``parent``'s current monitor (so the window opens on
       whichever display the main app window is on).
    3. Centered on the primary display at ``default_size_ratio``.

    ``min_width`` / ``min_height`` are used as lower bounds when falling
    back to the primary display.
    """
    # Make sure the window knows its screen metrics.
    try:
        root.update_idletasks()
    except Exception:
        pass

    # 1) Try saved geometry
    saved = load_saved_geometry(key)
    if saved:
        parsed = _parse_geometry(saved)
        if parsed is not None:
            w, h, x, y = parsed
            if _is_rect_on_any_monitor(root, x, y, w, h):
                try:
                    root.geometry(saved)
                    return
                except Exception as e:
                    print(
                        f"window_geometry: saved geometry '{saved}' for "
                        f"'{key}' could not be applied: {e}"
                    )

    # 2) Fall back to parent-centered placement
    if parent is not None:
        try:
            parent.update_idletasks()
            px = parent.winfo_x()
            py = parent.winfo_y()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            # Use a sane default size relative to the parent's screen
            screen_w = root.winfo_screenwidth()
            screen_h = root.winfo_screenheight()
            w = max(min_width, int(screen_w * default_size_ratio))
            h = max(min_height, int(screen_h * default_size_ratio))
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            root.geometry(f"{w}x{h}+{x}+{y}")
            return
        except Exception as e:
            print(
                f"window_geometry: parent-centered fallback failed for "
                f"'{key}': {e}"
            )

    # 3) Final fallback: primary-display centered
    try:
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        w = max(min_width, int(screen_w * default_size_ratio))
        h = max(min_height, int(screen_h * default_size_ratio))
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")
    except Exception as e:
        print(f"window_geometry: primary-display fallback failed for '{key}': {e}")
