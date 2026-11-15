"""Expand a compact deck outline into a full content plan.

The outline states each page once: its title, its copy as typed blocks, and
one or two lines of direction. This module derives the source inventory, the
atom bindings, the coverage ledger and the storyboard rows from it, so the
author writes the copy a single time. The full plan format stays available
for work that needs a ledger against an external source document.
"""
import argparse
import json
import re
import sys
from pathlib import Path

CHARTS = {'bars': 'bar-compare', 'columns': 'bar-vertical', 'line': 'line-chart', 'ring': 'ring',
          'stacked': 'stacked-bar'}
BLOCKS = ('statement', 'text', 'list', 'stat', 'chart', 'versus', 'steps', 'timeline', 'quote', 'modules')
PAGE_KEYS = {'id', 'kind', 'title', 'body', 'kicker', 'context', 'blocks', 'note', 'notes', 'job', 'takeaway',
             'look', 'print', 'next', 'risk', 'fallback', 'density', 'direction', 'ordered', 'emphasis', 'by',
             'featured', 'heading', 'image', *BLOCKS}
LOOKS = {
    'cover': 'Left editorial stack: the title above a short deck line.',
    'section': 'Reversed divider with a large section number.',
    'statement': 'One statement at a reading measure with open space beside it.',
    'text': 'A measured column of copy under the page title.',
    'list': 'Points on torn paper, read left to right and then down.',
    'stat': 'A dominant figure with its label, then the sentence that explains it.',
    'chart': 'A chart set as a newspaper clipping with its values labelled.',
    'versus': 'Two sheets side by side on a shared baseline.',
    'steps': 'A numbered sequence read left to right.',
    'timeline': 'Dated nodes along one line.',
    'quote': 'The exact words as the dominant block with the credit attached.',
    'modules': 'Measured evidence bands under the page title.',
}
PRINTS = {
    'cover': 'Offset title plates and the overprinted corner field.',
    'section': 'Flooded ink field.',
    'list': 'Torn cards or one ruled sheet over a spot-ink field.',
    'chart': 'Newsprint clipping with a second plate out of register.',
    'versus': 'Two reading sheets over one torn field.',
    'quote': 'A flooded field with a dot screen for the featured quotation, overprinted circles otherwise.',
}


def _words(value):
    return len(re.findall(r"[\w'’-]+", str(value)))


def _pairs(rows, name):
    out = []
    for row in rows:
        if isinstance(row, str):
            out.append(dict(label=row))
        elif isinstance(row, (list, tuple)) and 1 <= len(row) <= 2 and all(isinstance(v, str) for v in row):
            out.append(dict(label=row[0], **({'text': row[1]} if len(row) == 2 and row[1] else {})))
        else:
            raise ValueError(f'{name}: each entry is a string or a [cue, detail] pair')
    if not out:
        raise ValueError(f'{name}: needs at least one entry')
    return out


def _blocks(page):
    """The page's blocks as (kind, value, options) in reading order."""
    if 'blocks' in page:
        rows = page['blocks']
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{page['id']}: blocks must be a non-empty list")
    else:
        rows = [{key: page[key] for key in page if key in BLOCKS or key in ('ordered', 'emphasis', 'by',
                                                                           'context', 'featured')}]
    out = []
    for row in rows:
        kinds = [key for key in BLOCKS if key in row]
        if len(kinds) != 1:
            if not kinds and page.get('kind') in ('cover', 'section'):
                continue
            raise ValueError(f"{page['id']}: each block needs exactly one of {', '.join(BLOCKS)}")
        out.append((kinds[0], row[kinds[0]], {k: v for k, v in row.items() if k != kinds[0]}))
    return out


def advice(outline):
    """Short notes on copy that will build but will not look its best."""
    notes = []
    for page in outline.get('pages', []):
        if not isinstance(page, dict):
            continue
        rows = page.get('blocks') if isinstance(page.get('blocks'), list) else [page]
        for row in rows:
            if not isinstance(row, dict):
                continue
            quote = row.get('quote')
            if isinstance(quote, str) and _words(quote) > 30:
                notes.append(f"{page.get('id')}: the quotation is {_words(quote)} words. A quotation page reads "
                             'best at 30 or fewer, so quote the strongest sentence.')
            cues = [item[0] for item in row.get('list', []) if isinstance(item, (list, tuple)) and len(item) == 2]
            if any(_words(cue) > 7 for cue in cues):
                notes.append(f"{page.get('id')}: a list cue runs past seven words. Keep the cue short and move "
                             'the rest into its detail.')
        if isinstance(page.get('title'), str) and _words(page['title']) > 12 and page.get('kind', 'content') == 'content':
            notes.append(f"{page.get('id')}: the title is {_words(page['title'])} words and will take three lines.")
    return notes


def expand(outline):
    """Return a lintable content plan for the outline."""
    import deck_content_plan as dcp

    for key in ('thesis', 'audience', 'purpose', 'rationale', 'art_direction', 'pages'):
        if not outline.get(key):
            raise ValueError(f'outline needs {key}')
    meta = dict(outline.get('meta', {}))
    meta.setdefault('lang', 'en')
    if not meta.get('title'):
        raise ValueError('outline.meta.title is required')
    pages = outline['pages']
    ids = [page.get('id') for page in pages]
    if any(not isinstance(i, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', i) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('every page needs a unique id of lowercase letters, digits and hyphens')

    content, relations, modules, directions, board = {}, {}, [], {}, []

    def module(page_id, mid, visual, prefix, level=2, headline='', body='', info='claim', data=None, **extra):
        row = dict(id=mid, page=page_id, level=level, info_type=info, visual=visual, headline=headline, body=body,
                   prefix=prefix, weight=.25 if level == 4 else 1, notes='', order=len(modules))
        if data:
            row['visual_data'] = data
        row.update(extra)
        modules.append(row)
        return row

    for index, page in enumerate(pages):
        pid = page['id']
        unknown = set(page) - PAGE_KEYS
        if unknown:
            raise ValueError(f"{pid}: unknown keys {', '.join(sorted(unknown))}")
        kind = page.get('kind', 'content')
        if kind not in ('cover', 'section', 'content', 'closing'):
            raise ValueError(f'{pid}: kind must be cover, section, content or closing')
        root = 's-' + pid
        store = content.setdefault(root, {})
        direction = dict(page.get('direction', {}))
        if page.get('image'):
            if kind in ('cover', 'section'):
                raise ValueError(f'{pid}: image belongs on a content page')
            direction['image'] = page['image']
        title = page.get('title', '')
        families = []
        first = len(modules)
        if kind == 'cover':
            if not title:
                raise ValueError(f'{pid}: a cover needs a title')
            store['title'] = title
            data = {}
            for key in ('body', 'kicker', 'context'):
                if page.get(key):
                    store[key] = page[key]
                    if key != 'body':
                        data[key] = page[key]
            module(pid, pid, 'text', root, 1, title, page.get('body', ''), data=data)
            direction.setdefault('composition', 'cover')
            families.append('cover')
        elif kind == 'section':
            if not title:
                raise ValueError(f'{pid}: a section needs a title')
            store['title'] = title
            module(pid, pid, 'text', root, 1, title, slide_kind='section')
            families.append('section')
        else:
            blocks = _blocks(page)
            if not blocks:
                raise ValueError(f'{pid}: a content page needs a block')
            if title:
                store['title'] = title
            for number, (block, value, options) in enumerate(blocks):
                key = f'b{number}'
                prefix = f'{root}.{key}'
                mid = pid if number == 0 else f'{pid}-{number + 1}'
                lead = number == 0
                headline = title if lead else options.get('heading', '')
                if not lead and headline:
                    store[key + 'h'] = headline
                level = 1 if kind == 'closing' and lead else 2 if lead or headline else 3
                families.append(block)
                if block in ('statement', 'text'):
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(f'{pid}: {block} must be text')
                    store[key] = value
                    data = {'emphasis': options['emphasis']} if options.get('emphasis') else None
                    if block == 'statement' and not title:
                        headline, value = value, ''
                    module(pid, mid, 'key-statement' if block == 'statement' else 'text', prefix, level, headline,
                           value, info='cta' if kind == 'closing' else 'claim', data=data)
                elif block == 'list':
                    items = _pairs(value, f'{pid}.list')
                    store[key] = [dict(item) for item in items]
                    module(pid, mid, 'takeaway-list', prefix, level, headline, data=dict(items=items))
                    if options.get('ordered'):
                        direction.setdefault('list_order', 'ordered')
                elif block in ('versus', 'steps', 'timeline'):
                    items = _pairs(value, f'{pid}.{block}')
                    if block == 'versus' and len(items) != 2:
                        raise ValueError(f'{pid}: versus needs exactly two sides')
                    store[key] = [dict(item) for item in items]
                    relations[prefix] = 'contrast' if block == 'versus' else 'sequence'
                    visual = dict(versus='contrast-pair', steps='step-flow', timeline='timeline')[block]
                    data = dict(items=items)
                    if block == 'steps':
                        data['orientation'] = options.get('orientation', 'horizontal' if len(items) <= 3 else 'auto')
                    module(pid, mid, visual, prefix, level, headline, options.get('body', ''),
                           info='comparison' if block == 'versus' else 'process_step' if block == 'steps' else 'timeline',
                           data=data)
                    if options.get('body'):
                        store[key + 'x'] = options['body']
                elif block == 'stat':
                    if not isinstance(value, dict) or not all(str(value.get(k, '')).strip() for k in ('value', 'unit', 'label')):
                        raise ValueError(f'{pid}: stat needs value, unit and label')
                    label = str(value['label'])
                    if str(value['unit']).lower() not in label.lower():
                        label = f"{value['unit']} \u2014 {label}"
                    store[key] = dict(value=str(value['value']), unit=str(value['unit']), label=label)
                    if value.get('body'):
                        store[key]['body'] = value['body']
                    module(pid, mid, 'stat-tile', prefix, level, headline, value.get('body', ''), info='statistic',
                           data=dict(value=str(value['value']), unit=str(value['unit']), label=label,
                                     atom=f'{prefix}.value'))
                elif block == 'chart':
                    form = CHARTS.get(value.get('type') if isinstance(value, dict) else None)
                    points = value.get('points') if isinstance(value, dict) else None
                    if not form or not value.get('unit') or not isinstance(points, list) or len(points) < 2:
                        raise ValueError(f"{pid}: chart needs type ({', '.join(CHARTS)}), unit and two or more points")
                    unit = str(value['unit'])
                    store[key] = [dict(label=str(label), value=str(amount), unit=unit) for label, amount in points]
                    if form == 'line-chart':
                        relations[prefix] = 'sequence'
                    data = dict(unit=unit, items=[dict(label=str(label), value=amount, atom=f'{prefix}.{n}.value')
                                                  for n, (label, amount) in enumerate(points)])
                    module(pid, mid, form, prefix, level, headline,
                           info='part_whole' if form in ('ring', 'stacked-bar') else 'timeline' if form == 'line-chart'
                           else 'comparison', data=data)
                elif block == 'quote':
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(f'{pid}: quote must be the exact words')
                    store[key] = dict(words=value)
                    data = {}
                    for source, target in (('by', 'attribution'), ('context', 'context')):
                        if options.get(source):
                            store[key][source] = options[source]
                            data[target] = options[source]
                    module(pid, mid, 'pull-quote', prefix, 3, headline if not lead else '', value, info='quote',
                           data=data)
                    if lead and len(blocks) == 1 and options.get('featured') is not None:
                        direction.setdefault('quote_priority', 'featured' if options['featured'] else 'supporting')
                else:  # raw modules for a form the shorthand does not cover
                    from deck_source_profile import DATA_FORMS
                    if not isinstance(value, list) or not all(isinstance(m, dict) and m.get('visual') for m in value):
                        raise ValueError(f'{pid}: modules must be a list of module objects with a visual')
                    for n, raw in enumerate(value):
                        if raw['visual'] in DATA_FORMS:
                            raise ValueError(f'{pid}: use a stat or chart block, or a full content plan, for data forms')
                        store[f'{key}m{n}'] = [line for line in dcp.text({k: raw[k] for k in (
                            'headline', 'body', 'visual_data') if raw.get(k)}).split('\n') if line.strip()]
                        row = dict(raw)
                        row.pop('atoms', None)
                        module(pid, raw.get('id', f'{mid}-m{n + 1}'), row.pop('visual'), f'{prefix}m{n}',
                               row.pop('level', 2 if n == 0 and lead else 3), row.pop('headline', headline if n == 0 else ''),
                               row.pop('body', ''), info=row.pop('info_type', 'claim'),
                               data=row.pop('visual_data', None), **{k: v for k, v in row.items() if k != 'id'})
            if page.get('note'):
                store['note'] = page['note']
                module(pid, pid + '-note', 'text', f'{root}.note', 4, '', page['note'], info='source')
        if page.get('notes'):
            modules[first]['notes'] = page['notes']
        if direction:
            directions[pid] = direction

        family = families[0]
        following = pages[index + 1].get('title') if index + 1 < len(pages) else None
        copy_words = _words(json.dumps(store, ensure_ascii=False))
        if kind == 'content' and not (page.get('job') and page.get('look')):
            raise ValueError(f'{pid}: say what the page adds in "job" and what the viewer sees first in "look"')
        board.append(dict(
            id=pid,
            purpose=page.get('job') or ('Open the deck and name its subject.' if kind == 'cover' else
                                        'Mark the turn to the next part.' if kind == 'section' else
                                        'Close on what the audience should remember or do.'),
            takeaway=page.get('takeaway') or title or modules[first].get('body') or outline['thesis'],
            modules=[],
            layout=page.get('look') or LOOKS[family],
            reading_order=(['title'] if title else []) + [f for f in families if f not in ('cover', 'section')]
                          + (['source note'] if page.get('note') else []) or ['title'],
            visual_role=page.get('look') or LOOKS[family],
            print_role=page.get('print') or PRINTS.get(family, 'Open paper page with the deck print marks.'),
            density=page.get('density') or ('light' if copy_words <= 28 else 'medium' if copy_words <= 75 else 'dense'),
            transition=page.get('next') or (f'Leads to: {following}' if following else 'Last page.'),
            risk=page.get('risk') or 'Copy may run long for this composition.',
            fallback=page.get('fallback') or 'The builder returns room in order: body size, insets, one sheet, '
                                             'a smaller title, then the open page.'))

    source = dict(content=content, meta=dict(title=meta['title']))
    if relations:
        source['relations'] = relations
    plan = dcp.scaffold(source, copy_mode='verbatim')
    atoms = [atom['id'] for atom in plan['atoms']]
    for row in modules:
        prefix = row.pop('prefix')
        mine = [a for a in atoms if a == prefix or a.startswith(prefix + '.')]
        if row['id'] == modules[[m['page'] for m in modules].index(row['page'])]['id']:
            # The page's first module carries the page title and any cover lines.
            root = 's-' + row['page']
            mine = [a for a in atoms if a in (f'{root}.title', f'{root}.body', f'{root}.kicker', f'{root}.context')
                    ] + [a for a in mine if a not in (f'{root}.title', f'{root}.body', f'{root}.kicker',
                                                      f'{root}.context')]
        row['atoms'] = mine
    # A block heading and a trailing body sentence belong to their block.
    owner = {}
    for row in modules:
        for atom in row['atoms']:
            owner.setdefault(atom, row['id'])
    for atom in atoms:
        if atom in owner:
            continue
        match = re.fullmatch(r'(s-[a-z0-9-]+\.b\d+)[hx]', atom)
        target = next((row for row in modules if match and any(a.startswith(match[1]) for a in row['atoms'])), None)
        if target is None:
            raise ValueError(f'outline copy {atom!r} is not placed on a slide')
        target['atoms'].append(atom)
        owner[atom] = target['id']
    order = {}
    for level4 in (False, True):
        for row in modules:
            if (row['level'] == 4) == level4:
                order.setdefault(row['page'], []).append(row['id'])
    for row in board:
        row['modules'] = order[row['id']]
    plan['modules'] = modules
    plan['ledger'] = [dict(atom=atom, status='kept', into=[owner[atom]], reason='Written for this slide')
                      for atom in atoms]
    plan.update(mode='storyboard', origin='outline', thesis=outline['thesis'], audience=outline['audience'],
                purpose=outline['purpose'], cta=outline.get('cta', ''), meta=meta, page_directions=directions,
                storyboard=dict(rationale=outline['rationale'], art_direction=outline['art_direction'], pages=board))
    if 'backgrounds' in outline:
        plan['backgrounds'] = outline['backgrounds']
    return dcp.annotate(plan)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--outline', required=True)
    ap.add_argument('--out', help='write the expanded content plan here')
    args = ap.parse_args()
    import deck_content_plan as dcp
    try:
        plan = expand(json.loads(Path(args.outline).read_text(encoding='utf-8-sig')))
        report = dcp.lint(plan, require_storyboard=True)
    except ValueError as exc:
        print('outline: FAILED\n' + str(exc))
        return 1
    if args.out:
        dcp.save(plan, args.out)
    print('outline: ' + ('OK' if report['ok'] else 'FAILED') + f" | {len(plan['storyboard']['pages'])} pages")
    for line in advice(json.loads(Path(args.outline).read_text(encoding='utf-8-sig')))[:5]:
        print('advice: ' + line)
    for line in report['errors']:
        print('error: ' + line)
    for line in report['warnings'][:8]:
        print('warn: ' + line)
    return int(not report['ok'])


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    raise SystemExit(main())
