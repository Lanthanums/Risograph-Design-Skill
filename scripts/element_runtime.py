"""Shared element geometry, output and namespaced history storage."""

import json
import os

from canvas import DECK_CANVAS
import elements as E
import layout as lay
import textmetrics as tm


def free_rects(text_rects, pad, bands=None,
               safety=None, min_w=40.0, min_h=32.0,
               limit=64, canvas=None):
    """Maximal empty rectangles on the page, in points, biggest first.

    The page is cut at every obstacle edge, so a page with a genuinely empty
    corner reports one large rectangle instead of a handful of clipped cells.
    Registration marks live 11-41pt from the edge, hence the `safety` inset.
    """
    canvas = canvas or DECK_CANVAS
    bands = bands or canvas.bands
    if safety is None:
        safety = (44.0,)*4 if canvas.artifact == "deck" else (0.0,)*4
    pad_l, pad_t, pad_r, pad_b = safety
    x0, y0 = pad_l, max(pad_t, bands[1])
    x1, y1 = canvas.width - pad_r, min(canvas.height - pad_b, bands[2])
    obstacles = [lay.inflate(r, pad) for r in text_rects]
    xs = sorted({x0, x1} | {min(max(v, x0), x1)
                            for r in obstacles for v in (r[0], r[2])})
    ys = sorted({y0, y1} | {min(max(v, y0), y1)
                            for r in obstacles for v in (r[1], r[3])})
    out = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            a, b, c, d = xs[i], ys[j], xs[i + 1], ys[j + 1]
            if c - a < min_w or d - b < min_h:
                continue
            cell = (a, b, c, d)
            if not any(lay.intersection(cell, o) for o in obstacles):
                out.append(cell)
    out.sort(key=lambda r: (lay.area(r), r[2] - r[0]), reverse=True)
    return out[:limit]


def content_obstacles(slide, canvas=None):
    """Protect existing charts, connectors and images from automatic accents."""
    canvas=canvas or DECK_CANVAS
    items=[]
    for shape in slide.shapes:
        if getattr(shape,'has_text_frame',False) and shape.text.strip():
            continue
        rect=lay.obb(shape)
        # The full-page generated print plate is an underlay, not an obstacle.
        if lay.area(rect)>=canvas.area*.98:
            continue
        # Zero-height/width connectors still occupy their visible stroke.
        if lay.line_segment(shape):
            rect=lay.inflate(rect,2)
        items.append({'rect':rect,'text':'','size':0})
    return items


def apply_plan(slide, plan, theme, media_dir, seed=0, page=1):
    """Render each planned element to a PNG and drop it on the slide."""
    from pptx.util import Pt
    os.makedirs(media_dir, exist_ok=True)
    palette = {"inkA": theme.inkA, "inkB": theme.inkB, "paper": theme.paper}
    records = []
    for i, item in enumerate(plan):
        meta = E.REGISTRY[item["name"]]
        w = max(8.0, item["rect"][2] - item["rect"][0])
        h = max(8.0, item["rect"][3] - item["rect"][1])
        rng_seed = seed * 7919 + page * 131 + i
        # rule D: group members share one ink; ungrouped pieces may alternate
        ink_swap = (i % 2 == 1) if "ink" not in item else item["ink"] == "B"
        pal = dict(palette)
        if ink_swap:
            pal["inkA"], pal["inkB"] = palette["inkB"], palette["inkA"]
        try:
            img = E.render(item["name"], pal, size=(w, h), seed=rng_seed,
                           **item.get("kw", {}))
        except Exception as exc:                       # never break a deck for decoration
            records.append({"element": item["name"], "error": str(exc)[:80]})
            continue
        path = os.path.join(media_dir, f"p{page:02d}_{i}_{item['name']}.png")
        img.save(path, optimize=True)
        pic = slide.shapes.add_picture(path, Pt(item["rect"][0]), Pt(item["rect"][1]),
                                       Pt(img.width / E.SCALE), Pt(img.height / E.SCALE))
        if item.get("rot"):
            pic.rotation = item["rot"]
        cat = meta["category"]
        tag = {"collage": "A", "doodle": "B", "geometric": "C", "texture": "TEX",
               "print": "PRINT", "typography": "TYPE", "retro_ui": "UI"}.get(cat, cat)
        if cat not in ('texture','print'):
            tag=item.get('dialect',tag)
        try:
            group='/group='+str(item['group']) if item.get('group') else ''
            pic._element.nvPicPr.cNvPr.set("name", f"el[{tag}]{item['name']}"+group)
        except Exception:
            pass
        rec = {"element": item["name"], "category": cat, "dialect":tag,"role": item["role"],
               "rect": [round(v, 1) for v in item["rect"]],
               "rotation": round(item.get("rot", 0), 1),
               "file": os.path.basename(path)}
        if item.get("placement"):
            rec["placement"] = item["placement"]
        if item.get("anchor"):
            rec["anchor"] = item["anchor"]
        if item.get("function"):
            rec["function"] = item["function"]
        if item.get("group"):
            rec["group"] = item["group"]
        for key in ('recipe','recipe_part'):
            if key in item:rec[key]=item[key]
        records.append(rec)
    return records


def history_path(skill_dir=None, artifact=None):
    # Keep the old argument for callers; it must never select a repo path.
    from state_paths import read_path
    name = f"{artifact}-history.json" if artifact else "history.json"
    return str(read_path(name))


def load_history(skill_dir=None, artifact=None):
    p = history_path(skill_dir, artifact)
    if artifact and not os.path.exists(p):
        # Migrate only matching entries from the former mixed history.
        rows = load_history(skill_dir)['decks']
        def route(row):
            return row.get('artifact', 'poster' if str(row.get('deck', '')).startswith('poster:') else 'deck')
        return {'decks': [row for row in rows if route(row) == artifact]}
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as fh:
                history = json.load(fh)
            if isinstance(history, dict) and isinstance(history.get("decks"), list):
                return history
        except Exception:
            pass
    return {"decks": []}


def append_history(skill_dir, record, keep=40, artifact=None):
    """Record the deck. Rebuilding the same deck (same title and seed) replaces
    its entry instead of adding one — otherwise a second build of the same spec
    counts its own predecessor as a "recent" deck, picks a different dialect, and
    stops being reproducible."""
    h = load_history(skill_dir, artifact)
    decks = h.setdefault("decks", [])
    key = (record.get("deck"), record.get("seed"))
    decks[:] = [d for d in decks if (d.get("deck"), d.get("seed")) != key]
    decks.append(record)
    h["decks"] = h["decks"][-keep:]
    from state_paths import write_json
    write_json(f'{artifact}-history.json' if artifact else 'history.json', h)
