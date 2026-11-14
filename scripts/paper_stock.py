"""Seeded raster paper for deck collage plates.

A piece is a sheet of stock with per-edge cuts and tears, an exposed fibre
core on torn edges, riso ink printed on its face, and a contact shadow. A
plate is one transparent picture the size of the slide. Copy and data marks
stay native above it.
"""
from hashlib import sha256
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# Edge grammar: octaves of (wavelength pt, amplitude pt), then the exposed
# fibre core as (minimum pt, variable pt). A tear wanders at several scales;
# a cut is nearly straight and shows no core.
EDGES = {
    'cut': (((320, .35),), (0, 0)),
    'deckle': (((46, .7), (7, .5), (2.2, .3)), (.3, .7)),
    'torn': (((130, 2.4), (38, 1.6), (10, .95), (2.8, .5)), (1.1, 2.9)),
    'rip': (((300, 9.5), (96, 4.6), (30, 2.1), (8, 1.05), (2.6, .5)), (1.5, 4.2)),
}
PAD = 16  # pt of transparent margin around a piece, for tear amplitude


def rng_for(*parts):
    digest = sha256('|'.join(map(str, parts)).encode()).hexdigest()
    return np.random.default_rng(int(digest[:16], 16))


def rgb(color):
    color = color.lstrip('#')
    return np.array([int(color[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


def mix(a, b, weight):
    return rgb(a) * (1 - weight) + rgb(b) * weight


def to_hex(color):
    return ''.join(f'{int(round(float(v) * 255)):02X}' for v in np.clip(color, 0, 1))


def _smooth(t):
    return t * t * (3 - 2 * t)


def noise1(n, wavelength, rng):
    """Smooth value noise in [-1, 1] sampled at n pixels."""
    wavelength = max(1.0, wavelength)
    knots = rng.uniform(-1, 1, int(n / wavelength) + 3)
    x = np.arange(n) / wavelength + rng.uniform(0, 1)
    i = np.floor(x).astype(int)
    f = _smooth(x - i)
    return knots[i] * (1 - f) + knots[i + 1] * f


def noise2(height, width, cell, rng):
    """Smooth 2D value noise in roughly [-1, 1]."""
    cell = max(1.0, cell)
    gh, gw = int(height / cell) + 3, int(width / cell) + 3
    grid = Image.fromarray(rng.uniform(-1, 1, (gh, gw)).astype(np.float32), mode='F')
    big = grid.resize((int(gw * cell), int(gh * cell)), Image.BICUBIC)
    oy, ox = rng.integers(0, max(1, int(cell))), rng.integers(0, max(1, int(cell)))
    return np.asarray(big)[oy:oy + height, ox:ox + width]


def _profile(n, kind, scale, rng):
    """Displacement into the sheet and fibre-core width along one edge, in px."""
    octaves, (core_min, core_var) = EDGES[kind]
    shift = np.zeros(n, np.float32)
    for wavelength, amplitude in octaves:
        shift += noise1(n, wavelength * scale, rng) * amplitude * scale
    if kind == 'cut':
        shift += np.linspace(-1, 1, n) * rng.uniform(-.7, .7) * scale
        return shift, np.zeros(n, np.float32)
    # The core is wide where a flap of the face tore away and thin elsewhere.
    flap = np.clip(noise1(n, 55 * scale, rng) * .9 + noise1(n, 13 * scale, rng) * .5, 0, None)
    core = (core_min + core_var * flap + .35 * np.abs(noise1(n, 3.2 * scale, rng))) * scale
    return shift, core.astype(np.float32)


def _ramp(distance, softness=1.0):
    return np.clip(distance / softness + .5, 0, 1)


def _texture(height, width, stock, scale, rng):
    """Multiplicative paper grain: mottle, tooth and a few visible fibres."""
    strength = {'kraft': 1.7, 'news': .85, 'bone': 1.0}.get(stock, 1.0)
    field = 1 + strength * (.022 * noise2(height, width, 46 * scale, rng)
                            + .016 * noise2(height, width, 7 * scale, rng)
                            + .013 * noise2(height, width, 1.3 * scale, rng))
    fibres = Image.new('L', (width, height), 128)
    draw = ImageDraw.Draw(fibres)
    count = int(height * width / (scale * scale) / (260 if stock == 'kraft' else 520))
    for _ in range(count):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        angle = rng.uniform(0, math.pi)
        length = rng.uniform(4, 15) * scale
        bend = rng.uniform(-.5, .5)
        points = [(x + length * t * math.cos(angle + bend * t), y + length * t * math.sin(angle + bend * t))
                  for t in (0, .5, 1)]
        tone = 128 + int(rng.choice((-1, 1)) * rng.uniform(5, 15 if stock == 'kraft' else 9))
        draw.line(points, fill=tone, width=max(1, round(.45 * scale)))
    fibres = np.asarray(fibres.filter(ImageFilter.GaussianBlur(.35 * scale)), np.float32) / 128
    field = field * fibres
    if stock == 'kraft':
        # Laid lines from the mould, barely visible.
        field = field * (1 + .012 * np.sin(np.arange(width) / (1.15 * scale))[None, :])
    return field.astype(np.float32)


def halftone(height, width, tone, pitch, angle, scale, origin=(0, 0)):
    """Coverage of a round-dot screen for a tone field in [0, 1]."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    xx, yy = xx + origin[0], yy + origin[1]
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    step = pitch * scale
    u = (xx * c + yy * s) / step
    v = (-xx * s + yy * c) / step
    du, dv = u - np.round(u), v - np.round(v)
    distance = np.sqrt(du * du + dv * dv) * step
    radius = np.sqrt(np.clip(tone, 0, 1)) * step * .64
    return np.clip(radius - distance + .5, 0, 1) * (np.asarray(tone) > .012)


def gradient(height, width, direction, start=0.0, end=1.0, curve=1.0):
    """Linear tone ramp; direction in degrees, 0 = left to right."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    c, s = math.cos(math.radians(direction)), math.sin(math.radians(direction))
    t = (xx / max(1, width - 1) - .5) * c + (yy / max(1, height - 1) - .5) * s
    t = np.clip(t / (abs(c) + abs(s)) + .5, 0, 1) ** curve
    return start + (end - start) * t


def _ink(base, color, coverage):
    """Riso ink is translucent: it multiplies with whatever is below it."""
    return base * (1 - coverage[..., None] * (1 - rgb(color)[None, None, :]))


def _flood(height, width, scale, rng, density=.94):
    """An ink flood with roller unevenness and pinholes where paper shows."""
    drift = .05 * noise2(height, width, 60 * scale, rng) + .025 * noise2(height, width, 9 * scale, rng)
    # Soy ink sits unevenly: a fine tooth everywhere and rare pinholes.
    tooth = .035 * noise2(height, width, .9 * scale, rng)
    pinholes = noise2(height, width, 1.1 * scale, rng) > .9
    banding = .012 * np.sin(np.arange(height) / (2.6 * scale))[:, None]
    return np.clip(density + drift + tooth + banding - .16 * pinholes, 0, 1).astype(np.float32)


def _greek(height, width, scale, rng, column=64, leading=4.3):
    """Columns of newspaper body copy seen from a distance. No letterforms."""
    layer = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(layer)
    gutter = 7 * scale
    x = rng.uniform(-column * .5, 0) * scale
    while x < width:
        y = rng.uniform(0, leading) * scale
        right = x + column * scale
        while y < height:
            if rng.random() < .045:
                # A crosshead: two heavier short lines and a space.
                for _ in range(2):
                    draw.rectangle([x, y, x + rng.uniform(.5, .9) * column * scale, y + 2.3 * scale], fill=235)
                    y += 5.4 * scale
                y += 3 * scale
                continue
            cursor = x
            last = rng.random() < .1
            limit = x + (rng.uniform(.3, .8) if last else 1) * column * scale
            while cursor < limit - 3 * scale:
                word = rng.uniform(3.5, 12) * scale
                end = min(cursor + word, limit)
                draw.rectangle([cursor, y, end, y + 1.3 * scale], fill=int(rng.uniform(135, 200)))
                cursor = end + 1.7 * scale
            y += leading * scale * (1.9 if last else 1)
        draw.rectangle([right + gutter * .45, 0, right + gutter * .45 + .35 * scale, height], fill=120)
        x = right + gutter
    return np.asarray(layer.filter(ImageFilter.GaussianBlur(.3 * scale)), np.float32) / 255


def _ruling(height, width, scale, pitch, both, origin=3.0):
    layer = np.zeros((height, width), np.float32)
    thickness = max(1, round(.42 * scale))
    position = origin * scale
    while position < height:
        layer[int(position):int(position) + thickness, :] = 1
        position += pitch * scale
    if both:
        position = origin * scale
        while position < width:
            layer[:, int(position):int(position) + thickness] = 1
            position += pitch * scale
    return layer


def stock_colors(theme):
    """Paper stocks derived from the deck palette; the kraft hue is fixed."""
    paper, ink = theme['paper'], theme['ink']
    return {
        'bone': mix(paper, 'FFFFFF', .66),
        'cream': mix(paper, 'FFF6DC', .5),
        'kraft': mix('C6A074', paper, .1),
        'news': mix(paper, 'DAD4C6', .55),
        'core': mix(paper, 'FFFFFF', .88),
        'shadow': mix(ink, '3A2A1C', .45),
    }


def render_piece(piece, theme, scale, seed):
    """Return (rgba float array, pad px) for one unrotated piece."""
    rng = rng_for(seed, piece['id'])
    width_pt, height_pt = piece['size']
    pad = int(round(PAD * scale))
    w, h = int(round(width_pt * scale)), int(round(height_pt * scale))
    W, H = w + 2 * pad, h + 2 * pad
    colors = stock_colors(theme)
    stock = piece.get('stock', 'bone')
    shape = piece.get('shape', 'sheet')
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    fuzz = noise2(H, W, 1.25 * scale, rng) * .55 * scale

    if shape == 'disc':
        cx, cy, radius = W / 2, H / 2, min(w, h) / 2
        theta = np.arctan2(yy - cy, xx - cx)
        wobble = sum(a * scale * np.sin(k * theta + rng.uniform(0, math.tau))
                     for k, a in ((2, .7), (3, .45), (7, .22)))
        distance = radius + wobble - np.hypot(xx - cx, yy - cy)
        outer = _ramp(distance + fuzz * .25)
        inner = outer
    else:
        top, right, bottom, left = piece.get('edges', ('cut', 'cut', 'torn', 'cut'))
        distances, cores = [], []
        for kind, length in ((top, W), (bottom, W), (left, H), (right, H)):
            shift, core = _profile(length, kind, scale, rng)
            distances.append(shift)
            cores.append(core)
        d_top = yy - (pad + distances[0][None, :])
        d_bottom = (pad + h - distances[1][None, :]) - yy
        d_left = xx - (pad + distances[2][:, None])
        d_right = (pad + w - distances[3][:, None]) - xx
        soft = [(.55 if kind == 'cut' else 1.0) for kind in (top, bottom, left, right)]
        rough = [(0.0 if kind == 'cut' else 1.0) for kind in (top, bottom, left, right)]
        fields = (d_top, d_bottom, d_left, d_right)
        core_fields = (cores[0][None, :], cores[1][None, :], cores[2][:, None], cores[3][:, None])
        outer = np.ones((H, W), np.float32)
        inner = np.ones((H, W), np.float32)
        ragged = noise2(H, W, 3.4 * scale, rng) * .8 * scale
        for field, core, softness, roughness in zip(fields, core_fields, soft, rough):
            outer = outer * _ramp(field + fuzz * roughness, softness)
            inner = inner * _ramp(field - core + (fuzz * 1.4 + ragged) * roughness, softness * 1.3)

    grain = _texture(H, W, stock, scale, rng)
    face = np.broadcast_to(colors.get(stock, colors['bone'])[None, None, :], (H, W, 3)).copy()
    origin = (int(rng.integers(0, 64)), int(rng.integers(0, 64)))
    for layer in piece.get('print', ()):
        kind = layer['kind']
        color = theme[layer['ink']] if layer.get('ink') in theme else layer.get('color', theme['inkA'])
        opacity = layer.get('opacity', 1.0)
        if kind == 'flood':
            coverage = _flood(H, W, scale, rng, layer.get('density', .94))
        elif kind == 'halftone':
            if 'tone' in layer:
                tone = np.full((H, W), layer['tone'], np.float32)
            else:
                tone = gradient(H, W, layer.get('direction', 0), layer.get('start', 0),
                                layer.get('end', .7), layer.get('curve', 1.0))
            tone = tone * (1 + .06 * noise2(H, W, 30 * scale, rng))
            coverage = halftone(H, W, tone, layer.get('pitch', 4.6), layer.get('angle', 30), scale, origin)
            coverage = coverage * (1 - .18 * (noise2(H, W, 1.5 * scale, rng) > .7))
        elif kind == 'greek':
            coverage = _greek(H, W, scale, rng, layer.get('column', 64), layer.get('leading', 4.3))
        elif kind in ('rule', 'grid'):
            coverage = _ruling(H, W, scale, layer.get('pitch', 13), kind == 'grid')
        elif kind == 'band':
            # A printed bar across the sheet, in piece fractions.
            x0, y0, x1, y1 = layer['rect']
            coverage = np.zeros((H, W), np.float32)
            coverage[pad + int(y0 * h):pad + int(y1 * h), pad + int(x0 * w):pad + int(x1 * w)] = 1
            coverage = coverage * _flood(H, W, scale, rng, .95)
        else:
            raise ValueError(f'Unknown print layer {kind!r}')
        dx, dy = layer.get('offset', (0, 0))
        if dx or dy:
            coverage = np.roll(coverage, (int(round(dy * scale)), int(round(dx * scale))), (0, 1))
        face = _ink(face, color, np.clip(coverage * opacity, 0, 1))
    face = face * grain[..., None]
    core = colors['core'][None, None, :] * (1 + .5 * (grain[..., None] - 1))
    color = core * (1 - inner[..., None]) + face * inner[..., None]
    if piece.get('translucent'):
        # Masking tape: the page shows through and the ends are pinked.
        teeth = 2.2 * scale
        saw = np.abs((yy / teeth) % 2 - 1) * teeth * .55
        outer = outer * _ramp(xx - pad - saw) * _ramp(pad + w - xx - saw)
        streak = 1 + .05 * noise2(H, W, 2.2 * scale, rng) + .04 * np.sin(yy / (1.1 * scale))
        color = np.broadcast_to(rgb(piece.get('tint', 'E9DDB8'))[None, None, :], (H, W, 3)) * streak[..., None]
        outer = outer * piece['translucent']
    out = np.dstack([np.clip(color, 0, 1), outer]).astype(np.float32)
    return out, pad


def stroke(points, width_pt, color, scale, seed, size):
    """A slightly dry pencil line through points given in plate pt."""
    rng = rng_for(seed, 'stroke', len(points), round(points[0][0]))
    W, H = int(size[0] * scale), int(size[1] * scale)
    layer = Image.new('L', (W, H), 0)
    draw = ImageDraw.Draw(layer)
    pts = [(x * scale + rng.normal(0, .25 * scale), y * scale + rng.normal(0, .25 * scale)) for x, y in points]
    draw.line(pts, fill=255, width=max(1, round(width_pt * scale)), joint='curve')
    alpha = np.asarray(layer.filter(ImageFilter.GaussianBlur(.28 * scale)), np.float32) / 255
    alpha = alpha * (.82 + .18 * (noise2(H, W, 1.4 * scale, rng) > -.35))
    out = np.zeros((H, W, 4), np.float32)
    out[..., :3] = rgb(color)
    out[..., 3] = alpha
    return out


class Plate:
    """One slide-sized transparent composite in premultiplied float."""

    def __init__(self, size, scale, theme, seed):
        self.width, self.height = size
        self.scale, self.theme, self.seed = scale, theme, seed
        self.W, self.H = int(round(size[0] * scale)), int(round(size[1] * scale))
        self.rgb = np.zeros((self.H, self.W, 3), np.float32)
        self.alpha = np.zeros((self.H, self.W), np.float32)
        self.records = []

    def _window(self, left, top, layer):
        h, w = layer.shape[:2]
        x0, y0 = max(0, left), max(0, top)
        x1, y1 = min(self.W, left + w), min(self.H, top + h)
        if x1 <= x0 or y1 <= y0:
            return None
        return (slice(y0, y1), slice(x0, x1)), layer[y0 - top:y1 - top, x0 - left:x1 - left]

    def _over(self, left, top, color, alpha, multiply=False):
        """Composite straight colour + alpha at a pixel offset."""
        hit = self._window(left, top, np.dstack([color, alpha]))
        if hit is None:
            return
        where, layer = hit
        src, a = layer[..., :3], layer[..., 3]
        dst, da = self.rgb[where], self.alpha[where]
        if multiply:
            # Ink over paper already on the plate multiplies; over the bare
            # page it stays a translucent film for the slide to show through.
            under = np.where(da[..., None] > 1e-4, dst / np.maximum(da[..., None], 1e-4), 1.0)
            inked = under * (1 - a[..., None] * (1 - src))
            self.rgb[where] = inked * da[..., None] + src * (a * (1 - da))[..., None]
            self.alpha[where] = da + a * (1 - da)
        else:
            self.rgb[where] = src * a[..., None] + dst * (1 - a[..., None])
            self.alpha[where] = a + da * (1 - a)

    def place(self, piece):
        """Draw one piece centred on its rect, rotated, with its shadow."""
        scale = self.scale
        x0, y0, x1, y1 = piece['rect']
        piece = dict(piece, size=(x1 - x0, y1 - y0))
        layer, pad = render_piece(piece, self.theme, scale, self.seed)
        image = Image.fromarray((np.dstack([layer[..., :3] * layer[..., 3:4], layer[..., 3]]) * 255
                                 ).astype(np.uint8), 'RGBa')
        angle = piece.get('rotation', 0)
        if angle:
            image = image.rotate(-angle, Image.BICUBIC, expand=True)
        data = np.asarray(image, np.float32) / 255
        alpha = data[..., 3]
        color = np.where(alpha[..., None] > 1e-4, data[..., :3] / np.maximum(alpha[..., None], 1e-4), 0)
        cx, cy = (x0 + x1) / 2 * scale, (y0 + y1) / 2 * scale
        left, top = int(round(cx - data.shape[1] / 2)), int(round(cy - data.shape[0] / 2))
        lift = piece.get('lift', 1.0)
        if lift:
            margin = int(12 * scale)
            padded = np.pad(alpha, margin)
            shade = stock_colors(self.theme)['shadow']
            for sigma, dx, dy, strength in ((3.4 * lift, 1.6 * lift, 2.8 * lift, .26), (.75, .4, .9, .30)):
                blurred = np.asarray(Image.fromarray((padded * 255).astype(np.uint8)).filter(
                    ImageFilter.GaussianBlur(sigma * scale)), np.float32) / 255
                opacity = strength * (.55 if piece.get('translucent') else 1)
                self._over(left - margin + int(round(dx * scale)), top - margin + int(round(dy * scale)),
                           np.broadcast_to(shade, blurred.shape + (3,)), blurred * opacity)
        self._over(left, top, color, alpha)
        self.records.append(dict(id=piece['id'], rect=[round(v, 1) for v in piece['rect']],
                                 stock=piece.get('stock', 'bone'), rotation=angle,
                                 role=piece.get('role', 'scrap')))

    def ink(self, rect, coverage_fn, color, opacity=.9):
        """Print straight onto the plate: coverage_fn(height, width) -> [0, 1]."""
        scale = self.scale
        x0, y0, x1, y1 = rect
        w, h = int(round((x1 - x0) * scale)), int(round((y1 - y0) * scale))
        if w < 2 or h < 2:
            return
        coverage = np.clip(coverage_fn(h, w), 0, 1).astype(np.float32) * opacity
        self._over(int(round(x0 * scale)), int(round(y0 * scale)),
                   np.broadcast_to(rgb(color), (h, w, 3)), coverage, multiply=True)

    def draw(self, points, color, width=1.5):
        layer = stroke(points, width, color, self.scale, self.seed, (self.width, self.height))
        self._over(0, 0, layer[..., :3], layer[..., 3], multiply=True)

    def image(self):
        color = np.where(self.alpha[..., None] > 1e-4, self.rgb / np.maximum(self.alpha[..., None], 1e-4), 0)
        data = np.dstack([np.clip(color, 0, 1), np.clip(self.alpha, 0, 1)])
        return Image.fromarray((data * 255 + .5).astype(np.uint8), 'RGBA')

    def bounds(self):
        rows = np.flatnonzero(self.alpha.max(axis=1) > .01)
        cols = np.flatnonzero(self.alpha.max(axis=0) > .01)
        if not len(rows):
            return None
        return [cols[0] / self.scale, rows[0] / self.scale, (cols[-1] + 1) / self.scale, (rows[-1] + 1) / self.scale]
