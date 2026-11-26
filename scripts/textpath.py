"""Turns every <text> in a generated SVG into vector outlines.

GitHub shows README SVGs as images, and browsers sometimes paint an SVG image before its
embedded font has loaded, leaving the text blank. Outlines always render.
Shaping goes through HarfBuzz, so kerning and ligatures survive.
"""
import html, re
from functools import lru_cache
from pathlib import Path

import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

FONTS = Path(__file__).resolve().parent.parent / "lab" / "fonts"

# symbols missing from the fonts, drawn by hand in a 1000-unit em (y up)
SYMBOLS = {
    "→": ("M80 330 H760 L560 140 L620 80 L920 380 L620 680 L560 620 L760 430 H80 Z", 1000),
    "←": ("M920 330 H240 L440 140 L380 80 L80 380 L380 680 L440 620 L240 430 H920 Z", 1000),
    "↓": ("M450 760 V160 L270 340 L210 280 L500 -10 L790 280 L730 340 L550 160 V760 Z", 1000),
    "↗": ("M190 70 L670 550 V310 H760 V700 H370 V610 H610 L130 130 Z", 900),
}

@lru_cache(None)
def font(name):
    path = FONTS / f"{name}.ttf"
    blob = hb.Blob.from_file_path(str(path))
    face = hb.Face(blob)
    f = hb.Font(face)
    tt = TTFont(path)
    return f, tt, tt.getGlyphSet(), tt.getGlyphOrder(), face.upem

@lru_cache(None)
def glyph_path(name, gid):
    _, tt, gs, order, _ = font(name)
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:.0f}")
    gs[order[gid]].draw(pen)
    return pen.getCommands()

def runs(text):
    """Split text into (is_symbol, chunk) runs."""
    out, cur = [], ""
    for ch in text:
        if ch in SYMBOLS:
            if cur: out.append((False, cur)); cur = ""
            out.append((True, ch))
        else:
            cur += ch
    if cur: out.append((False, cur))
    return out

def layout(text, name, size, spacing=0.0):
    """Return list of (path_d_in_font_units, x_offset_px, scale) and total width px."""
    f, tt, gs, order, upem = font(name)
    s = size / upem
    items, x = [], 0.0
    for sym, chunk in runs(text):
        if sym:
            d, adv = SYMBOLS[chunk]
            k = size / 1000
            items.append((d, x, k)); x += adv * k + spacing
            continue
        buf = hb.Buffer(); buf.add_str(chunk); buf.guess_segment_properties()
        hb.shape(f, buf, {"kern": True, "liga": True})
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            d = glyph_path(name, info.codepoint)
            if d: items.append((d, x + pos.x_offset * s, s))
            x += pos.x_advance * s + spacing
    return items, x - (spacing if text else 0)

def measure(text, name, size, spacing=0.0):
    return layout(text, name, size, spacing)[1]

def font_for(cls):
    c = set(cls.split())
    if "serif" in c: return "serif-italic"
    if "mono" in c: return "mono-bold" if "b" in c else "mono"
    return "grotesk-bold" if "b" in c else "grotesk"

ATTR = re.compile(r'([\w-]+)="([^"]*)"')
TEXT = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)

def to_path(attrs, content, defs):
    a = dict(ATTR.findall(attrs))
    text = html.unescape(re.sub(r"<[^>]+>", "", content))
    size = float(a.get("font-size", 16)); spacing = float(a.get("letter-spacing", 0))
    name = font_for(a.get("class", "sans"))
    items, width = layout(text, name, size, spacing)
    x, y = float(a.get("x", 0)), float(a.get("y", 0))
    anchor = a.get("text-anchor", "start")
    if anchor == "middle": x -= width / 2
    elif anchor == "end": x -= width
    parts = []
    for d, ox, k in items:
        gid = defs.setdefault(d, f"g{len(defs)}")
        parts.append(f'<use href="#{gid}" transform="translate({x+ox:.1f} {y:.1f}) scale({k:.5f} {-k:.5f})"/>')
    keep = " ".join(f'{k}="{v}"' for k, v in a.items()
                    if k in ("fill", "opacity", "style", "fill-opacity", "transform", "stroke", "stroke-width", "paint-order", "stroke-linejoin"))
    return f'<g {keep}>{"".join(parts)}</g>'

def outline(svg):
    defs = {}
    svg = TEXT.sub(lambda m: to_path(m.group(1), m.group(2), defs), svg)
    if defs:
        block = "<defs>" + "".join(f'<path id="{i}" d="{d}"/>' for d, i in defs.items()) + "</defs>"
        svg = re.sub(r"(<svg\b[^>]*>)", lambda m: m.group(1) + "\n" + block, svg, count=1)
    return svg
