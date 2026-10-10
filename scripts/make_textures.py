#!/usr/bin/env python3
"""make_textures.py — riso-slides background texture generator.

Generates riso-style page backgrounds: paper grain, overprint circles (multiply),
45-degree halftone dot fields, registration marks. Also converts photos into
two-ink duotone halftone images.

Commands
--------
  bg        generate one image per page
  duotone   convert a photo into a two-ink halftone image
  selftest  regression tests for the four bugs this file has fixed

Per-page control
----------------
Each page's pattern is chosen explicitly, so no deck length produces a silent
repeat and a dot field can be aimed at a specific corner — the style spec's own
rule ("网点只出现在页面边角或空白处，绝不压在正文后面") depends on that. Three
levels of control:

  1. automatic       nothing passed -> non-repeating, adjacent-distinct
  2. named patterns  --plan "1:circles_tr,4:reverse+dots_bl"
  3. explicit fields --plan-file plan.json  (exact centre / direction / radius)

Every page is seeded independently, so adding or reordering a page never
re-textures the others; --manifest writes a machine-readable record (spec,
sha256, byte size, ink bbox, dot centroid) that qa.py verifies.

Output size
-----------
The grain is high-entropy noise: PNG cannot compress it. A 1920x1080 page is
~1.8 MB as PNG and ~0.4 MB as JPEG q90, with no visible difference at
projection size. JPEG is therefore the default.
"""
import argparse
import hashlib
import json
import math
import os
import random
import sys
sys.dont_write_bytecode = True
from canvas import DECK_CANVAS

import numpy as np
from PIL import Image, ImageDraw, ImageChops, ImageFilter

PALETTES = {
    # name: (paper, inkA, inkB, ink, accent1, accent2)
    "A": ("#F2EBDA", "#0F5A3C", "#2E8B5E", "#2B2B2B", "#E8B923", "#C2441C"),
    "B": ("#F4EFE6", "#2F4BD8", "#FF5FA2", "#1F1F2E", "#FFD93B", "#7FD6B5"),
    "C": ("#F3E9D8", "#FF6C2F", "#1D2A5B", "#20232E", "#F5C518", "#2FA7A0"),
    "D": ("#F4EEE2", "#0E8C8C", "#FF6F59", "#22303C", "#F2C14E", "#0A5F63"),
    "E": ("#F6ECE3", "#7A1F3D", "#F28CB1", "#2A1F24", "#E0A526", "#C8442F"),
    "F": ("#EFE8DC", "#5B2A86", "#FF7A1A", "#1E1A26", "#FFD21F", "#FF8FB8"),
    "G": ("#EFE7D8", "#D7261E", "#1E1E1E", "#1E1E1E", "#E8B923", "#5C6B7A"),
}


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(c):
    return "#%02X%02X%02X" % tuple(int(round(v)) for v in c)


def multiply(c1, c2):
    """Overprint: what you get when both inks hit the same spot."""
    return tuple(a * b / 255.0 for a, b in zip(c1, c2))


def blend(c1, c2, t):
    """Tint of c1 on c2 at coverage t (0 = c2, 1 = c1)."""
    return tuple(a * t + b * (1 - t) for a, b in zip(c1, c2))


class Ctx:
    """Render context: geometry + palette + derived inks."""

    def __init__(self, pw, ph, scale, palette):
        self.pw, self.ph, self.s = pw, ph, scale
        self.W, self.H = int(pw * scale), int(ph * scale)
        (self.paper, self.inkA, self.inkB, self.ink,
         self.acc1, self.acc2) = [hex2rgb(c) for c in palette]
        # Derived riso colours.
        #
        # The three-layer title stack is defined in terms of ink A only, never
        # as "deep ink / light ink / charcoal": that reading is unbuildable in
        # any palette whose second ink is the ink black (G: inkB == ink),
        # because there is no lighter ink to put in the middle. Ink A works for
        # every palette:  back = ink_deep (ink A pushed toward the ink black),
        #                 middle = inkA (the identity colour), front = ink.
        self.inkAB = multiply(self.inkA, self.inkB)     # texture / overprint areas
        self.ink_deep = blend(self.inkA, self.ink, 0.45)  # type stack, back layer
        self.tintA = blend(self.inkA, self.paper, 0.45)   # wash / low-emphasis ink A
        self.tintB = blend(self.inkB, self.paper, 0.28)

    def u(self, v):
        return int(round(v * self.s))

    def tokens(self):
        return {
            "paper": rgb2hex(self.paper), "inkA": rgb2hex(self.inkA),
            "inkB": rgb2hex(self.inkB), "ink": rgb2hex(self.ink),
            "accent1": rgb2hex(self.acc1), "accent2": rgb2hex(self.acc2),
            "inkAB": rgb2hex(self.inkAB), "ink_deep": rgb2hex(self.ink_deep),
            "tintA": rgb2hex(self.tintA), "tintB": rgb2hex(self.tintB),
        }


def seed_for(base_seed, page):
    """Independent per-page seed: page N never depends on page N-1."""
    return base_seed * 1000003 + page * 7919


def reseed(base_seed, page):
    s = seed_for(base_seed, page)
    random.seed(s)
    np.random.seed(s % (2 ** 32))


def paper_base(ctx, color=None):
    color = color or ctx.paper
    img = Image.new("RGB", (ctx.W, ctx.H), color)
    arr = np.array(img).astype(np.int16)
    arr = arr + np.random.normal(0, 5.5, (ctx.H, ctx.W, 1))
    low = np.random.normal(0, 1, (ctx.H // 12, ctx.W // 12))
    low_img = Image.fromarray(
        ((low - low.min()) / (np.ptp(low) + 1e-9) * 255).astype(np.uint8)
    ).resize((ctx.W, ctx.H), Image.BILINEAR)
    arr = arr + ((np.array(low_img).astype(np.int16) - 128) * 0.045)[:, :, None]
    flecks = np.random.random((ctx.H, ctx.W)) < 0.0006
    arr[flecks] = arr[flecks] - 26
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def quiet_plate(image, regions, color, seed, page_size=(960, 540)):
    """Wash texture away only behind measured chrome; keep seeded paper grain.

    Regions are in canvas points. This creates a derived background and never
    alters source artwork. Its local noise generator cannot affect decoration.
    """
    sx, sy = image.width / page_size[0], image.height / page_size[1]
    mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(mask)
    for x0, y0, x1, y1 in regions:
        draw.rectangle(((x0-9)*sx, (y0-9)*sy, (x1+9)*sx, (y1+9)*sy), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(3*min(sx, sy)))
    noise = np.random.default_rng(seed).normal(0, 5.5, (image.height, image.width, 1))
    flat = Image.fromarray(np.clip(np.array(color)+noise, 0, 255).astype('uint8'))
    return Image.composite(flat, image.convert('RGB'), mask)


def overprint_circle(ctx, base, cx, cy, r, color):
    mask = Image.new("L", (ctx.W, ctx.H), 0)
    d = ImageDraw.Draw(mask)
    pts = []
    for a in range(0, 360, 2):
        rr = ctx.u(r) + random.uniform(-1.2, 1.2) * ctx.s
        rad = math.radians(a)
        pts.append((ctx.u(cx) + rr * math.cos(rad), ctx.u(cy) + rr * math.sin(rad)))
    d.polygon(pts, fill=255)
    m = np.array(mask).astype(np.float32) / 255.0
    m = m * np.clip(np.random.normal(1.0, 0.05, (ctx.H, ctx.W)), 0.75, 1.0)
    holes = np.random.random((ctx.H, ctx.W)) < 0.0012
    m[holes] = m[holes] * 0.35
    mask = Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8))
    solid = Image.new("RGB", (ctx.W, ctx.H), color)
    base.paste(ImageChops.multiply(base, solid), (0, 0), mask)


def halftone(ctx, base, cx, cy, n, spacing, r_max, color, dirx, diry, falloff,
             jitter=0.25, alpha=255, radius=None):
    """45-degree dot field.

    Dots are dense at (cx, cy) and fade along (dirx, diry) over `falloff`. The
    falloff is radial as well as directional, so nothing *behind* the centre can
    sit at full density (a half-plane would flood the page). `radius` bounds it
    into a blob.
    """
    overlay = Image.new("RGBA", (ctx.W, ctx.H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    sq2 = math.sqrt(2)
    norm = math.hypot(dirx, diry) or 1.0
    dirx, diry = dirx / norm, diry / norm
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x = cx + (i - j) * spacing / sq2
            y = cy + (i + j) * spacing / sq2
            if x < -r_max or x > ctx.pw + r_max or y < -r_max or y > ctx.ph + r_max:
                continue
            t = ((x - cx) * dirx + (y - cy) * diry) / falloff
            k = max(0.0, min(1.0, 1.0 - t))
            if radius is not None:
                k *= max(0.0, min(1.0, 1.0 - math.hypot(x - cx, y - cy) / radius))
            r = r_max * (k ** 0.75) * (1 + random.uniform(-jitter, jitter))
            if r < 0.5:
                continue
            X, Y, R = ctx.u(x), ctx.u(y), ctx.u(r)
            d.ellipse([X - R, Y - R, X + R, Y + R], fill=tuple(color) + (int(alpha),))
    rgba = base.convert("RGBA")
    rgba.alpha_composite(overlay)
    return rgba.convert("RGB")


def registration_marks(ctx, base, color, geometry=None):
    d = ImageDraw.Draw(base)
    inset, radius, arm = geometry or DECK_CANVAS.registration
    r, off = ctx.u(radius), ctx.u(inset)
    lw = max(2, ctx.u(1.1))
    for cx, cy in [(off, off), (ctx.W - off, off), (off, ctx.H - off), (ctx.W - off, ctx.H - off)]:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=lw)
        ext = ctx.u(arm)
        d.line([cx - r - ext, cy, cx + r + ext, cy], fill=color, width=lw)
        d.line([cx, cy - r - ext, cx, cy + r + ext], fill=color, width=lw)


# --- named patterns (page-unit coordinates assume 960x540; scaled if different) ---
# Each returns None (drew in place) or a new image. cmd_bg must always keep the
# return value, or a reversed page comes out blank.

def _pat_circles_tr(ctx, b, A, B):
    overprint_circle(ctx, b, ctx.pw + 45, -35, 205, B)
    overprint_circle(ctx, b, ctx.pw - 80, -60, 135, A)


def _pat_dots_bl(ctx, b, A, B):
    return halftone(ctx, b, 20, ctx.ph + 35, 28, 13, 6.2, B, 1, -0.75, 300, alpha=160)


def _pat_minimal(ctx, b, A, B):
    return halftone(ctx, b, -10, -10, 16, 13, 4.2, B, 1, 1, 170, alpha=70)


def _pat_circles_r(ctx, b, A, B):
    overprint_circle(ctx, b, ctx.pw + 50, ctx.ph * 0.55, 215, B)
    overprint_circle(ctx, b, ctx.pw - 55, ctx.ph * 0.32, 130, A)
    return halftone(ctx, b, 40, ctx.ph, 22, 12, 5.0, B, 1, -0.8, 230, alpha=150)


def _pat_band(ctx, b, A, B):
    return halftone(ctx, b, ctx.pw * 0.3, ctx.ph * 0.85, 24, 13, 5.4, B, 1, -0.5, 260, alpha=120)


def _pat_circles_l(ctx, b, A, B):
    overprint_circle(ctx, b, -55, ctx.ph * 0.6, 200, A)
    overprint_circle(ctx, b, 55, ctx.ph * 0.3, 120, B)
    return halftone(ctx, b, ctx.pw - 20, 40, 20, 12, 4.6, B, -0.7, 1, 190, alpha=130)


def _pat_dots_tr(ctx, b, A, B):
    return halftone(ctx, b, ctx.pw - 60, 60, 16, 12, 4.4, B, -1, 0.6, 160, alpha=90)


def _pat_circles_bl(ctx, b, A, B):
    overprint_circle(ctx, b, -40, ctx.ph + 30, 190, B)
    overprint_circle(ctx, b, 120, ctx.ph - 60, 120, A)


def _pat_dots_br(ctx, b, A, B):
    return halftone(ctx, b, ctx.pw - 10, ctx.ph + 30, 24, 13, 5.8, B, -1, -0.7, 230, alpha=150)


PATTERNS = [_pat_circles_tr, _pat_dots_bl, _pat_minimal, _pat_circles_r, _pat_band,
            _pat_circles_l, _pat_dots_tr, _pat_circles_bl, _pat_dots_br]
PATTERN_NAMES = {p.__name__.replace("_pat_", ""): p for p in PATTERNS}


def auto_sequence(pages, seed):
    """Non-repeating, adjacent-distinct pattern sequence of any length."""
    rnd = random.Random(seed)
    seq = []
    while len(seq) < pages:
        block = list(range(len(PATTERNS)))
        rnd.shuffle(block)
        if seq and block[0] == seq[-1]:
            block[0], block[1] = block[1], block[0]
        seq.extend(block)
    return [PATTERNS[i] for i in seq[:pages]]


# ---------------------------------------------------------------------------
# Calibrated field presets.
#
# These are the dot-field / overprint-circle recipes that were tuned by hand
# against real renders and then frozen here. They exist so that a later run
# never has to look at a finished deck, a reference poster or a previous output
# to know "how dense should this corner fade be" — the answer is in the skill.
# Values are in page points; see references/design-system.md for the catalogue
# and for which page archetype each one suits.
# ---------------------------------------------------------------------------
FIELD_PRESETS = {
    "cover-bleed-tr": dict(
        circles=[[1120, -70, 250, "B"], [975, -105, 155, "A"]],
        note="封面：两枚叠印圆自右上角出血"),
    "cover-bleed-bl": dict(
        circles=[[-80, 630, 240, "B"], [70, 575, 130, "A"]],
        note="封面变体：左下角出血，封面正文止于 y≈365 时可用"),
    "corner-fade-br": dict(
        field=dict(c=[1030, 585], dir=[-1, -0.70], f=230, sp=13, rm=5.8, a=150),
        note="数据页：右下角大颗粒渐隐，左重版式"),
    "corner-fade-bl-sm": dict(
        field=dict(c=[-60, 570], dir=[1, -1.0], f=200, sp=13, rm=4.6, a=100),
        note="数据页：左下角小渐隐，右重版式"),
    "corner-fade-tr-sm": dict(
        field=dict(c=[1010, 0], dir=[-1, 0.80], f=170, sp=12, rm=4.6, a=110),
        note="列表/占比页：右上角细密点，避开中部图表"),
    "corner-fade-tr-xs": dict(
        field=dict(c=[1010, -55], dir=[-1, 1.0], f=200, sp=12, rm=4.6, a=95),
        note="引语页：右上角极轻点，几乎只是纸纹"),
    "corner-speckle-tr": dict(
        field=dict(c=[980, 10], dir=[-1, 0.60], f=150, sp=11, rm=4.6, a=100),
        note="表格/对比页：只占右上角一小块，页面主体保持干净"),
    "edge-fade-left": dict(
        field=dict(c=[-100, 320], dir=[1, 0.0], f=170, sp=12, rm=4.8, a=120),
        note="图解页：左边缘一条墨迹，配合右侧留白"),
    "edge-fade-right": dict(
        field=dict(c=[1050, 430], dir=[-1, -0.30], f=200, sp=12, rm=5.0, a=130),
        note="风险页：右边缘下半段渐隐，避开左侧大数字"),
    "band-bottom": dict(
        field=dict(c=[700, 565], dir=[0.0, -1.0], f=140, sp=12, rm=4.6, a=110),
        note="占比/条形页：沿底边积墨，正文止于 y≈400 时可用"),
    "blob-corner-tl": dict(
        field=dict(c=[-70, -70], dir=[1, 1.0], f=170, sp=12, rm=4.8, a=115,
                   radius=260),
        note="通用：左上角有界斑点（radius 保证不铺满整页）"),
    "blob-corner-br": dict(
        field=dict(c=[980, 560], dir=[-1, -1.0], f=200, sp=13, rm=5.4, a=130,
                   radius=300),
        note="通用：右下角有界斑点"),
    "reverse-blob-bl": dict(
        field=dict(c=[200, 480], dir=[1, -1.0], f=200, sp=13, rm=5.0, a=130),
        dot_ink="B",
        note="反白页：左下角墨点（点在油墨 A 底上用油墨 B）"),
    "reverse-circle-br": dict(
        circles=[[1050, 620, 250, "B"], [930, 570, 150, "#7E1610"]],
        note="反白章节页：右下角黑圆出血 + 叠印深红"),
    "reverse-circle-tr": dict(
        circles=[[1180, -70, 230, "B"], [1050, -120, 130, "#7E1610"]],
        note="反白结尾页：右上角黑圆出血 + 叠印深红"),
}

RECOMMENDED_PRESET = {
    "cover": ("cover-bleed-tr", "cover-bleed-bl"),
    "divider": ("reverse-circle-br", "reverse-blob-bl"),
    "closing": ("reverse-circle-tr",),
    "data": ("corner-fade-br", "corner-fade-bl-sm"),
    "features": ("corner-fade-tr-sm", "band-bottom"),
    "quote": ("corner-fade-tr-xs",),
    "grid": ("corner-speckle-tr",),
    "venn": ("edge-fade-left", "blob-corner-tl"),
    "numbered": ("edge-fade-right", "corner-fade-bl-sm"),
    "timeline": ("blob-corner-tl", "band-bottom"),
    "ask": ("corner-speckle-tr", "blob-corner-br"),
    "statement": ("cover-bleed-bl", "blob-corner-br"),
}


def expand_presets(spec):
    """Merge named presets into a page spec (explicit keys win)."""
    names = spec.pop("presets", None)
    if not names and spec.get("preset"):
        names = [spec.pop("preset")]
    if not names:
        return spec
    merged = {}
    for n in names:
        if n not in FIELD_PRESETS:
            raise SystemExit(f"unknown preset {n!r}; run `presets` to list them")
        for k, v in FIELD_PRESETS[n].items():
            if k != "note":
                merged[k] = v
    merged.update(spec)          # explicit keys override the preset
    return merged



def ink_mask(img, threshold=25, median=3):
    """Boolean ink mask, robust to paper grain.

    A raw per-pixel distance from the paper colour is dominated by the grain
    (every page "has ink" everywhere), so the difference image is median
    filtered first. That keeps dots (>= 2 px) and drops single-pixel noise.
    """
    from PIL import ImageFilter
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    paper = np.median(a.reshape(-1, 3), axis=0)
    diff = np.clip(np.abs(a - paper).sum(axis=2), 0, 255).astype(np.uint8)
    d = Image.fromarray(diff)
    if median:
        d = d.filter(ImageFilter.MedianFilter(median))
    return np.asarray(d) > threshold


def ink_stats(img, margin=0, threshold=25, grid=(4, 6), page_width=None):
    """Ink bbox / centroid (page points), density grid, texture strength.

    `margin` (page points) blanks a frame before measuring so callers can ignore
    the registration marks the generator always draws. `grid` returns ink
    coverage per cell of a rows x cols lattice — qa.py uses it to tell a dot
    field that sits in a corner from one that floods the page, and to check that
    no field lands under body copy.
    """
    page_width = page_width or DECK_CANVAS.width
    mask = ink_mask(img, threshold)
    h, w = mask.shape
    if margin:
        m = int(round(margin * w / page_width))
        mask[:m, :] = False
        mask[-m:, :] = False
        mask[:, :m] = False
        mask[:, -m:] = False
    rows, cols = grid
    density = [[round(float(mask[r * h // rows:(r + 1) * h // rows,
                                c * w // cols:(c + 1) * w // cols].mean()), 4)
                for c in range(cols)] for r in range(rows)]
    out = {"ink_fraction": round(float(mask.mean()), 4), "density": density}
    if not mask.any():
        out.update({"ink_pixels": 0, "ink_bbox": None, "ink_centroid": None})
        out["std"] = round(float(np.asarray(img.convert("RGB")).std()), 2)
        return out
    ys, xs = np.where(mask)
    px_pt = w / page_width
    out.update({
        "ink_pixels": int(mask.sum()),
        "ink_bbox": [round(xs.min() / px_pt, 1), round(ys.min() / px_pt, 1),
                     round(xs.max() / px_pt, 1), round(ys.max() / px_pt, 1)],
        "ink_centroid": [round(xs.mean() / px_pt, 1), round(ys.mean() / px_pt, 1)],
    })
    out["std"] = round(float(np.asarray(img.convert("RGB")).std()), 2)
    return out


def right_half_density(info):
    """Max ink coverage over the right-hand third of the density grid."""
    cols = len(info["density"][0]) if info.get("density") else 0
    if not cols:
        return 0.0
    return max(max(row[cols // 2:]) for row in info["density"])


def save_img(img, path, fmt, quality):
    fmt = (fmt or "jpg").lower()
    if fmt in ("jpg", "jpeg"):
        path = os.path.splitext(path)[0] + ".jpg"
        img.convert("RGB").save(path, quality=quality, optimize=True,
                                subsampling=1, progressive=True)
    else:
        path = os.path.splitext(path)[0] + ".png"
        img.save(path, optimize=True)
    return path


def parse_plan(text):
    """'1:preset:cover-bleed-tr,4:reverse+preset:reverse-circle-br' -> {1: {...}}"""
    plan = {}
    for chunk in (text or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        page_s, _, spec = chunk.partition(":")
        entry = {"reverse": False}
        for part in spec.split("+"):
            part = part.strip()
            if part == "reverse":
                entry["reverse"] = True
            elif part.startswith("preset:"):
                name = part.split(":", 1)[1]
                if name not in FIELD_PRESETS:
                    raise SystemExit(f"unknown preset {name!r}; "
                                     f"run `presets` to list them")
                entry.setdefault("presets", []).append(name)
            elif part in PATTERN_NAMES:
                entry["pattern"] = part
            else:
                raise SystemExit(f"unknown plan token {part!r} on page {page_s}")
        plan[int(page_s)] = entry
    return plan


def parse_plan_file(path):
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    plan = {}
    for k, v in raw.get("pages", raw).items():
        entry = dict(v)
        entry["reverse"] = bool(entry.get("reverse", False))
        plan[int(k)] = entry
    return plan


def render_page(ctx, spec, seed, page):
    reseed(seed, page)
    rev = spec.get("reverse", False)
    base = paper_base(ctx, ctx.inkA if rev else None)
    desc = []
    for c in spec.get("circles", []):
        cx, cy, r, col = c[0], c[1], c[2], c[3]
        # NB: .get(col, hex2rgb(col)) would evaluate hex2rgb eagerly and blow up
        # on the "A"/"B" shorthand. Branch explicitly.
        if col == "A":
            colour = ctx.inkA
        elif col == "B":
            colour = ctx.inkB
        else:
            colour = hex2rgb(col)
        overprint_circle(ctx, base, cx, cy, r, colour)
        desc.append(f"circle({cx},{cy},r{r},{col})")
    field = spec.get("field")
    if field:
        dot_colour = ctx.inkA if spec.get("dot_ink") == "A" else ctx.inkB
        base = halftone(ctx, base, field["c"][0], field["c"][1], field.get("n", 32),
                        field.get("spacing", 13), field.get("rmax", 5.0), dot_colour,
                        field["dir"][0], field["dir"][1], field.get("falloff", 200),
                        jitter=field.get("jitter", 0.25), alpha=field.get("alpha", 130),
                        radius=field.get("radius"))
        desc.append("field(%s)" % json.dumps(field, separators=(",", ":")))
    if spec.get("pattern"):
        fn = PATTERN_NAMES[spec["pattern"]]
        out = fn(ctx, base, ctx.inkB, ctx.inkB if rev else ctx.inkA)
        if out is not None:          # keep it: reversed pages depend on this
            base = out
        desc.append(f"pattern({spec['pattern']})")
    # rule E: chrome text zones are forbidden ground — even a bleeding corner
    # block must wash out where a header/footer label lives. Feathered, so the
    # paper grain survives and no hard rectangle edge appears.
    for q in spec.get("quiet_zones", []):
        x0, y0, x1, y1 = [ctx.u(v) for v in q]
        mask = Image.new("L", (ctx.W, ctx.H), 0)
        ImageDraw.Draw(mask).rectangle([x0, y0, x1, y1], fill=215)
        mask = mask.filter(ImageFilter.GaussianBlur(ctx.u(6)))
        flat = paper_base(ctx, ctx.inkA if rev else None)
        base = Image.composite(flat, base, mask)
        desc.append(f"quiet({q[0]},{q[1]})")
    if spec.get("registration_marks", True):
        registration_marks(ctx, base, ctx.paper if rev else ctx.ink,
                           spec.get("registration"))
    return base, ";".join(desc) or "paper"


def cmd_bg(args):
    palette = PALETTES[args.palette] if args.palette else args.colors.split(",")
    pw, ph = [float(v) for v in args.page_size.split("x")]
    ctx = Ctx(pw, ph, args.scale, palette)
    os.makedirs(args.out, exist_ok=True)

    if args.plan_file:
        plan = parse_plan_file(args.plan_file)
    elif args.plan:
        plan = parse_plan(args.plan)
    else:
        plan = {}
    reverse = set(args.reverse or [])
    auto = auto_sequence(args.pages, args.seed)
    # zones that must stay paper-quiet for the chosen chrome set (rule E)
    guard = {"full": [(40, 8, 640, 42), (240, 8, 925, 42), (560, 482, 925, 540)],
             "light": [(40, 8, 640, 42), (560, 482, 925, 540)],
             "none": []}.get(getattr(args, "chrome_set", None) or "none", [])
    if pw != DECK_CANVAS.width or ph != DECK_CANVAS.height:
        guard = [(x0*pw/DECK_CANVAS.width,y0*ph/DECK_CANVAS.height,
                  x1*pw/DECK_CANVAS.width,y1*ph/DECK_CANVAS.height)
                 for x0,y0,x1,y1 in guard]

    manifest = {"palette": args.palette or "custom", "tokens": ctx.tokens(),
                "seed": args.seed, "page_size": args.page_size, "scale": args.scale,
                "format": args.format, "pages": []}
    total_bytes = 0
    for page in range(1, args.pages + 1):
        raw = dict(plan.get(page, {}))
        used_presets = list(raw.get("presets") or ([raw["preset"]] if raw.get("preset") else []))
        spec = expand_presets(raw)
        if not (spec.get("pattern") or spec.get("field") or spec.get("circles")
                or spec.get("paper_only")):
            spec["pattern"] = auto[page - 1].__name__.replace("_pat_", "")
        if page in reverse:
            spec["reverse"] = True
        if guard:
            spec["quiet_zones"] = list(spec.get("quiet_zones") or []) + guard
        img, desc = render_page(ctx, spec, args.seed, page)
        path = save_img(img, os.path.join(args.out, f"bg{page}"), args.format, args.quality)
        blob = open(path, "rb").read()
        total_bytes += len(blob)
        entry = {"page": page, "file": os.path.basename(path),
                 "reversed": bool(spec.get("reverse")), "spec": desc,
                 "presets": used_presets,
                 "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()[:16]}
        entry.update(ink_stats(img, page_width=pw))
        manifest["pages"].append(entry)
        print(f"bg{page:>2} {os.path.basename(path):<9} {desc}")

    manifest["total_bytes"] = total_bytes
    if args.manifest:
        with open(args.manifest, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
        print(f"manifest -> {args.manifest}")
    print(f"seed={args.seed} palette={args.palette or 'custom'} pages={args.pages} "
          f"total={total_bytes/1e6:.2f} MB")
    if total_bytes > 8e6:
        print("warning: backgrounds exceed 8 MB — use --format jpg --quality 90 "
              "or --scale 1.5", file=sys.stderr)
    return 0


def paper_base_for(ctxless, color):
    w, h = ctxless
    img = Image.new("RGB", (w, h), color)
    arr = np.array(img).astype(np.int16)
    arr = arr + np.random.normal(0, 5.0, (h, w, 1))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def cmd_duotone(args):
    palette = PALETTES[args.palette] if args.palette else args.colors.split(",")
    paper, inkA, inkB = hex2rgb(palette[0]), hex2rgb(palette[1]), hex2rgb(palette[2])
    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)
    img = Image.open(args.infile).convert("L")
    w, h = img.size
    k = args.max_dim / max(w, h)
    if k < 1:
        img = img.resize((int(w * k), int(h * k)), Image.LANCZOS)
    w, h = img.size
    out = paper_base_for(ctxless=(w, h), color=paper)
    d = ImageDraw.Draw(out)
    # Pitch is expressed as cells across the long edge, so dot size stays fixed
    # while --max-dim changes the output resolution.
    spacing = max(4.0, max(w, h) / float(args.cells))
    sq2 = math.sqrt(2)
    steps = int((w + h) / spacing / sq2) + 2
    for i in range(-2, steps):
        for j in range(-2, steps):
            x = (i - j) * spacing / sq2
            y = (i + j) * spacing / sq2
            if x < 0 or x >= w or y < 0 or y >= h:
                continue
            dark = 1 - img.getpixel((int(x), int(y))) / 255.0
            rA = spacing * 0.62 * (dark ** 1.1)
            rB = spacing * 0.40 * max(0.0, dark - 0.55)
            if rA > 0.6:
                d.ellipse([x - rA, y - rA, x + rA, y + rA], fill=inkA)
            if rB > 0.6:
                d.ellipse([x - rB, y - rB, x + rB, y + rB], fill=inkB)
    path = save_img(out, args.out, args.format, args.quality)
    print(f"duotone -> {path} ({w}x{h}, spacing={spacing:.1f}px, "
          f"{os.path.getsize(path)/1e6:.2f} MB)")
    return 0


def _bg_ns(out, pages, **kw):
    base = dict(out=out, pages=pages, palette="G", colors=None, seed=1, reverse=[],
                plan_file=None, plan=None, page_size="960x540", scale=1,
                format="png", quality=90, manifest=None)
    base.update(kw)
    return argparse.Namespace(**base)


def cmd_selftest(args):
    """Regression tests for the four bugs this file has fixed."""
    import tempfile
    from contextlib import redirect_stdout
    import io

    tmp = tempfile.mkdtemp(prefix="riso_selftest_")
    failures = []

    def check(name, ok, detail=""):
        print(f"  [{'ok' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    def quiet(fn, *a, **kw):
        with redirect_stdout(io.StringIO()):
            return fn(*a, **kw)

    print("make_textures selftest")

    # 1. reversed page + halftone field must NOT be blank
    plan = {"pages": {"1": {"reverse": True,
                            "field": {"c": [200, 480], "dir": [1, -1], "falloff": 200,
                                      "spacing": 13, "rmax": 5.0, "alpha": 130}}}}
    pf = os.path.join(tmp, "plan.json")
    json.dump(plan, open(pf, "w"))
    out = os.path.join(tmp, "rev")
    quiet(cmd_bg, _bg_ns(out, 1, plan_file=pf, reverse=[1]))
    st = ink_stats(Image.open(os.path.join(out, "bg1.png")))
    check("reversed page keeps its halftone field", st["std"] > 3.0,
          f"std={st['std']} (~1.0 means a flat red page)")

    # 2. no duplicate textures at any length
    out2 = os.path.join(tmp, "seq")
    quiet(cmd_bg, _bg_ns(out2, 12, seed=7))
    hashes = [hashlib.sha256(open(os.path.join(out2, f"bg{i}.png"), "rb").read()).hexdigest()
              for i in range(1, 13)]
    check("12-page deck has no duplicate page texture", len(set(hashes)) == 12,
          f"{len(set(hashes))}/12 unique")

    # 3. per-page seeding: adding pages must not re-texture earlier ones
    quiet(cmd_bg, _bg_ns(tmp + "/grow6", 6, seed=7))
    quiet(cmd_bg, _bg_ns(tmp + "/grow8", 8, seed=7))
    same = all(
        hashlib.sha256(open(os.path.join(tmp + "/grow6", f"bg{i}.png"), "rb").read()).hexdigest()
        == hashlib.sha256(open(os.path.join(tmp + "/grow8", f"bg{i}.png"), "rb").read()).hexdigest()
        for i in range(1, 7))
    check("growing the deck does not re-texture earlier pages", same)

    # 4. jpeg size budget for grain
    out4 = os.path.join(tmp, "size")
    quiet(cmd_bg, _bg_ns(out4, 2, seed=3, scale=2, format="jpg"))
    jpg = sum(os.path.getsize(os.path.join(out4, f)) for f in os.listdir(out4))
    check("jpeg backgrounds under 600 KB/page at 2x", jpg / 2 < 600_000,
          f"{jpg/2/1000:.0f} KB/page")

    # 5. manifest is machine-readable
    mf = os.path.join(tmp, "m.json")
    quiet(cmd_bg, _bg_ns(tmp + "/man", 2, seed=3, format="jpg", manifest=mf))
    man = json.load(open(mf))
    check("manifest records spec + sha256 + ink box per page",
          len(man["pages"]) == 2 and all(
              p.get("sha256") and p.get("ink_bbox") and p.get("spec")
              for p in man["pages"]))

    # 6. derived tokens exist (the colours the three-layer stack needs)
    ctx = Ctx(960, 540, 1, PALETTES["G"])
    check("derived ink_deep / inkAB / tintA tokens",
          ctx.ink_deep not in (ctx.inkA, ctx.inkB) and ctx.inkAB not in (ctx.inkA, ctx.inkB),
          f"ink_deep={rgb2hex(ctx.ink_deep)} inkAB={rgb2hex(ctx.inkAB)} "
          f"tintA={rgb2hex(ctx.tintA)}")

    # 7. a bounded blob field really is bounded (no half-plane flood)
    out7 = os.path.join(tmp, "blob")
    plan7 = {"pages": {"1": {"field": {"c": [100, 100], "dir": [1, 1], "falloff": 400,
                                         "radius": 120, "spacing": 11, "rmax": 5.0,
                                         "alpha": 160}}}}
    pf7 = os.path.join(tmp, "blob.json")
    json.dump(plan7, open(pf7, "w"))
    quiet(cmd_bg, _bg_ns(out7, 1, plan_file=pf7))
    info = ink_stats(Image.open(os.path.join(out7, "bg1.png")), margin=40)
    check("field radius bounds the dot field",
          info["density"][0][0] > 0.15 and right_half_density(info) < 0.05,
          f"near cell {info['density'][0][0]}, right half max "
          f"{right_half_density(info)} (same seed without radius "
          f"reaches ~0.37)")

    # 8. circle shorthand and explicit hex both work (an eager .get() default
    #    would raise on the "A"/"B" shorthand)
    out8 = os.path.join(tmp, "circ")
    plan8 = {"pages": {"1": {"circles": [[1200, -60, 240, "B"], [980, -90, 150, "A"],
                                        [300, 560, 140, "#7E1610"]]}}}
    pf8 = os.path.join(tmp, "circ.json")
    json.dump(plan8, open(pf8, "w"))
    quiet(cmd_bg, _bg_ns(out8, 1, plan_file=pf8))
    info8 = ink_stats(Image.open(os.path.join(out8, "bg1.png")))
    check("circle colours: A/B shorthand and hex", info8["ink_fraction"] > 0.02,
          f"ink fraction {info8['ink_fraction']}")

    print(f"\n{len(failures)} failure(s)" + (": " + ", ".join(failures) if failures else ""))
    return 1 if failures else 0


def cmd_presets(args):
    """List the calibrated field presets and which page archetype each suits."""
    if args.json:
        print(json.dumps(FIELD_PRESETS, ensure_ascii=False, indent=2))
        return 0
    rec = {}
    for arch, names in RECOMMENDED_PRESET.items():
        for n in names:
            rec.setdefault(n, []).append(arch)
    print(f"{len(FIELD_PRESETS)} calibrated field presets "
          f"(see references/design-system.md)\n")
    for name, spec in FIELD_PRESETS.items():
        kind = "circles" if spec.get("circles") else "field"
        print(f"  {name:<20} {kind:<8} {spec.get('note', '')}")
        if spec.get("field"):
            f = spec["field"]
            print(f"  {'':<20} centre={tuple(f['c'])} dir={tuple(f['dir'])} "
                  f"falloff={f['f']} spacing={f['sp']} rmax={f['rm']} "
                  f"alpha={f['a']}" + (f" radius={f['radius']}" if f.get("radius") else ""))
        if spec.get("circles"):
            print(f"  {'':<20} circles={spec['circles']}")
        if rec.get(name):
            print(f"  {'':<20} 适用页型: {', '.join(rec[name])}")
        print()
    return 0


def main():
    p = argparse.ArgumentParser(description="riso-slides texture generator")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--palette", choices=list(PALETTES), default=None,
                        help="palette name A-G (default A unless --colors)")
        sp.add_argument("--colors", default=None,
                        help="custom comma hexes: paper,inkA,inkB,ink,accent1,accent2")

    bg = sub.add_parser("bg", help="generate page backgrounds")
    common(bg)
    bg.add_argument("--out", required=True)
    bg.add_argument("--pages", type=int, required=True)
    bg.add_argument("--seed", type=int, default=42)
    bg.add_argument("--reverse", type=lambda s: [int(x) for x in s.split(",") if x],
                    default=[], help="1-based page numbers on an ink-A background")
    bg.add_argument("--plan", default=None,
                    help='inline per-page spec, e.g. "1:circles_tr,4:reverse+dots_bl"')
    bg.add_argument("--plan-file", dest="plan_file", default=None,
                    help="JSON per-page spec: circles / field / pattern / reverse / dot_ink")
    bg.add_argument("--manifest", default=None, help="write a JSON manifest here")
    bg.add_argument("--page-size", default="960x540")
    bg.add_argument("--scale", type=float, default=2)
    bg.add_argument("--format", default="jpg", choices=["png", "jpg"])
    bg.add_argument("--quality", type=int, default=90)
    bg.add_argument("--chrome-set", dest="chrome_set",
                    choices=["full", "light", "none"], default=None,
                    help="wash out the label zones of this chrome set (rule E)")
    bg.set_defaults(func=cmd_bg)

    duo = sub.add_parser("duotone", help="convert a photo to two-ink halftone")
    common(duo)
    duo.add_argument("--in", dest="infile", required=True)
    duo.add_argument("--out", required=True)
    duo.add_argument("--max-dim", type=int, default=1600)
    duo.add_argument("--cells", type=int, default=178,
                     help="halftone cells across the long edge (resolution independent)")
    duo.add_argument("--seed", type=int, default=None, help="reproducible grain")
    duo.add_argument("--format", default="jpg", choices=["png", "jpg"])
    duo.add_argument("--quality", type=int, default=90)
    duo.set_defaults(func=cmd_duotone)

    st = sub.add_parser("selftest", help="regression tests for the fixed bugs")
    st.set_defaults(func=cmd_selftest)

    pr = sub.add_parser("presets", help="list the calibrated field presets")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_presets)

    args = p.parse_args()
    if not hasattr(args, "palette"):
        return args.func(args)
    if not args.palette and not args.colors:
        args.palette = "A"
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
