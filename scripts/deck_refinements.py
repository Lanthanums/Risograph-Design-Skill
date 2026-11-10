"""Scoped v4.6 revisions after the approved deck furniture has been planned."""
from copy import copy
import re
from types import SimpleNamespace

import layout
import riso_kit as rk
import textmetrics as tm
from layout_check import check_slide
from deck_press_chart import PRESS_FORMS


def featured_quote(pages, reversed_pages):
    """Give the classic editorial composition one opportunity in a deck."""
    options = []
    for number, page in enumerate(pages, 1):
        if page.get('archetype') != 'quote' or not page.get('editorial'):
            continue
        direction = page.get('art_direction', {})
        style = direction.get('quote_layout', 'auto')
        priority = direction.get('quote_priority', 'auto')
        if style == 'classic' or (style == 'auto' and priority != 'supporting'):
            from typefit import source_text
            length = len(source_text(page['lines']).split())
            options.append((style == 'classic', priority == 'featured', 6 <= length <= 35,
                            number in reversed_pages, -number))
    return -max(options)[-1] if options else None


def revise(slide, page, theme, number, total, meta, original, feature, previous, writers, media):
    """Keep the baseline's background, chrome and RNG; transact only the content."""
    arch = page['archetype']
    direction = page.get('art_direction', {})
    writer, classic_quote = writers
    modules = page.get('modules', [])
    forms = {module.get('visual') for module in modules}
    if arch in ('cover', 'divider', 'closing'):
        return {}
    quote = arch == 'quote' and page.get('editorial')
    chart = bool(forms & PRESS_FORMS)
    cards = 'takeaway-list' in forms and theme.deck_paper_mode != 'off'
    inline_quote = 'pull-quote' in forms
    if not any((quote, chart, cards, inline_quote)):
        return {}

    local = copy(theme)
    local.t = dict(theme.t)
    local.evidence_pages = []
    from qa import Report, geometry_checks

    def failures():
        report = Report()
        geometry_checks(report, slide, number, SimpleNamespace(
            edge_tol=1.5, text_protection=9.0, media=media), canvas=rk.DECK_CANVAS)
        return ({item['detail'] for item in report.items if item['severity'] == 'fail'}
                | set(check_slide(slide, number, archetype=arch)['fails']))

    original_check = failures()
    tree = slide.shapes._spTree
    former = [(tree.index(shape._element), shape._element) for shape in original]
    insert_at = former[0][0] if former else len(tree)
    for _, element in former:
        tree.remove(element)
    existing = {shape._element for shape in slide.shapes}

    def transaction(draw):
        try:
            result = draw()
            new = [shape._element for shape in slide.shapes if shape._element not in existing]
            for index, element in enumerate(new, insert_at):
                tree.insert(index, element)
            new_failures = failures() - original_check
            if new_failures:
                raise ValueError('; '.join(sorted(new_failures)))
            return result
        except ValueError as exc:
            errors.append(str(exc))
            for shape in list(slide.shapes):
                if shape._element not in existing:
                    tree.remove(shape._element)
            return None

    errors = []
    if quote:
        from deck_quote import candidates, draw, draw_mark
        requested = direction.get('quote_layout', 'auto')
        alternatives = candidates(page['lines'], previous)
        if requested in alternatives:
            alternatives = [requested, *[style for style in alternatives if style != requested]]

        def draw_classic():
            classic_quote(slide, page, local)
            return 'classic'

        actual = transaction(draw_classic) if number == feature else None
        if actual is None:
            for style in alternatives:
                actual = transaction(lambda: draw(slide, page, local, [style], number, marked=True))
                if actual:
                    break
        if actual:
            return {'quote': actual, 'colors': set(local.t.values())-set(theme.t.values())}
        # Preserve the already-fitted source copy if a custom layout is tight.
        for index, element in former:
            tree.insert(index, element)
        if getattr(theme, 'previous_quote_layout', None) == 'classic' and number != feature:
            # The authored classic can be very dense. The alternate writer can
            # use the full baseline fit by dropping only the classic rail/mark.
            raise ValueError(f'Slide {number}: use a shorter quotation or a wider alternative')
        if getattr(theme, 'previous_quote_layout', None) != 'classic':
            draw_mark(slide, local, rk.SAFE[0] + 3, rk.SAFE[1] + 2, 40)
        return {'quote': getattr(theme, 'previous_quote_layout', None), 'fallback': errors}

    revised = dict(page, art_direction=dict(direction, _press_chart=chart, _cut_paper=cards,
                                           _inline_quote=inline_quote))

    def draw_evidence():
        writer(slide, revised, local, number, total, meta)
        return local.evidence_pages[-1]['plan']

    plan = transaction(draw_evidence)
    if plan is None and chart:
        revised['art_direction']['_press_bands'] = True
        plan = transaction(draw_evidence)
    if plan is None and chart:
        # Short labels can use a compact comparison column. If the full
        # ledger cannot fit that measure, retain the proven v4.5 geometry.
        revised['art_direction']['content_width'] = min(direction.get('content_width', 1), .62)
        plan = transaction(draw_evidence)
    if plan:
        return {'plan': plan, 'colors': set(local.t.values())-set(theme.t.values())}
    for index, element in former:
        tree.insert(index, element)
    if inline_quote:
        from deck_quote import draw_mark
        draw_mark(slide, local, rk.SAFE[2] - 38, rk.SAFE[1] + 2, 40)
    return {'fallback': errors}


def sparse_cutaway(slide, page, theme, seed):
    """Place a small native paper vignette in a measured case/body opening."""
    from deck_paper_collage import cutaway
    from glyphs import GLYPHS
    modules = [m for m in page.get('modules', []) if m.get('level') != 4]
    direction = page.get('art_direction', {})
    mode = direction.get('case_collage', 'auto')
    if (mode == 'off' or page.get('archetype') not in ('statement', 'features') or len(modules) != 1
            or modules[0].get('visual') not in ('text', 'key-statement', 'summary-box')
            or modules[0].get('visual_data', {}).get('items')
            or not 1 <= len(str(modules[0].get('body', '')).split()) <= (90 if mode == 'on' else 72)):
        return None
    body_shapes = [record for record in tm.audit(slide, mode='ink')
                   if '-body-' in record['shape'].name]
    if not body_shapes:
        return None
    occupied = [record['rect'] for record in tm.audit(slide, mode='ink')]
    from element_runtime import content_obstacles
    occupied.extend(record['rect'] for record in content_obstacles(slide))
    left, _, right, bottom = rk.SAFE
    last = max(r['rect'][3] for r in body_shapes)
    glyph = direction.get('case_collage_glyph')
    if glyph and glyph not in GLYPHS:
        raise ValueError(f'Unknown case collage glyph {glyph!r}')
    if not glyph and re.search(r'\b\d{1,2}:\d{2}\b', modules[0]['body']):
        glyph = 'clock'
    for width, height in ((302, 78), (222, 64), (180, 54)):
        for x in (right-width-98, left+30, right-width-58):
            for y in (last+19, last+39):
                region = (x, y, x+width, y+height)
                if y+height <= bottom-18 and not any(
                        layout.intersection(layout.inflate(region, 5), ob) for ob in occupied):
                    cutaway(slide, theme, region, seed, glyph)
                    return dict(purpose='case-cutaway', rect=region, glyph=glyph)
    return None
