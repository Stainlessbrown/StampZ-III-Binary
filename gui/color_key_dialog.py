#!/usr/bin/env python3
"""
Colour Key Dialog for StampZ

Displays library colours as physical-style swatches — solid colour rectangles
with a transparent oval window in the centre — in a scrollable grid.  A stamp
image can be loaded and panned underneath the swatches so the user can compare
the stamp's colour to each reference by looking through the oval, exactly as
the Stanley Gibbons and Michel printed colour keys work.

Usage:
    from gui.color_key_dialog import open_color_key
    open_color_key(parent, app=self)
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk


class ColorKeyDialog:
    """Physical-style colour key using library swatches."""

    # Default swatch geometry — user can change columns at runtime
    SWATCH_W = 200   # swatch width  (px)
    SWATCH_H = 150   # swatch height (px)
    OVAL_W   = 100   # transparent window width
    OVAL_H   = 70    # transparent window height
    COLS     = 4     # swatches per row
    GAP      = 8     # gap between swatches

    def __init__(self, parent, app=None):
        self.parent = parent
        self._app   = app

        # Library / colour data
        self._library    = None
        self._all_colors = []   # List[LibraryColor] for the current filter
        self._swatches   = []   # List of (name, RGBA PIL Image)

        # Stamp image pan state
        self._stamp_pil     = None   # PIL Image (RGB) at original resolution
        self._stamp_display = None   # cached scaled version used for rendering
        self._stamp_offset  = [0, 0]
        self._drag_start    = None
        self._photo_ref     = None   # keep reference to prevent GC

        # Build window
        self.root = tk.Toplevel(parent)
        self.root.title("Colour Key")
        self.root.minsize(700, 450)
        try:
            if app and hasattr(app, "root"):
                w = app.root.winfo_width()
                h = app.root.winfo_height()
                self.root.geometry(f"{max(w, 900)}x{max(h, 600)}")
            else:
                self.root.geometry("1200x800")
        except Exception:
            self.root.geometry("1200x800")

        self._build_ui()
        self._load_library_list()

    # ================================================================ #
    # UI construction
    # ================================================================ #

    def _build_ui(self):
        # ── Top toolbar ─────────────────────────────────────────────
        tb = ttk.Frame(self.root)
        tb.pack(fill=tk.X, padx=8, pady=4)

        ttk.Label(tb, text="Library:").pack(side=tk.LEFT)
        self._lib_var = tk.StringVar()
        self._lib_combo = ttk.Combobox(tb, textvariable=self._lib_var,
                                       state="readonly", width=22)
        self._lib_combo.pack(side=tk.LEFT, padx=(2, 8))
        self._lib_combo.bind("<<ComboboxSelected>>", self._on_library_changed)

        ttk.Label(tb, text="Hue:").pack(side=tk.LEFT)
        self._hue_var = tk.StringVar(value="All Colors")
        self._hue_combo = ttk.Combobox(tb, textvariable=self._hue_var,
                                       state="readonly", width=18)
        self._hue_combo.pack(side=tk.LEFT, padx=(2, 8))
        self._hue_combo.bind("<<ComboboxSelected>>", self._on_hue_changed)

        ttk.Button(tb, text="🔄 Refresh",
                   command=self._refresh_swatches).pack(side=tk.LEFT, padx=4)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT,
                                                    fill=tk.Y, padx=10)

        ttk.Button(tb, text="📂 Open Stamp Image",
                   command=self._open_stamp).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="✖ Clear",
                   command=self._clear_stamp).pack(side=tk.LEFT, padx=2)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT,
                                                    fill=tk.Y, padx=10)

        ttk.Label(tb, text="Columns:").pack(side=tk.LEFT)
        self._cols_var = tk.IntVar(value=self.COLS)
        ttk.Spinbox(tb, from_=1, to=8, width=3,
                    textvariable=self._cols_var,
                    command=self._refresh_swatches).pack(side=tk.LEFT, padx=2)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT,
                                                    fill=tk.Y, padx=10)

        ttk.Label(tb, text="Stamp Scale:").pack(side=tk.LEFT, padx=(0, 4))
        self._scale_var = tk.IntVar(value=40)   # 40 % default
        for pct in (40, 60):
            ttk.Radiobutton(
                tb, text=f"{pct}%", value=pct,
                variable=self._scale_var,
                command=self._on_scale_changed,
            ).pack(side=tk.LEFT, padx=2)

        # Status (right-aligned)
        self._status = ttk.Label(tb, text="Select a library to begin.",
                                 foreground="gray")
        self._status.pack(side=tk.RIGHT, padx=8)

        # ── Scrollable canvas ────────────────────────────────────────
        cf = ttk.Frame(self.root)
        cf.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 2))

        self._canvas = tk.Canvas(cf, bg="#404040", cursor="fleur",
                                 highlightthickness=0)
        vsb = ttk.Scrollbar(cf, orient=tk.VERTICAL,
                            command=self._canvas.yview)
        hsb = ttk.Scrollbar(cf, orient=tk.HORIZONTAL,
                            command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=vsb.set,
                               xscrollcommand=hsb.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        cf.grid_rowconfigure(0, weight=1)
        cf.grid_columnconfigure(0, weight=1)

        # Bindings
        self._canvas.bind("<ButtonPress-1>",   self._on_pan_start)
        self._canvas.bind("<B1-Motion>",       self._on_pan_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_pan_end)
        self._canvas.bind("<MouseWheel>",      self._on_scroll)
        self._canvas.bind("<Button-4>",        self._on_scroll)
        self._canvas.bind("<Button-5>",        self._on_scroll)
        self._canvas.bind("<Configure>",
                          lambda _e: self._render())

        # ── Help bar ─────────────────────────────────────────────────
        ttk.Label(
            self.root,
            text=(
                "Drag to pan the stamp image under the swatches  ·  "
                "Look through the oval window to compare each swatch to the stamp"
            ),
            font=("Arial", 9),
            foreground="#666",
        ).pack(pady=(0, 4))

    # ================================================================ #
    # Library / data loading
    # ================================================================ #

    def _load_library_list(self):
        """Populate the library combobox from available database files."""
        try:
            from utils.path_utils import get_color_libraries_dir
            lib_dir = get_color_libraries_dir()
            if not os.path.isdir(lib_dir):
                return
            names = sorted(
                f[:-11]
                for f in os.listdir(lib_dir)
                if f.endswith("_library.db")
            )
            self._lib_combo["values"] = names
            if names:
                self._lib_combo.current(0)
                self._on_library_changed()
        except Exception as exc:
            self._status.configure(text=f"Library load error: {exc}")

    def _on_library_changed(self, _event=None):
        lib_name = self._lib_var.get()
        if not lib_name:
            return
        try:
            from utils.color_library import ColorLibrary
            from utils.hue_sorting import get_available_hue_names
            self._library = ColorLibrary(lib_name)
            self._hue_combo["values"] = ["All Colors"] + get_available_hue_names()
            self._hue_var.set("All Colors")
            self._refresh_swatches()
        except Exception as exc:
            self._status.configure(text=f"Error loading library: {exc}")

    def _on_hue_changed(self, _event=None):
        self._refresh_swatches()

    def _refresh_swatches(self):
        if self._library is None:
            return
        self._all_colors = self._library.get_all_colors()
        hue_sel = self._hue_var.get()
        if hue_sel and hue_sel != "All Colors":
            try:
                from utils.hue_sorting import filter_by_friendly_name
                rgb_tuples = [
                    (int(lc.rgb[0]), int(lc.rgb[1]), int(lc.rgb[2]))
                    for lc in self._all_colors
                ]
                filtered_rgb = set(filter_by_friendly_name(rgb_tuples, hue_sel))
                self._all_colors = [
                    lc for lc in self._all_colors
                    if (int(lc.rgb[0]), int(lc.rgb[1]), int(lc.rgb[2])) in filtered_rgb
                ]
            except Exception as exc:
                print(f"Hue filter error: {exc}")
        self.COLS = max(1, self._cols_var.get())

        self._swatches = []
        for lc in self._all_colors:
            r = int(max(0, min(255, lc.rgb[0])))
            g = int(max(0, min(255, lc.rgb[1])))
            b = int(max(0, min(255, lc.rgb[2])))
            self._swatches.append((lc.name, self._make_swatch((r, g, b))))

        n = len(self._swatches)
        hint = ("Drag stamp image to compare"
                if self._stamp_pil else "Load a stamp image to compare")
        self._status.configure(text=f"{n} colour{'s' if n != 1 else ''}  ·  {hint}")
        self._render()

    def _make_swatch(self, rgb):
        """Return an RGBA PIL Image: solid colour with a transparent oval centre."""
        r, g, b = rgb
        img  = Image.new("RGBA", (self.SWATCH_W, self.SWATCH_H), (r, g, b, 255))
        draw = ImageDraw.Draw(img)
        cx, cy = self.SWATCH_W // 2, self.SWATCH_H // 2
        hw, hh = self.OVAL_W // 2, self.OVAL_H // 2
        # Punch a transparent oval through the swatch
        draw.ellipse(
            [cx - hw, cy - hh, cx + hw, cy + hh],
            fill=(0, 0, 0, 0),
        )
        return img

    # ================================================================ #
    # Stamp image
    # ================================================================ #

    def _rebuild_stamp_display(self):
        """(Re-)create the scaled display version of the stamp image.

        LANCZOS downsampling averages neighbouring pixels, which reduces the
        visible halftone / grain from high-DPI scans and gives a more
        realistic 'viewed at normal distance' appearance.
        """
        if self._stamp_pil is None:
            self._stamp_display = None
            return
        pct   = max(5, min(100, self._scale_var.get()))
        scale = pct / 100.0
        w, h  = self._stamp_pil.size
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        self._stamp_display = self._stamp_pil.resize(
            (new_w, new_h), Image.LANCZOS
        )

    def _on_scale_changed(self):
        """Called when the Stamp Scale spinbox value changes."""
        self._rebuild_stamp_display()
        self._render()

    def _open_stamp(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Open Stamp Image",
            filetypes=[
                ("Image files", "*.tif *.tiff *.png *.jpg *.jpeg"),
                ("All files",   "*.*"),
            ],
        )
        if not path:
            return
        try:
            from utils.image_processor import load_image
            pil, _ = load_image(path)
            self._stamp_pil    = pil.convert("RGB")
            self._stamp_offset = [0, 0]
            self._rebuild_stamp_display()
            w, h = self._stamp_pil.size
            pct  = self._scale_var.get()
            self._status.configure(
                text=f"{os.path.basename(path)}  ({w}\u00d7{h})  ·  "
                     f"{pct}% scale ({self._stamp_display.width}\u00d7"
                     f"{self._stamp_display.height})  ·  Drag to pan"
            )
            self._render()
        except Exception as exc:
            messagebox.showerror("Load Error",
                                 f"Could not load image:\n{exc}",
                                 parent=self.root)

    def _clear_stamp(self):
        self._stamp_pil     = None
        self._stamp_display = None
        self._stamp_offset  = [0, 0]
        self._status.configure(text="Stamp image cleared.")
        self._render()

    # ================================================================ #
    # Pan / scroll
    # ================================================================ #

    def _on_pan_start(self, event):
        self._drag_start = (event.x, event.y)

    def _on_pan_drag(self, event):
        if self._drag_start is None or self._stamp_pil is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._drag_start = (event.x, event.y)
        self._stamp_offset[0] += dx
        self._stamp_offset[1] += dy
        self._render()

    def _on_pan_end(self, _event):
        self._drag_start = None

    def _on_scroll(self, event):
        if event.num == 4 or getattr(event, "delta", 0) > 0:
            self._canvas.yview_scroll(-1, "units")
        else:
            self._canvas.yview_scroll(1, "units")

    # ================================================================ #
    # Compositing / rendering
    # ================================================================ #

    def _render(self):
        """Composite all swatches over the panned stamp image and display."""
        cols = max(1, self.COLS)
        sw   = self.SWATCH_W + self.GAP
        sh   = self.SWATCH_H + self.GAP
        n    = len(self._swatches)
        rows = max(1, (n + cols - 1) // cols)

        total_w = cols * sw + self.GAP
        total_h = rows * sh + self.GAP

        cw = max(self._canvas.winfo_width(),  total_w)
        ch = max(self._canvas.winfo_height(), total_h)

        # --- Base layer: dark grey background or panned stamp image ---
        base = Image.new("RGB", (cw, ch), (64, 64, 64))

        # Use the pre-scaled display version (faster render, reduces grain)
        stamp = self._stamp_display or self._stamp_pil
        if stamp is not None:
            ox, oy  = self._stamp_offset
            iw, ih  = stamp.size
            src_x0  = max(0, -ox)
            src_y0  = max(0, -oy)
            src_x1  = min(iw, cw - ox)
            src_y1  = min(ih, ch - oy)
            if src_x1 > src_x0 and src_y1 > src_y0:
                region = stamp.crop((src_x0, src_y0, src_x1, src_y1))
                base.paste(region, (max(0, ox), max(0, oy)))

        # --- Overlay each swatch (RGBA with transparent oval) ---
        draw = ImageDraw.Draw(base)
        for i, (name, swatch_rgba) in enumerate(self._swatches):
            row = i // cols
            col = i % cols
            x   = self.GAP + col * sw
            y   = self.GAP + row * sh

            # The RGBA swatch: alpha=255 → solid colour, alpha=0 → see stamp
            base.paste(swatch_rgba, (x, y), mask=swatch_rgba)

            # Name label at the bottom of the swatch
            label_y = y + self.SWATCH_H - 22
            draw.rectangle(
                [x + 1, label_y, x + self.SWATCH_W - 1, y + self.SWATCH_H - 1],
                fill=(0, 0, 0),
            )
            display = name if len(name) <= 25 else name[:23] + "…"
            draw.text((x + 5, label_y + 4), display, fill=(255, 255, 255))

        self._photo_ref = ImageTk.PhotoImage(base)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor=tk.NW, image=self._photo_ref)
        self._canvas.configure(scrollregion=(0, 0, total_w, total_h))


# -------------------------------------------------------------------- #

def open_color_key(parent, app=None):
    """Convenience wrapper — open the Colour Key dialog."""
    return ColorKeyDialog(parent, app=app)
