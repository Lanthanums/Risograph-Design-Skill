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


def draw_mark(slide, theme, x, y, size, centered=False, color=None):
    mark = tf.fit('\u201c', theme.f_display, size, 72, 120, minimum=size, role='quote mark')
    return tf.draw(slide, x, y, 72, mark, theme, role='quote-mark',
                   alignment='c' if centered else 'l',
                   color=color or (theme.display_ink if theme.on_red else theme.inkA))[0]


def _draw(slide, theme, layout, measured, marked=False):
    quote, width, credits, credit_width, support = measured
    left, top, right, bottom = rk.SAFE
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
            _draw(slide, theme, layout, measured, marked)
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
