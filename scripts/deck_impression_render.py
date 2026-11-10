"""Draw native print accents inside planned deck rectangles."""
from glyphs import circle
from native_vectors import bounds, native_path
import riso_kit as rk


def draw(slide, item, theme, number):
    x, y, x1, y1 = item['rect']
    w, h = x1 - x, y1 - y
    ink = theme.paper if theme.on_red else theme.inkA
    second = theme.accent1 if theme.on_red else theme.inkB
    kind = item['kind'].replace('_', '-')
    name = f"deck-mark[{kind}]/{number}"

    def rect(left, top, width, height, color):
        shape = rk.rect(slide, x + left*w, y + top*h, width*w, height*h, fill=color)
        shape.name = name

    def path(points, color, *, fill=False, width=1.2):
        paths = [[[x+a*w, y+b*h] for a, b in line] for line in points]
        shape = native_path(slide, dict(id=name, paths=paths, rect=bounds(paths),
                                       fill=color if fill else None,
                                       line=None if fill else color,
                                       closed=fill, line_width=width))
        shape.name = name

    if kind in ('screen', 'dot-screen', 'halftone'):
        columns = max(5, min(13, int(w/4)))
        rows = max(3, min(7, int(h/4)))
        dots = [
            circle((c + .6 + .22*(r % 2))/columns, (r + .6)/rows,
                   (.33 - .23*c/columns)/max(columns, rows), n=8)
            for r in range(rows) for c in range(columns)
        ]
        path(dots, ink, fill=True)
    elif kind in ('swatch', 'plate-swatch', 'overprint'):
        rect(.02, .12, .63, .59, ink)
        rect(.36, .30, .62, .59, second)
        rect(.36, .30, .29, .41, theme.inkAB if not theme.on_red else theme.ink_deep)
    elif kind in ('register', 'register-tick', 'offset-register'):
        path([[[.12,.70],[.12,.20],[.74,.20]], [[.44,.12],[.44,.85]]], ink)
        path([[[.23,.89],[.23,.37],[.89,.37]], [[.57,.27],[.57,.96]]], second)
    elif kind in ('rule', 'notch', 'folio-notch'):
        path([[[.04,.33],[.87,.33]], [[.04,.70],[.53,.70]]], ink)
        path([[[.63,.70],[.95,.70]]], second, width=2.1)
    else:
        raise ValueError(f'Unknown deck impression kind {kind!r}')
