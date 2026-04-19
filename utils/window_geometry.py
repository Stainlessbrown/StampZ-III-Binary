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


def _is_geometry_reasonable(x: int, y: int, w: int, h: int) -> bool:
    """Permissive sanity check for a saved Tk geometry.
    
    We deliberately do NOT try to verify the rect is on a connected
    monitor: macOS Tk often reports ``winfo_vrootwidth`` as only the
    primary display's width, which would cause us to wrongly reject any
    saved position on a secondary monitor.
    
    Instead we just reject obviously absurd values. If the user ends up
    with a genuinely off-screen saved window, they can reset via the
    Close All menu item or by deleting ``window_geometry`` from
    ``preferences.json``.
    """
    if w < 200 or h < 150:
        return False
    # Very wide bounds: accommodates multi-monitor setups with displays
    # placed anywhere in the virtual desktop, while still rejecting
    # corrupted values.
    MAX = 20000
    if x < -MAX or x > MAX:
        return False
    if y < -MAX or y > MAX:
        return False
    return True


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
    
    1. Saved geometry for ``key`` (if the values look plausible).
    2. Centered on the primary display at ``default_size_ratio`` — this
       matches the pre-existing behavior of StampZ windows, so first-time
       opens aren't surprising.
    
    ``parent`` is accepted for forward compatibility but is intentionally
    not used for placement: centering the fallback on the parent window
    caused the new window to swallow the main app on multi-monitor setups
    (the parent and the 90%-of-primary child have very different sizes).
    
    ``min_width`` / ``min_height`` are used as lower bounds.
    """
    del parent  # accepted for API stability; see docstring
    
    # 1) Try saved geometry
    saved = load_saved_geometry(key)
    if saved:
        parsed = _parse_geometry(saved)
        if parsed is not None:
            w, h, x, y = parsed
            if _is_geometry_reasonable(x, y, w, h):
                try:
                    root.geometry(saved)
                    return
                except Exception as e:
                    print(
                        f"window_geometry: saved geometry '{saved}' for "
                        f"'{key}' could not be applied: {e}"
                    )
    
    # 2) Primary-display centered fallback (pre-existing behavior).
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
