"""Collage direction for the print poster. Poster-only.

``poster_print`` measures the copy. This module decides which modules sit on
torn paper, what lies behind and beside them, and what is printed on the
sheet itself: two spot-ink fields, a paper scene in the masthead, crop marks
and a colour bar. Paper is rendered by ``poster_paper_stock`` into one
transparent plate above the printed ground. Copy and data marks stay native.
"""
from hashlib import sha256
import copy
import math
import random
import re

CHARTS = ('bar-compare', 'bar-vertical', 'line-chart', 'ring', 'stacked-bar', 'pictogram-row')
DIAGRAMS = ('step-flow', 'timeline', 'before-after', 'versus')
FIGURES = ('stat-tile', 'big-number', 'stat-row')
TAIL = re.compile(r'(?::\s+|\s+[—–]\s+)([^:—–]+?)[.!?]?$')


def inflate(r, dx, dy=None):
    dy = dx if dy is None else dy
    return [r[0] - dx, r[1] - dy, r[2] + dx, r[3] + dy]


def meets(a, b, gap=0.0):
    return a[0] < b[2] + gap and a[2] > b[0] - gap and a[1] < b[3] + gap and a[3] > b[1] - gap


def union(rects):
    rects = list(rects)
    return [min(r[0] for r in rects), min(r[1] for r in rects),
            max(r[2] for r in rects), max(r[3] for r in rects)]


def tokens(ink):
    """Palette roles for the paper engine, from a poster ink plan."""
    def multiply(a, b):
        return ''.join(f'{int(a[i:i + 2], 16) * int(b[i:i + 2], 16) // 255:02X}' for i in (0, 2, 4))
    return dict(paper=ink['paper'], inkA=ink['main'][0], inkB=ink['main'][1], ink=ink['body'],
                accent1=ink['accent'], accent2=multiply(ink['main'][0], ink['main'][1]))


def _treatment(name, rng):
    """A stock plus its riso layers. Screens get a seeded angle and direction."""
    angle = rng.choice((15, 30, 45, 60, 75))
    direction = rng.choice((0, 25, 90, 155, 180, 270))
    return {
        'flood': dict(stock='bone', print=[dict(kind='flood', ink='inkA')]),
        'flood-screen': dict(stock='bone', print=[
            dict(kind='flood', ink='inkA', density=.9),
            dict(kind='halftone', ink='ink', direction=direction, start=0, end=.42, pitch=4.6, angle=angle)]),
        'spot': dict(stock='bone', print=[dict(kind='flood', ink='inkB', density=.95)]),
        'spot-screen': dict(stock='bone', print=[
            dict(kind='halftone', ink='inkB', direction=direction, start=.06, end=.86, pitch=5.4, angle=angle)]),
        'duotone': dict(stock='bone', print=[
            dict(kind='halftone', ink='inkA', direction=direction, start=.08, end=.78, pitch=4.8, angle=45),
            dict(kind='halftone', ink='inkB', direction=direction + 180, start=0, end=.6, pitch=4.8, angle=15)]),
        'tint': dict(stock='bone', print=[dict(kind='halftone', ink='inkA', tone=.2, pitch=3.8, angle=angle)]),
        'kraft': dict(stock='kraft'),
        'cream': dict(stock='cream'),
        'kraft-screen': dict(stock='kraft', print=[
            dict(kind='halftone', ink='ink', direction=direction, start=0, end=.5, pitch=5.0, angle=angle,
                 opacity=.8)]),
        'night': dict(stock='bone', print=[dict(kind='flood', ink='ink', density=.97)]),
        'news': dict(stock='news', print=[dict(kind='greek', color='4A4550', opacity=.34)]),
        'grid': dict(stock='bone', print=[dict(kind='grid', ink='inkA', opacity=.13, pitch=11)]),
        'accent': dict(stock='bone', print=[dict(kind='flood', ink='accent1', density=.96)]),
    }[name]


FIELDS = ('flood', 'kraft', 'spot-screen', 'night', 'duotone', 'kraft-screen', 'flood-screen')
SLIVERS = ('spot-screen', 'kraft', 'flood', 'accent', 'duotone', 'night', 'news')
EDGE_SETS = (
    ('cut', 'cut', 'torn', 'cut'), ('cut', 'torn', 'cut', 'cut'), ('deckle', 'cut', 'torn', 'cut'),
    ('cut', 'cut', 'torn', 'deckle'), ('torn', 'cut', 'cut', 'cut'), ('cut', 'deckle', 'torn', 'cut'),
)


def _family(name):
    return name.split('-')[0]


class Composer:
    """Lays paper down in three layers: under, reading faces, over."""

    def __init__(self, seed, variant, frame):
        digest = sha256(f'poster:{seed}:{variant}'.encode()).hexdigest()
        self.rng = random.Random(int(digest[:16], 16))
        self.variant = variant
        self.keepout = []
        self.frame = frame
        self.under, self.faces, self.over, self.strokes = [], [], [], []
        self.count = 0

    def _id(self, role):
        self.count += 1
        return f'collage-{role}-{self.count}'

    def sheet(self, layer, role, rect, treatment=None, edges=None, rotation=0.0, **extra):
        piece = dict(id=self._id(role), role=role, rect=[round(v, 2) for v in rect], rotation=round(rotation, 2),
                     edges=edges or self.rng.choice(EDGE_SETS), treatment=treatment or 'bone')
        piece.update(_treatment(treatment, self.rng) if treatment else dict(stock='bone'))
        piece.update(extra)
        layer.append(piece)
        return piece

    def fit(self, rect, pad=6.0, minimum=(40, 24)):
        """Pull a backing sheet back from open copy, along the side that costs least."""
        rect = [max(rect[0], self.frame[0]), max(rect[1], self.frame[1]),
                min(rect[2], self.frame[2]), min(rect[3], self.frame[3])]
        for other in self.keepout:
            if not meets(rect, other, pad):
                continue
            options = []
            if other[3] + pad < rect[3]:
                options.append([rect[0], other[3] + pad, rect[2], rect[3]])
            if other[1] - pad > rect[1]:
                options.append([rect[0], rect[1], rect[2], other[1] - pad])
            if other[2] + pad < rect[2]:
                options.append([other[2] + pad, rect[1], rect[2], rect[3]])
            if other[0] - pad > rect[0]:
                options.append([rect[0], rect[1], other[0] - pad, rect[3]])
            if not options:
                return None
            rect = max(options, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
        if rect[2] - rect[0] < minimum[0] or rect[3] - rect[1] < minimum[1]:
            return None
        return rect

    def tape(self, x, y, length=None, rotation=None):
        length = length or self.rng.uniform(52, 74)
        rotation = self.rng.uniform(-9, 9) if rotation is None else rotation
        return self.sheet(self.over, 'tape', [x - length / 2, y - 8.5, x + length / 2, y + 8.5],
                          edges=('cut',) * 4, rotation=rotation, translucent=.76, lift=.35,
                          tint=self.rng.choice(('E9DDB8', 'E4D6AE', 'EFE6C8')))

    def disc(self, cx, cy, radius, treatment='spot', layer=None):
        return self.sheet(self.over if layer is None else layer, 'disc',
                          [cx - radius, cy - radius, cx + radius, cy + radius], treatment,
                          shape='disc', lift=.6)

    def scribble(self, kind, rect, color='ink'):
        """Pencil marks: a loose arrow, a wave or a loop, inside rect."""
        x0, y0, x1, y1 = rect
        w, h = x1 - x0, y1 - y0
        rng = self.rng
        if kind == 'wave':
            points = [(x0 + w * t / 24, (y0 + y1) / 2 + h * .42 * math.sin(t * .95 + rng.uniform(-.1, .1)) * (1 - t / 60))
                      for t in range(25)]
            self.strokes.append(dict(points=points, ink=color, width=1.9))
        elif kind == 'arrow':
            bow = rng.uniform(.25, .5) * rng.choice((-1, 1))
            points = [(x0 + w * t, y1 - h * t + h * bow * math.sin(math.pi * t)) for t in [i / 16 for i in range(17)]]
            self.strokes.append(dict(points=points, ink=color, width=1.9))
            (ax, ay), (bx, by) = points[-3], points[-1]
            heading = math.atan2(by - ay, bx - ax)
            for side in (-.5, .5):
                self.strokes.append(dict(points=[(bx - 11 * math.cos(heading + side), by - 11 * math.sin(heading + side)),
                                                 (bx, by)], ink=color, width=1.9))
        elif kind == 'loop':
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            points = [(cx + (w / 2) * (1 + .05 * math.sin(3 * t)) * math.cos(t + .4),
                       cy + (h / 2) * (1 + .07 * math.cos(2 * t)) * math.sin(t + .4))
                      for t in [i * math.tau * 1.08 / 40 for i in range(41)]]
            self.strokes.append(dict(points=points, ink=color, width=1.9))

    def field_name(self, shift=0):
        return FIELDS[(self.variant + shift) % len(FIELDS)]

    def sliver_name(self, shift=0, avoid=()):
        taken = {_family(a) for a in avoid}
        for step in range(len(SLIVERS)):
            name = SLIVERS[(self.variant * 3 + shift + step) % len(SLIVERS)]
            if _family(name) not in taken:
                return name
        return SLIVERS[shift % len(SLIVERS)]

    # --- reading faces -------------------------------------------------------

    def reading_sheet(self, face, r):
        """The lead: one wide face over a larger torn field that shows on two sides."""
        rng = self.rng
        w, h = r[2] - r[0], r[3] - r[1]
        field = self.field_name()
        right = rng.random() < .7
        dx, dy = (rng.uniform(16, 26) if right else -rng.uniform(14, 22)), rng.uniform(14, 22)
        back = self.fit([r[0] + dx + (w * .16 if right else 0), r[1] + dy + h * .1,
                         r[2] + dx - (0 if right else w * .16), r[3] + dy], pad=5)
        if back:
            self.sheet(self.under, 'field', back, field, ('torn', 'torn', 'rip', 'torn'),
                       rng.uniform(.5, 1.1) * rng.choice((-1, 1)))
        sw, sh = min(200, w * .3), min(64, h * .5)
        sx = r[0] - 12 if right else r[2] - sw + 12
        strip = self.fit([sx, r[1] - 11, sx + sw, r[1] - 11 + sh], pad=5)
        if strip:
            self.sheet(self.under, 'sliver', strip, self.sliver_name(1, avoid=(field,)),
                       ('torn', 'cut', 'cut', 'torn'), rng.uniform(-3, 3))
        self.sheet(self.faces, 'face', r, None, ('cut', 'cut', 'torn', 'cut'), 0, face=face)
        self.tape(r[0] + w * (rng.uniform(.7, .84) if right else rng.uniform(.16, .3)), r[1] + 1)
        return 'bone'

    def card(self, face, r, index):
        """A small face with a sliver of colour behind one corner, or taped down."""
        rng = self.rng
        tilt = (-1.6, 1.3, .9, -1.2)[index % 4]
        stock = 'cream' if index % 3 == 1 else None
        if index % 2 == self.variant % 2:
            side = rng.choice(((10, 9), (-9, 10), (11, -7)))
            back = self.fit([r[0] + side[0], r[1] + side[1], r[2] + side[0], r[3] + side[1]])
            if back:
                self.sheet(self.under, 'sliver', back, self.sliver_name(index), rotation=tilt)
        else:
            self.tape(r[0] + (r[2] - r[0]) * rng.uniform(.3, .7), r[1] + 1)
        self.sheet(self.faces, 'face', r, stock, EDGE_SETS[(index + self.variant) % len(EDGE_SETS)], 0, face=face)
        return 'cream' if stock else 'bone'

    def clipping(self, face, r):
        """A chart cut from the paper: a newsprint face over more of the page."""
        rng = self.rng
        w, h = r[2] - r[0], r[3] - r[1]
        back = self.fit([r[0] + w * .34, r[1] - 13, r[2] + rng.uniform(12, 18), r[1] + h * rng.uniform(.5, .7)],
                        pad=5)
        if back:
            self.sheet(self.under, 'field', back, 'news', ('torn', 'rip', 'torn', 'cut'), rng.uniform(.8, 1.6))
        colour = self.fit([r[0] - rng.uniform(9, 14), r[1] + h * .5, r[0] + w * rng.uniform(.3, .46),
                           r[3] + rng.uniform(10, 16)], pad=5)
        if colour:
            self.sheet(self.under, 'sliver', colour, self.sliver_name(0, avoid=('news', 'night')),
                       ('torn', 'torn', 'rip', 'cut'), rng.uniform(-2.2, -1.0))
        self.sheet(self.faces, 'face', r, None, ('cut', 'deckle', 'torn', 'cut'), 0, face=face, stock='news')
        self.tape(r[0] + w * rng.uniform(.1, .22), r[1] + 1, rotation=rng.uniform(-7, -2))
        return 'news'

    def note(self, face, r):
        """A squared note for a quotation, taped at its head."""
        rng = self.rng
        self.sheet(self.faces, 'face', r, 'grid', ('cut', 'cut', 'deckle', 'cut'), 0, face=face)
        self.tape((r[0] + r[2]) / 2 + rng.uniform(-24, 24), r[1] + 1)
        return 'bone'

    def action(self, face, r):
        """The call to action: a torn strip flooded with the first ink, and a spot."""
        rng = self.rng
        h = r[3] - r[1]
        peek = self.fit([r[0] + (r[2] - r[0]) * .5, r[1] + h * .3, r[2] + 12, r[3] + 12], pad=5)
        if peek:
            self.sheet(self.under, 'sliver', peek, 'spot-screen', ('cut', 'torn', 'torn', 'cut'),
                       rng.uniform(-1.6, -.6))
        self.sheet(self.faces, 'face', r, 'flood', ('cut', 'rip', 'torn', 'cut'), 0, face=face)
        radius = min(h * .46, 30)
        self.disc(r[2] - radius * 1.5, r[1] + h * .5, radius, 'accent')
        return 'flood'

    def stub(self, r):
        """Logistics on a kraft strip that runs off the foot of the sheet."""
        self.sheet(self.under, 'stub', r, 'kraft', ('torn', 'cut', 'cut', 'cut'), self.rng.uniform(-.35, .35), lift=.8)
        return 'kraft'

    # --- paper scenes ---------------------------------------------------------

    def _pair(self):
        first, second = self.field_name(2), self.field_name(4)
        if _family(first) == _family(second):
            second = 'kraft' if _family(first) != 'kraft' else 'duotone'
        return first, second

    def horizon(self, rect):
        """Three torn strata under a paper sun."""
        rng = self.rng
        x0, y0, x1, y1 = rect
        w, h = x1 - x0, y1 - y0
        far, near = self._pair()
        sky = 'tint' if _family(far) != 'flood' else 'spot-screen'
        self.sheet(self.under, 'strata', [x0 + w * .03, y0 + h * .02, x1 - w * .02, y1 - h * .12], sky,
                   ('torn', 'cut', 'cut', 'torn'), rng.uniform(-1.8, -.6))
        radius = min(h * .2, w * .14, 64)
        self.disc(x0 + w * rng.uniform(.56, .72), y0 + h * .36, radius,
                  'accent' if 'spot' in (far, near, sky) or _family(sky) == 'spot' else 'spot', layer=self.under)
        self.sheet(self.under, 'strata', [x0, y0 + h * rng.uniform(.4, .48), x1 - w * .1, y1 - h * .04], far,
                   ('rip', 'torn', 'cut', 'cut'), rng.uniform(.6, 1.8))
        self.sheet(self.under, 'strata', [x0 + w * .22, y0 + h * rng.uniform(.6, .68), x1, y1], near,
                   ('rip', 'cut', 'torn', 'torn'), rng.uniform(-1.4, -.4))
        self.sheet(self.under, 'strata', [x0 + w * .02, y0 + h * .8, x0 + w * .58, y1 + h * .02], 'night',
                   ('rip', 'torn', 'cut', 'cut'), rng.uniform(-.6, 1.0))
        self.tape(x0 + w * rng.uniform(.14, .3), y0 + h * .04, rotation=rng.uniform(-14, 14))
        self.scribble('wave', [x0 + w * .14, y0 + h * .14, x0 + w * .4, y0 + h * .26],
                      'inkA' if _family(sky) != 'spot' else 'ink')

    def stack(self, rect):
        """A fanned pile of offcuts with a spot on its corner."""
        rng = self.rng
        x0, y0, x1, y1 = rect
        w, h = x1 - x0, y1 - y0
        first, second = self._pair()
        layers = ((first, -5.0, (.02, .12, .86, .98)), (second, 3.4, (.14, .04, .98, .84)),
                  ('news', -1.2, (.2, .22, .8, .9)))
        for name, angle, (a, b, c, d) in layers:
            self.sheet(self.under, 'strata', [x0 + w * a, y0 + h * b, x0 + w * c, y0 + h * d], name,
                       ('torn', 'cut', 'rip', 'torn'), angle + rng.uniform(-1, 1))
        radius = min(w, h) * .17
        self.disc(x0 + w * .8, y0 + h * .2, radius, 'accent' if 'spot' in (first, second) or
                  'spot-screen' in (first, second) else 'spot')
        self.tape(x0 + w * .3, y0 + h * .14, rotation=rng.uniform(-18, -6))
        self.scribble('arrow', [x0 + w * .3, y0 + h * .62, x0 + w * .58, y0 + h * .82], 'ink')

    def moon(self, rect):
        """One large spot rising behind a torn sheet, on a screened ground."""
        rng = self.rng
        x0, y0, x1, y1 = rect
        w, h = x1 - x0, y1 - y0
        first, second = self._pair()
        ground = 'duotone' if 'duotone' not in (first, second) else 'tint'
        self.sheet(self.under, 'strata', [x0 + w * .08, y0 + h * .04, x1 - w * .04, y1 - h * .1], ground,
                   ('cut', 'torn', 'torn', 'cut'), rng.uniform(1.0, 2.4))
        radius = min(w * .28, h * .3)
        cx = x0 + w * rng.uniform(.42, .58)
        self.disc(cx, y0 + h * .44, radius, 'spot' if _family(ground) != 'spot' else 'accent', layer=self.under)
        front = first if _family(first) not in ('spot', 'duotone') else 'night'
        self.sheet(self.under, 'strata', [x0, y0 + h * .56, x1 - w * .12, y1], front,
                   ('rip', 'torn', 'cut', 'cut'), rng.uniform(-2.4, -.8))
        self.sheet(self.under, 'strata', [x0 + w * .5, y0 + h * .7, x1, y1 - h * .04],
                   'grid' if _family(front) != 'kraft' else 'news', ('cut', 'cut', 'deckle', 'torn'),
                   rng.uniform(1.5, 3.5))
        self.tape(x0 + w * .78, y0 + h * .7, 52, rotation=rng.uniform(-30, -12))
        self.scribble('wave', [x0 + w * .1, y0 + h * .13, x0 + w * .34, y0 + h * .24], 'ink')

    def press(self, rect):
        """Newspaper columns, a flooded strip and a spot."""
        rng = self.rng
        x0, y0, x1, y1 = rect
        w, h = x1 - x0, y1 - y0
        colour = ('flood', 'spot-screen', 'duotone', 'flood-screen')[self.variant % 4]
        small = ('kraft', 'night', 'accent', 'kraft-screen')[(self.variant // 2) % 4]
        self.sheet(self.under, 'strata', [x0 + w * .1, y0, x0 + w * .96, y1 - h * .06], 'news',
                   ('cut', 'torn', 'rip', 'cut'), rng.uniform(1.6, 3.2))
        top = y0 + h * rng.uniform(.46, .58)
        self.sheet(self.under, 'strata', [x0, top, x0 + w * .78, y1], colour,
                   ('rip', 'cut', 'torn', 'torn'), rng.uniform(-2.6, -1.2))
        self.sheet(self.under, 'strata', [x0 + w * .5, top + h * rng.uniform(.06, .16), x1, y1 - h * .1], small,
                   ('torn', 'cut', 'cut', 'deckle'), rng.uniform(.8, 2.2))
        radius = min(w * .2, h * .2, 58) * rng.uniform(.82, 1.0)
        self.disc(x0 + w * .26, y0 + h * rng.uniform(.24, .34), radius,
                  'accent' if _family(colour) == 'spot' else 'spot')
        self.tape(x0 + w * .68, y0 + h * .05, rotation=rng.uniform(4, 16))
        self.scribble(('loop', 'wave')[self.variant % 2], [x0 + w * .56, y0 + h * .24, x0 + w * .84, y0 + h * .36],
                      'inkA')

    def scene(self, rect, kind='auto'):
        x0, y0, x1, y1 = rect
        w, h = x1 - x0, y1 - y0
        if w < 110 or h < 88:
            return None
        if kind == 'auto':
            if w / h >= 1.6:
                kind = ('horizon', 'press')[self.variant % 2]
            else:
                kind = ('moon', 'stack', 'press', 'horizon')[self.variant % 4] if w / h >= .95 else \
                    ('moon', 'stack')[self.variant % 2]
        getattr(self, kind)([x0, y0, x1, y1])
        return kind

    def pieces(self):
        return self.under + self.faces + self.over


def _emphasis(module_text, wanted):
    """The phrase a highlighter marks: authored, or the close of a statement."""
    if wanted and wanted in module_text:
        return wanted
    match = TAIL.search(module_text.strip())
    if match and 2 <= len(match[1].split()) <= 7:
        return match[1].strip()
    return None


def _segments(lines, start, end):
    pieces, at = [], 0
    for index, line in enumerate(lines):
        a, b = max(start, at), min(end, at + len(line))
        if a < b:
            pieces.append((index, a - at, b - at))
        at += len(line) + 1
    return pieces


def _marks(piece, ink, rects, opacity=1.0, rough=False):
    if rects:
        piece['print'] = list(piece.get('print', ())) + [
            dict(kind='marks', ink=ink, rects=[[round(v, 2) for v in r] for r in rects],
                 opacity=opacity, rough=rough)]


def _furnish(piece, members, emphasis=None):
    """Print structure on a reading face: a column head, ledger lines, a highlighter."""
    import textmetrics as tm
    texts = [ob for ob in members if ob['kind'] == 'text']
    if not texts:
        return
    ox, oy = piece['rect'][0], piece['rect'][1]
    width = piece['rect'][2] - ox
    left = min(ob['rect'][0] for ob in texts) - ox
    top = min(ob['rect'][1] for ob in texts) - oy
    rows = {}
    for ob in texts:
        match = re.search(r'visual_data\.items\.(\d+)\.|-nav-(\d+)$', ob['id'])
        if match:
            key = int(match[1] if match[1] is not None else match[2])
            box = rows.setdefault(key, [ob['rect'][1], ob['rect'][3]])
            box[0], box[1] = min(box[0], ob['rect'][1]), max(box[1], ob['rect'][3])
    ordered = sorted(rows.values())
    hairs = []
    for (_, bottom), (next_top, _) in zip(ordered, ordered[1:]):
        if next_top - bottom >= 7:
            y = (bottom + next_top) / 2 - oy
            hairs.append([left, y - .35, width - left, y + .35])
    _marks(piece, 'ink', hairs, .3)
    if top >= 17:
        y = top - 12.5
        _marks(piece, 'inkB', [[left, y, left + 34, y + 4.2]], .95)
        _marks(piece, 'ink', [[left + 40, y + 1.7, width - left, y + 2.5]], .34)
    if emphasis:
        swipes = []
        for ob in texts:
            fit = ob['fit']
            joined = ' '.join(fit['lines'])
            at = joined.find(' '.join(emphasis.split()))
            if at < 0:
                continue
            for index, a, b in _segments(fit['lines'], at, at + len(' '.join(emphasis.split()))):
                line = fit['lines'][index]
                x0 = ob['rect'][0] - ox + .5 + tm.advance(line[:a], fit['font'], fit['size'], fit['bold'])
                x1 = ob['rect'][0] - ox + .5 + tm.advance(line[:b], fit['font'], fit['size'], fit['bold'])
                y0 = ob['rect'][1] - oy + index * fit['pitch']
                swipes.append([x0 - 4, y0 + fit['pitch'] * .2, x1 + 5, y0 + fit['pitch'] * .95])
            break
        _marks(piece, 'accent1', swipes, .85, rough=True)


def dress(plan, direction):
    """Choose the paper for every module and compose the sheet around the copy."""
    import poster_paper_stock as ps

    ink = plan['ink_plan']
    theme = tokens(ink)
    stocks = {k: ps.to_hex(v) for k, v in ps.stock_colors(theme).items()}
    stocks['flood'] = ink['main'][0]
    W, H = plan['canvas']['width'], plan['canvas']['height']
    x = plan['canvas']['safe'][0]
    layout = plan['layout']
    objs = plan['objects']
    by = {o['id']: o for o in objs}
    seed = plan['seed']
    variant = int(direction.get('collage_variant', seed))
    composer = Composer(seed, variant, (-34.0, -34.0, W + 34.0, H + 34.0))
    overhang = layout['overhang']
    paper_mode = direction.get('paper', 'auto')

    # --- which modules read from paper -------------------------------------
    # Charts, quotations and the lead always take paper; diagrams and figures
    # stay open. Plain copy alternates like a chequerboard, so paper and open
    # ground meet across every gutter and down every column.
    def forced(cell):
        visual, kind = cell['visual'], cell['kind']
        if kind == 'lead':
            return 'sheet'
        if kind == 'action':
            return 'action'
        if kind == 'foot':
            return 'stub'
        if visual in CHARTS:
            return 'clipping'
        if visual == 'pull-quote':
            return 'note'
        if visual in DIAGRAMS or visual in FIGURES:
            return 'open'
        return None

    grid = {}
    for cell in layout['cells']:
        cell['face'] = forced(cell)
        if cell['kind'] == 'grid':
            grid.setdefault(cell['row'], []).append(cell)
    plain = 0
    for cell in layout['cells']:
        if cell['face'] is not None:
            continue
        if cell['kind'] != 'grid':
            cell['face'] = 'card' if (plain + variant) % 2 == 0 else 'open'
            plain += 1
            continue
        beside = [other for other in grid[cell['row']] if other is not cell and other['column'] != cell['column']
                  and other['rect'][1] < cell['rect'][3] and other['rect'][3] > cell['rect'][1]]
        decided = [other['face'] for other in beside if other['face'] is not None]
        above = [other for other in layout['cells'] if other.get('face') and other['kind'] in ('grid', 'wide', 'lead')
                 and other['rect'][3] <= cell['rect'][1] and other['rect'][0] < cell['rect'][2]
                 and other['rect'][2] > cell['rect'][0]]
        if above:
            cell['face'] = 'card' if above[-1]['face'] == 'open' else 'open'
        else:
            cell['face'] = 'card' if (cell['column'] + variant) % 2 == 0 else 'open'
        if decided and cell['face'] == 'open' and all(f == 'open' for f in decided):
            cell['face'] = 'card'
    for cell in layout['cells']:
        wanted = cell.get('paper')
        kind = cell['kind']
        face = cell['face']
        if paper_mode == 'none' and face in ('sheet', 'card', 'clipping', 'note'):
            face = 'open'
        if wanted == 'open' and kind not in ('action', 'foot'):
            face = 'open'
        elif wanted == 'sheet' and face == 'open':
            face = 'card'
        cell['face'] = face

    title = by['title']
    open_copy = [inflate(title['rect'], 6, 8)]
    for cell in layout['cells']:
        if cell['face'] in ('open', 'stub'):
            members = [by[i] for i in cell['members'] if i in by]
            if members:
                # The column head printed above an open module is copy too.
                r = union([o['rect'] for o in members] + [cell['rect']])
                open_copy.append([r[0] - 6, r[1] - 22, r[2] + 6, r[3] + 6])
    composer.keepout = open_copy

    # --- masthead: an ink band under a reversed title, then the scene ---------
    if layout.get('band'):
        composer.sheet(composer.under, 'band', layout['band'], 'flood', ('cut', 'cut', 'rip', 'cut'), 0, lift=.9)
    scene = layout.get('scene')
    scene_kind = None
    if scene:
        scene_kind = composer.scene(scene, direction.get('scene', 'auto'))

    # --- faces --------------------------------------------------------------
    cards = 0
    faces = []
    for cell in layout['cells']:
        members = [by[i] for i in cell['members'] if i in by]
        if not members or cell['face'] == 'open':
            continue
        extent = union(o['rect'] for o in members if not o.get('micro'))
        r = cell['rect']
        if cell['face'] == 'stub':
            stock = composer.stub([-34, layout['foot_strip'][0], W + 34, H + 34]) if not any(
                p['role'] == 'stub' for p in composer.under) else 'kraft'
            for ob in members:
                if ob['kind'] == 'text':
                    ob['background'] = stocks[stock]
            continue
        top = 22 if cell['face'] in ('sheet', 'card') else 15
        rect = [r[0] - overhang, min(extent[1], r[1]) - top, r[2] + overhang, extent[3] + 15]
        if cell['face'] == 'action':
            rect = [r[0], r[1], r[2] + overhang * .4, r[3]]
            stock = composer.action(cell['id'], rect)
        elif cell['face'] == 'sheet':
            stock = composer.reading_sheet(cell['id'], rect)
        elif cell['face'] == 'clipping':
            stock = composer.clipping(cell['id'], rect)
        elif cell['face'] == 'note':
            stock = composer.note(cell['id'], rect)
        else:
            stock = composer.card(cell['id'], rect, cards)
            cards += 1
        piece = composer.faces[-1]
        cell['face_rect'] = rect
        faces.append(dict(module=cell['id'], kind=cell['face'], stock=stock, rect=[round(v, 1) for v in rect]))
        for ob in members:
            ob['on_face'] = cell['id']
            if ob['kind'] == 'text':
                ob['background'] = stocks[stock]
        if cell['face'] in ('sheet', 'card'):
            wanted = None
            if cell['face'] == 'sheet':
                body = next((o for o in members if o['kind'] == 'text' and '-body-' in o['id']), None)
                if body:
                    wanted = _emphasis(body['text'], cell.get('emphasis'))
            _furnish(piece, members, wanted)

    # --- open modules: a printed column head, and overprinted figures --------
    extras = []
    for cell in layout['cells']:
        members = [by[i] for i in cell['members'] if i in by]
        if cell['face'] == 'open':
            heading = next((o for o in members if o['id'].endswith('-heading')), None)
            if heading:
                yy = cell['rect'][1] - 14
                extras.append(dict(id=cell['id'] + '-head-bar', kind='rect', rect=[cell['rect'][0], yy, cell['rect'][0] + 34, yy + 4.5],
                                   fill=ink['main'][1], role='emphasis', rotation=0, anchor=heading['id'], micro=True,
                                   vocabulary='column-head'))
                line = [[[cell['rect'][0] + 40, yy + 2.25], [cell['rect'][2], yy + 2.25]]]
                extras.append(dict(id=cell['id'] + '-head-rule', kind='path', paths=line,
                                   rect=[line[0][0][0], yy + 1.75, line[0][1][0], yy + 2.75], line=ink['body'],
                                   line_width=.9, role='structure', rotation=0, anchor=heading['id'], micro=True,
                                   vocabulary='column-head'))
        for ob in members:
            if ob.get('stat_tile') and cell['face'] in ('open', 'sheet', 'card'):
                shift = max(1.6, ob['fit']['size'] * .03)
                under = {k: copy.deepcopy(ob[k]) for k in ('kind', 'text', 'fit', 'background', 'rotation')}
                under.update(id='ink-' + ob['id'], source=None, duplicate_of=ob['id'], role='overprint',
                             color=ink['main'][1], rect=[v + shift for v in ob['rect']])
                objs.insert(objs.index(ob), under)
    objs.extend(extras)

    # --- the printed ground --------------------------------------------------
    quiet = [inflate(o['rect'], 10) for o in objs if o['kind'] == 'text' and not o.get('duplicate_of')]
    # Open modules keep the whole cell clear, diagrams and figures included.
    quiet += [[c['rect'][0] - 14, c['rect'][1] - 26, c['rect'][2] + 14, c['rect'][3] + 14]
              for c in layout['cells'] if c['face'] == 'open']
    fields = []
    if scene:
        cx, cy = scene[2] - (scene[2] - scene[0]) * .28, scene[1] + (scene[3] - scene[1]) * .34
        radius = (scene[2] - scene[0]) * .62
        fields.append(dict(kind='disc', ink='inkB', center=[cx, cy], radius=radius, density=.93))
        fields.append(dict(kind='disc', ink='inkA', center=[cx - radius * .98, cy + radius * .9], radius=radius * .46,
                           density=.9))
        fields.append(dict(kind='screen', ink='inkA', origin=[W + 20, scene[3] + radius * .2], reach=W * .5,
                           direction=[-1, .25], pitch=9.5, top=.82, angle=30))
    else:
        fields.append(dict(kind='screen', ink='inkB', origin=[W + 20, -20], reach=W * .3, direction=[-1, 1],
                           pitch=9.5, top=.85, angle=30))
    fields.append(dict(kind='screen', ink='inkB', origin=[-20, H + 20], reach=W * .42, direction=[1, -.8],
                       pitch=9.5, top=.8, angle=60))
    ground = dict(fields=fields, quiet=[[round(v, 1) for v in r] for r in quiet],
                  crop_marks=True, colour_bar=[x, H - 17, 'left'] if not layout.get('foot_strip') else [x, 9, 'left'])

    plate = dict(id='collage-plate', kind='plate', rect=[0, 0, W, H], role='surface', layer='surface',
                 vocabulary='plate', rotation=0, anchor='title', file='collage1.png')
    objs.insert(0, plate)
    plan['collage'] = dict(pieces=composer.pieces(), strokes=composer.strokes, ground=ground, faces=faces,
                           scene=scene_kind, variant=variant, tokens=theme)
    return plan['collage']


def summary(plan):
    """One line for the run report: masthead, scene, then where each module sits."""
    layout, collage = plan['layout'], plan['collage']
    title = next(o for o in plan['objects'] if o['id'] == 'title')
    head = ('band' if layout.get('band') else 'open') + f" title {title['fit']['size']:g}pt"
    head += f", scene {collage['scene']}" if collage.get('scene') else ', no scene'
    cells = ['action strip' if c['kind'] == 'action' else f"{c['id']} {c['face']}"
             for c in layout['cells'] if c['kind'] != 'foot']
    return head + ' | ' + ', '.join(cells)


def render_ground(plan, scale=2.0):
    """The sheet itself: paper grain, two spot-ink fields, crop marks and a colour bar."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    import poster_paper_stock as ps

    collage = plan['collage']
    theme = collage['tokens']
    ground = collage['ground']
    W, H = plan['canvas']['width'], plan['canvas']['height']
    w, h = int(round(W * scale)), int(round(H * scale))
    rng = ps.rng_for(plan['seed'], 'ground')
    grain = ps._texture(h, w, 'bone', scale, rng, strength=.55)
    image = np.broadcast_to(ps.rgb(theme['paper'])[None, None, :], (h, w, 3)).copy()

    # Ink keeps clear of every line of copy, with a soft edge.
    mask = Image.new('L', (w, h), 255)
    draw = ImageDraw.Draw(mask)
    for r in ground['quiet']:
        draw.rectangle([v * scale for v in r], fill=0)
    quiet = np.asarray(mask.filter(ImageFilter.GaussianBlur(7 * scale)), np.float32) / 255
    quiet = np.clip((quiet - .45) / .5, 0, 1)

    # Each field is inked inside its own box; the rest of the sheet is untouched.
    for field in ground['fields']:
        color = theme[field['ink']]
        if field['kind'] == 'disc':
            cx, cy, radius = field['center'][0] * scale, field['center'][1] * scale, field['radius'] * scale
            x0, x1 = max(0, int(cx - radius) - 2), min(w, int(cx + radius) + 3)
            y0, y1 = max(0, int(cy - radius) - 2), min(h, int(cy + radius) + 3)
            if x1 <= x0 or y1 <= y0:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            distance = radius - np.hypot(xx - cx, yy - cy)
            wobble = ps.noise2(y1 - y0, x1 - x0, 2.2 * scale, rng) * .6 * scale
            coverage = np.clip(distance + wobble + .5, 0, 1) * ps._flood(y1 - y0, x1 - x0, scale, rng, field['density'])
        else:
            ox, oy = field['origin'][0] * scale, field['origin'][1] * scale
            reach = field['reach'] * scale
            dx, dy = field['direction']
            norm = math.hypot(dx, dy)
            ux, uy = dx / norm, dy / norm
            corners = [(ox + ux * t - uy * s, oy + uy * t + ux * s) for t in (0, reach)
                       for s in (-reach * .55, reach * .55)]
            x0, x1 = max(0, int(min(c[0] for c in corners))), min(w, int(max(c[0] for c in corners)) + 1)
            y0, y1 = max(0, int(min(c[1] for c in corners))), min(h, int(max(c[1] for c in corners)) + 1)
            if x1 <= x0 or y1 <= y0:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            along = (xx - ox) * ux + (yy - oy) * uy
            across = np.abs(-(xx - ox) * uy + (yy - oy) * ux)
            tone = np.clip(1 - along / reach, 0, 1) * np.clip(1 - across / (reach * .55), 0, 1)
            tone = np.where(along < 0, 0, tone) ** 1.5 * field['top']
            tone = tone * (1 + .08 * ps.noise2(y1 - y0, x1 - x0, 40 * scale, rng))
            # The screen keeps one lattice across the sheet, whatever its box.
            coverage = ps.halftone(y1 - y0, x1 - x0, tone, field['pitch'], field['angle'], scale, (x0, y0))
            coverage = coverage * (1 - .16 * (ps.noise2(y1 - y0, x1 - x0, 1.6 * scale, rng) > .72))
        coverage = (coverage * quiet[y0:y1, x0:x1]).astype(np.float32)
        image[y0:y1, x0:x1] = ps._ink(image[y0:y1, x0:x1], color, coverage)

    # Print furniture lives in the margin, outside every line of copy.
    marks = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(marks)
    line = max(1, round(.6 * scale))
    if ground.get('crop_marks'):
        inset, length = 14 * scale, 13 * scale
        for cx in (inset, w - inset):
            for cy in (inset, h - inset):
                draw.line([cx - length, cy, cx + length, cy], fill=255, width=line)
                draw.line([cx, cy - length, cx, cy + length], fill=255, width=line)
                draw.ellipse([cx - 4.5 * scale, cy - 4.5 * scale, cx + 4.5 * scale, cy + 4.5 * scale],
                             outline=255, width=line)
    coverage = np.asarray(marks.filter(ImageFilter.GaussianBlur(.2 * scale)), np.float32) / 255
    image = ps._ink(image, theme['ink'], coverage * .8)
    bar = ground.get('colour_bar')
    if bar:
        size, bx, by = 9 * scale, bar[0] * scale + 22 * scale, bar[1] * scale
        for i, name in enumerate(('inkA', 'inkB', 'accent1', 'ink', 'inkA+inkB')):
            x0, y0 = int(bx + i * (size + 1.5 * scale)), int(by)
            x1, y1 = int(x0 + size), int(y0 + size * .62)
            patch = ps._flood(y1 - y0, x1 - x0, scale, rng, .94)
            for part in name.split('+'):
                image[y0:y1, x0:x1] = ps._ink(image[y0:y1, x0:x1], theme[part], patch)
    image = np.clip(image * grain[..., None], 0, 1)
    return Image.fromarray((image * 255 + .5).astype(np.uint8), 'RGB')


def render_plate(plan, scale=2.0):
    """Rasterise the paper to one transparent plate the size of the sheet."""
    import poster_paper_stock as ps

    collage = plan['collage']
    size = (plan['canvas']['width'], plan['canvas']['height'])
    plate = ps.Plate(size, scale, collage['tokens'], plan['seed'] * 977 + 1)
    plate.place_all(collage['pieces'])
    for mark in collage.get('strokes', ()):
        plate.draw(mark['points'], collage['tokens'][mark.get('ink', 'ink')], mark.get('width', 1.9))
    return plate
