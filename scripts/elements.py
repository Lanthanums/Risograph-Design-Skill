#!/usr/bin/env python3
"""elements.py — the riso element library.

Every decoration is drawn by code. Nothing is loaded from a reference poster, a
previous deck or a stock asset: an element is a function of (ink colours, size,
seed, params) that returns a transparent RGBA image ready to drop on a slide.

The three dialects that were reverse-engineered from finished posters
(collage A, doodle-journal B, Swiss-geometric C) are implemented here; the
remaining categories live in elements_b.py and register into the same registry.

Design rules baked into the generators:
  * hand-drawn means jittered control points AND varying stroke width, never a
    clean vector outline;
  * every shape gets ink unevenness (grain, small voids) so it reads as printed;
  * rotation, size and ink assignment are the caller's business — the element
    itself is drawn upright and unrotated so the composer can vary it per page.

Usage
-----
  python elements.py catalogue                 # list everything, grouped
  python elements.py sheet out.jpg [--group A] # render a contact sheet to eyeball
"""
import sys
sys.dont_write_bytecode = True
import argparse
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textmetrics as tm

SCALE = 2                      # render elements at 2x for projection
REGISTRY = {}


def element(name, category, dialects, size, note=""):
    """Register a generator. `size` = (min_w, max_w, min_h, max_h) in pt."""
    def deco(fn):
        REGISTRY[name] = {"name": name, "category": category,
                          "dialects": tuple(dialects), "size": tuple(size),
                          "note": note, "fn": fn}
        return fn
    return deco


# --------------------------------------------------------------- helpers
def px(v):
    return int(round(v * SCALE))


def canvas(w, h):
    return Image.new("RGBA", (px(w), px(h)), (0, 0, 0, 0))


def grain(img, rng, uneven=0.10, holes=0.0015, soften=0.0):
    """Ink unevenness: modulate alpha, punch tiny voids, optionally soften edges."""
    a = img.getchannel("A")
    import numpy as np
    noise = np.random.default_rng(rng.getrandbits(64))
    arr = np.asarray(a).astype("float32") / 255.0
    arr *= np.clip(noise.normal(1.0, uneven, arr.shape), 0.4, 1.0)
    if holes:
        holes_m = noise.random(arr.shape) < holes
        arr[holes_m] *= 0.25
    if soften:
        arr = np.asarray(Image.fromarray((arr * 255).astype("uint8"))
                         .filter(ImageFilter.GaussianBlur(soften))).astype("float32") / 255.0
    img.putalpha(Image.fromarray((arr * 255).astype("uint8")))
    return img


def jitter_path(pts, rng, amp=1.6, freq=0.35):
    """Wobble a polyline — the difference between 'drawn' and 'plotted'."""
    out = []
    for i, (x, y) in enumerate(pts):
        out.append((x + rng.uniform(-amp, amp), y + rng.uniform(-amp, amp)))
        if freq and i + 1 < len(pts) and rng.random() < freq:
            mx = (x + pts[i + 1][0]) / 2 + rng.uniform(-amp * 2, amp * 2)
            my = (y + pts[i + 1][1]) / 2 + rng.uniform(-amp * 2, amp * 2)
            out.append((mx, my))
    return out


def resample(pts, step=2.0):
    """Dense points along a polyline, for variable-width stroking."""
    if len(pts) < 2:
        return list(pts)
    out = [pts[0]]
    for i in range(1, len(pts)):
        x0, y0 = out[-1] if False else pts[i - 1]
        x1, y1 = pts[i]
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(d / step))
        for k in range(1, n + 1):
            t = k / n
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    return out


def marker_stroke(img, pts, colour, width, rng, taper=(0.55, 1.0),
                  alpha=255, jitter=None, resample_step=1.2):
    """A pen/marker stroke: overlapping discs with jittered radius.

    Tapering the ends plus radius jitter is what makes a line read as hand-drawn
    rather than as a vector path with a stroke width. Jitter is capped relative
    to the stroke width, otherwise thin lines bead up into a dotted chain.
    """
    d = ImageDraw.Draw(img)
    path = resample(pts, resample_step * SCALE)
    n = max(2, len(path))
    if jitter is None:
        jitter = min(0.30, 0.75 / max(0.6, width))
    for i, (x, y) in enumerate(path):
        t = i / (n - 1)
        w = width * SCALE * (taper[0] + (taper[1] - taper[0])
                             * math.sin(math.pi * t) ** 0.5)
        w = max(1.0, w * (1 + rng.uniform(-jitter, jitter)))
        ox, oy = rng.uniform(-w * 0.10, w * 0.10), rng.uniform(-w * 0.10, w * 0.10)
        d.ellipse([x - w / 2 + ox, y - w / 2 + oy, x + w / 2 + ox, y + w / 2 + oy],
                  fill=tuple(colour) + (alpha,))
    return img


def bezier(p0, p1, p2, p3, n=48):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def arc_pts(cx, cy, rx, ry, a0, a1, n=48, start_open=0.0):
    pts = []
    a0 += start_open
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def ragged_polygon(pts, rng, amp=2.2):
    """Push a polygon's vertices around and subdivide its edges."""
    out = []
    for i, (x, y) in enumerate(pts):
        out.append((x + rng.uniform(-amp, amp) * SCALE,
                    y + rng.uniform(-amp, amp) * SCALE))
        if rng.random() < 0.5 and i + 1 < len(pts):
            nx, ny = pts[i + 1]
            out.append(((x + nx) / 2 + rng.uniform(-amp, amp) * SCALE,
                        (y + ny) / 2 + rng.uniform(-amp, amp) * SCALE))
    return out


def fit_text(txt, family, size, max_w, min_size=5.0):
    """Shrink a label until it fits — a label inside a stamp/tag/ticket must
    not run past its own frame, which is the same class of bug as text leaving
    the slide. Never let an element's own label overflow the element."""
    s = size
    while s > min_size and tm.advance(txt, family, s) > max_w:
        s *= 0.94
    return s


def text_image(txt, family, size, colour, bold=False, spc=0.0):
    """Render text to an RGBA tile using the same metrics the layout uses."""
    w = tm.advance(txt, family, size, bold, spc)
    h = tm.line_height(family, size, bold, 1.0)
    img = Image.new("RGBA", (max(2, px(w)), max(2, px(h))), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = tm.font(family, size * SCALE, bold)
    if f is None:
        return img
    x = 0.0
    for ch in txt:
        d.text((x, 0), ch, font=f, fill=tuple(colour) + (255,))
        x += (tm.advance(ch, family, size, bold, spc)) * SCALE
    return img


# =============================================================== collage (A)
@element("torn_paper", "collage", ("A",), (90, 380, 60, 260),
         "撕纸边纸片：边缘用抖动折线，可双色叠印")
def el_torn_paper(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    steps = 26
    pts = []
    for i in range(steps + 1):                       # top edge, torn
        pts.append((w * i / steps, rng.uniform(0, 3.2)))
    for i in range(steps + 1):                       # right
        pts.append((w - rng.uniform(0, 3.2), h * i / steps))
    for i in range(steps + 1):                       # bottom
        pts.append((w - w * i / steps, h - rng.uniform(0, 4.5)))
    for i in range(steps + 1):                       # left, torn harder
        pts.append((rng.uniform(0, 5.0), h - h * i / steps))
    poly = [(px(x), px(y)) for x, y in pts]
    d.polygon(poly, fill=tuple(ink) + (255,))
    if kw.get("second_ink"):
        off = kw.get("offset", 3.0)
        d.polygon([(x + px(off), y + px(off)) for x, y in poly],
                  fill=tuple(ink2) + (150,))
    return grain(img, rng, uneven=0.09, holes=0.002)


@element("handcut_polygon", "collage", ("A", "C"), (60, 240, 50, 200),
         "手剪折角多边形")
def el_handcut(ink, ink2, paper, size, rng, **kw):
    w, h = size
    sides = kw.get("sides", rng.randint(5, 7))
    cx, cy = w / 2, h / 2
    rx, ry = w / 2, h / 2
    pts = []
    for i in range(sides):
        a = 2 * math.pi * i / sides + rng.uniform(-0.18, 0.18)
        r = 1.0 - rng.uniform(0, 0.16)
        pts.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
    img = canvas(w, h)
    ImageDraw.Draw(img).polygon(
        ragged_polygon([(px(x), px(y)) for x, y in pts], rng, amp=1.4),
        fill=tuple(ink) + (255,))
    return grain(img, rng, uneven=0.08)


@element("washi_tape", "collage", ("A", "B", "F"), (70, 320, 18, 60),
         "和纸胶带：纯色/条纹/圆点/格子，两端锯齿或撕裂")
def el_washi_tape(ink, ink2, paper, size, rng, **kw):
    w, h = size
    mode = kw.get("mode") or rng.choice(["solid", "stripe", "dot", "grid"])
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    body = [(px(2 + rng.uniform(0, 2)), px(0)), (px(w - 2), px(0)),
            (px(w - 2), px(h)), (px(2), px(h))]
    d.polygon(body, fill=tuple(ink) + (kw.get("alpha", 190),))
    if mode == "stripe":
        x = 0
        while x < w:
            d.line([(px(x), 0), (px(x), px(h))], fill=tuple(ink2) + (200,),
                   width=px(2.5))
            x += rng.uniform(7, 12)
    elif mode == "dot":
        y = 4.0
        while y < h:
            x = rng.uniform(2, 6)
            while x < w:
                r = px(1.6)
                d.ellipse([px(x) - r, px(y) - r, px(x) + r, px(y) + r],
                          fill=tuple(ink2) + (210,))
                x += rng.uniform(8, 12)
            y += 8
    elif mode == "grid":
        for x in range(0, int(w), 7):
            d.line([(px(x), 0), (px(x), px(h))], fill=tuple(ink2) + (110,), width=1)
        for y in range(0, int(h), 7):
            d.line([(0, px(y)), (px(w), px(y))], fill=tuple(ink2) + (110,), width=1)
    for side in (0, 1):                              # torn ends
        x = 2 if side == 0 else w - 2
        for y in range(0, int(h), 3):
            d.rectangle([px(x - 3), px(y), px(x + 3), px(y + 3)],
                        fill=(0, 0, 0, 0))
    return grain(img, rng, uneven=0.07)


@element("stamp_postmark", "collage", ("A", "D"), (50, 110, 60, 130),
         "邮票 + 邮戳")
def el_stamp(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    d.rectangle([px(3), px(3), px(w - 3), px(h - 3)], fill=tuple(paper) + (255,),
                outline=tuple(ink) + (255,), width=px(1.2))
    d.rectangle([px(3), px(3), px(w - 3), px(h - 32)], fill=tuple(ink) + (255,))
    d.polygon([(px(6), px(h - 34)), (px(w * 0.5), px(h * 0.35)),
               (px(w - 6), px(h - 34))], fill=tuple(paper) + (235,))
    r = px(3)
    d.ellipse([px(w - 22) - r, px(h - 46) - r, px(w - 22) + r, px(h - 46) + r],
              fill=tuple(ink2) + (255,))
    for i in range(4):                               # perforation
        for x in range(4, int(w) - 4, 8):
            for yy in (0.0, h):
                d.ellipse([px(x) - 2, px(yy) - 2, px(x) + 2, px(yy) + 2],
                          fill=(0, 0, 0, 0))
    if kw.get("postmark", True):
        cx, cy = w * 0.62, h * 0.30
        d.ellipse([px(cx - 20), px(cy - 20), px(cx + 20), px(cy + 20)],
                  outline=tuple(ink2) + (230,), width=px(1.4))
        d.ellipse([px(cx - 14), px(cy - 14), px(cx + 14), px(cy + 14)],
                  outline=tuple(ink2) + (170,), width=1)
        for k in range(3):
            d.line([(px(cx - 26 + k * 3), px(cy + 16)),
                    (px(cx + 24 + k * 3), px(cy + 16))],
                   fill=tuple(ink2) + (180,), width=px(0.9))
    return grain(img, rng, uneven=0.07)


@element("ticket_stub", "collage", ("A", "D"), (110, 300, 44, 90),
         "票根：虚线齿孔 + 侧边号")
def el_ticket(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    d.rectangle([px(2), px(2), px(w - 2), px(h - 2)], fill=tuple(paper) + (255,),
                outline=tuple(ink) + (255,), width=px(1.3))
    d.rectangle([px(2), px(2), px(w * 0.26), px(h - 2)], fill=tuple(ink) + (255,))
    for y in range(3, int(h) - 3, 5):                # perforation column
        d.ellipse([px(w * 0.26) - 2, px(y) - 2, px(w * 0.26) + 2, px(y) + 2],
                  fill=tuple(paper) + (255,))
    label = kw.get("label", "ADMIT ONE")
    ls_ = fit_text(label, "Arial Black", min(15, h * 0.30), w * 0.62)
    img.alpha_composite(text_image(label, "Arial Black", ls_, ink),
                        (px(w * 0.32), px(h * 0.20)))
    sub = kw.get("sub", "NO. 0417")
    ss = fit_text(sub, "Georgia", min(10, h * 0.20), w * 0.62)
    img.alpha_composite(text_image(sub, "Georgia", ss, ink2),
                        (px(w * 0.32), px(h * 0.58)))
    return grain(img, rng, uneven=0.06)


@element("paperclip", "collage", ("A", "D"), (26, 70, 40, 110), "回形针 / 订书钉")
def el_paperclip(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    outer = [(w * 0.30, h * 0.02), (w * 0.72, h * 0.02), (w * 0.72, h * 0.80),
             (w * 0.30, h * 0.80), (w * 0.30, h * 0.22), (w * 0.56, h * 0.22),
             (w * 0.56, h * 0.66)]
    pts = resample([(px(x), px(y)) for x, y in outer], 1.4 * SCALE)
    marker_stroke(img, pts, ink, 1.1, rng, taper=(0.95, 1.0), jitter=0.05,
                  resample_step=0.8)
    return img


@element("polaroid", "collage", ("A",), (90, 260, 90, 280),
         "宝丽来相框：可用渐变/网点当照片内容")
def el_polaroid(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, px(w), px(h)], fill=tuple(paper) + (255,),
                outline=tuple(ink) + (70,), width=px(0.8))
    d.rectangle([px(w * 0.08), px(h * 0.07), px(w * 0.92), px(h * 0.72)],
                fill=tuple(ink2) + (235,))
    horizon = h * 0.50
    d.polygon([(px(w * 0.08), px(h * 0.72)), (px(w * 0.34), px(horizon)),
               (px(w * 0.58), px(h * 0.72))], fill=tuple(ink) + (255,))
    d.polygon([(px(w * 0.40), px(h * 0.72)), (px(w * 0.62), px(horizon + 6)),
               (px(w * 0.92), px(h * 0.72))], fill=tuple(ink) + (210,))
    r = px(5)
    d.ellipse([px(w * 0.74) - r, px(h * 0.20) - r, px(w * 0.74) + r,
               px(h * 0.20) + r], fill=tuple(ink) + (255,))
    cap = kw.get("caption", "the coast, 1987")
    cs = fit_text(cap, "Georgia", min(12, h * 0.06), w * 0.80)
    img.alpha_composite(text_image(cap, "Georgia", cs, ink),
                        (px(w * 0.10), px(h * 0.80)))
    return grain(img, rng, uneven=0.05)


@element("ransom_word", "collage", ("A", "F"), (90, 420, 26, 64),
         "勒索信式单词：每个字母不同底块与字体")
def el_ransom(ink, ink2, paper, size, rng, **kw):
    word = kw.get("word", "RETURN")
    w, h = kw.get("box", (size[0], size[1]))
    img = canvas(w, h)
    x = 0.0
    for ch in word:
        bw = rng.uniform(h * 0.72, h * 1.02)
        if x + bw > w:
            break
        bg = rng.choice([ink, ink2, paper])
        fg = paper if bg != paper else ink
        tile = canvas(bw, h)
        ImageDraw.Draw(tile).rectangle(
            [0, 0, px(bw) - 1, px(h) - 1], fill=tuple(bg) + (255,))
        glyph = text_image(ch, rng.choice(["Arial Black", "Georgia", "Impact"]),
                           h * 0.62, fg, bold=rng.random() < 0.5)
        tile.alpha_composite(glyph, (int(px(bw) * 0.5 - glyph.width * 0.5),
                                     int(px(h) * 0.5 - glyph.height * 0.5)))
        tile = tile.rotate(rng.uniform(-4, 4), expand=True,
                           resample=Image.BICUBIC)
        img.alpha_composite(tile, (int(px(x)), int(px(h * 0.5) - tile.height * 0.5)))
        x += bw + rng.uniform(1, 4)
    return grain(img, rng, uneven=0.06)


@element("layered_stack", "collage", ("A", "D"), (80, 260, 60, 200),
         "叠层纸片：三张错位纸 + 投影")
def el_layered_stack(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    for i, col in enumerate([ink2, ink, paper]):
        off = (i - 1) * rng.uniform(3, 7)
        box = [px(6 + off), px(6 + off), px(w - 6 + off), px(h - 6 + off)]
        layer = Image.new("RGBA", (px(w), px(h)), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rectangle(box, fill=tuple(col) + (255,),
                                        outline=tuple(ink) + (190,), width=px(0.8))
        layer = grain(layer, rng, uneven=0.05)
        img.alpha_composite(layer)
    for k in range(4):                               # faux text lines
        y = h * 0.30 + k * h * 0.12
        ImageDraw.Draw(img).rectangle(
            [px(w * 0.20), px(y), px(w * (0.62 + rng.random() * 0.22)), px(y + 2)],
            fill=tuple(ink) + (150,))
    return img


@element("luggage_tag", "collage", ("A",), (80, 220, 60, 170),
         "吊牌：孔 + 系绳")
def el_tag(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    d.polygon([(px(w * 0.18), px(h * 0.08)), (px(w * 0.82), px(h * 0.02)),
               (px(w * 0.95), px(h * 0.62)), (px(w * 0.50), px(h * 0.98)),
               (px(w * 0.05), px(h * 0.62))], fill=tuple(ink) + (255,))
    d.ellipse([px(w * 0.44), px(h * 0.10), px(w * 0.56), px(h * 0.22)],
              fill=tuple(paper) + (255,))
    lab = kw.get("label", "ITEM 0417")
    img.alpha_composite(text_image(lab, "Arial Black",
                                   fit_text(lab, "Arial Black", h * 0.14, w * 0.64),
                                   paper), (px(w * 0.18), px(h * 0.40)))
    sub = kw.get("sub", "PLEASE RETURN")
    img.alpha_composite(text_image(sub, "Georgia",
                                   fit_text(sub, "Georgia", h * 0.085, w * 0.62),
                                   paper), (px(w * 0.20), px(h * 0.58)))
    return grain(img, rng, uneven=0.08)


@element("airmail_envelope", "collage", ("A",), (120, 340, 80, 220),
         "航空信封：斜纹边框 + 地址线")
def el_airmail(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, px(w), px(h)], fill=tuple(paper) + (255,),
                outline=tuple(ink) + (200,), width=px(1))
    band = 10.0
    for side in ("t", "b"):
        y0 = 0 if side == "t" else h - band
        for i in range(-1, int(w / 8) + 1):
            d.polygon([(px(i * 8), px(y0)), (px(i * 8 + 4), px(y0)),
                       (px(i * 8 + 4 - 4), px(y0 + band)), (px(i * 8 - 4), px(y0 + band))],
                      fill=tuple(ink2) + (255,))
    for side in ("l", "r"):
        x0 = 0 if side == "l" else w - band
        for i in range(-1, int(h / 8) + 1):
            d.polygon([(px(x0), px(i * 8)), (px(x0), px(i * 8 + 4)),
                       (px(x0 + band), px(i * 8 + 4 - 4)), (px(x0 + band), px(i * 8 - 4))],
                      fill=tuple(ink) + (255,))
    d.rectangle([px(band), px(band), px(w - band), px(h - band)],
                fill=tuple(paper) + (255,))
    for k in range(3):
        y = h * 0.34 + k * h * 0.13
        d.line([(px(w * 0.28), px(y)), (px(w * (0.62 + rng.random() * 0.18)), px(y))],
               fill=tuple(ink) + (150,), width=px(1.2))
    return grain(img, rng, uneven=0.06)


@element("rubber_stamp", "collage", ("A", "D"), (80, 240, 40, 110),
         "橡皮章：框内文字 + 断墨")
def el_rubber_stamp(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    d.rectangle([px(2), px(2), px(w - 2), px(h - 2)], outline=tuple(ink) + (255,),
                width=px(2.2))
    d.rectangle([px(6), px(6), px(w - 6), px(h - 6)], outline=tuple(ink) + (170,),
                width=px(0.8))
    lab = kw.get("label", "ARCHIVED")
    img.alpha_composite(text_image(lab, "Arial Black",
                                   fit_text(lab, "Arial Black", h * 0.34, w * 0.84),
                                   ink), (px(w * 0.08), px(h * 0.33)))
    a = img.getchannel("A")
    import numpy as np
    arr = np.asarray(a).astype("float32") / 255.0
    noise = np.random.default_rng(rng.getrandbits(64))
    arr *= np.clip(noise.normal(1.0, 0.22, arr.shape), 0.15, 1.0)
    img.putalpha(Image.fromarray((arr * 255).astype("uint8")))
    img = img.rotate(rng.uniform(-6, 6), expand=True, resample=Image.BICUBIC)
    return img


@element("newspaper_clipping", "collage", ("A", "D"), (110, 300, 90, 260),
         "报纸剪报：标题 + 双栏文字块")
def el_clipping(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, px(w), px(h)], fill=tuple(paper) + (255,))
    head = kw.get("head", "Harbor Loses Its Bell Again")
    img.alpha_composite(text_image(head, "Georgia",
                                   fit_text(head, "Georgia", h * 0.085, w * 0.90),
                                   ink, bold=True), (px(w * 0.05), px(h * 0.05)))
    for col in range(2):
        x0 = w * 0.05 + col * w * 0.48
        for line in range(int(h * 0.72 / (h * 0.045))):
            y = h * 0.22 + line * h * 0.045
            ln = rng.uniform(0.30, 0.44) * w
            d.rectangle([px(x0), px(y), px(x0 + ln), px(y + 1.6)],
                        fill=tuple(ink) + (135,))
    return grain(img, rng, uneven=0.07)


@element("zigzag_strip", "collage", ("A", "C", "F"), (90, 420, 12, 44),
         "锯齿边条带")
def el_zigzag_strip(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    teeth = max(6, int(w / rng.uniform(9, 14)))
    pts = [(0, h)]
    for i in range(teeth + 1):
        pts.append((w * i / teeth, h * 0.1 if i % 2 else h * 0.85))
    pts.append((w, h))
    d.polygon([(px(x), px(y)) for x, y in pts], fill=tuple(ink) + (255,))
    return grain(img, rng, uneven=0.07)


@element("grain_fade", "collage", ("A", "C", "E"), (120, 460, 70, 300),
         "带颗粒渐隐的色块（方向/径向可调）")
def el_grain_fade(ink, ink2, paper, size, rng, **kw):
    import numpy as np
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, px(w), px(h)], fill=tuple(ink) + (255,))
    a = np.asarray(img.getchannel("A")).astype("float32") / 255.0
    yy, xx = np.mgrid[0:img.height, 0:img.width]
    mode = kw.get("mode", "linear")
    if mode == "radial":
        cx, cy = img.width * 0.5, img.height * 0.5
        t = np.sqrt(((xx - cx) / (img.width * 0.6)) ** 2
                    + ((yy - cy) / (img.height * 0.6)) ** 2)
    else:
        t = xx / max(1, img.width)
    a *= np.clip(1.35 - t * 1.15, 0, 1)
    noise = np.random.default_rng(rng.getrandbits(64))
    a *= np.clip(noise.normal(1.0, 0.16, a.shape), 0.25, 1.0)
    a[noise.random(a.shape) < 0.02] *= 0.1
    img.putalpha(Image.fromarray((np.clip(a, 0, 1) * 255).astype("uint8")))
    return img


# ================================================================ doodle (B)
@element("scribble_circle", "doodle", ("B", "F"), (90, 420, 70, 320),
         "手绘圈注：不闭合、重描、线宽变化")
def el_scribble_circle(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    passes = kw.get("passes", rng.randint(2, 3))
    for p in range(passes):
        a0 = rng.uniform(-30, 10)
        a1 = a0 + rng.uniform(300, 350)
        pts = arc_pts(w / 2 + rng.uniform(-3, 3), h / 2 + rng.uniform(-3, 3),
                      w / 2 - 4, h / 2 - 4, a0, a1, n=64)
        pts = jitter_path([(px(x), px(y)) for x, y in pts], rng, amp=1.6 * SCALE)
        marker_stroke(img, pts, ink if p == 0 else ink2,
                      rng.uniform(1.6, 2.6), rng,
                      taper=(0.6, 1.0), alpha=255 if p == 0 else 200)
    return grain(img, rng, uneven=0.05, holes=0)


@element("wavy_underline", "doodle", ("B", "F"), (100, 460, 14, 44),
         "波浪下划线")
def el_wavy_underline(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    amp = kw.get("amp", h * 0.30)
    cycles = max(2, int(w / rng.uniform(16, 26)))
    pts = []
    for i in range(121):
        t = i / 120
        pts.append((px(w * t), px(h / 2 + amp * math.sin(2 * math.pi * cycles * t))))
    marker_stroke(img, jitter_path(pts, rng, amp=0.8 * SCALE), ink,
                  rng.uniform(1.6, 2.4), rng, taper=(0.5, 1.0))
    return img


@element("double_underline", "doodle", ("B",), (100, 460, 16, 48), "双下划线")
def el_double_underline(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    for y, col in ((h * 0.30, ink), (h * 0.66, ink2)):
        pts = [(px(rng.uniform(0, 3) + w * i / 40), px(y + rng.uniform(-1.6, 1.6)))
               for i in range(41)]
        marker_stroke(img, pts, col, rng.uniform(1.4, 2.2), rng, taper=(0.55, 1.0))
    return img


@element("hand_arrow", "doodle", ("B", "F"), (70, 320, 40, 180),
         "手绘箭头：直/弯/回环")
def el_hand_arrow(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    mode = kw.get("mode") or rng.choice(["straight", "curve", "loop"])
    if mode == "straight":
        pts = bezier((w * 0.04, h * 0.5), (w * 0.35, h * 0.42),
                     (w * 0.62, h * 0.58), (w * 0.92, h * 0.5))
    elif mode == "curve":
        pts = bezier((w * 0.06, h * 0.82), (w * 0.22, h * 0.12),
                     (w * 0.72, h * 0.10), (w * 0.93, h * 0.62))
    else:
        pts = bezier((w * 0.06, h * 0.62), (w * 0.45, h * 0.02),
                     (w * 0.98, h * 0.42), (w * 0.60, h * 0.84))
    pts = jitter_path([(px(x), px(y)) for x, y in pts], rng, amp=1.4 * SCALE)
    marker_stroke(img, pts, ink, rng.uniform(2.0, 3.0), rng, taper=(0.45, 1.0))
    tipx, tipy = pts[-1]
    ang = math.atan2(tipy - pts[-6][1], tipx - pts[-6][0])
    L = px(rng.uniform(11, 16))
    for s in (2.5, -2.5):
        d = ImageDraw.Draw(img)
        d.polygon([(tipx, tipy),
                   (tipx - L * math.cos(ang - 0.42 * s),
                    tipy - L * math.sin(ang - 0.42 * s)),
                   (tipx - L * 0.72 * math.cos(ang),
                    tipy - L * 0.72 * math.sin(ang))],
                  fill=tuple(ink) + (255,))
    return img


@element("scribble_fill", "doodle", ("B", "F"), (70, 380, 50, 240),
         "斜线涂抹填色（三色可选）")
def el_scribble_fill(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    colour = kw.get("colour", ink)
    y = h * 0.18
    while y < h * 0.92:
        pts = bezier((w * 0.06 + rng.uniform(-4, 6), y),
                     (w * 0.35, y + rng.uniform(-h * 0.10, h * 0.05)),
                     (w * 0.66, y + rng.uniform(-h * 0.05, h * 0.10)),
                     (w * 0.94, y + rng.uniform(-4, 6)))
        marker_stroke(img, jitter_path([(px(x), px(y2)) for x, y2 in pts], rng,
                                       amp=1.5 * SCALE),
                      colour, rng.uniform(3.0, 4.6), rng, taper=(0.85, 1.0),
                      alpha=250)
        y += rng.uniform(h * 0.10, h * 0.16)
    return grain(img, rng, uneven=0.07)


@element("asterisk", "doodle", ("B", "C", "F"), (24, 90, 24, 90), "手绘星号")
def el_asterisk(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    arms = kw.get("arms", rng.randint(5, 7))
    cx, cy = w / 2, h / 2
    for i in range(arms):
        a = 2 * math.pi * i / arms + rng.uniform(-0.2, 0.2)
        r = rng.uniform(0.35, 0.48)
        pts = [(px(cx), px(cy)),
               (px(cx + w * r * math.cos(a)), px(cy + h * r * math.sin(a)))]
        marker_stroke(img, jitter_path(pts, rng, amp=1.0 * SCALE), ink,
                      rng.uniform(1.8, 3.0), rng, taper=(0.7, 1.0))
    return img


@element("starburst", "doodle", ("B", "C", "F"), (36, 150, 36, 150), "星爆 / 爆炸形")
def el_starburst(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    spikes = kw.get("spikes", rng.randint(9, 14))
    pts = []
    for i in range(spikes * 2):
        a = math.pi * i / spikes
        r = (0.5 if i % 2 == 0 else rng.uniform(0.20, 0.30))
        pts.append((px(w / 2 + w * r * math.cos(a)),
                    px(h / 2 + h * r * math.sin(a))))
    ImageDraw.Draw(img).polygon(pts, fill=tuple(kw.get("fill", ink)) + (255,))
    return grain(img, rng, uneven=0.09, holes=0.003)


@element("spiral", "doodle", ("B",), (30, 130, 30, 130), "螺旋")
def el_spiral(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    turns = rng.uniform(2.4, 3.4)
    r_max = min(w, h) * 0.46
    pts = []
    steps = 220
    for i in range(steps + 1):
        t = i / steps
        a = t * math.pi * 2 * turns
        r = (0.10 + 0.90 * t) * r_max
        pts.append((px(w / 2 + r * math.cos(a)), px(h / 2 + r * math.sin(a))))
    marker_stroke(img, jitter_path(pts, rng, amp=0.7 * SCALE), ink,
                  rng.uniform(1.4, 2.0), rng, taper=(0.45, 1.0))
    return img


@element("doodle_face", "doodle", ("B", "F"), (30, 110, 30, 110), "涂鸦小脸")
def el_face(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    mood = kw.get("mood") or rng.choice(["happy", "flat", "wow", "sad", "dizzy"])
    pts = jitter_path([(px(x), px(y)) for x, y in arc_pts(
        w / 2, h / 2, w / 2 - 3, h / 2 - 3, 0, 360, n=48)], rng, amp=1.4 * SCALE)
    marker_stroke(img, pts + [pts[0]], ink, rng.uniform(1.5, 2.2), rng,
                  taper=(0.9, 1.0))
    d = ImageDraw.Draw(img)
    eye = rng.uniform(1.6, 2.6)
    for sx in (-1, 1):
        cx, cy = w / 2 + sx * w * 0.17, h * 0.40
        if mood == "wow":
            d.ellipse([px(cx - eye), px(cy - eye * 1.4), px(cx + eye),
                       px(cy + eye * 1.4)], fill=tuple(ink) + (255,))
        else:
            d.ellipse([px(cx - eye), px(cy - eye), px(cx + eye), px(cy + eye)],
                      fill=tuple(ink) + (255,))
    if mood == "happy":
        m = jitter_path([(px(x), px(y)) for x, y in arc_pts(
            w / 2, h * 0.58, w * 0.20, h * 0.16, 20, 160, n=24)], rng, amp=1.0 * SCALE)
        marker_stroke(img, m, ink, 1.8, rng, taper=(0.6, 1.0))
    elif mood in ("flat", "dizzy"):
        d.line([(px(w * 0.36), px(h * 0.68)), (px(w * 0.64), px(h * 0.68))],
               fill=tuple(ink) + (255,), width=px(1.8))
    else:
        m = jitter_path([(px(x), px(y)) for x, y in arc_pts(
            w / 2, h * 0.82, w * 0.20, h * 0.16, 200, 340, n=24)], rng, amp=1.0 * SCALE)
        marker_stroke(img, m, ink, 1.8, rng, taper=(0.6, 1.0))
    return grain(img, rng, uneven=0.05, holes=0)


@element("speech_bubble", "doodle", ("B", "F"), (90, 340, 60, 220), "对话气泡")
def el_speech_bubble(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    body = [(px(w * 0.06), px(h * 0.14)), (px(w * 0.94), px(h * 0.08)),
            (px(w * 0.90), px(h * 0.72)), (px(w * 0.34), px(h * 0.78)),
            (px(w * 0.22), px(h * 0.98)), (px(w * 0.20), px(h * 0.74)),
            (px(w * 0.04), px(h * 0.68))]
    d.polygon(ragged_polygon(body, rng, amp=1.6), fill=tuple(kw.get("fill", paper)) + (255,),
              outline=tuple(ink) + (255,))
    d.line(ragged_polygon(body, rng, amp=1.2) + [body[0]], fill=tuple(ink) + (230,),
           width=px(1.6), joint="curve")
    return grain(img, rng, uneven=0.05)


@element("thought_cloud", "doodle", ("B",), (100, 340, 70, 220), "思考云")
def el_thought_cloud(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    bumps = rng.randint(9, 13)
    pts = []
    for i in range(bumps * 8):
        a = 2 * math.pi * i / (bumps * 8)
        r = 0.42 + 0.05 * math.sin(a * bumps)
        pts.append((px(w / 2 + w * r * math.cos(a)),
                    px(h * 0.44 + h * r * 0.86 * math.sin(a))))
    d.polygon(pts, fill=tuple(kw.get("fill", paper)) + (255,))
    d.line(pts + [pts[0]], fill=tuple(ink) + (235,), width=px(1.5), joint="curve")
    for i, (bx, by, br) in enumerate([(0.28, 0.86, 0.055), (0.20, 0.94, 0.035)]):
        d.ellipse([px(w * (bx - br)), px(h * (by - br * 1.6)),
                   px(w * (bx + br)), px(h * (by + br * 1.6))],
                  fill=tuple(kw.get("fill", paper)) + (255,),
                  outline=tuple(ink) + (235,), width=px(1.2))
    return grain(img, rng, uneven=0.05)


@element("hand_brace", "doodle", ("B",), (18, 60, 60, 240), "手绘括号")
def el_brace(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    side = kw.get("side", "l")
    sx = 0.25 if side == "l" else 0.75
    pts = bezier((w * (1 - sx), h * 0.04), (w * sx, h * 0.18),
                 (w * sx, h * 0.36), (w * sx, h * 0.5))
    pts += bezier((w * sx, h * 0.5), (w * sx, h * 0.64), (w * sx, h * 0.82),
                  (w * (1 - sx), h * 0.96))
    marker_stroke(img, jitter_path([(px(x), px(y)) for x, y in pts], rng,
                                   amp=1.1 * SCALE), ink,
                  rng.uniform(1.8, 2.6), rng, taper=(0.55, 1.0))
    return img


@element("sticky_note", "doodle", ("B", "A"), (80, 240, 70, 220),
         "便利贴：微旋 + 折角 + 手写线")
def el_sticky_note(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    body = [(6, 4), (w - 4, 8), (w - 2, h - 6), (8, h - 2)]
    d.polygon([(px(x), px(y)) for x, y in body], fill=tuple(kw.get("fill", ink2)) + (255,))
    fold = rng.uniform(10, 18)
    d.polygon([(px(w - fold - 4), px(h - 2)), (px(w - 2), px(h - 6)),
               (px(w - 4), px(h - fold - 6))], fill=tuple(paper) + (170,))
    for k in range(4):
        y = h * 0.24 + k * h * 0.16
        pts = [(px(w * 0.14), px(y)), (px(w * (0.60 + rng.random() * 0.24)), px(y + rng.uniform(-2, 2)))]
        marker_stroke(img, pts, ink, 1.3, rng, taper=(0.7, 1.0), alpha=200)
    return grain(img, rng, uneven=0.06)


@element("checklist", "doodle", ("B", "D"), (70, 260, 50, 200),
         "勾选框 + 清单行")
def el_checklist(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    rows = max(2, int(h / 18))
    for i in range(rows):
        y = 4 + i * (h - 8) / rows
        bx = 2
        box = [(px(bx), px(y)), (px(bx + 11), px(y)), (px(bx + 11), px(y + 11)),
               (px(bx), px(y + 11))]
        d.line(box + [box[0]], fill=tuple(ink) + (235,), width=px(1.3))
        if rng.random() < 0.55:
            pts = [(px(bx + 2), px(y + 6)), (px(bx + 5), px(y + 10)),
                   (px(bx + 10), px(y + 1))]
            marker_stroke(img, pts, ink2 if rng.random() < 0.5 else ink,
                          1.9, rng, taper=(0.7, 1.0))
        d.line([(px(bx + 17), px(y + 5.5)), (px(bx + 17 + rng.uniform(20, 46)), px(y + 5.5))],
               fill=tuple(ink) + (150,), width=px(1.0))
    return grain(img, rng, uneven=0.06)


@element("mini_doodle", "doodle", ("B", "F"), (18, 70, 18, 70),
         "小涂鸦：闪电/爱心/花/眼睛/皇冠/星星")
def el_mini_doodle(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    d = ImageDraw.Draw(img)
    kind = kw.get("kind") or rng.choice(["bolt", "heart", "flower", "eye", "crown", "star"])
    if kind == "bolt":
        d.polygon([(px(w * 0.56), px(h * 0.04)), (px(w * 0.22), px(h * 0.56)),
                   (px(w * 0.46), px(h * 0.56)), (px(w * 0.34), px(h * 0.96)),
                   (px(w * 0.78), px(h * 0.40)), (px(w * 0.52), px(h * 0.40))],
                  fill=tuple(ink) + (255,))
    elif kind == "heart":
        pts = [(px(x), px(y)) for x, y in
               arc_pts(w * 0.30, h * 0.36, w * 0.22, h * 0.22, 150, 380, n=26)]
        pts += [(px(x), px(y)) for x, y in
                arc_pts(w * 0.70, h * 0.36, w * 0.22, h * 0.22, 160, 390, n=26)]
        d.polygon(pts + [(px(w * 0.5), px(h * 0.95))], fill=tuple(ink) + (255,))
    elif kind == "flower":
        for i in range(6):
            a = 2 * math.pi * i / 6
            cx, cy = w / 2 + w * 0.24 * math.cos(a), h / 2 + h * 0.24 * math.sin(a)
            d.ellipse([px(cx - w * 0.16), px(cy - h * 0.16), px(cx + w * 0.16),
                       px(cy + h * 0.16)], fill=tuple(ink) + (240,))
        d.ellipse([px(w * 0.40), px(h * 0.40), px(w * 0.60), px(h * 0.60)],
                  fill=tuple(ink2) + (255,))
    elif kind == "eye":
        d.polygon([(px(x), px(y)) for x, y in arc_pts(w / 2, h * 0.62, w * 0.42, h * 0.34, 200, 340, n=28)],
                  fill=tuple(ink) + (255,))
        d.polygon([(px(x), px(y)) for x, y in arc_pts(w / 2, h * 0.38, w * 0.42, h * 0.34, 20, 160, n=28)],
                  fill=tuple(ink) + (255,))
        d.ellipse([px(w * 0.40), px(h * 0.38), px(w * 0.60), px(h * 0.62)],
                  fill=tuple(ink2) + (255,))
    elif kind == "crown":
        d.polygon([(px(w * 0.08), px(h * 0.78)), (px(w * 0.20), px(h * 0.26)),
                   (px(w * 0.38), px(h * 0.56)), (px(w * 0.52), px(h * 0.18)),
                   (px(w * 0.66), px(h * 0.56)), (px(w * 0.84), px(h * 0.26)),
                   (px(w * 0.94), px(h * 0.78))], fill=tuple(ink) + (255,))
    else:
        pts = []
        for i in range(10):
            a = math.pi * i / 5 - math.pi / 2
            r = 0.48 if i % 2 == 0 else 0.21
            pts.append((px(w / 2 + w * r * math.cos(a)), px(h / 2 + h * r * math.sin(a))))
        d.polygon(pts, fill=tuple(ink) + (255,))
    return grain(img, rng, uneven=0.07, holes=0.002)


@element("scribble_redact", "doodle", ("B", "F"), (70, 300, 16, 52),
         "涂抹遮蔽：把一段字盖掉")
def el_redact(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    y = h * 0.35
    while y < h * 0.75:
        pts = [(px(rng.uniform(0, 3)), px(y)),
               (px(w * 0.5), px(y + rng.uniform(-h * 0.12, h * 0.12))),
               (px(w - rng.uniform(0, 3)), px(y + rng.uniform(-2, 2)))]
        marker_stroke(img, jitter_path(pts, rng, amp=1.6 * SCALE), ink,
                      rng.uniform(3.4, 5.2), rng, taper=(0.85, 1.0))
        y += rng.uniform(h * 0.14, h * 0.22)
    return grain(img, rng, uneven=0.08)


@element("loop_border", "doodle", ("B", "F", "C"), (120, 500, 14, 44),
         "线圈/串珠边框条")
def el_loop_border(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    style = kw.get("style", "loops")
    if style == "beads":
        x = 3.0
        while x < w - 3:
            r = px(h * 0.28)
            d = ImageDraw.Draw(img)
            d.ellipse([px(x) - r, px(h / 2) - r, px(x) + r, px(h / 2) + r],
                      fill=tuple(ink) + (255,))
            x += h * 0.52
    else:
        x = 0.0
        step = h * 0.46
        while x < w:
            loop = canvas(step, h)
            pts = [(px(step * 0.06), px(h * 0.80)), (px(step * 0.50), px(h * 0.04)),
                   (px(step * 0.94), px(h * 0.80))]
            marker_stroke(loop, jitter_path(pts, rng, amp=0.8 * SCALE), ink,
                          rng.uniform(1.3, 1.8), rng, taper=(0.75, 1.0))
            img.alpha_composite(loop, (int(px(x)), 0))
            x += step * 0.86
    return img


@element("marker_frame", "doodle", ("B",), (140, 520, 90, 360),
         "马克笔手绘边框（不闭合）")
def el_marker_frame(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = canvas(w, h)
    m = rng.uniform(3, 6)
    corners = [(m, m), (w - m, m * 0.8), (w - m * 0.7, h - m), (m * 1.2, h - m * 0.8)]
    order = [0, 1, 2, 3, 0]
    for i in range(4):
        a, b = corners[order[i]], corners[order[i + 1]]
        pts = bezier((px(a[0]), px(a[1])),
                     (px(a[0] + (b[0] - a[0]) * 0.35), px(a[1] + (b[1] - a[1]) * 0.35 + rng.uniform(-6, 6))),
                     (px(a[0] + (b[0] - a[0]) * 0.7), px(a[1] + (b[1] - a[1]) * 0.7 + rng.uniform(-6, 6))),
                     (px(b[0]), px(b[1])))
        marker_stroke(img, jitter_path(pts, rng, amp=1.2 * SCALE), ink,
                      rng.uniform(2.2, 3.4), rng, taper=(0.8, 1.0))
        if rng.random() < 0.6:                       # over-drawn corner
            marker_stroke(img, jitter_path(pts, rng, amp=2.0 * SCALE), ink2,
                          rng.uniform(1.2, 1.8), rng, taper=(0.5, 1.0), alpha=170)
    return img


# --------------------------------------------------------------- registry API
def register_module(mod):
    """Pull in a sibling module's @element definitions."""
    for meta in getattr(mod, "REGISTRY", {}).values():
        REGISTRY.setdefault(meta["name"], meta)


def catalogue(category=None, dialect=None):
    items = []
    for m in REGISTRY.values():
        if category and m["category"] != category:
            continue
        if dialect and dialect not in m["dialects"]:
            continue
        items.append(m)
    return sorted(items, key=lambda m: (m["category"], m["name"]))


COPY_FIELDS={
    'ticket_stub':('label','sub'), 'polaroid':('caption',),
    'luggage_tag':('label','sub'), 'rubber_stamp':('label',),
    'newspaper_clipping':('head',), 'ransom_word':('word',),
    'outline_letter':('letter',), 'circle_text_badge':('text','inner'),
    'barcode':('code',), 'printed_note':('text','sub'),
    'marquee_band':('text',), 'vertical_text':('text',),
    'issue_stamp':('top','mid','date'), 'caption_label':('text',),
    'starburst_badge':('text','sub'), 'circled_number':('number',),
    'drop_cap':('letter',), 'os_window':('title',),
    'progress_bar':('value','label'), 'dialog_box':('title','buttons'),
    'colour_bar':('colours',),
}


def render(name, palette, size=None, seed=0, allow_defaults=False, **kw):
    """Draw one element. `palette` = dict with ink / ink2 / paper / accent keys."""
    meta = REGISTRY.get(name)
    if not meta:
        raise KeyError(f"unknown element {name!r}")
    if not allow_defaults:
        missing=[key for key in COPY_FIELDS.get(name,()) if key not in kw]
        if missing:
            raise ValueError(f'Information element {name!r} requires supplied fields: {missing}')
    rng = random.Random(seed)
    if size is None:
        lo_w, hi_w, lo_h, hi_h = meta["size"]
        size = (rng.uniform(lo_w, hi_w), rng.uniform(lo_h, hi_h))
    ink = _rgb(palette.get("inkA", "#D7261E"))
    ink2 = _rgb(palette.get("inkB", "#1E1E1E"))
    paper = _rgb(palette.get("paper", "#EFE7D8"))
    return meta["fn"](ink, ink2, paper, size, rng, **kw)


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def sheet(path, group=None, cell=210, cols=6, palette=None):
    """Contact sheet of every registered element — the visual check."""
    palette = palette or {"paper": "#EFE7D8", "inkA": "#D7261E", "inkB": "#1E1E1E"}
    items = catalogue(dialect=group)
    if not items:
        raise SystemExit(f"no elements for group {group!r}")
    rows = (len(items) + cols - 1) // cols
    W, H = cols * cell, rows * (cell + 18)
    out = Image.new("RGB", (W, H), (239, 231, 216))
    d = ImageDraw.Draw(out)
    f = tm.font("Georgia", 10 * SCALE) or ImageFont.load_default()
    for i, meta in enumerate(items):
        r, c = divmod(i, cols)
        x0, y0 = c * cell, r * (cell + 18)
        d.rectangle([x0 + 4, y0 + 4, x0 + cell - 4, y0 + cell - 4],
                    outline=(190, 182, 168))
        img = render(meta["name"], palette, seed=1000 + i, allow_defaults=True)
        k = min((cell - 34) / max(1, img.width), (cell - 34) / max(1, img.height))
        img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))),
                         Image.LANCZOS)
        out.paste(img, (x0 + (cell - img.width) // 2,
                        y0 + (cell - img.height) // 2), img)
        d.text((x0 + 8, y0 + cell + 2), f"{meta['name']}  [{'/'.join(meta['dialects'])}]",
               font=f, fill=(60, 55, 50))
    out.save(path, quality=90)
    return path


def write_markdown(path):
    """Generate the compact registry index; query the CLI for sizes and notes."""
    cats={}
    for m in catalogue():cats.setdefault(m['category'],[]).append(m['name'])
    out=['# Element index', '', f'**{len(REGISTRY)}** registered generators. Load only the needed dialect:', '',
         '```bash', 'python scripts/elements.py catalogue --dialect C --safe --limit 8',
         'python scripts/elements.py catalogue --dialect B --role hero --safe --json', '```', '',
         'The full registry includes self-lettered demo elements. Automatic composition',
         'uses the copy-free curated pool (`--safe`); do not invent facts with stamps',
         'or labels. Element functions generate transparent PNGs from palette/seed.',
         'Use `sheet OUTPUT/elements.png --group C` only for visual selection.', '']
    for cat,names in cats.items():
        out += ['## '+cat, '', ', '.join('`'+n+'`' for n in names), '']
    with open(path,'w',encoding='utf-8') as f:f.write('\n'.join(out))
    print(f'wrote {path} ({len(REGISTRY)} elements)')
    return path


def main():
    ap = argparse.ArgumentParser(description="riso element library")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("catalogue")
    c.add_argument("--json", action="store_true")
    c.add_argument("--dialect", choices=list('ABCDEF'))
    c.add_argument("--role", choices=['hero','support','micro'])
    c.add_argument("--safe", action="store_true", help="only copy-free automatic placement candidates")
    c.add_argument("--limit", type=int, help="maximum returned elements")
    c.add_argument("--markdown", default=None,
                   help="regenerate references/elements.md from the registry")
    s = sub.add_parser("sheet")
    s.add_argument("out")
    s.add_argument("--group", default=None, help="dialect letter: A B C D E F")
    s.add_argument("--cols", type=int, default=6)
    a = ap.parse_args()
    if a.cmd == "catalogue":
        if a.limit is not None and a.limit<1:ap.error('--limit must be positive')
        selected=catalogue(dialect=a.dialect)
        if a.safe or a.role:
            import compose
            dialects=[a.dialect] if a.dialect else list('ABCDEF')
            allowed={n for d in dialects for role,n in compose.element_pool(d,d)
                     if a.role is None or role==a.role}
            selected=[m for m in catalogue() if m['name'] in allowed]
        if a.limit is not None:selected=selected[:a.limit]
        if a.json:
            print(json.dumps([{k: v for k, v in m.items() if k != "fn"}
                              for m in selected], ensure_ascii=False, indent=2))
        elif a.markdown:
            write_markdown(a.markdown)
        else:
            cat = None
            for m in selected:
                if m["category"] != cat:
                    cat = m["category"]
                    print(f"\n[{cat}]")
                print(f"  {m['name']:<20} {','.join(m['dialects']):<8} "
                      f"size {m['size']}  {m['note']}")
            print(f"\n{len(selected)} elements")
        return 0
    print(sheet(a.out, a.group, cols=a.cols))
    return 0


# The catalogue is completed at import time so that any consumer (compose.py,
# qa.py, a test) sees the same registry without remembering to load the second
# module. elements_b imports this module, so the import has to sit at the very
# bottom, after every helper it needs already exists.
def load_siblings():
    try:
        import elements_b
    except Exception as exc:                      # keep the core usable alone
        print(f"elements: elements_b not loaded ({exc})", file=sys.stderr)
        return
    register_module(elements_b)
    # When this file is run as a script, `import elements_b` pulls in a *second*
    # copy of elements.py under the name `elements`; its registrations land in
    # that copy's REGISTRY, not ours. Merge them so the CLI sees the whole
    # catalogue rather than half of it.
    other = sys.modules.get("elements")
    if other is not None and other is not sys.modules.get(__name__):
        register_module(other)


load_siblings()


if __name__ == "__main__":
    sys.exit(main())
