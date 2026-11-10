"""Turn assets/BrunePFP.jpeg into the card's coloured ASCII portrait.

Writes assets/ascii-art.txt (dark card), assets/ascii-art-light.txt (light card)
and assets/ascii-colors.json (one hex colour per character, per theme), which
tools/build_card.py reads to tint every glyph with the pixel it came from.

The image is sampled on a 87 x 47 grid: a terminal cell is ~0.54 as wide as it
is tall, so a square picture needs 47 rows for 87 columns (the same ratio
build_card.ART_CELL_ASPECT assumes). Cells outside the avatar's ring are left
blank so it floats on the card as a round badge.

Usage:
    python tools/make_ascii.py
"""

from __future__ import annotations

import colorsys
import json
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "BrunePFP.jpeg"

COLS, ROWS = 87, 47
RAMP = " .:-=+*#%@"
RING_RADIUS = 0.485          # fraction of the image width; just past the red ring


def sample() -> Image.Image:
    img = Image.open(SRC).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.15)
    return img.resize((COLS, ROWS), Image.LANCZOS)


def inside(x: int, y: int) -> bool:
    dx = (x + 0.5) / COLS - 0.5
    dy = (y + 0.5) / ROWS - 0.5
    return dx * dx + dy * dy <= RING_RADIUS ** 2


def tint(rgb: tuple[int, int, int], vmin: float, vmax: float, smin: float) -> str:
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    s = max(s, smin) if s > 0.08 else s
    v = min(max(v, vmin), vmax)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def render(img: Image.Image, light: bool) -> tuple[list[str], list[list[str]]]:
    lines, colors = [], []
    for y in range(ROWS):
        line, row = [], []
        for x in range(COLS):
            if not inside(x, y):
                line.append(" "); row.append("")
                continue
            rgb = img.getpixel((x, y))
            luma = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255
            # Subject dense, background sparse in both themes; only the ink differs
            # (brightened for the dark card, darkened for the white one).
            _, sat, val = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
            d = min(1.0, max(max(0.0, luma * 2.3 - 0.08) ** 0.9, 1.3 * sat * val))
            col = tint(rgb, 0.25, 0.72, 0.0) if light else tint(rgb, 0.78, 1.0, 0.0)
            idx = round(d * (len(RAMP) - 1))
            if idx == 0:
                line.append(" "); row.append("")
            else:
                line.append(RAMP[idx]); row.append(col)
        lines.append("".join(line).rstrip().ljust(COLS))
        colors.append(row)
    return lines, colors


def main() -> None:
    img = sample()
    out = {}
    for theme, light in (("dark", False), ("light", True)):
        lines, colors = render(img, light)
        name = "ascii-art-light.txt" if light else "ascii-art.txt"
        (ROOT / "assets" / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        out[theme] = colors
        print(f"wrote assets/{name} ({COLS}x{ROWS})")
    (ROOT / "assets" / "ascii-colors.json").write_text(json.dumps(out), encoding="utf-8")
    print("wrote assets/ascii-colors.json")


if __name__ == "__main__":
    main()
