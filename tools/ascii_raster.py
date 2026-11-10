"""Rasterise ascii-magic frames ({text, color} grids) into pixel images.

The pieces draw into a character grid: a glyph and a palette key per cell. This
module turns that into real pixels without ever touching a font for the shading
characters, so the output is crisp flat colour (cheap to compress) rather than
anti-aliased type. Everything is vectorised with numpy: a frame is one fancy
index into a stack of per-glyph masks.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BG = (13, 17, 23)                         # GitHub dark canvas
FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
)
SHADE = {"░": 0.25, "▒": 0.5, "▓": 0.75, "█": 1.0}
LOWER = {c: (i + 1) / 8 for i, c in enumerate("▁▂▃▄▅▆▇█")}


def hex_rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _font(size: int) -> ImageFont.FreeTypeFont:
    for f in FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


class Glyphs:
    """Alpha masks (cell-sized, 0..1) for every character, built on demand."""

    def __init__(self, cw: int, ch: int) -> None:
        self.cw, self.ch = cw, ch
        self.font = _font(max(6, round(cw / 0.602)))
        self.index: dict[str, int] = {}
        self.masks: list[np.ndarray] = []
        self.get(" ")

    def get(self, c: str) -> int:
        if c in self.index:
            return self.index[c]
        self.index[c] = len(self.masks)
        self.masks.append(self._make(c))
        return self.index[c]

    def stack(self) -> np.ndarray:
        return np.stack(self.masks)

    def _make(self, c: str) -> np.ndarray:
        cw, ch = self.cw, self.ch
        if c == " ":
            return np.zeros((ch, cw), np.float32)
        if c in SHADE:
            return np.full((ch, cw), SHADE[c], np.float32)
        m = Image.new("L", (cw, ch), 0)
        d = ImageDraw.Draw(m)
        mx, my = cw / 2 - 0.5, ch / 2 - 0.5
        if c in LOWER:
            h = max(1, round(ch * LOWER[c]))
            d.rectangle([0, ch - h, cw, ch], fill=255)
        elif c in "▟▙":
            hw, hh = cw // 2, ch // 2
            d.rectangle([0, hh, cw, ch], fill=255)
            d.rectangle([cw - hw, 0, cw, hh], fill=255) if c == "▟" else d.rectangle([0, 0, hw, hh], fill=255)
        elif c in "║═╔╗╲╱╳":
            a, b = round(mx) - 1, round(mx) + 1
            hy0, hy1 = round(my) - 1, round(my) + 1
            if c == "║":
                d.line([a, 0, a, ch], fill=255); d.line([b, 0, b, ch], fill=255)
            elif c == "═":
                d.line([0, hy0, cw, hy0], fill=255); d.line([0, hy1, cw, hy1], fill=255)
            elif c == "╔":
                d.line([a, hy0, cw, hy0], fill=255); d.line([b, hy1, cw, hy1], fill=255)
                d.line([a, hy0, a, ch], fill=255); d.line([b, hy1, b, ch], fill=255)
            elif c == "╗":
                d.line([0, hy0, b, hy0], fill=255); d.line([0, hy1, a, hy1], fill=255)
                d.line([b, hy0, b, ch], fill=255); d.line([a, hy1, a, ch], fill=255)
            if c in "╲╳":
                d.line([0, 0, cw, ch], fill=255)
            if c in "╱╳":
                d.line([cw, 0, 0, ch], fill=255)
        else:
            d.fontmode = "1"
            d.text((cw / 2, round(ch * 0.76)), c, font=self.font, fill=255, anchor="ms")
        return np.asarray(m, np.float32) / 255.0


def render_grid(frame: dict, pal: dict, cols: int, rows: int, gl: Glyphs,
                plates: dict | None = None) -> np.ndarray:
    """One frame -> uint8 RGB array (rows*ch, cols*cw, 3).

    `plates` maps (x, y) -> (char, fg_rgb, bg_rgb) for labels laid over the art.
    """
    lines = frame["text"].split("\n")
    keys = frame["color"].split("\n")
    idx = np.zeros((rows, cols), np.int32)
    col = np.zeros((rows, cols, 3), np.float32)
    bg = np.empty((rows, cols, 3), np.float32)
    bg[:] = BG
    rgb = {k: hex_rgb(v) for k, v in pal.items()}
    for y in range(rows):
        t, k = lines[y], keys[y]
        for x in range(cols):
            ch = t[x] if x < len(t) else " "
            if ch == " ":
                continue
            idx[y, x] = gl.get(ch)
            col[y, x] = rgb.get(k[x], (255, 255, 255)) if x < len(k) else (255, 255, 255)
    if plates:
        for (x, y), (ch, fg, pb) in plates.items():
            if 0 <= x < cols and 0 <= y < rows:
                idx[y, x] = gl.get(ch); col[y, x] = fg; bg[y, x] = pb
    return _compose(idx, col, bg, gl)


def _compose(idx, col, bg, gl) -> np.ndarray:
    masks = gl.stack()
    a = masks[idx][..., None]                                  # rows, cols, ch, cw, 1
    out = bg[:, :, None, None, :] * (1 - a) + col[:, :, None, None, :] * a
    rows, cols = idx.shape
    out = out.transpose(0, 2, 1, 3, 4).reshape(rows * gl.ch, cols * gl.cw, 3)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def render_dots(frame: dict, pal: dict, cols: int, rows: int, cell: int) -> np.ndarray:
    """The halftone `dots` look: a disc per cell, sized by the level glyph."""
    lines = frame["text"].split("\n")
    keys = frame["color"].split("\n")
    rgb = {k: hex_rgb(v) for k, v in pal.items()}
    lv = np.zeros((rows, cols), np.int32)
    col = np.zeros((rows, cols, 3), np.float32)
    for y in range(rows):
        for x in range(cols):
            lv[y, x] = "▁▂▃▄▅▆▇█".index(lines[y][x]) if lines[y][x] in "▁▂▃▄▅▆▇█" else 7
            col[y, x] = rgb[keys[y][x]]
    yy, xx = np.mgrid[0:cell, 0:cell].astype(np.float32)
    dist = np.hypot(xx - (cell - 1) / 2, yy - (cell - 1) / 2)
    masks = np.stack([np.clip((cell * (0.30 + 0.12 * l) - dist) * 2, 0, 1) if l < 7 else np.ones((cell, cell), np.float32)
                      for l in range(8)])
    a = masks[lv][..., None]
    out = np.asarray(BG, np.float32) * (1 - a) + col[:, :, None, None, :] * a
    out = out.transpose(0, 2, 1, 3, 4).reshape(rows * cell, cols * cell, 3)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def save_anim(frames: list[Image.Image], path: str | Path, fps: float) -> int:
    """Write an animated WebP (small) or GIF depending on the extension."""
    path = Path(path)
    dur = round(1000 / fps)
    if path.suffix == ".webp":
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=dur, loop=0,
                       lossless=False, quality=82, method=4, minimize_size=True)
    else:
        pal = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
        pal[0].save(path, save_all=True, append_images=pal[1:], duration=dur, loop=0, optimize=True, disposal=1)
    return path.stat().st_size
