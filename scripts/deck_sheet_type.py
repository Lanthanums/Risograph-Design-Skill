"""Typography and printed furniture inside a reading sheet.

A sheet of copy reads as designed when its type has more than one voice and
the paper carries a little printed structure: a ruled column head, ledger
lines between the rows of a list, a margin line beside numbered points, and
a highlighter over the few words that carry a statement. Copy stays native.
The furniture is printed on the sheet, so it turns and tears with it.
"""
import re

import textmetrics as tm

LEAD = re.compile(r'^(.{2,36}?)(?::\s+|\s+[—–]\s+)(?=\S)')
TAIL = re.compile(r'(?::\s+|\s+[—–]\s+)([^:—–]+?)[.!?]?$')


def lead_in(label):
    """Length of an opening cue such as "January 1, midnight:" or 0."""
    match = LEAD.match(label)
    if not match or len(label) - match.end() < 4:
        return 0
    return match.end(1) + (1 if label[match.end(1)] == ':' else 0)


def auto_emphasis(text):
    """The closing phrase after a colon or dash, when it is short enough."""
    match = TAIL.search(text.strip())
    if match and 2 <= len(match[1].split()) <= 6:
        return match[1].strip()
    return None


def segments(lines, start, end):
    """Split [start, end) of the joined lines into (line, from, to) pieces."""
    pieces, at = [], 0
    for index, line in enumerate(lines):
        a, b = max(start, at), min(end, at + len(line))
        if a < b:
            pieces.append((index, a - at, b - at))
        at += len(line) + 1
    return pieces


def find(lines, phrase):
    """Offsets of ``phrase`` in the fitted lines, ignoring how they broke."""
    joined = ' '.join(lines)
    wanted = ' '.join(str(phrase).split())
    at = joined.find(wanted)
    return (at, at + len(wanted)) if wanted and at >= 0 else None


def span(ob, start, end, **style):
    """Give part of a text object its own run style. Offsets index the joined lines."""
    ob.setdefault('spans', []).append(dict(start=start, end=end, **style))


def apply_spans(shape, ob, theme):
    """Split each line's run where a span starts or ends, and restyle the pieces."""
    from copy import deepcopy
    import riso_kit as rk

    lines = ob['fit']['lines']
    for item in ob.get('spans', ()):
        style = {k: item[k] for k in ('color', 'bold') if k in item}
        if item.get('bold') is False:
            style['font'] = theme.f_body
        for index, a, b in segments(lines, item['start'], item['end']):
            paragraph = shape.text_frame.paragraphs[index]
            # Earlier spans may have split this line already.
            position = 0
            for run in list(paragraph.runs):
                text = run.text
                lo, hi = max(a, position), min(b, position + len(text))
                if lo < hi:
                    cuts = [(text[:lo - position], False), (text[lo - position:hi - position], True),
                            (text[hi - position:], False)]
                    cuts = [(t, styled) for t, styled in cuts if t]
                    anchor = run._r
                    for order, (t, styled) in enumerate(cuts):
                        element = anchor if order == 0 else deepcopy(run._r)
                        if order:
                            anchor.addnext(element)
                            anchor = element
                        piece = type(run)(element, run._parent)
                        piece.text = t
                        if styled:
                            rk.style_run(piece, **style)
                position += len(text)


def _marks(piece, ink, rects, opacity=1.0, rough=False):
    if rects:
        piece['print'] = list(piece.get('print', ())) + [
            dict(kind='marks', ink=ink, rects=[[round(v, 2) for v in r] for r in rects],
                 opacity=opacity, rough=rough)]


def dress(plan, pieces, variant=0):
    """Print structure on each reading face from the copy it carries."""
    objects = {ob['id']: ob for ob in plan['objects']}
    for piece in pieces:
        face = objects.get(piece.get('face'))
        if face is None or face.get('family') in ('chart', 'note'):
            continue
        members = [objects[m] for m in face.get('members', ()) if m in objects]
        texts = [ob for ob in members if ob['kind'] == 'text']
        if not texts:
            continue
        ox, oy = piece['rect'][0], piece['rect'][1]
        width, height = piece['rect'][2] - ox, piece['rect'][3] - oy
        left = min(ob['rect'][0] for ob in texts) - ox
        top = min(ob['rect'][1] for ob in texts) - oy
        rows = {}
        for ob in texts:
            match = re.search(r'visual_data\.items\.(\d+)\.|-nav-(\d+)$', ob['id'])
            if match:
                key = int(match[1] if match[1] is not None else match[2])
                box = rows.setdefault(key, [ob['rect'][1], ob['rect'][3]])
                box[0], box[1] = min(box[0], ob['rect'][1]), max(box[1], ob['rect'][3])
        numerals = [ob for ob in texts if re.search(r'-nav-\d+$', ob['id'])]
        card = face.get('family') == 'card' and not face.get('ruled')

        # Ledger lines in the gaps between the rows of a list.
        hairs = []
        ordered = sorted(rows.values())
        for (_, bottom), (next_top, _) in zip(ordered, ordered[1:]):
            if next_top - bottom >= 7 and not card:
                y = (bottom + next_top) / 2 - oy
                hairs.append([9, y - .3, width - 9, y + .3])
        _marks(piece, 'ink', hairs, .3)

        # A margin line between the numerals and their points.
        if numerals and not card and len(rows) >= 2:
            labels = [ob for ob in texts if '.label' in ob['id']]
            x = min(ob['rect'][0] for ob in labels) - ox - 9 if labels else left - 9
            _marks(piece, 'inkB', [[x, 5, x + 1.1, height - 6]], .82)

        # A column head above the copy: a short bar of spot ink on a hairline.
        if top >= 15 and not card and not rows:
            y = min(8.5, top - 8.5)
            bar = 34 if variant % 2 else 26
            _marks(piece, 'inkB', [[left, y, left + bar, y + 3.4]], .95)
            _marks(piece, 'ink', [[left + bar + 5, y + 1.3, width - 13, y + 1.95]], .34)

        # A highlighter across the words that carry the statement.
        swipes = []
        for ob in texts:
            for start, end in ob.get('swipes', ()):
                fit = ob['fit']
                for index, a, b in segments(fit['lines'], start, end):
                    line = fit['lines'][index]
                    x0 = ob['rect'][0] - ox + .5 + tm.advance(line[:a], fit['font'], fit['size'], fit['bold'])
                    x1 = ob['rect'][0] - ox + .5 + tm.advance(line[:b], fit['font'], fit['size'], fit['bold'])
                    y0 = ob['rect'][1] - oy + index * fit['pitch']
                    swipes.append([x0 - 3, y0 + fit['pitch'] * .2, x1 + 3.5, y0 + fit['pitch'] * .93])
        _marks(piece, 'inkB', swipes, .6, rough=True)
