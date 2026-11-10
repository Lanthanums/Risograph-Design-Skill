"""Press-style chart furniture, using the existing spot inks and source data."""
from deck_paper_collage import screen
from native_vectors import bounds

PRESS_FORMS = frozenset(('bar-compare', 'bar-vertical', 'line-chart', 'ring', 'stacked-bar'))


def bar_rows(mid, items, tx, yy, tw, body, peak, unit, ink, val, box, path):
    """Give labels, zero-based bars and tabular values their own columns."""
    labels = tw * .34
    value_width = max(65, min(108, tw * .17))
    start = tx + labels + 11
    value_x = tx + tw - value_width
    scale = (value_x - start - 16) / peak
    top = yy
    axis = path(mid+'-zero-axis', [[[start, top+5], [start, top+6]]], ink['main'][1], role='structure')
    for j, item in enumerate(items):
        prefix = f'visual_data.items.{j}'
        label = val(prefix+'.label', item['label'], tx, yy+5, labels, body, tidy_rag=True)
        value = val(prefix+'.value', item['value'], value_x, yy+5, value_width, body, True)
        size = float(item['value']) * scale
        if size > 0:
            bar = box(mid+f'-bar-{j}', [start, yy+8, start+size, yy+8+body*.73],
                      ink['main'][j % 2], anchor=label['id'])
            bar['data_point'] = dict(atom=item.get('atom'), value=item['value'], unit=unit,
                                     zero_origin=start, scale=scale, axis='x')
        yy = max(label['rect'][3], value['rect'][3], yy+body+10) + 7
        rule = path(mid+f'-rule-{j}', [[[tx, yy-2], [tx+tw, yy-2]]], ink['main'][1], role='structure')
        rule['line_width'] = .55
        rule['stroke_opacity'] = 48
    axis['paths'][0][1][1] = yy-2
    axis['rect'] = bounds(axis['paths'], .4)
    axis['line_width'] = .75
    axis['stroke_opacity'] = 68
    return yy + 5


def finish(plan, start, module, region):
    """Place editorial rules and a screen strictly inside measured bar faces."""
    ink = plan['ink_plan']
    objects = plan['objects']
    for ob in objects[start:]:
        if ob['kind'] != 'rect' or ob['role'] != 'data' or not ob.get('fill'):
            continue
        x, y, right, bottom = ob['rect']
        if right-x < 15 or bottom-y < 11:
            continue
        # The dot field never changes either endpoint of the data mark.
        paths = screen(x+3.6, y+3.4, min(15, int((right-x-5)/4.5)),
                       min(3, int((bottom-y-4)/4.5)), 4.5)
        if paths:
            objects.insert(objects.index(ob)+1, dict(
                id=ob['id']+'-ink-screen', kind='path', rect=bounds(paths), paths=paths,
                closed=True, fill=ink['paper'], opacity=44, role='surface',
                layer='surface', material='press-ink-screen', anchor=ob['id']))

    x, y, right, _ = region
    paths = [[[x+10, y+1], [right-10, y+1]]]
    objects.insert(start, dict(
        id=module+'-press-rule', kind='path', rect=bounds(paths, .6), paths=paths,
        line=ink['main'][0], line_width=1.2, role='surface',
        layer='surface', material='press-column-rule', anchor='title'))
