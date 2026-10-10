#!/usr/bin/env python3
"""layout.py — geometry primitives shared by the composer and the checker.

Everything here works in page points on the 960x540 grid, and everything is
computed rather than eyeballed. That is the answer to "should the agent
screenshot the deck to find layout bugs, or compute distances?": compute them.
Measuring is arithmetic, costs no tokens, and is reproducible; a rendered image
is only needed to judge craft (does the doodle look hand-drawn), never to find
out whether a caption collides with a sticker.

The three defects that prompted this module were all geometry:
  1. text ran past the canvas edge      -> `inside(rect, bounds)`
  2. a caption collided with a sticker  -> `classify_overlap(text, shape)`
  3. a highlight bar missed its word    -> `covers(bar, word_rect)`
"""
import sys
sys.dont_write_bytecode = True
import math
from canvas import DECK_CANVAS

PAGE_W, PAGE_H = DECK_CANVAS.width, DECK_CANVAS.height

# how much clear space a decorative element must leave around text
TEXT_PROTECTION = 9.0
# smallest acceptable gap between two text blocks that are not nested
MIN_TEXT_GAP = 3.0
# a highlight bar may overhang the word it marks by at most this much
HIGHLIGHT_SLOP = 2.5


def rect(x, y, w, h):
    return (x, y, x + w, y + h)


def inflate(r, pad):
    return (r[0] - pad, r[1] - pad, r[2] + pad, r[3] + pad)


def area(r):
    return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])


def intersection(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def overlaps(a, b, pad=0.0):
    return intersection(inflate(a, pad), b) is not None


def contains(outer, inner, tol=0.5):
    return (outer[0] <= inner[0] + tol and outer[1] <= inner[1] + tol
            and outer[2] >= inner[2] - tol and outer[3] >= inner[3] - tol)


def inside(r, bounds=None, tol=0.0, canvas=None):
    bounds = bounds or (canvas or DECK_CANVAS).bounds
    return (r[0] >= bounds[0] - tol and r[1] >= bounds[1] - tol
            and r[2] <= bounds[2] + tol and r[3] <= bounds[3] + tol)


def gap(a, b):
    """Shortest distance between two rects (0 if they touch or overlap)."""
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return math.hypot(dx, dy)


def ellipse_contains(ellipse, inner, tol=.5):
    """All glyph-rectangle corners must belong to the actual ellipse."""
    cx,cy=(ellipse[0]+ellipse[2])/2,(ellipse[1]+ellipse[3])/2
    rx,ry=(ellipse[2]-ellipse[0])/2+tol,(ellipse[3]-ellipse[1])/2+tol
    return rx>0 and ry>0 and all(((x-cx)/rx)**2+((y-cy)/ry)**2<=1
        for x in (inner[0],inner[2]) for y in (inner[1],inner[3]))


def segment_rect_distance(a,b,r):
    """Distance from a real line segment to a rectangle, including diagonals."""
    # Liang-Barsky clips the segment to the rectangle. The broad AABB is only
    # a fast rejection, never the collision decision.
    dx,dy=b[0]-a[0],b[1]-a[1]
    lo,hi=0.,1.
    for p,q in ((-dx,a[0]-r[0]),(dx,r[2]-a[0]),(-dy,a[1]-r[1]),(dy,r[3]-a[1])):
        if p==0:
            if q<0:break
        else:
            t=q/p
            if p<0:lo=max(lo,t)
            else:hi=min(hi,t)
            if lo>hi:break
    else:
        return 0.
    def point_segment(c):
        t=max(0.,min(1.,((c[0]-a[0])*dx+(c[1]-a[1])*dy)/(dx*dx+dy*dy))) if dx or dy else 0
        return math.hypot(c[0]-a[0]-t*dx,c[1]-a[1]-t*dy)
    def point_rect(c):
        return math.hypot(max(r[0]-c[0],c[0]-r[2],0),max(r[1]-c[1],c[1]-r[3],0))
    return min(point_rect(a),point_rect(b),*(point_segment((x,y)) for x in (r[0],r[2]) for y in (r[1],r[3])))


def line_segment(shape):
    """Actual connector direction or a thin filled rule's center path."""
    x,y,w,h=shape.left.pt,shape.top.pt,shape.width.pt,shape.height.pt
    if shape.shape_type==9:  # LINE
        flip=shape._element.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm')
        fh=flip is not None and flip.get('flipH') in ('1','true')
        fv=flip is not None and flip.get('flipV') in ('1','true')
        a=(x+w if fh else x,y+h if fv else y)
        b=(x if fh else x+w,y if fv else y+h)
        return a,b,(shape.line.width.pt if shape.line.width else .75)
    if min(w,h)<=2.5 and is_solid(shape):
        return ((x,y+h/2),(x+w,y+h/2),h) if w>=h else ((x+w/2,y),(x+w/2,y+h),w)
    return None


def measured_issues(slide):
    """Shared hard geometry checks used by both checker entry points."""
    import textmetrics as tm
    issues=[]
    texts=tm.audit(slide)
    for sh in slide.shapes:
        segment=line_segment(sh)
        if segment:
            a,b,width=segment
            for t in texts:
                if any(segment_rect_distance(a,b,r)<=width/2+.5 for r in tm.glyph_rects(t['shape'])):
                    issues.append(f'line-glyph collision: {t["text"][:32]!r} with {sh.name}')
    circles={s.name:obb(s) for s in slide.shapes if s.name.startswith('venn-circle[')}
    for t in texts:
        name=t['shape'].name
        if not name.startswith('venn-label['):continue
        role=name.split('[')[1].split(']')[0]
        expected=['left','right'] if role=='centre' else [role]
        glyphs=tm.glyph_rects(t['shape'])
        if not all(f'venn-circle[{r}]' in circles and all(ellipse_contains(circles[f'venn-circle[{r}]'],g) for g in glyphs) for r in expected):
            issues.append(f'Venn {role} label outside its circle/intersection: {t["text"]!r}')
    return issues


def obb(shape):
    """Axis-aligned bbox of a shape *after* its rotation is applied.

    python-pptx exposes the unrotated frame, which reads smaller than what a
    rotated sticker actually prints. This returns the true footprint.
    """
    x, y = shape.left.pt, shape.top.pt
    w, h = shape.width.pt, shape.height.pt
    rot = float(getattr(shape, "rotation", 0) or 0)
    if abs(rot) < 0.01:
        return (x, y, x + w, y + h)
    cx, cy = x + w / 2.0, y + h / 2.0
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    xs, ys = [], []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        xs.append(cx + dx * ca - dy * sa)
        ys.append(cy + dx * sa + dy * ca)
    return (min(xs), min(ys), max(xs), max(ys))


def obb_contains(shape, r):
    """Does a (possibly rotated) shape contain rect r? Uses the OBB, so a
    rotated sticker is judged by what it actually covers."""
    return contains(obb(shape), r)


def is_solid(shape):
    """Shapes that read as ink on the page: filled autoshapes (no text) and
    decorative pictures. Text boxes, transparent shapes and light washes are not.

    Opacity matters, not just fill type. The venn diagram's overprint lens is a
    solid-filled freeform at 88% alpha, and its own centre label is *drawn on top
    of it* by design - judging it as opaque ink reported the diagram as a
    collision with the word it exists to explain. Washes (the grid's 12% panel)
    are excluded for the same reason.
    """
    kind = shape.shape_type
    if kind == 13:                                    # PICTURE
        return True
    if shape.has_text_frame and shape.text_frame.text.strip():
        return False
    try:
        from pptx.enum.dml import MSO_FILL
        if shape.fill.type != MSO_FILL.SOLID:
            return False
    except Exception:
        return False
    try:
        from pptx.oxml.ns import qn
        clr = shape._element.spPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
        alpha = clr.find(qn("a:alpha"))
        if alpha is not None and int(alpha.get("val")) < 95000:   # opaque = 100000
            return False
    except Exception:
        pass
    return True


def classify_overlap(shape, text_rect, pad=0.0, tolerance=0.85):
    """How a filled shape and a text block relate.

    Returns one of:
      'clear'      disjoint (the normal, wanted case)
      'underlay'   the *shape* sits inside the text block — a highlight bar or a
                   rule behind a line: intentional overprint. Judged by area, so
                   a bar that overhangs its line by a point is still an underlay.
      'wrap'       the text sits inside the shape — a sticker or a solid panel
                   with type on it: intentional
      'collision'  partial overlap: the defect this module exists to catch (a
                   caption half-swallowed by a sticker)
    """
    a = inflate(text_rect, pad)
    b = obb(shape) if hasattr(shape, "rotation") else shape
    inter = intersection(a, b)
    if inter is None:
        return "clear"
    share_of_shape = area(inter) / max(1e-6, area(b))
    share_of_text = area(inter) / max(1e-6, area(a))
    if share_of_shape >= tolerance:
        return "underlay"
    if share_of_text >= tolerance:
        return "wrap"
    return "collision"


def covers(bar, word, slop=HIGHLIGHT_SLOP):
    """Does a highlight bar actually cover the word it is supposed to mark?

    A bar that is offset, too narrow, or shifted up by a few points would slip
    through review unseen. This is the measurement.
    """
    if not bar or not word:
        return False
    return (bar[0] <= word[0] + slop and bar[1] <= word[1] + slop
            and bar[2] >= word[2] - slop and bar[3] >= word[3] - slop)


def overhang(bar, word):
    """(left, right) overhang of a bar beyond a word, in points."""
    return (max(0.0, word[0] - bar[0]), max(0.0, bar[2] - word[2]))


def best_text_band(rects, height, top, bottom, x0, x1, step=4.0):
    """Find the quietest horizontal band of `height` between top and bottom.

    Used by the composer to slot elements into whitespace instead of on top of
    copy. Returns (y, score) where score is the free width fraction.
    """
    best, best_y = -1.0, top
    y = top
    while y + height <= bottom:
        band = (x0, y, x1, y + height)
        used = 0.0
        for r in rects:
            i = intersection(band, r)
            if i:
                used += area(i)
        free = 1.0 - used / max(1.0, area(band))
        if free > best:
            best, best_y = free, y
        y += step
    return best_y, best
