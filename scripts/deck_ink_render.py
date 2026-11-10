"""Write fitted English title plates as editable PowerPoint text."""
import textmetrics as tm
import typefit as tf
from deck_ink import plates


def allowance(theme, size, style):
    offsets = [abs(v) for dx, dy, _ in plates(theme, size, style) for v in (dx, dy)]
    return 2 * max(offsets, default=0)


def draw(slide, x, y, width, fitted, theme, style, role, color=None):
    layers = plates(theme, fitted.size, style)
    if not layers:
        return tf.draw(slide, x, y, width, fitted, theme, role=role, color=color)

    import riso_kit as rk

    before = len(slide.shapes)
    face = tm.font(fitted.font, fitted.size, fitted.bold)
    left_pad = max(0, -min((face.getbbox(line)[0] for line in fitted.lines if line), default=0)) + .5
    guard = fitted.offset / 2
    for i, line in enumerate(fitted.lines):
        if not line:
            continue
        front = (0, 0, color or theme.display_ink)
        for dx, dy, ink in (*layers, front):
            if ink not in theme.t.values():
                theme.t[f'deck-plate-{len(theme.t)}'] = ink
            shape = rk.text(slide, x + guard + left_pad + dx, y + guard + i * fitted.pitch + dy,
                            width - fitted.offset - left_pad, fitted.pitch,
                            [dict(runs=[(line, {})], font=fitted.font, size=fitted.size,
                                  bold=fitted.bold, color=ink, ls=fitted.ls, spc=fitted.spc)],
                            wrap=False, fit_nowrap=False)
            shape.name = role + ('/riso-layer[front]' if (dx, dy) == (0, 0) else '/riso-layer[back]')
    return list(slide.shapes)[before:]
