#!/usr/bin/env python3
"""elements_b.py — the rest of the riso element library.

Why this file exists
--------------------
elements.py carries the three dialects that were reverse-engineered from finished
posters (collage A, doodle-journal B, Swiss-geometric C). The remaining families
live here and register into the same registry through the same decorator, so the
composer cannot tell which file an element came from:

    @E.element(name, category, dialects, (min_w, max_w, min_h, max_h), note)
    def el_x(ink, ink2, paper, size, rng, **kw) -> PIL RGBA Image

  geometric   C/D  Swiss precision: ImageDraw polygons, no jitter, almost no grain
  texture     A–F  halftone screens and grain fields, parameterised by dir + fade
  print       A/C/D  the printer's furniture: bars, crop marks, folds, holes, barcode
  typography  B/C/D/F  bands, stamps, badges, drop caps
  retro_ui    E    the 1990s desktop vocabulary, in 8×8 pixels

Design rules kept from elements.py
----------------------------------
  * an element owns its ink unevenness (E.grain) so it reads as printed;
  * shapes are drawn upright and unrotated — rotation is the composer's business;
  * an element's own label may never leave its own frame, so every string goes
    through E.fit_text before it is rendered;
  * randomness comes only from the passed-in `rng`, never from the global one.

Two rules specific to this file
-------------------------------
  * geometric = exact. Radii, pitches and cell sizes are computed from the box so
    the element fills it at any aspect ratio (the registry renders min and max
    sizes independently in w and h, so nothing may assume a fixed aspect);
  * texture = a real gradient. Dot radius, line width and alpha are all driven by
    one fade field (none / linear / radial / band) along kw["dir"], and the radius
    reaches exactly zero where the field does — a halftone that stops fading is a
    flat grid, not a screen.

Usage
-----
  python elements_b.py                       # self-test at min and max size
  python elements.py catalogue               # both modules, grouped by category
  python elements.py sheet out.jpg --group C # contact sheet for one dialect
"""
import sys
sys.dont_write_bytecode = True
import math
import os
import random
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import elements as E
import textmetrics as tm


# --------------------------------------------------------------- helpers
def _np_rng(rng):
    """A numpy Generator seeded from the element's own rng.

    Grain, fade fields and glyph erosion all derive noise from the element's
    own rng, so unrelated numpy draws cannot change the output.
    """
    import numpy as np
    return np.random.default_rng(rng.getrandbits(32))


def _layer(img, fn):
    """Draw on a transparent layer, then blend it down.

    ImageDraw writes raw pixels: a second ink drawn straight onto the canvas
    replaces the first instead of overprinting it. Anything that has to *mix*
    (overprint, tint, shadow, knockout text) goes through here.
    """
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    fn(ImageDraw.Draw(lay))
    img.alpha_composite(lay)
    return img


def _box(x0, y0, x1, y1):
    """Rectangle corners in page pt -> pixel box for ImageDraw."""
    return [E.px(x0), E.px(y0), E.px(x1), E.px(y1)]


def _taper_seg(d, p0, p1, w0, w1, fill):
    """A quad with a different width at each end.

    PIL's line() takes an integer width, so a screen whose tone changes along the
    line would step in whole pixels and notch at every joint. A tapered quad is
    gapless and sub-pixel accurate.
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    d.polygon([(p0[0] + nx * w0 / 2, p0[1] + ny * w0 / 2),
               (p1[0] + nx * w1 / 2, p1[1] + ny * w1 / 2),
               (p1[0] - nx * w1 / 2, p1[1] - ny * w1 / 2),
               (p0[0] - nx * w0 / 2, p0[1] - ny * w0 / 2)], fill=fill)


def _fade_axes(w, h, kw):
    """(ux, uy, half) for kw["dir"] — 0 = 向右, 90 = 向下, 180 = 向左, 270 = 向上."""
    deg = float(kw.get("dir", 0.0) or 0.0)
    ux, uy = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    half = max(1e-6, (abs(ux) * w + abs(uy) * h) / 2.0)
    return ux, uy, half


def _fade_at(x, y, w, h, mode, ux, uy, half):
    """Tone of the fade field at one point: 1 where the ink is full, 0 where it has
    died. `mode` is none / linear / radial / band."""
    if mode in (None, "", "none"):
        return 1.0
    if mode == "radial":
        dx = (x - w / 2.0) / max(1e-6, w / 2.0)
        dy = (y - h / 2.0) / max(1e-6, h / 2.0)
        return min(1.0, max(0.0, (1.0 - math.hypot(dx, dy)) / 0.75))
    t = 0.5 + ((x - w / 2.0) * ux + (y - h / 2.0) * uy) / (2.0 * half)
    t = min(1.0, max(0.0, t))
    if mode == "band":
        return min(1.0, max(0.0, (0.5 - abs(t - 0.5)) / 0.28))
    return 1.0 - t                                  # linear


def _fade_grid(w, h, mode, ux, uy, half):
    """_fade_at over the whole canvas as a float array — the numpy-side version."""
    import numpy as np
    yy, xx = np.mgrid[0:E.px(h), 0:E.px(w)]
    x = (xx + 0.5) / E.SCALE
    y = (yy + 0.5) / E.SCALE
    if mode in (None, "", "none"):
        return np.ones(x.shape, dtype="float32")
    if mode == "radial":
        dx = (x - w / 2.0) / max(1e-6, w / 2.0)
        dy = (y - h / 2.0) / max(1e-6, h / 2.0)
        return np.clip((1.0 - np.sqrt(dx * dx + dy * dy)) / 0.75, 0, 1).astype("float32")
    t = np.clip(0.5 + ((x - w / 2.0) * ux + (y - h / 2.0) * uy) / (2.0 * half), 0, 1)
    if mode == "band":
        return np.clip((0.5 - np.abs(t - 0.5)) / 0.28, 0, 1).astype("float32")
    return (1.0 - t).astype("float32")


def _dot_lattice(w, h, spacing, rng):
    """45° halftone lattice, exactly as specified:
    x = (i-j)·spacing/√2, y = (i+j)·spacing/√2.

    Walked as (m, n) = (i+j, i-j) so the parity of m+n keeps i and j integral, and
    only the dots whose lattice cell can touch the canvas are visited.
    """
    s45 = spacing / math.sqrt(2.0)
    off = s45 * rng.random()
    m_max = int(h / s45) + 2
    n_max = int(w / s45) + 2
    for m in range(-2, m_max + 1):
        for n in range(-2, n_max + 1):
            if (m + n) & 1:
                continue
            yield (n * s45 + off, m * s45 + off)


def _line_field(img, w, h, colour, angle, pitch, lw, kw, alpha=255, segs=12):
    """Parallel lines at `angle` degrees whose width AND alpha follow the fade
    field, so the screen dissolves to nothing instead of ending on a hard edge."""
    fade = str(kw.get("fade", "linear"))
    ux, uy, half = _fade_axes(w, h, kw)
    pitch = max(0.8, float(pitch))
    a = math.radians(angle)
    vx, vy = math.cos(a), math.sin(a)
    nx, ny = -vy, vx
    cx, cy = w / 2.0, h / 2.0
    reach = (w + h) * 0.5 + pitch
    k_max = int(reach / pitch) + 1
    lw_px = max(0.4, lw) * E.SCALE
    def paint(d):
        for k in range(-k_max, k_max + 1):
            ox, oy = cx + nx * k * pitch, cy + ny * k * pitch
            for s in range(segs):
                t0, t1 = s / segs, (s + 1) / segs
                x0 = ox + vx * (t0 - 0.5) * 2 * reach
                y0 = oy + vy * (t0 - 0.5) * 2 * reach
                x1 = ox + vx * (t1 - 0.5) * 2 * reach
                y1 = oy + vy * (t1 - 0.5) * 2 * reach
                v0 = _fade_at(x0, y0, w, h, fade, ux, uy, half)
                v1 = _fade_at(x1, y1, w, h, fade, ux, uy, half)
                w0, w1 = lw_px * v0, lw_px * v1
                if w0 < 0.6 and w1 < 0.6:
                    continue
                av = int(alpha * min(1.0, 0.30 + 0.70 * (v0 + v1) / 2.0))
                _taper_seg(d, (E.px(x0), E.px(y0)), (E.px(x1), E.px(y1)),
                           max(0.6, w0), max(0.6, w1), tuple(colour) + (av,))
    _layer(img, paint)
    return img


def _rotated_lines(size, pitch, lw, colour, angle, alpha=235):
    """A hairline screen drawn on an oversized canvas and rotated back down.

    The oversize is the point: rotating in place would leave the four corners
    empty, and the moiré pair only reads as interference when both screens cover
    the whole box.
    """
    W, H = size
    big = Image.new("RGBA", (int(W * 1.5) + 4, int(H * 1.5) + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    lpx = max(1, int(round(E.px(lw))))
    y = pitch * 0.5
    while y * E.SCALE < big.height:
        d.rectangle([0, E.px(y), big.width, E.px(y) + lpx - 1],
                    fill=tuple(colour) + (alpha,))
        y += pitch
    big = big.rotate(angle, resample=Image.BICUBIC, expand=False)
    x0 = (big.width - W) // 2
    y0 = (big.height - H) // 2
    return big.crop((x0, y0, x0 + W, y0 + H))


def _shear(tile, k):
    """Slant a text tile. No oblique face is installed, and a synthetic slant is
    what makes a marquee band read as italic rather than as upright caps."""
    W, H = tile.size
    out_w = W + int(abs(k) * H) + 2
    return tile.transform((out_w, H), Image.AFFINE, (1, k, -k * H, 0, 1, 0),
                          resample=Image.BICUBIC)


def _erode(arr, r):
    """Min-filter an alpha array by `r` px — 24 directions is close enough to a
    round nib, and it is what turns a filled glyph into an outline glyph."""
    import numpy as np
    r = int(round(r))
    if r < 1:
        return arr
    out = arr.copy()
    for i in range(24):
        a = 2 * math.pi * i / 24
        dy, dx = int(round(r * math.sin(a))), int(round(r * math.cos(a)))
        out = np.minimum(out, np.roll(arr, (dy, dx), axis=(0, 1)))
    return out


def _fit_tile(txt, family, size, colour, max_w, min_size=3.6):
    """fit_text + text_image in one call. Every label in this module goes through
    here, so no element's own text can leave its own frame."""
    s = E.fit_text(txt, family, size, max_w, min_size)
    return E.text_image(txt, family, s, colour), s


def _ink_name(rgb):
    """两三个字的墨色名——色标条上要能读出这管墨是什么颜色。"""
    r, g, b = [c / 255.0 for c in rgb]
    mx, mn = max(r, g, b), min(r, g, b)
    sat = 0.0 if mx <= 0 else (mx - mn) / mx
    if sat < 0.14:
        if mx < 0.24:
            return "墨黑"
        if mx > 0.72:
            return "米白"
        return "中灰"
    if mx == r:
        hue = ((g - b) / (mx - mn)) % 6
    elif mx == g:
        hue = (b - r) / (mx - mn) + 2
    else:
        hue = (r - g) / (mx - mn) + 4
    hue *= 60.0
    for lim, name in ((15, "正红"), (45, "橘橙"), (70, "明黄"), (160, "草绿"),
                      (200, "青碧"), (255, "湖蓝"), (285, "紫罗兰"),
                      (330, "洋红"), (361, "朱红")):
        if hue < lim:
            return name
    return "朱红"


def _diag_stripes(w, h, pitch, band, colour, alpha, phase=0.0):
    """45° stripe tile, used as window/dialog fill."""
    tile = E.canvas(w, h)
    d = ImageDraw.Draw(tile)
    k = int(-h / pitch) - 2
    while k * pitch + phase < w + h + pitch:
        x = k * pitch + phase
        d.polygon([(E.px(x), 0), (E.px(x + band), 0),
                   (E.px(x + band + h), E.px(h)), (E.px(x + h), E.px(h))],
                  fill=tuple(colour) + (alpha,))
        k += 1
    return tile


# =============================================================== geometric (C/D)
@E.element("arch", "geometric", ("C", "D"), (40, 200, 46, 240),
           "拱门：半圆顶 + 两条腿，描边/实心/套色")
def el_arch(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    ry = min(w / 2.0, h * 0.62)                # 顶弧压扁也不会顶出画布
    t = min(max(2.0, min(w / 2.0, ry) * 0.24), w * 0.24, h * 0.20)

    def path(rx, ry_, leg):
        pts = E.arc_pts(w / 2.0, ry, rx, ry_, 180, 360, n=72)
        return [(E.px(x), E.px(y)) for x, y in pts] + [(E.px(w / 2 + rx), E.px(leg)),
                                                       (E.px(w / 2 - rx), E.px(leg))]
    mode = kw.get("mode") or rng.choice(["outline", "solid", "duo"])
    d.polygon(path(w / 2.0, ry, h), fill=tuple(ink) + (255,))
    if mode == "outline":
        d.polygon(path(w / 2.0 - t, ry - t, h - t), fill=(0, 0, 0, 0))
        inner = path(w / 2.0 - t * 2.1, ry - t * 2.1, h - t * 2.1)
        _layer(img, lambda dd: dd.line(inner, fill=tuple(ink2) + (210,),
                                       width=max(1, E.px(0.9)), joint="curve"))
    elif mode == "duo":
        in_rx, in_ry = w / 2.0 - t * 1.7, ry - t * 1.7
        if in_rx > 1.5 and in_ry > 1.5:
            _layer(img, lambda dd: dd.polygon(path(in_rx, in_ry, h - t * 1.7),
                                              fill=tuple(ink2) + (235,)))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("pill", "geometric", ("C", "D"), (44, 240, 24, 96),
           "胶囊：圆角矩形，填充/描边/内嵌套色")
def el_pill(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    r = min(w, h) / 2.0
    t = min(max(1.8, min(w, h) * 0.20), h * 0.28, w * 0.28)
    mode = kw.get("mode") or rng.choice(["fill", "outline", "duo"])
    outer = [0, 0, E.px(w) - 1, E.px(h) - 1]
    if mode == "outline":
        d.rounded_rectangle(outer, radius=max(1, E.px(r) - 1),
                            outline=tuple(ink) + (255,), width=max(1, E.px(t)))
    else:
        d.rounded_rectangle(outer, radius=max(1, E.px(r) - 1), fill=tuple(ink) + (255,))
        if mode == "duo":
            iw, ih = E.px(w - 3 * t), E.px(h - 3 * t)
            if iw > 3 and ih > 3:
                ir = max(0, min(E.px(r - 1.5 * t) - 1, iw // 2 - 1, ih // 2 - 1))
                _layer(img, lambda dd: dd.rounded_rectangle(
                    [E.px(1.5 * t), E.px(1.5 * t), E.px(1.5 * t) + iw, E.px(1.5 * t) + ih],
                    radius=ir, fill=tuple(ink2) + (240,)))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("stairs", "geometric", ("C", "D"), (56, 260, 50, 220),
           "阶梯：3–5 级剪影，实心/描边/双色勾边")
def el_stairs(ink, ink2, paper, size, rng, **kw):
    w, h = size
    n = max(3, min(5, int(kw.get("steps", rng.randint(3, 5)))))
    sw, sh = w / n, h / n
    pts = [(0.0, h)]
    for i in range(n):
        y = h - (i + 1) * sh
        pts += [(i * sw, y), ((i + 1) * sw, y)]
    pts.append((w, h))
    poly = [(E.px(x), E.px(y)) for x, y in pts]
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    mode = kw.get("mode") or rng.choice(["solid", "outline", "duo"])
    lw = max(1, E.px(min(w, h) * 0.055))
    if mode == "outline":
        d.line(poly + [poly[0]], fill=tuple(ink) + (255,), width=lw, joint="curve")
    else:
        d.polygon(poly, fill=tuple(ink) + (255,))
        if mode == "duo":
            _layer(img, lambda dd: dd.line(poly + [poly[0]], fill=tuple(ink2) + (255,),
                                           width=max(1, lw - 1), joint="curve"))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("stripe_band", "geometric", ("C", "D"), (60, 420, 14, 60),
           "条纹带：diagonal 斜纹 / vertical 竖条 / thin 细线屏")
def el_stripe_band(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    mode = kw.get("mode") or rng.choice(["diagonal", "vertical", "thin"])
    if mode == "vertical":
        pitch = float(kw.get("pitch", max(7.0, h * 0.55)))
        band = pitch * 0.50
        x, k = 0.0, 0
        while x < w:
            d.rectangle([E.px(x), 0, E.px(x + band), E.px(h)],
                        fill=tuple(ink if k % 2 == 0 else ink2) + (255,))
            x += pitch
            k += 1
    elif mode == "thin":
        pitch = float(kw.get("pitch", max(2.4, h * 0.24)))
        x = 0.0
        while x < w:
            d.rectangle([E.px(x), 0, max(E.px(x), E.px(x + pitch * 0.34)), E.px(h)],
                        fill=tuple(ink) + (255,))
            x += pitch
    else:
        pitch = float(kw.get("pitch", max(8.0, h * 0.70)))
        band = pitch * 0.52
        k = int(-h / pitch) - 2
        while k * pitch < w + h + pitch:
            x = k * pitch
            d.polygon([(E.px(x), 0), (E.px(x + band), 0),
                       (E.px(x + band + h), E.px(h)), (E.px(x + h), E.px(h))],
                      fill=tuple(ink if k % 2 == 0 else ink2) + (255,))
            k += 1
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("checkerboard", "geometric", ("C", "D"), (60, 320, 50, 220),
           "棋盘格：单色或双色交替方块，铺满不留缝")
def el_checkerboard(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    target = max(6.0, min(w, h) / 5.0)
    cols = max(2, int(round(w / target)))
    rows = max(2, int(round(h / target)))
    cw, ch = w / cols, h / rows
    mode = kw.get("mode") or rng.choice(["single", "two"])
    skip = float(kw.get("skip", 0.0))
    for j in range(rows):
        for i in range(cols):
            if (i + j) % 2:
                if mode == "single":
                    continue
                col = ink2
            else:
                col = ink
            if skip and rng.random() < skip:
                continue
            d.rectangle([E.px(i * cw), E.px(j * ch), E.px((i + 1) * cw), E.px((j + 1) * ch)],
                        fill=tuple(col) + (255,))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("zigzag_band", "geometric", ("C", "D"), (70, 440, 14, 56),
           "锯齿带：等厚人字纹，带一条第二色缝线")
def el_zigzag_band(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    n = max(4, int(round(w / max(9.0, h * 0.62))))
    cy, amp = h / 2.0, h * 0.26
    xs = [E.px(w * i / n) for i in range(n + 1)]
    ys = [cy + amp * (1.0 if i % 2 == 0 else -1.0) for i in range(n + 1)]
    pts = [(xs[i], E.px(ys[i])) for i in range(n + 1)]
    d = ImageDraw.Draw(img)
    d.line(pts, fill=tuple(ink) + (255,), width=max(1, E.px(h * 0.32)), joint="curve")
    if kw.get("second", True):
        _layer(img, lambda dd: dd.line(pts, fill=tuple(ink2) + (230,),
                                       width=max(1, E.px(h * 0.10)), joint="curve"))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("blob", "geometric", ("C", "D"), (40, 220, 40, 220),
           "有机斑块：光滑闭合曲线，可叠一层第二色")
def el_blob(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    lobes = int(kw.get("lobes", rng.randint(2, 4)))
    p0, p1 = rng.uniform(0, 6.28), rng.uniform(0, 6.28)

    def ring(scale, phase):
        pts = []
        for i in range(160):
            a = 2 * math.pi * i / 160
            rr = (1.0 + 0.16 * math.sin(lobes * a + phase)
                  + 0.07 * math.sin((lobes + 2) * a + phase * 1.7)) / 1.23
            pts.append((E.px(w / 2 + (w / 2 - 1) * scale * rr * math.cos(a)),
                        E.px(h / 2 + (h / 2 - 1) * scale * rr * math.sin(a))))
        return pts
    ImageDraw.Draw(img).polygon(ring(1.0, p0), fill=tuple(ink) + (255,))
    if kw.get("second", rng.random() < 0.6):
        _layer(img, lambda dd: dd.polygon(ring(0.58, p1), fill=tuple(ink2) + (225,)))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("plus_grid", "geometric", ("C", "D"), (60, 320, 60, 320),
           "加号网格：等距十字，少量第二色点缀")
def el_plus_grid(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    spacing = float(kw.get("spacing", max(9.0, min(w, h) / 3.2)))
    cols = max(2, int(w / spacing))
    rows = max(2, int(h / spacing))
    cw, ch = w / cols, h / rows
    arm = min(cw, ch) * 0.30
    mix = float(kw.get("mix", 0.25))
    for j in range(rows):
        for i in range(cols):
            cx, cy = (i + 0.5) * cw, (j + 0.5) * ch
            col = ink2 if rng.random() < mix else ink
            d.rectangle([E.px(cx - arm), E.px(cy - arm * 0.34),
                         E.px(cx + arm), E.px(cy + arm * 0.34)], fill=tuple(col) + (255,))
            d.rectangle([E.px(cx - arm * 0.34), E.px(cy - arm),
                         E.px(cx + arm * 0.34), E.px(cy + arm)], fill=tuple(col) + (255,))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("scallop_block", "geometric", ("C", "D"), (50, 300, 40, 180),
           "扇贝边块：一条边是半圆齿，块面填色")
def el_scallop_block(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    r = min(h * 0.55, max(5.0, w / 6.0))
    n = max(2, int(round(w / (2 * r))))
    bw = w / n
    r = bw / 2.0
    base = h - r
    pts = [(0.0, 0.0), (w, 0.0), (w, base)]
    for k in range(n - 1, -1, -1):
        pts += E.arc_pts((k + 0.5) * bw, base, r, r, 0, 180, n=18)
    d.polygon([(E.px(x), E.px(y)) for x, y in pts], fill=tuple(ink) + (255,))
    if kw.get("second", rng.random() < 0.5):
        edge = [(E.px(x), E.px(y)) for x, y in pts[2:]]
        _layer(img, lambda dd: dd.line(edge, fill=tuple(ink2) + (210,),
                                       width=max(1, E.px(min(h, w) * 0.02)),
                                       joint="curve"))
    if kw.get("edge", "bottom") == "top":
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("outline_letter", "geometric", ("C", "D"), (40, 200, 40, 200),
           "轮廓大写字母：只描边，字腔镂空")
def el_outline_letter(ink, ink2, paper, size, rng, **kw):
    import numpy as np
    w, h = size
    img = E.canvas(w, h)
    ch = (str(kw.get("letter", "A")) or "A")[:1]
    fam = kw.get("family", "Arial Black")
    probe = E.text_image(ch, fam, 100.0, ink)
    pb = probe.getchannel("A").getbbox()
    if pb is None:                              # 字体缺失时的兜底：一个描边方块
        ImageDraw.Draw(img).rectangle(_box(w * 0.16, h * 0.06, w * 0.84, h * 0.94),
                                      outline=tuple(ink) + (255,),
                                      width=max(1, E.px(min(w, h) * 0.07)))
        return E.grain(img, rng, uneven=0.04, holes=0)
    # 按“墨迹”而不是行高定字号：字母才真的撑满这个框
    kw_per = max(1e-6, (pb[2] - pb[0]) / E.SCALE / 100.0)
    kh_per = max(1e-6, (pb[3] - pb[1]) / E.SCALE / 100.0)
    s = min(w * 0.94 / kw_per, h * 0.94 / kh_per)
    tile = E.text_image(ch, fam, s, ink)
    bbox = tile.getchannel("A").getbbox()
    for _ in range(8):                          # 保证不出框
        if bbox and bbox[2] - bbox[0] <= E.px(w * 0.97) and bbox[3] - bbox[1] <= E.px(h * 0.97):
            break
        s *= 0.94
        tile = E.text_image(ch, fam, s, ink)
        bbox = tile.getchannel("A").getbbox()
    if bbox is None:
        return E.grain(img, rng, uneven=0.04, holes=0)
    tile = tile.crop(bbox)
    t = max(1.2, min(tile.width, tile.height) / E.SCALE * 0.075)
    a = np.asarray(tile.getchannel("A")).astype("float32")
    out = np.clip(a - _erode(a, t * E.SCALE), 0, 255).astype("uint8")
    glyph = Image.new("RGBA", tile.size, tuple(ink) + (0,))
    glyph.putalpha(Image.fromarray(out))
    img.alpha_composite(glyph, (int((img.width - glyph.width) / 2),
                                int((img.height - glyph.height) / 2)))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("triangle_strip", "geometric", ("C", "D"), (60, 440, 18, 70),
           "三角带：正反三角交替，双色或描边")
def el_triangle_strip(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    n = max(3, int(round(w / max(10.0, h * 1.05))))
    tw = w / n
    mode = kw.get("mode") or rng.choice(["two", "single", "outline"])
    lw = max(1, E.px(min(w, h) * 0.05))
    for i in range(n):
        x0, x1, xm = i * tw, (i + 1) * tw, (i + 0.5) * tw
        if i % 2 == 0:
            tri = [(E.px(x0), E.px(h)), (E.px(x1), E.px(h)), (E.px(xm), 0)]
        else:
            tri = [(E.px(x0), 0), (E.px(x1), 0), (E.px(xm), E.px(h))]
        if mode == "outline":
            d.line(tri + [tri[0]], fill=tuple(ink) + (255,), width=lw, joint="curve")
        else:
            col = ink if (mode == "single" or i % 2 == 0) else ink2
            d.polygon(tri, fill=tuple(col) + (255,))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("ring", "geometric", ("C", "D"), (30, 200, 30, 200),
           "圆环：同心环，或实心圆盘加细圈")
def el_ring(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    cx, cy = w / 2.0, h / 2.0
    outer = min(w, h) / 2.0 - 0.6
    rings = max(2, min(4, int(kw.get("rings", rng.randint(2, 4)))))
    mode = kw.get("mode") or rng.choice(["rings", "disc"])
    if mode == "disc":
        d.ellipse(_box(cx - outer, cy - outer, cx + outer, cy + outer),
                  fill=tuple(ink) + (255,))

        def circles(dd):
            for k in range(1, rings + 1):
                rr = outer * (1 - 0.22 * k)
                if rr > 1.0:
                    dd.ellipse(_box(cx - rr, cy - rr, cx + rr, cy + rr),
                               outline=tuple(ink2) + (235,),
                               width=max(1, E.px(min(w, h) * 0.018)))
        _layer(img, circles)
    else:
        for k in range(rings):
            r_out = outer * (1 - k / rings)
            r_in = outer * (1 - (k + 0.5) / rings)
            d.ellipse(_box(cx - r_out, cy - r_out, cx + r_out, cy + r_out),
                      fill=tuple(ink if k % 2 == 0 else ink2) + (255,))
            d.ellipse(_box(cx - r_in, cy - r_in, cx + r_in, cy + r_in), fill=(0, 0, 0, 0))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("quarter_tiles", "geometric", ("C", "D"), (40, 240, 40, 240),
           "四分之一圆风车瓦片：对角双扇相对，双色拼满整块")
def el_quarter_tiles(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    n = max(2, min(4, int(kw.get("n", rng.choice([2, 3])))))
    for j in range(n):
        for i in range(n):
            box = _box(i * w / n, j * h / n, (i + 1) * w / n, (j + 1) * h / n)
            start = ((i + j) % 4) * 90
            col = ink if (i + j) % 2 == 0 else ink2
            other = ink2 if col is ink else ink
            dx, dy = (box[2] - box[0]) * 0.20, (box[3] - box[1]) * 0.20
            inner = [box[0] + dx, box[1] + dy, box[2] - dx, box[3] - dy]
            dx2, dy2 = (box[2] - box[0]) * 0.38, (box[3] - box[1]) * 0.38
            small = [box[0] + dx2, box[1] + dy2, box[2] - dx2, box[3] - dy2]
            d.pieslice(box, start, start + 90, fill=tuple(col) + (255,))
            d.pieslice(box, start + 180, start + 270, fill=tuple(other) + (255,))
            d.pieslice(inner, start, start + 90, fill=tuple(other) + (255,))
            d.pieslice(small, start + 180, start + 270, fill=tuple(col) + (255,))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("line_screen", "geometric", ("C", "D"), (60, 320, 60, 320),
           "线屏：line 平行线 / cross 十字网 / moire 摩尔纹")
def el_line_screen(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    mode = kw.get("mode") or rng.choice(["line", "cross", "moire"])
    pitch = float(kw.get("spacing", max(2.6, min(w, h) / 16.0)))
    lpx = max(1, int(round(E.px(pitch * 0.30))))
    if mode == "line":
        y = pitch * 0.5
        while y < h:
            d.rectangle([0, E.px(y), img.width, E.px(y) + lpx - 1], fill=tuple(ink) + (255,))
            y += pitch
    elif mode == "cross":
        def grid(dd):
            y = pitch * 0.5
            while y < h:
                dd.rectangle([0, E.px(y), img.width, E.px(y) + lpx - 1],
                             fill=tuple(ink) + (255,))
                y += pitch
            x = pitch * 0.5
            while x < w:
                dd.rectangle([E.px(x), 0, E.px(x) + lpx - 1, img.height],
                             fill=tuple(ink2) + (240,))
                x += pitch
        _layer(img, grid)
    else:
        for ang, col in ((-7.0, ink), (7.0, ink2)):
            img.alpha_composite(_rotated_lines(img.size, pitch, pitch * 0.30, col, ang))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("circle_text_badge", "geometric", ("C", "D"), (64, 260, 64, 260),
           "圆形环绕文字徽章：文字沿圆周排布 + 内圈小字")
def el_circle_text_badge(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    cx, cy = w / 2.0, h / 2.0
    half = min(w, h) / 2.0
    text = str(kw.get("text", "RISOGRAPH ORIGINAL PRINT · ")).upper()
    inner = str(kw.get("inner", "01"))
    fam = kw.get("family", "Arial")
    # 字号由圆周长决定：一路收小，直到这一圈字刚好排得下且不压字
    s = max(4.0, min(half * 0.62, (half - 3.0) / 2.05))
    while s > 3.6:
        lh = tm.line_height(fam, s)
        R = half - 1.0 - lh * 0.80
        if R > 2.0 and sum(tm.advance(c, fam, s) for c in text) <= 2 * math.pi * R * 0.92:
            break
        s *= 0.94
    lh = tm.line_height(fam, s)
    R = max(2.0, half - 1.0 - lh * 0.80)
    hole = R - lh * 0.62                       # 圈内净空：内圈小字只能占这么多
    total = sum(tm.advance(c, fam, s) for c in text)
    ang = -math.pi / 2 - (total / R) / 2.0       # 从正上方起排，整圈居中
    for ch in text:
        adv = tm.advance(ch, fam, s)
        mid = ang + (adv / 2.0) / R
        tile = E.text_image(ch, fam, s, ink)
        if tile.getchannel("A").getbbox() is not None:
            rot = tile.rotate(-(math.degrees(mid) + 90.0), resample=Image.BICUBIC,
                              expand=True)
            img.alpha_composite(rot, (int(E.px(cx + R * math.cos(mid)) - rot.width / 2.0),
                                      int(E.px(cy + R * math.sin(mid)) - rot.height / 2.0)))
        ang += adv / R
    lw = max(1, E.px(half * 0.035))
    d.ellipse(_box(cx - R - lh * 0.62, cy - R - lh * 0.62,
                   cx + R + lh * 0.62, cy + R + lh * 0.62),
              outline=tuple(ink) + (255,), width=lw)
    if R - lh * 0.60 > 1.2:                      # 圈太小时内圈会翻过来
        d.ellipse(_box(cx - R + lh * 0.60, cy - R + lh * 0.60,
                       cx + R - lh * 0.60, cy + R - lh * 0.60),
                  outline=tuple(ink2) + (230,), width=max(1, lw - 1))
    if inner and hole > 3.0:
        itile, _is = _fit_tile(inner, fam, min(hole * 0.90, s * 2.4), ink2,
                               hole * 1.50, 3.0)
        img.alpha_composite(itile, (int(E.px(cx) - itile.width / 2.0),
                                    int(E.px(cy) - itile.height / 2.0)))
    return E.grain(img, rng, uneven=0.04, holes=0)


# =============================================================== texture (A–F)
def _screen_dots(img, w, h, colour, kw, rng, square=False):
    """One halftone screen on the 45° lattice, tone carried by the dot radius.

    radius = rmax · fade, so the dots march monotonically down to zero and then
    stop being drawn at all — that is the difference between a screen and a grid.
    """
    fade = str(kw.get("fade", "linear"))
    ux, uy, half = _fade_axes(w, h, kw)
    spacing = max(1.4, float(kw.get("spacing", max(3.0, min(w, h) / 20.0))))
    rmax = float(kw.get("rmax", spacing * 0.46))
    alpha = int(kw.get("alpha", 235))
    d = ImageDraw.Draw(img)
    for x, y in _dot_lattice(w, h, spacing, rng):
        v = _fade_at(x, y, w, h, fade, ux, uy, half)
        if v <= 0.015:
            continue
        r = rmax * v
        if r < 0.26:
            continue
        a = int(alpha * min(1.0, 0.45 + 0.55 * v))
        if a < 8:
            continue
        if square:
            d.rectangle(_box(x - r, y - r, x + r, y + r), fill=tuple(colour) + (a,))
        else:
            d.ellipse(_box(x - r, y - r, x + r, y + r), fill=tuple(colour) + (a,))
    return img


@E.element("dot_screen", "texture", ("A", "B", "C", "D", "E", "F"), (60, 340, 50, 300),
           "圆点网点：45° 排布，点径沿 dir 由大到无")
def el_dot_screen(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    _screen_dots(img, w, h, ink, kw, rng, square=False)
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("square_dot_screen", "texture", ("A", "B", "C", "D", "E", "F"),
           (60, 340, 50, 300), "方点网点：同样是 45° 排布，方块边长渐隐")
def el_square_dot_screen(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    _screen_dots(img, w, h, kw.get("colour", ink), kw, rng, square=True)
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("line_texture", "texture", ("A", "B", "C", "D", "E", "F"), (60, 340, 50, 300),
           "排线：平行线，线宽与浓度一起渐隐")
def el_line_texture(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    pitch = float(kw.get("spacing", max(3.6, min(w, h) / 15.0)))
    lw = float(kw.get("lw", pitch * 0.46))
    angle = float(kw.get("angle", float(kw.get("dir", 0.0) or 0.0) + 90.0))
    _line_field(img, w, h, ink, angle, pitch, lw,
                {"dir": kw.get("dir", 0.0), "fade": kw.get("fade", "linear")},
                alpha=int(kw.get("alpha", 250)))
    return E.grain(img, rng, uneven=0.06, holes=0)


@E.element("cross_hatch", "texture", ("A", "B", "C", "D", "E", "F"), (60, 340, 50, 300),
           "交叉网：两组斜排线叠印，交汇处更深")
def el_cross_hatch(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    pitch = float(kw.get("spacing", max(5.0, min(w, h) / 11.0)))
    lw = float(kw.get("lw", pitch * 0.34))
    d0 = float(kw.get("dir", 0.0) or 0.0)
    fade = kw.get("fade", "linear")
    alpha = int(kw.get("alpha", 225))
    _line_field(img, w, h, ink, d0 + 45.0, pitch, lw, {"dir": d0, "fade": fade}, alpha)
    _line_field(img, w, h, ink2, d0 - 45.0, pitch, lw, {"dir": d0, "fade": fade}, alpha)
    return E.grain(img, rng, uneven=0.06, holes=0)


@E.element("stipple", "texture", ("A", "B", "C", "D", "E", "F"), (60, 340, 60, 300),
           "点刻：随机点的密度与点径双重渐隐")
def el_stipple(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    fade = str(kw.get("fade", "linear"))
    ux, uy, half = _fade_axes(w, h, kw)
    tries = int(kw.get("count", max(600.0, w * h / 9.0)))
    tries = max(120, min(tries, 9000))
    rmax = float(kw.get("rmax", max(0.42, min(w, h) / 220.0)))
    alpha = int(kw.get("alpha", 245))
    for _ in range(tries):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        v = _fade_at(x, y, w, h, fade, ux, uy, half)
        if v <= 0.02 or rng.random() > v ** 1.35:
            continue
        r = rmax * (0.55 + 0.45 * v)
        if r < 0.24:
            continue
        a = int(alpha * min(1.0, 0.50 + 0.50 * v))
        d.ellipse(_box(x - r, y - r, x + r, y + r), fill=tuple(ink) + (a,))
    return E.grain(img, rng, uneven=0.06, holes=0)


@E.element("grain_gradient", "texture", ("A", "B", "C", "D", "E", "F"), (60, 340, 60, 300),
           "颗粒渐变：随机颗粒的疏密沿 dir 渐隐")
def el_grain_gradient(ink, ink2, paper, size, rng, **kw):
    import numpy as np
    w, h = size
    img = E.canvas(w, h)
    fade = str(kw.get("fade", "linear"))
    ux, uy, half = _fade_axes(w, h, kw)
    field = _fade_grid(w, h, fade, ux, uy, half)
    noise = _np_rng(rng).random(field.shape)
    density = float(kw.get("density", 0.62))
    keep = noise < np.clip(field, 0, 1) ** 1.25 * density
    a = (0.35 + 0.65 * field) * 255.0 * keep
    layer = Image.new("RGBA", img.size, tuple(ink) + (0,))
    layer.putalpha(Image.fromarray(a.astype("uint8")))
    img.alpha_composite(layer)
    return img


# ================================================================ print (A/C/D)
@E.element("colour_bar", "print", ("A", "C", "D"), (70, 420, 26, 90),
           "色标条：一排墨色块，每块下方标两三个字的墨色名")
def el_colour_bar(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    mix = tuple(int(round(ink[i] * ink2[i] / 255.0)) for i in range(3))
    swatches = kw.get("colours") or [(ink, _ink_name(ink)), (ink2, _ink_name(ink2)),
                                     (mix, "叠印"), (paper, _ink_name(paper))]
    n = max(1, len(swatches))
    pad = max(1.2, w * 0.014)
    gap = max(1.0, w * 0.010)
    sw = max(3.0, (w - 2 * pad - gap * (n - 1)) / n)
    lab_h = min(h * 0.34, 13.0)
    sw_h = max(3.0, h - pad - lab_h * 1.30 - 1.0)
    for i, (col, name) in enumerate(swatches):
        x0 = pad + i * (sw + gap)
        d.rectangle(_box(x0, pad, x0 + sw, pad + sw_h), fill=tuple(col) + (255,))
        if sum(col) / 3.0 > 190:                 # 浅色块要有一圈极细的边才看得见
            d.rectangle(_box(x0, pad, x0 + sw, pad + sw_h),
                        outline=tuple(ink) + (110,), width=1)
        tile, _s = _fit_tile(name, "SimHei", min(lab_h, sw * 0.85), ink, sw * 0.96, 3.2)
        img.alpha_composite(tile, (int(E.px(x0 + sw / 2) - tile.width / 2),
                                   E.px(pad + sw_h + 0.5)))
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("crop_marks", "print", ("A", "C", "D"), (40, 300, 40, 300),
           "裁切线：四角 L 形，可带中心十字规矩线")
def el_crop_marks(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    m = float(kw.get("margin", max(1.2, min(w, h) * 0.02)))
    arm = min(w, h) * float(kw.get("arm", 0.22))
    lw = max(1, int(round(E.px(max(0.9, min(w, h) * 0.012)))))
    for sx in (0, 1):
        for sy in (0, 1):
            x = m if sx == 0 else w - m
            y = m if sy == 0 else h - m
            dx = 1.0 if sx == 0 else -1.0
            dy = 1.0 if sy == 0 else -1.0
            d.line([(E.px(x), E.px(y)), (E.px(x + dx * arm), E.px(y))],
                   fill=tuple(ink) + (255,), width=lw)
            d.line([(E.px(x), E.px(y)), (E.px(x), E.px(y + dy * arm))],
                   fill=tuple(ink) + (255,), width=lw)
    if kw.get("center", True):
        r = min(w, h) * 0.10
        d.line([(E.px(w / 2 - r), E.px(h / 2)), (E.px(w / 2 + r), E.px(h / 2))],
               fill=tuple(ink2) + (235,), width=max(1, lw - 1))
        d.line([(E.px(w / 2), E.px(h / 2 - r)), (E.px(w / 2), E.px(h / 2 + r))],
               fill=tuple(ink2) + (235,), width=max(1, lw - 1))
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("fold_line", "print", ("A", "C", "D"), (60, 420, 12, 40),
           "折叠虚线：dash / dot / dashdot 三种节奏")
def el_fold_line(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    mode = kw.get("mode") or rng.choice(["dash", "dot", "dashdot"])
    vertical = bool(kw.get("vertical", False)) or int(kw.get("dir", 0) or 0) % 180 == 90
    L = h if vertical else w
    t = max(0.9, min(h, w) * 0.10)
    unit = max(2.4, t * 2.2)
    pat = {"dash": [(1.6, 1.0)], "dot": [(0.35, 1.0)],
           "dashdot": [(1.6, 0.9), (0.35, 0.9)]}.get(mode, [(1.6, 1.0)])
    mid = (w if vertical else h) / 2.0
    pos = 0.0
    while pos < L:
        for on, off in pat:
            if pos >= L:
                break
            end = min(L, pos + on * unit)
            if vertical:
                d.rectangle(_box(mid - t / 2, pos, mid + t / 2, end),
                            fill=tuple(ink) + (255,))
            else:
                d.rectangle(_box(pos, mid - t / 2, end, mid + t / 2),
                            fill=tuple(ink) + (255,))
            pos = end + off * unit
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("binding_holes", "print", ("A", "C", "D"), (30, 160, 80, 340),
           "装订孔：纸边 + 一列圆孔，孔下沿带浅影")
def el_binding_holes(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    strip = min(w * 0.80, max(11.0, w * 0.64))
    d.rectangle([0, 0, E.px(strip), E.px(h)], fill=tuple(paper) + (255,))
    for k in range(5):                            # 纸边右侧的分级投影
        x0 = strip + k * max(0.8, w * 0.02)
        if x0 >= w:
            break
        d.rectangle(_box(x0, 0, min(w, x0 + max(0.8, w * 0.02)), h),
                    fill=tuple(ink) + (max(9, 60 - k * 13),))
    d.rectangle([E.px(strip), 0, min(img.width - 1, E.px(strip) + max(1, E.px(0.7))),
                 img.height - 1], fill=tuple(ink) + (120,))
    sp = max(16.0, h / 5.5)
    n = max(2, int(h / sp))
    sp = h / n
    r = min(strip * 0.30, max(2.0, sp * 0.26))
    for i in range(n):
        cy = (i + 0.5) * sp
        if cy - r < 1.0 or cy + r > h - 1.0:
            continue
        cx = strip * 0.5
        d.arc(_box(cx - r, cy - r + r * 0.22, cx + r, cy + r + r * 0.22),
              10, 170, fill=tuple(ink2) + (120,), width=max(1, E.px(0.8)))
    for i in range(n):                            # 冲孔
        cy = (i + 0.5) * sp
        if cy - r < 1.0 or cy + r > h - 1.0:
            continue
        cx = strip * 0.5
        d.ellipse(_box(cx - r, cy - r, cx + r, cy + r), fill=(0, 0, 0, 0))
    return E.grain(img, rng, uneven=0.05, holes=0.0006)


@E.element("ink_smudge", "print", ("A", "C", "D"), (40, 260, 30, 180),
           "墨渍：不规则边缘 + 少量飞溅点")
def el_ink_smudge(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    cx, cy = w / 2.0, h / 2.0
    rx = (w / 2.0 - 1.0) / 1.42 * rng.uniform(0.60, 0.92)
    ry = (h / 2.0 - 1.0) / 1.42 * rng.uniform(0.60, 0.92)
    p0, p1 = rng.uniform(0, 6.28), rng.uniform(0, 6.28)
    pts = []
    for i in range(120):
        a = 2 * math.pi * i / 120
        rr = (1.0 + 0.20 * math.sin(3 * a + p0) + 0.12 * math.sin(7 * a + p1)
              + rng.uniform(-0.045, 0.045))
        pts.append((E.px(cx + rx * rr * math.cos(a)), E.px(cy + ry * rr * math.sin(a))))
    d.polygon(pts, fill=tuple(ink) + (255,))
    if kw.get("second", rng.random() < 0.5):      # 第二色小晕
        _layer(img, lambda dd: dd.ellipse(
            _box(cx - rx * 0.45, cy - ry * 0.45, cx + rx * 0.45, cy + ry * 0.45),
            fill=tuple(ink2) + (200,)))
    for _ in range(rng.randint(3, 8)):            # 飞溅
        sx, sy = rng.uniform(1.0, w - 1.0), rng.uniform(1.0, h - 1.0)
        if math.hypot((sx - cx) / max(rx, 1e-6), (sy - cy) / max(ry, 1e-6)) < 1.05:
            continue
        sr = rng.uniform(0.5, 1.7)
        d.ellipse(_box(sx - sr, sy - sr, sx + sr, sy + sr), fill=tuple(ink) + (240,))
    return E.grain(img, rng, uneven=0.10, holes=0.004)


@E.element("barcode", "print", ("A", "C", "D"), (70, 320, 40, 130),
           "条形码：随机条宽 + 下方数字")
def el_barcode(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    code = str(kw.get("code", "".join(str(rng.randint(0, 9)) for _ in range(12))))
    n = max(1, len(code))
    slot = (w - 4.0) / n
    s = E.fit_text("0", "Arial", min(h * 0.18, slot * 1.7, 20.0), slot * 0.86, 2.6)
    tl_h = tm.line_height("Arial", s)
    bh = max(4.0, h - tl_h - 3.0)
    unit = max(0.7, w / 110.0)
    x = 2.0
    while x < w - 2.5:
        bw = min(unit * rng.choice([1, 1, 1, 2, 3]), w - 2.0 - x)
        d.rectangle(_box(x, 1.0, x + bw, 1.0 + bh), fill=tuple(ink) + (255,))
        x += bw + unit * rng.choice([1, 1, 2])
    ty = int(E.px(1.0 + bh + 1.6))
    for i, ch in enumerate(code):
        tile = E.text_image(ch, "Arial", s, ink)
        img.alpha_composite(tile, (int(E.px(2.0 + (i + 0.5) * slot) - tile.width / 2), ty))
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("printed_note", "print", ("A", "C", "D"), (90, 360, 22, 70),
           "版权小字：上下细线之间的印注，可两行")
def el_printed_note(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    t = max(0.7, h * 0.05)
    d.rectangle([0, 0, img.width, max(1, E.px(t))], fill=tuple(ink) + (255,))
    d.rectangle([0, img.height - max(1, E.px(t)), img.width, img.height],
                fill=tuple(ink) + (255,))
    main = str(kw.get("text", "PRINTED IN 2 COLOURS"))
    sub = str(kw.get("sub", "RISOGRAPH · LIMITED EDITION"))
    band = h - 2 * t
    fam = kw.get("family", "Arial Black")
    mtile, ms = _fit_tile(main, fam, band * 0.60, ink, w * 0.94, 4.0)
    mh = tm.line_height(fam, ms)
    stile = None
    if sub and band - mh > band * 0.30:
        stile, _ss = _fit_tile(sub, "Georgia", min(mh * 0.52, band * 0.28),
                               ink2, w * 0.90, 3.4)
        if stile.height / E.SCALE + mh > band * 0.98:
            stile = None
    total = mh + (stile.height / E.SCALE if stile else 0.0)
    y = t + (band - total) / 2.0
    img.alpha_composite(mtile, (int((img.width - mtile.width) / 2), int(E.px(y))))
    if stile is not None:
        img.alpha_composite(stile, (int((img.width - stile.width) / 2),
                                    int(E.px(y + mh))))
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("paper_sheet", "print", ("A", "C", "D"), (120, 500, 90, 380),
           "整页纸：白边 + 右下投影，可当整页底")
def el_paper_sheet(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    m = float(kw.get("margin", max(3.0, min(w, h) * 0.045)))
    m = max(2.0, min(m, w * 0.18, h * 0.18))
    off = max(1.5, min(w, h) * 0.022)
    off = min(off, m * 0.60)
    sheet = _box(m, m, w - m, h - m)

    def shadow(dd):
        for k, a in ((2, 16), (1, 34), (0, 58)):
            dd.rectangle([sheet[0] + E.px(off * (1 + k * 0.55)),
                          sheet[1] + E.px(off * (1 + k * 0.55)),
                          sheet[2] + E.px(off * (1 + k * 0.55)),
                          sheet[3] + E.px(off * (1 + k * 0.55))],
                         fill=tuple(ink2) + (a,))
    _layer(img, shadow)
    d = ImageDraw.Draw(img)
    d.rectangle(sheet, fill=tuple(paper) + (255,))
    if kw.get("frame", True):
        inset = max(2.0, min(w, h) * 0.045)
        d.rectangle(_box(m + inset, m + inset, w - m - inset, h - m - inset),
                    outline=tuple(ink) + (70,), width=1)
    tick = max(3.0, min(w, h) * 0.055)            # 四角印刷角标
    for sx in (0, 1):
        for sy in (0, 1):
            x = m + tick if sx == 0 else w - m - tick
            y = m + tick if sy == 0 else h - m - tick
            dx = 1.0 if sx == 0 else -1.0
            dy = 1.0 if sy == 0 else -1.0
            d.line([(E.px(x), E.px(y)), (E.px(x + dx * tick * 0.6), E.px(y))],
                   fill=tuple(ink2) + (150,), width=max(1, E.px(0.8)))
            d.line([(E.px(x), E.px(y)), (E.px(x), E.px(y + dy * tick * 0.6))],
                   fill=tuple(ink2) + (150,), width=max(1, E.px(0.8)))
    return E.grain(img, rng, uneven=0.05, holes=0.0006, soften=0.6)


# =========================================================== typography (B/C/D/F)
@E.element("marquee_band", "typography", ("B", "C", "D", "F"), (90, 460, 20, 64),
           "跑马灯条带：重复文字 + 上下边线，可斜体")
def el_marquee_band(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    rule = max(0.8, h * 0.055)
    d.rectangle([0, 0, img.width, max(1, E.px(rule))], fill=tuple(ink) + (255,))
    d.rectangle([0, img.height - max(1, E.px(rule)), img.width, img.height],
                fill=tuple(ink) + (255,))
    band = h - 2 * rule
    txt = str(kw.get("text", "RISOGRAPH PRESS · OPEN STUDIO · "))
    fam = kw.get("family", "Impact")
    italic = bool(kw.get("italic", rng.random() < 0.5))
    tile, _s = _fit_tile(txt, fam, min(band * 0.66, w * 0.5), ink, w * 0.46, 4.0)
    if italic:
        tile = _shear(tile, float(kw.get("slant", 0.22)))
    y = int((img.height - tile.height) / 2)
    x = -tile.width * 0.35
    while x < img.width:
        img.alpha_composite(tile, (int(x), y))
        x += tile.width
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("vertical_text", "typography", ("B", "C", "D", "F"), (26, 120, 80, 340),
           "竖排文字：逐字竖排，右侧细线，可整列倒置")
def el_vertical_text(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    txt = str(kw.get("text", "竖排文字"))
    fam = kw.get("family", "SimHei")
    rule = bool(kw.get("rule", True))
    pad = max(1.6, w * 0.10) if rule else max(1.0, w * 0.05)
    avail = max(4.0, w - pad - 1.0)
    n = max(1, len(txt))
    cell = h / n
    s = min(avail * 0.92, cell / 1.32)
    widest = max(tm.advance(c, fam, s) for c in txt)
    if widest > avail * 0.94:
        s *= avail * 0.94 / widest
    for i, ch in enumerate(txt):
        tile = E.text_image(ch, fam, s, ink)
        if tile.getchannel("A").getbbox() is None:
            continue
        img.alpha_composite(tile, (int(E.px(avail / 2) - tile.width / 2),
                                   int(E.px(i * cell + (cell - tile.height / E.SCALE) / 2))))
    if rule:
        d = ImageDraw.Draw(img)
        lw = max(1, E.px(max(0.7, w * 0.045)))
        d.rectangle([img.width - lw, 0, img.width, img.height],
                    fill=tuple(ink2) + (210,))
    if kw.get("upside", False):
        img = img.transpose(Image.ROTATE_180)
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("issue_stamp", "typography", ("B", "C", "D", "F"), (70, 260, 50, 150),
           "期号章：方框 + 三行小字 + 细分隔线")
def el_issue_stamp(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    lw = max(1, int(round(E.px(max(1.0, min(w, h) * 0.032)))))
    d.rectangle([E.px(1), E.px(1), img.width - 1 - E.px(1), img.height - 1 - E.px(1)],
                outline=tuple(ink) + (255,), width=lw)
    inner = max(2.5, min(w, h) * 0.10)
    d.rectangle(_box(inner, inner, w - inner, h - inner),
                outline=tuple(ink) + (120,), width=1)
    specs = [("Arial", str(kw.get("top", "VOL. 03"))),
             ("Arial Black", str(kw.get("mid", "ISSUE 07"))),
             ("Georgia", str(kw.get("date", "MAR 2024")))]
    box_w = max(6.0, w - 2 * inner - 4.0)
    avail = max(6.0, h - 2 * inner - 2.0)
    sizes = [E.fit_text(t, f, min(box_w * 0.42, avail * 0.42), box_w * 0.94, 3.4)
             for f, t in specs]
    sep = max(1.6, h * 0.045)

    def total(ss):
        return sum(tm.line_height(f, s) for (f, _t), s in zip(specs, ss)) + 2 * (sep + 1.0)
    if total(sizes) > avail * 0.98:
        k = avail * 0.98 / total(sizes)
        sizes = [s * k for s in sizes]
    y = inner + max(0.0, (avail - total(sizes)) / 2.0)
    for i, ((fam, txt), s) in enumerate(zip(specs, sizes)):
        tile = E.text_image(txt, fam, s, ink)
        img.alpha_composite(tile, (int((img.width - tile.width) / 2), int(E.px(y))))
        y += tm.line_height(fam, s)
        if i < len(specs) - 1:
            y += sep
            d.rectangle(_box(w / 2 - box_w / 2, y, w / 2 + box_w / 2, y + 0.8),
                        fill=tuple(ink2) + (170,))
            y += 1.0 + sep
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("caption_label", "typography", ("B", "C", "D", "F"), (70, 380, 14, 44),
           "图注标签：短横线 + 小字")
def el_caption_label(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    txt = str(kw.get("text", "FIG. 01 — PRESS SHEET"))
    fam = kw.get("family", "Georgia")
    tick = min(w * 0.24, max(6.0, h * 0.95))
    gap = max(2.5, h * 0.24)
    t = max(0.8, h * 0.10)
    d.rectangle(_box(0, h / 2 - t / 2, tick, h / 2 + t / 2), fill=tuple(ink) + (255,))
    if kw.get("dot", True):
        r = max(0.8, t * 0.75)
        d.ellipse(_box(-r + t * 0.6, h / 2 - r, t * 0.6 + r, h / 2 + r),
                  fill=tuple(ink2) + (235,))
    tile, _s = _fit_tile(txt, fam, min(h * 0.74, (w - tick - gap) * 0.62),
                         ink, w - tick - gap, 3.4)
    img.alpha_composite(tile, (int(E.px(tick + gap)),
                               int((img.height - tile.height) / 2)))
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("starburst_badge", "typography", ("B", "C", "D", "F"), (60, 260, 60, 260),
           "星爆徽章：尖角底 + 镂空内圈 + 两行文字")
def el_starburst_badge(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    spikes = max(8, min(20, int(kw.get("spikes", rng.randint(11, 16)))))
    rx, ry = w / 2.0 - 0.6, h / 2.0 - 0.6
    pts = []
    for i in range(spikes * 2):
        a = math.pi * i / spikes - math.pi / 2
        r = 1.0 if i % 2 == 0 else float(kw.get("inner", 0.74))
        pts.append((E.px(w / 2 + rx * r * math.cos(a)), E.px(h / 2 + ry * r * math.sin(a))))
    d.polygon(pts, fill=tuple(ink) + (255,))
    ir = min(rx, ry) * 0.60
    frame = max(1, E.px(min(w, h) * 0.012))
    d.ellipse(_box(w / 2 - ir, h / 2 - ir, w / 2 + ir, h / 2 + ir), fill=(0, 0, 0, 0))
    d.ellipse(_box(w / 2 - ir, h / 2 - ir, w / 2 + ir, h / 2 + ir),
              outline=tuple(ink) + (255,), width=frame)
    main = str(kw.get("text", "NEW"))
    sub = str(kw.get("sub", "2024"))
    mtile, ms = _fit_tile(main, "Arial Black", ir * 1.15, ink, ir * 1.30, 3.4)
    stile, ss = _fit_tile(sub, "Georgia", ir * 0.62, ink2, ir * 1.20, 3.0)
    mh = mtile.height / E.SCALE
    sh = stile.height / E.SCALE
    if mh + sh > ir * 1.34:                      # 保证两行都落在内圈里
        k = ir * 1.34 / (mh + sh)
        mtile = E.text_image(main, "Arial Black", ms * k, ink)
        stile = E.text_image(sub, "Georgia", ss * k, ink2)
        mh = mtile.height / E.SCALE
        sh = stile.height / E.SCALE
    y = int((img.height - E.px(mh + sh)) / 2.0)
    img.alpha_composite(mtile, (int((img.width - mtile.width) / 2), y))
    img.alpha_composite(stile, (int((img.width - stile.width) / 2), y + mtile.height))
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("circled_number", "typography", ("B", "C", "D", "F"), (24, 110, 24, 110),
           "圆圈数字：描边圈或实心圈（数字是镂空的）")
def el_circled_number(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    num = str(kw.get("number", rng.randint(1, 99)))
    mode = kw.get("mode") or rng.choice(["outline", "solid"])
    r = min(w, h) / 2.0 - 0.6
    t = max(1.2, min(w, h) * 0.09)
    box = _box(w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r)
    if mode == "solid":
        d.ellipse(box, fill=tuple(ink) + (255,))
    else:
        d.ellipse(box, outline=tuple(ink) + (255,), width=max(1, E.px(t)))
    ts = E.fit_text(num, "Arial Black", r * 1.30, r * 1.36, 3.2)
    tile = E.text_image(num, "Arial Black", ts, ink)
    bbox = tile.getchannel("A").getbbox()
    if bbox is None:
        return E.grain(img, rng, uneven=0.04, holes=0)
    tile = tile.crop(bbox)
    pos = (int((img.width - tile.width) / 2), int((img.height - tile.height) / 2))
    if mode == "solid":
        img.paste((0, 0, 0, 0), pos, tile.getchannel("A"))
    else:
        img.alpha_composite(tile, pos)
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("drop_cap", "typography", ("B", "C", "D", "F"), (90, 380, 60, 260),
           "首字下沉：大字母块 + 旁边若干条文字线")
def el_drop_cap(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    ch = (str(kw.get("letter", rng.choice(["A", "T", "S", "M"]))) or "A")[:1]
    fam = kw.get("family", "Georgia")
    mode = kw.get("mode") or rng.choice(["plain", "block"])
    side = min(h * 0.96, w * 0.42)
    probe = E.text_image(ch, fam, 100.0, ink)
    pb = probe.getchannel("A").getbbox()
    if pb is None:
        d.rectangle(_box(0, 0, side, side), fill=tuple(ink) + (255,))
        return E.grain(img, rng, uneven=0.05, holes=0)
    # 同样按墨迹定字号：大写字母要真的占满这个方块
    kw_per = max(1e-6, (pb[2] - pb[0]) / E.SCALE / 100.0)
    kh_per = max(1e-6, (pb[3] - pb[1]) / E.SCALE / 100.0)
    s = min(side * 0.86 / kw_per, side * 0.86 / kh_per)
    tile = E.text_image(ch, fam, s, ink)
    bbox = tile.getchannel("A").getbbox()
    if bbox is None:
        d.rectangle(_box(0, 0, side, side), fill=tuple(ink) + (255,))
        return E.grain(img, rng, uneven=0.05, holes=0)
    tile = tile.crop(bbox)
    pos = (int(E.px(side / 2) - tile.width / 2), int(E.px(side / 2) - tile.height / 2))
    if mode == "block":
        d.rectangle(_box(0, 0, side, side), fill=tuple(ink) + (255,))
        img.paste((0, 0, 0, 0), pos, tile.getchannel("A"))
    else:
        img.alpha_composite(tile, pos)
    gap = max(2.5, w * 0.035)
    line_h = max(3.2, side * 0.24)
    rows = max(3, int(h / line_h))
    bar = max(1.2, line_h * 0.30)
    for i in range(rows):
        y = i * line_h
        x0 = side + gap if y < side else 0.0
        avail = w - x0
        if avail < 6.0:
            continue
        ln = avail * rng.uniform(0.58, 0.98)
        if i == rows - 1:
            ln = avail * rng.uniform(0.28, 0.46)
        d.rectangle(_box(x0, y + (line_h - bar) / 2, x0 + ln, y + line_h - (line_h - bar) / 2),
                    fill=tuple(ink if i % 4 else ink2) + (150,))
    return E.grain(img, rng, uneven=0.05, holes=0)


# ================================================================ retro_ui (E)
PIXEL_ART = {
    "folder": ("00000000", "01110000", "01111110", "11111111",
               "11111111", "11111111", "11111111", "02222220"),
    "disk": ("11111111", "12222221", "12222221", "11111111",
             "11111111", "12222221", "12222221", "11111111"),
    "star": ("00011000", "00011000", "01111110", "11111111",
             "01111110", "00111100", "01100110", "11000011"),
    "heart": ("01100110", "11111111", "11111111", "11111111",
              "01111110", "00111100", "00011000", "00000000"),
}


@E.element("os_window", "retro_ui", ("E",), (110, 420, 80, 300),
           "复古 OS 窗口：标题栏 + 三个按钮 + 内容斜纹 + 缩放角")
def el_os_window(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    lwpt = max(1.0, min(w, h) * 0.016)
    lw = max(1, int(round(E.px(lwpt))))
    off = max(1.5, min(w, h) * 0.022)

    def shadow(dd):
        dd.rectangle([E.px(off), E.px(off), img.width - 1, img.height - 1],
                     fill=tuple(ink2) + (60,))
    _layer(img, shadow)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width - 1, img.height - 1], fill=tuple(paper) + (255,))
    th = max(9.0, min(h * 0.17, 22.0))
    d.rectangle([lw, lw, img.width - 1 - lw, E.px(th)], fill=tuple(ink) + (255,))
    bs = max(2.4, th * 0.34)
    for k in range(3):                           # 三个窗口按钮
        x = w - lwpt - (k + 1) * (bs * 1.6) - 1.0
        d.rectangle(_box(x, th / 2 - bs / 2, x + bs, th / 2 + bs / 2),
                    fill=tuple(paper) + (255,))
        d.rectangle(_box(x, th / 2 - bs / 2, x + bs, th / 2 + bs / 2),
                    outline=tuple(ink) + (255,), width=1)
    title = str(kw.get("title", "PRINT.JOB"))
    avail = max(8.0, w - lwpt - 3 * bs * 1.7 - 3.0)
    ttile, _ts = _fit_tile(title, "Arial", th * 0.66, paper, avail, 3.2)
    img.alpha_composite(ttile, (int(E.px(lwpt + 2.0)),
                                int(E.px(th / 2) - ttile.height / 2)))
    cx0, cy0 = lwpt + 2.0, th + 2.0
    cw, ch = max(6.0, w - 2 * lwpt - 4.0), max(6.0, h - th - lwpt - 4.0)
    pitch = max(6.0, min(cw, ch) * 0.16)
    img.alpha_composite(_diag_stripes(cw, ch, pitch, pitch * 0.34, ink, 40, pitch * 0.3),
                        (E.px(cx0), E.px(cy0)))
    d.rectangle([lw, lw, img.width - 1 - lw, img.height - 1 - lw],
                outline=tuple(ink) + (255,), width=lw)
    grip = max(3.0, min(cw, ch) * 0.10)          # 右下缩放角
    for k in range(3):
        gx = cx0 + cw - grip * (k + 0.4)
        d.line([(E.px(gx), E.px(cy0 + ch - 1.0)),
                (E.px(gx + grip * 0.7), E.px(cy0 + ch - 1.0 - grip * 0.7))],
               fill=tuple(ink2) + (200,), width=max(1, lw - 1))
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("cursor_arrow", "retro_ui", ("E",), (20, 70, 28, 90),
           "光标箭头：实心箭头 + 纸白描边")
def el_cursor_arrow(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    shape = [(0.06, 0.03), (0.06, 0.78), (0.27, 0.60), (0.41, 0.96),
             (0.56, 0.89), (0.42, 0.55), (0.70, 0.53)]
    if kw.get("flip", False):
        shape = [(1 - x, y) for x, y in shape]
    poly = [(E.px(x * w), E.px(y * h)) for x, y in shape]
    pad = max(1.6, min(w, h) * 0.12)
    d.line(poly + [poly[0]], fill=tuple(paper) + (255,), width=max(1, E.px(pad)),
           joint="curve")
    d.polygon(poly, fill=tuple(ink) + (255,))
    if kw.get("second", False):
        _layer(img, lambda dd: dd.line(poly + [poly[0]], fill=tuple(ink2) + (200,),
                                       width=max(1, E.px(pad * 0.4)), joint="curve"))
    return E.grain(img, rng, uneven=0.04, holes=0)


@E.element("pixel_icon", "retro_ui", ("E",), (24, 120, 24, 120),
           "像素图标：8×8 或 16×16，folder / disk / star / heart")
def el_pixel_icon(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    kind = kw.get("kind") or rng.choice(["folder", "disk", "star", "heart"])
    art = PIXEL_ART.get(str(kind), PIXEL_ART["star"])
    res = 16 if int(kw.get("res", rng.choice([8, 16]))) >= 16 else 8
    grid = [list(row) for row in art]
    if res == 16:
        grid = [[c for c in row for _ in (0, 1)] for row in grid]
        grid = [row for row in grid for _ in (0, 1)]
    for j in range(res):                         # 掉几个像素：老图标不会这么干净
        for i in range(res):
            r = rng.random()
            if grid[j][i] == "0" and r < 0.015:
                grid[j][i] = "1"
            elif grid[j][i] == "1" and r < 0.030:
                grid[j][i] = "2"
            elif grid[j][i] == "2" and r < 0.030:
                grid[j][i] = "1"
    cell = max(1, E.px(min(w, h)) // res)
    ox = (img.width - cell * res) // 2
    oy = (img.height - cell * res) // 2
    cols = {"1": ink, "2": ink2}
    for j in range(res):
        for i in range(res):
            c = grid[j][i]
            if c == "0":
                continue
            d.rectangle([ox + i * cell, oy + j * cell,
                         ox + (i + 1) * cell, oy + (j + 1) * cell],
                        fill=tuple(cols[c]) + (255,))
    return img


@E.element("progress_bar", "retro_ui", ("E",), (80, 340, 20, 54),
           "进度条：外框 + 分段填充 + 百分比文字")
def el_progress_bar(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    d = ImageDraw.Draw(img)
    value = max(0.0, min(1.0, float(kw.get("value", rng.uniform(0.35, 0.92)))))
    lab = str(kw.get("label", f"{int(round(value * 100))}%"))
    ltile, _ls = _fit_tile(lab, "Arial Black", h * 0.62, ink, w * 0.26, 3.2)
    gap = max(1.8, w * 0.030)
    bw = max(10.0, w - ltile.width / E.SCALE - gap)
    t = max(1.0, h * 0.10)
    d.rectangle([0, 0, E.px(bw), img.height - 1], outline=tuple(ink) + (255,),
                width=max(1, E.px(t)))
    inner_x, inner_y = 2 * t, 2 * t
    iw, ih = bw - 4 * t, h - 4 * t
    if iw > 3 and ih > 1.5:
        segs = max(4, int(iw / max(3.2, h * 0.34)))
        filled = int(round(segs * value))
        sw = iw / segs
        for i in range(segs):
            x0 = inner_x + i * sw
            col = ink if i < filled else ink2
            d.rectangle(_box(x0 + sw * 0.12, inner_y, x0 + sw * 0.88, inner_y + ih),
                        fill=tuple(col) + (255 if i < filled else 60,))
    img.alpha_composite(ltile, (int(E.px(bw + gap)),
                                int((img.height - ltile.height) / 2)))
    return E.grain(img, rng, uneven=0.05, holes=0)


@E.element("dialog_box", "retro_ui", ("E",), (110, 420, 80, 300),
           "弹窗对话框：标题栏 + 正文线 + 两个按钮 + 投影")
def el_dialog_box(ink, ink2, paper, size, rng, **kw):
    w, h = size
    img = E.canvas(w, h)
    off = max(1.5, min(w, h) * 0.022)

    def shadow(dd):
        dd.rectangle([E.px(off), E.px(off), img.width - 1, img.height - 1],
                     fill=tuple(ink2) + (70,))
    _layer(img, shadow)
    d = ImageDraw.Draw(img)
    lwpt = max(0.9, min(w, h) * 0.012)
    lw = max(1, int(round(E.px(lwpt))))
    d.rectangle([0, 0, img.width - 1, img.height - 1], fill=tuple(paper) + (255,))
    d.rectangle([0, 0, img.width - 1, img.height - 1], outline=tuple(ink) + (255,), width=lw)
    th = max(8.0, min(h * 0.19, 20.0))
    d.rectangle([lw, lw, img.width - 1 - lw, E.px(th)], fill=tuple(ink) + (255,))
    title = str(kw.get("title", "PRINT.JOB"))
    ttile, _ts = _fit_tile(title, "Arial", th * 0.62, paper, w - 3 * lwpt - 6.0, 3.2)
    img.alpha_composite(ttile, (int(E.px(lwpt + 2.5)),
                                int(E.px(th / 2) - ttile.height / 2)))
    labels = list(kw.get("buttons", ("OK", "CANCEL")))
    btn_h = max(6.0, min(h * 0.21, 18.0))
    btn_y = h - lwpt - btn_h - max(2.0, h * 0.06)
    body_top = th + max(2.5, h * 0.07)
    body_bot = max(body_top + 3.0, btn_y - max(2.0, h * 0.05))
    rows = max(2, int((body_bot - body_top) / max(4.0, h * 0.11)))
    for i in range(rows):
        y = body_top + i * (body_bot - body_top) / rows
        ln = (w - 2 * lwpt - 6.0) * (0.55 + 0.42 * rng.random())
        d.rectangle(_box(lwpt + 3.0, y, lwpt + 3.0 + ln, y + max(1.0, h * 0.014)),
                    fill=tuple(ink) + (140,))
    x = w - lwpt - max(3.0, w * 0.035)
    for lab in reversed(labels):
        bs = E.fit_text(lab, "Arial", btn_h * 0.58, w * 0.30, 3.0)
        bwid = max(btn_h * 1.7, tm.advance(lab, "Arial", bs) + btn_h * 0.9)
        x -= bwid
        if x < lwpt + 2.0:
            break
        d.rectangle(_box(x, btn_y, x + bwid, btn_y + btn_h), outline=tuple(ink) + (255,),
                    width=max(1, E.px(0.9)))
        tile = E.text_image(lab, "Arial", bs, ink)
        img.alpha_composite(tile, (int(E.px(x + bwid / 2) - tile.width / 2),
                                   int(E.px(btn_y + btn_h / 2) - tile.height / 2)))
        x -= max(2.0, w * 0.02)
    return E.grain(img, rng, uneven=0.05, holes=0)


# --------------------------------------------------------------- module API
# This module does NOT keep a registry of its own — E.element has already filled
# the one in elements.py, and everything below is a view onto that same dict.
# The alias exists so that elements.register_module(elements_b) finds the entries
# on the documented integration path: when elements.py runs as a script it is
# `__main__`, so `import elements` here pulls in a *second* copy of it, and the
# registrations land in that copy. (elements.load_siblings() merges the same
# second copy back for the CLI; this alias keeps the direct call honest too.)
REGISTRY = E.REGISTRY

# The elements defined in this file (elements.py's functions report a different
# __module__, so this stays stable however the module was imported).
OWN_ELEMENTS = tuple(sorted(m["name"] for m in E.REGISTRY.values()
                            if m["fn"].__module__ == __name__))


def own():
    """Metadata for the elements this module registers, in catalogue order."""
    return [E.REGISTRY[n] for n in OWN_ELEMENTS]


def _selftest():
    """Render every element here at its min and at its max size.

    A generator that returns an empty image, or a picture made of a couple of
    stray pixels, is broken however good it looks in the one size the author
    happened to try — and the composer picks sizes from the whole declared range.
    """
    import numpy as np
    ink, ink2, paper = (215, 38, 30), (30, 30, 30), (239, 231, 216)
    bad = []
    for i, meta in enumerate(own()):
        lo_w, hi_w, lo_h, hi_h = meta["size"]
        for tag, size in (("min", (lo_w, lo_h)), ("max", (hi_w, hi_h))):
            rng = random.Random(9000 + i)
            img = meta["fn"](ink, ink2, paper, size, rng)
            assert img is not None and img.mode == "RGBA", \
                f"{meta['name']} [{tag}] did not return an RGBA image"
            assert (img.width, img.height) == (E.px(size[0]), E.px(size[1])), \
                f"{meta['name']} [{tag}] wrong canvas size {img.size}"
            a = np.asarray(img.getchannel("A"))
            frac = float((a > 100).sum()) / float(a.size)
            if frac <= 0.005:
                bad.append(f"{meta['name']} [{tag}] {size} only {frac * 100:.2f}% ink")
    assert not bad, "empty or near-empty renders:\n  " + "\n  ".join(bad)
    print(f"elements_b selftest: {len(OWN_ELEMENTS)} elements ok")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
