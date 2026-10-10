#!/usr/bin/env python3
"""riso_kit — the riso-slides build layer.

Every deck would otherwise re-invent the same fragile pptx plumbing:
East-Asian typeface assignment, letter spacing, shape alpha, freeform lenses,
the three-layer misregistered title, the page chrome. That work is where styles
drift and where text silently falls back to the wrong font. It lives here now.

Everything is authored on a 960 x 540 pt grid (16:9, 13.333 x 7.5 in) — the same
grid make_textures.py rasterises.

Geometry is derived from the registration marks the generator draws (26 pt inset,
9 pt radius, 6 pt arms), so the header/footer rules can never collide with them.
"""
import sys
sys.dont_write_bytecode = True
import math
from canvas import DECK_CANVAS

from pptx import Presentation
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.oxml.ns import qn

import make_textures as mt
import textmetrics as tm

# ------------------------------------------------------------------ geometry
PAGE_W, PAGE_H = DECK_CANVAS.width, DECK_CANVAS.height
REGISTRATION = dict(zip(("inset", "radius", "arm"), DECK_CANVAS.registration))
_MARK_EDGE = REGISTRATION["inset"] + REGISTRATION["radius"] + REGISTRATION["arm"]
MARGIN_L = 48.0
MARGIN_R = PAGE_W - 48.0
HEAD_Y = 18.0                     # header label top
RULE_Y = 38.0                     # header rule
FOOT_RULE_Y = 486.0               # footer rule
FOOT_Y = 490.0                    # footer label top
SAFE = DECK_CANVAS.safe

# ------------------------------------------------------------------- text fit
# A text box declared `wrap=False` is NOT a no-wrap box in PowerPoint: PowerPoint
# still breaks the line at the box width, while `auto_size=NONE` keeps the frame
# height fixed, so the overflow lands on top of whatever is below. LibreOffice
# honours wrap=False and paints one long line, which is why the defect was
# invisible in the preview render. Every box that must stay on one line is sized
# from the measured line width here instead of from the design grid.
NO_WRAP = {
    "slack": 1.06,        # measure the renderer, then leave a little room
    "pad_pt": 8.0,        # plus an absolute floor, for wide-and-short strings
}

# ------------------------------------------------------------------ fonts
FONTS = {
    "display_latin": "Georgia",       # resolved by Theme's platform fallback chain
    "heading": "Microsoft YaHei",
    "body": "Noto Serif SC",
    "label_latin": "Georgia",
    "fallback_body": "SimSun",
    "fallback_heading": "SimHei",
}

ALIGN = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT,
         "j": PP_ALIGN.JUSTIFY}
ANCHOR = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}

_RPR_SEQ = ("a:ln", "a:noFill", "a:solidFill", "a:gradFill", "a:blipFill",
            "a:pattFill", "a:grpFill", "a:effectLst", "a:effectDag",
            "a:highlight", "a:uLnTx", "a:uLn", "a:uFillTx", "a:uFill",
            "a:latin", "a:ea", "a:cs", "a:sym", "a:hlinkClick",
            "a:hlinkMouseOver", "a:rtl", "a:extLst")

GRAMMAR_LEVELS = ("full", "light", "none")

# ---------------------------------------------------------------------------
# DESIGN — the frozen design system.
#
# Every number here was calibrated once, against real renders, and is now part
# of the skill. That is deliberate: a deck must not inherit the layout grammar
# of whatever reference image happened to be lying around. The calibration is
# done; the result lives here. Nothing in this skill may read an external design
# artifact to re-derive any of it.
#
# references/design-system.md is the human-readable form of this table, and
# `build_deck.py --design-system` prints it as JSON.
# ---------------------------------------------------------------------------
DESIGN = {
    "canvas": {"w": PAGE_W, "h": PAGE_H, "unit": "pt", "ratio": "16:9"},
    "registration": dict(REGISTRATION, content_boundary=_MARK_EDGE + 18),
    "grid": {
        "margin_left": MARGIN_L, "margin_right": MARGIN_R,
        "head_y": HEAD_Y, "rule_y": RULE_Y,
        "foot_rule_y": FOOT_RULE_Y, "foot_y": FOOT_Y,
        "safe": list(SAFE),
        "chrome_bands": list(DECK_CANVAS.chrome_bands),
    },
    "colour_roles": {
        # role -> token, and the share of the layout it should occupy
        "paper": ("paper", "55-65%"),
        "inkA": ("inkA", "10-20%  (身份色：大数字、条、贴纸、高亮旁注)"),
        "inkB": ("inkB", "5-12%   (次级条、几何图形)"),
        "ink_black": ("ink", "~10%   (线条、描边、墨点)"),
        "text": ("#2B2B2B", "炭黑正文色，永远不用纯黑"),
        "ink_deep": ("ink_deep", "三层错位最底层、维恩交叠区"),
        "inkAB": ("inkAB", "背景大面积叠印"),
        "accent1": ("accent1", "≤5%，只做高亮底色条"),
        "accent2": ("accent2", "≤2%，一根小条级别的点缀"),
    },
    "type_scale": {
        "display_xl": [100, 170, "大数字 / 海报级标题（错位 3 层）"],
        "display_l": [70, 100, "页面主标题（错位 3 层）"],
        "page_title": [26, 34, "页面标题（错位 2 层）"],
        "hero_label": [22, 27, "大数字下的说明"],
        "body": [17, 22, "正文（投影下限 17pt）"],
        "caption": [16, 17, "图注、脚注式说明"],
        "label": [12, 14, "页眉页脚、标签、编号（12pt 硬下限）"],
        "note": [13, 15, "括号旁注（斜体；中文用楷体不倾斜）"],
    },
    "misregistration": {
        # tier: (back offset, mid offset) in pt — back carries ink_deep, mid inkA
        "display_xl": [11.0, 5.5],
        "display_l": [8.0, 4.0],
        "display_m": [5.0, 2.5],
        "page_title": [3.0, 1.5],
        "layer_order": ["ink_deep", "inkA", "text"],
        "print": {"ratio": .045, "cap": 6.0},
        "reverse": {"ratio": .075, "cap": 12.0},
    },
    "decoration": {
        "sticker": {"rot_deg": [-6, 6], "outline_pt": 3, "outline": "ink",
                    "fill": "inkA", "text": "paper", "size_pt": [34, 50],
                    "box_pt": [150, 176, 96, 118], "per_page_max": 1},
        "star4": {"size_pt": [30, 44], "rot_deg": [10, 14], "fill": "accent1",
                  "per_page_max": 1},
        "dashed_rule": {"width_pt": 0.9, "colour": "text",
                        "per_page_max": 2},
        "quote_bar": {"width_pt": 5, "colour": "inkA",
                      "inset_left_pt": 22, "per_page_max": 1},
        "highlight": {"colour": "accent1", "height_em": 1.15,
                      "y_offset_em": 0.08, "per_page_max": 2,
                      "rule": "只垫在深色文字后面，不做纸色底上的文字色"},
        "note_aside": {"font": "label_latin", "italic": True, "colour": "inkA",
                       "spc_pt": 0.6, "per_page_max": 1,
                       "format": "( 前后留空格 )"},
        "kicker": {"font": "label_latin", "colour": "inkA", "spc_pt": 2.0,
                   "format": "NN  SECTION"},
        "element_budget_per_page": 24,
    },
    "dot_fields": {
        "source": "make_textures.FIELD_PRESETS（15 个已校准预设）",
        "rule": "点场只放该页空白区；必须给 radius 或让种子点在画布外",
        "ladder": {
            "whisper": "alpha 90-100, rmax 4.2-4.6  → 引语页、表格页",
            "light": "alpha 105-115, rmax 4.6-4.8 → 列表页、图解页",
            "medium": "alpha 120-130, rmax 4.8-5.2 → 风险页、边缘渐隐",
            "heavy": "alpha 150, rmax 5.8          → 数据页右下角",
        },
    },
    "provenance": {
        "calibrated": ["palette tokens and derived colours",
                       "misregistration offsets per type tier",
                       "dot-field parameter ladder and 15 named presets",
                       "chrome geometry vs registration marks",
                       "decoration treatments and per-page limits"],
        "policy": "These values are frozen in this file. Future runs must not "
                  "read a poster, a previous deck or an example image to "
                  "re-derive them; user-supplied photos may only enter through "
                  "`make_textures.py duotone`.",
    },
}


def _lum(hexcolor):
    """Relative luminance 0..1 of a '#rrggbb' colour."""
    c = hexcolor.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def misreg_offsets(size, mode=None):
    """Layer offsets for a display type size, from DESIGN.misregistration."""
    m = DESIGN["misregistration"]
    if mode is not None:
        if mode not in ('print','reverse'):
            raise ValueError('misregistration mode must be print or reverse')
        back = min(float(size)*m[mode]['ratio'], m[mode]['cap'])
        return back, back/2
    if size >= 100:
        return tuple(m["display_xl"])
    if size >= 70:
        return tuple(m["display_l"])
    if size >= 34:
        return tuple(m["display_m"])
    return tuple(m["page_title"])


def design_system():
    """The whole frozen design system, JSON-serialisable."""
    d = dict(DESIGN)
    d["fonts"] = dict(FONTS)
    d["dot_fields"] = dict(DESIGN["dot_fields"])
    d["dot_fields"]["presets"] = mt.FIELD_PRESETS
    d["dot_fields"]["recommended_by_archetype"] = mt.RECOMMENDED_PRESET
    return d



class Theme:
    """Palette + fonts + how loud the print grammar is."""

    def __init__(self, palette="G", palette_hex=None, print_grammar="light",
                 lang="zh", fonts=None):
        if print_grammar not in GRAMMAR_LEVELS:
            raise ValueError(f"print_grammar must be one of {GRAMMAR_LEVELS}")
        self.palette = palette
        colours = (palette_hex.split(",") if palette_hex else mt.PALETTES[palette])
        ctx = mt.Ctx(PAGE_W, PAGE_H, 1, colours)
        self.t = ctx.tokens()
        self.paper = self.t["paper"]
        self.inkA = self.t["inkA"]
        self.inkB = self.t["inkB"]
        self.ink = self.t["ink"]
        self.ink_deep = self.t["ink_deep"]
        self.inkAB = self.t["inkAB"]
        self.tintA = self.t["tintA"]
        self.tintB = self.t["tintB"]
        self.accent1 = self.t["accent1"]
        self.accent2 = self.t["accent2"]
        self.text = "#2B2B2B"            # charcoal, never pure black on paper
        self.print_grammar = print_grammar
        # Page kind. A reversed page is flooded with ink A, so display type on it
        # is paper-coloured; a paper page needs ink. Archetypes must read this
        # rather than hardcode a colour, or a paper page gets paper-coloured
        # type and the title disappears into the sheet.
        self.on_red = False
        self.lang = lang
        self.fonts = dict(FONTS)
        if fonts:
            self.fonts.update(fonts)
        self.font_diagnostics = []
        chains = {
            'display_latin': ('Georgia','DejaVu Serif','Liberation Serif','Arial'),
            'label_latin': ('Georgia','DejaVu Serif','Liberation Serif','Arial'),
            'heading': ('Microsoft YaHei','PingFang SC','Noto Sans CJK SC','Noto Sans SC','SimHei','Heiti SC'),
            'body': ('Noto Serif SC','Noto Serif CJK SC','SimSun','Songti SC','Microsoft YaHei','Noto Sans CJK SC'),
        }
        if not lang.lower().startswith('zh'):
            chains['body'] += ('Georgia','DejaVu Serif','Liberation Serif')
            chains['heading'] += ('Georgia','DejaVu Sans','Liberation Sans')
        for role, chain in chains.items():
            requested = self.fonts[role]
            if tm.resolve(requested):
                continue
            if role in (fonts or {}):
                raise ValueError(f'Unresolved explicit font {requested!r} for {role}')
            fallback = next((f for f in chain if tm.resolve(f)), None)
            if not fallback:
                raise ValueError(f'No available font for {role} ({lang}); install a local font from {chain}')
            self.fonts[role] = fallback
            message = f'font fallback for {role}: {requested} -> {fallback}'
            self.font_diagnostics.append(message)
            import warnings
            warnings.warn(message, RuntimeWarning)

    # role-based accessors keep the spec's vocabulary ("ink black", "front layer")
    @property
    def front_ink(self):
        """Colour of the front (unaligned) layer of display type on this page."""
        return self.paper if self.on_red else self.text

    @property
    def back_ink(self):
        """Colour of the offset back layer: ink on paper, ink on a flood too."""
        return self.ink if self.on_red else self.ink_deep

    @property
    def f_display(self):
        return self.fonts["display_latin"]

    @property
    def f_heading(self):
        return self.fonts["heading"]

    @property
    def f_body(self):
        return self.fonts["body"]

    @property
    def f_label(self):
        return self.fonts["label_latin"]

    def bilingual_labels(self):
        """Label language follows the content language. English caps labels on
        every deck are noise on a Chinese business report, where a page full of
        English kickers says nothing the reader needs."""
        return self.lang.lower().startswith("zh")


# ------------------------------------------------------------------ low level
def _set_typeface(rPr, tag, name):
    el = rPr.find(qn(tag))
    if el is None:
        el = rPr.makeelement(qn(tag), {})
        rPr.insert_element_before(el, *_RPR_SEQ[_RPR_SEQ.index(tag) + 1:])
    el.set("typeface", name)


def _hex(c):
    """Theme tokens carry a leading '#'; RGBColor.from_string does not accept it."""
    return c.lstrip("#").upper() if isinstance(c, str) else c


def style_run(run, font=None, size=None, bold=None, italic=None, color=None,
              spc=None):
    f = run.font
    if font:
        f.name = font
        _set_typeface(f._rPr, "a:ea", font)   # without this CJK falls back
        _set_typeface(f._rPr, "a:cs", font)
    if size is not None:
        f.size = Pt(size)
    if bold is not None:
        f.bold = bold
    if italic is not None:
        f.italic = italic
    if color is not None:
        f.color.rgb = RGBColor.from_string(_hex(color))
    if spc:
        f._rPr.set("spc", str(int(round(spc * 100))))


def line_width(runs, family, size, bold=False, spc=0.0):
    """Measured width of one line made of [(text, overrides), ...] runs.

    Each run is measured in its own effective font and size, so a display run
    followed by a smaller unit run ("612" + " members") measures correctly.
    """
    total = 0.0
    for item in runs:
        t, over = (item, {}) if isinstance(item, str) else item
        total += tm.advance(t, over.get("font", family),
                            over.get("size", size),
                            over.get("bold", bold), over.get("spc", spc))
    return total


def no_wrap_width(needed, w):
    """Box width for a line that must not break: the measured width plus slack,
    never narrower than the design width the caller asked for."""
    slack = NO_WRAP["slack"] * needed + NO_WRAP["pad_pt"]
    return max(w, slack)


def text(slide, x, y, w, h, paras, anchor="t", wrap=True, **defaults):
    """Native text box. `paras` = list of dicts:

    dict(runs=[(text, {overrides}), ...], font=, size=, color=, bold=,
         align='l', ls=1.35, before=, after=, spc=)

    With `wrap=False` the box is widened to the measured line width (see
    NO_WRAP), so PowerPoint cannot re-break a line this module laid out. Set
    `wrap=False, fit_nowrap=False` to keep the literal width — that is only
    correct when the design width is already wider than the text.
    """
    fit_nowrap = defaults.pop("fit_nowrap", True)
    if not wrap and fit_nowrap and paras:
        need = 0.0
        for spec in paras:
            merged = dict(defaults)
            merged.update(spec)
            runs = merged.get("runs") or []
            if not runs:
                continue
            need = max(need, line_width(
                runs, merged.get("font") or FONTS["body"],
                merged.get("size", 20), merged.get("bold", False),
                merged.get("spc", 0.0)))
        if need > 0:
            w = no_wrap_width(need, w)
    tb = slide.shapes.add_textbox(Pt(x), Pt(y), Pt(w), Pt(h))
    tf = tb.text_frame
    # `auto_size` stays NONE: the frame is placed by geometry, so it must not
    # resize itself behind the layout's back. Sizing the box is what keeps the
    # line unbroken in every renderer.
    tf.word_wrap = wrap
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = ANCHOR[anchor]
    for i, spec in enumerate(paras):
        merged = dict(defaults)
        merged.update(spec)
        runs = merged.pop("runs")
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = ALIGN[merged.pop("align", "l")]
        p.line_spacing = merged.pop("ls", 1.35)
        if "before" in merged:
            p.space_before = Pt(merged.pop("before"))
        if "after" in merged:
            p.space_after = Pt(merged.pop("after"))
        for run_text, over in runs:
            opts = dict(merged)
            opts.update(over)
            r = p.add_run()
            r.text = run_text
            style_run(r, **opts)
    return tb


def _plain(shape):
    el = shape._element
    st = el.find(qn("p:style"))
    if st is not None:
        el.remove(st)
    spPr = el.spPr
    if spPr.find(qn("a:effectLst")) is None:
        spPr.append(spPr.makeelement(qn("a:effectLst"), {}))


def _fill_alpha(shape, opacity):
    spPr = shape._element.spPr
    sf = spPr.find(qn("a:solidFill"))
    if sf is None:
        return
    clr = sf.find(qn("a:srgbClr"))
    for old in clr.findall(qn("a:alpha")):
        clr.remove(old)
    clr.append(clr.makeelement(qn("a:alpha"), {"val": str(int(opacity * 1000))}))


def shape(slide, kind, x, y, w, h, fill=None, line=None, lw=0.75, alpha=None,
          rot=None, dash=None):
    sp = slide.shapes.add_shape(kind, Pt(x), Pt(y), Pt(w), Pt(h))
    _plain(sp)
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = RGBColor.from_string(_hex(fill))
        if alpha is not None:
            _fill_alpha(sp, alpha)
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = RGBColor.from_string(_hex(line))
        sp.line.width = Pt(lw)
        if dash:
            sp.line.dash_style = dash
    if rot:
        sp.rotation = rot
    sp.text_frame.word_wrap = False
    return sp


def rect(slide, x, y, w, h, **kw):
    return shape(slide, MSO_SHAPE.RECTANGLE, x, y, w, h, **kw)


def oval(slide, x, y, w, h, **kw):
    return shape(slide, MSO_SHAPE.OVAL, x, y, w, h, **kw)


def star4(slide, cx, cy, size, **kw):
    return shape(slide, MSO_SHAPE.STAR_4_POINT, cx - size / 2, cy - size / 2,
                 size, size, **kw)


def rule(slide, x, y, w, color, lw=0.8):
    return rect(slide, x, y, w, lw, fill=color)


def dashed(slide, x1, y1, x2, y2, color, lw=0.9):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Pt(x1), Pt(y1),
                                   Pt(x2), Pt(y2))
    c.line.color.rgb = RGBColor.from_string(_hex(color))
    c.line.width = Pt(lw)
    c.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    return c


def freeform(slide, pts, fill=None, line=None, lw=0.75, alpha=None):
    fb = slide.shapes.build_freeform(pts[0][0], pts[0][1], scale=12700)
    fb.add_line_segments(pts[1:], close=True)
    sp = fb.convert_to_shape()
    _plain(sp)
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = RGBColor.from_string(_hex(fill))
        if alpha is not None:
            _fill_alpha(sp, alpha)
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = RGBColor.from_string(_hex(line))
        sp.line.width = Pt(lw)
    return sp


# ------------------------------------------------------------------ idioms
def eta_width(s, size):
    """Rough advance width in points. CJK = 1em, ASCII = 0.55em, space = 0.3em.
    Used to place highlight bars; qa.py verifies the result on pixels."""
    total = 0.0
    for ch in s:
        if ord(ch) > 0x2E80:
            total += 1.0
        elif ch == " ":
            total += 0.30
        else:
            total += 0.55
    return total * size


def stack(slide, x, y, w, h, runs, theme, front=None, back=None, mid=None,
          offsets=None, align="l", ls=1.0, spc=None, anchor="t",
          autofit=True, paint=None):
    """Three-layer misregistered display type — native, editable text boxes.

    back = theme.ink_deep (ink A pushed toward the ink black)
    mid  = theme.inkA
    front= theme.text (charcoal), or `paint` when the page is reversed
    The rule ("deep ink / light ink / charcoal") is unbuildable when the
    second ink *is* the ink black; this stack is defined from ink A only, so it
    works for every palette. Offsets default to the frozen per-size tiers in
    DESIGN["misregistration"] (see references/design-system.md).

    `paint` sets the front layer's colour. It must be chosen from the page, not
    from the archetype: a reversed page needs paper-coloured type, a paper page
    needs ink. Passing paper on a paper page paints the title in the background
    colour, which leaves only the offset back layer visible as a ghost.
    """
    def draw(dx, dy, color):
        text(slide, x + dx, y + dy, w, h,
             [dict(runs=[(t, dict(font=f, size=s, color=color, bold=b))
                         for t, f, s, b in runs], align=align, ls=ls, spc=spc)],
             anchor=anchor, wrap=False)
    if autofit:
        # Fit the runs TOGETHER, not one at a time: shrinking "612" and " members"
        # independently over-shrinks each and the pair still overflows, which is
        # how the ask page ended with $90k across a divider rule.
        lone = [(t, f, tm.fit_size(t, f, sz, w, b, spc), b)
                for t, f, sz, b in runs]
        need = line_width([(t, dict(font=f, size=s, bold=b)) for t, f, s, b in lone],
                          runs[0][1] if runs else FONTS["body"],
                          runs[0][2] if runs else 20, spc=spc)
        if need > w:
            k = w / need
            runs = [(t, f, max(8.0, s * k), b) for t, f, s, b in lone]
        else:
            runs = lone
    front_color = paint if paint is not None else (front or theme.text)
    size0 = max(s for _t, _f, s, _b in runs)
    base_off = offsets if offsets is not None else misreg_offsets(size0, 'reverse' if theme.on_red else 'print')
    # An explicit None for a layer means "the caller does not want it", which is
    # what p_statement asks for on a reversed page (mid=None). Only a bare
    # default falls back to the theme colour.
    back_col = theme.ink_deep if back is None else back
    mid_col = theme.inkA if mid is None else mid
    raw = []
    if back_col and base_off[0]:
        raw.append((back_col, base_off[0]))
    if mid_col and base_off[1]:
        raw.append((mid_col, base_off[1]))
    if size0 < 100 and len(raw) > 1:
        # Rule G allows one shadow under 100pt. Keep the FIRST candidate: the
        # back layer is the one that reads on both a paper page and a reversed
        # one, whereas the mid layer prints ink A on an ink-A flood and
        # disappears there.
        raw = raw[:1]
    layers = []
    for color, off in raw:
        ref = layers[-1][0] if layers else front_color
        # Rule G drops a layer whose neighbour is too close in luminance. That
        # is a sound test on a paper page, where the neighbour of a display line
        # is the layer behind it. On a reversed page the backdrop is the ink
        # flood, not the front layer, so running the test there deletes the very
        # layer it is meant to check — a paper-white halo judged muddy against
        # charcoal type. On a flood every layer is kept and qa.py judges the
        # contrast of the result.
        if not theme.on_red and abs(_lum(color) - _lum(ref)) < 0.25:
            continue            # muddy neighbour: drop the farther layer
        layers.append((color, off))
    if not layers and raw:
        # Rule G is a "drop the muddy layer" rule, not a "print flat type" rule.
        # Some palettes place ink_deep within 0.05 luminance of the charcoal
        # front, so the test can reject the theme's own back layer and leave the
        # misregistered stack with a single layer — the display type loses its
        # overprint. When the test would remove everything, keep the back layer:
        # one shadow is the minimum the archetypes are designed around, and a
        # 0.05 luminance step still reads as an edge at display sizes. Only the
        # muddiness test is relaxed; the <=2 layer cap stands.
        color, off = raw[0]
        layers.append((color, off))
    for color, off in layers:
        draw(off, off, color)
        slide.shapes[-1].name = 'riso-layer[back]'
    draw(0, 0, front_color)
    slide.shapes[-1].name = 'riso-layer[front]'


def send_behind(slide, shape, target):
    """Move `shape` directly behind `target` in the shape tree."""
    tree = slide.shapes._spTree
    tree.remove(shape._element)
    tree.insert(list(tree).index(target._element), shape._element)


def highlight_word(slide, text_shape, full_text, target, theme, colour=None,
                   ls=1.25, pad=1.0, spc=0.0, font=None, bold=None, size=None):
    """Draw a highlight bar that provably sits behind `target`.

    The text shape is measured with real font metrics, the word's sub-rectangle
    is derived from that measurement, and the bar is then moved behind the text.
    Estimating the width instead puts the bar 5-20pt off for Latin text, so
    every bar goes through the measurement.
    """
    run = None
    for p in text_shape.text_frame.paragraphs:
        if p.runs:
            run = p.runs[0]
            break
    if run is None:
        return None
    fam = font or run.font.name or theme.f_body
    sz = size or (run.font.size.pt if run.font.size else 18)
    bd = bold if bold is not None else bool(run.font.bold)
    try:
        spc_pt = float(run.font._rPr.get("spc") or 0) / 100.0
    except Exception:
        spc_pt = spc
    box = tm.tight_rect(text_shape, mode="box")
    sub = tm.sub_rect(box, full_text, target, fam, sz, bd, ls, spc_pt)
    if not sub:
        return None
    bar = rect(slide, sub[0] - pad, sub[1] - pad,
               (sub[2] - sub[0]) + 2 * pad, (sub[3] - sub[1]) + 2 * pad,
               fill=colour or theme.accent1)
    send_behind(slide, bar, text_shape)
    return bar


def hero(slide, x, y, w, h, value, theme, unit=None, size=148, unit_size=None,
         front=None, layers=None,
         autofit=True):
    """The page's single big number. Same misregistration, fewer layers.

    `layers` is (colour role, offset) — named roles, not magic indices.
    """
    if autofit:
        base = value + (unit or "")
        size = tm.fit_size(base, theme.f_display, size, w, False)
    front_color = front or theme.text
    if layers is None:
        off = misreg_offsets(size, 'reverse' if theme.on_red else 'print')
        layers = (("ink_deep",off[0]),("inkA",off[1]))
    raw = list(layers)
    if size < 100 and len(raw) > 1:
        raw = raw[-1:]          # rule G: one shadow under 100pt
    kept = []
    for role, off in raw:
        ref = getattr(theme, kept[-1][0]) if kept else front_color
        if abs(_lum(getattr(theme, role)) - _lum(ref)) < 0.25:
            continue
        kept.append((role, off))
    runs = [(value, theme.f_display, size, False)]
    if unit:
        runs.append((unit, theme.f_heading, unit_size or size * 0.36, True))
    def draw(dx, dy, color):
        text(slide, x + dx, y + dy, w, h,
             [dict(runs=[(t, dict(font=f, size=s, color=color, bold=b))
                         for t, f, s, b in runs], ls=1.0)], wrap=False)
    for role, off in kept:
        draw(off, off, getattr(theme, role))
        slide.shapes[-1].name = 'riso-layer[back]'
    draw(0, 0, front_color)
    slide.shapes[-1].name = 'riso-layer[front]'


def label(slide, x, y, w, txt, theme, size=12, color=None, align="l", spc=1.6,
          font=None, h=None):
    return text(slide, x, y, w, h or size * 1.6,
                [dict(runs=[(txt, {})], font=font or theme.f_label, size=size,
                      color=color or theme.text, bold=True, align=align, spc=spc,
                      ls=1.0)])


def note(slide, x, y, w, txt, theme, color=None, align="l", size=13):
    """One red italic bracketed aside per page, max."""
    return text(slide, x, y, w, size * 1.7,
                [dict(runs=[(txt, {})], font=theme.f_label, size=size,
                      color=color or theme.inkA, italic=True, align=align,
                      ls=1.0, spc=0.6)])


def highlight(slide, x, y, w, h, theme, color=None):
    """Fluorescent bar BEHIND dark text. Never text on the accent colour."""
    return rect(slide, x, y, w, h, fill=color or theme.accent1)


def kicker(slide, x, y, num, txt, theme, color=None, size=13):
    return text(slide, x, y, 700, size * 1.6,
                [dict(runs=[(num + "  ", {}), (txt, {})], font=theme.f_label,
                      size=size, bold=True, color=color or theme.inkA, spc=2.0,
                      ls=1.0)])


def page_title(slide, x, y, txt, theme, size=34, w=700, front=None):
    off=misreg_offsets(size,'reverse' if theme.on_red else 'print')[0]
    back=text(slide, x + off, y + off, w, size * 1.5,
         [dict(runs=[(txt, {})], font=theme.f_heading, size=size,
               color=theme.inkA, bold=True, ls=1.1)], wrap=False)
    back.name='riso-layer[back]'
    result=text(slide, x, y, w, size * 1.5,
                [dict(runs=[(txt, {})], font=theme.f_heading, size=size,
                      color=front or theme.text, bold=True, ls=1.1)], wrap=False)
    result.name='riso-layer[front]'
    return result


def body(slide, x, y, w, h, lines, theme, size=20, color=None, ls=1.5, font=None,
         fit=False):
    """Each line is a string, a [(text, {overrides}), ...] run list, or a full
    paragraph dict.

    fit=True scales `size` down (measured with real font metrics) so the longest
    line fits `w` on one line. Narrow columns in a 4-up layout are otherwise
    only usable with copy short enough to be meaningless.
    """
    paras = []
    for line in lines:
        if isinstance(line, str):
            sz = tm.fit_size(line, font or theme.f_body, size, w) if fit else size
            paras.append(dict(runs=[(line, {})], font=font or theme.f_body,
                              size=sz, color=color or theme.text, ls=ls))
        elif isinstance(line, (list, tuple)):
            runs = [(i, {}) if isinstance(i, str) else (i[0], i[1]) for i in line]
            if fit:
                flat = "".join(t for t, _o in runs)
                sz = tm.fit_size(flat, font or theme.f_body, size, w)
            else:
                sz = size
            paras.append(dict(runs=runs, font=font or theme.f_body, size=sz,
                              color=color or theme.text, ls=ls))
        else:
            paras.append(line)
    return text(slide, x, y, w, h, paras)


def sticker(slide, x, y, w, h, txt, theme, size=44, rot=-5, fill=None,
            line=None, color=None, font=None):
    rect(slide, x, y, w, h, fill=fill or theme.inkA, line=line or theme.ink,
         lw=3, rot=rot)
    # the sticker is rotated, so its live text width is ~0.78w; a long word
    # ("BORROW") at a fixed size would sail off the canvas edge
    fam = font or theme.f_display
    size = max(22.0, min(float(size),
                         tm.fit_size(txt, fam, size, w * 0.78, True)))
    return text(slide, x, y, w, h,
                [dict(runs=[(txt, {})], font=fam, size=size,
                      color=color or theme.paper, align="c", ls=1.0)],
                anchor="m", wrap=False)


def bar_row(slide, x, y, w, pct, scale_max, theme, color=None, height=20):
    """Flat geometry bar — no pptx chart objects, so the look stays riso."""
    length = w * (pct / float(scale_max))
    rect(slide, x, y, length, height, fill=color or theme.inkB)
    return length


# Rule E: the chrome set is chosen ONCE per deck and never re-decided per
# page; at most 4 items; every item counts into the page's decoration budget.
CHROME_SETS = {
    "full": ("head_label", "right_label", "foot_rule", "page_num"),
    "light": ("head_label", "foot_rule", "page_num"),
    "none": ("page_num",),
}


def chrome(slide, theme, idx, total, left, right, foot_left=None,
           on_red=False, items=None, right_cap=None):
    """Header/footer furniture, drawn from the deck-wide chrome set.

    Labels must stay on one line: the font size is shrunk to the measured
    width rather than letting the label wrap onto a rule. `right_cap` pulls
    the right label's right edge in (e.g. a cover's corner sticker lives at
    x 812+, so the label must stop short of it instead of overlapping)."""
    fg = theme.paper if on_red else theme.text
    g = theme.print_grammar
    items = items or CHROME_SETS.get(g, CHROME_SETS["light"])

    def fit_label(x, y, w, txt, align="l", spc=1.6):
        size = tm.fit_size(txt, theme.f_label, 12.0, w, True, spc)
        size = max(9.0, min(12.0, size))
        return label(slide, x, y, w, txt, theme, size=size, color=fg,
                     align=align, spc=spc)

    if "head_label" in items and left:
        fit_label(MARGIN_L, HEAD_Y, 560, left)
    if "right_label" in items and right:
        r_edge = min(MARGIN_R, right_cap if right_cap else MARGIN_R)
        fit_label(240, HEAD_Y, r_edge - 240, right, align="r")
    if "head_rule" in items:
        rule(slide, MARGIN_L - 4, RULE_Y, (MARGIN_R - MARGIN_L) + 8, fg)
    if "foot_rule" in items:
        rule(slide, MARGIN_L - 4, FOOT_RULE_Y, (MARGIN_R - MARGIN_L) + 8, fg)
    if "foot_label" in items and (foot_left or ""):
        fit_label(MARGIN_L, FOOT_Y, 620, foot_left, spc=1.4)
    if "page_num" in items:
        label(slide, MARGIN_R - 320, FOOT_Y, 320, f"{idx:02d} / {total:02d}",
              theme, size=12, color=fg, spc=1.4, align="r")


def chrome_area(items):
    """Approximate ink area of a chrome set, in pt^2 — counted into the
    page's decoration budget (rule E)."""
    area = 0.0
    if "head_label" in items:
        area += 560 * 14 * 0.35
    if "right_label" in items:
        area += 300 * 14 * 0.35
    if "foot_label" in items:
        area += 620 * 14 * 0.35
    if "head_rule" in items:
        area += 928 * 0.8
    if "foot_rule" in items:
        area += 928 * 0.8
    if "page_num" in items:
        area += 80 * 14 * 0.4
    return area


# ------------------------------------------------------------------ figures
def lens_points(c1, c2, r1, r2, steps=28):
    """Outline of the intersection lens of two circles (the overprint area)."""
    (x1, y1), (x2, y2) = c1, c2
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy)
    if d == 0 or d >= r1 + r2 or d <= abs(r1 - r2):
        return []
    a = (d * d + r1 * r1 - r2 * r2) / (2 * d)
    h = math.sqrt(max(r1 * r1 - a * a, 0.0))
    ux, uy = dx / d, dy / d
    xm, ym = x1 + a * ux, y1 + a * uy
    i1 = (xm - h * uy, ym + h * ux)
    i2 = (xm + h * uy, ym - h * ux)

    def arc(cx, cy, r, p_from, p_to, other_c, other_r):
        a0 = math.atan2(p_from[1] - cy, p_from[0] - cx)
        a1 = math.atan2(p_to[1] - cy, p_to[0] - cx)
        for sweep in ((a1 - a0) % (2 * math.pi), -((a0 - a1) % (2 * math.pi))):
            mid = a0 + sweep / 2.0
            mx, my = cx + r * math.cos(mid), cy + r * math.sin(mid)
            if math.hypot(mx - other_c[0], my - other_c[1]) <= other_r + 1e-6:
                return [(cx + r * math.cos(a0 + sweep * i / steps),
                         cy + r * math.sin(a0 + sweep * i / steps))
                        for i in range(steps + 1)]
        return []

    return arc(x1, y1, r1, i1, i2, c2, r2) + arc(x2, y2, r2, i2, i1, c1, r1)



def venn(slide,c1,c2,r,theme,left_txt,right_txt,centre_txt):
    import layout as lay
    import typefit as tf
    circles=[]
    for name,c,fill,alpha in (('left',c1,theme.inkA,32),('right',c2,theme.text,14)):
        sh=oval(slide,c[0]-r,c[1]-r,2*r,2*r,fill=fill,alpha=alpha,line=fill,lw=2)
        sh.name=f'venn-circle[{name}]'
        circles.append(lay.obb(sh))
    freeform(slide,lens_points(c1,c2,r,r),fill=theme.ink_deep,alpha=88)
    placements=(('left',left_txt,c1[0]-r*.5,r*.75,r*.70,theme.text,theme.f_body),
                ('right',right_txt,c2[0]+r*.5,r*.75,r*.70,theme.text,theme.f_body),
                ('centre',centre_txt,(c1[0]+c2[0])/2,r*.58,r*.55,theme.paper,theme.f_heading))
    for role,value,cx,w,h,color,family in placements:
        if not value:continue
        fitted=tf.fit(value,family,18,w,h,minimum=14,bold=role=='centre',role='venn '+role)
        shapes=tf.draw(slide,cx-w/2,c1[1]-fitted.height/2,w,fitted,theme,
                       alignment='c',color=color,role='venn-label')
        for sh in shapes:
            sh.name=f'venn-label[{role}]'
            required=circles if role=='centre' else [circles[0 if role=='left' else 1]]
            if not all(lay.ellipse_contains(circle,glyph) for circle in required for glyph in tm.glyph_rects(sh)):
                raise ValueError(f'venn {role}: measured glyphs do not fit the circle/intersection')


# ------------------------------------------------------------------ deck
def new_deck(canvas=None):
    canvas = canvas or DECK_CANVAS
    prs = Presentation()
    prs.slide_width = Pt(canvas.width)
    prs.slide_height = Pt(canvas.height)
    return prs


def add_page(prs, bg_path):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    if bg_path:
        slide.shapes.add_picture(bg_path, Pt(0), Pt(0), prs.slide_width, prs.slide_height)
    return slide


def set_notes(slide, txt):
    if txt:
        slide.notes_slide.notes_text_frame.text = txt
