#!/usr/bin/env python3
"""Comparison-image composition for StampZ.

Produces a single PIL Image combining a stamp image with its averaged
sample colour, in one of two layouts:

  * ``compose_swatch_layer``  — stamp on top of a solid swatch layer.
    If the stamp has an alpha channel (e.g. a triangle crop saved as
    PNG), the swatch shows through the transparent corners, giving you
    an instant visual comparison between the sample average and the
    stamp's ink. For fully-opaque stamps you still get a swatch frame
    around the image.

  * ``compose_side_by_side``  — stamp on the left, a swatch panel on
    the right (optionally with RGB / Lab values printed on it).

Both functions are pure: image in, image out. No Tk, no state.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

# Either a solid RGB triplet or a pre-rendered tile/pattern image. The
# composers tile a pattern image across the swatch backdrop / panel.
FillSpec = Union[Sequence[float], Image.Image]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _to_int_rgb(rgb: Sequence[float]) -> Tuple[int, int, int]:
    """Clamp/round an (R, G, B) triplet to 0..255 ints for PIL."""
    r, g, b = rgb[0], rgb[1], rgb[2]
    return (
        max(0, min(255, int(round(r)))),
        max(0, min(255, int(round(g)))),
        max(0, min(255, int(round(b)))),
    )


def _load_font(size: int) -> ImageFont.ImageFont:
    """Best-effort font loader. Falls back to PIL's default bitmap font."""
    for path in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _best_text_color(bg_rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Pick white or black text for readability over ``bg_rgb``.

    Uses the standard luminance test from WCAG: dark backgrounds get
    white text, light backgrounds get black text.
    """
    r, g, b = bg_rgb
    # Rec. 709 luminance
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return (255, 255, 255) if luma < 140 else (0, 0, 0)


def _fill_canvas_with(canvas: Image.Image, fill: FillSpec) -> None:
    """Repaint ``canvas`` with either a solid RGB or a tiled pattern.

    Solid case: equivalent to ``Image.new`` of the canvas size, used so
    callers can build the canvas once and have one place that handles
    both fill kinds.

    Tile case: the pattern is repeated edge-to-edge across the canvas
    using nested ``paste`` calls. The pattern is treated as opaque RGB.

    Efficiency: rather than pasting one tiny tile at a time across the
    whole canvas (which becomes very slow for small periods on large
    images), we first double the tile repeatedly until it covers the
    full width, paste one wide strip, then double that strip vertically.
    This reduces paste calls from O(W*H / period²) to O(log(W) + log(H)).
    """
    cw, ch = canvas.size
    if isinstance(fill, Image.Image):
        tile = fill if fill.mode == "RGB" else fill.convert("RGB")
        tw, th = tile.size
        if tw <= 0 or th <= 0:
            return
        # Build one full-width row by tiling the tile horizontally,
        # then paste that row vertically. This reduces paste calls from
        # O(W*H / period²) to O(W/period + H/period).
        row = Image.new("RGB", (cw, th))
        for x in range(0, cw, tw):
            row.paste(tile, (x, 0))
        for y in range(0, ch, th):
            canvas.paste(row, (0, y))
    else:
        rgb = _to_int_rgb(fill)
        canvas.paste(Image.new("RGB", canvas.size, rgb), (0, 0))


# --------------------------------------------------------------------------- #
# Striped swatch (perceptually-honest paper/ink blend)
# --------------------------------------------------------------------------- #

def make_striped_swatch(
    ink_rgb: Sequence[float],
    paper_rgb: Sequence[float],
    coverage_ratio: float,
    period: int = 10,
    orientation: str = "vertical",
) -> Image.Image:
    """Return a tiny ``period × period`` tile that, when tiled across a
    swatch panel, produces alternating ink/paper stripes at the given
    coverage ratio.

    Rationale: a flat coverage-weighted blend ("effective tone") only
    matches what the eye sees at far-field viewing distance, where
    finely-printed lines fall below the eye's spatial resolution. For
    stamps viewed up close, the eye doesn't fully fuse the ink lines
    with the paper between them, and a flat blended swatch looks
    nothing like the perceived colour. A striped swatch instead
    *behaves* the same way the stamp does: at close range you see
    structure on both, at distance both fuse to the same tone. That
    parallel behaviour is a much more honest perceptual comparison.

    Args:
        ink_rgb: sRGB triple in 0..255 for the ink stripe.
        paper_rgb: sRGB triple in 0..255 for the paper stripe.
        coverage_ratio: Ink fraction in [0, 1]. Clamped so each stripe
            ends up at least 1 px wide (i.e. ink_w ∈ [1, period-1]).
        period: Width of one (ink + paper) stripe pair, in pixels.
            Default 10 px gives ~45 stripe-pairs across a 450-px panel,
            which fuses cleanly at typical screen viewing distances.
        orientation: ``"vertical"`` (default) or ``"horizontal"``.

    Returns:
        A small RGB ``Image`` of size ``(period, period)`` suitable
        for tiling. Use ``_fill_canvas_with`` (or any tile-aware paste
        loop) to project it across an arbitrary swatch area.
    """
    period = max(2, int(period))
    cov = max(0.0, min(1.0, float(coverage_ratio)))
    ink_w = int(round(cov * period))
    ink_w = max(1, min(period - 1, ink_w))

    ink = _to_int_rgb(ink_rgb)
    paper = _to_int_rgb(paper_rgb)

    if orientation == "horizontal":
        # Top ink_w rows = ink, bottom (period - ink_w) rows = paper.
        tile = Image.new("RGB", (period, period), paper)
        tile.paste(Image.new("RGB", (period, ink_w), ink), (0, 0))
        return tile

    # Vertical (default): leftmost ink_w columns = ink, rest = paper.
    tile = Image.new("RGB", (period, period), paper)
    tile.paste(Image.new("RGB", (ink_w, period), ink), (0, 0))
    return tile


# --------------------------------------------------------------------------- #
# Layout 1: swatch behind the stamp
# --------------------------------------------------------------------------- #

def compose_swatch_layer(
    stamp_image: Image.Image,
    avg_rgb: FillSpec,
    frame_padding: int = 60,
) -> Image.Image:
    """Return the stamp pasted on top of a swatch layer.

    Args:
        stamp_image: PIL image of the stamp. May be RGBA (transparent
            background from a shaped crop) or any other mode.
        avg_rgb: Either a solid (R, G, B) triple in 0..255, or a
            pre-rendered PIL image which will be tiled across the
            backdrop. The tile path is what the striped
            paper/ink swatch uses.
        frame_padding: Pixels of swatch visible around the stamp on
            every side. Gives the swatch room to show around a fully
            opaque image and to surround a transparent-crop shape.

    Returns:
        A new RGB PIL Image of size
        ``(stamp_w + 2*padding, stamp_h + 2*padding)``.
    """
    sw, sh = stamp_image.size
    canvas_size = (sw + 2 * frame_padding, sh + 2 * frame_padding)

    # Build the backdrop. Solid-colour fills are still done at
    # construction for speed; pattern fills use the tiling helper.
    if isinstance(avg_rgb, Image.Image):
        canvas = Image.new("RGB", canvas_size, (255, 255, 255))
        _fill_canvas_with(canvas, avg_rgb)
    else:
        canvas = Image.new("RGB", canvas_size, _to_int_rgb(avg_rgb))

    # Normalise the stamp to RGBA so we can paste it with its alpha as a
    # mask — this is what lets the swatch show through transparent crop
    # corners. For fully-opaque sources the mask is all-255 so the paste
    # is a simple overlay.
    if stamp_image.mode != "RGBA":
        stamp_rgba = stamp_image.convert("RGBA")
    else:
        stamp_rgba = stamp_image

    canvas.paste(stamp_rgba, (frame_padding, frame_padding), mask=stamp_rgba)
    return canvas


# --------------------------------------------------------------------------- #
# Layout 2: side-by-side panel
# --------------------------------------------------------------------------- #

def compose_side_by_side(
    stamp_image: Image.Image,
    avg_rgb: FillSpec,
    avg_lab: Optional[Sequence[float]] = None,
    swatch_ratio: float = 0.35,
    gap: int = 16,
    include_values: bool = True,
    text_block: Optional[List[str]] = None,
    text_bg_rgb: Optional[Sequence[float]] = None,
) -> Image.Image:
    """Return a combined 'stamp | swatch' panel.

    Args:
        stamp_image: PIL image of the stamp.
        avg_rgb: Either a solid sRGB triple (0..255) or a pre-rendered
            tile image which will be tiled across the swatch panel.
            The tile path is used for the striped paper/ink swatch.
        avg_lab: Optional Lab tuple. Used in the auto-generated text
            block (only) when ``avg_rgb`` is a solid colour.
        swatch_ratio: Swatch panel width as a fraction of the stamp width
            (default 35 %).
        gap: Pixels of white gap between the stamp and the swatch panel.
        include_values: When True, overlay numeric labels on the swatch.
        text_block: Optional list of pre-formatted text lines; the first
            line is rendered with the heading font, the rest with the
            body font. When supplied, this overrides the auto-generated
            "Average / RGB / Lab" text. Required when ``avg_rgb`` is an
            Image (the auto-generated text needs a single RGB triple).
        text_bg_rgb: Optional sRGB triple used to choose black or white
            text for contrast. When ``avg_rgb`` is an Image, this should
            be the visually-averaged colour of the tiled pattern (e.g.
            the coverage-weighted blend). When omitted, falls back to
            ``avg_rgb`` for solid fills, or mid-grey for patterns.

    Returns:
        A new RGB PIL Image wide enough to contain both panels.
    """
    sw, sh = stamp_image.size

    # Flatten any transparent stamp onto white so the side-by-side panel
    # has a uniform background. (Writing the panel itself as RGBA would
    # be possible but most consumers don't care, and white matches the
    # existing swatch displays in the Results panel.)
    if stamp_image.mode == "RGBA":
        stamp_rgb = Image.new("RGB", stamp_image.size, (255, 255, 255))
        stamp_rgb.paste(stamp_image, mask=stamp_image.split()[3])
    else:
        stamp_rgb = stamp_image.convert("RGB")

    swatch_w = max(60, int(sw * swatch_ratio))
    total_w = sw + gap + swatch_w
    canvas = Image.new("RGB", (total_w, sh), (255, 255, 255))

    # Left: stamp
    canvas.paste(stamp_rgb, (0, 0))

    # Right: swatch panel (solid OR tiled pattern)
    panel = Image.new("RGB", (swatch_w, sh), (255, 255, 255))
    _fill_canvas_with(panel, avg_rgb)
    canvas.paste(panel, (sw + gap, 0))

    if include_values:
        # Resolve the colour we use for the black-vs-white text-contrast
        # decision. For solid fills it's the fill itself; for tiled
        # patterns the caller supplies a representative average
        # (typically the coverage-weighted blend of ink and paper).
        if text_bg_rgb is not None:
            contrast_rgb = _to_int_rgb(text_bg_rgb)
        elif isinstance(avg_rgb, Image.Image):
            contrast_rgb = (128, 128, 128)
        else:
            contrast_rgb = _to_int_rgb(avg_rgb)

        _overlay_swatch_text(
            canvas,
            swatch_rgb=contrast_rgb,
            panel_origin=(sw + gap, 0),
            panel_size=(swatch_w, sh),
            avg_rgb=avg_rgb if not isinstance(avg_rgb, Image.Image) else None,
            avg_lab=avg_lab,
            text_block=text_block,
        )

    return canvas


def _overlay_swatch_text(
    canvas: Image.Image,
    swatch_rgb: Tuple[int, int, int],
    panel_origin: Tuple[int, int],
    panel_size: Tuple[int, int],
    avg_rgb: Optional[Sequence[float]] = None,
    avg_lab: Optional[Sequence[float]] = None,
    text_block: Optional[List[str]] = None,
) -> None:
    """Draw labels on a swatch panel.

    When ``text_block`` is given, those lines are rendered verbatim
    (first line as heading, rest as body). Otherwise an auto-generated
    "Average / RGB / Lab" block is built from ``avg_rgb`` and
    ``avg_lab`` (the existing solid-swatch behaviour).
    """
    draw = ImageDraw.Draw(canvas)
    px, py = panel_origin
    pw, ph = panel_size

    # Font size scales with panel width so labels stay readable on both
    # small and huge stamps. Capped so it doesn't dominate the panel.
    font_size = max(14, min(36, pw // 12))
    heading_font = _load_font(font_size + 4)
    body_font = _load_font(font_size)

    text_color = _best_text_color(swatch_rgb)

    if text_block is not None and text_block:
        # Custom lines: first = heading, rest = body. Empty list falls
        # through to the auto path so a caller passing [] still gets
        # something sensible if avg_rgb was provided.
        lines = [(text_block[0], heading_font)]
        for ln in text_block[1:]:
            lines.append((ln, body_font))
    else:
        if avg_rgb is None:
            # Nothing to draw — caller asked for include_values but
            # didn't give us solid-RGB material to format.
            return
        lines = [
            ("Average", heading_font),
            (f"RGB  {int(round(avg_rgb[0])):3d}, "
             f"{int(round(avg_rgb[1])):3d}, "
             f"{int(round(avg_rgb[2])):3d}", body_font),
        ]
        if avg_lab is not None:
            lines.append((
                f"L*a*b*  {avg_lab[0]:.1f}, {avg_lab[1]:.1f}, {avg_lab[2]:.1f}",
                body_font,
            ))

    # Simple top-padded left-aligned stack. Padding is proportional so it
    # looks right across sizes.
    pad_x = max(8, pw // 20)
    cursor_y = max(8, ph // 20)
    for text, font in lines:
        draw.text((px + pad_x, py + cursor_y), text, font=font, fill=text_color)
        # `font.getbbox` is present on truetype and default fonts alike.
        try:
            bbox = font.getbbox(text)
            line_h = bbox[3] - bbox[1]
        except AttributeError:
            line_h = font_size
        cursor_y += line_h + max(4, font_size // 3)
