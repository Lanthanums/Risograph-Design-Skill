"""Deck-only rules for the shared rendered QA."""


def sheet_cell(background, box, px):
    """Ink under copy that sits on a paper sheet, measured against that sheet.

    A clean sheet reads as clean and a dot screen under copy still fails. A
    faint ruling is not a dot field, and turned copy keeps a few points of
    tolerance at the edge of its box. Returns None for a box too small to judge.
    """
    import make_textures as mt

    x0, y0, x1, y1 = box
    trim = int(3 * px)
    if x1 - x0 <= 4 * trim or y1 - y0 <= 3 * trim:
        return None
    return mt.ink_mask(background.crop((x0 + trim, y0 + trim, x1 - trim, y1 - trim)), threshold=64)
