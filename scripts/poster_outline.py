"""Expand a compact poster outline into a full content plan. Poster-only.

The outline states the poster once: a title, a lead, a few typed modules, an
action and a footer. This module derives the source inventory, the atom
bindings, the coverage ledger and the evidence levels from it, so the author
writes the copy a single time. The full plan format stays available for work
that needs a ledger against an external source document.
"""
import argparse
from decimal import Decimal
import json
import re
import sys
from pathlib import Path

CHARTS = {'bars': 'bar-compare', 'columns': 'bar-vertical', 'line': 'line-chart', 'ring': 'ring',
          'stacked': 'stacked-bar'}
BLOCKS = ('statement', 'text', 'list', 'stat', 'chart', 'versus', 'steps', 'timeline', 'quote')
TEXT_FORMS = ('key-statement', 'summary-box', 'takeaway-list', 'pull-quote')
MODULE_KEYS = {'id', 'title', 'emphasis', 'by', 'paper', *BLOCKS}
OUTLINE_KEYS = {'title', 'audience', 'purpose', 'meta', 'canvas', 'look', 'lead', 'modules', 'action', 'footer'}


def _words(value):
    return len(re.findall(r"[\w'’-]+", str(value)))


def _pairs(rows, name, detail=False):
    out = []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, str) and not detail:
            out.append(dict(label=row))
        elif isinstance(row, (list, tuple)) and len(row) == 2 and all(isinstance(v, str) and v.strip() for v in row):
            out.append(dict(label=row[0], text=row[1]))
        else:
            raise ValueError(f'{name}: each entry is ' + ('a [label, text] pair' if detail else
                                                          'a string or a [label, text] pair'))
    if not out:
        raise ValueError(f'{name}: needs at least one entry')
    return out


def advice(outline):
    """Short notes on copy that will build but will not look its best."""
    notes = []
    title = outline.get('title', '')
    if _words(title) > 5:
        notes.append(f'the title is {_words(title)} words. Two to five keep it large; move the rest to the lead.')
    if not outline.get('lead'):
        notes.append('no lead. Give the one figure or sentence a passer-by should take away.')
    rows = [m for m in outline.get('modules', []) if isinstance(m, dict)]
    if len(rows) > 6:
        notes.append(f'{len(rows)} modules. Three to five read best on one sheet.')
    if sum('chart' in m for m in rows) > 1:
        notes.append('more than one chart. Keep the strongest and state the other figure as a stat.')
    for m in rows:
        if isinstance(m.get('quote'), str) and _words(m['quote']) > 30:
            notes.append(f"{m.get('id')}: the quotation is {_words(m['quote'])} words. Quote the strongest sentence.")
        steps = m.get('steps') if isinstance(m.get('steps'), list) else []
        if any(_words(s if isinstance(s, str) else s[0]) > 6 for s in steps if s):
            notes.append(f"{m.get('id')}: a step label runs past six words. Keep the label short.")
    return notes


def _module(mid, row, root, lead=False):
    """One outline entry as (stored source, plan module, declared relation)."""
    kinds = [key for key in BLOCKS if key in row]
    if len(kinds) != 1:
        raise ValueError(f"{mid}: needs exactly one of {', '.join(BLOCKS)}")
    block, value = kinds[0], row[kinds[0]]
    title = row.get('title', '')
    store = {'title': title} if title else {}
    module = dict(id=mid, level=1 if lead else 2, headline=title, body='', weight=1, group=None)
    relation = None
    if row.get('paper') in ('sheet', 'open'):
        module['paper'] = row['paper']
    elif 'paper' in row:
        raise ValueError(f'{mid}: paper is "sheet" or "open"')
    if block in ('statement', 'text'):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{mid}: {block} must be text')
        store['text'] = value
        module.update(visual='key-statement' if block == 'statement' else 'summary-box', info_type='claim', body=value)
        if row.get('emphasis'):
            if row['emphasis'] not in value:
                raise ValueError(f'{mid}: emphasis must be words from the {block}')
            module['visual_data'] = dict(emphasis=row['emphasis'])
    elif block == 'list':
        items = _pairs(value, f'{mid}.list')
        store['items'] = [dict(item) for item in items]
        module.update(visual='takeaway-list', info_type='claim', visual_data=dict(items=items))
    elif block in ('versus', 'steps', 'timeline'):
        items = _pairs(value, f'{mid}.{block}', detail=block != 'steps')
        if block == 'versus' and len(items) != 2:
            raise ValueError(f'{mid}: versus needs exactly two sides')
        store[block] = [dict(item) for item in items]
        relation = 'contrast' if block == 'versus' else 'sequence'
        module.update(visual=dict(versus='contrast-pair', steps='step-flow', timeline='timeline')[block],
                      info_type=dict(versus='comparison', steps='process_step', timeline='timeline')[block],
                      visual_data=dict(items=items))
    elif block == 'stat':
        if not isinstance(value, dict) or not all(str(value.get(k, '')).strip() for k in ('value', 'unit', 'label')):
            raise ValueError(f'{mid}: stat needs value, unit and label')
        figure = {k: str(value[k]) for k in ('value', 'unit', 'label')}
        store.update(figure)
        if value.get('body'):
            store['body'] = module['body'] = str(value['body'])
        module.update(visual='stat-tile', info_type='statistic', visual_data=dict(figure, atom=f'{root}.value'))
    elif block == 'chart':
        form = CHARTS.get(value.get('type') if isinstance(value, dict) else None)
        points = value.get('points') if isinstance(value, dict) else None
        if (not form or not value.get('unit') or not isinstance(points, list) or len(points) < 2
                or not all(isinstance(p, (list, tuple)) and len(p) == 2 and isinstance(p[1], (int, float))
                           and not isinstance(p[1], bool) for p in points)):
            raise ValueError(f"{mid}: chart needs type ({', '.join(CHARTS)}), unit and two or more [label, number] points")
        unit = str(value['unit'])
        values = [Decimal(str(amount)) for _, amount in points]
        if not all(amount.is_finite() for amount in values):
            raise ValueError(f'{mid}: chart point values must be finite numbers')
        # Save the same plain decimal in the source ledger and native labels.
        points = [(str(label), format(amount, 'f')) for (label, _), amount in zip(points, values)]
        store['points'] = [dict(label=label, value=amount, unit=unit) for label, amount in points]
        if form == 'line-chart':
            relation = 'sequence'
        module.update(visual=form, info_type='part_whole' if form in ('ring', 'stacked-bar') else
                      'timeline' if form == 'line-chart' else 'comparison',
                      visual_data=dict(unit=unit, items=[dict(label=str(label), value=amount,
                                                              atom=f'{root}.points.{n}.value')
                                                         for n, (label, amount) in enumerate(points)]))
    else:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{mid}: quote must be the exact words')
        store['words'] = value
        module.update(visual='pull-quote', info_type='quote', body=value)
        if row.get('by'):
            store['by'] = row['by']
            module['visual_data'] = dict(attribution=row['by'])
    module['role'] = module['info_type']
    return store, module, relation


def expand(outline):
    """Return a lintable content plan for the outline."""
    import content_plan as cp
    from evidence_scale import scale

    if not isinstance(outline, dict) or not str(outline.get('title', '')).strip():
        raise ValueError('outline needs a title')
    unknown = set(outline) - OUTLINE_KEYS
    if unknown:
        raise ValueError(f"unknown outline keys {', '.join(sorted(unknown))}; allowed {', '.join(sorted(OUTLINE_KEYS))}")
    rows = outline.get('modules', [])
    if not isinstance(rows, list) or not all(isinstance(m, dict) for m in rows):
        raise ValueError('modules must be a list of module objects')
    if not rows:
        raise ValueError('a poster needs at least one module besides the title and lead')
    ids = [m.get('id') for m in rows]
    if any(not isinstance(i, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', i) for i in ids) or len(set(ids)) != len(ids) \
            or set(ids) & {'title', 'lead', 'action', 'footer'}:
        raise ValueError('every module needs a unique id of lowercase letters, digits and hyphens '
                         '(title, lead, action and footer are taken)')
    for m in rows:
        if set(m) - MODULE_KEYS:
            raise ValueError(f"{m['id']}: unknown keys {', '.join(sorted(set(m) - MODULE_KEYS))}")

    title = str(outline['title'])
    content = {'title': title}
    relations = {}
    modules = [dict(id='title', level=1, role='title', info_type='claim', visual='text', headline='', body=title,
                    weight=1, group=None, root='title')]
    if outline.get('lead'):
        if not isinstance(outline['lead'], dict):
            raise ValueError('lead is one block, for example {"stat": {...}} or {"statement": "..."}')
        store, module, relation = _module('lead', outline['lead'], 'lead', lead=True)
        content['lead'] = store
        modules.append(dict(module, root='lead'))
        if relation:
            relations['lead'] = relation
    for m in rows:
        root = 'm-' + m['id']
        store, module, relation = _module(m['id'], m, root)
        content[root] = store
        modules.append(dict(module, root=root))
        if relation:
            relations[root] = relation
    if outline.get('action'):
        content['action'] = str(outline['action'])
        modules.append(dict(id='action', level=3, role='cta', info_type='cta', visual='stamp', headline='',
                            body=content['action'], weight=.8, group=None, root='action'))
    if outline.get('footer'):
        content['footer'] = str(outline['footer'])
        modules.append(dict(id='footer', level=4, role='logistics', info_type='logistics', visual='ticket',
                            headline='', body=content['footer'], weight=.25, group=None, root='footer'))

    source = dict(content=content)
    if relations:
        source['relations'] = relations
    plan = cp.scaffold(source, 'poster', 'verbatim')
    atoms = [atom['id'] for atom in plan['atoms']]
    owner = {}
    for order, module in enumerate(modules):
        root = module.pop('root')
        module['order'] = order
        module['atoms'] = [a for a in atoms if a == root or a.startswith(root + '.')]
        for atom in module['atoms']:
            owner[atom] = module['id']
    plan['modules'] = modules
    plan['ledger'] = [dict(atom=atom, status='kept', into=[owner[atom]], reason='Written for this poster')
                      for atom in atoms]
    meta = dict(outline.get('meta', {}))
    meta.setdefault('lang', 'en')
    plan.update(mode='infographic', origin='outline', thesis=title, cta=str(outline.get('action', '')),
                audience=str(outline.get('audience') or 'General audience'),
                purpose=str(outline.get('purpose') or 'Posted, read standing'), meta=meta,
                art_direction=dict(outline.get('look', {})))
    if outline.get('canvas'):
        plan['canvas'] = outline['canvas']

    # The author chose the forms. Level 2 goes to figures and diagrams first,
    # then to as much plain copy as the source's evidence level allows; the
    # rest supports at level 3. A sheet that is still text-heavy for its
    # figures keeps its copy and records a lower level instead of failing.
    natural = cp.evidence_for(plan)['level']
    body = [m for m in modules if m['level'] == 2]

    def settle(level):
        policy = scale(level)
        figures = sum(m['visual'] not in TEXT_FORMS for m in body)
        plain = 0
        for m in body:
            m['level'] = 2
            if m['visual'] in TEXT_FORMS:
                room = figures + plain + 1 <= policy['l2_range'][1]
                if room and (plain + 1) / (figures + plain + 1) <= policy['text_fraction'] + 1e-9:
                    plain += 1
                else:
                    m['level'] = 3
        second = [m for m in body if m['level'] == 2]
        return (policy['l2_range'][0] <= len(second) <= policy['l2_range'][1]
                and sum(m['level'] == 3 for m in modules) <= 8
                and all(cp.words(cp.text(m)) <= policy['module_words'] for m in second)
                and cp.words(title) <= policy['thesis_words'])

    for level in [natural] + [v for v in (.75, .5, .25, 0.) if v < natural]:
        if settle(level):
            if level != natural:
                plan['evidence'] = dict(level=level, override_reason='Outline forms and copy were set by the author; '
                                                                     'the sheet keeps its own balance of text and figures.')
            break
    return cp.annotate(plan)


def compile_outline(path, out):
    """Expand and lint; write the plan. Returns (ok, lines to print)."""
    import content_plan as cp
    try:
        outline = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        plan = expand(outline)
        report = cp.lint(plan)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return False, ['outline: FAILED', 'error: ' + str(exc)]
    lines = ['advice: ' + line for line in advice(outline)[:4]]
    if plan.get('evidence', {}).get('override_reason') and plan['evidence']['profile']['data_density'] >= .5:
        lines.append('advice: text-heavy for a source with figures. A stat or chart from its numbers would carry more.')
    if not report['ok']:
        return False, ['outline: FAILED'] + ['error: ' + e for e in report['errors'][:8]] + lines
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8')
    return True, lines


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--outline', required=True)
    ap.add_argument('--out', required=True, help='write the expanded content plan here')
    args = ap.parse_args()
    ok, lines = compile_outline(args.outline, args.out)
    if ok:
        print('outline: OK')
    print('\n'.join(lines))
    return int(not ok)


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    raise SystemExit(main())
