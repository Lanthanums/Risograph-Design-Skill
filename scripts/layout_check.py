#!/usr/bin/env python3
"""layout_check.py — parse a .pptx and grade every page's layout.

This is the quantitative conscience of the skill. qa.py checks pixels and
text fit; this script checks *composition*: who is the protagonist, how much
of the page is decoration, whether decoration collides with copy or chrome,
whether the quiet zone survived, whether fonts resolved, whether dialects
were mixed. Every number comes from the file itself, not from memory.

Usage:
    python layout_check.py --deck deck.pptx [--json report.json] [--quiet]

Exit code 0 = every page passed, 1 = at least one page failed.
"""
import argparse
import json
import re
import sys
import os
sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pptx import Presentation
from pptx.util import Emu

import layout as lay
import textmetrics as tm
import artifact_io as aio
from place_decor import TEXT_TIERS, TEXT_PAD, tier_of, word_count
from poster_layouts import TITLE_MIN_SHARE, TITLE_BODY_RATIO
from canvas import DECK_CANVAS, presentation_canvas
import rhythm

PAGE_W, PAGE_H = lay.PAGE_W, lay.PAGE_H
PAGE_AREA = PAGE_W * PAGE_H
EMU_PT = 12700.0

# chrome bands from the frozen grid (design-system.md)
HEAD_BAND = (DECK_CANVAS.bands[0], DECK_CANVAS.bands[1])
FOOT_BAND = (DECK_CANVAS.bands[2], DECK_CANVAS.bands[3])

# fonts the typography chain may legitimately resolve to (textmetrics.FONT_FILES)
ALLOWED_FONTS = set(tm.FONT_FILES) | {"Georgia", "Microsoft YaHei"}

MOOD_ARCHETYPES = {"cover", "statement", "quote", "closing", "divider"}
# Diagram/columnar pages tile the canvas with CONTENT (circles, bars, columns)
# by design: the quiet-rectangle metric inflates every label by 25.2pt and
# cannot tell a four-column timeline from clutter — it false-alarmed at 6% on
# pages that read airy (LOOP p4/p6). On these archetypes anti-clutter is
# policed by the decor area cap, overlap checks, and the foci count instead.
DIAGRAM_ARCHETYPES = {"venn", "data", "grid", "timeline", "ask", "features"}

# text-load tier -> (area cap, group cap, micro cap, quiet floor); the tiers
# themselves live in place_decor.TEXT_TIERS — one source of truth
_LO = {"T0": 0, "T1": 13, "T2": 36, "T3": 71}
TIERS = [(name, _LO[name], TEXT_TIERS[name]["hi"], TEXT_TIERS[name]["area"],
          TEXT_TIERS[name]["groups"], TEXT_TIERS[name]["micro"],
          TEXT_TIERS[name]["quiet"])
         for name in ("T0", "T1", "T2", "T3")]

WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[’'\-][A-Za-z0-9]+)*")
PAGE_NUM_RE = re.compile(r"^\s*\d{1,2}\s*[/／]\s*\d{1,2}\s*$")


def pt(v):
    return v / EMU_PT


def bbox(shape):
    return (pt(shape.left), pt(shape.top),
            pt(shape.left) + pt(shape.width), pt(shape.top) + pt(shape.height))


def words_of(text):
    return word_count(text)


def tier_for(words):
    for name, lo, hi, *rest in TIERS:
        if lo <= words <= hi:
            return (name, *rest)
    return ("T3", 0.08, 1, 1, 0.10)


def _runs(shape):
    for p in shape.text_frame.paragraphs:
        for r in p.runs:
            yield r


def _text_info(shape):
    """text, max font size, set of fonts, any unspecified font."""
    txt = '\n'.join(''.join(r.text for r in p.runs) for p in shape.text_frame.paragraphs)
    sizes, fonts, unspec = [], set(), False
    for r in _runs(shape):
        if r.font.size:sizes.append(r.font.size.pt)
        if r.font.name:fonts.add(r.font.name)
        elif r.text.strip():unspec=True
    return txt, (max(sizes) if sizes else 0.0), fonts, unspec


def _measured_lines(shape):
    """Measured wrapped-line count and required height for a text frame."""
    records=tm.line_records(shape)
    return len(records),sum(r['h']+r['before']+r['after'] for r in records)


def _clusters(rects, gap=36.0):
    """Union-find clustering of rects whose bboxes come within `gap`."""
    n = len(rects)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        parent[find(i)] = find(j)

    for i in range(n):
        a = lay.inflate(rects[i], gap / 2.0)
        for j in range(i + 1, n):
            if lay.intersection(a, lay.inflate(rects[j], gap / 2.0)):
                union(i, j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def _largest_empty(occupied, pad=0.0, canvas=None):
    """Largest empty axis-aligned rectangle on a 0.5in grid, as a page share."""
    canvas = canvas or DECK_CANVAS
    cell = min(18.0,canvas.width/4,canvas.height/4)
    cols, rows = int(canvas.width // cell), int(canvas.height // cell)
    grid = [[True] * cols for _ in range(rows)]
    for r in occupied:
        x0, y0, x1, y1 = lay.inflate(r, pad)
        c0 = max(0, int(x0 // cell))
        c1 = min(cols - 1, int((x1 - 1e-6) // cell))
        r0 = max(0, int(y0 // cell))
        r1 = min(rows - 1, int((y1 - 1e-6) // cell))
        for rr in range(r0, r1 + 1):
            for cc in range(c0, c1 + 1):
                grid[rr][cc] = False
    heights = [0] * cols
    best = 0
    for rr in range(rows):
        for cc in range(cols):
            heights[cc] = heights[cc] + 1 if grid[rr][cc] else 0
        stack = []
        for cc in range(cols + 1):
            h = heights[cc] if cc < cols else 0
            start = cc
            while stack and stack[-1][1] > h:
                idx, hh = stack.pop()
                start = idx
                best = max(best, hh * (cc - idx))
            stack.append((start, h))
    return best * cell * cell / canvas.area


def _merge_stack_layers(recs):
    """The misregistered title stack is 2-3 text boxes with identical text at
    slightly offset positions. For layout purposes it is ONE ink block."""
    out, used = [], set()
    for i, a in enumerate(recs):
        if i in used:
            continue
        group = [a]
        for j in range(i + 1, len(recs)):
            b = recs[j]
            if j in used or b["text"] != a["text"]:
                continue
            if not any('riso-layer[' in t['shape'].name for t in (a,b)):
                continue
            if (abs(a["rect"][0] - b["rect"][0]) <= 14
                    and abs(a["rect"][1] - b["rect"][1]) <= 14):
                group.append(b)
                used.add(j)
        keep = max(group, key=lambda r: r["z"])      # front layer
        x0 = min(g["rect"][0] for g in group)
        y0 = min(g["rect"][1] for g in group)
        x1 = max(g["rect"][2] for g in group)
        y1 = max(g["rect"][3] for g in group)
        keep = dict(keep)
        keep["rect"] = (x0, y0, x1, y1)
        keep["layers"] = len(group)
        out.append(keep)
    return out


def check_slide(slide, idx, primary=None, secondary=None, archetype=None,
                density_band=None, canvas=None, poster_policy=None):
    canvas = canvas or DECK_CANVAS
    PAGE_W,PAGE_H,PAGE_AREA = canvas.width,canvas.height,canvas.area
    HEAD_BAND,FOOT_BAND = (0,canvas.bands[1]),(canvas.bands[2],canvas.height)
    shapes = list(slide.shapes)
    texts, decor, chrome, bars, figures = [], [], [], [], []
    images = []
    for z, sh in enumerate(shapes):
        r = bbox(sh)
        name = ""
        try:
            name = sh.name or ""
        except Exception:
            pass
        if sh.shape_type == 13:                      # PICTURE
            if canvas.artifact == 'poster' and name == 'riso-paper[background]':
                continue  # verified separately against generated paper provenance
            if canvas.artifact == 'deck' and lay.area(r) > 0.92 * PAGE_AREA and not name.startswith(("el[","user-image[")):
                continue                             # background texture
            m = re.match(r"el\[([^\]]+)\](.+)", name)
            if m:
                decor.append({"rect": r, "name": m.group(2), "tag": m.group(1),
                              "kind": "element"})
            else:
                images.append({"rect": r, "name": name, "shape": sh})
            continue
        if getattr(sh, "has_text_frame", False) and sh.has_text_frame:
            txt, maxsz, fonts, unspec = _text_info(sh)
            if txt.strip():
                cy = (r[1] + r[3]) / 2.0
                is_chrome = (canvas.artifact == "deck" and
                             (cy < HEAD_BAND[1] or cy > FOOT_BAND[0])) or bool(
                             PAGE_NUM_RE.match(txt.strip())) or name.startswith("chrome[")
                rec = {"rect": r, "text": txt.strip(), "size": maxsz,
                       "fonts": sorted(fonts), "unspec": unspec, "z": z,
                       "wrap": bool(sh.text_frame.word_wrap),
                       "shape": sh,
                       "kind": "chrome" if is_chrome else "text"}
                (chrome if is_chrome else texts).append(rec)
                continue
        # autoshapes / connectors / freeforms without text
        w, h = r[2] - r[0], r[3] - r[1]
        thin = min(w, h) <= 2.5
        cy = (r[1] + r[3]) / 2.0
        in_band = cy < HEAD_BAND[1] or cy > FOOT_BAND[0]
        edge_mark = (min(r[0], PAGE_W - r[2]) < 44 and min(r[1], PAGE_H - r[3]) < 44
                     and max(w, h) < 60)
        if canvas.artifact == "deck" and (in_band or edge_mark):
            chrome.append({"rect": r, "text": "", "size": 0.0, "fonts": [],
                           "unspec": False, "z": z, "kind": "chrome"})
        elif name.startswith('information['):
            figures.append({'rect':r,'z':z})
        elif thin:
            # an in-body rule is content structure (grid lines, dividers),
            # not furniture — counting it as chrome false-alarms the 4-item
            # cap on every table page (LOOP p5)
            figures.append({"rect": r, "z": z})
        elif h >= 8 and w / max(h, 1e-6) >= 2.2:
            bars.append({"rect": r, "z": z})       # highlight bar / quote bar
        else:
            figures.append({"rect": r, "z": z})    # venn, bar_row, sticker fill

    words = sum(words_of(t["text"]) for t in texts)
    tier, area_cap, group_cap, micro_cap, quiet_min = tier_for(words)

    # The misregistered title stack is one ink block, not N text boxes.
    texts = _merge_stack_layers(texts)
    words = sum(words_of(t["text"]) for t in texts)
    tier,area_cap,group_cap,micro_cap,quiet_min = tier_for(words)
    # Judge text by where the glyphs actually are, not by the declared box —
    # declared boxes are intentionally oversized (no-wrap slack, stack slack).
    for t in texts:
        try:
            t["ink"] = tm.tight_rect(t["shape"], mode="ink")
        except Exception:
            t["ink"] = t["rect"]

    # --- overlaps -----------------------------------------------------------
    def hits(a_list, b_list, key_b="rect"):
        out = []
        for a in a_list:
            for b in b_list:
                if lay.intersection(a["rect"], b.get(key_b, b["rect"])):
                    out.append((a.get("name") or a.get("text", "")[:18]
                                or a["kind"],
                                b.get("name") or b.get("text", "")[:18]
                                or b["kind"]))
        return out

    ov_text = hits(decor, texts, key_b="ink")
    ov_chrome = hits(decor, chrome)

    # --- areas, groups, foci -------------------------------------------------
    decor_area = sum(lay.area(d["rect"]) for d in decor) / PAGE_AREA
    text_area = sum(lay.area(t["ink"]) for t in texts) / PAGE_AREA
    groups = _clusters([d["rect"] for d in decor]) if decor else []
    group_sizes = [sum(lay.area(decor[i]["rect"]) for i in g) / PAGE_AREA
                   for g in groups]
    # tier semantics (place_decor): a GROUP is 2-4 clustered pieces; a singleton
    # cluster is a standalone DETAIL. Counting singletons as groups (or group
    # members as micro details) double-counts and false-alarms dense tiers.
    multi_groups = [g for g in groups if len(g) >= 2]
    singles = [g for g in groups if len(g) == 1]
    foci = sum(1 for a in group_sizes if a >= 0.08)

    quiet = _largest_empty([lay.inflate(t["ink"], TEXT_PAD) for t in texts]
                           + [d["rect"] for d in decor]
                           + [c["rect"] for c in chrome]
                           + ([im["rect"] for im in images] if canvas.artifact == "poster" else []),
                           canvas=canvas)
    quiet_floor = None if archetype in DIAGRAM_ARCHETYPES else quiet_min
    if (canvas.artifact == "poster" and (poster_policy or {}).get("full_bleed_reason")
            and any(lay.area(im["rect"]) >= canvas.area*.98 for im in images)):
        quiet_floor = None

    # --- wrap / overflow ------------------------------------------------------
    wrap_issues = []
    for t in texts + [c for c in chrome if c["text"]]:
        lines, need_h = _measured_lines(t["shape"])
        box_h = t["rect"][3] - t["rect"][1]
        if not t["wrap"]:
            single = _line_width_of(t["shape"])
            if single > (t["rect"][2] - t["rect"][0]) * 1.02:
                wrap_issues.append(f"no-wrap line wider than box: "
                                   f"\"{t['text'][:24]}\"")
            glyphs=tm.glyph_rects(t['shape'])
            if glyphs and max(r[3] for r in glyphs)>t['rect'][3]+4:
                wrap_issues.append(f"no-wrap glyphs exceed box height: \"{t['text'][:24]}\"")
        else:
            glyphs=tm.glyph_rects(t['shape'])
            if glyphs and max(r[3] for r in glyphs)>t['rect'][3]+4:
                wrap_issues.append(f"text glyphs from {lines} measured lines exceed "
                                   f"a {box_h:.0f}pt box: \"{t['text'][:24]}\"")

    # --- highlight bars -------------------------------------------------------
    # A bar must cover the WORDS it sits behind, not merely fit inside the
    # line. Match the bar's x-range against measured word spans of the line
    # whose glyph band the bar overlaps; every covered word must end inside
    # the bar (±3pt), and the bar must not outrun the words either.
    bar_issues = []
    for b in bars:
        bx0, by0, bx1, by1 = b["rect"]
        for t in texts:
            if not lay.intersection(b["rect"], t["rect"]):
                continue
            spans = _word_spans(t["shape"])
            # the bar belongs to the line whose band contains its CENTRE —
            # edge-overlap (s1 <= by1) pulls the next line's words in when the
            # line pitch is tighter than the bar height (a known false alarm)
            bcy = (by0 + by1) / 2
            line = [s for s in spans if s[1] - 2 <= bcy <= s[3] + 2]
            covered = [s for s in line
                       if min(bx1, s[2]) - max(bx0, s[0]) > 0.4 * (s[2] - s[0])]
            if not covered:
                break
            need = (min(s[0] for s in covered), max(s[2] for s in covered))
            over = [s for s in line if s not in covered
                    and min(bx1, s[2]) - max(bx0, s[0]) > 3.0]
            if bx0 > need[0] + 3.0 or bx1 < need[1] - 3.0:
                bar_issues.append(
                    f"bar x {bx0:.0f}..{bx1:.0f} does not cover its words "
                    f"x {need[0]:.0f}..{need[1]:.0f}: \"{t['text'][:24]}\"")
            elif over:
                bar_issues.append(
                    f"bar spills onto \"{over[0][0] and over[0][4]}\": "
                    f"\"{t['text'][:24]}\"")
            break

    # --- fonts -----------------------------------------------------------------
    used = set()
    for t in texts + [c for c in chrome if c["text"]]:
        used.update(t["fonts"])
    bad_fonts = sorted(f for f in used if f not in ALLOWED_FONTS and not tm.resolve(f))
    unspec = any(t["unspec"] for t in texts)

    # --- dialects ---------------------------------------------------------------
    # Rule F: every decorative element belongs to the primary dialect; at most
    # ONE element per page may come from the secondary dialect. Texture and
    # print marks are dialect-neutral.
    tags = [d["tag"] for d in decor if d["tag"] not in ("TEX", "PRINT")]
    tagset = sorted(set(tags))
    mixed = False
    if primary:
        sec = sum(1 for t in tags if t != primary)
        distinct_off = sorted({t for t in tags if t != primary})
        mixed = sec > 1 or len(distinct_off) > 1
    else:
        mixed = len(tagset) > 1
    chrome_over = len(chrome) > 4

    # --- verdict ------------------------------------------------------------------
    fails, warns = lay.measured_issues(slide), []
    if ov_text:
        fails.append(f"decoration overlaps copy: {len(ov_text)} pair(s)")
    if ov_chrome:
        fails.append(f"decoration overlaps chrome: {len(ov_chrome)} pair(s)")
    if decor and decor_area > area_cap + 1e-9:
        fails.append(f"decoration {decor_area:.0%} over {tier} cap {area_cap:.0%}")
    if len(multi_groups) > group_cap:
        warns.append(f"{len(multi_groups)} decor groups over {tier} cap "
                     f"{group_cap}")
    if len(singles) > micro_cap:
        warns.append(f"{len(singles)} standalone details over {tier} cap "
                     f"{micro_cap}")
    if foci > 2:
        fails.append(f"{foci} visual foci (>=8% area) — more than protagonist "
                     f"+ one")
    # the 18pt quiet grid quantizes to ~0.35% steps; treat sub-0.5% shortfalls
    # as measurement noise, not clutter. Diagram/columnar pages are exempt
    # (see DIAGRAM_ARCHETYPES above).
    if quiet_floor is not None and quiet < quiet_floor - 0.005:
        fails.append(f"largest quiet rectangle {quiet:.0%} under "
                     f"{quiet_floor:.0%}")
    fails += wrap_issues
    bar_issues and warns.extend(bar_issues)
    if bad_fonts:
        fails.append(f"font(s) outside the spec chain: {bad_fonts}")
    unresolved = sorted(f for f in used if not tm.resolve(f))
    if unresolved:
        fails.append(f"unresolved font files: {unresolved}")
    if unspec:
        warns.append("some runs carry no explicit font (renderer default)")
    if mixed:
        fails.append(f"mixed dialects on one page: {tagset}")
    if chrome_over:
        warns.append(f"{len(chrome)} chrome items over the 4-item cap")
    if density_band and archetype and archetype not in MOOD_ARCHETYPES:
        lo, hi = density_band
        if words < lo * 0.75:
            warns.append(f"content page carries {words:.0f} words, below the "
                         f"{lo}-{hi} band — thin copy dilutes the deck")
        elif words > hi * 1.25:
            warns.append(f"content page carries {words:.0f} words, above the "
                         f"{lo}-{hi} band")

    if canvas.artifact == "poster":
        policy_fails,policy_warns = poster_checks(slide,texts,images,decor,chrome,
                                                 canvas,poster_policy or {})
        fails.extend(policy_fails)
        warns.extend(policy_warns)
        if bar_issues:
            fails.extend(bar_issues)
    # Horizontal chart bars are composition; highlight underlays are not.
    content_bars = [b for b in bars if not any(
        lay.intersection(b['rect'],t['ink']) for t in texts)]
    evidence = rhythm.composition(texts,figures+content_bars,images,canvas)
    return {
        "page": idx, "tier": tier, "words": round(words, 1),
        "archetype": archetype,
        **evidence,
        "max_font": max([t["size"] for t in texts], default=0.0),
        "decor": [{"name": d["name"], "tag": d["tag"],
                   "area": round(lay.area(d["rect"]) / PAGE_AREA, 4)}
                  for d in decor],
        "decor_count": len(decor), "decor_area": round(decor_area, 4),
        "chrome_count": len(chrome), "text_area": round(text_area, 4),
        "quiet_rect": round(quiet, 4), "groups": len(multi_groups),
        "details": len(singles), "foci": foci,
        "overlap_text": ov_text, "overlap_chrome": ov_chrome,
        "bar_issues": bar_issues, "fonts": sorted(used),
        "bad_fonts": bad_fonts, "mixed_dialects": tagset if mixed else [],
        "fails": fails, "warns": warns,
        "pass": not fails,
    }


def poster_checks(slide,texts,images,decor,chrome,canvas,policy):
    """Poster-specific measurable contract; uses the same page geometry."""
    import hashlib
    fails,warns=[],[]
    if chrome:
        fails.append('poster contains deck chrome/page number')
    for t in texts:
        role=t['shape'].name.split(']')[0].replace('poster[','')
        bounds=canvas.bounds if role in policy.get('text_bleed',[]) else canvas.safe
        if not lay.inside(t['ink'],bounds,tol=1.5):
            fails.append(f'poster {role} text violates safe/trim bounds')
    title=[t for t in texts if t['shape'].name.startswith('poster[title]')]
    body=[t for t in texts if t['shape'].name.startswith(('poster[body]','poster[block]','poster[metadata]'))]
    if not title:
        fails.append('poster title is missing')
    else:
        title_size=max(t['size'] for t in title)
        body_size=max([t['size'] for t in body],default=0)
        if title_size<min(canvas.width,canvas.height)*TITLE_MIN_SHARE:
            fails.append('poster title lacks distance scale')
        if body_size and title_size<body_size*TITLE_BODY_RATIO:
            fails.append('poster title/body hierarchy is too weak')
    if policy.get('protagonist') == 'image' and not images:
        fails.append('image-led poster has no treated image')
    if policy.get('full_bleed_reason') and not any(
            lay.area(im['rect'])>=canvas.area*.98 for im in images):
        fails.append('full-bleed exception requires a real full-bleed content image')
    records=policy.get('images',[])
    papers=[s for s in slide.shapes if s.shape_type==13 and s.name=='riso-paper[background]']
    if len(papers)!=1 or hashlib.sha256(papers[0].image.blob).hexdigest()!=policy.get('background_sha256'):
        fails.append('poster background has no verified generated-paper provenance')
    for sh in (im['shape'] for im in images):
        digest=hashlib.sha256(sh.image.blob).hexdigest()
        record=next((r for r in records if r.get('sha256')==digest),None)
        if not record or record.get('treatment')!='duotone_halftone':
            fails.append('user image has no verified duotone/print provenance')
    for im in images:
        full=lay.area(im['rect'])>=canvas.area*.98
        if any(lay.intersection(im['rect'],t['ink']) for t in texts) and not (
                full and policy.get('full_bleed_reason')):
            fails.append('content image illegally overlaps poster text')
        if not lay.inside(im['rect'],canvas.bleed_bounds,tol=1):
            fails.append('content image exceeds poster bleed')
    for sh in (s for s in slide.shapes if s.shape_type==13 and s.name.startswith('el[')):
        if not lay.inside(lay.obb(sh),canvas.bleed_bounds,tol=1):
            fails.append('decoration exceeds poster bleed')
    leads=[t for t in texts if t['size']==max([v['size'] for v in texts],default=0)]
    if leads:
        lead_area=sum(lay.area(t['ink']) for t in leads)
        if any(lay.area(d['rect'])>canvas.area*.08 and
               lay.area(d['rect'])>lead_area/3 for d in decor):
            fails.append('decoration competes with the typographic protagonist')
    return fails,warns


def _line_width_of(shape):
    """Measured width of the longest line of a text shape."""
    best = 0.0
    for p in shape.text_frame.paragraphs:
        w = 0.0
        for r in p.runs:
            if r.text:
                w += tm.advance(r.text, r.font.name or "Georgia",
                                r.font.size.pt if r.font.size else 18.0,
                                bool(r.font.bold))
        best = max(best, w)
    return best


def _word_spans(shape):
    """Measured (x0, y0, x1, y1, word) spans for every word, line by line.

    Only single-line paragraphs are spanned precisely; multi-line boxes use
    the greedy wrap estimate, which is what the bar matcher needs."""
    from typefit import TOKEN
    spans=[]
    for record in tm.line_records(shape):
        cx=record['x']
        for value,o in record['runs']:
            for match in TOKEN.finditer(value):
                token=match.group()
                if token.isspace():continue
                a=tm.advance(value[:match.start()],o['font'],o['size'],o['bold'],o['spc'])
                b=tm.advance(value[:match.end()],o['font'],o['size'],o['bold'],o['spc'])
                top,height=tm.ink_band(token,o['font'],o['size'],o['bold'])
                lead=max(0,(record['h']-tm.line_height(o['font'],o['size'],o['bold']))/2)
                yy=record['y']+lead+top
                spans.append((cx+a,yy,cx+b,yy+height,token))
            cx+=tm.advance(value,o['font'],o['size'],o['bold'],o['spc'])
    return spans


def main():
    ap = argparse.ArgumentParser(description="riso-slides layout checker")
    ap.add_argument("--deck", required=True)
    ap.add_argument("--json", help="write the full report here")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--primary", help="primary dialect letter (rule F)")
    ap.add_argument("--secondary", help="secondary dialect letter (rule F)")
    ap.add_argument("--artifact", choices=("deck", "poster"))
    ap.add_argument("--deck-level", action="store_true",
                    help="deck rhythm is included by default for deck artifacts")
    args = ap.parse_args()

    # a deck built by build_deck carries style.json beside it: dialects,
    # archetypes and the density level — read it instead of guessing
    archetypes, band, st = [], None, {}
    st=aio.read_style(args.deck)
    if st:
        d=st.get('dialect') or {}
        args.primary=args.primary or d.get('primary')
        args.secondary=args.secondary or d.get('secondary')
        archetypes=[p.get('archetype') for p in st.get('pages',[])]
        band=(st.get('density') or {}).get('band')
        if not band and (st.get('density') or {}).get('level'):
            import compose
            band=compose.DENSITY_LEVELS[st['density']['level']]['words']

    prs = Presentation(args.deck)
    if args.artifact:
        if st.get('artifact') and args.artifact!=st['artifact']:
            raise ValueError('Artifact conflicts with style metadata')
        st['artifact']=args.artifact
    canvas = presentation_canvas(prs,st)
    pages = [check_slide(s, i + 1, primary=args.primary,
                         secondary=args.secondary,
                         archetype=archetypes[i] if i < len(archetypes) else None,
                         density_band=band,canvas=canvas,
                         poster_policy=st.get('poster'))
             for i, s in enumerate(prs.slides)]
    report = {"deck": os.path.basename(args.deck), "pages": pages,
              "artifact":canvas.artifact,"canvas":canvas.to_dict(),
              "pass": all(p["pass"] for p in pages)}
    if canvas.artifact == 'deck':
        report['deck']=rhythm.check_deck(pages)
        report['file']=os.path.basename(args.deck)
        report['pass']=report['pass'] and report['deck']['pass']
    elif len(pages)!=1:
        report['pass']=False
        report['artifact_fails']=['poster must contain exactly one page']
    if args.json:
        json.dump(report, open(args.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    if not args.quiet:
        for p in pages:
            mark = "PASS" if p["pass"] else "FAIL"
            print(f"p{p['page']:02d} [{mark}] tier={p['tier']} "
                  f"words={p['words']:.0f} maxfont={p['max_font']:.0f} "
                  f"decor={p['decor_count']} ({p['decor_area']:.0%}) "
                  f"chrome={p['chrome_count']} foci={p['foci']} "
                  f"quiet={p['quiet_rect']:.0%} "
                  f"ovT={len(p['overlap_text'])} ovC={len(p['overlap_chrome'])}")
            for f in p["fails"]:
                print(f"     fail: {f}")
            for w in p["warns"]:
                print(f"     warn: {w}")
        print(f"deck: {'PASS' if report['pass'] else 'FAIL'}")
        for severity in ('fails','warns'):
            for message in (report.get('deck') or {}).get(severity,[]) if isinstance(report.get('deck'),dict) else []:
                print(f'     {severity}: {message}')
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
