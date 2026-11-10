"""Fit English deck headlines before the editable front and ink plates draw."""

import math

import textmetrics as tm
import typefit as tf
from riso_kit import NO_WRAP

from deck_title_wrap import choose_title_lines, has_weak_break


def fit(value, family, size, width, height, *, minimum, ls=1.08,
        offset=0, keep_phrases=(), role='deck title'):
    value = (tf.source_text(value).replace('\r\n', '\n').replace('\r', '\n')
             .replace('\u2028', '\n').replace('\u2029', '\n'))
    if not all(math.isfinite(v) and v > 0 for v in (size, minimum, width, height)) or minimum > size:
        raise ValueError(f'{role}: invalid title size or measured region')
    candidates = [size - i * .5 for i in range(int((size - minimum) / .5) + 1)]
    if candidates[-1] > minimum:
        candidates.append(minimum)
    explicit = '\n' in value
    fallback = None
    for max_lines in (len(value.split('\n')),) if explicit else (2, 3, 4):
        for chosen in (candidates if max_lines <= 2 or explicit else [minimum]):
            shadow = float(offset(chosen) if callable(offset) else offset)
            available = (width - shadow - NO_WRAP['pad_pt']) / NO_WRAP['slack']
            pitch = tm.line_height(family, chosen, True, ls)
            limit = min(max_lines, int((height - shadow + 1e-6) // pitch))
            if limit < 1 or available <= 0:
                continue
            measure = lambda s: tm.advance(s, family, chosen, True)
            lines = choose_title_lines(value, limit, measure, available, keep_phrases)
            if lines:
                result = tf.Fit(value, tuple(lines), family, chosen, True, ls, 0,
                                max(map(measure, lines)), len(lines) * pitch + shadow, pitch, shadow)
                if explicit or not has_weak_break(lines):
                    return result
                if fallback is None:
                    fallback = result
    if fallback is not None:
        return fallback
    raise ValueError(f'{role}: cannot fit intact headline and planned breaks at {minimum:g}pt '
                     f'in {width:.0f} × {height:.0f}pt; widen the title band, move supporting copy, '
                     'or revise the assertion when the brief permits')
