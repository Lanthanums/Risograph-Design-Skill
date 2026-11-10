"""Bind source modules to deck-specific editorial compositions."""


def bind(page, composition, controls):
    """Copy only fields that the selected writer can faithfully render."""
    if composition not in ('cover', 'quote'):
        raise ValueError(f"{page['id']}: composition must be auto, cover or quote")
    modules = page['modules']
    if len(modules) != 1:
        raise ValueError(f"{page['id']}: {composition} needs one module; bind context and attribution in visual_data")
    module = modules[0]
    data = module.get('visual_data', {})
    headline = module.get('headline')
    body = module.get('body')
    if composition == 'cover':
        if (not isinstance(headline, str) or not headline.strip()
                or module['visual'] not in ('text', 'key-statement', 'summary-box')
                or not isinstance(data, dict) or data.keys() - {'kicker', 'context'}):
            raise ValueError(f"{page['id']}: cover needs a headline and optional body/kicker/context")
        size = controls.pop('title_size', 78)
        if type(size) not in (int, float) or not 42 <= size <= 180:
            raise ValueError(f"{page['id']}: cover title_size must be 42–180pt")
        page.update(archetype='cover', composition='classic-cover', title_size=size,
                    thesis=[body] if body else [], question=data.get('kicker'),
                    aside=data.get('context'), aside_size=16)
        return

    if (module['visual'] != 'pull-quote' or not isinstance(body, str) or not body.strip()
            or not isinstance(data, dict)
            or data.keys() - {'attribution', 'context'}):
        raise ValueError(f"{page['id']}: quote needs pull-quote, body and optional attribution/context")
    page.update(archetype='quote', composition='editorial-quote', lines=body,
                attribution=data.get('attribution'), source=data.get('context'), editorial=True)
    if headline and headline != body:
        page['header_left'] = headline
