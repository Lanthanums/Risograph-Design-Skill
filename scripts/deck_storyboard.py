"""Validate the editorial decisions against the pages the deck will render."""

PAGE_FIELDS = ('purpose', 'takeaway', 'layout', 'visual_role', 'print_role',
               'transition', 'risk', 'fallback')
DENSITIES = ('light', 'medium', 'dense')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_storyboard(plan, pages, *, required=False):
    if 'storyboard' not in plan:
        return ['An authored deck requires plan.storyboard'] if required else []

    board = plan['storyboard']
    if not isinstance(board, dict):
        return ['storyboard must be an object']

    errors = []
    if plan.get('target') != 'deck' or plan.get('mode') == 'editorial':
        errors.append('storyboard requires an authored deck plan, separate from editorial migration')
    meta = plan.get('meta', {})
    lang = meta.get('lang') if isinstance(meta, dict) else None
    if not isinstance(lang, str) or lang.lower().split('-')[0] != 'en':
        errors.append('storyboard requires an English deck (meta.lang: en)')

    for key in ('rationale', 'art_direction'):
        if not _text(board.get(key)):
            errors.append(f'storyboard.{key} must be non-empty text')
    if not isinstance(board.get('pages'), list) or not board['pages']:
        return errors + ['storyboard.pages must be a non-empty list']

    entries = board['pages']
    if not all(isinstance(row, dict) and _text(row.get('id')) for row in entries):
        return errors + ['Every storyboard page needs a non-empty string id']

    ids = [row['id'] for row in entries]
    compiled_ids = [page.get('id') for page in pages]
    if ids != compiled_ids:
        errors.append(f'Storyboard page IDs must match compiled page order: {compiled_ids!r}')
    if len(set(ids)) != len(ids):
        errors.append('Storyboard page IDs must be unique')

    membership = {
        page.get('id'): [module['id'] for module in page.get('modules', [])]
        for page in pages
    }
    for module in plan['modules']:
        page_id = module.get('page')
        if not _text(page_id) or page_id not in membership:
            errors.append(f"Module {module['id']!r} needs an explicit storyboard page")
    for row in entries:
        label = f"storyboard page {row['id']!r}"
        for key in PAGE_FIELDS:
            if not _text(row.get(key)):
                errors.append(f'{label} needs non-empty {key}')
        if row.get('modules') != membership.get(row['id']) or not row.get('modules'):
            errors.append(f'{label} must list its compiled module IDs in order')
        order = row.get('reading_order')
        if not isinstance(order, list) or not order or not all(map(_text, order)):
            errors.append(f'{label} needs reading_order as a list of text cues')
        if row.get('density') not in DENSITIES:
            errors.append(f"{label} density must be light, medium or dense")
        if 'density_reason' in row and not _text(row['density_reason']):
            errors.append(f'{label} density_reason must be non-empty text')
    return errors


def markdown(plan, module_text):
    board = plan['storyboard']
    lines = ['# PowerPoint storyboard', '', plan['thesis'], '',
             f"Audience — {plan['audience']}", f"Purpose — {plan['purpose']}"]
    if plan.get('cta'):
        lines.append(f"Desired action — {plan['cta']}")
    lines.extend(('', '## Sequence', '', board['rationale'], '',
                  '## Art direction', '', board['art_direction']))
    fields = (*PAGE_FIELDS, 'density', 'density_reason', 'reading_order', 'modules')
    modules = {module['id']: module for module in plan['modules']}
    for number, row in enumerate(board['pages'], 1):
        lines.extend(('', f"## {number}. {row['id']}", ''))
        for key in fields:
            if key not in row:
                continue
            value = row[key]
            if isinstance(value, list):
                value = ' → '.join(value) if key == 'reading_order' else ', '.join(value)
            lines.append(f"- **{key.replace('_', ' ').capitalize()}** — {value}")
        lines.extend(('', '### Visible copy and evidence'))
        for mid in row['modules']:
            copy = module_text(modules[mid]).strip()
            if copy:
                lines.extend(('', f'**{mid}**', '', copy))
        notes = [modules[mid].get('notes') for mid in row['modules']]
        if any(notes):
            lines.extend(('', '### Speaker notes', '', '\n\n'.join(note for note in notes if note)))
    return '\n'.join(lines) + '\n'
