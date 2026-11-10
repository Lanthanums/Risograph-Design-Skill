"""Deck-only paper panels, with native contours and a quiet reading face."""
from hashlib import sha256
import math
import random

from native_vectors import bounds

CUT_STOCK = ('anchor', 'newsclip', 'tabbed', 'proof', 'case')


def _contour(left, top, right, bottom, rng, style):
    """Cut top and sides, with one seeded torn edge below the live copy."""
    width = right - left
    count = max(16, math.ceil(width / 5))
    phase = rng.uniform(0, math.tau)
    tear = []
    for i in range(count + 1):
        x = right - width * i / count
        grain = 1.5 * math.sin(x / 16 + phase) + rng.uniform(-1.7, 1.7)
        if style in CUT_STOCK:
            grain += 2.2 * math.sin(i / count * math.tau * 2.1 + phase)
        tear.append([x, bottom + grain])
    if style == 'cut':
        return [[left, top], [right - 15, top], [right, top + 13],
                [right, bottom - 2], [left, bottom]]
    if style == 'tab':
        return [[left, top + 2], [left + 78, top], [left + 89, top + 5],
                [right, top + 5], *tear]
    if style in CUT_STOCK:
        lip = min(32, width * .12)
        return [[left, top + 5], [left + lip, top + 1], [right - lip, top + 2],
                [right - (6 if style == 'newsclip' else 0), top + 7], *tear,
                [left + 1, (top + bottom) / 2]]
    return [[left, top + 1], [right - 2, top], [right, top + 4], *tear]


def _shift(path, dx, dy):
    return [[x + dx, y + dy] for x, y in path]


def screen(left, top, columns, rows, pitch=4.8):
    """Draw an ink screen that thins across the scrap instead of blurring."""
    return [
        [[left + (col + (row % 2) * .5) * pitch + r * math.cos(a * math.tau / 8),
          top + row * pitch + r * math.sin(a * math.tau / 8)] for a in range(8)]
        for row in range(rows) for col in range(columns)
        if (r := 1.65 - 1.15 * col / max(1, columns - 1) - row * .07) > .3
    ]


def add_panel(plan, start, module_id, region, members, style='sheet'):
    """Insert material below the measured list, returning its source binding."""
    rx, ry, x1, text_bottom = region
    compact = style != 'sheet'
    left, top, right = rx + 3, ry + 2, x1 - (11 if compact else 14)
    bottom = text_bottom + (8 if compact else 14)
    seed = f"{plan['seed']}:{module_id}"
    rng = random.Random(int(sha256(seed.encode()).hexdigest()[:16], 16))
    ink = plan['ink_plan']
    content = [ob for ob in members if ob['kind'] == 'text']
    live = [left + 10, top + (10 if compact else 12), right - 10,
            bottom - (7 if compact else 10)]
    for ob in content:
        x, y, xx, yy = ob['rect']
        if x < live[0] - .01 or y < live[1] - .01 or xx > live[2] + .01 or yy > live[3] + .01:
            raise ValueError(f"{module_id}: paper panel cannot contain {ob['id']} with a quiet inset")
        ob['paper_panel'] = module_id
        ob['paper_style'] = style

    def surface(suffix, paths, fill, opacity=None):
        return dict(id=f'{module_id}-paper-{suffix}', kind='path', paths=paths,
                    rect=bounds(paths), closed=True, fill=fill, opacity=opacity,
                    role='surface', layer='surface', material=f'list-paper-{suffix}', paper_style=style,
                    anchor=content[0]['id'], rotation=0)

    face = _contour(left, top, right, bottom, rng, style)
    back = _contour(left + 7, top + 6, right + (6 if compact else 8),
                    bottom + (6 if compact else 11), rng, style)
    dot_paths = []
    rows = (bottom + 3.5, bottom + 6) if compact else (bottom + 4.5, bottom + 8.5)
    for row, y in enumerate(rows):
        for col in range(10 if compact else 19):
            origin = left + 20 if style == 'tab' else right - (68 if compact else 115)
            x = origin + col * 5.5 + row * 2.75
            radius = 0.65 + 0.65 * col / 18 + row * .22
            dot_paths.append([[x + radius * math.cos(a * math.tau / 8),
                               y + radius * math.sin(a * math.tau / 8)] for a in range(8)])
    layers = [
        surface('shadow', [_shift(back, 2, 3)], ink['body'], 13),
        surface('backing', [back], ink['main'][1]),
    ]
    if style != 'cut':
        layers.append(surface('screen', dot_paths, ink['main'][1], 72))
    layers.extend([surface('contact', [_shift(face, 1, 2.5)], ink['body'], 17),
                   surface('face', [face], ink['paper'])])
    face_id = layers[-1]['id']
    if style in CUT_STOCK:
        lip = [[left+5,bottom-4], [left+56,bottom-2], [left+69,bottom+8],
               [left+14,bottom+10]]
        fiber = _contour(left-2, top+1, right+2, bottom+2, rng, style)
        back_start = left + (12 if style in ('anchor', 'tabbed') else 40)
        back = _contour(back_start, top+9, right+4, bottom+8, rng, style)
        dots = screen(right-91 if style == 'anchor' else left+18,
                      bottom+3, 15 if style == 'anchor' else 9, 2, 4.6)
        layers = [
            surface('shadow', [_shift(back, 1.5, 2.5)], ink['body'], 13),
            surface('backing', [back, lip], ink['main'][1]),
            surface('fiber', [fiber], ink['paper']),
            surface('face', [face], ink['paper']),
            surface('screen', dots, ink['main'][1], 76),
        ]
        face_id = layers[3]['id']
    if style in ('tab', 'tabbed'):
        tape = [[right-61, top-3], [right-17, top-5],
                [right-16, top+6], [right-59, top+7]]
        layers.append(surface('tape', [tape], ink['accent'], 58))
    plan['objects'][start:start] = layers
    plan['overlaps'].extend(dict(objects=[ob['id'], face_id],
                                 reason='List text on a paper panel', min_contrast=4.5)
                            for ob in content)
    return dict(module=module_id, rect=bounds([path for ob in layers for path in ob['paths']]),
                live_rect=live, face=face_id, members=[ob['id'] for ob in content],
                layers=[ob['id'] for ob in layers], style=style)


def panel_color(theme, material, style='sheet'):
    """Choose a light stock and a palette-derived ink for the exposed layer."""
    def mix(color, weight):
        paper = theme.paper.lstrip('#')
        ink = color.lstrip('#')
        return ''.join(f'{round(int(paper[i:i+2], 16) * (1-weight) + int(ink[i:i+2], 16) * weight):02X}'
                       for i in (0, 2, 4))

    if material == 'list-paper-face':
        if style in CUT_STOCK:
            base, weight = {
                'anchor': (theme.inkB, .13), 'newsclip': ('FFFFFF', .83),
                'tabbed': (theme.accent1, .23), 'proof': (theme.inkA, .10),
                'case': ('FFFFFF', .62),
            }[style]
            return mix(base, weight)
        return mix('FFF8DA' if style == 'tab' else 'FFFFFF', .69 if style != 'cut' else .86)
    if material == 'list-paper-backing':
        if style in CUT_STOCK:
            return mix(theme.inkA if style in ('anchor', 'proof') else theme.inkB, .72)
        return mix(theme.inkA if style == 'cut' else theme.accent1 if style == 'tab' else theme.inkB, .42)
    if material == 'list-paper-screen':
        return mix(theme.inkB, .9)
    if material == 'list-paper-tape':
        return mix(theme.accent1, .55)
    if material == 'list-paper-fiber':
        return mix('FFFFFF', .92)
    return theme.text


def cutaway(slide, theme, rect, seed, icon=None):
    """A short collage in the existing white space of a case page."""
    from glyphs import glyph
    from native_vectors import native_path
    left, top, right, bottom = rect
    width = right - left
    rng = random.Random(seed)

    def layer(name, paths, color, opacity=None):
        return native_path(slide, dict(id='case-cutaway-' + name, rect=bounds(paths),
                                       paths=paths, fill=color, closed=True, opacity=opacity))

    backing = _contour(left+6, top+22, right-18, bottom-5, rng, 'case')
    face = _contour(left+width*.19, top+8, right-37, bottom-12, rng, 'case')
    layer('shadow', [_shift(backing, 3, 3)], theme.text, 16)
    layer('base', [backing], theme.inkA, 71)
    layer('ink-slip', [_contour(left+width*.47, top+20, right-4, bottom-13, rng, 'cut')],
          theme.inkB, 80)
    layer('edge', [_shift(face, 0, 2)], theme.paper)
    layer('stock', [face], panel_color(theme, 'list-paper-face', 'case'))
    layer('screen', screen(left+width*.56, top+20, 15, 6), theme.inkA, 77)
    layer('tape', [[[left+12,top+12], [left+58,top+6], [left+63,top+18], [left+16,top+23]]],
          theme.inkB, 66)
    if icon:
        size = min(42, (bottom-top)*.56)
        x, y = left + width*.28, top + 12
        native_path(slide, glyph(icon, [x, y, x+size, y+size], theme.inkA,
                                'case-cutaway-glyph', 'case-cutaway-stock'))
    else:
        # A blind-ruled fragment suggests a clipped note without dummy copy.
        x = left + width*.27
        paths = [[[x, top+24+i*7], [x+width*(.18-i*.015), top+24+i*7]] for i in range(4)]
        native_path(slide, dict(id='case-cutaway-ruling', rect=bounds(paths, .45),
                               paths=paths, line=theme.inkA, line_width=.7, opacity=57))
