"""English deck print fields, adapted from the 2.1.0 slide recipes."""

# The focal page and section break carry the strongest ink fields.
# Interior pages use smaller halftone fields beside the argument.
PRESET_BY_PAGE = {
    'cover': 'cover-bleed-tr',
    'divider': 'reverse-circle-br',
    'closing': 'reverse-circle-tr',
    'statement': 'corner-fade-tr-xs',
    'quote': 'corner-fade-tr-xs',
    'data': 'corner-fade-br',
    'chart': 'corner-fade-br',
    'numbered': 'edge-fade-right',
    'timeline': 'corner-fade-tr-sm',
    'versus': 'corner-speckle-tr',
    'grid': 'corner-speckle-tr',
    'features': 'corner-fade-tr-sm',
}


def page_field(spec, page, index, english):
    """Resolve the author field first, with deck-local semantic defaults."""
    from make_textures import expand_presets

    fields = spec.get('backgrounds', {})
    if not isinstance(fields, dict):
        raise ValueError('backgrounds must map page numbers to background settings')
    field = fields.get(str(index), page.get('background'))
    archetype = page.get('archetype', 'data')
    reverse = bool(page.get('reverse', archetype in ('divider', 'closing')))
    default_enabled = english and (bool(page.get('modules')) or
                                   spec.get('meta', {}).get('print_grammar') == 'full')
    if field is None and spec.get('meta', {}).get('print_fields', default_enabled):
        preset = ('cover-bleed-tr' if index == 1 and archetype == 'statement'
                  else PRESET_BY_PAGE.get(archetype))
        if preset:
            field = {'preset': preset}
    if field is None:
        field = {}
    if not isinstance(field, dict):
        raise ValueError(f'Background for page {index} must be an object')
    try:
        settings = expand_presets(dict(field))
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc
    settings.setdefault('reverse', reverse)
    settings.setdefault('registration_marks', english and spec.get('meta', {}).get('print_grammar') == 'full')
    # 2.1.0 shipped these aliases in the preset catalogue.
    if 'field' in settings:
        aliases = {'f': 'falloff', 'sp': 'spacing', 'rm': 'rmax', 'a': 'alpha'}
        settings['field'] = {aliases.get(k, k): v for k, v in settings['field'].items()}
    return settings


# Fields for quotation pages, in page points. A flooded page takes a wide dot
# screen from its lower left. A paper page takes two overprinted circles and
# a bounded screen at the foot, clear of the page number.
QUOTE_FIELDS = {
    'flood': dict(field=dict(c=[-20, 620], dir=[1, -0.45], falloff=265, spacing=14, rmax=6.8, alpha=180),
                  dot_ink='B'),
    'bloom-right': dict(circles=[[630, 672, 210, 'B'], [478, 630, 116, 'A']],
                        field=dict(c=[430, 640], dir=[-1, -0.5], falloff=300, spacing=13, rmax=5.6, alpha=150,
                                   radius=270)),
    'bloom-left': dict(circles=[[330, 655, 210, 'B'], [482, 612, 116, 'A']],
                       field=dict(c=[530, 640], dir=[1, -0.5], falloff=300, spacing=13, rmax=5.6, alpha=150,
                                  radius=270)),
}


def feature_quote_field(spec, fields):
    """Print the featured quotation on a flooded ink field with a dot screen.

    An authored background or ``reverse`` setting wins. Beside another
    reversed page the quotation keeps its paper and takes overprinted
    circles with a screen instead, so two floods never meet.
    """
    from copy import deepcopy
    from deck_refinements import featured_quote

    pages = spec.get('pages', [])
    reversed_pages = {i for i, field in enumerate(fields, 1) if field['reverse']}
    feature = featured_quote(pages, reversed_pages)
    # A deck carries at most two flooded pages; dividers and the close come first.
    room = len(reversed_pages) < 2
    for number, page in enumerate(pages, 1):
        if page.get('archetype') != 'quote' or not page.get('editorial'):
            continue
        if (str(number) in spec.get('backgrounds', {}) or page.get('background') is not None
                or 'reverse' in page):
            continue
        # A supporting quotation keeps its paper and takes the circles.
        flood = number == feature and room and not {number - 1, number + 1} & reversed_pages
        # The classic composition reads down the left, so its circles sit right.
        paper = 'bloom-right' if number == feature else 'bloom-left'
        settings = deepcopy(QUOTE_FIELDS['flood' if flood else paper])
        settings['reverse'] = flood
        settings['registration_marks'] = fields[number - 1].get('registration_marks', False)
        fields[number - 1] = settings
        # The quotation writers keep clear of the field they are printed on.
        page['_quote_field'] = 'flood' if flood else 'bloom'
        if flood:
            reversed_pages.add(number)
    return feature


def chrome_foreground(theme):
    """Choose the higher-contrast available ink for small reversed labels."""
    def luminance(color):
        color = color.lstrip('#')
        rgb = [int(color[i:i+2], 16) / 255 for i in (0, 2, 4)]
        channels = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
        return sum(v * w for v, w in zip(channels, (.2126, .7152, .0722)))

    base = luminance(theme.inkA)
    def contrast(color):
        low, high = sorted((base, luminance(color)))
        return (high + .05) / (low + .05)

    return max((theme.paper, theme.ink), key=contrast)
