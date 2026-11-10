"""Measured takeaway rows with a common reading edge and a quiet gutter."""


def use_cards(items, width, order, list_layout, paper_layout):
    if width < 680 or not 2 <= len(items) <= 4 or paper_layout == 'single':
        return False
    if paper_layout == 'staggered':
        return True
    long_points = sum(len(item.get('text') or item['label']) >= 44 for item in items)
    return len(items) >= 3 and long_points >= 2 and order != 'ordered' and list_layout == 'auto'


def render_cards(plan, items, region, body, module, val, order, cut_paper=False):
    """Place cards left, right, left, right while keeping source and z order."""
    from deck_paper_collage import add_panel

    left, top, width = region
    gap = 26
    lane = (width - gap) / 2
    next_y = [top, top + (28 if cut_paper else 10)]
    previous_top = top - 10
    cards = []
    for index, item in enumerate(items):
        column = index % 2
        inset = (0, 6, 11, 0)[index]
        right_trim = (8, 0, 0, 10)[index]
        x = left + column * (lane + gap) + inset
        right = left + column * (lane + gap) + lane - right_trim
        if cut_paper:
            x = left + width * (0.012, .577, .067, .532)[index]
            right = left + width * (.553, .992, .508, .964)[index]
        y = max(next_y[column], previous_top + (19 if cut_paper and index else 10))
        previous_top = y
        start = len(plan['objects'])
        row = f'visual_data.items.{index}'
        text_x = x + (40 if order == 'ordered' else 19)
        text_width = right - text_x - 21
        cue_y = y + 12
        if order == 'ordered':
            val(f'nav-{index}', f'{index + 1:02d}', x + 15, cue_y + 2, 23,
                12, True, 'navigation')
        detail = item.get('text')
        cue = val(row + '.label', item['label'], text_x, cue_y, text_width,
                  min(25, body + 3) if detail else body, bool(detail), tidy_rag=True)
        if detail:
            val(row + '.text', detail, text_x, cue['rect'][3] + 3, text_width, tidy_rag=True)
        members = plan['objects'][start:]
        bottom = max(ob['rect'][3] for ob in members)
        style = (('anchor', 'newsclip', 'tabbed', 'proof') if cut_paper else
                 ('torn', 'cut', 'tab', 'torn'))[index]
        panel = add_panel(plan, start, f'{module}-item-{index + 1}',
                          [x, y, right, bottom], members, style)
        panel.update(module=module, item=index + 1)
        cards.append(panel)
        next_y[column] = panel['rect'][3] + (12 if cut_paper else 10)
    return max(card['rect'][3] for card in cards), cards


def render_items(items, x, y, width, body, ink, mid, val, path, order, layout):
    gutter = 35 if order == 'ordered' else 22
    # Keep text at a usable measure on wide slides; narrow columns already
    # control the measure.
    measure = min(width - gutter, body * 31)
    xx = x + gutter
    long_details = sum(len(item.get('text') or '') >= 45 for item in items)
    paired = width >= 610 and (layout == 'side-by-side' or
                              (layout == 'auto' and len(items) >= 4 and long_details >= 3))
    cue_width = min(195, body * 9)
    detail_x = xx + cue_width + 18
    detail_width = min(width - (detail_x - x), body * 28)
    for j, item in enumerate(items):
        start = y
        prefix = f'visual_data.items.{j}'
        detail = item.get('text')
        size = body + (2 if paired else min(5, body * .22)) if detail else body
        if order == 'ordered':
            val(f'nav-{j}', f'{j + 1:02d}', x, start + 1, gutter - 5, 13, True, 'navigation')
        label = val(prefix + '.label', item['label'], xx, y,
                    cue_width if paired and detail else measure, size, bool(detail), tidy_rag=True)
        center = start + size * .53
        if order != 'ordered':
            mark = path(f'{mid}-list-mark-{j}', [[[x + 1, center], [x + 8, center]]],
                        ink['main'][1], role='structure', anchor=label['id'])
            mark['line_width'] = 2.2
        y = label['rect'][3]
        if detail:
            detail_fit = val(prefix + '.text', detail, detail_x if paired else xx,
                             start + 1 if paired else y + 2,
                             detail_width if paired else measure, tidy_rag=True)
            y = max(y, detail_fit['rect'][3])
        # Gaps between points are wider than the cue/detail gap. Break rules
        # are omitted, so the row group is defined by type and proximity.
        y += min(17, body * .60) if j < len(items) - 1 else 8
    return y
