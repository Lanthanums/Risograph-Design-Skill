#!/usr/bin/env python3
"""deck_ink — bounded, asymmetric misregistration plates for deck display type.

v4.3 replacement for the shared-diagonal underprint in ``riso_kit.stack`` /
``riso_kit.hero``.  This module owns only the *back* and *mid* plates.  The
main writer paints the *front* layer separately at (0, 0) with
``theme.display_ink`` (or an explicit ``paint`` override), so the front stays
crisp and the front colour never moves.

Contract
--------
``plates(theme, size, style='spot') -> tuple[(dx, dy, '#RRGGBB'), ...]``

* Ordered first-to-last, i.e. in paint order: back, then mid.
* Offsets are points; every ``abs(dx)`` / ``abs(dy)`` is within 0..8 pt for
  30-180 pt type (magnitude <= 8 pt as well).
* ``size < 30`` -> ``()`` (no underprint below 30 pt).
* ``style='off'`` -> ``()``; ``style='quiet'`` is the same two-plate grammar
  at roughly 55% throw with softer ink; ``style='spot'`` is the deck default.
* Unknown styles and non-finite sizes raise ``ValueError``.

Colour policy
-------------
Paper page: the back plate is a chromatic tint of the palette's identity ink
(``theme.inkA``).  The mid plate takes the first *other* palette ink that keeps
real chroma at a pale tint — normally ``inkB``, otherwise a warm/cool accent,
otherwise a lighter tint of ``inkA``.  ``title_mid`` / ``title_back`` are
deliberately not used as-is: on monochrome palettes (e.g. palette G, whose
``inkB`` is neutral) they blend to a low-chroma warm grey, which is exactly the
grey drop shadow this module replaces.  Every returned colour must clear a
minimum chroma and a minimum luminance distance from the sheet.

Reversed page (``theme.on_red``): the flood is ``inkA``, so both plates are
tints of the dark ink over that flood; they stay red-shifted rather than grey.
"""
from __future__ import annotations

import math

__all__ = ["plates", "STYLES", "MIN_PT", "MAX_PT", "MAX_OFFSET_PT"]

STYLES = ("spot", "quiet", "off")
MIN_PT = 30.0
MAX_PT = 180.0
MAX_OFFSET_PT = 8.0

# Per-plate drift directions.  Neither vector has dx == dy, the two layers do
# not share a diagonal, and they are close to perpendicular: a press drifting
# its plates independently, not one grey shadow marching down-right.
_BACK_DIR = (-0.78, -0.63)   # back plate slips up-left
_MID_DIR = (0.63, -0.78)     # mid plate slips up-right, on a different slope

# (minimum, maximum) throw in points, interpolated over 30..180 pt.
_THROW = {
    "spot": {"back": (2.2, 7.2), "mid": (1.5, 4.7)},
    "quiet": {"back": (1.4, 4.1), "mid": (0.9, 2.7)},
}

# (coverage of the ink over the sheet, minimum luminance delta).
_INK = {
    "spot": {"back": (0.50, 0.24), "mid": (0.26, 0.075)},
    "quiet": {"back": (0.32, 0.12), "mid": (0.16, 0.045)},
}

_STEP = 0.02
_CAP_BACK = 0.70
_CAP_MID = 0.42
_MIN_CHROMA_BACK = 20.0     # 0..255 max-minus-min; paper itself is ~20
_MIN_CHROMA_MID = 26.0      # a tint of a neutral ink only inherits paper's grey
_MIN_MID_DL = 0.03          # keep the two plates from collapsing into one tone


# ------------------------------------------------------------------ helpers
def _tok(theme, name, default=None):
    """Read a theme token from an object or a mapping."""
    if isinstance(theme, dict):
        return theme.get(name, default)
    return getattr(theme, name, default)


def _rgb(value):
    """'#rrggbb' (or a 3-tuple) -> (r, g, b) floats 0..255."""
    if isinstance(value, str):
        text = value.lstrip("#")
        if len(text) == 3:
            text = "".join(c * 2 for c in text)
        if len(text) != 6:
            raise ValueError(f"colour must be #rrggbb, got {value!r}")
        return tuple(float(int(text[i:i + 2], 16)) for i in (0, 2, 4))
    return tuple(float(c) for c in value[:3])


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(int(round(max(0.0, min(255.0, c)))) for c in rgb)


def _lum(rgb):
    r, g, b = (c / 255.0 for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _chroma(rgb):
    return max(rgb) - min(rgb)


def _mix(ground, ink, coverage):
    """Ink printed on `ground` at `coverage` (0 = ground, 1 = ink)."""
    return tuple(i * coverage + g * (1.0 - coverage) for i, g in zip(ink, ground))


def _tint(ground, ink, coverage, min_dl, min_chroma, cap):
    """A tint that clears both the luminance and chroma floors, or None.

    Coverage rises only as far as the cap, so a neutral ink cannot be dragged
    all the way to black just to fake chroma.
    """
    steps = int(round((cap - coverage) / _STEP))
    for i in range(steps + 1):
        cov = min(cap, coverage + i * _STEP)
        color = _mix(ground, ink, cov)
        if abs(_lum(color) - _lum(ground)) >= min_dl and _chroma(color) >= min_chroma:
            return color
    return None


def _distinct(color, other):
    return (abs(_lum(color) - _lum(other)) >= _MIN_MID_DL
            or abs(_chroma(color) - _chroma(other)) >= 24.0)


def _ordered_candidates(theme):
    """Palette inks for the mid plate, most hue-distinct first."""
    return [_tok(theme, "inkB", "#000000"),
            _tok(theme, "accent2", "#000000"),
            _tok(theme, "accent1", "#000000"),
            _tok(theme, "inkA", "#000000")]


def _colours(theme, style):
    """(back, mid) RGB colours for this page, contrast-tuned against the sheet."""
    on_red = bool(_tok(theme, "on_red", False))
    spec = _INK[style]
    if on_red:
        ground = _rgb(_tok(theme, "inkA", "#D7261E"))
        ink = _rgb(_tok(theme, "ink", "#1E1E1E"))
        # A reversed page is flooded with inkA; density changes read as colour,
        # not as neutral grey, because the ground is already chromatic.  Quiet
        # keeps a lower contrast floor so it stays visibly lighter than spot.
        floor = {"spot": (0.10, 0.045), "quiet": (0.06, 0.025)}[style]
        back = _tint(ground, ink, spec["back"][0], floor[0], 16.0, _CAP_BACK)
        mid = _tint(ground, ink, spec["mid"][0], floor[1], 14.0, _CAP_MID)
        if back is None:
            back = _mix(ground, ink, _CAP_BACK)
        if mid is None or not _distinct(mid, back):
            mid = _mix(ground, ink, spec["mid"][0] * 0.7)
        return back, mid

    ground = _rgb(_tok(theme, "paper", "#F2EBDA"))
    back_ink = _rgb(_tok(theme, "inkA", "#1E1E1E"))
    back = _tint(ground, back_ink, spec["back"][0], spec["back"][1],
                 _MIN_CHROMA_BACK, _CAP_BACK)
    if back is None:
        back = _mix(ground, back_ink, _CAP_BACK)

    mid = None
    for token in _ordered_candidates(theme):
        color = _tint(ground, _rgb(token), spec["mid"][0], spec["mid"][1],
                      _MIN_CHROMA_MID, _CAP_MID)
        if color is not None and _distinct(color, back):
            mid = color
            break
    if mid is None:
        # Last resort: a lighter tint of the identity ink.  Still chromatic.
        mid = _mix(ground, back_ink, max(0.10, spec["mid"][0] * 0.7))
    return back, mid


def _hit(direction, magnitude):
    """One bounded offset: per-component clamp, rounded for stable output."""
    def bound(value):
        return round(max(-MAX_OFFSET_PT + 0.1,
                         min(MAX_OFFSET_PT - 0.1, value)), 2)
    dx = bound(direction[0] * magnitude)
    dy = bound(direction[1] * magnitude)
    if dx == 0.0 and dy == 0.0:
        dx = round(direction[0] * 1.5, 2)
        dy = round(direction[1] * 1.5, 2)
    return dx, dy


# --------------------------------------------------------------------- API
def plates(theme, size, style="spot"):
    """Return the (dx, dy, colour) underprint plates, back first then mid.

    ``theme`` is a riso_kit Theme (or any object/dict exposing ``paper``,
    ``inkA``, ``inkB``, ``ink``, ``accent1``, ``accent2``, ``display_ink`` and
    ``on_red``).  ``size`` is the display type size in points.  The caller
    paints the front layer itself at (0, 0).
    """
    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}, got {style!r}")
    try:
        size = float(size)
    except (TypeError, ValueError):
        raise ValueError(f"size must be a number of points, got {size!r}") from None
    if not math.isfinite(size):
        raise ValueError(f"size must be finite, got {size!r}")
    if style == "off" or size < MIN_PT:
        return ()

    span = MAX_PT - MIN_PT
    t = (min(size, MAX_PT) - MIN_PT) / span
    back, mid = _colours(theme, style)
    out = []
    for key, direction, color in (("back", _BACK_DIR, back),
                                  ("mid", _MID_DIR, mid)):
        low, high = _THROW[style][key]
        magnitude = min(MAX_OFFSET_PT, low + (high - low) * t)
        dx, dy = _hit(direction, magnitude)
        out.append((dx, dy, _hex(color)))
    return tuple(out)
