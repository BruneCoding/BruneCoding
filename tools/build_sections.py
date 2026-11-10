"""Pixel-art section headers and project buttons for the README.

Same toolbox as the card and the link buttons: colours from build_card.THEMES,
a pixel font drawn from rectangles (pixfont.py), stepped corners, one accent bar.

  section_<name>_<theme>.svg          a `> TITLE ----------` rule across the column
  projects/<slug>_<theme>.svg         one button per project: icon + NAME, nothing else

Project icons: drop <slug>.png next to the README (or in assets/ or assets/icons/)
and re-run this script (the Action does it on push). The PNG is shrunk to a chunky
18x18 grid and embedded in the SVG, because a README image can't load files. Until
a PNG exists the button shows a placeholder sprite.

Usage:
    python tools/build_sections.py
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

import pixfont
from build_card import THEMES
from build_pacman import CANVAS_W, CLAUDE_CORAL, bitmap, mix, sprite_path

ROOT = Path(__file__).resolve().parent.parent
PX = 3
GAP = 14
HEIGHT = 20 * PX
TEXT_PX = 2                      # label pixel size (glyphs are 10 x 14 px)
ICON = 36                        # icon box, 12 sprite pixels
ICON_GRID = 18                   # icons are quantised to this many pixels a side
ICON_GAP = 14
OUTLINE_MIX = 0.18

SECTIONS = ("projects", "hobbies", "contributions", "accounts", "orbit", "moon")
TITLES = {
    "projects": "PROJECTS",
    "hobbies": "HOBBIES",
    "moon": "THE MOON TODAY",
    "orbit": "VIEW FROM ORBIT",
    "contributions": "CONTRIBUTIONS",
    "accounts": "GAMING ACCOUNTS",
}

# (slug, label, url, accent, row). The label is all the button says.
PROJECTS = (
    ("arborultra", "ARBOR ULTRA!", "https://greasyfork.org/en/scripts/600113-1-9-arbor-%F0%9D%96%80%F0%9D%93%9B%F0%9D%93%A3%E2%84%9B%F0%9D%93%90", "key", 0),
    ("raybrowser", "RAY BROWSER", "https://brunecoding.github.io/Ray-Browser/Codebase/index.html", "value", 0),
    ("brunglebrowser", "BRUNGLE BROWSER", "https://brungle.pages.dev", "coral", 0),
    ("brunglestudio", "BRUNGLE STUDIO", "https://brunecoding.github.io/Brungle-AI-Studio/Codebase/Mainbase/main.html", "key", 1),
    ("bloxdtrailer", "BLOXD.IO TRAILER", "https://drive.google.com/file/d/1fvE1s8JKwhEYwi2T2MUYJtDti9Kij-KV/view?usp=sharing", "value", 1),
)

PLACEHOLDER = """
############
#..........#
#.....##...#
#.....##...#
#..#.......#
#.###..###.#
#########..#
############
"""


def section(theme: str, title: str) -> str:
    c = THEMES[theme]
    px, h = 3, 37
    label = "> " + title + " "
    tw = pixfont.text_width(label, px)
    y = 8
    return f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}px" height="{h}px" viewBox="0 0 {CANVAS_W} {h}">
<g shape-rendering="crispEdges">
<path d="{pixfont.text_path(label, 0, y, px)}" fill="{c['key']}"/>
<rect x="{tw + 6:g}" y="{y + 9}" width="{CANVAS_W - tw - 6:g}" height="{px}" fill="{c['dots']}"/>
</g>
</svg>
"""


def find_icon(slug: str) -> Path | None:
    for d in (ROOT, ROOT / "assets", ROOT / "assets" / "icons", ROOT / "icons"):
        p = d / f"{slug}.png"
        if p.exists():
            return p
    return None


def icon_data_uri(path: Path) -> str:
    im = Image.open(path).convert("RGBA")
    im.thumbnail((ICON_GRID, ICON_GRID), Image.LANCZOS)
    canvas = Image.new("RGBA", (ICON_GRID, ICON_GRID), (0, 0, 0, 0))
    canvas.paste(im, ((ICON_GRID - im.width) // 2, (ICON_GRID - im.height) // 2))
    big = canvas.resize((ICON, ICON), Image.NEAREST)             # chunky 2 px pixels
    buf = io.BytesIO()
    big.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def stepped(x: float, y: float, w: float, h: float) -> str:
    return (f"M{x + PX:g} {y:g}h{w - 2 * PX:g}v{PX}h{PX}v{h - 2 * PX:g}h{-PX}v{PX}"
            f"h{-(w - 2 * PX):g}v{-PX}h{-PX}v{-(h - 2 * PX):g}h{PX}z")


def button(theme: str, slug: str, label: str, accent_key: str, slot: int, n: int) -> str:
    c = THEMES[theme]
    accent = CLAUDE_CORAL[theme] if accent_key == "coral" else c[accent_key]
    slot_w = CANVAS_W / n
    button_w = (CANVAS_W - (n - 1) * GAP) / n
    x = slot * GAP / n
    label_w = pixfont.text_width(label, TEXT_PX)
    assert ICON + ICON_GAP + label_w <= button_w - 8 * PX, f"{label!r} does not fit its button"
    left = x + (button_w - ICON - ICON_GAP - label_w) / 2
    mid = (PX + HEIGHT - 2 * PX) / 2
    top = round(mid - 7)                       # a glyph is 14 px tall
    icon_y = round(mid - ICON / 2)
    png = find_icon(slug)
    if png:
        icon = (f'<image x="{left:.0f}" y="{icon_y}" width="{ICON}" height="{ICON}" '
                f'style="image-rendering:pixelated" href="{icon_data_uri(png)}"/>')
    else:
        icon = (f'<g fill="{accent}" transform="translate({left + ICON / 2:.1f},{icon_y + ICON / 2})">'
                f'<path d="{sprite_path(bitmap(PLACEHOLDER), PX, PX)}"/></g>')
    return f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" width="{slot_w:.3f}px" height="{HEIGHT}px" viewBox="0 0 {slot_w:.3f} {HEIGHT}">
<g shape-rendering="crispEdges">
<path d="{stepped(x, 0, button_w, HEIGHT)}" fill="{mix(c['bg'], c['fg'], OUTLINE_MIX)}"/>
<path d="{stepped(x + PX, PX, button_w - 2 * PX, HEIGHT - 2 * PX)}" fill="{c['bg']}"/>
<rect x="{x + 2 * PX:g}" y="{HEIGHT - 2 * PX}" width="{button_w - 4 * PX:g}" height="{PX}" fill="{accent}"/>
{icon}
<path d="{pixfont.text_path(label, round(left + ICON + ICON_GAP), top, TEXT_PX)}" fill="{c['fg']}"/>
</g>
</svg>
"""


def main() -> None:
    (ROOT / "projects").mkdir(exist_ok=True)
    for theme in THEMES:
        for name in SECTIONS:
            (ROOT / f"section_{name}_{theme}.svg").write_text(section(theme, TITLES[name]), encoding="utf-8")
        for row in sorted({p[4] for p in PROJECTS}):
            ps = [p for p in PROJECTS if p[4] == row]
            for slot, (slug, label, _url, accent, _r) in enumerate(ps):
                (ROOT / "projects" / f"{slug}_{theme}.svg").write_text(
                    button(theme, slug, label, accent, slot, len(ps)), encoding="utf-8")
    for slug, *_ in PROJECTS:
        p = find_icon(slug)
        print(f"{slug:15} icon: {p.relative_to(ROOT) if p else 'none yet (placeholder)'}")
    print("wrote section headers and project buttons")


if __name__ == "__main__":
    main()
