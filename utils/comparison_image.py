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

from typing import Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont


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


# --------------------------------------------------------------------------- #
# Layout 1: swatch behind the stamp
# --------------------------------------------------------------------------- #

def compose_swatch_layer(
    stamp_image: Image.Image,
    avg_rgb: Sequence[float],
    frame_padding: int = 60,
) -> Image.Image:
    """Return the stamp pasted on top of a solid swatch layer.

    Args:
        stamp_image: PIL image of the stamp. May be RGBA (transparent
            background from a shaped crop) or any other mode.
        avg_rgb: Averaged sample colour as (R, G, B) in 0..255.
        frame_padding: Pixels of swatch visible around the stamp on
            every side. Gives the swatch room to show around a fully
            opaque image and to surround a transparent-crop shape.

    Returns:
        A new RGB PIL Image of size
        ``(stamp_w + 2*padding, stamp_h + 2*padding)``.
    """
    swatch_rgb = _to_int_rgb(avg_rgb)
    sw, sh = stamp_image.size
    canvas_size = (sw + 2 * frame_padding, sh + 2 * frame_padding)

    canvas = Image.new("RGB", canvas_size, swatch_rgb)

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
    avg_rgb: Sequence[float],
    avg_lab: Optional[Sequence[float]] = None,
    swatch_ratio: float = 0.35,
    gap: int = 16,
    include_values: bool = True,
) -> Image.Image:
    """Return a combined 'stamp | swatch' panel.

    Args:
        stamp_image: PIL image of the stamp.
        avg_rgb: Averaged sample colour, 0..255.
        avg_lab: Optional averaged Lab tuple; if supplied (and
            ``include_values=True``) it's printed on the swatch panel.
        swatch_ratio: Swatch panel width as a fraction of the stamp width
            (default 35 %).
        gap: Pixels of white gap between the stamp and the swatch panel.
        include_values: When True, overlay RGB (and Lab, if given)
            numeric labels on the swatch.

    Returns:
        A new RGB PIL Image wide enough to contain both panels.
    """
    swatch_rgb = _to_int_rgb(avg_rgb)
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

    # Right: solid swatch panel
    canvas.paste(Image.new("RGB", (swatch_w, sh), swatch_rgb), (sw + gap, 0))

    if include_values:
        _overlay_swatch_text(
            canvas,
            swatch_rgb=swatch_rgb,
            panel_origin=(sw + gap, 0),
            panel_size=(swatch_w, sh),
            avg_rgb=avg_rgb,
            avg_lab=avg_lab,
        )

    return canvas


def _overlay_swatch_text(
    canvas: Image.Image,
    swatch_rgb: Tuple[int, int, int],
    panel_origin: Tuple[int, int],
    panel_size: Tuple[int, int],
    avg_rgb: Sequence[float],
    avg_lab: Optional[Sequence[float]] = None,
) -> None:
    """Draw 'Average', RGB, and optional Lab labels on a swatch panel."""
    draw = ImageDraw.Draw(canvas)
    px, py = panel_origin
    pw, ph = panel_size

    # Font size scales with panel width so labels stay readable on both
    # small and huge stamps. Capped so it doesn't dominate the panel.
    font_size = max(14, min(36, pw // 12))
    heading_font = _load_font(font_size + 4)
    body_font = _load_font(font_size)

    text_color = _best_text_color(swatch_rgb)

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
