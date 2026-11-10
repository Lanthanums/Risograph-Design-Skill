#!/usr/bin/env python3
"""build_deck.py — render a riso deck from a JSON spec.

The page types are fixed implementations and the spec only supplies content:
re-writing the pptx plumbing per deck is exactly how a style drifts and how a
stray reference poster takes over a deck (there is nothing else to imitate).

  python build_deck.py --spec deck.json --out deck.pptx
  python build_deck.py --schema          # print the spec schema

Backgrounds are read from <meta.media>/bgN.(jpg|png); the matching manifest
(written by make_textures.py --manifest) tells us which pages are reversed so
the page chrome can switch to paper ink.

Spec
----
Placeholders below show shape, not copy — never lift wording from this docstring.

{
  "meta": {
    "title": "...", "lang": "zh", "scenario": "report",   # speech|report|course|proposal
    "palette": "G", "print_grammar": "light",             # full|light|none
    "seed": 1026, "total": 13,
    "media": "media", "bg_manifest": "media/manifest.json",
    "footer": "FOOTER TEXT",
    "header_right": "RIGHT HEADER LABEL",
    "notes_default": ""
  },
  "pages": [
    {"archetype": "cover", "notes": "Full supplied script for this page",  "question": ["Q：", "..."], "title": "...", "title_en": "...",
     "thesis": [["bold part", {"bold": true}], [" rest", {}]],
     "highlight": "bold part", "sticker": "Q3",
     "bullets": ["section one", "section two"], "aside": "( 2026 )"},
    {"archetype": "divider", "index": "01", "title": "...",
     "title_en": "SECTION", "aside": "( ... )"},
    {"archetype": "data",   "label": "METRIC - PERIOD",
     "hero": "00.0", "unit": " k", "caption": "...", "delta": "+00%",
     "delta_label": "QUARTER OVER QUARTER", "aside": "( ... )",
     "side": {"title": "...", "items": ["...", "..."]},
     "bars": [{"label": "Q1", "value": "00.0", "pct": 1.0, "color": "inkB"},
              {"label": "Q2", "value": "00.0", "pct": 2.0, "color": "inkA"}]},
    {"archetype": "features", "title": "...", "hero": "00%", "hero_label": "...",
     "hero_caption": "MOST-LOVED FEATURE",
     "rows": [{"label": "...", "pct": 33}], "aside": "..."},
    {"archetype": "quote",  "lines": ["...", "..."], "attribution": "...",
     "source": "...", "highlight": "..."},
    {"archetype": "grid",   "title": "...", "note": "...",
     "columns": [{"label": "us", "ours": true}, {"label": "A"}],
     "rows": [{"label": "...", "cells": [{"text": "00%", "size": 32, "ours": true},
                                         {"text": "00%", "size": 26}]}]},
    {"archetype": "venn",   "title": "...", "left": "...", "right": "...",
     "centre": "...", "gap_label": "...", "gap_items": ["..."], "takeaway": "..."},
    {"archetype": "numbered", "title": "...", "hero": "0.0%",
     "label": "...", "gauge": {"title": "...", "rows": [
        {"label": "...", "pct": 1.0, "color": "inkB", "value": "1.0%"}]},
     "takeaway": "...", "aside": "..."},
    {"archetype": "timeline", "title": "...", "subtitle": "...",
     "items": [{"month": "1", "unit": "月", "name": "...", "desc": "..."}]},
    {"archetype": "ask",    "title": "...", "asks": [
        {"value": "0", "unit": " unit", "name": "...", "desc": "..."}],
     "target": "...", "aside": "..."},
    {"archetype": "statement", "lines": [["...", 50]], "sticker": "01",
     "note": "...", "aside": "..."},
    {"archetype": "closing", "quote": "...", "target": "...", "big": "THANK YOU",
     "sticker": "Q & A"}
  ]
}
"""
import argparse
import glob
import json
import os
import sys

sys.dont_write_bytecode = True
from runtime import prepare
prepare()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import riso_kit as rk
import compose
import textmetrics as tm
import typefit as tf
import artifact_io as aio
from pathlib import Path
import shutil
import random
from riso_kit import (PAGE_W, PAGE_H, SAFE, MARGIN_L, MARGIN_R, FOOT_RULE_Y,
                      Theme, text, rect, oval, dashed, star4, freeform, label,
                      note, highlight, kicker, page_title, body, sticker,
                      rule, chrome, hero, stack, venn, set_notes,
                      add_page, new_deck)

KIND = {"ink": "ink", "inkA": "inkA", "inkB": "inkB", "ink_deep": "ink_deep",
        "text": "text", "paper": "paper", "tintA": "tintA", "accent1": "accent1",
        "accent2": "accent2"}

# `numbered` rows draw their bar from x=600 and their value text from x=732, so
# a bar longer than this would run under the value. Keep the two apart.
GAUGE_BAR_MAX = 128


def deck_language(spec):
    meta = spec.get('meta', {})
    explicit = meta.get('lang') or meta.get('language')
    if explicit:
        return explicit
    if any(page.get('modules') for page in spec.get('pages', [])):
        copy = json.dumps(spec.get('pages', []), ensure_ascii=False)
        return 'zh' if any('\u3400' <= char <= '\u9fff' for char in copy) else 'en'
    return 'zh'


def col(theme, name):
    return getattr(theme, KIND.get(name, "text"))


def find_bg(media, page):
    for ext in (".jpg", ".jpeg", ".png"):
        p = os.path.join(media, f"bg{page}{ext}")
        if os.path.exists(p):
            return p
    return None


def rich_runs(theme, items, size, color=None, font=None, ls=1.3):
    """[["text", {"bold": true}], ...] -> paragraph runs."""
    runs = []
    for item in items:
        if isinstance(item, str):
            runs.append((item, {}))
        else:
            t, over = item
            runs.append((t, over))
    return dict(runs=runs, font=font or theme.f_body, size=size,
                color=color or theme.text, ls=ls)


def flat(items):
    return "".join(i if isinstance(i, str) else i[0] for i in items)



def _latin(value):
    return sum(ord(ch)<0x2E80 for ch in str(value)) >= .6*max(1,len(str(value)))


def _shadow(theme,offsets=None):
    if offsets is not None:return max(abs(float(v)) for v in offsets)
    return lambda size: max(rk.misreg_offsets(size,'reverse' if theme.on_red else 'print'))


def fitted_text(slide,value,theme,x,y,w,h,size,minimum,role,index=None,
                font=None,bold=False,display=False,alignment='l'):
    f=tf.fit(value,font or theme.f_body,size,w,h,minimum=minimum,bold=bold,
             role=role,block_index=index,offset=_shadow(theme) if display else 0)
    tf.draw(slide,x,y,w,f,theme,role=role,block_index=index,
            display=display,alignment=alignment)
    return f


# --------------------------------------------------------------- archetypes
def p_cover(s, spec, th, idx, total, meta):
    x0,y0,x1,y1 = SAFE
    gap = 12
    cursor = y0 + 8
    if spec.get('question'):
        q = ''.join(spec['question'])
        f = tf.fit(q, th.f_body, 17, 740 if spec.get('sticker') else x1-x0, 52,
                   minimum=16, role='cover question')
        tf.draw(s,x0,cursor,x1-x0,f,th,role='cover-question')
        cursor += f.height+gap
    supports = []
    for role,value,size,font,minimum in (
        ('title_en',spec.get('title_en'),spec.get('title_en_size',58),th.f_display,28),
        ('thesis',flat(spec['thesis']) if spec.get('thesis') else None,24,th.f_body,18),
        ('bullets',' · '.join(spec.get('bullets',[])),16,th.f_body,14),
        ('subtitle',spec.get('subtitle'),20,th.f_body,16),
        ('aside',spec.get('aside'),spec.get('aside_size',14),th.f_label,spec.get('aside_size',13))):
        if value:
            fitted = tf.fit(value,font,size,x1-x0,130,minimum=min(minimum,size),role='cover '+role)
            supports.append((role,fitted))
    reserved = sum(f.height+gap for _,f in supports)
    title_w = 740 if spec.get('sticker') else x1-x0
    size = spec.get('title_size',154)
    available=y1-cursor-reserved-8
    if not supports:
        # Large multiline type still preserves the existing quiet-space floor.
        # Reserve that space before fitting; this is no decoration/fill quota.
        from place_decor import word_count,tier_of,TEXT_TIERS
        available-=PAGE_H*TEXT_TIERS[tier_of(word_count(spec.get('title','')))]['quiet']
    plates = getattr(th, 'deck_title_plates', None)
    offset = _shadow(th,spec.get('offsets'))
    if plates is not None:
        from deck_ink_render import allowance, draw
        offset = lambda size: allowance(th, size, plates)
    if getattr(th, 'deck_editorial', False):
        from deck_title_fit import fit as fit_title
        value = spec.get('title', '')
        phrases = spec.get('art_direction', {}).get('title_keep_phrases', ())
        f = fit_title(value, th.f_display, size, title_w, available,
                      minimum=min(size,42), ls=1.12, offset=offset, role='cover title',
                      keep_phrases=phrases)
        if len(f.lines) == 2 and '\n' not in value and f.width > title_w * .76:
            # A modest optical trim maintains the open right edge when a
            # semantic break makes the second line heavier than the first.
            trimmed = max(min(size, 42), f.size * .90, f.size * title_w * .76 / f.width)
            f = fit_title(value, th.f_display, trimmed, title_w, available,
                          minimum=trimmed, ls=1.12, offset=offset, role='cover title',
                          keep_phrases=phrases)
    else:
        f = tf.fit(spec.get('title',''), th.f_display if _latin(spec.get('title','')) else th.f_heading,
                   size,title_w,available,minimum=min(size,54),bold=True,
                   role='cover title',offset=offset)
    if plates is not None:
        draw(s, x0, cursor, title_w, f, th, plates, 'cover-title')
    else:
        tf.draw(s,x0,cursor,title_w,f,th,role='cover-title',display=True,
                offsets=spec.get('offsets'))
    cursor += f.height+gap
    for role,f in supports:
        shapes = tf.draw(s,x0,cursor,x1-x0,f,th,role='cover-'+role,
                         display=role=='title_en')
        if role=='thesis' and spec.get('highlight') and len(f.lines)==1:
            rk.highlight_word(s,shapes[-1],f.lines[0],spec['highlight'],th,
                              font=f.font,size=f.size,ls=f.ls)
        cursor += f.height+gap
    if spec.get('sticker'):
        sticker(s,820,26,150,100,spec['sticker'],th,size=50,rot=-5)


def p_divider(s, spec, th, idx, total, meta):
    x0, y0, x1, y1 = SAFE
    # a divider is meant to be reversed; if it is not, its type must be ink
    ink = th.display_ink
    stack(s, x0, y0 + 34, 500, 210,
          [(spec.get("index", "01"), th.f_display, spec.get("index_size", 168), False)],
          th, front=ink, back=th.back_ink, mid=None if not th.on_red else th.ink_deep,
          offsets=spec.get('offsets'))
    if getattr(th, 'deck_editorial', False):
        from deck_title_fit import fit as fit_title
        from deck_ink_render import allowance, draw
        plates = th.deck_title_plates
        f = fit_title(spec.get('title', ''), th.f_heading, 80, 700, 108, minimum=38,
                      offset=lambda size: allowance(th, size, plates), role='section title',
                      keep_phrases=spec.get('art_direction', {}).get('title_keep_phrases', ()))
        draw(s, x0, y0 + 242, 700, f, th, plates, 'divider-title', color=ink)
    else:
        stack(s, x0, y0 + 242, 700, 110,
              [(spec.get("title", ""), th.f_heading, 80, True)],
              th, front=ink, back=th.back_ink, mid=None, offsets=spec.get('offsets'))
    if spec.get("title_en"):
        label(s, x0 + 4, y0 + 354, 700, spec["title_en"], th, size=14,
              color=ink, spc=3.0)
    dashed(s, x0, y0 + 384, 540, y0 + 384, ink)
    if spec.get("aside"):
        # keep the aside on the left: reversed pages bleed an ink circle off the
        # bottom-right, and qa.py flags text sitting on top of it.
        # `aside_x` / `aside_y` let a spec move it when the flood reaches further
        # left than the default placement assumes.
        note(s, spec.get("aside_x", x0), y0 + spec.get("aside_y", 392), 540,
             spec["aside"], th, color=ink, align="l", size=14)
    if spec.get("star", True):
        star4(s, 866, y0 + 60, 42, fill=th.accent1, rot=12)


def p_data(s, spec, th, idx, total, meta):
    x0, y0, x1, y1 = SAFE
    label(s, x0, y0 + 2, 400, spec.get("label", ""), th, size=12)
    hero(s, x0, y0 + 20, 700, 190, spec.get("hero", ""), th,
         unit=spec.get("unit"), size=spec.get("hero_size", 148))
    if spec.get("caption"):
        fitted_text(s,spec['caption'],th,x0,y0+196,520,48,20,18,'data caption')
    dy = y0 + 250
    if spec.get("delta"):
        stack(s, x0, dy, 400, 90,
              [(spec["delta"], th.f_display, 62, False)], th,
              front=th.inkA, back=th.ink_deep, mid=None, offsets=spec.get('offsets'))
        if spec.get("delta_label"):
            label(s, x0, dy + 82, 260, spec["delta_label"], th, size=12)
    side = spec.get("side")
    if side:
        label(s, 600, y0 + 50, 312, side.get("title", ""), th, color=th.inkA, size=12)
        side_items=side.get('items',[])
        yy=y0+92
        side_end=y0+228-(30 if side.get('aside') else 0)
        for i, item in enumerate(side_items):
            rect(s, 600, yy + 6, 8, 8, fill=th.inkA)
            remain=len(side_items)-i
            item_height=(side_end-yy-8*(remain-1))/remain
            measured=fitted_text(s,item,th,620,yy,292,item_height,21 if th.lang == 'en' else 19,16,'data side item',i)
            yy+=measured.height+8
        dashed(s,600,yy+4,x1,yy+4,th.text)
        if side.get("aside"):
            fitted_text(s,side['aside'],th,600,yy+10,312,30,13,13,'data side aside')
    bars = spec.get("bars") or []
    if bars:
        top = y0 + 300
        peak = max(b["pct"] for b in bars) or 1
        for i, b in enumerate(bars):
            yy = top + i * 46
            colour = col(th, b.get("color", "inkB"))
            # stacked above its own bar: side by side the label ran into the
            # bar that starts at x=380
            label(s, 380, yy - 24, 330, b["label"], th, size=17 if th.lang == 'en' else 15, color=colour,
                  spc=1.0)
            w = 240 * (b["pct"] / float(peak))
            rect(s, 380, yy - 2, int(w), 22, fill=colour)
            fitted_text(s,b.get('value',''),th,748,yy-4,164,36,21 if th.lang == 'en' else 18,16,'data bar value',i)


def p_features(s, spec, th, idx, total, meta):
    x0, y0, x1, y1 = SAFE
    page_title(s, x0, y0 + 34, spec.get("title", ""), th, size=34)
    # left column: hero, its label, the caption, the aside note.
    # Rows live entirely on the right, starting below the page title.
    hero(s, x0, y0 + 88, 420, 150, spec.get("hero", ""), th,
         size=spec.get("hero_size", 104))
    hl = spec.get("hero_label", "")
    hl_w = spec.get("hero_label_w", 420)
    hsize = tm.fit_size(hl, th.f_heading, spec.get("hero_label_size", 26), hl_w)
    text(s, x0, y0 + 226, hl_w, 40, [dict(runs=[(hl, {})], font=th.f_heading,
                                          size=hsize, bold=True,
                                          color=th.text, ls=1.0)], wrap=False)
    if spec.get("hero_caption"):
        label(s, x0, y0 + 272, hl_w, spec["hero_caption"], th, color=th.inkA,
              size=12)
    if spec.get("list_title"):
        label(s, 430, y0 + 54, 482, spec["list_title"], th, color=th.inkA, size=12)
    rows = spec.get("rows") or []
    row_h = spec.get("row_h", 76)
    bar_w = spec.get("bar_w", 300)
    for i, r in enumerate(rows):
        # rows start below the page title so they never meet the label column
        yy = y0 + 120 + i * row_h
        # label, bar and value each get their own band or column: sharing a band
        # is what put the value label on top of the row label
        fitted_text(s,r['label'],th,430,yy-10,300,38,spec.get('row_label_size',19),16,'features row label',i)
        # bars are right-aligned inside the row column: extending them left from
        # x=430 ran them into the hero label on the other side of the page
        w = int(bar_w * r["pct"] / float(spec.get("row_scale", 41)))
        bar_x = spec.get("bar_right", 470) + spec.get("bar_max", 120) - w
        rect(s, bar_x, yy + 32, w, 18,
             fill=col(th, r.get("color", "inkB" if r["pct"] > 10 else "accent2")))
        # `value` lets a row show its real unit; without it the row shows its pct
        vtxt = str(r.get("value", f"{r['pct']}%"))
        v_x = 716
        v_avail = 916 - v_x
        vs = tm.fit_size(vtxt, th.f_display, 18, v_avail)
        text(s, v_x, yy + 26, v_avail, 26,
             [dict(runs=[(vtxt, {})], font=th.f_display, size=vs,
                   color=th.text, ls=1.0)], wrap=False)
    if spec.get("aside"):
        dashed(s, x0, y0 + 330, 380, y0 + 330, th.text)
        note(s, x0, y0 + 344, 380, spec["aside"], th, size=13)


def p_quote(s, spec, th, idx, total, meta):
    x0, y0, x1, y1 = SAFE
    if spec.get('editorial'):
        layout = spec.get('art_direction', {}).get('quote_layout', 'auto')
        if layout == 'classic':
            p_editorial_quote(s, spec, th)
        else:
            from deck_quote import candidates, draw
            layouts = candidates(spec['lines'], getattr(th, 'previous_quote_layout', None))
            if layout != 'auto':
                layouts = [layout, *[v for v in layouts if v != layout]]
            layout = draw(s, spec, th, layouts, idx)
        th.previous_quote_layout = layout
        if not hasattr(th, 'quote_compositions'):
            th.quote_compositions = []
        th.quote_compositions.append(dict(page=idx, layout=layout))
        return
    text(s, x0 + 48, y0 + 28, 200, 190,
         [dict(runs=[("\u201c", {})], font=th.f_label, size=150, color=th.inkA,
               ls=1.0)], wrap=False)
    lines = spec.get("lines", [])
    size = spec.get("size", 30)
    qy = y0 + 154
    support = (42 if spec.get('attribution') else 0) + (34 if spec.get('source') else 0) + 14
    fitted = tf.fit(lines, th.f_body, size, 760, y1-qy-support,
                    minimum=min(24,size), bold=True, ls=1.45, role='quote body')
    rect(s, x0 + 22, qy + 14, 5, max(8,fitted.height-14), fill=th.inkA)
    quote_shape = tf.draw(s, x0+62, qy, 760, fitted, th,
                          role='quote-body', color=th.front_ink)[0]
    if spec.get("highlight") and lines:
        rk.highlight_word(s, quote_shape, fitted.lines[0], spec["highlight"], th,
                          ls=fitted.ls, font=fitted.font, size=fitted.size, bold=fitted.bold)
    # Anchor the rule to the MEASURED glyph box, not to ls math: Noto Serif's
    # line box is ~1.3em, so ls=1.45 pitches lines at ~1.9x size and any fixed
    # formula eventually draws the rule through the last line.
    dy = tm.tight_rect(quote_shape, mode="ink")[3] + 14
    dashed(s, x0 + 62, dy, 820, dy, th.text)
    if spec.get("attribution"):
        text(s, x0 + 62, dy + 14, 700, 28, [dict(runs=[
            ("— ", dict(color=th.inkA)), (spec["attribution"], {})],
            font=th.f_body, size=17, color=th.text, ls=1.2)])
    if spec.get("source"):
        label(s, x0 + 62, dy + 48, 600, spec["source"], th, size=12)


def p_editorial_quote(slide, page, theme):
    """Measure a pull quote and its attribution as one vertical composition."""
    left, top, right, bottom = SAFE
    x = left + 54
    width = min(right - x - 8, 720)
    details = []
    for role, value, size in (
        ('quote-attribution', page.get('attribution'), 18),
        ('quote-context', page.get('source'), 16),
    ):
        if value:
            fitted = tf.fit(value, theme.f_body, size, width, 86,
                            minimum=size, role=role)
            details.append((role, fitted))

    mark = tf.fit('\u201c', theme.f_display, 88, 100, 150, minimum=88, role='quote mark')
    header_height = min(mark.height, 84)
    rule_gap = 17
    support_height = sum(fit.height + 8 for _, fit in details) + (rule_gap + 16 if details else 0)
    quote = tf.fit(page['lines'], theme.f_body, 40, width,
                   bottom - top - header_height - support_height - 18,
                   minimum=24, bold=True, ls=1.15, role='quote body')
    original_tail = ' '.join(tf.source_text(page['lines']).splitlines()[-1].split())
    if (len(quote.lines) > 1 and len(quote.lines[-1].split()) == 1
            and original_tail.endswith(' '.join(quote.lines[-2:]))):
        # Rebalance a wrapped final paragraph while preserving authored breaks.
        previous = quote.lines[-2].rsplit(maxsplit=1)
        if len(previous) == 2 and len(previous[0].split()) >= 2:
            tail = f'{previous[1]} {quote.lines[-1]}'
            if tm.advance(tail, quote.font, quote.size, quote.bold) <= quote.width:
                from dataclasses import replace
                quote = replace(quote, lines=(*quote.lines[:-2], previous[0], tail))
    group_height = header_height + quote.height + support_height
    y = top + (bottom - top - group_height) * .42
    accent = theme.display_ink if theme.on_red else theme.inkA
    mark_shape = tf.draw(slide, x, y, 100, mark, theme, role='quote-mark', color=accent)[0]
    if page.get('art_direction', {}).get('quote_screen', True):
        from deck_marks import quote_screen
        mark_ink = tm.tight_rect(mark_shape, mode='ink')
        quote_screen(slide, mark_ink[2] + 20, mark_ink[1], accent)
    y += header_height
    shape = tf.draw(slide, x, y, width, quote, theme, role='quote-body')[0]
    ink = tm.tight_rect(shape, mode='ink')
    rect(slide, x - 22, ink[1], 4, max(8, ink[3] - ink[1]), fill=accent)
    if details:
        y += quote.height + rule_gap
        dashed(slide, x, y, x + width, y, theme.front_ink)
        y += 16
        for role, fitted in details:
            tf.draw(slide, x, y, width, fitted, theme, role=role)
            y += fitted.height + 8


def p_grid(s, spec, th, idx, total, meta):
    x0,y0,x1,y1=SAFE
    page_title(s,x0,y0+34,spec.get('title',''),th,size=34)
    cols=spec.get('columns',[])
    weights=spec.get('column_weights',spec.get('weights',[c.get('weight',1) for c in cols]))
    if not isinstance(weights,(list,tuple)) or len(weights)!=len(cols) or not weights:
        raise ValueError('grid column_weights must match the nonempty columns')
    import math
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in weights):
        raise ValueError('grid column_weights must contain positive finite numbers')
    label_w=spec.get('label_w',200)
    widths=[(x1-x0-label_w-16)*v/sum(weights) for v in weights]
    xs=[]; x=x0+label_w+8
    for w in widths:
        xs.append(x); x+=w
    top=y0+88
    row_h=spec.get('row_h',72)
    rows=spec.get('rows',[])
    required=top+34+len(rows)*row_h+(48 if spec.get('note') else 0)
    if required>y1:
        raise ValueError(f'grid: {len(rows)} rows at {row_h:g}pt need {required-top:.1f}pt in {y1-top:.1f}pt; '
                         'reduce row_h or allocate the supplied rows across pages before adding a note')
    for i,c in enumerate(cols):
        if c.get('ours'):
            rect(s,xs[i],top+30,widths[i]-8,row_h*len(rows)+4,fill=th.inkA,alpha=12)
        fitted_text(s,c['label'],th,xs[i],top,widths[i]-8,30,19,16,'grid column',i,bold=True)
    for i in range(len(rows)+1):
        rule(s,x0,top+34+i*row_h,x1-x0,th.text)
    for ri,row in enumerate(rows):
        yy=top+34+ri*row_h+8
        fitted_text(s,row['label'],th,x0,yy,label_w-8,row_h-16,17,16,'grid row',ri)
        if len(row.get('cells',[]))>len(cols):
            raise ValueError(f'grid row {ri}: too many cells')
        for ci,cell in enumerate(row.get('cells',[])):
            sz=cell.get('size',17)
            fitted_text(s,cell['text'],th,xs[ci],yy,widths[ci]-8,row_h-16,sz,min(16,sz),
                        'grid cell',ri,font=th.f_display if sz>=24 else th.f_body,bold=bool(cell.get('ours')))
    if spec.get('note'):
        yy=top+34+len(rows)*row_h+12
        fitted_text(s,spec['note'],th,x0,yy,x1-x0,y1-yy,16,16,'grid note')


def p_venn(s, spec, th, idx, total, meta):
    x0,y0,x1,y1=SAFE
    page_title(s,x0,y0+34,spec.get('title',''),th,size=34)
    r=float(spec.get('r',90))
    c1=(290,y0+224);c2=(c1[0]+r*1.3,c1[1])
    venn(s,c1,c2,r,th,spec.get('left',''),spec.get('right',''),spec.get('centre',''))
    caption_y=c1[1]+r+8
    for role,cx in (('left_en',c1[0]-r*.55),('right_en',c2[0]+r*.55)):
        if spec.get(role):
            fitted_text(s,spec[role],th,cx-85,caption_y,170,28,16,16,'venn '+role,alignment='c')
    cursor=y0+116
    if spec.get('gap_label'):
        f=fitted_text(s,spec['gap_label'],th,634,cursor,278,42,17,16,'venn gap label',bold=True)
        cursor+=f.height+8
    for i,item in enumerate(spec.get('gap_items',[])):
        f=fitted_text(s,item,th,634,cursor,278,70,19,16,'venn gap item',i)
        cursor+=f.height+8
    # Caption and takeaway use independent bottom regions, outside the circles.
    bottom_top=max(caption_y+32,cursor+4)
    if spec.get('note'):
        f=fitted_text(s,spec['note'],th,x0,bottom_top,x1-x0,
                     (y1-bottom_top)*.55 if spec.get('takeaway') else y1-bottom_top,
                     16,16,'venn caption')
        bottom_top+=f.height+8
    if spec.get('takeaway'):
        fitted_text(s,spec['takeaway'],th,x0,bottom_top,x1-x0,y1-bottom_top,19,16,'venn takeaway')


def p_numbered(s, spec, th, idx, total, meta):
    x0,y0,x1,y1=SAFE
    page_title(s,x0,y0+34,spec.get('title',''),th,size=34)
    hero(s,x0,y0+94,500,190,spec.get('hero',''),th,size=spec.get('hero_size',150))
    if spec.get('label'):
        fitted_text(s,spec['label'],th,x0,y0+282,500,36,16,16,'numbered label')
    gauge=spec.get('gauge')
    if gauge:
        rows=gauge.get('rows',[])
        if len(rows)>4:
            raise ValueError('gauge supports at most four rows; reallocate content')
        fitted_text(s,gauge.get('title',''),th,600,y0+94,312,34,17,16,'gauge title',bold=True)
        top=y0+134
        bottom=y0+326
        row_h=(bottom-top)/max(1,len(rows))
        for i,g in enumerate(rows):
            yy=top+i*row_h
            fitted_text(s,g['label'],th,600,yy,312,row_h-18,17,16,'gauge label',i)
            gw=max(2,min(int(g.get('scale',120)*g['pct']),GAUGE_BAR_MAX))
            rect(s,600,yy+row_h-18,gw,12,fill=col(th,g.get('color','inkB')))
            if g.get('value'):
                fitted_text(s,g['value'],th,748,yy+row_h-24,164,24,17,16,'gauge value',i,font=th.f_display)
        if gauge.get('aside'):
            fitted_text(s,gauge['aside'],th,600,bottom+4,312,26,13,13,'gauge aside')
    yy=y0+360
    if spec.get('takeaway'):
        f=fitted_text(s,spec['takeaway'],th,600,yy,312,y1-yy,22,16,'numbered takeaway')
        yy+=f.height+8
    if spec.get('support'):
        fitted_text(s,spec['support'],th,600,yy,312,y1-yy,16,16,'numbered support')


def p_timeline(s, spec, th, idx, total, meta):
    x0,y0,x1,y1=SAFE
    page_title(s,x0,y0+34,spec.get('title',''),th,size=34)
    if spec.get('subtitle'):
        fitted_text(s,spec['subtitle'],th,x0,y0+82,700,64,19,16,'timeline subtitle')
    items=spec.get('items',[])
    span=780/max(len(items),1);tw=span-20
    line_y=y0+210
    rect(s,90,line_y,780,1.6,fill=th.text)
    for i,it in enumerate(items):
        cx=90+span*(i+.5);bx=cx-span/2+10
        fitted_text(s,str(it['month'])+(' '+it['unit'] if it.get('unit') else ''),th,
                    bx,line_y-70,tw,56,36,22,'timeline marker',i,font=th.f_heading,alignment='c')
        oval(s,cx-9,line_y-9,18,18,fill=th.inkA,line=th.text,lw=1)
        f=fitted_text(s,it['name'],th,bx,line_y+24,tw,66,23,18,'timeline name',i,bold=True,alignment='c')
        yy=line_y+24+f.height+8
        if it.get('desc'):
            fitted_text(s,it['desc'],th,bx,yy,tw,y1-yy,18,16,'timeline description',i)
    if spec.get('aside'):
        note(s,620,y0+44,292,spec['aside'],th,align='r',size=13)


def p_ask(s, spec, th, idx, total, meta):
    x0, y0, x1, y1 = SAFE
    page_title(s, x0, y0 + 34, spec.get("title", ""), th, size=34)
    asks = spec.get("asks", [])
    colw = (x1 - x0) / max(len(asks), 1)
    for i, a in enumerate(asks):
        ax = x0 + i * colw
        runs = [(a["value"], th.f_display, 96, False)]
        if a.get("unit"):
            runs.append((a["unit"], th.f_heading, 38, True))
        stack(s, ax, y0 + 98, colw - 40, 120, runs, th, offsets=spec.get('offsets'))
        # the column name is fitted at 26pt, but below 20pt it wraps to two
        # lines instead — shrinking further produced 12pt columns that still
        # ran off the canvas (LOOP p6)
        name_size = tm.fit_size(a["name"], th.f_heading, 26, colw - 40)
        if name_size >= 20.0:
            text(s, ax, y0 + 216, colw - 40, 34, [dict(runs=[(a["name"], {})],
                                                       font=th.f_heading,
                                                       size=name_size,
                                                       bold=True, color=th.text,
                                                       ls=1.0)], wrap=False)
            dy = y0 + 256
        else:
            # two lines at 18pt; real line pitch is ~1.8x the nominal size
            # (font line box x ls), so budget 32pt per line, not 26
            nl = _wrap_lines(a["name"], th.f_heading, 18, colw - 40)
            body(s, ax, y0 + 210, colw - 40, 32 * len(nl),
                 [[(piece, {"bold": True})] for piece in nl], th, size=18,
                 ls=1.3)
            dy = y0 + 210 + 32 * len(nl) + 6
        if a.get("desc"):
            # floor at the 16pt body minimum; when a target band claims the
            # bottom strip the column gets one desc line, not two
            room2 = dy + 66 <= (y0 + 330 if spec.get("target") else 470)
            dl = _wrap_lines(a["desc"], th.f_body, 16, colw - 40)
            body(s, ax, dy, colw - 40, 30 * len(dl), dl, th, size=16, ls=1.35)
            dy += 30 * len(dl) + 6
        if not spec.get("target") or dy <= y0 + 330:
            rule(s, ax, max(y0 + 288, dy), colw - 40, th.text)
    if spec.get("aside"):
        # title row: the bottom strip belongs to the columns and target band
        note(s, 620, y0 + 44, 292, spec["aside"], th, align="r", size=13)
    if spec.get("target"):
        rect(s, x0, y0 + 338, x1 - x0, 62, fill=th.inkA)
        runs = ([(spec.get("target_label", ""), dict(bold=True))]
                if spec.get("target_label") else [])
        runs.append((spec["target"], {}))
        text(s, x0 + 28, y0 + 338, x1 - x0 - 56, 62,
             [dict(runs=runs, font=th.f_body, size=22, color=th.paper, ls=1.0)],
             anchor="m")


def _wrap_lines(txt, family, size, max_w):
    return tf.lines_of(txt,family,size,max_w*.94)


def p_statement(s, spec, th, idx, total, meta):
    x0,y0,x1,y1=SAFE
    width=620 if spec.get('sticker') else x1-x0
    y=y0+36
    for i,item in enumerate(spec.get('lines',[])):
        txt,size=item if isinstance(item,list) else (item,44)
        f=fitted_text(s,txt,th,x0,y,width,132,size,min(size,34),'statement title',i,
                      font=th.f_heading,bold=True,display=True)
        y+=f.height+10
    if spec.get('body'):
        f=fitted_text(s,spec['body'],th,x0,y+10,min(width,spec.get('body_w',width)),
                      y1-y-70,22,18,'statement body')
        y+=f.height+20
    # Both rule endpoints and copy use measured geometry; sticker room is
    # reserved before fitting, rather than drawn over an already placed line.
    if spec.get('note'):
        dashed(s,x0,y+8,x0+width,y+8,th.front_ink)
        f=fitted_text(s,spec['note'],th,x0,y+22,width,y1-y-22,19,16,'statement note')
    if spec.get('sticker'):
        sticker(s,730,y0+176,176,118,spec['sticker'],th,size=34,rot=6)
    if spec.get('aside'):
        note(s,660,y0+330,252,spec['aside'],th,color=th.front_ink,align='r',size=13)



def p_closing(s, spec, th, idx, total, meta):
    x0,y0,x1,y1=SAFE
    width=620 if spec.get('sticker') else x1-x0
    cursor=y0+38
    # Reserve the real big-title and optional target before fitting the quote.
    big=spec.get('big','THANK YOU')  # legacy closing default
    bf=tf.fit(big,th.f_display,72,width,120,minimum=42,role='closing big',offset=_shadow(th))
    target=None
    if spec.get('target'):
        target=tf.fit(spec['target'],th.f_body,24,width,80,minimum=18,role='closing target')
    reserve=bf.height+32+(target.height+18 if target else 0)
    if spec.get('quote'):
        f=tf.fit(spec['quote'],th.f_heading,50,width,y1-cursor-reserve,minimum=28,
                 bold=True,role='closing quote',offset=_shadow(th))
        tf.draw(s,x0,cursor,width,f,th,display=True,role='closing-quote')
        cursor+=f.height+18
    if target:
        tf.draw(s,x0,cursor,width,target,th,role='closing-target')
        cursor+=target.height+18
    dashed(s,x0,cursor+2,x0+width,cursor+2,th.front_ink)
    tf.draw(s,x0,cursor+16,width,bf,th,display=True,role='closing-big')
    if spec.get('sticker'):
        sticker(s,730,y0+300,176,118,spec['sticker'],th,size=34,rot=6,
                fill=th.paper,line=th.ink,color=th.inkA)


def p_infographic(slide, spec, th, idx, total, meta):
    """Deck-specific planning and writing; shared evidence primitives remain read-only."""
    from deck_layout import make_plan
    from deck_renderer import apply_colors, draw
    if spec.get('chart_backend','shapes')!='shapes':raise ValueError('native charts are not validated; use chart_backend: shapes')
    direction=dict(spec.get('art_direction',{}));ladder=meta.get('type_scale',{})
    direction.setdefault('body_size',ladder.get('body',20));direction.setdefault('title_size',ladder.get('title',44))
    direction.setdefault('dialect',meta.get('evidence_dialect','swiss'));direction.setdefault('columns',min(2,len(spec['modules'])))
    direction.setdefault('autofit',True)
    direction['type_plates'] = getattr(th, 'deck_title_plates', None)
    direction['_editorial'] = getattr(th, 'deck_editorial', False)
    direction['_paper_mode'] = getattr(th, 'deck_paper_mode', 'off')
    modules=__import__('copy').deepcopy(spec['modules'])
    title=spec['title']
    charts=[m for m in modules if m.get('visual') in ('bar-compare','bar-vertical','line-chart','ring','stacked-bar')]
    if len(charts)==1:
        unit=charts[0].get('visual_data',{}).get('unit','')
        if unit and unit.lower() not in title.lower():title+=' ('+unit+')'
        charts[0]['render_unit_heading']=False
    for m in modules:
        if m.get('headline')==spec['title']:m['render_heading']=False
    candidate=dict(content=dict(title=title,modules=modules),
                        canvas=dict(width=PAGE_W,height=PAGE_H,safe=SAFE),
                        meta=dict(lang=meta.get('lang', th.lang),fonts=meta.get('fonts'),seed=meta.get('seed',1)),
                        evidence=spec.get('evidence',{}),art_direction=direction)
    paper_mode, body_size = direction['_paper_mode'], direction['body_size']
    paper_layout = direction.get('paper_layout', 'auto')
    attempts = [(paper_mode, paper_layout, body_size)]
    # Return the space reserved for the paper before shrinking body type.
    if paper_mode != 'off':
        if paper_layout != 'single' and any(m.get('visual') == 'takeaway-list' for m in modules):
            attempts.append((paper_mode, 'single', body_size))
        attempts.append(('off', 'single', body_size))
    if body_size > 18:
        attempts.append(('off', 'single', 18))
    for index, (mode, layout, size) in enumerate(attempts):
        direction.update(_paper_mode=mode, paper_layout=layout, body_size=size)
        first_shape = len(slide.shapes)
        palette = dict(th.t)
        try:
            plan = make_plan(candidate)
            apply_colors(plan, th)
            draw(slide, plan, th)
            if any(len(m.get('paper_panels', ())) > 1 for m in plan['module_metrics']):
                from layout_check import check_slide
                report = check_slide(slide, idx, archetype=spec['archetype'])
                if any(f.startswith('largest quiet rectangle') for f in report['fails']):
                    raise ValueError('Staggered paper cards leave too little quiet space')
        except ValueError:
            for shape in list(slide.shapes)[first_shape:]:
                shape._element.getparent().remove(shape._element)
            th.t.clear()
            th.t.update(palette)
            if index == len(attempts) - 1:
                raise
        else:
            if paper_mode != mode:
                plan['autofit']['changes'].append('Paper panel omitted to preserve measured list capacity')
            elif paper_layout != layout:
                plan['autofit']['changes'].append('One paper sheet retained to preserve measured list capacity')
            if body_size != size:
                plan['autofit']['changes'].append('Deck body fitted to the 18pt readability floor')
            break
    plan['source_modules']=spec['modules']
    if not hasattr(th,'evidence_pages'):th.evidence_pages=[]
    th.evidence_pages.append(dict(page=idx,plan=plan))


ARCHETYPES = {
    "cover": p_cover, "divider": p_divider, "data": p_data,
    "features": p_features, "quote": p_quote, "grid": p_grid, "venn": p_venn,
    "numbered": p_numbered, "timeline": p_timeline, "ask": p_ask,
    "statement": p_statement, "closing": p_closing, "infographic": p_infographic,"chart":p_infographic,"versus":p_infographic,
}


def page_writer(page, archetype):
    modules = page.get('modules', [])
    if not modules or archetype == 'cover' or page.get('editorial'):
        return ARCHETYPES[archetype]
    # A section label alone uses the classic reverse-number divider.
    if (archetype == 'divider' and len(modules) == 1 and
            not modules[0].get('body') and not modules[0].get('visual_data')):
        return p_divider
    return p_infographic


def draw_content(slide, page, theme, number, total, meta, writer, storyboard):
    try:
        writer(slide, page, theme, number, total, meta)
    except ValueError:
        from deck_press_chart import PRESS_FORMS
        if not storyboard or theme.lang != 'en' or writer is not p_infographic or not any(
                module.get('visual') in PRESS_FORMS for module in page.get('modules', [])):
            raise
        press = dict(page, art_direction=dict(page.get('art_direction', {}), _press_chart=True))
        writer(slide, press, theme, number, total, meta)


def write_style(out_path, spec, theme, manifest, extra=None):
    """style.json — what the deck is made of, so a later request ("change one
    page", "add two pages", "recolour") can stay consistent."""
    meta = spec.get("meta", {})
    style = {
        "skill": "riso-slides",
        "artifact": "deck",
        "canvas_spec": rk.DECK_CANVAS.to_dict(),
        "deck": meta.get("title", ""),
        "canvas": "960x540pt (13.333x7.5in), 16:9",
        "scenario": meta.get("scenario", "report"),
        "lang": meta.get("lang", "zh"),
        "palette": {"id": meta.get("palette", "G"), "tokens": theme.t},
        "fonts": theme.fonts, "font_diagnostics": theme.font_diagnostics,
        "print_grammar": theme.print_grammar,
        "seed": meta.get("seed"),
        "pages": [{"n": i, "archetype": p.get("archetype", "data")}
                  for i, p in enumerate(spec.get("pages", []), 1)],
        "reversed_pages": [p["page"] for p in (manifest or {}).get("pages", [])
                           if p.get("reversed")],
        # the anti-overfit contract: state where each ingredient came from
        "calibrated_from_reference": meta.get("calibrated_from_reference", []),
        "from_content": meta.get("from_content", []),
    }
    if extra:
        style.update(extra)
    return aio.write_style(out_path,style)


def check(spec):
    """Measure every page in memory; return all page failures in one call."""
    meta=spec.get('meta',{})
    theme=Theme(palette=meta.get('palette','G'),palette_hex=meta.get('palette_hex'),
                lang=deck_language(spec),fonts=meta.get('fonts'),print_grammar=meta.get('print_grammar','light'))
    results=[]
    for i,page in enumerate(spec.get('pages',[]),1):
        prs=new_deck();slide=add_page(prs,None)
        arch=page.get('archetype','data')
        try:
            if arch not in ARCHETYPES:raise ValueError(f'unknown archetype {arch!r}')
            theme.on_red=bool(page.get('reverse',arch in ('divider','closing')))
            draw_content(slide,page,theme,i,len(spec['pages']),meta,
                         page_writer(page, arch),bool(spec.get('storyboard')))
            results.append({'page':i,'archetype':arch,'ok':True,'slots':[
                {'role':t['shape'].name,'rect':[round(v,1) for v in t['rect']]} for t in tm.audit(slide)]})
        except (ValueError,KeyError,TypeError) as exc:
            results.append({'page':i,'archetype':arch,'ok':False,'error':str(exc)})
    return {'ok':bool(results) and all(r['ok'] for r in results),'pages':results}


def build(spec, out_path, base_dir=None):
    import metric_cache
    metric_cache.enable()
    if spec.get("artifact", "deck") != "deck":
        raise ValueError("Use build_poster.py for artifact=poster")
    meta = spec.get("meta", {})
    th = Theme(palette=meta.get("palette", "G"), palette_hex=meta.get("palette_hex"),
               print_grammar=meta.get("print_grammar", "light"),
               lang=deck_language(spec), fonts=meta.get("fonts"))
    if spec.get('storyboard') and th.lang.lower().startswith('en'):
        if 'heading' not in (meta.get('fonts') or {}):
            th.fonts['heading'] = th.f_display
        meta = dict(meta, fonts=th.fonts)
    out,sidecar,media=aio.paths(out_path)
    out.parent.mkdir(parents=True,exist_ok=True)
    manifest=None
    source=None
    if meta.get('media'):
        source=aio.input_path(meta['media'],base_dir,'deck media',directory=True)
    if source is not None:
        if source!=media:
            shutil.copytree(source,media,dirs_exist_ok=True)
    else:
        media.mkdir(parents=True,exist_ok=True)
        # A spec without prebuilt media still receives deterministic paper;
        # existing external background plans remain supported unchanged.
        import make_textures as mt
        from deck_print import page_field
        colors=meta.get('palette_hex').split(',') if meta.get('palette_hex') else mt.PALETTES[th.palette]
        ctx=mt.Ctx(PAGE_W,PAGE_H,2,colors)
        records=[]
        import hashlib
        for i,page in enumerate(spec.get('pages',[]),1):
            field = page_field(spec, page, i, th.lang == 'en')
            reverse = field['reverse']
            bg, treatment = mt.render_page(ctx, field, meta.get('seed', 1), i)
            bg_path=media/f'bg{i}.jpg';mt.save_img(bg,str(bg_path),'jpg',70)
            blob=bg_path.read_bytes()
            records.append({'page':i,'file':bg_path.name,'reversed':reverse,'bytes':len(blob),
                            'sha256':hashlib.sha256(blob).hexdigest()[:16],'treatment':treatment,**mt.ink_stats(bg)})
        manifest={'palette':th.palette,'tokens':th.t,'scale':2,'recommended_render_width':1920,'pages':records,'total_bytes':sum(r['bytes'] for r in records)}
        (media/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    manifest_path=aio.input_path(meta['bg_manifest'],base_dir,'background manifest') if meta.get('bg_manifest') else media/'manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest_path!=media/'manifest.json':shutil.copy2(manifest_path,media/'manifest.json')
    for i,_ in enumerate(spec.get('pages',[]),1):
        if not find_bg(media,i):raise ValueError(f'Missing input background for page {i}: {media}')
    reversed_pages = {p["page"] for p in (manifest or {}).get("pages", [])
                      if p.get("reversed")}

    # ---- dialect + density: decided once per deck, from content and scenario
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    history = compose.load_history(skill_dir, artifact="deck")
    scenario = meta.get("scenario", compose.DEFAULT_SCENARIO)
    blob = meta.get("title", "") + " " + " ".join(
        str(p.get(k, "")) for p in spec.get("pages", [])
        for k in ("title", "label", "question", "takeaway", "subtitle"))
    forced = None
    if meta.get("dialect"):
        d = meta["dialect"]
        forced = d if isinstance(d, list) else [d]
    primary, secondary, why = compose.pick_dialects(
        blob, scenario, meta.get("seed", 1), history, forced,
        self_key=(meta.get("title", ""), meta.get("seed")))
    meta=dict(meta,evidence_dialect=meta.get('evidence_dialect',{'A':'collage','B':'doodle','C':'swiss'}.get(primary,'swiss')))
    density = compose.DENSITY.get(scenario,
                                  compose.DENSITY[compose.DEFAULT_SCENARIO])
    density_level = compose.infer_density(scenario, meta.get("density"))
    rnd = random.Random(meta.get("seed", 1) * 31 + 7)
    th.grammar = compose.grammar_for(primary, secondary, th.print_grammar)
    want_elements = meta.get("elements", True) and scenario != "none"

    # rule E: the chrome set is chosen once, here, for the whole deck
    chrome_items = meta.get("chrome") or rk.CHROME_SETS.get(
        th.print_grammar, rk.CHROME_SETS["light"])
    chrome_ink = rk.chrome_area(chrome_items)

    pages = spec.get("pages", [])
    total = meta.get("total", len(pages))
    prs = new_deck()
    deck_records = []
    blocked_records = []
    impression_records = []
    collage_records = []
    auto_collage_pages = []
    from deck_refinements import featured_quote, revise, sparse_cutaway
    feature = featured_quote(pages, reversed_pages)
    rendered_quotes = []
    cutaway_pages = []
    refinement_colors = set()
    refinement_fallbacks = []
    from deck_print import chrome_foreground
    for i, page in enumerate(pages, 1):
        slide = add_page(prs, None)
        arch = page.get("archetype", "data")
        if arch not in ARCHETYPES:
            raise SystemExit(f"page {i}: unknown archetype {arch!r}; "
                             f"known: {sorted(ARCHETYPES)}")
        on_red = i in reversed_pages
        th.on_red = on_red
        direction = page.get('art_direction', {})
        th.deck_editorial = bool(spec.get('storyboard')) and th.lang == 'en'
        pool = page.get('element_pool', meta.get('element_pool'))
        paper_mode = direction.get('paper_collage', 'off' if pool == [] else 'auto')
        auto_available = (len(auto_collage_pages) < min(3, max(1, (total + 2) // 3))
                          and (not auto_collage_pages or auto_collage_pages[-1] != i - 1))
        th.deck_paper_mode = (paper_mode if th.deck_editorial and want_elements
                              and (paper_mode == 'on' or auto_available) else 'off')
        th.deck_title_plates = (direction.get('type_plates', 'spot' if arch == 'cover' or on_red else 'quiet')
                                if spec.get('storyboard') else None)
        chrome(slide, th, i, total, page.get("header_left", meta.get("header_left", "")),
               page.get("header_right", meta.get("header_right", "")),
               foot_left=meta.get("footer", ""), on_red=on_red,
               items=chrome_items,
               foreground=chrome_foreground(th) if on_red and th.lang == 'en' else None,
               right_cap=800.0 if arch == "cover" and page.get("sticker")
               else None)
        first_content_shape = len(slide.shapes)
        writer = page_writer(page, arch)
        try:
            draw_content(slide, page, th, i, total, meta, writer, th.deck_editorial)
        except ValueError as exc:
            raise ValueError(f"Deck slide {i} ({page.get('id', arch)}): {exc}") from exc
        original_content = list(slide.shapes)[first_content_shape:]
        evidence_pages = getattr(th, 'evidence_pages', [])
        metrics = evidence_pages[-1]['plan']['module_metrics'] if evidence_pages and evidence_pages[-1]['page'] == i else []
        panels = [panel for m in metrics for panel in m.get('paper_panels', [])]
        collage_records.extend(dict(panel, page=i, purpose='list-container') for panel in panels)
        if panels and th.deck_paper_mode == 'auto':
            auto_collage_pages.append(i)
        # Measure the actual furniture before protecting its background. A
        # footer number must not inherit the corner dot field beneath it.
        from PIL import Image
        from pptx.util import Pt
        import make_textures as mt
        import hashlib
        original = find_bg(media, i)
        regions = [r['rect'] for r in tm.audit(slide)]
        background = original
        treatment = next((row.get('treatment') for row in (manifest or {}).get('pages', []) if row['page'] == i), None)
        if regions and treatment != 'paper':
            background = str(media / f'bg{i}-chrome.jpg')
            with Image.open(original) as image:
                washed = mt.quiet_plate(image, regions, mt.hex2rgb(th.inkA if on_red else th.paper),
                                       mt.seed_for(meta.get('seed', 1), i), (PAGE_W, PAGE_H))
            washed.save(background, quality=90, subsampling=0)
            if manifest:
                record = next((p for p in manifest['pages'] if p['page'] == i), None)
                if record is not None:
                    data = Path(background).read_bytes()
                    record.update(file=Path(background).name, bytes=len(data),
                                  sha256=hashlib.sha256(data).hexdigest()[:16],
                                  chrome_quiet_regions=[list(r) for r in regions],
                                  **mt.ink_stats(washed))
        picture = slide.shapes.add_picture(background, Pt(0), Pt(0), prs.slide_width, prs.slide_height)
        slide.shapes._spTree.insert(2, picture._element)
        set_notes(slide, page.get("notes", meta.get("notes_default", "")))
        if want_elements:
            candidates = page.get('element_pool', meta.get('element_pool'))
            if candidates is None and page.get('composition') in ('classic-cover', 'editorial-quote'):
                candidates = []
            # pass the audit records, not bare rects: run sizes tell plan_page
            # which pieces of copy are anchors (title / big number / label) so
            # decoration can attach to the content instead of filling gaps
            enriched = []
            for t in tm.audit(slide, mode="ink"):
                sizes = [r.font.size.pt
                         for p in t["shape"].text_frame.paragraphs
                         for r in p.runs if r.font.size is not None]
                # Planner and renderer now share the same resolved language/font.
                enriched.append({"rect": t["rect"], "text": t["text"],
                                 "size": max(sizes) if sizes else 0.0,
                                 "duplicate_layer": 'riso-layer[back]' in t['shape'].name})
            enriched.extend(compose.content_obstacles(slide))
            plan = compose.plan_page(page.get("motif", arch), primary, secondary,
                                     scenario, rnd, enriched,
                                     taken_area=chrome_ink,
                                     archetype_kind=arch,
                                     exclusions=page.get('exclude_elements',meta.get('exclude_elements',[])),
                                     candidates=[] if panels else candidates)
            # Last deck-only protection gate for attached decorations.
            from place_decor import _rot_bbox
            import layout as deck_geometry
            blocked = [item for item in plan if page.get('modules') and any(
                deck_geometry.overlaps(_rot_bbox(item['rect'], abs(item.get('rot', 0)) + .5),
                                       region['rect'], pad=10)
                for region in enriched)]
            blocked_records.extend(dict(page=i, element=item['name'], rect=item['rect'], reason='planned text collision') for item in blocked)
            blocked_groups = {item['group'] for item in blocked if item.get('group')}
            plan = [item for item in plan if item not in blocked
                    and item.get('group') not in blocked_groups]
            before_elements = {shape.shape_id for shape in slide.shapes}
            recs = compose.apply_plan(slide, plan, th,
                                      os.path.join(media, "el"),
                                      seed=meta.get("seed", 1), page=i)
            pictures = [shape for shape in slide.shapes
                        if shape.shape_id not in before_elements and shape.shape_type == 13]
            successful = [record for record in recs if 'error' not in record]
            if len(pictures) != len(successful):
                raise ValueError('Deck decoration records do not match native pictures')
            kept = []
            for picture, record in zip(pictures, successful):
                if page.get('modules') and any(deck_geometry.overlaps(deck_geometry.obb(picture), region['rect'], pad=10)
                       for region in enriched):
                    blocked_records.append(dict(page=i, element=record['element'], rect=list(deck_geometry.obb(picture)), reason='native picture text collision'))
                    picture._element.getparent().remove(picture._element)
                else:
                    kept.append(record)
            recs = kept + [record for record in recs if 'error' in record]
            for r in recs:
                r["page"] = i
            deck_records += recs
        mark_density = direction.get('print_marks', 'off' if pool == [] else 'rich')
        if th.deck_editorial and want_elements and mark_density != 'off':
            from deck_impressions import plan_impressions
            from deck_impression_render import draw as draw_impression
            occupied = [record['rect'] for record in enriched if record['text']]
            occupied.extend(record['rect'] for record in compose.content_obstacles(slide))
            mark_page = dict(page, role='closing' if on_red and i == len(pages) else arch)
            if panels:
                mark_page['paper_collage_placed'] = True
                if mark_density == 'rich':
                    mark_density = 'balanced'
            if arch == 'quote' and getattr(th, 'previous_quote_layout', None) != 'classic':
                mark_page['art_direction'] = dict(direction, quote_screen=False)
            for number, mark in enumerate(plan_impressions(mark_page, occupied, SAFE, mark_density), 1):
                draw_impression(slide, mark, th, number)
                impression_records.append(dict(mark, page=i))
        if th.lang == 'en' and (th.deck_editorial or page.get('editorial')):
            result = revise(slide, page, th, i, total, meta, original_content, feature,
                            rendered_quotes[-1]['layout'] if rendered_quotes else None,
                            (writer, p_editorial_quote), media)
            refinement_colors.update(result.get('colors', ()))
            if result.get('fallback'):
                refinement_fallbacks.append(dict(page=i, reasons=result['fallback']))
            if result.get('quote'):
                rendered_quotes.append(dict(page=i, layout=result['quote']))
            if result.get('plan'):
                new_plan = result['plan']
                evidence_pages[-1]['plan'] = new_plan
                collage_records = [record for record in collage_records if record['page'] != i]
                collage_records.extend(dict(panel, page=i, purpose='list-container')
                                       for metric in new_plan['module_metrics']
                                       for panel in metric.get('paper_panels', []))
            cutaway_mode = direction.get('case_collage', 'auto')
            if (want_elements and pool != [] and (cutaway_mode == 'on' or
                    (len(cutaway_pages) < 2 and (not cutaway_pages or cutaway_pages[-1] < i-1)))):
                cutaway = sparse_cutaway(slide, page, th, meta.get('seed', 1)*131+i)
                if cutaway:
                    from deck_paper_collage import panel_color
                    refinement_colors.add(panel_color(th, 'list-paper-face', 'case'))
                    cutaway_pages.append(i)
                    collage_records.append(dict(cutaway, page=i))
    if manifest:
        manifest['total_bytes'] = sum(p.get('bytes', 0) for p in manifest['pages'])
        (media/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    th.t.update({f'local-refinement-{index}': color for index, color in
                 enumerate(sorted(refinement_colors-set(th.t.values())))})
    aio.save_pptx(prs,out_path)
    write_style(out_path, spec, th, manifest, {
        "dialect": {"primary": primary, "secondary": secondary, "chosen_by": why,
                    "name": f"{compose.DIALECTS[primary]['name']} + "
                            f"{compose.DIALECTS[secondary]['name']}"},
        "density": {"scenario": scenario, "level": density_level,
                    "band": compose.density_band(scenario,density_level,meta.get("word_band")),
                    **density},
        "elements": deck_records,
        "blocked_elements": blocked_records,
        "print_impressions": impression_records,
        "paper_collage": collage_records,
        "quote_compositions": rendered_quotes or getattr(th, 'quote_compositions', []),
        "refinement_fallbacks": refinement_fallbacks,
        "grammar": th.grammar,
        "rhythm_plan": compose.plan_rhythm(pages),
        "evidence_pages":getattr(th,'evidence_pages',[]),
    })
    aio.legacy_media_alias(out_path)
    compose.append_history(skill_dir, {
        "deck": meta.get("title", ""), "seed": meta.get("seed"),
        "scenario": scenario, "primary": primary, "secondary": secondary,
        "chosen_by": why,
        "motifs": [p.get("motif", p.get("archetype")) for p in pages],
        "hero_elements": sorted({r["element"] for r in deck_records
                                 if r.get("role") == "hero"}),
    }, artifact="deck")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="riso-slides deck builder")
    ap.add_argument("--spec", help="path to the deck JSON spec")
    ap.add_argument("--out", help="output .pptx path")
    ap.add_argument("--schema", action="store_true", help="print the spec schema")
    ap.add_argument('--check',action='store_true',help='measure all pages in memory without textures/files/state')
    ap.add_argument('--verbose',action='store_true')
    ap.add_argument("--design-system", action="store_true",
                    help="print the frozen design system as JSON "
                         "(colours, type scale, offsets, decoration, dot presets)")
    ap.add_argument('--content-plan')
    ap.add_argument('--skip-plan',action='store_true')
    args = ap.parse_args()
    if args.schema:
        print(__doc__.split("Spec\n----", 1)[1].strip())
        return 0
    if args.design_system:
        print(json.dumps(rk.design_system(), ensure_ascii=False, indent=2))
        return 0
    if not args.spec or (not args.out and not args.check):
        ap.error("--spec and --out are required (or use --schema / --design-system)")
    spec = json.load(open(args.spec, encoding="utf-8"))
    from deck_content_plan import gate
    gate(spec,args.content_plan,args.skip_plan,args.spec)
    if args.check:
        result=check(spec)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result['ok'] else 2
    path = build(spec, args.out, Path(args.spec).resolve().parent)
    print(f"saved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
