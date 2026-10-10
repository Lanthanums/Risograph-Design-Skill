#!/usr/bin/env python3
"""qa.py — machine-checkable version of references/checklist.md.

A prose checklist ("网点不在正文后面", "对比度清晰", "大标题有 3 层错位") can only be
honoured by looking at rendered PNGs and guessing. Most of the items are
measurable; this script measures them.

  python qa.py --deck deck.pptx --media media [--render preview] [--json qa.json]

Without --render it runs the structural checks; with it, the pixel checks run
too (text overflow past the safe area, dot fields under body copy, highlight
bars that are not behind text, text/background contrast).

Exit code is non-zero if anything fails.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
sys.dont_write_bytecode = True

import numpy as np
from PIL import Image
from pptx import Presentation
from pptx.util import Pt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_textures as mt
import textmetrics as tm
import artifact_io as aio
import layout as lay
from canvas import DECK_CANVAS, presentation_canvas

# geometry mirror of riso_kit (kept in sync by tests/test_contract.py)
PAGE_W, PAGE_H = DECK_CANVAS.width, DECK_CANVAS.height
SAFE = DECK_CANVAS.safe
MARK_BAND = 46.0            # registration marks live inside this frame
CHROME_BAND = (DECK_CANVAS.bands[1], DECK_CANVAS.bands[2])
MIN_FONT = 12.0
MIN_BODY_FONT = 16.0
BODY_CHARS = 10
MAX_SHAPES = 34
MIN_LUM_DELTA = 60.0
MIN_GLYPH_DELTA = 45.0

NEUTRALS = {"FFFFFF", "000000", "2B2B2B", "1E1E1E"}


def lum(rgb):
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Report:
    def __init__(self):
        self.items = []
        self.notes = []
        self.pixel_checks = 'skipped'
        self.pixel_check_count = 0
        self.phase = 'structural'

    def note(self, detail):
        self.notes.append(detail)

    def add(self, ok, check, detail="", page=None, severity="fail"):
        self.items.append({"ok": bool(ok), "check": check, "detail": detail,
                           "page": page, "severity": severity if not ok else "ok",
                           'phase': self.phase, 'status': 'passed' if ok else severity})

    def exempt(self, check, detail, page=None):
        self.add(True, check, detail, page)
        self.items[-1].update(status='not_applicable', severity='skip')

    def failures(self):
        return [i for i in self.items if not i["ok"]]

    def print(self):
        # Console output must never abort the run: this is the step that happens
        # before --json is written, and on a GBK console a single non-encodable
        # character (a ¥ in a spec string, a ≤ in a message) would raise
        # UnicodeEncodeError and leave no report at all.
        try:
            sys.stdout.reconfigure(errors="replace")
        except Exception:
            pass
        for i in self.items:
            tag = 'SKIP' if i['status'] == 'not_applicable' else "ok  " if i["ok"] else ("warn" if i["severity"] == "warn" else "FAIL")
            where = f"p{i['page']:02d} " if i.get("page") else "deck "
            line = (f"  [{tag}] {where}{i['check']}"
                    + (f" — {i['detail']}" if i["detail"] else ""))
            try:
                print(line)
            except UnicodeEncodeError:
                enc = getattr(sys.stdout, "encoding", None) or "ascii"
                print(line.encode(enc, "replace").decode(enc, "replace"))
        for note in self.notes:
            print(f'  [NOTE] {note}')
        bad = [i for i in self.items if not i["ok"] and i["severity"] == "fail"]
        warn = [i for i in self.items if not i["ok"] and i["severity"] == "warn"]
        print(f"\n{len(bad)} failure(s), {len(warn)} warning(s), "
              f"{len(self.items)} check(s)")
        exempt = sum(i['status'] == 'not_applicable' for i in self.items)
        if exempt:
            print(f'{exempt} check slot(s) NOT APPLICABLE (reasons above); excluded from passed count')
        return 1 if bad else 0


def slide_colours(slide):
    out = set()
    for el in slide._element.iter():
        tag = el.tag.split("}")[-1]
        if tag == "srgbClr" and el.get("val"):
            out.add(el.get("val").upper())
    return out


def slide_fonts(slide):
    out = set()
    for el in slide._element.iter():
        tag = el.tag.split("}")[-1]
        if tag in ("latin", "ea", "cs") and el.get("typeface"):
            out.add(el.get("typeface"))
    return out


def text_shapes(slide):
    """Per text-bearing shape: geometry, text, max size, effective length, and
    whether every run is letter-spaced (i.e. a caps label, not body copy).

    `measure_w` is the width the glyphs actually occupy, taken from the same
    metrics call tm.audit makes. It matters because a text frame is usually much
    wider than its text (a right-aligned footer label declares 320pt and prints
    60pt), and anything that samples "the text box" would mostly sample page.
    """
    out = []
    records = tm.audit(slide, mode="ink")
    for sh in slide.shapes:
        if not sh.has_text_frame or not sh.text_frame.text.strip():
            continue
        txt = sh.text_frame.text.strip()
        # the glyph rectangle, from the audit record for this shape's own text.
        # Joining on the declared box is wrong in both axes: right-aligned text
        # prints at the far end of a wide frame, and aligned text starts offset,
        # so sampling "the text box" mostly samples page.
        glyph = None
        for rec in records:
            # python-pptx creates a fresh Shape proxy on each iteration. The
            # underlying XML element is stable; proxy identity silently misses
            # every record and samples the whole (often mostly empty) frame.
            if rec['shape']._element is not sh._element:
                continue
            r = rec["rect"]
            if glyph is None or (r[2] - r[0]) < (glyph[2] - glyph[0]):
                glyph = r
        if glyph is None:
            glyph = (sh.left.pt, sh.top.pt,
                     sh.left.pt + sh.width.pt, sh.top.pt + sh.height.pt)
        sizes, spc, lines = [], [], []
        pick_text, pick_rgb, pick_font, pick_bold = "", None, None, False
        for p in sh.text_frame.paragraphs:
            para = "".join(r.text for r in p.runs)
            if para:
                lines.append(para)
            for r in p.runs:
                if r.font.size:
                    sizes.append(r.font.size.pt)
                try:
                    spc.append(bool(r.font._rPr.get("spc")))
                except Exception:
                    spc.append(False)
                if len(r.text) > len(pick_text):
                    pick_text = r.text
                    pick_font = r.font.name
                    pick_bold = bool(r.font.bold)
                    try:
                        pick_rgb = hex2rgb(str(r.font.color.rgb))
                    except Exception:
                        pick_rgb = None
        txt = sh.text_frame.text.strip()
        cjk = len(re.findall(r"[\u3400-\u9fff]", txt))
        out.append({
            "x": sh.left.pt, "y": sh.top.pt, "w": sh.width.pt, "h": sh.height.pt,
            "measure_w": glyph[2] - glyph[0],
            "glyph": glyph,
            "text": txt, "size": max(sizes) if sizes else None,
            "chars": max(len(txt), int(cjk * 1.6)),
            "letterspaced": bool(spc) and all(spc),
            "shape": sh,
            "run_rgb": pick_rgb or hex2rgb("#2B2B2B"),
            "font": pick_font or "Noto Serif SC",
            "bold": pick_bold,
            "lines": lines or [txt],
            "runs": [[(r.text, r.font.name or "Noto Serif SC",
                       r.font.size.pt if r.font.size else 18,
                       bool(r.font.bold)) for r in p.runs]
                     for p in sh.text_frame.paragraphs if p.runs],
        })
    return out


def in_chrome_band(ts, canvas=None):
    canvas = canvas or DECK_CANVAS
    return bool(canvas.chrome_bands) and (
        ts["y"] < canvas.bands[1] or ts["y"] > canvas.bands[2])


def is_annotation(txt):
    """Bracketed asides / attribution dashes are labels, not body copy, even
    when they are long enough to trip the character count."""
    t = txt.strip()
    return t.startswith(("(", "（", "—", "–", "[", "【"))


def artifact_context(deck, prs, requested=None):
    style = aio.read_style(deck)
    if requested:
        if style.get("artifact") and style["artifact"] != requested:
            raise ValueError("Requested artifact conflicts with style metadata")
        style["artifact"] = requested
    return presentation_canvas(prs, style), style


def geometry_checks(rep, slide, i, args, canvas=None):
    """The defects that prompted these checks: text off the canvas, a caption
    colliding with a sticker, a highlight bar missing its word.

    All three are computed from real font metrics (textmetrics) and shape
    geometry (layout) — no image inspection, no model tokens.
    """
    canvas = canvas or getattr(args, "canvas", DECK_CANVAS)
    PAGE_W, PAGE_H = canvas.width, canvas.height
    texts = tm.audit(slide)
    for issue in lay.measured_issues(slide):
        rep.add(False,'measured line/circle geometry',issue,i)
    for t in texts:
        r = t["rect"]
        rep.add(lay.inside(r, (0, 0, PAGE_W, PAGE_H), tol=args.edge_tol),
                "text stays on the canvas",
                f"\"{t['text'][:16]}\" spans x {r[0]:.0f}..{r[2]:.0f} "
                f"(page 0..{PAGE_W:.0f})", i)
        rep.add(lay.inside(r, (4, 4, PAGE_W - 4, PAGE_H - 4), tol=args.edge_tol),
                "text inside the trim margin",
                f"\"{t['text'][:16]}\" y {r[1]:.0f}..{r[3]:.0f}", i, "warn")
        if canvas.artifact == "poster":
            role = t['shape'].name.split(']')[0].removeprefix('poster[')
            bleed_roles = (getattr(args, "style", {}).get("poster") or {}).get("text_bleed", [])
            allowed = canvas.bounds if role in bleed_roles else canvas.safe
            rep.add(lay.inside(r, allowed, tol=args.edge_tol),
                    "poster text respects safe/trim policy", t['text'][:24], i)
    # text must not sit on top of unrelated text (`layer_groups` first folds the
    # misregistered copies of one title into a single unit)
    for group in tm.layer_groups(texts):
        head = texts[group[0]]
        for j, other in enumerate(texts):
            if j in group:
                continue
            if lay.overlaps(head["rect"], other["rect"], pad=0.0):
                rep.add(False, "text blocks do not overlap",
                        f"\"{head['text'][:16]}\" vs \"{other['text'][:16]}\"", i)
                break
    # filled shapes: underlays and wraps are intentional, partial overlap is not
    solids = [s for s in slide.shapes if lay.is_solid(s) and s.shape_type != 13]
    for sh in solids:
        for t in texts:
            verdict = lay.classify_overlap(sh, t["rect"])
            if verdict == "collision":
                rep.add(False, "text does not clip decorations",
                        f"\"{t['text'][:18]}\" partially overlaps a "
                        f"{sh.shape_type} at ({sh.left.pt:.0f},{sh.top.pt:.0f}) "
                        f"size {sh.width.pt:.0f}x{sh.height.pt:.0f}", i)
                break
    # decorative element images must keep clear of copy
    for pic in (s for s in slide.shapes if s.shape_type == 13):
        if pic.width.pt >= PAGE_W - 2 and pic.height.pt >= PAGE_H - 2:
            continue                                   # the page background
        pr = lay.obb(pic)
        for t in texts:
            if lay.overlaps(pr, t["rect"], pad=args.text_protection):
                rep.add(False, "elements respect the text protection zone",
                        f"element at ({pr[0]:.0f},{pr[1]:.0f}) is within "
                        f"{args.text_protection:.0f}pt of \"{t['text'][:16]}\"", i)
                break
    # highlight bars must actually cover the words they mark
    from pptx.enum.dml import MSO_FILL
    accents = set()
    mf = os.path.join(args.media or "", "manifest.json")
    if os.path.exists(mf):
        with open(mf, encoding="utf-8") as fh:
            accents.add(json.load(fh)["tokens"]["accent1"].lstrip("#").upper())
    for sh in slide.shapes:
        try:
            if sh.fill.type != MSO_FILL.SOLID or not sh.has_text_frame:
                continue
            fill = str(sh.fill.fore_color.rgb).upper()
        except Exception:
            continue
        if accents and fill not in accents:
            continue
        # only a wide flat rectangle can be a highlight bar; the accent colour is
        # also used by starbursts and badges, which are not bars
        try:
            from pptx.enum.shapes import MSO_SHAPE
            if sh.auto_shape_type != MSO_SHAPE.RECTANGLE:
                continue
        except Exception:
            pass
        if sh.height.pt > 48 or sh.width.pt < 1.6 * sh.height.pt:
            continue
        bar = lay.obb(sh)
        host, best = None, 1e9
        for t in texts:
            r = t["rect"]
            if not (r[0] - 60 <= bar[0] and r[2] + 60 >= bar[2]):
                continue
            d = 0.0 if (bar[1] <= r[3] and bar[3] >= r[1]) else min(
                abs(bar[1] - r[3]), abs(r[1] - bar[3]))
            if d < best:
                best, host = d, t
        if host is None or best > max(18.0, host["rect"][3] - host["rect"][1]):
            continue
        r = host["rect"]
        if not (bar[0] >= r[0] - lay.HIGHLIGHT_SLOP
                and bar[2] <= r[2] + lay.HIGHLIGHT_SLOP):
            rep.add(False, "highlight sits within its line",
                    f"bar x {bar[0]:.0f}..{bar[2]:.0f} vs text x "
                    f"{r[0]:.0f}..{r[2]:.0f}", i)
        rep.add(bar[1] >= r[1] - 4 and bar[3] <= r[3] + 4,
                "highlight covers the line's glyph band",
                f"bar y {bar[1]:.0f}..{bar[3]:.0f} vs text y "
                f"{r[1]:.0f}..{r[3]:.0f}", i)


def budget_checks(rep, slide, i, args, canvas=None):
    """Element budget: few pieces, each with a legitimate place — attached to
    copy, on a margin, the one hero, or inside a large remaining gap — and the
    total inside the area budget."""
    canvas = canvas or getattr(args, "canvas", DECK_CANVAS)
    PAGE_W, PAGE_H = canvas.width, canvas.height
    deco = [s for s in slide.shapes
            if (s.shape_type == 13 and not (s.width.pt >= PAGE_W - 2
                                            and s.height.pt >= PAGE_H - 2)
                and not s.name.startswith("user-image["))]
    if not deco:
        return
    total = sum(lay.area(lay.obb(s)) for s in deco)
    frac = total / (PAGE_W * PAGE_H)
    rep.add(len(deco) <= args.max_elements, "element budget: not cluttered",
            f"{len(deco)} elements (max {args.max_elements})", i)
    rep.add(frac <= args.max_element_area, "element area budget",
            f"decoration covers {frac*100:.1f}% (max "
            f"{args.max_element_area*100:.0f}%)", i)
    if deco:
        # How large a hero *can* be is a property of the layout, not of the
        # scenario alone: a page whose text leaves 4% of itself empty cannot
        # carry a 22% element no matter what the density table says. The floor is
        # therefore raised only as far as the free space allows, and the report
        # says which limit applied.
        # heroes are optional by design (hero_min_room), so there is no
        # size floor any more — only the oversize cap remains. A page whose
        # largest element is small is not broken; it is quiet on purpose.
        hero = max(lay.area(lay.obb(s2)) for s2 in deco)
        rep.add(hero / (PAGE_W * PAGE_H) <= args.max_hero_area,
                "hero element is not oversized",
                f"largest element is {hero/(PAGE_W*PAGE_H)*100:.1f}% of the page "
                f"(max {args.max_hero_area*100:.0f}%)", i)
        # every piece of decoration must answer where it lives —
        #   attached:  next to the copy it punctuates (<= ATTACH_NEAR away)
        #   marginal:  far from all copy (>= 90pt), on the page's edge zone
        #   hero/free: the page's largest element, or inside a top-3 empty rect
        # Both ends are legal, the band between them is not: that is where
        # confetti lives, so nothing may land in "near" and "far" at once.
        try:
            import compose
            rects = [t["rect"] for t in tm.audit(slide, mode="ink")]
            gaps = compose.free_rects(rects, lay.TEXT_PROTECTION, canvas=canvas)[:3]
            biggest = max(lay.area(lay.obb(s2)) for s2 in deco)

            def gap_to(r, ob):
                dx = max(r[0] - ob[2], ob[0] - r[2], 0.0)
                dy = max(r[1] - ob[3], ob[1] - r[3], 0.0)
                return (dx * dx + dy * dy) ** 0.5

            for s2 in deco:
                ob = lay.obb(s2)
                match=re.search(r'/group=([^/]+)',s2.name)
                if match:
                    # A deliberately aligned group is anchored as one unit;
                    # collision and area checks still inspect every member.
                    members=[lay.obb(s) for s in deco if s.name.endswith('/group='+match.group(1))]
                    ob=(min(r[0] for r in members),min(r[1] for r in members),
                        max(r[2] for r in members),max(r[3] for r in members))
                d = min((gap_to(t, ob) for t in rects), default=1e9)
                ok = (d <= compose.ATTACH_NEAR or d >= 90.0
                      or lay.area(ob) >= biggest - 1e-6
                      or any(lay.intersection(ob, lay.inflate(g, 6.0))
                             for g in gaps))
                rep.add(ok, "decoration is anchored, marginal, or in a large gap",
                        f"element at ({ob[0]:.0f},{ob[1]:.0f}) hovers "
                        f"{d:.0f}pt off the copy in no large gap", i, "warn")
        except Exception:
            pass


def structural(rep, deck, media, spec, args):
    prs = Presentation(deck)
    args.canvas, args.style = artifact_context(deck, prs, getattr(args,"artifact",None))
    canvas = args.canvas
    PAGE_W, PAGE_H = canvas.width, canvas.height
    slides = list(prs.slides)
    rep.add(True, "deck opens and has slides", f"{len(slides)} slides")
    if args.expect_pages:
        rep.add(len(slides) == args.expect_pages, "slide count",
                f"{len(slides)} != expected {args.expect_pages}")
    if canvas.artifact == "deck" and (abs(PAGE_W-DECK_CANVAS.width)>1 or
                                      abs(PAGE_H-DECK_CANVAS.height)>1):
        rep.add(False, "canvas is 960x540pt",
                f"{prs.slide_width.pt:.0f}x{prs.slide_height.pt:.0f}")
    elif canvas.artifact == "deck":
        rep.add(True, "canvas is 960x540pt")
    else:
        rep.add(len(slides)==1, "poster is one page")
        rep.add(True, "poster canvas", f"{PAGE_W:.2f}x{PAGE_H:.2f}pt")

    allowed = set(NEUTRALS)
    if media:
        mf = os.path.join(media, "manifest.json")
        if os.path.exists(mf):
            tok = json.load(open(mf, encoding="utf-8")).get("tokens", {})
            allowed |= {v.lstrip("#").upper() for v in tok.values()}
    allowed |= {c.lstrip("#").upper() for c in args.extra_colors}

    all_fonts, page_no_re = set(), re.compile(r"^\s*\d{2}\s*/\s*\d{2}\s*$")
    for i, slide in enumerate(slides, 1):
        pics = [s for s in slide.shapes if s.shape_type == 13]
        bg_pics = [s for s in pics if s.width.pt >= PAGE_W - 2 and s.height.pt >= PAGE_H - 2]
        rep.add(len(bg_pics) >= 1, "page has a full-bleed background",
                f"{len(bg_pics)} of {len(pics)} pictures cover the page", i)
        rep.add(len(pics) <= args.max_shapes, "decoration budget (pictures)",
                f"{len(pics)} pictures (max {args.max_shapes})", i, "warn")
        cols = slide_colours(slide) - allowed
        rep.add(not cols, "palette compliance",
                f"off-palette colours: {sorted(cols)}", i)
        all_fonts |= slide_fonts(slide)
        nums = [s.text_frame.text for s in slide.shapes
                if s.has_text_frame and page_no_re.match(s.text_frame.text or "")]
        if canvas.artifact == "poster":
            rep.add(not nums, "poster has no deck page number", f"found {nums}", i)
        else:
            rep.add(len(nums) == 1, "page number present", f"found {nums}", i)
        if canvas.artifact == "deck" and (not slide.has_notes_slide or
                not slide.notes_slide.notes_text_frame.text.strip()):
            rep.add(False, "speaker notes", "empty", i, "warn")
        for ts in text_shapes(slide):
            if ts["size"] and ts["size"] < MIN_FONT:
                rep.add(False, "minimum font size", f"{ts['size']}pt < {MIN_FONT}",
                        i)
            if (ts["chars"] >= BODY_CHARS and ts["size"] and ts["size"] < MIN_BODY_FONT
                    and not is_annotation(ts["text"]) and not ts["letterspaced"]
                    and not in_chrome_band(ts, canvas)):
                rep.add(False, "body copy size",
                        f"{ts['size']}pt for {ts['chars']} chars "
                        f"(min {MIN_BODY_FONT}pt)", i)
        geometry_checks(rep, slide, i, args)
        budget_checks(rep, slide, i, args)
        if canvas.artifact=='poster':
            from layout_check import check_slide
            dialect=args.style.get('dialect',{})
            checked=check_slide(slide,i,canvas=canvas,poster_policy=args.style.get('poster',{}),
                                primary=dialect.get('primary'),secondary=dialect.get('secondary'))
            for failure in checked['fails']:
                rep.add(False,'poster measured policy',failure,i)
    unresolved=sorted(f for f in all_fonts if not tm.resolve(f))
    rep.add(not unresolved,'font resolution',str(unresolved))
    if args.expect_fonts:
        want = {f.strip() for f in args.expect_fonts.split(",") if f.strip()}
        unknown = all_fonts - want
        rep.add(not unknown, "fonts are the declared set",
                f"unexpected: {sorted(unknown)} (allowed {sorted(want)})")
    if media:
        mf = os.path.join(media, "manifest.json")
        if os.path.exists(mf):
            man = json.load(open(mf, encoding="utf-8"))
            pages = man["pages"]
            rev = [p["page"] for p in pages if p["reversed"]]
            # the 1-2 reversed pages convention exists for full decks; a tiny
            # test deck of 1-3 pages legitimately has none
            if canvas.artifact == "deck" and len(pages) >= 4:
                rep.add(1 <= len(rev) <= args.max_reversed, "1–2 reversed pages",
                        f"reversed: {rev}")
            hashes = [p["sha256"] for p in pages]
            dupes = [i + 1 for i in range(1, len(hashes)) if hashes[i] == hashes[i - 1]]
            rep.add(not dupes, "adjacent pages have different textures",
                    f"repeated on {dupes}")
            rep.add(len(set(hashes)) == len(hashes), "no duplicate page textures",
                    f"{len(set(hashes))}/{len(hashes)} unique", None, "warn")
            total = man.get("total_bytes", 0)
            rep.add(total < args.max_media_bytes, "background payload budget",
                    f"{total/1e6:.1f} MB (max {args.max_media_bytes/1e6:.0f} MB)",
                    None, "warn")


def pixel_checks(rep, deck, media, render, args):
    rep.phase = 'pixel'
    prs = Presentation(deck)
    canvas = getattr(args, "canvas", None) or presentation_canvas(prs)
    PAGE_W, PAGE_H = canvas.width, canvas.height
    SAFE = canvas.safe
    CHROME_BAND = (canvas.bands[1],canvas.bands[2])
    files = sorted(glob.glob(os.path.join(render, "page-*.png")))
    if not files:
        rep.add(False, "rendered previews", f"none in {render}")
        return
    rep.add(len(files) == len(prs.slides.__iter__.__self__._sldIdLst),
            "preview page count matches", f"{len(files)} images")
    # Which pages are floods? The dot-field check below assumes the reference
    # colour of a page is its paper, which fails on a reversed one: the whole
    # sheet is ink A, the median colour IS ink A, so the flood's own grain
    # measures as "background ink" (measured: 25.5% of a clean flood region
    # crosses the 25 threshold, 9.1% of it survives the median filter) and a
    # clean page gets flagged for a dot field it never had. Floods are exempted
    # and reported as such.
    reversed_pages = set()
    if media:
        mf0 = os.path.join(media, "manifest.json")
        if os.path.exists(mf0):
            reversed_pages = {p["page"] for p in
                              json.load(open(mf0, encoding="utf-8"))["pages"]
                              if p.get("reversed")}
    for i, f in enumerate(files, 1):
        img = Image.open(f).convert("RGB")
        w, h = img.size
        px = w / float(PAGE_W)
        bg = None
        cand = aio.background_file(media, i)
        if cand:
            bg = Image.open(cand).convert("RGB").resize((w, h), Image.LANCZOS)

        # --- content = render minus background -------------------------------
        if bg is not None:
            a = np.asarray(img).astype(np.int16)
            b = np.asarray(bg).astype(np.int16)
            content = np.abs(a - b).sum(axis=2) > 90
        else:
            content = mt.ink_mask(img, threshold=45)
        content_frac = float(content.mean())

        # (a) nothing but the page chrome may leave the safe area
        x0, y0, x1, y1 = [int(v * px) for v in SAFE]
        outside = content.copy()
        outside[y0:y1, x0:x1] = False
        # allow the header/footer bands and the registration-mark frame
        outside[:int(CHROME_BAND[0] * px), :] = False
        outside[int(CHROME_BAND[1] * px):, :] = False
        m = int(MARK_BAND * px)
        outside[:m, :] = outside[-m:, :] = False
        outside[:, :m] = outside[:, -m:] = False
        frac = float(outside.mean())
        if canvas.artifact == "deck":
            rep.add(frac < args.max_outside, "content stays in the safe area",
                    f"{frac*100:.2f}% of the page is ink outside the safe box", i)
        else:
            rep.exempt("poster raster bleed is allowed",
                    "text safe/trim policy is checked by geometry", i)

        # (b) dot fields must not sit under body copy. Exempt: chrome bands,
        #     bracketed annotations, display type (>24pt, where texture reads as
        #     texture rather than noise), and the generator's own registration
        #     marks. Letter-spaced caps labels warn instead of failing.
        if bg is not None and i in reversed_pages:
            rep.exempt("no dot field under body copy",
                    f"page {i} is a flood: dot-field coverage is not separable "
                    f"from the flood's own grain", i)
        elif bg is not None:
            bg_mask = mt.ink_mask(bg, threshold=25)
            bg_frac = float(bg_mask.mean())
            worst, worst_txt, worst_sev = 0.0, "", "fail"
            for ts in text_shapes(prs.slides[i - 1]):
                if ts["chars"] < BODY_CHARS or is_annotation(ts["text"]):
                    continue
                if ts["size"] and ts["size"] > 24:
                    continue
                if not args.strict_chrome and in_chrome_band(ts, canvas):
                    continue
                cx0 = max(0, int(ts["x"] * px)); cy0 = max(0, int(ts["y"] * px))
                cx1 = min(w, int((ts["x"] + ts["w"]) * px))
                cy1 = min(h, int((ts["y"] + ts["h"]) * px))
                if cx1 <= cx0 or cy1 <= cy0:
                    continue
                cell = bg_mask[cy0:cy1, cx0:cx1]
                if cell.size == 0:
                    continue
                frac_cell = float(cell.mean())
                if frac_cell > worst:
                    worst = frac_cell
                    worst_txt = ts["text"][:18]
                    worst_sev = "warn" if ts["letterspaced"] else "fail"
            rep.add(worst < args.max_bg_ink, "no dot field under body copy",
                    f"worst text box has {worst*100:.1f}% background ink "
                    f"(\"{worst_txt}\"; page background ink is {bg_frac*100:.1f}%)",
                    i, worst_sev)

        # Sampling the rendered page, not the background plate: the plate carries
        # no type, so sampling it reports every box as flat paper. Contrast is
        # measured between the glyphs and the pixels around them, never against
        # an assumed run colour — an assumption cannot see paper-coloured type
        # on a paper page.
        page_px = np.asarray(img)
        worst_delta, worst_txt = 999.0, ""
        for ts in text_shapes(prs.slides[i - 1]):
            gx0, gy0, gx1, gy1 = ts["glyph"]
            cx0 = max(0, int(gx0 * px)); cy0 = max(0, int(gy0 * px))
            cx1 = min(w, int(gx1 * px)); cy1 = min(h, int(gy1 * px))
            if cx1 - cx0 < 3 or cy1 - cy0 < 3:
                continue
            cell = page_px[cy0:cy1, cx0:cx1].reshape(-1, 3)
            lums = np.sort(cell @ np.array([0.2126, 0.7152, 0.0722]))
            n = max(1, len(lums) // 5)
            delta = float(lums[-n:].mean() - lums[:n].mean())
            if delta < worst_delta:
                worst_delta, worst_txt = delta, ts["text"][:18]
        if worst_txt:
            rep.add(worst_delta >= MIN_GLYPH_DELTA, "text is legible where it sits",
                    f"worst text box has {worst_delta:.0f} luminance spread "
                    f"(min {MIN_GLYPH_DELTA:.0f}) on \"{worst_txt}\"", i)

        # (d) a text box declared no-wrap must actually be wide enough for its
        # own line. PowerPoint breaks at the box width even with word_wrap off,
        # and auto_size=NONE keeps the frame height, so the overflow lands on the
        # next element. LibreOffice does not break, so this has to be measured.
        # Each run is measured in its own font and size: a misregistered title is
        # several boxes holding the same line, and one box may mix a display run
        # with a smaller unit run.
        for ts in text_shapes(prs.slides[i - 1]):
            if ts["shape"].text_frame.word_wrap is not False:
                continue
            widest = 0.0
            for para in ts.get("runs", []):
                widest = max(widest, sum(
                    tm.advance(t, fam, sz, bd) for t, fam, sz, bd in para))
            if widest > ts["w"] + 0.5:
                rep.add(False, "no-wrap text fits its own box",
                        f"\"{ts['text'][:18]}\" measures {widest:.0f}pt in a "
                        f"{ts['w']:.0f}pt box (breaks in PowerPoint)", i)


def pixel_inventory(deck, media):
    """Count the applicable scheduled pixel checks, without claiming execution.

    Additional no-wrap failures are reported when found; no-wrap fitting is also
    checked by the structural audit. Flood dot-field checks cannot distinguish
    ink from grain and are explicitly exempted by the existing pixel contract.
    """
    prs = Presentation(deck)
    count = 1  # preview page count
    for i, slide in enumerate(prs.slides, 1):
        count += 1  # safe area / poster bleed policy
        count += bool(text_shapes(slide))  # rendered glyph contrast
        count += aio.background_file(media, i) is not None
    return count


def preview_problem(deck, directory):
    """Require a complete, readable page sequence, never accept stale subsets."""
    if not directory:
        return 'no --render preview directory supplied'
    provenance=os.path.join(directory,'render.json')
    if os.path.isfile(provenance):
        try:
            with open(provenance,encoding='utf-8') as fh:
                data=json.load(fh)
            with open(deck,'rb') as fh:
                digest=hashlib.sha256(fh.read()).hexdigest()
            if data.get('source_sha256') != digest:
                return 'preview source hash does not match the PPTX; re-render this artifact'
        except (OSError,ValueError) as exc:
            return f'invalid preview provenance: {exc}'
    files = sorted(glob.glob(os.path.join(directory, 'page-*.png')))
    expected = len(Presentation(deck).slides)
    if len(files) != expected:
        return f'preview page count {len(files)} != {expected} in {directory}'
    try:
        numbers = [int(os.path.basename(f)[5:-4]) for f in files]
        if numbers != list(range(1, expected + 1)):
            return 'preview page sequence must be 1..N with no missing or duplicate pages'
        for f in files:
            with Image.open(f) as img:
                img.verify()
    except (OSError, ValueError) as exc:
        return f'invalid preview: {exc}'
    return None


def main():
    ap = argparse.ArgumentParser(description="riso-slides QA")
    ap.add_argument("--deck", required=True)
    ap.add_argument("--artifact", choices=("deck", "poster"), default=None)
    ap.add_argument("--media", default=None, help="background dir (with manifest.json)")
    ap.add_argument("--render", default=None, help="dir of page-*.png previews")
    ap.add_argument('--require-render', action='store_true',
                    help='CI gate: require complete existing previews; missing/invalid previews exit 3')
    ap.add_argument("--spec", default=None, help="deck JSON spec (unused checks skipped)")
    ap.add_argument("--json", default=None)
    ap.add_argument("--expect-pages", type=int, default=0)
    ap.add_argument("--expect-fonts", default="")
    ap.add_argument("--extra-colors", default="", help="comma hex list")
    ap.add_argument("--max-shapes", type=int, default=MAX_SHAPES)
    ap.add_argument("--max-reversed", type=int, default=2)
    ap.add_argument("--max-outside", type=float, default=0.004)
    ap.add_argument("--max-bg-ink", type=float, default=0.03)
    ap.add_argument("--max-media-bytes", type=float, default=6e6)
    ap.add_argument("--edge-tol", type=float, default=1.5,
                    help="how far text may stray past the canvas edge")
    ap.add_argument("--text-protection", type=float, default=9.0,
                    help="clear space decorative elements must leave around text")
    ap.add_argument("--max-elements", type=int, default=14)
    ap.add_argument("--max-element-area", type=float, default=0.35)
    ap.add_argument("--max-hero-area", type=float, default=0.60)
    ap.add_argument("--strict-chrome", action="store_true",
                    help="also check header/footer labels against dot fields")
    args = ap.parse_args()
    local_media=aio.paths(args.deck)[2]
    if local_media.is_dir():args.media=str(local_media)
    elif not args.media:args.media=str(aio.discover_media(args.deck))
    args.extra_colors = [c for c in args.extra_colors.split(",") if c]

    rep = Report()
    print(f"qa: {os.path.basename(args.deck)}")
    structural(rep, args.deck, args.media, args.spec, args)
    problem = preview_problem(args.deck, args.render)
    scheduled = pixel_inventory(args.deck, args.media)
    if args.render and not problem:
        rep.pixel_checks = 'run'
        before = len(rep.items)
        pixel_checks(rep, args.deck, args.media, args.render, args)
        rep.pixel_check_count = len(rep.items) - before
    else:
        rep.note(f'{scheduled} scheduled pixel checks SKIPPED ({problem}) — '
                 'legibility, dot-field and safe-area are UNVERIFIED, not passed')
        if args.render:
            rep.add(False, 'rendered previews', problem)
    rc = rep.print()
    if args.require_render and problem:
        print('error: --require-render requires real page previews. Run render.py '
              '--autodiscover (or --kit/--node) and supply --render; '
              'renderer discovery alone is not execution proof.', file=sys.stderr)
        rc = 3
    if args.json:
        json.dump({"deck": args.deck, "items": rep.items,
                   "failures": sum(i['status'] == 'fail' for i in rep.items),
                   'warnings': sum(i['status'] == 'warn' for i in rep.items),
                   'passed': sum(i['status'] == 'passed' for i in rep.items),
                   'not_applicable': sum(i['status'] == 'not_applicable' for i in rep.items),
                   'notes': rep.notes,
                   'pixel_checks': rep.pixel_checks,
                   'pixel_check_count': rep.pixel_check_count,
                   'pixel_checks_executed': sum(i['phase']=='pixel' and i['status']!='not_applicable' for i in rep.items),
                   'pixel_checks_scheduled': scheduled,
                   'verification': 'complete' if rep.pixel_checks == 'run' else 'incomplete'},
                  open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"report -> {args.json}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
