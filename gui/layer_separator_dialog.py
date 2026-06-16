#!/usr/bin/env python3
"""
Layer Separator Dialog for StampZ — Stepped Wizard

Guides the user through layer separation one step at a time:
  Step 1: Sample & remove background
  Step 2: Remove cancellation (adjustable, multi-pass)
  Step 3: Separate ink from paper (automatic Otsu)
  Step 4: View results, compare to library, save

Each step locks its result before proceeding to the next.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import numpy as np


class LayerSeparatorDialog:
    """Stepped wizard for stamp layer separation."""

    STEPS = ["1. Background", "2. Cancellation", "3. Ink / Paper", "4. Results"]

    def __init__(self, parent, pil_image: Image.Image):
        self.parent = parent
        self.original_image = pil_image.convert('RGB')
        self._arr = np.array(self.original_image, dtype=np.float32)
        self._photo_ref = None
        self._current_pil = self.original_image
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._drag_start = None
        self._display_offset = (0, 0)
        self._display_scale = 1.0

        # Layer state
        self._bg_rgb = None
        self._bg_mask = None       # locked background mask
        self._cancel_mask = None   # locked cancellation mask
        self._ink_mask = None
        self._paper_mask = None
        self._result = None        # LayerResult after step 3
        self._separator = None
        self._current_step = 0     # 0-based

        self.root = tk.Toplevel(parent)
        self.root.title("Stamp Layer Separator")
        self.root.geometry("920x780")
        self.root.minsize(720, 580)

        self._build_ui()
        self.root.after(50, self._fit_to_canvas)
        self._update_step_ui()

    # ================================================================== #
    # UI construction
    # ================================================================== #

    def _build_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=8, pady=4)

        # Step indicator
        step_frame = ttk.Frame(top)
        step_frame.pack(fill=tk.X, pady=(0, 4))
        self._step_labels = []
        for i, name in enumerate(self.STEPS):
            lbl = ttk.Label(step_frame, text=name, font=("Arial", 10),
                            foreground="gray", padding=(6, 2))
            lbl.pack(side=tk.LEFT, padx=2)
            self._step_labels.append(lbl)

        # Status
        self.status_label = ttk.Label(top, text="", font=("Arial", 11, "bold"))
        self.status_label.pack(anchor=tk.W, pady=(0, 2))

        # ── Step-specific controls (stacked frames, only one visible) ──
        self._step_frames = []

        # Step 0: Background
        f0 = ttk.Frame(top)
        r0 = ttk.Frame(f0)
        r0.pack(fill=tk.X)
        ttk.Label(r0, text="Sample:").pack(side=tk.LEFT)
        self.bg_display = tk.Label(r0, text="  (click image)  ",
                                   bg="#cccccc", relief=tk.SUNKEN, width=18)
        self.bg_display.pack(side=tk.LEFT, padx=4)
        ttk.Label(r0, text="ΔE:").pack(side=tk.LEFT, padx=(10, 2))
        self.bg_threshold = tk.DoubleVar(value=12.0)
        ttk.Spinbox(r0, from_=2, to=50, increment=1,
                    textvariable=self.bg_threshold, width=5).pack(side=tk.LEFT)
        ttk.Button(r0, text="Preview", command=self._preview_background).pack(side=tk.LEFT, padx=6)
        ttk.Button(r0, text="Lock & Next ▸", command=self._lock_background).pack(side=tk.LEFT, padx=4)
        self._step_frames.append(f0)

        # Step 1: Cancellation
        f1 = ttk.Frame(top)
        r1 = ttk.Frame(f1)
        r1.pack(fill=tk.X)
        ttk.Label(r1, text="Brightness:").pack(side=tk.LEFT)
        self.cancel_brightness = tk.IntVar(value=80)
        ttk.Spinbox(r1, from_=20, to=180, increment=5,
                    textvariable=self.cancel_brightness, width=4).pack(side=tk.LEFT)
        ttk.Label(r1, text="Sat:").pack(side=tk.LEFT, padx=(8, 2))
        self.cancel_saturation = tk.IntVar(value=40)
        ttk.Spinbox(r1, from_=10, to=100, increment=5,
                    textvariable=self.cancel_saturation, width=4).pack(side=tk.LEFT)
        ttk.Button(r1, text="Preview", command=self._preview_cancel).pack(side=tk.LEFT, padx=6)
        ttk.Button(r1, text="Lock & Next ▸", command=self._lock_cancel).pack(side=tk.LEFT, padx=4)
        ttk.Button(r1, text="◂ Back", command=lambda: self._go_step(0)).pack(side=tk.LEFT, padx=4)
        self._step_frames.append(f1)

        # Step 2: Ink/Paper (automatic)
        f2 = ttk.Frame(top)
        r2 = ttk.Frame(f2)
        r2.pack(fill=tk.X)
        ttk.Label(r2, text="Otsu auto-threshold separates ink from paper.").pack(side=tk.LEFT)
        ttk.Button(r2, text="Separate & Next ▸", command=self._lock_ink_paper).pack(side=tk.LEFT, padx=6)
        ttk.Button(r2, text="◂ Back", command=lambda: self._go_step(1)).pack(side=tk.LEFT, padx=4)
        self._step_frames.append(f2)

        # Step 3: Results
        f3 = ttk.Frame(top)
        r3a = ttk.Frame(f3)
        r3a.pack(fill=tk.X, pady=2)
        ttk.Label(r3a, text="View:").pack(side=tk.LEFT)
        for lbl, lay in [("Original", "original"), ("Ink", "ink"),
                         ("Paper", "paper"), ("Cancel", "cancellation"),
                         ("Stamp", "stamp")]:
            ttk.Button(r3a, text=lbl, width=8,
                       command=lambda l=lay: self._show_layer(l)).pack(side=tk.LEFT, padx=2)
        ttk.Separator(r3a, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(r3a, text="Save Layers...", command=self._save_layers).pack(side=tk.LEFT, padx=2)
        ttk.Button(r3a, text="Compare Ink...", command=self._compare_to_library).pack(side=tk.LEFT, padx=2)
        ttk.Button(r3a, text="◂ Start Over", command=lambda: self._go_step(0)).pack(side=tk.LEFT, padx=4)
        self._step_frames.append(f3)

        # ── Zoom controls (always visible) ────────────────────────────
        zf = ttk.Frame(top)
        zf.pack(fill=tk.X, pady=2)
        ttk.Button(zf, text="Fit", width=4, command=self._fit_to_canvas).pack(side=tk.LEFT, padx=2)
        ttk.Button(zf, text="1:1", width=4, command=self._zoom_actual).pack(side=tk.LEFT, padx=2)
        ttk.Button(zf, text="+", width=2, command=lambda: self._zoom_by(1.25)).pack(side=tk.LEFT)
        ttk.Button(zf, text="\u2212", width=2, command=lambda: self._zoom_by(0.8)).pack(side=tk.LEFT)
        self.zoom_label = ttk.Label(zf, text="100%", width=6)
        self.zoom_label.pack(side=tk.LEFT, padx=4)

        # ── Canvas ────────────────────────────────────────────────────
        cf = ttk.Frame(self.root)
        cf.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.canvas = tk.Canvas(cf, bg="#333333", cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Button-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_drag)
        self.canvas.bind("<Button-3>", self._on_pan_start)
        self.canvas.bind("<B3-Motion>", self._on_pan_drag)
        self.canvas.bind("<Shift-Button-1>", self._on_pan_start)
        self.canvas.bind("<Shift-B1-Motion>", self._on_pan_drag)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<Button-4>", lambda e: self._zoom_by(1.15))
        self.canvas.bind("<Button-5>", lambda e: self._zoom_by(0.87))

        # ── Results panel ─────────────────────────────────────────────
        rf = ttk.LabelFrame(self.root, text="Results")
        rf.pack(fill=tk.X, padx=8, pady=(0, 8))
        ri = ttk.Frame(rf)
        ri.pack(fill=tk.X, padx=8, pady=4)
        self.results_label = ttk.Label(ri, text="Complete all steps to see results.",
                                       font=("Courier", 10), justify=tk.LEFT)
        self.results_label.pack(side=tk.LEFT, anchor=tk.W)
        sf = ttk.Frame(ri)
        sf.pack(side=tk.RIGHT, padx=(20, 0))
        self.ink_swatch = tk.Label(sf, text="  Ink  ", bg="#cccccc",
                                   relief=tk.RAISED, width=10, height=2,
                                   font=("Arial", 10, "bold"))
        self.ink_swatch.pack(side=tk.LEFT, padx=4)
        self.paper_swatch = tk.Label(sf, text=" Paper ", bg="#cccccc",
                                     relief=tk.RAISED, width=10, height=2,
                                     font=("Arial", 10, "bold"))
        self.paper_swatch.pack(side=tk.LEFT, padx=4)

    # ================================================================== #
    # Step management
    # ================================================================== #

    def _go_step(self, step):
        self._current_step = step
        # Reset downstream locks when going back
        if step <= 0:
            self._bg_mask = None
            self._cancel_mask = None
            self._ink_mask = None
            self._paper_mask = None
            self._result = None
        elif step <= 1:
            self._cancel_mask = None
            self._ink_mask = None
            self._paper_mask = None
            self._result = None
        elif step <= 2:
            self._ink_mask = None
            self._paper_mask = None
            self._result = None
        self._update_step_ui()
        self._show_image(self.original_image)

    def _update_step_ui(self):
        """Show only the current step's controls; highlight step indicator."""
        for i, f in enumerate(self._step_frames):
            if i == self._current_step:
                f.pack(fill=tk.X, pady=2)
            else:
                f.pack_forget()
        for i, lbl in enumerate(self._step_labels):
            if i == self._current_step:
                lbl.configure(foreground="blue", font=("Arial", 10, "bold"))
            elif i < self._current_step:
                lbl.configure(foreground="green", font=("Arial", 10))
            else:
                lbl.configure(foreground="gray", font=("Arial", 10))

        messages = [
            "Click on the background area outside the stamp to sample its color.",
            "Adjust brightness/saturation to capture cancellation. Preview, then Lock.",
            "Click 'Separate' to auto-split remaining pixels into ink and paper.",
            "View layers, save images, or compare ink color to your library.",
        ]
        self.status_label.configure(text=messages[self._current_step])

    # ================================================================== #
    # Zoom / pan / display
    # ================================================================== #

    def _render(self):
        if self._current_pil is None:
            return
        iw, ih = self._current_pil.size
        nw, nh = max(1, int(iw * self._zoom)), max(1, int(ih * self._zoom))
        disp = self._current_pil.resize((nw, nh), Image.LANCZOS)
        self._photo_ref = ImageTk.PhotoImage(disp)
        self.canvas.delete("all")
        cw = max(self.canvas.winfo_width(), 400)
        ch = max(self.canvas.winfo_height(), 300)
        cx = cw // 2 + int(self._pan_x * self._zoom)
        cy = ch // 2 + int(self._pan_y * self._zoom)
        self.canvas.create_image(cx, cy, image=self._photo_ref, anchor=tk.CENTER)
        self._display_scale = self._zoom
        self._display_offset = (cx - nw // 2, cy - nh // 2)
        self.zoom_label.configure(text=f"{int(self._zoom * 100)}%")

    def _fit_to_canvas(self):
        cw = max(self.canvas.winfo_width(), 400)
        ch = max(self.canvas.winfo_height(), 300)
        iw, ih = self._current_pil.size
        self._zoom = min(cw / iw, ch / ih, 1.0)
        self._pan_x = self._pan_y = 0
        self._render()

    def _zoom_actual(self):
        self._zoom = 1.0
        self._pan_x = self._pan_y = 0
        self._render()

    def _zoom_by(self, f):
        self._zoom = max(0.1, min(self._zoom * f, 10.0))
        self._render()

    def _on_scroll(self, e):
        self._zoom_by(1.15 if e.delta > 0 else 0.87)

    def _on_pan_start(self, e):
        self._drag_start = (e.x, e.y)

    def _on_pan_drag(self, e):
        if not self._drag_start:
            return
        dx, dy = e.x - self._drag_start[0], e.y - self._drag_start[1]
        self._drag_start = (e.x, e.y)
        self._pan_x += dx / self._zoom
        self._pan_y += dy / self._zoom
        self._render()

    def _show_image(self, pil):
        self._current_pil = pil
        self._fit_to_canvas()

    def _canvas_to_image(self, cx, cy):
        ox, oy = self._display_offset
        return int((cx - ox) / self._display_scale), int((cy - oy) / self._display_scale)

    # ================================================================== #
    # Canvas click (background sampling in step 0)
    # ================================================================== #

    def _on_canvas_click(self, event):
        if self._current_step != 0:
            return  # only sample in step 0
        if self._photo_ref is None:
            return
        img_x, img_y = self._canvas_to_image(event.x, event.y)
        iw, ih = self.original_image.size
        if not (0 <= img_x < iw and 0 <= img_y < ih):
            return
        arr = np.array(self.original_image)
        x1, x2 = max(0, img_x - 2), min(iw, img_x + 3)
        y1, y2 = max(0, img_y - 2), min(ih, img_y + 3)
        avg = np.mean(arr[y1:y2, x1:x2].reshape(-1, 3), axis=0)
        self._bg_rgb = tuple(avg.tolist())
        r, g, b = int(avg[0]), int(avg[1]), int(avg[2])
        self.bg_display.configure(
            text=f"  RGB({r},{g},{b})  ", bg=f"#{r:02x}{g:02x}{b:02x}",
            fg="white" if (r + g + b) / 3 < 128 else "black")
        # indicator
        self.canvas.delete("bg_indicator")
        rad = max(4, int(3 * self._display_scale))
        self.canvas.create_oval(event.x - rad, event.y - rad,
                                event.x + rad, event.y + rad,
                                outline="yellow", width=2, tags="bg_indicator")

    # ================================================================== #
    # Step 0: Background
    # ================================================================== #

    def _get_separator(self):
        from utils.stamp_layer_separator import StampLayerSeparator
        sep = StampLayerSeparator(self.original_image)
        if self._bg_rgb:
            sep.set_background_color(*self._bg_rgb)
        sep.set_thresholds(
            background_delta_e=self.bg_threshold.get(),
            cancellation_brightness=self.cancel_brightness.get(),
            cancellation_saturation=self.cancel_saturation.get())
        return sep

    def _preview_background(self):
        if self._bg_rgb is None:
            messagebox.showinfo("Sample First", "Click on the background area first.")
            return
        sep = self._get_separator()
        mask = sep._mask_background()
        self._show_masked(mask, "background")

    def _lock_background(self):
        if self._bg_rgb is None:
            messagebox.showinfo("Sample First", "Click on the background area first.")
            return
        sep = self._get_separator()
        self._bg_mask = sep._mask_background()
        self._separator = sep
        n = int(np.sum(self._bg_mask))
        self._current_step = 1
        self._update_step_ui()
        self.status_label.configure(
            text=f"Background locked ({n:,} pixels). Now adjust cancellation thresholds.")
        # Show image with background removed
        arr = np.array(self.original_image).copy()
        arr[self._bg_mask] = [255, 255, 255]
        self._show_image(Image.fromarray(arr))

    # ================================================================== #
    # Step 1: Cancellation
    # ================================================================== #

    def _preview_cancel(self):
        if self._bg_mask is None:
            return
        sep = self._get_separator()
        cancel = sep._mask_cancellation(self._bg_mask)
        # Show cancel pixels highlighted in RED on the original image
        # (background already removed as white)
        arr = np.array(self.original_image).copy()
        arr[self._bg_mask] = [255, 255, 255]  # background → white
        # Highlight cancel pixels in semi-transparent red
        arr[cancel, 0] = np.minimum(arr[cancel, 0].astype(np.int16) + 180, 255).astype(np.uint8)
        arr[cancel, 1] = (arr[cancel, 1] * 0.3).astype(np.uint8)
        arr[cancel, 2] = (arr[cancel, 2] * 0.3).astype(np.uint8)
        self._show_image(Image.fromarray(arr))
        # Show count
        n = int(np.sum(cancel))
        self.status_label.configure(
            text=f"Cancel preview: {n:,} pixels detected (shown in red). Adjust and re-preview, or Lock.")

    def _lock_cancel(self):
        if self._bg_mask is None:
            return
        sep = self._get_separator()
        self._cancel_mask = sep._mask_cancellation(self._bg_mask)
        self._separator = sep
        n = int(np.sum(self._cancel_mask))
        self._current_step = 2
        self._update_step_ui()
        self.status_label.configure(
            text=f"Cancellation locked ({n:,} pixels). Click Separate to split ink from paper.")
        # Show image with background + cancel removed
        arr = np.array(self.original_image).copy()
        arr[self._bg_mask] = [255, 255, 255]
        arr[self._cancel_mask] = [255, 255, 255]
        self._show_image(Image.fromarray(arr))

    # ================================================================== #
    # Step 2: Ink / Paper
    # ================================================================== #

    def _lock_ink_paper(self):
        if self._bg_mask is None or self._cancel_mask is None:
            return
        sep = self._get_separator()
        stamp_area = ~self._bg_mask & ~self._cancel_mask
        self._ink_mask, self._paper_mask = sep._separate_ink_paper(stamp_area)
        self._separator = sep

        # Build a full LayerResult for the results step
        from utils.stamp_layer_separator import LayerResult
        r = LayerResult()
        r.background_mask = self._bg_mask
        r.cancellation_mask = self._cancel_mask
        r.ink_mask = self._ink_mask
        r.paper_mask = self._paper_mask
        r.total_pixels = self._bg_mask.size
        r.background_pixels = int(np.sum(self._bg_mask))
        r.cancellation_pixels = int(np.sum(self._cancel_mask))
        r.ink_pixels = int(np.sum(self._ink_mask))
        r.paper_pixels = int(np.sum(self._paper_mask))
        stamp_total = r.ink_pixels + r.paper_pixels
        if stamp_total > 0:
            r.ink_percentage = r.ink_pixels / stamp_total * 100
            r.paper_percentage = r.paper_pixels / stamp_total * 100
        sep._compute_aggregates(r)
        self._result = r

        # Update results display
        self._update_results_display(r)

        self._current_step = 3
        self._update_step_ui()
        self._show_layer("ink")

    # ================================================================== #
    # Helpers
    # ================================================================== #

    def _show_masked(self, mask, label="preview"):
        """Show image with masked pixels replaced by white."""
        arr = np.array(self.original_image)
        out = arr.copy()
        out[mask] = [255, 255, 255]
        self._show_image(Image.fromarray(out))

    def _show_layer(self, layer):
        if layer == "original":
            self._show_image(self.original_image)
            return
        if self._result is None or self._separator is None:
            return
        self._show_image(self._separator.get_layer_image(self._result, layer))

    def _update_results_display(self, r):
        lines = [
            f"Pixels: total={r.total_pixels:,}  bg={r.background_pixels:,}  "
            f"cancel={r.cancellation_pixels:,}  ink={r.ink_pixels:,}  paper={r.paper_pixels:,}",
            f"Ink/Paper: {r.ink_percentage:.1f}% / {r.paper_percentage:.1f}%",
        ]
        if r.ink_aggregate_lab:
            lines.append(f"Ink mean  L*a*b*: L*={r.ink_aggregate_lab[0]:.1f}  a*={r.ink_aggregate_lab[1]:.1f}  b*={r.ink_aggregate_lab[2]:.1f}")
        if r.ink_median_lab:
            lines.append(f"Ink median:       L*={r.ink_median_lab[0]:.1f}  a*={r.ink_median_lab[1]:.1f}  b*={r.ink_median_lab[2]:.1f}")
        if r.paper_aggregate_lab:
            lines.append(f"Paper:            L*={r.paper_aggregate_lab[0]:.1f}  a*={r.paper_aggregate_lab[1]:.1f}  b*={r.paper_aggregate_lab[2]:.1f}")
        self.results_label.configure(text="\n".join(lines))

        if r.ink_aggregate_rgb:
            ir, ig, ib = [int(v) for v in r.ink_aggregate_rgb]
            self.ink_swatch.configure(
                bg=f"#{ir:02x}{ig:02x}{ib:02x}", text=f"Ink\nRGB({ir},{ig},{ib})",
                fg="white" if (ir + ig + ib) / 3 < 128 else "black")
        if r.paper_aggregate_rgb:
            pr, pg, pb = [int(v) for v in r.paper_aggregate_rgb]
            self.paper_swatch.configure(
                bg=f"#{pr:02x}{pg:02x}{pb:02x}", text=f"Paper\nRGB({pr},{pg},{pb})",
                fg="white" if (pr + pg + pb) / 3 < 128 else "black")

    # ================================================================== #
    # Save
    # ================================================================== #

    def _save_layers(self):
        if self._result is None:
            messagebox.showinfo("Not Ready", "Complete all steps first.")
            return
        d = filedialog.askdirectory(title="Save layer images", parent=self.root)
        if not d:
            return
        base = "stamp"
        if hasattr(self.parent, 'current_file') and self.parent.current_file:
            base = os.path.splitext(os.path.basename(self.parent.current_file))[0]
        for ln in ['ink', 'paper', 'cancellation', 'stamp']:
            self._separator.get_layer_image(self._result, ln).save(
                os.path.join(d, f"{base}_{ln}.png"))
        with open(os.path.join(d, f"{base}_layer_results.txt"), 'w') as f:
            f.write(self.results_label.cget('text'))
        messagebox.showinfo("Saved", f"Layer images saved to:\n{d}")

    # ================================================================== #
    # Compare ink to library
    # ================================================================== #

    def _compare_to_library(self):
        if self._result is None or self._result.ink_aggregate_lab is None:
            messagebox.showinfo("Not Ready", "Complete all steps first.")
            return
        L, a, b = self._result.ink_aggregate_lab
        ink_rgb = self._result.ink_aggregate_rgb
        try:
            from utils.color_library import ColorLibrary
            from utils.path_utils import get_color_libraries_dir
            import glob

            lib_dir = get_color_libraries_dir()
            lib_files = sorted(glob.glob(os.path.join(lib_dir, '*.db')))
            if not lib_files:
                messagebox.showinfo("No Libraries", "No color libraries found.")
                return
            lib_names = [os.path.splitext(os.path.basename(f))[0].replace('_library', '')
                         for f in lib_files]

            win = tk.Toplevel(self.root)
            win.title("Compare Ink to Library")
            win.geometry("540x450")
            win.transient(self.root)

            # Ink swatch
            sf = ttk.Frame(win)
            sf.pack(fill=tk.X, padx=12, pady=(12, 4))
            ir, ig, ib = ([int(v) for v in ink_rgb] if ink_rgb else [128, 128, 128])
            tk.Label(sf, text=f"  Ink Mean  \n  L*={L:.1f}  a*={a:.1f}  b*={b:.1f}  ",
                     bg=f"#{ir:02x}{ig:02x}{ib:02x}", relief=tk.RAISED,
                     font=("Arial", 11, "bold"), padx=10, pady=6,
                     fg="white" if (ir + ig + ib) / 3 < 128 else "black"
                     ).pack(side=tk.LEFT)

            lf = ttk.Frame(win)
            lf.pack(fill=tk.X, padx=12, pady=4)
            ttk.Label(lf, text="Library:").pack(side=tk.LEFT)
            lib_var = tk.StringVar(value="(All libraries)")
            ttk.Combobox(lf, textvariable=lib_var,
                         values=["(All libraries)"] + lib_names,
                         state="readonly", width=30).pack(side=tk.LEFT, padx=6)

            rt = tk.Text(win, font=("Courier", 11), height=14, width=60,
                         state=tk.DISABLED, wrap=tk.WORD)
            rt.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

            def _search():
                sel = lib_var.get()
                search = lib_names if sel == "(All libraries)" else [sel]
                matches = []
                for ln in search:
                    try:
                        lib = ColorLibrary(ln)
                        for m in lib.find_closest_matches(
                                sample_lab=(L, a, b), max_delta_e=30.0, max_results=5):
                            m.library_name = ln
                            matches.append(m)
                    except Exception as e:
                        print(f"Library '{ln}' failed: {e}")
                matches.sort(key=lambda m: m.delta_e_2000)
                top = matches[:10]
                lines = [f"Ink: L*={L:.1f}  a*={a:.1f}  b*={b:.1f}", ""]
                if not top:
                    lines.append("No matches found.")
                else:
                    for i, m in enumerate(top, 1):
                        lines.append(
                            f" {i:2}. {m.library_color.name:<25} "
                            f"{m.library_color.category:<12} "
                            f"\u0394E={m.delta_e_2000:5.2f} [{m.match_quality}]")
                rt.configure(state=tk.NORMAL)
                rt.delete("1.0", tk.END)
                rt.insert("1.0", "\n".join(lines))
                rt.configure(state=tk.DISABLED)

            bf = ttk.Frame(win)
            bf.pack(fill=tk.X, padx=12, pady=(0, 8))
            ttk.Button(bf, text="Search", command=_search).pack(side=tk.LEFT, padx=4)
            ttk.Button(bf, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=4)
            _search()

        except Exception as e:
            messagebox.showerror("Compare Error", f"Failed:\n\n{str(e)}")


def open_layer_separator(parent, pil_image):
    """Convenience function to open the dialog."""
    return LayerSeparatorDialog(parent, pil_image)
