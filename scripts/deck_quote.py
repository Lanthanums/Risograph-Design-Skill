"""Measured quote compositions with editable copy and source credit."""
from dataclasses import replace

import riso_kit as rk
import textmetrics as tm
import typefit as tf
from deck_title_wrap import choose_title_lines


def candidates(value, previous):
    length = len(tf.source_text(value).split())
    if length <= 13:
        order = ['broadside', 'margin', 'folio']
    elif length >= 38:
        order = ['folio', 'margin', 'broadside']
    else:
        order = ['margin', 'folio', 'broadside']
    return [layout for layout in order if layout != previous] + [layout for layout in order if layout == previous]


def _fit_quote(value, font, size, width, height):
    quote = tf.fit(value, font, size, width, height, minimum=24, ls=1.12, role='quote body')
    if (len(quote.lines) > 1 and len(quote.lines[-1].split()) == 1
            and '\n' not in tf.source_text(value)):
        measure = lambda s: tm.advance(s, font, quote.size, False)
        limit = (width - rk.NO_WRAP['pad_pt']) / rk.NO_WRAP['slack']
        lines = choose_title_lines(quote.text, len(quote.lines), measure, limit)
        if lines and len(lines) == len(quote.lines):
            quote = replace(quote, lines=tuple(lines), width=max(map(measure, lines)))
    return quote


def _measure(page, theme, layout, marked=False):
    left, top, right, bottom = rk.SAFE
    if layout == 'margin':
        width, credit_width, size = right-left-244, 166, 43
    elif layout == 'broadside':
        width = credit_width = right-left-142
        size = 53 if len(tf.source_text(page['lines']).split()) <= 13 else 46
    else:
        width = credit_width = right-left-130
        size = 40
    credits = []
    for role, value, size_pt in (('quote-attribution', page.get('attribution'), 18),
                                 ('quote-context', page.get('source'), 16)):
        if value:
            fit = tf.fit(value, theme.f_body, size_pt, credit_width, 100,
                         minimum=size_pt, role=role)
            credits.append((role, fit))
    support = sum(f.height + 5 for _, f in credits)
    headroom = 46 if layout == 'margin' else 70
    if marked and layout != 'margin':
        headroom += 26
    quote = _fit_quote(page['lines'], theme.f_display if layout == 'broadside' else theme.f_body,
                       size, width, bottom - top - headroom - (support if layout != 'margin' else 0))
    return quote, width, credits, credit_width, support


def draw_mark(slide, theme, x, y, size, centered=False, color=None, box=72):
    mark = tf.fit('\u201c', theme.f_display, size, box, box * 5 / 3, minimum=size, role='quote mark')
    return tf.draw(slide, x, y, box, mark, theme, role='quote-mark',
                   alignment='c' if centered else 'l',
                   color=color or (theme.display_ink if theme.on_red else theme.inkA))[0]


def _draw(slide, theme, layout, measured, marked=False, lift=0):
    quote, width, credits, credit_width, support = measured
    left, top, right, bottom = rk.SAFE
    bottom -= lift
    accent = theme.paper if theme.on_red else theme.inkA
    align = 'c' if layout == 'broadside' else 'l'
    color = theme.front_ink
    if layout == 'margin':
        x = left + 224
        y = top + (bottom - top - max(quote.height, support + 14)) * .43
        credit_x, credit_y = left + 14, y + (48 if marked else 16)
        # Two short impressions signal the source column without boxing the quote.
        if marked:
            draw_mark(slide, theme, credit_x, y - 51, 78)
        else:
            rk.rect(slide, credit_x, y, 28, 3, fill=accent)
            rk.rect(slide, credit_x + 14, y + 4, 27, 3, fill=theme.inkB)
    elif layout == 'broadside':
        x = (left + right - width) / 2
        y = top + (bottom - top - quote.height - support - 22) * .38
        center = (left + right) / 2
        if marked:
            y = max(top + 68, y)
            draw_mark(slide, theme, center - 36, y - 72, 80, centered=True)
        else:
            rk.rect(slide, center - 27, y - 21, 35, 4, fill=accent)
            rk.rect(slide, center - 8, y - 17, 35, 4, fill=theme.inkB)
        credit_x, credit_y = x, y + quote.height + 22
    else:
        x = left + 54
        y = top + (bottom - top - quote.height - support - 24) * .33
        if marked:
            y = max(top + 72, y)
        credit_x, credit_y = x, y + quote.height + 21
        end = credit_y + support if credits else y + quote.height
        a, b, c, d = x-23, y-(56 if marked else 17), x+width+24, end+12
        rk.freeform(slide, [(a+6,b+5),(c+8,b+6),(c+10,d+5),(a+7,d+8)], fill=theme.inkB, alpha=38)
        theme.t['quote-folio-stock'] = 'FFFDF4'
        rk.freeform(slide, [(a,b+2),(c-14,b),(c,b+12),(c-3,d),(a,d-3)], fill=theme.t['quote-folio-stock'])
        if marked:
            draw_mark(slide, theme, x, y - 66, 74, color=theme.inkA)
        else:
            rk.rect(slide, x, y - 6, 28, 2.5, fill=theme.inkA)
        color = theme.text
    tf.draw(slide, x, y, width, quote, theme, role='quote-body', alignment=align, color=color)
    for role, fit in credits:
        tf.draw(slide, credit_x, credit_y, credit_width, fit, theme, role=role, alignment=align, color=color)
        credit_y += fit.height + 5


def draw(slide, page, theme, layouts, number, marked=False):
    from layout_check import check_slide

    for layout in layouts:
        start = len(slide.shapes)
        try:
            measured = _measure(page, theme, layout, marked)
            # Overprinted circles hold the foot of the page, so the words sit higher.
            _draw(slide, theme, layout, measured, marked, 70 if page.get('_quote_field') == 'bloom' else 0)
            report = check_slide(slide, number, archetype='quote')
            if any(f.startswith('largest quiet rectangle') for f in report['fails']):
                raise ValueError(f'{layout} leaves too little quiet space around the quotation')
        except ValueError as exc:
            error = exc
            for shape in list(slide.shapes)[start:]:
                shape._element.getparent().remove(shape._element)
        else:
            return layout
    raise error


def paper_mark(slide, x, y, height, color):
    """An opening quotation mark drawn as one editable shape: two inked sixes."""
    import math
    from native_vectors import bounds, native_path

    width = height / 2.05
    r = width / 2

    def blob(ox):
        tip = (ox + width * .97, y)
        outer = [((1-t)**2 * tip[0] + 2*(1-t)*t * (ox + width * .04) + t*t * ox,
                  (1-t)**2 * tip[1] + 2*(1-t)*t * (y + height * .24) + t*t * (y + height - r))
                 for t in [i / 10 for i in range(11)]]
        bowl = [(ox + r + r * math.cos(math.radians(a)), y + height - r + r * math.sin(math.radians(a)))
                for a in range(170, -60, -10)]
        last = bowl[-1]
        inner = [((1-t)**2 * last[0] + 2*(1-t)*t * (ox + width * .56) + t*t * tip[0],
                  (1-t)**2 * last[1] + 2*(1-t)*t * (y + height * .3) + t*t * tip[1])
                 for t in [i / 8 for i in range(1, 8)]]
        return [list(point) for point in outer + bowl + inner]

    paths = [blob(x), blob(x + width * 1.2)]
    shape = native_path(slide, dict(id='quote-mark', rect=bounds(paths), paths=paths, fill=color, closed=True))
    shape.name = 'quote-mark[paper]'
    return shape


def draw_paper(slide, page, theme, layouts, number, collage, made):
    """Set a quotation on a torn sheet: a hanging mark above, the credit on a slip.

    The classic composition stays reserved for the featured quotation. Every
    other quotation gets this treatment, so each one opens with a large mark.
    """
    from deck_collage import FRAME, Composer
    from deck_renderer import _turn
    from layout_check import check_slide

    left, top, right, bottom = rk.SAFE
    error = ValueError('No quotation layout fits')
    for layout in layouts:
        start = len(slide.shapes)
        try:
            quote, width, credits, credit_width, support = _measure(page, theme, layout, True)
            reach = max(quote.width, 300)
            slip_width = max((fit.width for _, fit in credits), default=0)
            if layout == 'broadside':
                x = (left + right - width) / 2
                y = top + max(96, (bottom - top - quote.height - support - 40) * .46)
                face = [(left + right - reach) / 2 - 44, y - 34, (left + right + reach) / 2 + 44,
                        y + quote.height + 30]
                credit_x = (left + right - slip_width) / 2
                align = 'c'
            elif layout == 'margin':
                x = right - reach - 60
                y = top + max(92, (bottom - top - quote.height - support - 40) * .42)
                face = [x - 34, y - 32, x + reach + 38, y + quote.height + 30]
                credit_x = max(left + 18, x - slip_width * .55)
                align = 'l'
            else:
                x = left + 62
                y = top + max(94, (bottom - top - quote.height - support - 40) * .4)
                face = [x - 34, y - 32, x + reach + 40, y + quote.height + 30]
                credit_x = x + min(reach * .3, max(0, reach - slip_width))
                align = 'l'
            credit_y = face[3] - 5
            slip = None
            if credits:
                slip = [credit_x - 15, credit_y - 9, credit_x + slip_width + 19, credit_y + support + 6]
            extent = face if slip is None else [min(face[0], slip[0]), face[1], max(face[2], slip[2]), slip[3]]
            if extent[0] < FRAME[0] + 8 or extent[2] > FRAME[2] - 8 or extent[3] > FRAME[3] - 8:
                raise ValueError(f'{layout} sheet does not fit the page')

            composer = Composer(collage['seed'], collage['variant'], [])
            composer.reading_sheet(dict(id='quote-face', rect=face), rich=True)
            sheet = next(piece for piece in composer.faces if piece.get('face') == 'quote-face')
            pivot = [(face[0] + face[2]) / 2, (face[1] + face[3]) / 2]
            turned = dict(rotation=sheet['rotation'], pivot=pivot)
            # The mark hangs across the top edge of the sheet.
            size = 56
            mark_left = (left + right) / 2 - size * .52 if align == 'c' else face[0] + 26
            _turn(paper_mark(slide, mark_left, face[1] - size * .56, size, theme.inkA), turned)
            for shape in tf.draw(slide, x, y, width, quote, theme, role='quote-body', alignment=align,
                                 color=theme.text):
                _turn(shape, turned)
            if slip:
                tilt = composer.rng.uniform(1.2, 2.4) * (-1 if sheet['rotation'] > 0 else 1)
                composer.sheet(composer.faces, 'slip', slip, ('kraft', 'cream')[collage['variant'] % 2],
                               ('cut', 'torn', 'cut', 'cut'), tilt)
                composer.tape(slip[0] + 12, slip[1] + 3, 40, rotation=-38)
                slip_turn = dict(rotation=tilt, pivot=[(slip[0] + slip[2]) / 2, (slip[1] + slip[3]) / 2])
                line_y = credit_y
                for role, fit in credits:
                    for shape in tf.draw(slide, credit_x, line_y, slip_width + 6, fit, theme, role=role,
                                         alignment='l', color=theme.text):
                        _turn(shape, slip_turn)
                    line_y += fit.height + 5
            report = check_slide(slide, number, archetype='quote')
            if any(f.startswith('largest quiet rectangle') for f in report['fails']):
                raise ValueError(f'{layout} leaves too little quiet space around the quotation')
        except ValueError as exc:
            error = exc
            for shape in list(slide.shapes)[start:]:
                shape._element.getparent().remove(shape._element)
        else:
            made['collage'] = composer.pieces()
            return layout
    raise error
