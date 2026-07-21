"""
DoomScroll Detox - client/assets/generate_tray_icon.py

One-off script to generate client/assets/tray_icon.png using Pillow.
Run this once (or whenever you want to regenerate the icon) so
QSystemTrayIcon in main.py has a real image instead of an empty/broken
icon.

Usage:
    cd doomscroll-detox/client
    python assets/generate_tray_icon.py

Produces a 256x256 RGBA PNG: a circular badge with a purple-to-pink
"Dark Mode Synthwave" gradient (matching ui/styles.qss) and a simple
white "watching eye" glyph, since this whole app is about someone
watching your screen habits.
"""

from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageDraw

# --------------------------------------------------------------------------
# Palette -- kept in sync with ui/styles.qss
# --------------------------------------------------------------------------

NEON_PURPLE = (185, 103, 255)   # #b967ff
HOT_PINK = (255, 46, 151)       # #ff2e97
BG_VOID = (10, 10, 16)          # #0a0a10

SIZE = 256  # high-res; OS tray scales down as needed


def generate_tray_icon(output_path: str, size: int = SIZE) -> None:
    # -- Diagonal purple -> pink gradient, computed with numpy for a
    # smooth blend (Pillow has no built-in linear gradient primitive).
    y, x = np.mgrid[0:size, 0:size]
    t = (x + y) / (2 * (size - 1))  # 0.0 (top-left) -> 1.0 (bottom-right)

    r = (NEON_PURPLE[0] * (1 - t) + HOT_PINK[0] * t).astype(np.uint8)
    g = (NEON_PURPLE[1] * (1 - t) + HOT_PINK[1] * t).astype(np.uint8)
    b = (NEON_PURPLE[2] * (1 - t) + HOT_PINK[2] * t).astype(np.uint8)
    alpha = np.full_like(r, 255)

    gradient = np.dstack([r, g, b, alpha])
    gradient_img = Image.fromarray(gradient, mode="RGBA")

    # -- Circular mask so the icon reads as a clean badge, not a square
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    padding = int(size * 0.03)
    mask_draw.ellipse([padding, padding, size - padding, size - padding], fill=255)

    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    icon.paste(gradient_img, (0, 0), mask=mask)

    # -- Simple "watching eye" glyph in the center
    draw = ImageDraw.Draw(icon)
    cx, cy = size // 2, size // 2
    eye_w, eye_h = size * 0.52, size * 0.28

    draw.ellipse(
        [cx - eye_w / 2, cy - eye_h / 2, cx + eye_w / 2, cy + eye_h / 2],
        fill=BG_VOID + (255,),
        outline=(255, 255, 255, 255),
        width=max(2, size // 40),
    )

    pupil_r = size * 0.085
    draw.ellipse(
        [cx - pupil_r, cy - pupil_r, cx + pupil_r, cy + pupil_r],
        fill=(255, 255, 255, 255),
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    icon.save(output_path, format="PNG")
    print(f"[generate_tray_icon] Saved {size}x{size} icon to: {output_path}")


if __name__ == "__main__":
    # Resolve relative to this script's location so it works regardless
    # of the current working directory when invoked.
    default_output = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tray_icon.png")
    generate_tray_icon(default_output)
