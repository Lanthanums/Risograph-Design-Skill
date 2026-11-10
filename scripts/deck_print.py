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
