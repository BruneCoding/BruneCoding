"""Render the ascii-magic pieces into README-friendly images.

GitHub strips <script> and custom elements from a README, so
<ascii-art piece="..."> cannot run there. Instead each piece is run in Node
(tools/ascii/render.mjs), rasterised here, and committed as an image.

    python tools/build_ascii.py hobbies      # rocket -> Saturn + floating hobbies (animated)
    python tools/build_ascii.py seedfinder   # wave function collapse banner (animated)
    python tools/build_ascii.py orbit        # window onto the Earth (animated)
    python tools/build_ascii.py moon         # TODAY's moon phase, as a crisp SVG (daily Action)
    python tools/build_ascii.py all          # everything

Needs: node 18+, Pillow, numpy.
"""

from __future__ import annotations

import datetime as dt
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import pixfont
from ascii_raster import BG, Glyphs, hex_rgb, load, render_dots, render_grid, save_anim

ROOT = Path(__file__).resolve().parent.parent
NODE_DIR = ROOT / "tools" / "ascii"
OUT = ROOT / "assets" / "art"
EXT = "gif"                    # "webp" is ~3x smaller if you prefer it
W = 832                        # every picture is this wide, so the README column stays even
CW, CH = 8, 13                 # cell size in pixels
ACCENT = (245, 184, 46)        # the card's gold
PLATE = (10, 14, 26)


def run_piece(slug: str, *args) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / f"{slug}.json"
        subprocess.run(["node", "render.mjs", slug, str(out), *map(str, args)], cwd=NODE_DIR, check=True,
                       stdout=subprocess.DEVNULL)
        return load(out)


def fit(img: np.ndarray, width: int = W, height: int | None = None) -> np.ndarray:
    """Scale to `width` (nearest, so pixels stay square-ish) and pad/crop to `height` with edge colour."""
    h, w = img.shape[:2]
    if w != width:
        img = np.asarray(Image.fromarray(img).resize((width, round(h * width / w)), Image.NEAREST))
    if height is not None:
        d = height - img.shape[0]
        if d > 0:
            img = np.pad(img, ((d // 2, d - d // 2), (0, 0), (0, 0)), mode="edge")
        elif d < 0:
            img = img[(-d) // 2:(-d) // 2 + height]
    return img


def blend(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    return np.clip(a * (1 - t) + b * t + 0.5, 0, 255).astype(np.uint8)


def write(frames: list[np.ndarray], name: str, fps: float) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.{EXT}"
    size = save_anim([Image.fromarray(f) for f in frames], path, fps)
    print(f"wrote {path.relative_to(ROOT)}  {len(frames)} frames, {size / 1e6:.2f} MB")


# --- Hobbies: rocket -> Saturn, hobbies orbiting ---------------------------------
HOBBIES = ["SPACE", "MATHS", "PHYSICS", "PLANES", "ROCKETS", "MINECRAFT", "ROBLOX", "BLOXD.IO"]


def labels_at(t: float, cols: int, rows: int) -> dict:
    """Hobby tags riding one slow ellipse around the scene; far side dims and sits behind."""
    cx, cy, rx, ry = cols / 2 + 2, rows / 2 + 1, cols / 2 - 14, rows / 2 - 7
    items = []
    for i, name in enumerate(HOBBIES):
        a = math.tau * (i / len(HOBBIES) + t / 16.0)
        items.append((math.sin(a), i, name, cx + rx * math.cos(a), cy + ry * math.sin(a)))
    plates = {}
    for depth, _, name, x, y in sorted(items):                  # far first, near last
        front = depth > 0
        fg = ACCENT if front else (128, 98, 30)
        bg = PLATE if front else (6, 8, 14)
        txt = f" {name} "
        x0, y0 = round(x - len(txt) / 2), round(y)
        for k, c in enumerate(txt):
            plates[(x0 + k, y0)] = (c, fg, bg)
    return plates


def build_hobbies() -> None:
    fps = 10
    rock = run_piece("rocket-launch", 0, 13, fps)
    ring = run_piece("ring-shadow-closeup", 0, 16, fps)
    gr, gg = Glyphs(CW, CH), Glyphs(CW, CH)
    H = 520

    def rocket_img(i):
        return fit(render_grid(rock["frames"][i], rock["palette"], rock["cols"], rock["rows"], gr), W, H)

    def ring_img(i):
        t = i / fps
        return fit(render_grid(ring["frames"][i % len(ring["frames"])], ring["palette"], ring["cols"], ring["rows"], gg,
                               labels_at(t, ring["cols"], ring["rows"])), W, H)

    frames = []
    n_rocket = 110                                   # 11 s: ignition, liftoff, the rocket leaves the top
    for i in range(n_rocket):
        frames.append(rocket_img(i))
    for i in range(20):                              # 2 s dissolve from empty dusk into space
        frames.append(blend(rocket_img(n_rocket + i), ring_img(i), (i + 1) / 20))
    for i in range(20, 150):                         # Saturn, hobbies orbiting
        frames.append(ring_img(i))
    for i in range(10):                              # 1 s dissolve back to the launch pad
        frames.append(blend(ring_img(150 + i), rocket_img(0), (i + 1) / 10))
    write(frames, "hobbies", fps)


def build_seedfinder() -> None:
    fps = 10
    d = run_piece("wave-function-collapse", 0, 15, fps)
    gl = Glyphs(CW, CH)
    txt = " > SEEDFINDER "
    plates = {(2 + k, d["rows"] - 3): (c, ACCENT, PLATE) for k, c in enumerate(txt)}
    sub = " for bloxd.io "
    plates.update({(2 + k, d["rows"] - 2): (c, (139, 148, 158), PLATE) for k, c in enumerate(sub)})
    write([fit(render_grid(f, d["palette"], d["cols"], d["rows"], gl, plates), W) for f in d["frames"]], "seedfinder", fps)


def build_orbit() -> None:
    fps = 10
    # one pass of the satellite across the window in 12 s (it crosses in ~30 s of the piece's own time)
    d = run_piece("orbit-window-earth", 14, 26, fps, 2.55)
    write([fit(render_dots(f, d["palette"], d["cols"], d["rows"], 5), W) for f in d["frames"]], "orbit", fps)


# --- Moon: today's real phase, as an SVG -----------------------------------------
SYNODIC = 29.530588853
NEW_MOON = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)


def moon_age(now: dt.datetime | None = None) -> float:
    """Fraction of the lunar cycle elapsed: 0 new, 0.5 full."""
    now = now or dt.datetime.now(dt.timezone.utc)
    return (((now - NEW_MOON).total_seconds() / 86400) % SYNODIC) / SYNODIC


def frame_svg(frame: dict, pal: dict, cols: int, rows: int, cw: int = CW, ch: int = CH, label: str = "") -> str:
    """A grid frame as pure rectangles: no fonts, so it renders identically everywhere."""
    lines, keys = frame["text"].split("\n"), frame["color"].split("\n")
    paths: dict[tuple, list[str]] = {}
    circles: list[str] = []

    def add(fill, op, x, y, w, h):
        paths.setdefault((fill, op), []).append(f"M{x:g} {y:g}h{w:g}v{h:g}h{-w:g}z")

    px, py = cw / (pixfont.ADV), ch / (pixfont.H + 1)
    for y in range(rows):
        x = 0
        while x < cols:
            c, k = lines[y][x], keys[y][x]
            fill = pal.get(k, "#ffffff")
            if c == " ":
                x += 1
                continue
            if c in "░▒▓█":
                op = {"░": 0.25, "▒": 0.5, "▓": 0.75, "█": 1}[c]
                e = x
                while e < cols and lines[y][e] == c and keys[y][e] == k:
                    e += 1
                add(fill, op, x * cw, y * ch, (e - x) * cw, ch)
                x = e
                continue
            ox, oy = x * cw, y * ch
            if c == "·":
                add(fill, 1, ox + cw / 2 - 1, oy + ch / 2 - 1, 2, 2)
            elif c == ".":
                add(fill, 1, ox + cw / 2 - 1, oy + ch * 0.7, 2, 2)
            elif c == "+":
                add(fill, 1, ox + 1, oy + ch / 2 - 1, cw - 2, 2); add(fill, 1, ox + cw / 2 - 1, oy + 2, 2, ch - 4)
            elif c == "●":
                circles.append(f'<circle cx="{ox + cw / 2:g}" cy="{oy + ch / 2:g}" r="3.4" fill="{fill}"/>')
            elif c == "○":
                circles.append(f'<circle cx="{ox + cw / 2:g}" cy="{oy + ch / 2:g}" r="2.9" fill="none" stroke="{fill}" stroke-width="1.3"/>')
            else:
                rows_ = pixfont.glyph(c)
                for r, row in enumerate(rows_):
                    for cc in range(pixfont.W):
                        if row[cc] == "#":
                            add(fill, 1, ox + cc * px + px * 0.5, oy + r * py + py * 0.5, px, py)
            x += 1
    body = []
    for (fill, op), d in paths.items():
        o = "" if op == 1 else f' fill-opacity="{op}"'
        body.append(f'<path fill="{fill}"{o} d="{"".join(d)}"/>')
    w, h = cols * cw, rows * ch
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{label}">\n<rect width="{w}" height="{h}" rx="15" fill="#0d1117"/>\n'
            f'<g shape-rendering="crispEdges">\n{chr(10).join(body)}\n</g>\n{chr(10).join(circles)}\n</svg>\n')


def build_moon(now: dt.datetime | None = None) -> None:
    age = moon_age(now)
    t = age * 18                                       # the piece's cycle is 18 s long
    d = run_piece("moon-phases", "still", t)
    names = ["new moon", "waxing crescent", "first quarter", "waxing gibbous", "full moon", "waning gibbous", "last quarter", "waning crescent"]
    label = f"Today's moon: {names[int(age * 8 + 0.5) % 8]}, {round((1 - math.cos(age * math.tau)) / 2 * 100)}% lit"
    svg = frame_svg(d["frames"][0], d["palette"], d["cols"], d["rows"], label=label)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "moon.svg").write_text(svg, encoding="utf-8")   # carries its own dark background, so one file serves both themes
    print(f"wrote assets/art/moon.svg  ({label}, {len(svg) / 1024:.0f} KB)")


JOBS = {"hobbies": build_hobbies, "seedfinder": build_seedfinder, "orbit": build_orbit, "moon": build_moon}

if __name__ == "__main__":
    which = sys.argv[1:] or ["all"]
    for name in (JOBS if "all" in which else which):
        JOBS[name]()
