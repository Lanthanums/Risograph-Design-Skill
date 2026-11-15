"""Print-collage poster planner. Poster-only.

The infographic content model stays as it is: a title and typed modules with
source-bound copy. This planner sets them as a printed sheet. A masthead holds
a display title beside a torn-paper scene, a lead module sits on its own
sheet, the remaining modules read down a two-column grid, and the action and
logistics close the page. Sizes are measured, then the largest body size that
fits is kept. ``poster_collage`` adds the paper, ink and print furniture.
"""
import copy
import itertools
import math
from dataclasses import replace

import typefit as tf
import textmetrics as tm
import riso_kit as rk
from canvas import poster_canvas
from poster_primitives import bounds
from content_plan import words, text

FULL_WIDTH = ('step-flow', 'timeline', 'before-after', 'versus')
DISPLAY = {
    'serif': (('Georgia', True), ('DejaVu Serif', True), ('Liberation Serif', True)),
    'grotesque': (('Arial Black', False), ('Impact', False), ('Arial', True), ('DejaVu Sans', True),
                  ('Liberation Sans', True)),
}


class Overflow(ValueError):
    """The measured page does not fit at this size."""


def print_style(direction):
    """``collage`` unless the author asks for the flat sheet or a legacy dialect."""
    wanted = direction.get('print')
    legacy = direction.get('dialect', 'auto') in ('collage', 'doodle')
    if wanted == 'collage' and legacy:
        raise ValueError('art_direction.print "collage" supplies its own paper and ink; '
                         'use print "flat" with the collage and doodle dialects')
    return wanted or ('flat' if legacy else 'collage')


def display_face(kind, theme):
    for family, bold in DISPLAY[kind]:
        if tm.resolve(family, bold):
            return family, bold
    return theme.f_heading, True


def compact(fit, leading):
    """Display lines set tight, keeping clear of the measured glyph height."""
    face = tm.font(fit.font, fit.size, fit.bold)
    ink = max((face.getbbox(line)[3] - face.getbbox(line)[1] for line in fit.lines if line), default=fit.size)
    pitch = max(fit.size * leading, ink + 3)
    first = fit.height / len(fit.lines)
    return replace(fit, pitch=pitch, height=(len(fit.lines) - 1) * pitch + first)


def fit_title(value, face, width, ceiling, floor, max_lines, max_height, leading):
    """Largest display size whose measured lines stay inside the masthead."""
    family, bold = face
    size = math.floor(ceiling)
    while size >= floor:
        try:
            fit = compact(tf.fit(value, family, size, width, 1e5, minimum=size, bold=bold, ls=1.0), leading)
        except ValueError:
            size -= 2
            continue
        if len(fit.lines) <= max_lines and fit.height <= max_height:
            return fit
        size -= 2
    return None


def make_plan(spec, *, flat=False):
    from poster_direction import INKS, digest
    from source_profile import profile, choose_form
    from evidence_scale import scale

    c = spec['content']
    a = spec.get('art_direction', {})
    meta = spec.get('meta', {})
    canvas = poster_canvas(spec.get('canvas'))
    x, y, x1, y1 = canvas.safe
    W, H = canvas.width, canvas.height
    w = x1 - x
    name = a.get('ink', 'cobalt-vermilion')
    ink = copy.deepcopy(INKS[name])
    ink['name'] = name
    theme = rk.Theme(palette='A', lang=meta.get('lang', 'en'), fonts=meta.get('fonts'))
    face = display_face(a.get('display', 'serif'), theme)
    heading_face = face if a.get('display', 'serif') == 'serif' else (theme.f_heading, True)
    seed = meta.get('seed', 1)

    modules = sorted(copy.deepcopy(c.get('modules', [])), key=lambda m: m.get('order', 0))
    evidence = copy.deepcopy(spec.get('evidence', {}))
    if not evidence:
        from content_plan import inventory
        evidence = dict(profile=profile(inventory({'content': c})), legacy=True)
    evidence.setdefault('level', evidence['profile']['data_density'])
    policy = scale(evidence['level'], 'swiss')
    for module in modules:
        module.setdefault('visual', choose_form(module, evidence['profile']))
    indexed = list(enumerate(modules))
    is_title = lambda m: m.get('level') == 1 and (m.get('role') == 'title' or text(m) == c['title'])
    foot = [(i, m) for i, m in indexed if m.get('level') == 4]
    cta = [(i, m) for i, m in indexed if m.get('visual') == 'stamp' and m.get('level') != 4]
    lead = next(((i, m) for i, m in indexed if m.get('level') == 1 and not is_title(m)
                 and m.get('visual') != 'stamp'), None)
    rest = [(i, m) for i, m in indexed if not is_title(m) and (i, m) not in foot and (i, m) not in cta
            and (lead is None or i != lead[0])]

    # Text columns keep one grid. Paper faces overhang it into the gutter.
    overhang = 15.0
    gutter = max(44.0, W * .055)
    wanted = a.get('columns', 2 if len(rest) >= 2 and w >= 440 else 1)
    columns = max(1, min(int(wanted), 3, len(rest) or 1))
    column = (w - gutter * (columns - 1)) / columns
    # Sizes are set for an A3 sheet and grow with a larger one, so a poster
    # reads at the same distance on any canvas. Smaller sheets keep A3 sizes.
    sheet_k = max(1.0, W / 842)
    pt = lambda size: size if sheet_k == 1 else math.floor(size * sheet_k * 2) / 2
    # Body copy stays near a comfortable measure for its column.
    ceiling = min(pt(policy['body_max']), max(pt(18), math.floor(column / 16.5 * 2) / 2))
    if 'body_size' in a:
        ceiling = max(pt(18), float(a['body_size']))
    title_value = '\n'.join(a['title_lines']) if a.get('title_lines') else c['title']
    leading = a.get('title_leading', .98)
    scene_wanted = not flat and a.get('scene', 'auto') != 'off'
    # Two mastheads: the title on open paper, or reversed out of a torn ink band.
    masthead = a.get('masthead', 'auto')
    if masthead == 'auto':
        masthead = 'band' if int(a.get('collage_variant', seed)) % 3 == 2 else 'open'
    inked = not flat and masthead == 'band'
    print_mode = 'flat' if flat else 'collage'

    def build(body, title_scale):
        # Paper overhangs the copy, so rows need room; small sheets close up a little.
        row_gap = max(46.0, body * 2.3) * min(1.0, max(.8, W / 842))
        # The geometry check reads a gap of 8% of the sheet height between lines
        # of copy as a hole. Every spacing below is held under this.
        hole = H * .075
        p = dict(version='3.8', mode='infographic', print=print_mode, source_sha256=digest(c), content_roles=[],
                 archetype='information-bands' if flat else 'print-collage',
                 selection_reason='Measured module grid' if flat else 'Masthead, lead sheet and a measured module grid',
                 dialect='swiss', looseness=0, skeleton='masthead-grid', seed=seed, canvas=canvas.to_dict(),
                 fonts=theme.fonts, font_diagnostics=theme.font_diagnostics, ink_plan=ink, objects=[],
                 overlaps=[], regions=[], micro_layer=[], content_words=0, density='medium', columns=columns,
                 scale_ladder=dict(body=body, detail=pt(16)), hero=dict(kind='statistic', object_ids=[], share=0),
                 constraints=dict(body_min=pt(18), decor_cap=.12, accent_cap=.18, max_nonstructural_repeat=3,
                                  max_edge_void=.14),
                 contract_warnings=[], revision=a.get('revision', 0), review_changes=a.get('review_changes', []),
                 tiers={}, preflight=dict(fields=len(modules), words=0), intentional_voids=[], parallel_sets=[],
                 reading_order=[], review_notes=[],
                 graphic_design=dict(recipe='info-type' if flat else 'print-collage', status='composed',
                                     meaning='Source-driven editable evidence' if flat else
                                     'Torn paper, spot ink and print furniture around source-bound evidence'),
                 autofit=dict(enabled=True, attempts=[], changes=[], source_changed=False), effective_controls={},
                 content_plan=spec.get('content_plan', {}), module_metrics=[], evidence=evidence,
                 evidence_policy=policy, layout={})
        objs = p['objects']

        def put(oid, value, xx, yy, width, size, source=None, role='argument', bold=False, color=None,
                font=None, ls=1.1):
            value = str(value)
            if not value.strip():
                return None
            # Lining figures for badge numerals; the text face carries the rest.
            family, heavy = (font or ((theme.f_heading, True) if role == 'navigation' else
                                      heading_face if bold else (theme.f_body, False)))
            f = tf.fit(value, family, size, width, H * 3, minimum=size, bold=heavy, ls=ls)
            ob = dict(id=oid, kind='text', text=value, source=source, role=role,
                      rect=[xx, yy, xx + width, yy + f.height], fit=f.to_dict(), color=color or ink['body'],
                      background=ink['paper'], rotation=0)
            objs.append(ob)
            if source:
                p['content_roles'].append(dict(id=source, source=source, text=value, role=role))
            return ob

        def rect(oid, r, color, role='data', **extra):
            ob = dict(id=oid, kind='rect', rect=r, fill=color, role=role, rotation=0, **extra)
            objs.append(ob)
            return ob

        def path(oid, paths, color=ink['main'][1], role='relation', **extra):
            ob = dict(id=oid, kind='path', paths=paths, rect=bounds(paths, 1), line=color, line_width=1.8,
                      role=role, rotation=0, **extra)
            objs.append(ob)
            return ob

        def node(mid, members, r, band=1, col=0):
            members = [o for o in members if o and o['kind'] == 'text']
            if not members:
                return
            p['regions'].append(dict(id=mid, rect=r, objects=[o['id'] for o in members], column=col))
            p['reading_order'].append(dict(order=len(p['reading_order']) + 1, region=mid,
                                           objects=[o['id'] for o in members], band=band, column=col,
                                           x=members[0]['rect'][0]))

        def figure(m, d, mid, base, tx, yy, tw, leading_figure):
            """A statistic: the numeral as large as its column allows, its unit set
            beside it, the label next to a wide numeral or under a narrow one, and a
            ring for a percentage."""
            value, label, unit = str(d.get('value', '')), str(d.get('label', '')), str(d.get('unit', ''))
            if not value or not label:
                raise ValueError(mid + ': statistic requires value + label')
            percent = unit in ('%', '％') or value.endswith('%')
            family, heavy = heading_face
            wanted = body * 4.6 * (1.3 if leading_figure else 1)
            share = .5 if tw > 500 else .72 if percent else 1.0
            advance = tm.advance(value, family, 100, heavy) / 100
            limit = (tw * share - rk.NO_WRAP['pad_pt'] - 4) / rk.NO_WRAP['slack'] / advance
            if limit < body * 4:
                limit = (tw - rk.NO_WRAP['pad_pt'] - 4) / rk.NO_WRAP['slack'] / advance
            size = max(body * 4, min(wanted, math.floor(limit)))
            width = advance * size * rk.NO_WRAP['slack'] + rk.NO_WRAP['pad_pt'] + 2
            number = put(mid + '-visual_data.value', value, tx, yy, width, size, base + '.visual_data.value',
                         'hero_stat', True, ink['main'][0], ls=1.0)
            number['stat_tile'] = True
            atom = d.get('atom')
            if not atom:
                # Bind the figure to the module atom that states this quantity.
                from source_profile import quantity
                q = quantity(value + unit)
                rows = [r for r in evidence['profile']['atoms'] if r['atom'] in m.get('atoms', [])]
                atom = next((r['atom'] for r in rows for z in r['quantities']
                             if q and z['value'] == q[0] and z['unit'] == q[1]), None)
            number['data_label'] = dict(atom=atom, value=value, unit=unit)
            p['hero']['object_ids'].append(number['id'])
            right = number['rect'][0] + number['fit']['width']
            bottom = number['rect'][3]
            if unit and not value.endswith(unit):
                unit_size = max(body * 1.3, math.floor(size * (.62 if percent else .4)))
                rise = tm.font(family, size, heavy).getmetrics()[0] - tm.font(family, unit_size, heavy).getmetrics()[0]
                unit_width = tm.advance(unit, family, unit_size, heavy) * rk.NO_WRAP['slack'] + rk.NO_WRAP['pad_pt'] + 2
                mark = put(mid + '-visual_data.unit', unit, right + size * .06, yy + rise, unit_width, unit_size,
                           base + '.visual_data.unit', 'hero_stat', True, ink['main'][0], ls=1.0)
                right = mark['rect'][0] + mark['fit']['width']
            ring = None
            if percent:
                try:
                    fraction = float(value.replace(',', '').rstrip('%')) / 100
                except ValueError:
                    fraction = None
                radius = min(number['rect'][3] - number['rect'][1], tw * .2) * .42
                if fraction is not None and 0 <= fraction <= 1 and tx + tw - right >= radius * 2 + 22:
                    cx, cy = tx + tw - radius - 2, yy + (number['rect'][3] - number['rect'][1]) * .5
                    for j, (lo, hi) in enumerate(((0, fraction), (fraction, 1))):
                        if hi - lo < 1e-6:
                            continue
                        arc = [-math.pi / 2 + (lo + (hi - lo) * k / 48) * math.tau for k in range(49)]
                        paths = [[[cx + radius * math.cos(t), cy + radius * math.sin(t)] for t in arc]
                                 + [[cx + radius * .58 * math.cos(t), cy + radius * .58 * math.sin(t)]
                                    for t in reversed(arc)]]
                        objs.append(dict(id=f'{mid}-proportion-{j}', kind='path', rect=bounds(paths), paths=paths,
                                         closed=True, fill=ink['main'][j], role='data', rotation=0,
                                         anchor=number['id']))
                    ring = cx - radius
            beside = (ring or tx + tw) - right - body * 1.2
            if beside >= 190 and tw > 500:
                lab = put(mid + '-visual_data.label', label, right + body * 1.2, yy, min(beside, 380),
                          math.floor(body * 1.25), base + '.visual_data.label', 'argument')
                drop = max(0, (number['rect'][3] - number['rect'][1] - (lab['rect'][3] - lab['rect'][1])) * .56)
                lab['rect'][1] += drop
                lab['rect'][3] += drop
            else:
                lab = put(mid + '-visual_data.label', label, tx, bottom + 2, tw, body,
                          base + '.visual_data.label', 'argument')
            return max(bottom, lab['rect'][3]) + body * .5

        context = dict(plan=p, put=put, rect=rect, path=path, node=node, theme=theme, pad=0, top=0, figure=figure,
                       heading_size=max(pt(24), math.floor(body * 1.34)), heading_gap=body * .5,
                       bar_thickness=max(pt(16), body * .8), chart_height=min(118.0 * sheet_k, H * .1), compact_bars=True,
                       detail_size=pt(16), pair_size=pt(25), mark_scale=sheet_k,
                       item_gap=body * .22, quote_mark=True, heading_face=heading_face
                       )

        def render(index, m, r, band, col, **extra):
            from evidence_forms import render_module
            return render_module(index, m, r, dict(context, **extra), band, col)

        def probe(index, m, width, **extra):
            """Measured height of a module at a width; the trial objects are discarded."""
            saved = {k: copy.deepcopy(p[k]) for k in ('objects', 'content_roles', 'regions', 'reading_order',
                                                      'module_metrics', 'hero', 'overlaps')}
            try:
                start = len(p['objects'])
                render(index, m, [0, 0, width, H * 4], 1, 0, **extra)
                used = [o['rect'][3] for o in p['objects'][start:] if not o.get('micro')]
                return max(used, default=0)
            finally:
                p.update(saved)
                nonlocal objs
                objs = p['objects']

        # --- masthead ---------------------------------------------------------
        title_ceiling = min(a.get('title_size', W * .165), W * .2) * title_scale
        title_floor = max(40.0, W * .062)
        # Beside a scene the title keeps to its own column. A generous masthead
        # accepts the extra lines that costs. A tight one keeps the scene only
        # when the title is no taller for it, and otherwise runs the full width.
        beside = fit_title(title_value, face, w * .64, title_ceiling, max(title_floor, W * .085), 4,
                           H * .27 * title_scale, leading) if scene_wanted and w >= 420 else None
        across = fit_title(title_value, face, w, title_ceiling, title_floor, 4, H * .3 * title_scale, leading)
        if beside and across and title_scale < .76 and beside.height > across.height + 2:
            # The same number of lines beside the scene, a little smaller, if that is close enough.
            narrow = fit_title(title_value, face, w * .64, title_ceiling, max(title_floor, W * .085),
                               len(across.lines), H * .27 * title_scale, leading)
            beside = narrow if narrow and narrow.size >= across.size * .8 else None
        split = beside is not None
        title = beside if split else across
        if title is None:
            raise ValueError('Title cannot be set inside the masthead; shorten it or supply art_direction.title_lines')
        top = y + (H * .012 if split or inked else 0)
        title_ob = dict(id='title', kind='text', text=c['title'], source='title', role='hook',
                        rect=[x, top, x + (w * .64 if split else w), top + title.height], fit=title.to_dict(),
                        color=ink['paper'] if inked else ink['main'][0],
                        background=ink['main'][0] if inked else ink['paper'], rotation=0)
        if not flat:
            shift = max(1.6, title.size * .028)
            under = copy.deepcopy(title_ob)
            under.update(id='title-ink', source=None, duplicate_of='title', color=ink['body'] if inked else ink['main'][1],
                         role='overprint', rect=[v + shift for v in title_ob['rect']])
            objs.append(under)
        objs.append(title_ob)
        p['content_roles'].append(dict(id='title', source='title', text=c['title'], role='hook'))
        node('title', [title_ob], title_ob['rect'], 0)
        rule_y = title_ob['rect'][3] + max(12.0, title.size * .16)
        bar = rect('title-bar', [x, rule_y, x + min(w * .16, title.size * 1.3), rule_y + max(5.0, title.size * .06)],
                   ink['accent'], 'emphasis', anchor='title', micro=True, vocabulary='column-head')
        path('title-rule', [[[bar['rect'][2] + 8, rule_y + (bar['rect'][3] - rule_y) / 2],
                             [x + (w * .64 if split else w), rule_y + (bar['rect'][3] - rule_y) / 2]]],
             ink['paper'] if inked else ink['body'], 'structure', anchor='title', micro=True,
             vocabulary='column-head')['line_width'] = .9
        masthead_bottom = bar['rect'][3] + (title.size * .14 if inked else 0)
        band_rect = [-34.0, -34.0, W + 34.0, masthead_bottom] if inked else None
        # The first row starts close under the title. A taller gap reads as a
        # hole across the sheet, and the scene is cut to end above that row.
        cy = min(masthead_bottom + row_gap * (.8 if inked else 1.05), title_ob['rect'][3] + H * .07)
        cy = min(max(cy, masthead_bottom + 28), title_ob['rect'][3] + hole)
        scene = None
        if split:
            scene_bottom = max(masthead_bottom, min(y + min(H * .24, w * .42) * title_scale, cy - body * .3))
            scene = [x + w * .68, y - canvas.bleed * .3, x1 + canvas.bleed * .35, scene_bottom]

        # --- closing matter is measured first, the body gets what remains --------
        foot_size = pt(16)
        foot_fits = [(i, m, tf.fit(text(m), theme.f_body, foot_size, w - 8, H, minimum=foot_size, ls=1.12))
                     for i, m in foot]
        foot_h = sum(f.height + 6 for _, _, f in foot_fits) + (20 if foot_fits else 0)
        cta_size = max(pt(24), math.floor(body * 1.45))
        cta_fits = [(i, m, tf.fit(str(m.get('body') or text(m)), heading_face[0], cta_size, w - 2 * overhang - 70,
                                  H, minimum=cta_size, bold=heading_face[1], ls=1.06)) for i, m in cta]
        after = min(row_gap * .8, max(10.0, hole - 36))
        cta_h = sum(f.height + 2 * 15 for _, _, f in cta_fits) + after * len(cta_fits)
        tail = row_gap * .6 if foot_fits and not cta_fits else 0
        bottom = y1 - foot_h - cta_h - tail
        available = bottom - cy

        # --- rows -------------------------------------------------------------
        rows = []
        if lead:
            rows.append(dict(kind='lead', items=[lead]))

        def is_wide(m):
            items = m.get('visual_data', {}).get('items', [])
            return (m.get('visual') in FULL_WIDTH or m.get('weight', 1) >= 1.8
                    or m.get('visual') == 'contrast-pair' and len(items) == 2
                    or m.get('visual') in ('bar-vertical', 'line-chart') and len(items) >= 5)

        # A column module left alone between full-width rows would waste half the
        # sheet. The next column module moves up beside it, past one wide row.
        flow = list(rest)
        if columns > 1 and not a.get('keep_order'):
            k = 0
            while k < len(flow):
                run = k
                while run < len(flow) and not is_wide(flow[run][1]):
                    run += 1
                if (run - k) % columns == 1 and run + 1 < len(flow) and not is_wide(flow[run + 1][1]) \
                        and not flow[run + 1][1].get('group') and not flow[run][1].get('group'):
                    flow.insert(run, flow.pop(run + 1))
                    p['autofit']['changes'].append(f'{flow[run][1]["id"]} set beside {flow[run - 1][1]["id"]}, '
                                                   f'ahead of {flow[run + 1][1]["id"]}')
                    run += 1
                k = run + 1
        pending = []
        for i, m in flow:
            wide = is_wide(m)
            if wide or columns == 1:
                if pending:
                    rows.append(dict(kind='grid', items=pending))
                    pending = []
                rows.append(dict(kind='wide', items=[(i, m)]))
            else:
                pending.append((i, m))
        if pending:
            rows.append(dict(kind='grid', items=pending))
        for row in rows:
            if row['kind'] != 'grid' or len(row['items']) == 1:
                index, m = row['items'][0]
                extra = dict(lead=True) if row['kind'] == 'lead' else {}
                row.update(kind='wide' if row['kind'] == 'grid' else row['kind'], width=w, stacks=[[0]],
                           heights=[probe(index, m, w, **extra)])
                row['height'] = row['heights'][0]
                continue
            n = min(columns, len(row['items']))
            width = (w - gutter * (n - 1)) / n
            heights = [probe(index, m, width) for index, m in row['items']]
            best = None
            for cuts in itertools.combinations(range(1, len(heights)), n - 1):
                if any(row['items'][cut - 1][1].get('group') and
                       row['items'][cut - 1][1].get('group') == row['items'][cut][1].get('group') for cut in cuts):
                    continue
                breaks = (0, *cuts, len(heights))
                stacks = [list(range(breaks[j], breaks[j + 1])) for j in range(n)]
                totals = [sum(heights[k] for k in stack) + row_gap * (len(stack) - 1) for stack in stacks]
                score = (max(totals), max(totals) - min(totals))
                if best is None or score < best[0]:
                    best = (score, stacks, totals)
            if best is None:
                raise Overflow('A semantic group cannot stay together in this column count')
            row.update(width=width, stacks=best[1], heights=heights, height=best[0][0], totals=best[2])
        needed = sum(r['height'] for r in rows) + row_gap * max(0, len(rows) - 1)
        if needed > available:
            tall = sorted(((r['height'], '+'.join(m['id'] for _, m in r['items'])) for r in rows), reverse=True)
            raise Overflow(f'needs {needed:.0f}pt of {available:.0f}pt at {body:g}pt body; tallest rows '
                           + ', '.join(f'{name} {height:.0f}pt' for height, name in tall[:3]))
        # Surplus opens the rows a little, then deepens the kraft stub, then
        # leaves a little room above the closing matter. What is still left
        # would show as a hole, so it is reported and the caller sets larger type.
        spare = available - needed
        extra_gap = max(0.0, min(row_gap * .7, hole - row_gap, spare / max(1, len(rows)))) if rows else 0
        gap = row_gap + extra_gap
        left = spare - extra_gap * max(0, len(rows) - 1)
        if cta_fits:
            stub_cap = max(0.0, (hole - 32 - after + .1 * row_gap) / .55) if foot_fits else 0
            slack_cap = max(0.0, hole - 19 - .1 * row_gap)
        elif foot_fits:
            stub_cap = max(0.0, (hole - 18 - tail) * .5 / .55)
            slack_cap = max(0.0, (hole - 18 - tail) * .5)
        else:
            stub_cap, slack_cap = 0, H * .09
        stub_grow = min(left, stub_cap, H * .05)
        left -= stub_grow
        unused = left - min(left, slack_cap)
        cells = []
        for number, row in enumerate(rows):
            # Band 2 is reserved by the reading check for fixed columns.
            band = 1 if row['kind'] == 'lead' else 3 + number
            extra = dict(lead=True) if row['kind'] == 'lead' else {}
            n = len(row['stacks'])
            for col, stack in enumerate(row['stacks']):
                yy = cy
                for k in stack:
                    index, m = row['items'][k]
                    cx = x + col * (row['width'] + gutter)
                    start = len(objs)
                    render(index, m, [cx, yy, cx + row['width'], yy + row['heights'][k] + 2], band, col, **extra)
                    cells.append(dict(id=m['id'], index=index, visual=m.get('visual'), level=m.get('level'),
                                      kind=row['kind'], column=col, columns=n, row=number,
                                      paper=m.get('paper'),
                                      emphasis=m.get('visual_data', {}).get('emphasis'),
                                      rect=[cx, yy, cx + row['width'], yy + row['heights'][k]],
                                      members=[o['id'] for o in objs[start:]]))
                    yy += row['heights'][k] + gap
            cy += row['height'] + gap
        body_bottom = cy - gap if rows else cy

        # --- action and logistics ---------------------------------------------
        cy = max(body_bottom + row_gap * .9, y1 - foot_h - stub_grow - cta_h + row_gap * .1)
        band = len(rows) + 4
        for index, m, f in cta_fits:
            value = str(m.get('body') or text(m))
            source = f'modules.{index}.body' if m.get('body') else f'modules.{index}.headline'
            ob = dict(id=m['id'] + '-action', kind='text', text=value, source=source, role='cta',
                      rect=[x + overhang, cy + 15, x + overhang + f.width + rk.NO_WRAP['pad_pt'] + 4,
                            cy + 15 + f.height],
                      fit=f.to_dict(), color=ink['main'][0] if flat else ink['paper'],
                      background=ink['paper'] if flat else ink['main'][0], rotation=0)
            objs.append(ob)
            p['content_roles'].append(dict(id=source, source=source, text=value, role='cta'))
            node(m['id'], [ob], [x, cy, x1, cy + f.height + 30], band)
            p['module_metrics'].append(dict(id=m['id'], level=m.get('level'), visual='stamp',
                                            rect=[x, cy, x1, cy + f.height + 30], text_only=False,
                                            weight=m.get('weight', 1), group=m.get('group')))
            cells.append(dict(id=m['id'], index=index, visual='stamp', level=m.get('level'), kind='action',
                              column=0, columns=1, rect=[x, cy, x1, cy + f.height + 30], members=[ob['id']]))
            cy += f.height + 30 + after
            band += 1
        strip_top = y1 - foot_h + 2 - stub_grow
        foot_y = y1 - foot_h + 14 - stub_grow * .45 if foot_fits else y1
        for index, m, f in foot_fits:
            label = text(m)
            ob = dict(id=m['id'], kind='text', text=label, source=f'modules.{index}.footer', role='meta',
                      rect=[x + 4, foot_y, x1 - 4, foot_y + f.height], fit=f.to_dict(), color=ink['body'],
                      background=ink['paper'], rotation=0)
            objs.append(ob)
            p['content_roles'].append(dict(id=ob['source'], source=ob['source'], text=label, role='meta'))
            node(m['id'], [ob], [x, foot_y, x1, foot_y + f.height], band)
            cells.append(dict(id=m['id'], index=index, visual='ticket', level=4, kind='foot', column=0, columns=1,
                              rect=[x, foot_y, x1, foot_y + f.height], members=[ob['id']]))
            foot_y += f.height + 6
            band += 1
        p['layout'] = dict(masthead=[x, y, x1, masthead_bottom], scene=scene, title_split=split, cells=cells,
                           band=band_rect,
                           body=[x, masthead_bottom, x1, body_bottom], foot_strip=[strip_top, y1] if foot_fits else None,
                           overhang=overhang, gutter=gutter, row_gap=gap, spare=round(spare, 1),
                           unused=round(unused, 1), title_scale=title_scale)
        p['content_extent'] = dict(top=title_ob['rect'][3], bottom=body_bottom, footer_edge=foot_y)
        p['capacity'] = dict(columns=[dict(column=1, height=needed, measured=needed, available=available,
                                           words=0)])
        # A hole the spacing rules did not prevent counts as unused sheet.
        from poster_flow import voids
        if any(not gap['intentional'] for gap in voids(p)):
            p['layout']['unused'] = max(p['layout']['unused'], H * .03)
        return p

    # A comfortable body under the largest title that leaves room for it. The
    # body then grows into what is left. Only a full sheet takes the body down.
    attempts = []

    def attempt(size, title_scale):
        try:
            return build(size, title_scale)
        except ValueError as exc:
            # A word too wide for its cell at this size is an overflow too:
            # the next, smaller setting may fit it.
            if not isinstance(exc, Overflow) and 'cannot fit region' not in str(exc):
                raise
            attempts.append(dict(body=size, title_scale=title_scale, error=str(exc)))
            return None

    # The title and its scene carry the sheet at a distance, so the body gives
    # a point before the masthead gives much. First setting that fits wins.
    plan = None
    ladder = ((1.0, 20.0), (.88, 20.0), (1.0, 19.0), (.88, 19.0), (.76, 19.0), (.64, 19.0), (.76, 18.0),
              (.64, 18.0), (.52, 18.0))
    for title_scale, floor in ladder:
        floor = min(pt(floor), ceiling)
        plan = attempt(floor, title_scale)
        if plan:
            size = floor + .5
            while size <= (ceiling if title_scale == 1.0 else min(ceiling, pt(20))):
                larger = attempt(size, title_scale)
                if not larger:
                    break
                plan, size = larger, size + .5
            break
    if plan and plan['layout']['unused'] > 1 and 'body_size' not in a:
        # A sparse sheet: the body grows past its comfortable measure before
        # any of the sheet is left empty.
        size = plan['scale_ladder']['body'] + .5
        while size <= pt(policy['body_max']) and plan['layout']['unused'] > 1:
            larger = attempt(size, plan['layout']['title_scale'])
            if not larger:
                break
            plan, size = larger, size + .5
    if plan and plan['layout']['unused'] > H * .02:
        raise ValueError(f"The copy fills too little of this sheet: {plan['layout']['unused']:.0f}pt stay empty at "
                         f"{plan['scale_ladder']['body']:g}pt body. Choose a smaller canvas (a4_portrait, 4:5 or "
                         'square) or add a module; nothing was stretched to hide the gap.')
    if plan is None:
        raise ValueError(f'Poster copy does not fit this sheet at {pt(18):g}pt body: ' + attempts[-1]['error']
                         + '. Cut or merge the modules in those rows; a larger canvas sets larger type and gains '
                           'no room. No copy was removed.')
    p = plan
    if not flat and a.get('ornament') == 'classic':
        p['contract_warnings'].append('ornament and element_density belong to print "flat"; the print collage '
                                      'sets its own paper and furniture')
    if attempts:
        p['autofit']['changes'].append(f'Body {p["scale_ladder"]["body"]:g}pt and title '
                                       f'{next(o["fit"]["size"] for o in p["objects"] if o["id"] == "title"):g}pt chosen after {len(attempts)} '
                                       'larger settings overflowed; source unchanged')
    p['autofit']['attempts'] = attempts[-6:]
    objs = p['objects']
    p['content_words'] = sum(words(text(m)) for m in modules if not is_title(m)) + words(c['title'])
    p['preflight'].update(words=p['content_words'])
    p['capacity']['columns'][0]['words'] = p['content_words']
    p['reading_graph'] = dict(node_ids=[n['region'] for n in p['reading_order']],
                              edges=[[u['region'], v['region']] for u, v in zip(p['reading_order'],
                                                                              p['reading_order'][1:])])
    known = {o['id'] for o in objs}
    for o in objs:
        if o.get('anchor') and o['anchor'] not in known:
            o['anchor'] = 'title'
    p['effective_controls'] = {k: dict(requested=a.get(k, 'auto'), effective=v) for k, v in [
        ('body_size', p['scale_ladder']['body']), ('skeleton', 'masthead-grid'), ('columns', columns),
        ('dialect', 'swiss'), ('print', print_mode)]}

    if not flat:
        import poster_collage
        poster_collage.dress(p, a)

    p['hero']['share'] = sum((o['rect'][3] - o['rect'][1]) * (o['rect'][2] - o['rect'][0]) for o in objs
                             if o['id'] in p['hero']['object_ids']) / canvas.area
    p['scale_ladder']['actual'] = sorted({o['fit']['size'] for o in objs if o['kind'] == 'text'}, reverse=True)
    from poster_flow import voids
    p['voids'] = voids(p)
    p['coordination'] = dict(fails=[])
    p['composition_signature'] = digest([dict(id=o['id'], rect=o['rect']) for o in objs])
    if flat and a.get('ornament') != 'focused':
        from auto_garnish import apply
        apply(p, a.get('element_density', policy['element_density']))
    elif flat:
        p['element_quota'] = dict(density='focused', suggested_count=[1, 1], minimum_families=1)
        p['micro_layer'] = [dict(kind='underline', role='title emphasis')]
    else:
        p['element_quota'] = dict(density='collage', suggested_count=[0, 99], minimum_families=0)
        p['micro_layer'] = [dict(kind=k, role=r) for k, r in (('paper', 'torn reading faces'), ('ink', 'spot fields'),
                                                              ('registration', 'title overprint'),
                                                              ('furniture', 'crop marks and colour bar'))]
    from infographic import assess
    from evidence_style import signature
    p['infographic_metrics'] = assess(p)
    p['infographic_metrics']['dialect_signature'] = signature(p)
    p['coordination']['fails'] = p['infographic_metrics']['fails']
    return p
