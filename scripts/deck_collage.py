"""Collage direction for deck pages: which papers lie where, and why.

The evidence writers ask for reading faces under their measured copy. This
module arranges everything else around them: one dominant field, a few
slivers of colour, tape, and a small paper scene in a large opening. Pieces
are rendered by ``paper_stock`` into the page plate. Copy stays native.
"""
from hashlib import sha256
import math
import random

FRAME = (10.0, 48.0, 950.0, 480.0)  # pieces stay clear of the chrome bands
TILT = True  # copy turns with the face it is printed on


def inflate(r, dx, dy=None):
    dy = dx if dy is None else dy
    return [r[0] - dx, r[1] - dy, r[2] + dx, r[3] + dy]


def meets(a, b, gap=0.0):
    return a[0] < b[2] + gap and a[2] > b[0] - gap and a[1] < b[3] + gap and a[3] > b[1] - gap


def union(rects):
    rects = list(rects)
    return [min(r[0] for r in rects), min(r[1] for r in rects),
            max(r[2] for r in rects), max(r[3] for r in rects)]


def clamp(r, frame=FRAME):
    return [max(r[0], frame[0]), max(r[1], frame[1]), min(r[2], frame[2]), min(r[3], frame[3])]


def largest_opening(occupied, frame, cell=12.0, min_size=(120.0, 76.0)):
    """Largest free rectangle on a coarse grid, or None when nothing useful is left."""
    columns = int((frame[2] - frame[0]) // cell)
    rows = int((frame[3] - frame[1]) // cell)
    free = [[True] * columns for _ in range(rows)]
    for x0, y0, x1, y1 in occupied:
        for row in range(max(0, int((y0 - frame[1]) // cell)), min(rows, int(math.ceil((y1 - frame[1]) / cell)))):
            for col in range(max(0, int((x0 - frame[0]) // cell)),
                             min(columns, int(math.ceil((x1 - frame[0]) / cell)))):
                free[row][col] = False
    heights = [0] * columns
    best = None
    for row in range(rows):
        for col in range(columns):
            heights[col] = heights[col] + 1 if free[row][col] else 0
        stack = []
        for col in range(columns + 1):
            current = heights[col] if col < columns else 0
            start = col
            while stack and stack[-1][1] >= current:
                start, height = stack.pop()
                width = col - start
                if width * cell >= min_size[0] and height * cell >= min_size[1]:
                    # Prefer area, with a mild preference for compact shapes.
                    score = width * height * min(1.0, 3.2 * min(width, height) / max(width, height))
                    if best is None or score > best[0]:
                        best = (score, start, row - height + 1, col, row + 1)
            stack.append((start, current))
    if best is None:
        return None
    _, c0, r0, c1, r1 = best
    return [frame[0] + c0 * cell, frame[1] + r0 * cell, frame[0] + c1 * cell, frame[1] + r1 * cell]


def _treatment(name, rng):
    """A stock plus its riso layers. Screens get a seeded angle and direction."""
    angle = rng.choice((15, 30, 45, 60, 75))
    direction = rng.choice((0, 25, 90, 155, 180, 270))
    return {
        'plum': dict(stock='bone', print=[dict(kind='flood', ink='inkA')]),
        'plum-screen': dict(stock='bone', print=[
            dict(kind='flood', ink='inkA', density=.9),
            dict(kind='halftone', ink='ink', direction=direction, start=0, end=.42, pitch=4.4, angle=angle)]),
        'spot': dict(stock='bone', print=[dict(kind='flood', ink='inkB', density=.95)]),
        'spot-screen': dict(stock='bone', print=[
            dict(kind='halftone', ink='inkB', direction=direction, start=.06, end=.86, pitch=5.0, angle=angle)]),
        'duotone': dict(stock='bone', print=[
            dict(kind='halftone', ink='inkA', direction=direction, start=.08, end=.78, pitch=4.4, angle=45),
            dict(kind='halftone', ink='inkB', direction=direction + 180, start=0, end=.6, pitch=4.4, angle=15)]),
        'tint': dict(stock='bone', print=[dict(kind='halftone', ink='inkA', tone=.2, pitch=3.6, angle=angle)]),
        'kraft': dict(stock='kraft'),
        'cream': dict(stock='cream'),
        'kraft-screen': dict(stock='kraft', print=[
            dict(kind='halftone', ink='ink', direction=direction, start=0, end=.5, pitch=4.8, angle=angle,
                 opacity=.8)]),
        'night': dict(stock='bone', print=[dict(kind='flood', ink='ink', density=.97)]),
        'news': dict(stock='news', print=[dict(kind='greek', color='4A4550', opacity=.34)]),
        'grid': dict(stock='bone', print=[dict(kind='grid', ink='inkA', opacity=.13, pitch=11)]),
        'accent': dict(stock='bone', print=[dict(kind='flood', ink='accent1', density=.96)]),
    }[name]


# Dominant fields rotate through the deck, so neighbouring pages differ.
FIELDS = ('plum', 'kraft', 'spot-screen', 'night', 'duotone', 'kraft-screen', 'plum-screen')
SLIVERS = ('spot-screen', 'kraft', 'plum', 'accent', 'duotone', 'night', 'news')
EDGE_SETS = (
    ('cut', 'cut', 'torn', 'cut'), ('cut', 'torn', 'cut', 'cut'), ('deckle', 'cut', 'torn', 'cut'),
    ('cut', 'cut', 'torn', 'deckle'), ('torn', 'cut', 'cut', 'cut'), ('cut', 'deckle', 'torn', 'cut'),
)


def _family(name):
    return name.split('-')[0]


class Composer:
    def __init__(self, seed, variant, keepout, frame=FRAME):
        digest = sha256(f'{seed}:{variant}'.encode()).hexdigest()
        self.rng = random.Random(int(digest[:16], 16))
        self.variant = variant
        self.keepout = [list(r) for r in keepout]
        self.frame = frame
        self.under, self.faces, self.over, self.strokes, self.inks = [], [], [], [], []
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

    def fit(self, rect, avoid=(), pad=5.0):
        """Pull a backing rect back from copy that is not printed on a face."""
        rect = clamp(rect, self.frame)
        for other in list(self.keepout) + list(avoid):
            if not meets(rect, other, pad):
                continue
            # Retreat along the side that loses the least area.
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
        if rect[2] - rect[0] < 36 or rect[3] - rect[1] < 22:
            return None
        return rect

    def tape(self, x, y, length=None, rotation=None):
        length = length or self.rng.uniform(46, 64)
        rotation = self.rng.uniform(-9, 9) if rotation is None else rotation
        return self.sheet(self.over, 'tape', [x - length / 2, y - 7.5, x + length / 2, y + 7.5],
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
            self.strokes.append(dict(points=points, ink=color, width=1.5))
        elif kind == 'arrow':
            bow = rng.uniform(.25, .5) * rng.choice((-1, 1))
            points = [(x0 + w * t, y1 - h * t + h * bow * math.sin(math.pi * t)) for t in [i / 16 for i in range(17)]]
            self.strokes.append(dict(points=points, ink=color, width=1.5))
            (ax, ay), (bx, by) = points[-3], points[-1]
            heading = math.atan2(by - ay, bx - ax)
            for side in (-.5, .5):
                self.strokes.append(dict(points=[(bx - 9 * math.cos(heading + side), by - 9 * math.sin(heading + side)),
                                                 (bx, by)], ink=color, width=1.5))
        elif kind == 'loop':
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            points = [(cx + (w / 2) * (1 + .05 * math.sin(3 * t)) * math.cos(t + .4),
                       cy + (h / 2) * (1 + .07 * math.cos(2 * t)) * math.sin(t + .4))
                      for t in [i * math.tau * 1.08 / 40 for i in range(41)]]
            self.strokes.append(dict(points=points, ink=color, width=1.5))

    def field_name(self, shift=0):
        return FIELDS[(self.variant + shift) % len(FIELDS)]

    def sliver_name(self, shift=0, avoid=()):
        taken = {_family(a) for a in avoid}
        for step in range(len(SLIVERS)):
            name = SLIVERS[(self.variant * 3 + shift + step) % len(SLIVERS)]
            if _family(name) not in taken:
                return name
        return SLIVERS[shift % len(SLIVERS)]

    # --- scenes around reading faces ----------------------------------------

    def cards(self, faces):
        """Several small faces scattered over one torn field."""
        rng = self.rng
        area = union(f['rect'] for f in faces)
        w, h = area[2] - area[0], area[3] - area[1]
        field = self.field_name()
        band = self.fit([area[0] + w * rng.uniform(.06, .12), area[1] + h * rng.uniform(.14, .24),
                         area[2] - w * rng.uniform(.03, .08), area[3] - h * rng.uniform(.06, .14)])
        if band:
            self.sheet(self.under, 'field', band, field, ('rip', 'torn', 'rip', 'torn'),
                       rng.uniform(1.6, 2.8) * rng.choice((-1, 1)))
        tilts = [-1.0, .8, .55, -.85]
        rng.shuffle(tilts)
        for index, face in enumerate(faces):
            r = face['rect']
            if index % 2 == (self.variant % 2):
                side = rng.choice(((9, 8), (-8, 9), (10, -6)))
                back = self.fit([r[0] + side[0], r[1] + side[1], r[2] + side[0], r[3] + side[1]])
                if back:
                    self.sheet(self.under, 'sliver', back, self.sliver_name(index, avoid=(field,)),
                               rotation=-tilts[index % 4] * 1.4)
            stock = 'grid' if index == (self.variant + 2) % len(faces) and len(faces) > 2 else None
            self.sheet(self.faces, 'face', r, stock, EDGE_SETS[(index + self.variant) % len(EDGE_SETS)],
                       tilts[index % 4] if TILT else 0, face=face['id'])
            if index % 2 != (self.variant % 2):
                self.tape(r[0] + (r[2] - r[0]) * rng.uniform(.3, .7), r[1] + 1)
        last = faces[-1]['rect']
        spot = [last[2] - 8, last[1] - 16, last[2] + 26, last[1] + 18]
        if not any(meets(spot, k, 4) for k in self.keepout) and spot[2] < self.frame[2]:
            self.disc((spot[0] + spot[2]) / 2, (spot[1] + spot[3]) / 2, 15,
                      'accent' if _family(field) == 'spot' else 'spot')

    def reading_sheet(self, face, stock=None, rich=True):
        """One reading face over a larger sheet that shows on two sides."""
        rng = self.rng
        r = face['rect']
        w, h = r[2] - r[0], r[3] - r[1]
        field = self.field_name()
        tilt = rng.uniform(.35, .75) * rng.choice((-1, 1)) if TILT else 0
        right = rng.random() < .7
        dx, dy = (rng.uniform(14, 24) if right else -rng.uniform(12, 20)), rng.uniform(12, 19)
        back = self.fit([r[0] + dx + (w * .1 if right else 0), r[1] + dy + h * .08,
                         r[2] + dx - (0 if right else w * .1), r[3] + dy], pad=4)
        if back:
            self.sheet(self.under, 'field', back, field, ('torn', 'torn', 'rip', 'torn'),
                       -tilt * 2.4 + rng.uniform(-.6, .6))
        if rich:
            # A second colour peeks from the opposite corner.
            sw, sh = min(160, w * .36), min(58, h * .5)
            x = r[0] - 10 if right else r[2] - sw + 10
            strip = self.fit([x, r[1] - 10, x + sw, r[1] - 10 + sh], pad=4)
            if strip:
                self.sheet(self.under, 'sliver', strip, self.sliver_name(1, avoid=(field,)),
                           ('torn', 'cut', 'cut', 'torn'), rng.uniform(-4, 4))
        self.sheet(self.faces, 'face', r, stock, face.get('edges') or ('cut', 'cut', 'torn', 'cut'), tilt,
                   face=face['id'])
        if rich:
            self.tape(r[0] + w * (rng.uniform(.62, .8) if right else rng.uniform(.2, .38)), r[1] + 1)

    def clipping(self, face):
        """A chart cut from the paper: a newsprint face over more of the page."""
        rng = self.rng
        r = face['rect']
        w, h = r[2] - r[0], r[3] - r[1]
        back = self.fit([r[0] + w * .34, r[1] - 13, r[2] + rng.uniform(15, 24), r[1] + h * rng.uniform(.5, .7)],
                        pad=4)
        if back:
            self.sheet(self.under, 'field', back, 'news', ('torn', 'rip', 'torn', 'cut'), rng.uniform(1.2, 2.2))
        colour = self.fit([r[0] - rng.uniform(10, 16), r[1] + h * .5, r[0] + w * rng.uniform(.3, .46),
                           r[3] + rng.uniform(10, 16)], pad=4)
        if colour:
            self.sheet(self.under, 'sliver', colour, self.sliver_name(0, avoid=('news', 'night')),
                       ('torn', 'torn', 'rip', 'cut'), rng.uniform(-2.6, -1.2))
        self.sheet(self.faces, 'face', r, None, ('cut', 'deckle', 'torn', 'cut'), 0, face=face['id'],
                   stock='news')
        self.tape(r[0] + w * rng.uniform(.08, .2), r[1] + 1, rotation=rng.uniform(-7, -2))

    def note(self, face, treatment='grid'):
        rng = self.rng
        r = face['rect']
        tilt = rng.uniform(.8, 1.4) * rng.choice((-1, 1)) if TILT else 0
        self.sheet(self.faces, 'face', r, treatment, ('cut', 'cut', 'deckle', 'cut'), tilt, face=face['id'])
        self.tape((r[0] + r[2]) / 2 + rng.uniform(-20, 20), r[1] + 1)

    # --- small paper scenes for openings ------------------------------------

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
        sky = 'tint' if _family(far) != 'plum' else 'spot-screen'
        self.sheet(self.under, 'strata', [x0 + w * .03, y0 + h * .02, x1 - w * .02, y1 - h * .12], sky,
                   ('torn', 'cut', 'cut', 'torn'), rng.uniform(-1.8, -.6))
        radius = min(h * .2, w * .12, 44)
        self.disc(x0 + w * rng.uniform(.58, .76), y0 + h * .36, radius,
                  'accent' if 'spot' in (far, near, sky) or _family(sky) == 'spot' else 'spot', layer=self.under)
        self.sheet(self.under, 'strata', [x0, y0 + h * rng.uniform(.4, .48), x1 - w * .1, y1 - h * .04], far,
                   ('rip', 'torn', 'cut', 'cut'), rng.uniform(.6, 1.8))
        self.sheet(self.under, 'strata', [x0 + w * .22, y0 + h * rng.uniform(.6, .68), x1, y1], near,
                   ('rip', 'cut', 'torn', 'torn'), rng.uniform(-1.4, -.4))
        self.sheet(self.under, 'strata', [x0 + w * .02, y0 + h * .8, x0 + w * .58, y1 + h * .02], 'night',
                   ('rip', 'torn', 'cut', 'cut'), rng.uniform(-.6, 1.0))
        self.tape(x0 + w * rng.uniform(.14, .3), y0 + h * .04, rotation=rng.uniform(-14, 14))
        self.scribble('wave', [x0 + w * .16, y0 + h * .16, x0 + w * .4, y0 + h * .28],
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

    def press(self, rect):
        """The rest of the newspaper: columns, a flooded strip and a spot."""
        rng = self.rng
        x0, y0, x1, y1 = rect
        w, h = x1 - x0, y1 - y0
        colour = ('plum', 'spot-screen', 'duotone', 'plum-screen')[self.variant % 4]
        small = ('kraft', 'night', 'accent', 'kraft-screen')[(self.variant // 2) % 4]
        flip = rng.random() < .5

        def span(a, b):
            # Mirror the arrangement on alternate pages.
            return (x0 + w * (1 - b), x0 + w * (1 - a)) if flip else (x0 + w * a, x0 + w * b)

        left, right = span(.1, .96)
        self.sheet(self.under, 'strata', [left, y0, right, y1 - h * .06], 'news',
                   ('cut', 'torn', 'rip', 'cut'), rng.uniform(1.6, 3.2) * (-1 if flip else 1))
        left, right = span(0, .78)
        top = y0 + h * rng.uniform(.46, .58)
        self.sheet(self.under, 'strata', [left, top, right, y1], colour,
                   ('rip', 'cut', 'torn', 'torn'), rng.uniform(-2.6, -1.2))
        left, right = span(.5, 1)
        self.sheet(self.under, 'strata', [left, top + h * rng.uniform(.06, .16), right, y1 - h * .1], small,
                   ('torn', 'cut', 'cut', 'deckle'), rng.uniform(.8, 2.2))
        radius = min(w * .2, h * .2, 42) * rng.uniform(.82, 1.0)
        cx = span(.24, .24)[0]
        self.disc(cx, y0 + h * rng.uniform(.24, .34), radius,
                  'accent' if _family(colour) == 'spot' or small == 'accent' and flip else 'spot')
        self.tape(span(.68, .68)[0], y0 + h * .05, rotation=rng.uniform(4, 16))
        left, right = span(.56, .84)
        self.scribble(('loop', 'wave')[self.variant % 2], [left, y0 + h * .24, right, y0 + h * .36], 'inkA')

    def moon(self, rect):
        """One large spot rising behind a torn sheet, on a screened ground."""
        rng = self.rng
        x0, y0, x1, y1 = rect
        w, h = x1 - x0, y1 - y0
        first, second = self._pair()
        ground = 'duotone' if 'duotone' not in (first, second) else 'tint'
        self.sheet(self.under, 'strata', [x0 + w * .08, y0 + h * .04, x1 - w * .04, y1 - h * .1], ground,
                   ('cut', 'torn', 'torn', 'cut'), rng.uniform(1.0, 2.4))
        radius = min(w * .26, h * .33)
        cx = x0 + w * rng.uniform(.42, .6)
        self.disc(cx, y0 + h * .46, radius, 'spot' if _family(ground) != 'spot' else 'accent', layer=self.under)
        front = first if _family(first) not in ('spot', 'duotone') else 'night'
        self.sheet(self.under, 'strata', [x0, y0 + h * .56, x1 - w * .12, y1], front,
                   ('rip', 'torn', 'cut', 'cut'), rng.uniform(-2.4, -.8))
        self.sheet(self.under, 'strata', [x0 + w * .52, y0 + h * .7, x1, y1 - h * .04],
                   'grid' if _family(front) != 'kraft' else 'news', ('cut', 'cut', 'deckle', 'torn'),
                   rng.uniform(1.5, 3.5))
        self.tape(x0 + w * .78, y0 + h * .7, 44, rotation=rng.uniform(-30, -12))
        self.scribble('wave', [x0 + w * .1, y0 + h * .14, x0 + w * .32, y0 + h * .26], 'ink')

    def vignette(self, rect, kind=None):
        x0, y0, x1, y1 = inflate(rect, -8, -6)
        w, h = x1 - x0, y1 - y0
        if w < 110 or h < 88:
            return
        if kind is None:
            # Rotate the scenes through the deck, within what the opening allows.
            wide, compact = ('horizon', 'moon'), ('stack', 'moon', 'horizon')
            if w / h >= 1.6:
                kind = wide[self.variant % 2]
            elif w / h >= 1.0:
                kind = compact[self.variant % 3]
            else:
                kind = ('stack', 'moon')[self.variant % 2]
        getattr(self, kind)([x0, y0, x1, y1])

    def pieces(self):
        return dict(pieces=self.under + self.faces + self.over, strokes=self.strokes, inks=self.inks)


def tilt_members(plan, pieces):
    """Turn the native copy and marks with the face they sit on."""
    objects = {ob['id']: ob for ob in plan['objects']}
    for piece in pieces:
        angle = piece.get('rotation', 0)
        face = objects.get(piece.get('face'))
        if not angle or face is None:
            continue
        x0, y0, x1, y1 = piece['rect']
        pivot = [(x0 + x1) / 2, (y0 + y1) / 2]
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        for member in face.get('members', ()):
            ob = objects.get(member)
            if ob is None:
                continue
            if ob['kind'] == 'path':
                ob['paths'] = [[[pivot[0] + (x - pivot[0]) * c - (y - pivot[1]) * s,
                                 pivot[1] + (x - pivot[0]) * s + (y - pivot[1]) * c] for x, y in path]
                               for path in ob['paths']]
                from native_vectors import bounds
                ob['rect'] = bounds(ob['paths'], ob.get('line_width', 0) / 2 if ob.get('line') else 0)
            else:
                ob['rotation'] = angle
                ob['pivot'] = pivot


def _overprints(plan, composer):
    """Riso habits for data marks: a second plate out of register, a screened area."""
    points = []
    for ob in plan['objects']:
        if not ob.get('on_face'):
            continue
        if ob['kind'] == 'rect' and ob.get('data_point') or '-part-' in ob['id'] and ob['kind'] == 'rect':
            x0, y0, x1, y1 = ob['rect']
            first = ob.get('fill') == plan['ink_plan']['main'][0]
            composer.inks.append(dict(rect=[x0 + 2.6, y0 + 2.6, x1 + 2.6, y1 + 2.6],
                                      ink='inkB' if first else 'inkA', tone=(.42, .42), pitch=3.4,
                                      angle=30 if first else 60, opacity=.85))
        elif ob['kind'] == 'path' and ob.get('data_point', {}).get('axis') == 'y':
            xs = [p[0] for p in ob['paths'][0]]
            ys = [p[1] for p in ob['paths'][0]]
            points.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, ob['data_point']['zero_origin']))
        elif ob['kind'] == 'path' and '-ring-' in ob['id'] and ob.get('fill'):
            ring = [[x + 3.2, y + 3.2] for x, y in ob['paths'][0]]
            xs, ys = [p[0] for p in ring], [p[1] for p in ring]
            composer.inks.append(dict(rect=[min(xs), min(ys), max(xs), max(ys)], polygon=ring, ink='ink',
                                      tone=(.3, .3), pitch=3.4, angle=45, opacity=.55))
    if len(points) >= 2:
        # The area under a trend line prints as a fading screen.
        points.sort()
        base = points[0][2]
        polygon = [(x, y) for x, y, _ in points] + [(points[-1][0], base), (points[0][0], base)]
        top = min(y for _, y, _ in points)
        composer.inks.append(dict(rect=[points[0][0], top, points[-1][0], base], polygon=polygon, ink='inkB',
                                  tone=(.62, .06), direction=90, pitch=4.2, angle=30, opacity=.9))


def compose(plan, direction, title_rect, loose):
    """Arrange the page's collage. ``loose`` are rects of copy not on a face."""
    faces = [ob for ob in plan['objects'] if ob['kind'] == 'paper']
    mode = direction.get('_collage', 'rich')
    keepout = [inflate(title_rect, 4, 6)] + [inflate(r, 4) for r in loose]
    composer = Composer(direction.get('_collage_seed', plan.get('seed', 1)),
                        direction.get('_collage_variant', 0), keepout)
    cards = [f for f in faces if f['family'] == 'card']
    if len(cards) >= 2:
        composer.cards(cards)
    singles = [f for f in faces if f['family'] != 'card' or len(cards) < 2]
    for index, face in enumerate(singles):
        family = face['family']
        if family == 'chart':
            composer.clipping(face)
        elif family == 'note' or index > 0:
            composer.note(face, 'grid' if family == 'note' or index % 2 else None)
        else:
            composer.reading_sheet(face, rich=mode == 'rich' or len(singles) == 1)
    _overprints(plan, composer)
    if mode != 'quiet' and direction.get('_collage_vignette', True):
        occupied = keepout + [inflate(p['rect'], 12) for p in composer.under + composer.faces + composer.over]
        frame = (FRAME[0] + 18, max(FRAME[1] + 14, title_rect[3] + 12), FRAME[2] - 16, FRAME[3] - 8)
        opening = largest_opening(occupied, frame)
        if opening and (opening[2] - opening[0]) * (opening[3] - opening[1]) >= 21000:
            # A scene stays smaller than the evidence it accompanies.
            ow, oh = opening[2] - opening[0], opening[3] - opening[1]
            width, height = min(ow, 400), min(oh, 300)
            if width / height > 2.6:
                width = max(260, height * 2.6) if ow > 520 else width
            x0 = opening[2] - width if opening[0] + ow / 2 > 480 else opening[0]
            y0 = opening[1] + (oh - height) * (.5 if oh > ow else 1)
            charts = any(f['family'] == 'chart' for f in faces) or direction.get('_press_chart')
            composer.vignette([x0, y0, x0 + width, y0 + height], 'press' if charts and width / height < 1.9 else None)
    result = composer.pieces()
    tilt_members(plan, result['pieces'])
    stocks = {piece['face']: piece.get('stock', 'bone') for piece in result['pieces'] if piece.get('face')}
    for ob in plan['objects']:
        if ob.get('on_face') in stocks:
            ob['face_stock'] = stocks[ob['on_face']]
    plan['collage'] = result
    return result


def _mask(ink, height, width, scale):
    """Clip a printed area to a polygon given in plate points."""
    polygon = ink.get('polygon')
    if not polygon:
        return 1.0
    from PIL import Image, ImageDraw
    import numpy as np
    x0, y0 = ink['rect'][:2]
    layer = Image.new('L', (width, height), 0)
    ImageDraw.Draw(layer).polygon([((x - x0) * scale, (y - y0) * scale) for x, y in polygon], fill=255)
    return np.asarray(layer, np.float32) / 255


def render(collage, theme, seed, size=(960.0, 540.0), scale=2):
    """Rasterise a page collage to one transparent plate."""
    import paper_stock as ps

    plate = ps.Plate(size, scale, theme, seed)
    for piece in collage['pieces']:
        plate.place(piece)
    for ink in collage.get('inks', ()):
        low, high = ink.get('tone', (.1, .8))

        def coverage(h, w, ink=ink, low=low, high=high):
            tone = ps.gradient(h, w, ink.get('direction', 90), low, high) * _mask(ink, h, w, scale)
            return ps.halftone(h, w, tone, ink.get('pitch', 4.6), ink.get('angle', 30), scale)

        plate.ink(ink['rect'], coverage, theme[ink.get('ink', 'inkB')], ink.get('opacity', .9))
    for mark in collage.get('strokes', ()):
        plate.draw(mark['points'], theme[mark.get('ink', 'ink')], mark.get('width', 1.5))
    return plate
