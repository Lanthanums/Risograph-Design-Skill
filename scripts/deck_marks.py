"""PPT-specific emphasis vocabulary."""
from native_vectors import bounds

ICON_BY_TYPE=dict(statistic='person',claim='chat',process_step='arrow',comparison='document',
                  part_whole='box',timeline='calendar',definition='book',quote='chat',
                  example='bulb',cta='flag',logistics='location',source='document')


def title_rule(title, top, color):
    """One editable ink stroke directly below the measured title."""
    x = title['rect'][0]
    right = x + min(title['rect'][2] - x, title['fit']['width'])
    paths = [[[x, top], [right, top]]]
    return dict(id='title-rule', kind='path', paths=paths, rect=bounds(paths, 2),
                line=color, line_width=4, role='emphasis', rotation=0,
                anchor=title['id'], micro=True, vocabulary='underline')


def quote_screen(slide, x, y, color):
    """One editable spot-ink swatch that fades away from the quotation mark."""
    from glyphs import circle
    from native_vectors import native_path

    paths = [
        circle(x + col * 4.4 + (row % 2) * 2.2, y + row * 3.8,
               1.75 - col * .16, n=8)
        for row in range(6) for col in range(9)
    ]
    return native_path(slide, dict(id='quote-screen', paths=paths,
                                   rect=bounds(paths), fill=color, closed=True))
