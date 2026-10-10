#!/usr/bin/env python3
"""textmetrics — real font metrics for layout decisions.

Why this exists
---------------
Three defects showed up in a produced deck: text ran off the canvas, a caption
collided with a sticker, and a highlight bar missed the word it was supposed to
sit behind. All three are geometry mistakes, and the old code made them
unavoidable because it never knew how wide text actually is — it carried a
hand-rolled `eta_width` estimate (CJK 1.0em, ASCII 0.55em) and declared text boxes
larger than their contents (`word_wrap=False`, `auto_size=NONE`), so neither the
builder nor the checker could tell where the glyphs really ended.

This module measures with the actual font files through Pillow/FreeType, so a
text run has a real bounding box before anything is drawn. Everything geometric
in the toolkit — highlight bars, element placement, overflow checks, collision
checks — is built on `tight_rect()`.

Cost model: measuring is arithmetic on the local machine. Checking a 13-page deck
costs a few hundred milliseconds and zero model tokens. Looking at 13 rendered
pages costs tens of thousands of tokens and is less reliable. So: measure with
code, render once for the pixel checks, and inspect representative renders for craft even when geometry passes.
"""
import sys
sys.dont_write_bytecode = True
import os
from pathlib import Path
from functools import lru_cache

from PIL import ImageFont

# family -> candidate font files, best first. Keep to OS-shipped faces plus the
# two Noto CJK faces the typography chain allows.
FONT_FILES = {
    "Arial Black": ["ariblk.ttf"],
    "Arial": ["arial.ttf", "arialbd.ttf"],
    "Impact": ["impact.ttf"],
    "Georgia": ["georgia.ttf", "georgiab.ttf"],
    "Microsoft YaHei": ["msyh.ttc", "msyhbd.ttc"],
    "SimHei": ["simhei.ttf"],
    "SimSun": ["simsun.ttc"],
    "Noto Serif SC": ["NotoSerifSC-VF.ttf"],
    "Noto Sans SC": ["NotoSansSC-VF.ttf"],
    "KaiTi": ["simkai.ttf"],
    "Noto Sans CJK SC": ["NotoSansCJK-Regular.ttc", "NotoSansCJK-Bold.ttc"],
    "Noto Serif CJK SC": ["NotoSerifCJK-Regular.ttc", "NotoSerifCJK-Bold.ttc"],
    "PingFang SC": ["PingFang.ttc"],
    "Songti SC": ["Songti.ttc"],
    "Heiti SC": ["STHeiti Light.ttc", "STHeiti Medium.ttc"],
    "DejaVu Sans": ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf"],
    "DejaVu Serif": ["DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf"],
    "Liberation Sans": ["LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"],
    "Liberation Serif": ["LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf"],
}
FONT_DIRS = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    os.path.expanduser("~/AppData/Local/Microsoft/Windows/Fonts"),
    "/System/Library/Fonts", "/Library/Fonts",
    "/usr/share/fonts", "/usr/share/fonts/truetype",
    "/usr/local/share/fonts", os.path.expanduser("~/.local/share/fonts"),
    os.path.expanduser("~/.fonts"), os.path.expanduser("~/Library/Fonts"),
]

_cache = {}
_resolved = {}
_faces = {}
_font_paths = None


def _paths():
    global _font_paths
    if _font_paths is None:
        _font_paths = sorted({str(p) for d in FONT_DIRS if Path(d).is_dir()
                              for p in Path(d).rglob('*')
                              if p.suffix.lower() in ('.ttf','.otf','.ttc','.otc')})
    return _font_paths


def _matching_face(path, family, bold):
    """Collections may put SC at an index other than zero. Match real names."""
    count = 64 if Path(path).suffix.lower() in ('.ttc','.otc') else 1
    candidates = []
    for index in range(count):
        try:
            face = ImageFont.truetype(path, 20, index=index)
            name, style = face.getname()
        except (OSError, ValueError):
            break
        # Some Windows fonts split the public family across family/style
        # metadata: ariblk.ttf reports ('Arial', 'Black'). This is an actual
        # face match, not a guessed substitution for a missing font.
        if family.casefold() in (name.casefold(), f'{name} {style}'.casefold()):
            is_bold = any(word in style.lower() for word in ('bold','black','heavy','semibold'))
            candidates.append((is_bold != bool(bold), index))
    return min(candidates)[1] if candidates else None


def resolve(family, bold=False):
    """Font file path for a family, or None."""
    key = (family, bool(bold))
    if key in _resolved:
        return _resolved[key]
    names = list(FONT_FILES.get(family, []))
    if bold and len(names) > 1:
        names = names[1:] + names[:1]
    preferred = [p for name in names for p in _paths()
                 if Path(p).name.casefold() == name.casefold()]
    found = None
    for p in preferred + [p for p in _paths() if p not in preferred]:
        index = _matching_face(p, family, bold)
        if index is not None:
            found = p
            _faces[key] = index
            # Prefer an actual bold face. The resolved path/index always names
            # a real font; callers may inspect its reported style.
            face = ImageFont.truetype(p, 20, index=index)
            if not bold or any(t in face.getname()[1].lower() for t in ('bold','black','heavy','semibold')):
                break
    _resolved[key] = found
    return found


def font(family, size, bold=False):
    key = (family, round(size, 1), bool(bold))
    if key not in _cache:
        path = resolve(family, bold)
        if not path:
            _cache[key] = None
            return None
        try:
            _cache[key] = ImageFont.truetype(path, max(1, int(round(size))),
                                           index=_faces.get((family,bool(bold)),0))
        except Exception:
            _cache[key] = None
    return _cache[key]


@lru_cache(maxsize=8192)
def advance(text, family, size, bold=False, spc=0.0):
    """Width of a string in points, including letter-spacing (`spc` in pt).

    Missing or unusable fonts fail; no synthetic width estimate is returned.
    """
    if not text:
        return 0.0
    spc = spc or 0.0
    f = font(family, size, bold)
    if f is None:
        raise ValueError(f'Font not resolvable for measurement: {family!r}')
    try:
        w = f.getlength(text)
    except Exception:
        raise ValueError(f'Font measurement failed: {family!r}')
    return w + spc * max(len(text) - 1, 0)


@lru_cache(maxsize=1024)
def line_height(family, size, bold=False, ls=1.0):
    """Ascender-to-descender height of one line at this size and line spacing."""
    f = font(family, size, bold)
    if f is None:
        raise ValueError(f'Font not resolvable for measurement: {family!r}')
    try:
        a, d = f.getmetrics()
        return (a + d) * ls
    except Exception as exc:
        raise ValueError(f'Font line metrics failed: {family!r}') from exc


def glyph_band(size, ls=1.0):
    """Kept for backwards compatibility — use ink_band(text, ...) instead."""
    return (ls - 1) * size / 2 + 0.10 * size, size * 0.98


def ink_band(text, family, size, bold=False, ls=1.0):
    """(offset from the line top, height) of the visible ink of `text`.

    Measured from the font's real bounding box, not from a ratio. Arial Black's
    caps start 0.39em below the line top, not 0.12em — an estimate that put the
    'ink' of a display line 20pt too high and made the collision checker report
    collisions that were not there, while hiding ones that were.
    """
    f = font(family, size, bold)
    if f is None:
        raise ValueError(f'Font not resolvable for measurement: {family!r}')
    try:
        a, d = f.getmetrics()
        line_h = (a + d) * ls
        lead = max(0.0, (line_h - (a + d)) / 2.0)
        bb = f.getbbox(text if text.strip() else "H")
    except Exception as exc:
        raise ValueError(f'Font ink metrics failed: {family!r}') from exc
    if not bb:
        return lead + a * 0.25, size * 0.72
    return lead + bb[1], max(2.0, float(bb[3] - bb[1]))


def fit_size(text, family, size, max_w, bold=False, spc=0.0, floor=8.0):
    """Shrink `size` until `text` fits `max_w`.

    Two defects came from never doing this: a 122pt cover title ran into the
    sticker beside it, and a 50pt closing line ran off the canvas. Display type
    is the one place where a long string is most likely, so it is measured and
    scaled here rather than discovered in a preview.
    """
    if max_w <= 0:
        return size
    w = advance(text, family, size, bold, spc)
    if w <= max_w:
        return size
    return max(floor, size * max_w / w)


def run_widths(runs, default_family, default_size, default_bold=False,
               default_spc=0.0):
    """Width of a paragraph made of [(text, opts), ...] runs."""
    total = 0.0
    for item in runs:
        if isinstance(item, str):
            text, opts = item, {}
        else:
            text, opts = item
        total += advance(text, opts.get("font", default_family),
                         opts.get("size", default_size),
                         opts.get("bold", default_bold),
                         opts.get("spc", default_spc) or 0.0)
    return total



def line_records(shape):
    """Measured visual lines, retaining mixed runs and explicit paragraphs."""
    tf=shape.text_frame
    bx,by=shape.left.pt+tf.margin_left.pt,shape.top.pt+tf.margin_top.pt
    bw=shape.width.pt-tf.margin_left.pt-tf.margin_right.pt
    bh=shape.height.pt-tf.margin_top.pt-tf.margin_bottom.pt
    records=[]
    from typefit import wrap_runs
    for p in tf.paragraphs:
        runs=[(r.text,dict(font=r.font.name or 'Georgia',size=r.font.size.pt if r.font.size else 18,
                          bold=bool(r.font.bold),spc=_spc(r))) for r in p.runs]
        if not runs:runs=[('',dict(font='Georgia',size=18,bold=False,spc=0))]
        ls=p.line_spacing if isinstance(p.line_spacing,float) else 1.
        align=str(p.alignment).split(' ')[0].lower() if p.alignment is not None else 'left'
        # Shared breaker for wrapped paragraphs. Explicitly fitted text uses
        # one native paragraph per measured line, with wrapping disabled.
        visual=[runs]
        if tf.word_wrap:
            try:visual=wrap_runs(runs,bw)
            except ValueError:visual=[runs]  # keep overflow visible to QA
        for vr in visual:
            height=max(line_height(o['font'],o['size'],o['bold'],ls) for _,o in vr)
            if hasattr(p.line_spacing,'pt'):height=p.line_spacing.pt
            records.append(dict(runs=vr,w=run_widths(vr,'Georgia',18),h=height,
                                align=align,before=p.space_before.pt if p.space_before else 0,
                                after=p.space_after.pt if p.space_after else 0))
    total=sum(r['h']+r['before']+r['after'] for r in records)
    anchor=str(tf.vertical_anchor).split(' ')[0].lower()
    y=by+((bh-total)/2 if anchor=='middle' else bh-total if anchor=='bottom' else 0)
    for r in records:
        y+=r['before']
        r['x']=bx+((bw-r['w'])/2 if r['align']=='center' else bw-r['w'] if r['align']=='right' else 0)
        r['y']=y
        y+=r['h']+r['after']
    return records


def glyph_rects(shape):
    """Per-character visible rectangles at their effective measured positions.

    Whitespace has no glyph. This lets a line pass through empty gaps rather
    than treating an entire paragraph AABB as printed ink.
    """
    out=[]
    for record in line_records(shape):
        x,y=record['x'],record['y']
        for value,o in record['runs']:
            face=font(o['font'],o['size'],o['bold'])
            if face is None:raise ValueError(f"Unresolved glyph font {o['font']!r}")
            for i,ch in enumerate(value):
                if ch.isspace():continue
                bb=face.getbbox(ch)
                pre=advance(value[:i],o['font'],o['size'],o['bold'],o['spc']) + (o['spc'] if i else 0)
                lead=max(0,(record['h']-line_height(o['font'],o['size'],o['bold']))/2)
                out.append((x+pre+bb[0],y+lead+bb[1],x+pre+bb[2],y+lead+bb[3]))
            x+=advance(value,o['font'],o['size'],o['bold'],o['spc'])
    return out


def tight_rect(shape, mode='box', protection=0.):
    records=line_records(shape)
    if mode=='ink':
        rects=glyph_rects(shape)
    else:
        rects=[(r['x'],r['y'],r['x']+r['w'],r['y']+r['h']) for r in records]
    if not rects:return None
    return (min(r[0] for r in rects)-protection,min(r[1] for r in rects)-protection,
            max(r[2] for r in rects)+protection,max(r[3] for r in rects)+protection)


def ink_rect(shape, protection=0.0):
    return tight_rect(shape, mode="ink", protection=protection)


def sub_rect(rect, full_text, target, family, size, bold=False, ls=1.0,
             spc=0.0):
    """Rectangle of `target` inside a single-line text starting at `rect`.

    Returns (x0, y0, x1, y1) — this is what a highlight bar must cover. Uses the
    measured advance for the horizontal position and the measured ink band for
    the vertical extent, so the bar lands on the word at any font size.
    """
    idx = full_text.find(target)
    if idx < 0:
        return None
    x0, y0, _x1, _y1 = rect
    pre = advance(full_text[:idx], family, size, bold, spc)
    w = advance(target, family, size, bold, spc)
    off, bh = ink_band(full_text, family, size, bold, ls)
    return (x0 + pre, y0 + off, x0 + pre + w, y0 + off + bh)


def _spc(run):
    try:
        v = run.font._rPr.get("spc")
        return float(v) / 100.0 if v else 0.0
    except Exception:
        return 0.0


def audit(slide, mode="ink"):
    """Every text shape on a slide with its rect — the basis for geometric
    checks. Defaults to the visible glyph band; use mode="box" when the question
    is 'does this fit on the page'."""
    out = []
    for sh in slide.shapes:
        if not sh.has_text_frame or not sh.text_frame.text.strip():
            continue
        box = tight_rect(sh, mode="box")
        ink = tight_rect(sh, mode=mode)
        if ink:
            out.append({"shape": sh, "rect": ink, "box": box,
                        "text": sh.text_frame.text.strip()})
    return out


def layer_groups(texts, pad=16.0):
    """Group misregistered copies of the same string.

    A three-layer title is the same words drawn two or three times, offset by a
    few points. Those copies legitimately overlap; treating them as a collision
    makes every stack look like a defect. Returns a list of index groups.
    """
    n = len(texts)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            a, b = texts[i], texts[j]
            if a["text"] != b["text"] or len(a["text"]) < 1:
                continue
            if not any('riso-layer[' in t['shape'].name for t in (a,b)):
                continue
            styles = [tuple((r.font.name,r.font.size,bool(r.font.bold))
                       for p in t['shape'].text_frame.paragraphs for r in p.runs) for t in (a,b)]
            if styles[0] != styles[1]:
                continue
            d = max(abs(a["rect"][k] - b["rect"][k]) for k in range(4))
            if d <= pad:
                pi, pj = find(i), find(j)
                if pi != pj:
                    parent[pj] = pi
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())
