"""Page-family revisions after the approved deck furniture has been planned.

The first pass reproduces v4.5 exactly, so the cover, dividers, classic quote
and every random draw stay stable. This pass redraws the content of the page
families that carry collage, press charts or measured quotations.
"""
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


# Pages that enumerate parallel information. Their points sit on torn paper.
LIST_FORMS = {'takeaway-list', 'concept-stack', 'keyword-band', 'contrast-pair', 'versus', 'before-after'}


def collage_mode(meta, page, pool, enabled):
    """Resolve the page's collage level from deck and page direction.

    Returns the level and whether the builder chose it. ``auto`` sets lists
    and charts on paper. Other pages stay open, and a few of them may take
    a paper scene beside their copy.
    """
    direction = page.get('art_direction', {})
    setting = direction.get('collage', meta.get('collage', 'auto'))
    if setting not in ('auto', 'lists', 'rich', 'quiet', 'scene', 'off'):
        raise ValueError('collage must be auto, lists, rich, quiet, scene or off')
    if not enabled or setting == 'off':
        return None, False
    if setting not in ('auto', 'lists'):
        return setting, False
    if (pool == [] or direction.get('paper_collage') == 'off' or direction.get('case_collage') == 'off'
            or page.get('archetype') in ('quote', 'closing')):
        return None, True
    mains = [m for m in page.get('modules', []) if m.get('level') != 4]
    forms = {m.get('visual') for m in mains}
    listing = any(m.get('visual') in LIST_FORMS and len(m.get('visual_data', {}).get('items', [])) >= 2
                  for m in mains)
    if listing or forms & PRESS_FORMS:
        return 'rich', True
    return 'scene', True


# A page title a little under the v4.5 size, with more room below its rule.
TITLE_SCALE, TITLE_GAP = .82, 12


def _title_lines(shapes):
    """Ink boxes of the front title lines, top to bottom."""
    lines = [tm.tight_rect(shape, mode='ink') for shape in shapes
             if shape.name.startswith('art[title]') and 'riso-layer[back]' not in shape.name]
    return sorted((list(line) for line in lines if line), key=lambda line: line[1])


def _follow_title(slide, old, fresh):
    """Keep an ornament that trails a title line at the end of the redrawn line.

    The ornament shrinks with the title. One that would now meet another
    mark, or leave the safe area, is lifted instead. Returns the shapes
    moved and the shapes lifted, so a failed attempt can put both back.
    """
    from pptx.util import Pt

    new = _title_lines([shape for shape in slide.shapes if shape._element in fresh])
    moved, lifted = [], []
    if not old or not new:
        return moved, lifted
    tree = slide.shapes._spTree
    marks = [shape for shape in slide.shapes if shape.name.startswith(('el[', 'deck-mark['))]
    for shape in marks:
        if not shape.name.startswith('el['):
            continue
        rect = layout.obb(shape)
        middle = (rect[1] + rect[3]) / 2
        for index, line in enumerate(old):
            if line[1] - 8 <= middle <= line[3] + 8 and line[2] - 14 <= rect[0] <= line[2] + 70:
                target = new[min(index, len(new) - 1)]
                moved.append((shape, shape.left, shape.top, shape.width, shape.height))
                width, height = shape.width.pt * TITLE_SCALE, shape.height.pt * TITLE_SCALE
                centre = (target[1] + target[3]) / 2 + (middle - (line[1] + line[3]) / 2) * TITLE_SCALE
                shape.left = Pt(target[2] + (rect[0] - line[2]) * TITLE_SCALE)
                shape.top = Pt(centre - height / 2)
                shape.width, shape.height = Pt(width), Pt(height)
                now = layout.obb(shape)
                if now[2] > rk.SAFE[2] or any(layout.intersection(layout.inflate(now, 6), layout.obb(other))
                                              for other in marks if other is not shape):
                    lifted.append((tree.index(shape._element), shape._element))
                    tree.remove(shape._element)
                break
    return moved, lifted


def _clear_decor(slide, fresh, pieces):
    """Lift first-pass ornaments that the redrawn page would collide with."""
    tree = slide.shapes._spTree
    copy = [record['rect'] for record in tm.audit(slide, mode='ink') if record['shape']._element in fresh]
    papers = [layout.inflate(piece['rect'], 4) for piece in pieces]
    removed = []
    for shape in list(slide.shapes):
        if not shape.name.startswith(('el[', 'deck-mark[')):
            continue
        rect = layout.obb(shape)
        if (any(layout.intersection(layout.inflate(rect, 10), other) for other in copy)
                or any(layout.intersection(rect, other) for other in papers)):
            removed.append((tree.index(shape._element), shape._element))
            tree.remove(shape._element)
    return removed


def revise(slide, page, theme, number, total, meta, original, feature, previous, writers, media,
           collage=None):
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
    evidence = bool(modules) and writer.__name__ == 'p_infographic'
    if not (evidence or quote):
        collage = None
    # ``collage: off`` keeps the whole v4.5 page, title included.
    legacy = 'off' in (meta.get('collage', 'auto'), direction.get('collage'))
    restyle = evidence and not legacy and 'title_size' not in direction
    style = dict(_title_scale=TITLE_SCALE, _title_gap=TITLE_GAP, _rescue=True) if restyle else {}
    if not any((quote, chart, cards, inline_quote, collage, restyle)):
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
    old_title = _title_lines(original) if restyle else []
    tree = slide.shapes._spTree
    former = [(tree.index(shape._element), shape._element) for shape in original]
    insert_at = former[0][0] if former else len(tree)
    for _, element in former:
        tree.remove(element)
    existing = {shape._element for shape in slide.shapes}

    def transaction(draw, papers=None):
        removed, moved = [], []
        try:
            result = draw()
            new = [shape._element for shape in slide.shapes if shape._element not in existing]
            for index, element in enumerate(new, insert_at):
                tree.insert(index, element)
            if old_title:
                shifted, lifted = _follow_title(slide, old_title, set(new))
                moved.extend(shifted)
                removed.extend(lifted)
            if papers is not None or old_title:
                removed.extend(_clear_decor(slide, set(new), papers(result) if papers is not None else []))
            new_failures = failures() - original_check
            if new_failures:
                raise ValueError('; '.join(sorted(new_failures)))
            return result
        except ValueError as exc:
            errors.append(str(exc))
            for shape in list(slide.shapes):
                if shape._element not in existing:
                    tree.remove(shape._element)
            for index, element in removed:
                tree.insert(index, element)
            for shape, left, top, width, height in moved:
                shape.left, shape.top, shape.width, shape.height = left, top, width, height
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

        # A mark planned around the first-pass layout gives way to the quotation.
        actual = transaction(draw_classic, lambda _: []) if number == feature else None
        if actual is None and collage and collage['mode'] in ('rich', 'quiet'):
            # On request, a supporting quotation is set on paper under a large mark.
            from deck_quote import draw_paper
            made = {}
            for style in alternatives:
                actual = transaction(lambda: draw_paper(slide, page, local, [style], number, collage, made),
                                     lambda _: made['collage']['pieces'])
                if actual:
                    return {'quote': actual, 'collage': made['collage'],
                            'colors': set(local.t.values())-set(theme.t.values())}
        if actual is None:
            for style in alternatives:
                actual = transaction(lambda: draw(slide, page, local, [style], number, marked=True),
                                     lambda _: [])
                if actual:
                    break
        if actual:
            return {'quote': actual, 'colors': set(local.t.values())-set(theme.t.values()),
                    'fallback': errors or None}
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

    revised = dict(page, art_direction=dict(direction, **style, _press_chart=chart, _cut_paper=cards,
                                           _inline_quote=inline_quote))

    def draw_evidence():
        writer(slide, revised, local, number, total, meta)
        return local.evidence_pages[-1]['plan']

    if collage and evidence:
        # Richest first: reading faces, then papers beside open copy.
        base = dict(direction, **style, _press_chart=chart, _inline_quote=inline_quote,
                    _collage_seed=collage['seed'], _collage_variant=collage['variant'])
        # A spread composition first; a compact one keeps the page's quiet zone.
        steps = [dict(base, _collage=collage['mode']), dict(base, _collage=collage['mode'], _compact=True)]
        if chart:
            steps.append(dict(base, _collage=collage['mode'], _press_bands=True))
        steps.append(dict(base, _collage='under'))
        if collage['mode'] == 'scene':
            # The copy stays on the open page and a paper scene takes the opening.
            steps = [dict(base, _collage='under')]
        def papers(made):
            pieces = made.get('collage', {}).get('pieces')
            if not pieces:
                raise ValueError('No paper fits beside this copy')
            return pieces

        for step in steps:
            revised['art_direction'] = step
            plan = transaction(draw_evidence, papers)
            if plan:
                return {'plan': plan, 'collage': plan['collage'],
                        'colors': set(local.t.values())-set(theme.t.values()),
                        'fallback': errors if step is not steps[0] else None}
        revised['art_direction'] = dict(direction, **style, _press_chart=chart, _cut_paper=cards,
                                        _inline_quote=inline_quote)

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
        # Record why a requested collage gave way to the open page. A scene
        # the builder offered on its own is simply left out.
        optional = (collage and collage.get('automatic') and collage['mode'] in ('scene', 'rich') and not chart
                    and not direction.get('image'))
        return {'plan': plan, 'colors': set(local.t.values())-set(theme.t.values()),
                'fallback': None if optional else errors or None}
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
