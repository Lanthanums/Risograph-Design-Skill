"""Deterministic, deck-only decorative print-mark placement."""

from hashlib import sha256
import json
import math


_KINDS = ("register_tick", "dot_screen", "plate_swatch", "folio_notch")
_ANCHORS = (
    "top-left", "top-center", "top-right", "mid-right",
    "bottom-right", "bottom-center", "bottom-left", "mid-left",
)
_ROLE_ANCHORS = {
    "cover": ("top-right", "bottom-left", "bottom-right", "mid-left"),
    "quote": ("top-left", "bottom-right", "top-right", "bottom-left"),
    "section": ("top-right", "mid-left", "bottom-right", "bottom-left"),
    "closing": ("bottom-right", "top-left", "top-right", "bottom-left"),
    "content": ("bottom-right", "top-right", "bottom-left", "mid-right"),
}


def _rect(value):
    if isinstance(value, dict):
        value = value.get("rect")
    try:
        x0, y0, x1, y1 = (float(v) for v in value)
    except (TypeError, ValueError):
        return None
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x1 <= x0 or y1 <= y0:
        return None
    return [x0, y0, x1, y1]


def _role(page):
    raw = "content"
    if isinstance(page, dict):
        raw = next((page[k] for k in ("role", "kind", "layout", "type")
                    if isinstance(page.get(k), str)), raw)
    elif isinstance(page, str):
        raw = page
    raw = raw.lower()
    if any(word in raw for word in ("cover", "title")):
        return "cover"
    if any(word in raw for word in ("quote", "testimonial")):
        return "quote"
    if any(word in raw for word in ("section", "divider", "chapter")):
        return "section"
    if any(word in raw for word in ("closing", "end", "back")):
        return "closing"
    return "content"


def _seed(page, role):
    values = []
    if isinstance(page, dict):
        for key in ("title", "subtitle", "heading", "quote", "text", "body",
                    "content", "semantic", "topic", "id", "index", "number"):
            if key in page:
                values.append(json.dumps(page[key], ensure_ascii=False, sort_keys=True, default=str))
    else:
        values.append(str(page))
    digest = sha256((role + "|" + "|".join(values)).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _target(role, density):
    density = str(density or "balanced").lower()
    level = {"quiet": 0, "balanced": 1, "rich": 2}.get(density, 1)
    if role in ("cover", "quote"):
        return (2, 2, 3)[level]
    return (1, 2, 3)[level]


def _size(kind, width, height):
    fractions = {
        "register_tick": (0.036, 0.048),
        "dot_screen": (0.090, 0.061),
        "plate_swatch": (0.077, 0.042),
        "folio_notch": (0.055, 0.018),
    }
    fx, fy = fractions[kind]
    return width * fx, height * fy


def _at_anchor(anchor, size, safe):
    width, height = size
    sx0, sy0, sx1, sy1 = safe
    mx, my = (sx1 - sx0) * 0.018, (sy1 - sy0) * 0.018
    if "left" in anchor:
        x0 = sx0 + mx
    elif "right" in anchor:
        x0 = sx1 - mx - width
    else:
        x0 = (sx0 + sx1 - width) / 2
    if "top" in anchor:
        y0 = sy0 + my
    elif "bottom" in anchor:
        y0 = sy1 - my - height
    else:
        y0 = (sy0 + sy1 - height) / 2
    return [x0, y0, x0 + width, y0 + height]


def _overlaps(a, b, gap=0.0):
    return (a[0] < b[2] + gap and a[2] > b[0] - gap
            and a[1] < b[3] + gap and a[3] > b[1] - gap)


def _clearance(rect, obstacles, safe):
    if not obstacles:
        return 1.0
    diagonal = math.hypot(safe[2] - safe[0], safe[3] - safe[1])
    distances = []
    for other in obstacles:
        dx = max(other[0] - rect[2], rect[0] - other[2], 0.0)
        dy = max(other[1] - rect[3], rect[1] - other[3], 0.0)
        distances.append(math.hypot(dx, dy) / diagonal)
    return min(distances)


def plan_impressions(page, occupied, safe, density):
    """Return up to three non-overlapping print-mark groups inside ``safe``.

    ``page`` may be a mapping or role string. Occupied and safe rectangles use
    ``[x0, y0, x1, y1]`` canvas coordinates. No rendering or I/O is performed.
    """
    safe = _rect(safe)
    if safe is None:
        return []
    obstacles = [rect for rect in (_rect(item) for item in (occupied or [])) if rect]
    role = _role(page)
    seed = _seed(page, role)
    width, height = safe[2] - safe[0], safe[3] - safe[1]
    gap = min(width, height) * 0.006
    preferred = _ROLE_ANCHORS[role]
    anchors = preferred + tuple(a for a in _ANCHORS if a not in preferred)
    kinds = _KINDS[seed % len(_KINDS):] + _KINDS[:seed % len(_KINDS)]
    if isinstance(page, dict) and (page.get('paper_collage_placed') or
                                  page.get('editorial') and page.get('art_direction', {}).get('quote_screen', True)):
        kinds = tuple(kind for kind in kinds if kind != 'dot_screen')
    selected = []
    for group in range(_target(role, density)):
        candidates = []
        for kind_index, kind in enumerate(kinds):
            if any(item["kind"] == kind for item in selected):
                continue
            for anchor_index, anchor in enumerate(anchors):
                if any(item["anchor"] == anchor for item in selected):
                    continue
                rect = _at_anchor(anchor, _size(kind, width, height), safe)
                if any(_overlaps(rect, other, gap) for other in obstacles + [i["rect"] for i in selected]):
                    continue
                tie = ((seed >> ((group * 17 + kind_index * 5 + anchor_index) % 61)) & 31) / 31
                score = _clearance(rect, obstacles, safe) * 4 + tie * 0.2
                score -= anchor_index * 0.06 + kind_index * 0.01
                candidates.append((score, kind, anchor, rect))
        if not candidates:
            break
        _, kind, anchor, rect = max(candidates, key=lambda item: item[0])
        selected.append({"kind": kind, "rect": [round(v, 3) for v in rect],
                         "anchor": anchor, "role": role})
    return selected
