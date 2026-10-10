#!/usr/bin/env python3
"""compose.py — dialects, density profiles, and the automatic element layer.

Two complaints drove this module: every deck came out with the same skeleton,
and a page carried almost no decoration beyond a halftone field. The fix is to
make the *decorative vocabulary* a first-class, selectable thing:

  dialect   which element pool, which layout motifs, how loud the print grammar
            is, how heavy the stroke character — one primary + one secondary per
            deck, chosen from content domain and never repeated back-to-back
  density   how big and how many elements a page gets, driven by the scenario
            unless the user asks for something specific

Decoration placed by "find the gaps and fill them" scatters into confetti and
competes with the copy, so placement is *anchored*, in decreasing order of
legitimacy (see plan_page):

  attached  bound to a content anchor — under the title, off a big number's
            corner, beside a label; the reader can explain what it points at
  marginal  one small piece on the page edge farthest from the copy
  free      only into the largest remaining gap, few of them, and a hero only
            when that gap is genuinely large; there is no area floor to meet

Everything keeps a protection gap from the *measured* text rectangles from
textmetrics, and qa.py verifies it afterwards.
"""
import sys
sys.dont_write_bytecode = True
import json
import math
import os
import random

from PIL import Image

import elements as E
import layout as lay
import textmetrics as tm
from canvas import DECK_CANVAS

# --------------------------------------------------------------- dialects
DIALECTS = {
    "A": {
        "name": "拼贴剪贴",
        "en": "collage",
        "pools": {
            "hero": ["torn_paper", "handcut_polygon", "grain_fade", "polaroid",
                     "newspaper_clipping", "airmail_envelope"],
            "support": ["washi_tape", "stamp_postmark", "ticket_stub",
                        "layered_stack", "luggage_tag", "rubber_stamp",
                        "zigzag_strip"],
            "micro": ["paperclip", "ransom_word", "stamp_postmark"],
        },
        "motifs": ["tabletop", "sticker_sheet", "spread", "band_split"],
        "grammar": {"header": "line", "footer": "line", "reg_marks": True},
        "stroke": "torn",
        "density_bias": 1.0,
        "palettes": ["C", "A", "E"],
    },
    "B": {
        "name": "涂鸦手帐",
        "en": "doodle journal",
        "pools": {
            "hero": ["scribble_circle", "scribble_fill", "thought_cloud",
                     "marker_frame", "speech_bubble", "sticky_note"],
            "support": ["wavy_underline", "hand_arrow", "asterisk", "spiral",
                        "checklist", "hand_brace", "double_underline",
                        "scribble_redact"],
            "micro": ["mini_doodle", "doodle_face", "starburst", "asterisk"],
        },
        "motifs": ["notebook_page", "annotation", "sticker_sheet", "list_form"],
        "grammar": {"header": "hand", "footer": "hand", "reg_marks": False},
        "stroke": "drawn",
        "density_bias": 1.15,
        "palettes": ["B", "F", "D"],
    },
    "C": {
        "name": "瑞士几何",
        "en": "swiss geometric",
        "pools": {
            "hero": ["arch", "blob", "circle_text_badge", "quarter_tiles",
                     "outline_letter", "stairs"],
            "support": ["pill", "stripe_band", "checkerboard", "zigzag_band",
                        "plus_grid", "scallop_block", "triangle_strip", "ring",
                        "line_screen"],
            "micro": ["plus_grid", "ring", "stripe_band", "circled_number"],
        },
        "motifs": ["band_split", "diagonal_cut", "badge_centre", "pure_type",
                   "swiss_grid"],
        "grammar": {"header": "line", "footer": "line", "reg_marks": True},
        "stroke": "precise",
        "density_bias": 0.95,
        "palettes": ["D", "C", "E"],
    },
    "D": {
        "name": "杂志模块",
        "en": "magazine grid",
        "pools": {
            "hero": ["newspaper_clipping", "paper_sheet", "blob", "ring",
                     "colour_bar"],
            "support": ["crop_marks", "fold_line", "caption_label",
                        "issue_stamp", "line_screen", "zigzag_strip",
                        "barcode"],
            "micro": ["printed_note", "caption_label", "circled_number",
                      "colour_bar"],
        },
        "motifs": ["magazine_grid", "spread", "list_form", "band_split"],
        "grammar": {"header": "rule", "footer": "rule", "reg_marks": True},
        "stroke": "precise",
        "density_bias": 1.05,
        "palettes": ["D", "C", "A"],
    },
    "E": {
        "name": "复古 OS / Y2K",
        "en": "retro OS",
        "pools": {
            "hero": ["os_window", "dialog_box", "pixel_icon", "progress_bar",
                     "grain_fade"],
            "support": ["progress_bar", "pixel_icon", "dot_screen",
                        "square_dot_screen", "barcode"],
            "micro": ["cursor_arrow", "pixel_icon", "printed_note"],
        },
        "motifs": ["stacked_windows", "band_split", "list_form", "badge_centre"],
        "grammar": {"header": "rule", "footer": "rule", "reg_marks": False},
        "stroke": "pixel",
        "density_bias": 1.0,
        "palettes": ["B", "F", "E"],
    },
    "F": {
        "name": "Zine 漫画",
        "en": "zine comic",
        "pools": {
            "hero": ["starburst", "speech_bubble", "marquee_band",
                     "scribble_fill", "handcut_polygon"],
            "support": ["starburst", "zigzag_strip", "loop_border", "asterisk",
                        "scribble_circle", "marquee_band"],
            "micro": ["mini_doodle", "starburst_badge", "circled_number",
                      "asterisk"],
        },
        "motifs": ["comic_panels", "badge_centre", "band_split", "pure_type"],
        "grammar": {"header": "marquee", "footer": "line", "reg_marks": False},
        "stroke": "loud",
        "density_bias": 1.25,
        "palettes": ["F", "B", "E"],
    },
}

# content domain -> (primary, secondary) preference
DOMAIN_MAP = [
    (("财务", "数据", "汇报", "finance", "data", "report", "quarter", "kpi"),
     ("D", "E")),
    (("教育", "学习", "笔记", "课程", "讲义", "education", "course", "note",
      "lecture", "study"), ("B", "A")),
    (("科技", "ai", "软件", "产品", "tech", "software", "product", "launch",
      "app"), ("E", "C")),
    (("环保", "自然", "地理", "能源", "climate", "energy", "nature"),
     ("C", "A")),
    (("文学", "人文", "演讲", "语言", "literature", "speech", "language",
      "humanities"), ("A", "C")),
    (("活动", "音乐", "青春", "社团", "music", "event", "festival", "club"),
     ("F", "C")),
]

# scenario -> how big and how many decorative elements a page gets.
#
# Every profile states *how many* AND *where*: a count alone would let
# decoration scatter into whatever holes the copy happened to leave and compete
# with the title. Three changes:
#
#   attached  elements bound to a content anchor (title, big number, label) —
#             the decorations a reader can explain ("it underlines the title")
#   free      unanchored extras, allowed only into the largest remaining gap
#             and only in small numbers; there is NO area floor any more —
#             a page with little room gets little decoration, and that is the
#             intended look, not a failure
#   hero_min_room  a hero appears only when the page genuinely has one: the
#             largest legal empty rectangle must be at least this share of the
#             page (mood archetypes use half). Otherwise the page goes hero-less.
DENSITY = {
    "speech": {
        "font_scale": 1.12, "hero_frac": (0.26, 0.44), "attached": (1, 2),
        "free": (0, 1), "element_scale": 1.15, "max_area": 0.22,
        "hero_min_room": 0.15,
        "note": "演讲：字大、元素少而大；装饰锚定标题与大数字，不填空",
    },
    "report": {
        "font_scale": 0.95, "hero_frac": (0.14, 0.26), "attached": (1, 2),
        "free": (0, 2), "element_scale": 0.85, "max_area": 0.18,
        "hero_min_room": 0.13,
        "note": "汇报：商务、克制；元素小而少，依附内容边缘",
    },
    "course": {
        "font_scale": 1.0, "hero_frac": (0.18, 0.32), "attached": (1, 2),
        "free": (0, 2), "element_scale": 0.90, "max_area": 0.22,
        "hero_min_room": 0.14,
        "note": "讲义：图表优先，元素服务于理解",
    },
    "proposal": {
        "font_scale": 0.98, "hero_frac": (0.18, 0.34), "attached": (1, 2),
        "free": (0, 2), "element_scale": 0.95, "max_area": 0.22,
        "hero_min_room": 0.14,
        "note": "提案：说服链清晰，元素强调而非装饰",
    },
    "poster": {
        "font_scale": 1.15, "hero_frac": (0.36, 0.58), "attached": (1, 3),
        "free": (1, 3), "element_scale": 1.30, "max_area": 0.38,
        "hero_min_room": 0.10,
        "note": "海报：满版、冲击力优先",
    },
    "zine": {
        "font_scale": 1.0, "hero_frac": (0.24, 0.44), "attached": (1, 3),
        "free": (1, 3), "element_scale": 1.05, "max_area": 0.34,
        "hero_min_room": 0.10,
        "note": "小志/漫画：密集、手作感、允许重叠",
    },
}
DEFAULT_SCENARIO = "report"

# ------------------------------------------------------- density levels (H)
# How much copy a content page should carry. The scenario decides the LOOK;
# the density level decides the WORDS. Page count follows from the source
# length: pages = ceil(content words / band midpoint), and the duration rule
# (25-40s per page) is only a ceiling, never a target.
DENSITY_LEVELS = {
    "D1": {"name": "海报型", "words": (0, 20), "body_min": 22,
           "use": "只在用户明确要求极简 / 海报感 / 一句话时使用"},
    "D2": {"name": "演讲伴随型", "words": (35, 60), "body_min": 22,
           "use": "演讲稿默认；封面 / 结尾 / 金句 / 大声明页不受限，但也不低于 8 词"
                  "（单词级大声明除外）"},
    "D3": {"name": "汇报型", "words": (60, 110), "body_min": 18,
           "use": "提案、汇报、方案默认"},
    "D4": {"name": "阅读型", "words": (110, 160), "body_min": 16,
           "use": "用户明确说发给别人读 / 详细时使用"},
}
DEFAULT_DENSITY = {"speech": "D2", "proposal": "D3", "report": "D3",
                   "course": "D3", "poster": "D1", "zine": "D2"}


SPEECH_WORD_BANDS={'D1':(0,20),'D2':(25,55),'D3':(45,85),'D4':(70,120)}


def density_band(scenario,level,override=None):
    """Word count is a configurable planning proxy, never a semantic score."""
    if override is not None:
        if not isinstance(override,(list,tuple)) or len(override)!=2 or any(
            isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in override) or not 0<=override[0]<override[1]:
            raise ValueError('meta.word_band must be [nonnegative lower, greater finite upper]')
        return tuple(override)
    return SPEECH_WORD_BANDS[level] if scenario=='speech' else DENSITY_LEVELS[level]['words']


def infer_density(scenario, hint=None):
    """Resolve the density level: explicit user hint > scenario default.
    Unsure => D2 (never D1 unless asked)."""
    if hint and hint in DENSITY_LEVELS:
        return hint
    return DEFAULT_DENSITY.get(scenario, "D2")


def content_pages_for(words, level="D2", mood_pages=2):
    """How many pages the source text justifies: content pages carry the band
    midpoint of words; mood pages (cover, closing) come on top, capped by the
    duration rule separately."""
    lo, hi = DENSITY_LEVELS[level]["words"]
    mid = max(12.0, (lo + hi) / 2.0)
    n_content = max(1, math.ceil(words / mid))
    return n_content + mood_pages

# Page types that *are* the mood (a cover, a statement, a closing) may carry a
# hero at the full scenario share. Page types that carry information (data,
# grid, timeline...) get a hero at most at a reduced share, and only when the
# room is genuinely there — the content is already the protagonist.
MOOD_ARCHETYPES = {"cover", "statement", "quote", "closing", "divider"}
CONTENT_HERO_SCALE = 0.55    # hero_frac multiplier on information pages
HERO_ROOM_CLIP = 0.62        # a hero never takes more than this of its room
QUIET_MIN = 0.10             # stop adding free/marginal items below this share

# Where a decoration may legally live, in priority order. Anything that cannot
# answer one of these three questions does not get drawn:
#   attached  — what does it point at? (bound to an anchor, protection-gap away)
#   marginal  — which page edge or corner does it live on? (far from anchors)
#   free      — which large empty region does it sit in? (largest gap only)
ATTACH_GAP = (11.0, 16.0)    # pts clear of the anchor's ink: near, never on it
ATTACH_NEAR = 60.0           # qa.py: within this of copy counts as attached
# attached pieces punctuate the content, so they live inside the content
# frame — never bleeding off the page edge or into the header/footer bands
ATTACH_FRAME = DECK_CANVAS.attach_frame

# Elements that draw their own words. They cannot be re-lettered from a spec, so
# using one puts a stranger's sentence on the page (see element_pool).
TEXT_BEARING = {
    "colour_bar",       # labelled swatch strip: grass green / overprint / rice white
    "issue_stamp",      # VOL. 03 / ISSUE 07 / MAR 2024
    "ransom_word",      # spells R E T U R N
    "caption_label",    # FIG. 01 — PRESS SHEET
    "printed_note",     # RISOGRAPH · LIMITED EDITION
    "newspaper_clipping",
    "barcode",
    "ticket_stub", "polaroid", "luggage_tag", "rubber_stamp", "outline_letter",
    "circle_text_badge", "marquee_band", "vertical_text", "drop_cap",
    "os_window", "progress_bar", "dialog_box",
}

# Elements that draw a number or glyph the spec never chose. A circled "53" beside
# a page title is a fact invented by the decorator, so these are excluded from the
# fallback pool even where a dialect lists them.
NUMBER_BEARING = {"circled_number", "asterisk", "mini_doodle", "starburst_badge",
                  "doodle_face"}
TEXT_BEARING |= set(E.COPY_FIELDS)

# Curated sets: what a press actually puts on a sheet — plates, rules, marks,
# texture. Used instead of the dialect pool when a dialect is listed here.
ELEMENT_SETS = {
    "D": {                       # magazine: plates, marks, rules
        "hero": ["paper_sheet", "layered_stack", "blob"],
        "support": ["ring", "line_screen", "crop_marks", "fold_line"],
        "micro": ["zigzag_strip", "plus_grid"],
    },
    "A": {                       # collage: pasted paper, stamps, tape
        "hero": ["handcut_polygon", "layered_stack"],
        "support": ["stamp_postmark", "rubber_stamp", "washi_tape"],
        "micro": ["paperclip", "zigzag_strip"],
    },
    "B": {
        "hero": ["scribble_circle", "scribble_fill", "marker_frame", "sticky_note"],
        "support": ["wavy_underline", "hand_arrow", "hand_brace", "double_underline"],
        "micro": ["spiral"],
    },
    "C": {
        "hero": ["arch", "blob", "ring", "stairs", "quarter_tiles", "outline_letter"],
        "support": ["pill", "stripe_band", "checkerboard", "zigzag_band",
                    "plus_grid", "scallop_block", "triangle_strip", "line_screen"],
        "micro": ["plus_grid", "ring", "stripe_band"],
    },
    "E": {
        "hero": ["pixel_icon", "cursor_arrow"],
        "support": ["progress_bar", "pixel_icon", "dot_screen", "square_dot_screen"],
        "micro": ["cursor_arrow"],
    },
    "F": {
        "hero": ["starburst", "speech_bubble", "marquee_band", "scribble_fill",
                 "handcut_polygon"],
        "support": ["zigzag_strip", "loop_border", "marquee_band"],
        "micro": ["zigzag_strip"],
    },
}


def _norm(s):
    return (s or "").lower()


def pick_dialects(text_blob, scenario, seed, history=None, forced=None,
                  self_key=None):
    """Choose a primary and a secondary dialect.

    Rule from the brief: user choice > content domain > seeded random, and never
    reuse the primary+major-motif combination of the last three decks.
    """
    rnd = random.Random(seed)
    if forced:
        primary = forced[0]
        secondary = forced[1] if len(forced) > 1 else _other(primary, rnd)
        return primary, secondary, "user"
    # A rebuild keeps its recorded choice even after unrelated builds intervene.
    if self_key:
        for rec in reversed((history or {}).get("decks", [])):
            if (rec.get("deck"), rec.get("seed")) == self_key:
                if rec.get("primary") in DIALECTS and rec.get("secondary") in DIALECTS:
                    return rec["primary"], rec["secondary"], rec.get("chosen_by", "domain")
    blob = _norm(text_blob)
    scored = []
    for keys, (a, b) in DOMAIN_MAP:
        hit = sum(1 for k in keys if k in blob)
        if hit:
            scored.append((hit, a, b))
    recent = set()
    for rec in (history or {}).get("decks", [])[-3:]:
        # rebuilding the same deck (same title + seed) is not a "recent deck" —
        # otherwise a second build of one spec drifts to another dialect and the
        # deck stops being reproducible
        if self_key and (rec.get("deck"), rec.get("seed")) == self_key:
            continue
        recent.add((rec.get("primary"), rec.get("secondary")))

    def fresh(pair):
        return pair not in recent

    if scored:
        scored.sort(key=lambda x: -x[0])
        # walk every domain match before falling back to random, so the same
        # content does not produce the same dialect three decks in a row
        for hit, a, b in scored:
            for cand in ((a, b), (b, a)):
                if fresh(cand):
                    return cand[0], cand[1], "domain"
    letters = list(DIALECTS)
    rnd.shuffle(letters)
    for a in letters:
        b = _other(a, rnd)
        if (a, b) not in recent:
            return a, b, "random"
    return letters[0], _other(letters[0], rnd), "random"


def _other(primary, rnd):
    pool = [d for d in DIALECTS if d != primary]
    rnd.shuffle(pool)
    return pool[0]


def element_pool(primary, secondary, exclusions=(), candidates=None):
    """Primary supplies 3/4 of the pool, the secondary the rest — that is what
    keeps a deck from looking like a single style sampler.

    Two filters run before an element is allowed on a page:

    1. `TEXT_BEARING` — a few library elements render their own copy, which no
       spec can edit. `colour_bar` is a labelled swatch strip ("grass green /
       overprint / rice white"), `issue_stamp` is "VOL. 03 / ISSUE 07 / MAR
       2024", `ransom_word` spells RETURN. Using one puts a stranger's sentence
       on the page.
    2. `circled_number` / `asterisk` / `mini_doodle` / `starburst_badge` draw a
       number or glyph the spec never chose — a "53" in a circle next to a page
       title is decoration made of a fact that does not exist. Sets that are
       decoration rather than data are curated per dialect in `ELEMENT_SETS`;
       anything not listed there falls back to the dialect pool as before.
    """
    def take(d, share):
        curated = ELEMENT_SETS.get(d)
        if curated:
            return [(role, n) for role, names in curated.items()
                    for n in names if n in E.REGISTRY and n not in TEXT_BEARING | NUMBER_BEARING] * (2 if share > 0.5 else 1)
        out = []
        for role, names in DIALECTS[d]["pools"].items():
            for n in names:
                if n in TEXT_BEARING or n in NUMBER_BEARING:
                    continue
                if n in E.REGISTRY:
                    out += [(role, n)] * (2 if share > 0.5 else 1)
        return out
    pool = take(primary, 1.0)
    pool += take(secondary, 0.0)
    # An intentionally empty pool is valid; no fallback adds unprovided copy.
    if candidates is not None:
        unknown=set(candidates)-set(E.REGISTRY)
        if unknown:raise ValueError(f'Unknown decoration candidates: {sorted(unknown)}')
        pool=[(r,n) for r,n in pool if n in candidates]
    unknown=set(exclusions)-set(E.REGISTRY)
    if unknown:raise ValueError(f'Unknown element exclusions: {sorted(unknown)}')
    return [(r,n) for r,n in pool if n not in exclusions]


def grammar_for(primary, secondary, print_grammar):
    """Print grammar is dialect-driven, not unconditional."""
    g = dict(DIALECTS[primary]["grammar"])
    if print_grammar == "none":
        return {"header": "none", "footer": "none", "reg_marks": False}
    if print_grammar == "full":
        g["header"] = g["header"] if g["header"] != "none" else "line"
        g["footer"] = "line"
    return g


# --------------------------------------------------------------- placement
def free_regions(text_rects, pad, bands=None, grid=6, canvas=None):
    """Legal placement rectangles for a page.

    Kept under its old name because callers import it, but it does NOT build a
    uniform grid. A 6x6 grid would cap every legal spot at one cell (~2.8% of
    the page), and most cells are clipped by the page title and the header/
    footer bands, so the composer would have almost nowhere to put decoration
    and would shrink every element to 1-3% of the page. The rectangles come
    from the real obstacle edges (see free_rects), and callers verify a
    candidate with `rect_clear` rather than by containment.
    """
    return free_rects(text_rects, pad, bands=bands, canvas=canvas)


def free_rects(text_rects, pad, bands=None,
               safety=None, min_w=40.0, min_h=32.0,
               limit=64, canvas=None):
    """Maximal empty rectangles on the page, in points, biggest first.

    The page is cut at every obstacle edge, so a page with a genuinely empty
    corner reports one large rectangle instead of a handful of clipped cells.
    Registration marks live 11-41pt from the edge, hence the `safety` inset.
    """
    canvas = canvas or DECK_CANVAS
    bands = bands or canvas.bands
    if safety is None:
        safety = (44.0,)*4 if canvas.artifact == "deck" else (0.0,)*4
    pad_l, pad_t, pad_r, pad_b = safety
    x0, y0 = pad_l, max(pad_t, bands[1])
    x1, y1 = canvas.width - pad_r, min(canvas.height - pad_b, bands[2])
    obstacles = [lay.inflate(r, pad) for r in text_rects]
    xs = sorted({x0, x1} | {min(max(v, x0), x1)
                            for r in obstacles for v in (r[0], r[2])})
    ys = sorted({y0, y1} | {min(max(v, y0), y1)
                            for r in obstacles for v in (r[1], r[3])})
    out = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            a, b, c, d = xs[i], ys[j], xs[i + 1], ys[j + 1]
            if c - a < min_w or d - b < min_h:
                continue
            cell = (a, b, c, d)
            if not any(lay.intersection(cell, o) for o in obstacles):
                out.append(cell)
    out.sort(key=lambda r: (lay.area(r), r[2] - r[0]), reverse=True)
    return out[:limit]


def rect_clear(rect, obstacles):
    """Is `rect` free of every obstacle?

    This, not containment in a free rectangle, is the real placement rule: a
    small element may sit in a gap that no maximal rectangle describes exactly,
    and the tool must not drop a perfectly legal spot just because the derived
    rectangle around it is bigger than the element.
    """
    return not any(lay.intersection(rect, o) for o in obstacles)


def largest_free_rect(rects, canvas=None):
    """Biggest legal rectangle, given a list of rectangles (largest first).

    A hero element wants a large share of the page, so the composer asks for the
    roomiest rectangle rather than one grid cell. Accepts either the rectangle
    list from `free_rects` or a legacy occupancy grid, so older callers keep
    working.
    """
    canvas = canvas or DECK_CANVAS
    if not rects:
        return None
    first = rects[0]
    if isinstance(first, (list, tuple)) and len(first) == 4 and all(
            isinstance(v, (int, float)) for v in first):
        return tuple(first)
    rows, cols = len(rects), len(rects[0])          # legacy boolean grid
    heights = [0] * cols
    best = (0, 0, 0, 0, 0)
    for rr in range(rows):
        for cc in range(cols):
            heights[cc] = heights[cc] + 1 if rects[rr][cc] else 0
        stack = []
        for cc in range(cols + 1):
            h = heights[cc] if cc < cols else 0
            start = cc
            while stack and stack[-1][1] > h:
                idx, hh = stack.pop()
                start = idx
                area = hh * (cc - idx)
                if area > best[0]:
                    best = (area, idx, rr - hh + 1, cc - idx, hh)
            stack.append((start, h))
    if best[0] == 0:
        return None
    _a, c0, r0, w, h = best
    return (c0 * canvas.width / cols, r0 * canvas.height / rows,
            (c0 + w) * canvas.width / cols, (r0 + h) * canvas.height / rows)


def _max_rot_bbox(rect, deg=7.0):
    """Outer bounding box of `rect` after a rotation of at most `deg`.

    qa.py judges a placed element with its rotated bounding box, so planning has
    to reserve that much room: an element that fits exactly, unrotated, reads as
    a 7pt invasion of the text protection zone once it is turned.
    """
    import math as _m
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    w, h = (x1 - x0) / 2.0, (y1 - y0) / 2.0
    t = _m.radians(abs(deg))
    c, s = abs(_m.cos(t)), abs(_m.sin(t))
    return (cx - (w * c + h * s), cy - (w * s + h * c),
            cx + (w * c + h * s), cy + (w * s + h * c))


def _anchor_gap(box, anchors, items):
    """Clearance between a candidate box and the nearest piece of copy.

    Used to find *marginal* spots: the legal rectangle that is farthest from
    everything the reader is looking at. Falls back to all text rects when no
    typed anchors exist (e.g. a caller that passed bare tuples).
    """
    refs = [a["rect"] for a in anchors] or [it["rect"] for it in items]
    best = 1e9
    for ar in refs:
        dx = max(ar[0] - box[2], box[0] - ar[2], 0.0)
        dy = max(ar[1] - box[3], box[1] - ar[3], 0.0)
        best = min(best, math.hypot(dx, dy))
    return best


def content_obstacles(slide, canvas=None):
    """Protect existing charts, connectors and images from automatic accents."""
    canvas=canvas or DECK_CANVAS
    items=[]
    for shape in slide.shapes:
        if getattr(shape,'has_text_frame',False) and shape.text.strip():
            continue
        rect=lay.obb(shape)
        # The full-page generated print plate is an underlay, not an obstacle.
        if lay.area(rect)>=canvas.area*.98:
            continue
        # Zero-height/width connectors still occupy their visible stroke.
        if lay.line_segment(shape):
            rect=lay.inflate(rect,2)
        items.append({'rect':rect,'text':'','size':0})
    return items


def plan_page(archetype, primary, secondary, scenario, rnd, text_rects,
              taken_area=0.0, protection=None, archetype_kind=None, canvas=None,
              exclusions=(), candidates=None, graphic_rect=None, graphic_element=None):
    """Decide what to draw on this page — delegates to place_decor.Placer.

    Anchor-first, never hole-filling: the whole protocol lives in place_decor
    (anti-clutter rules A–F) — tiered budgets from the page's real word count,
    one protagonist, grouped elements, function tags, and a quiet-zone
    invariant checked after every placement.

    `text_rects` may be bare (x0,y0,x1,y1) tuples — then the page counts as
    wordless (T0) — or dicts {"rect", "text", "size"} as build_deck produces
    from tm.audit().
    """
    import place_decor as pd
    canvas = canvas or DECK_CANVAS

    dens = DENSITY.get(scenario, DENSITY[DEFAULT_SCENARIO])
    kind = archetype_kind or archetype
    mood = kind in MOOD_ARCHETYPES

    items = []
    for t in text_rects:
        if isinstance(t, dict):
            items.append(t)
        else:
            items.append({"rect": tuple(t), "text": "", "size": 0.0})
    # the tier listens to the COPY, not the chrome: header/footer labels and
    # page numbers are not content words
    words = sum(pd.word_count(it.get("text", "")) for it in items if not it.get('duplicate_layer')
                if canvas.artifact == "poster" or
                50 <= (it["rect"][1] + it["rect"][3]) / 2.0 <= 478)

    placer = pd.Placer(items, scenario, primary, secondary, rnd,
                       words=words, taken_area=taken_area, mood=mood, canvas=canvas)
    valid=element_pool(primary,secondary,exclusions,candidates)
    allowed={name for _role,name in valid}
    placer._pools={key:[(role,name) for role,name in pool if name in allowed]
                   for key,pool in placer._pools.items()}
    placer.precise = DIALECTS[primary]["stroke"] == "precise"
    # the scenario profile stays as a second ceiling (rule B caps win when
    # tighter); chrome area counts into the budget (rule E)
    placer.area_cap = min(dens["max_area"], placer.area_cap)
    scale = dens["element_scale"] * DIALECTS[primary]["density_bias"]

    if graphic_rect:
        placer.place_composition(graphic_rect, graphic_element)
    att_lo, att_hi = dens["attached"]
    placer.attach(max_count=rnd.randint(att_lo, att_hi), element_scale=scale)
    placer.place_hero(element_scale=scale,
                      min_room=dens.get("hero_min_room", 0.12))
    placer.place_group(element_scale=scale)
    main_names={n for _,n in placer._pools['main']}
    for item in placer.placed:
        item['dialect']=primary if item['name'] in main_names else secondary
    return placer.placed


def apply_plan(slide, plan, theme, media_dir, seed=0, page=1):
    """Render each planned element to a PNG and drop it on the slide."""
    from pptx.util import Pt
    os.makedirs(media_dir, exist_ok=True)
    palette = {"inkA": theme.inkA, "inkB": theme.inkB, "paper": theme.paper}
    records = []
    for i, item in enumerate(plan):
        meta = E.REGISTRY[item["name"]]
        w = max(8.0, item["rect"][2] - item["rect"][0])
        h = max(8.0, item["rect"][3] - item["rect"][1])
        rng_seed = seed * 7919 + page * 131 + i
        # rule D: group members share one ink; ungrouped pieces may alternate
        ink_swap = (i % 2 == 1) if "ink" not in item else item["ink"] == "B"
        pal = dict(palette)
        if ink_swap:
            pal["inkA"], pal["inkB"] = palette["inkB"], palette["inkA"]
        try:
            img = E.render(item["name"], pal, size=(w, h), seed=rng_seed,
                           **item.get("kw", {}))
        except Exception as exc:                       # never break a deck for decoration
            records.append({"element": item["name"], "error": str(exc)[:80]})
            continue
        path = os.path.join(media_dir, f"p{page:02d}_{i}_{item['name']}.png")
        img.save(path, optimize=True)
        pic = slide.shapes.add_picture(path, Pt(item["rect"][0]), Pt(item["rect"][1]),
                                       Pt(img.width / E.SCALE), Pt(img.height / E.SCALE))
        if item.get("rot"):
            pic.rotation = item["rot"]
        cat = meta["category"]
        tag = {"collage": "A", "doodle": "B", "geometric": "C", "texture": "TEX",
               "print": "PRINT", "typography": "TYPE", "retro_ui": "UI"}.get(cat, cat)
        if cat not in ('texture','print'):
            tag=item.get('dialect',tag)
        try:
            group='/group='+str(item['group']) if item.get('group') else ''
            pic._element.nvPicPr.cNvPr.set("name", f"el[{tag}]{item['name']}"+group)
        except Exception:
            pass
        rec = {"element": item["name"], "category": cat, "dialect":tag,"role": item["role"],
               "rect": [round(v, 1) for v in item["rect"]],
               "rotation": round(item.get("rot", 0), 1),
               "file": os.path.basename(path)}
        if item.get("placement"):
            rec["placement"] = item["placement"]
        if item.get("anchor"):
            rec["anchor"] = item["anchor"]
        if item.get("function"):
            rec["function"] = item["function"]
        if item.get("group"):
            rec["group"] = item["group"]
        records.append(rec)
    return records


def history_path(skill_dir=None):
    # Keep the old argument for callers; it must never select a repo path.
    from state_paths import read_path
    return str(read_path("history.json"))


def plan_rhythm(pages):
    """Record source anchors and intended hierarchy without adding pages/copy.

    Explicit archetypes win. This plan deliberately does not claim to evaluate
    argument quality; claim/support/anchor are user-provided planning metadata.
    """
    out=[]
    for i,p in enumerate(pages,1):
        anchors={k:p[k] for k in ("quote","hero","thesis","turning_point")
                 if p.get(k)}
        out.append({"page":i,"archetype":p.get("archetype","data"),
                    "roles":p.get("planning",{}),"emphasis_candidates":anchors})
    return out


def load_history(skill_dir=None):
    p = history_path(skill_dir)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as fh:
                history = json.load(fh)
            if isinstance(history, dict) and isinstance(history.get("decks"), list):
                return history
        except Exception:
            pass
    return {"decks": []}


def append_history(skill_dir, record, keep=40):
    """Record the deck. Rebuilding the same deck (same title and seed) replaces
    its entry instead of adding one — otherwise a second build of the same spec
    counts its own predecessor as a "recent" deck, picks a different dialect, and
    stops being reproducible."""
    h = load_history(skill_dir)
    decks = h.setdefault("decks", [])
    key = (record.get("deck"), record.get("seed"))
    decks[:] = [d for d in decks if (d.get("deck"), d.get("seed")) != key]
    decks.append(record)
    h["decks"] = h["decks"][-keep:]
    from state_paths import write_json
    write_json('history.json',h)
