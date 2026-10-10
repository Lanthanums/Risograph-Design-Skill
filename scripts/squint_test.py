#!/usr/bin/env python3
"""squint_test.py — the squint test, automated.

A riso page must read at arm's length: blur the render, and the protagonist
should be the loudest thing on the sheet. This script shrinks a rendered page
to ~320px wide, blurs it, divides it into a 4x3 grid, and reports the ink
load of every cell. The page passes when the cell with the most ink sits in
the expected protagonist region and carries at least 1.5x the ink of the
runner-up.

    python squint_test.py --image page-0001.png --expect top
    python squint_test.py --preview preview_dir --expect-map cover:top,statement:top

Exit code 0 = pass.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import glob
import json
import os
import sys

from PIL import Image, ImageFilter

REGIONS = {
    "top": [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1), (3, 1)],
    "centre": [(1, 1), (2, 1)],
    "left": [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)],
    "full": [(c, r) for c in range(4) for r in range(3)],
}


def ink_grid(path, cols=4, rows=3):
    """Ink load (1 - luminance) per grid cell of a blurred 320px-wide render."""
    img = Image.open(path).convert("L")
    w = 320
    img = img.resize((w, int(img.height * w / img.width)), Image.LANCZOS)
    img = img.filter(ImageFilter.GaussianBlur(3))
    cw, ch = img.width // cols, img.height // rows
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            cell = img.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
            import numpy as np
            px = np.asarray(cell, dtype=float)
            row.append(round(1 - px.mean() / 255.0, 4))
        grid.append(row)
    return grid


def judge(grid, expect="top", ratio=1.5):
    loads = sorted(((v, c, r) for r, row in enumerate(grid)
                    for c, v in enumerate(row)), reverse=True)
    top = loads[0]
    # a wide protagonist (a title band, a hero block) legitimately spills into
    # the cells next to its loudest cell; those neighbours are part of the
    # protagonist, not competition. Competition is the loudest cell NOT
    # adjacent to the protagonist cluster.
    cluster = {(top[1], top[2])}
    frontier = [(top[1], top[2])]
    by_cell = {(c, r): v for v, c, r in loads}
    while frontier:
        c, r = frontier.pop()
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nc, nr = c + dc, r + dr
            if (nc, nr) in by_cell and (nc, nr) not in cluster \
                    and by_cell[(nc, nr)] >= 0.6 * top[0]:
                cluster.add((nc, nr))
                frontier.append((nc, nr))
    rivals = [v for v, c, r in loads[1:] if (c, r) not in cluster]
    second = max(rivals) if rivals else 0.0
    region = REGIONS.get(expect, REGIONS["full"])
    in_region = (top[1], top[2]) in region
    # No protagonist at all: a uniform sheet would have its loudest cell barely
    # above the page average, so there is nothing for the eye to land on. Screen
    # against that with the loudest-cell-to-mean ratio rather than by counting
    # cluster cells — a legitimately busy page (a wide data page, a venn, a
    # two-column table) can spread ink through 11 of 12 cells and still have a
    # measurable protagonist, whereas a flat sheet sits near 1.0. A page that
    # clears this screen still has to win the dominance ratio below.
    vals = [v for row in grid for v in row]
    mean = sum(vals) / len(vals) if vals else 0.0
    uniform = mean <= 0 or top[0] < 1.2 * mean
    dominant = top[0] >= ratio * max(second, 1e-6) and not uniform
    return {
        "grid": grid, "max_cell": [top[1], top[2]], "max_ink": top[0],
        "protagonist_cells": sorted(cluster),
        "runner_up_ink": round(second, 4),
        "page_mean_ink": round(mean, 4), "uniform": uniform,
        "expect": expect, "in_region": in_region, "dominant": dominant,
        "pass": in_region and dominant,
    }


def main():
    ap = argparse.ArgumentParser(description="riso-slides squint test")
    ap.add_argument("--image")
    ap.add_argument("--preview", help="directory of page-*.png renders")
    ap.add_argument("--expect", default="top",
                    help="top | centre | left | full")
    ap.add_argument("--expect-map", help="per-archetype map, e.g. cover:top")
    ap.add_argument("--style", help="style.json for reversed-page exemption")
    ap.add_argument("--ratio", type=float, default=1.5)
    ap.add_argument("--json")
    args = ap.parse_args()

    results = []
    # Reversed (full-flood) pages are exempt: the whole sheet is inked by
    # design, the protagonist reads as negative space, and "dominant ink cell"
    # is meaningless. reversed_pages come from the deck's style.json, looked up
    # next to the preview dir unless --style says otherwise.
    reversed_pages = set()
    style_path = args.style
    if not style_path and args.preview:
        cand = os.path.join(os.path.dirname(os.path.abspath(args.preview)),
                            "style.json")
        if os.path.exists(cand):
            style_path = cand
    if style_path and os.path.exists(style_path):
        st = json.load(open(style_path, encoding="utf-8"))
        reversed_pages = set(st.get("reversed_pages", []))
        # manual curtain-call pages (poster + thank-you diptych) are built
        # outside the placer and legitimately carry TWO focal points; the
        # single-protagonist assumption does not apply to them either
        for k, v in st.items():
            if isinstance(v, dict) and v.get("type") == "manual_append" \
                    and k.startswith("page"):
                try:
                    reversed_pages.add(int(k[4:k.index("_")]))
                except (ValueError, IndexError):
                    pass
    # per-archetype protagonist regions: an ask page's call-to-action band is
    # SUPPOSED to be the loudest ink, and it lives low — "top" would fail it
    expect_map = {}
    for chunk in (args.expect_map or "").split(","):
        k, _, v = chunk.partition(":")
        if k and v:
            expect_map[k.strip()] = v.strip()
    archetypes = []
    if style_path and os.path.exists(style_path):
        archetypes = [p.get("archetype") for p in st.get("pages", [])]
    if args.image:
        results.append((args.image, judge(ink_grid(args.image), args.expect,
                                          args.ratio)))
    elif args.preview:
        for p in sorted(glob.glob(os.path.join(args.preview, "page-*.png"))):
            n = int(os.path.basename(p)[5:9])
            if n in reversed_pages:
                print(f"{os.path.basename(p)} [SKIP] reversed / manual page — "
                      f"squint protagonist rule N/A")
                continue
            expect = args.expect
            if n - 1 < len(archetypes):
                expect = expect_map.get(archetypes[n - 1], expect)
            if expect == "skip":
                # Evenly-tiled diagram pages (e.g. multi-column timelines)
                # have no single protagonist by design; squint N/A.
                print(f"{os.path.basename(p)} [SKIP] archetype exempt — "
                      f"evenly-tiled layout, no single protagonist")
                continue
            results.append((p, judge(ink_grid(p), expect, args.ratio)))
    ok = True
    for path, res in results:
        ok &= res["pass"]
        mark = "PASS" if res["pass"] else "FAIL"
        print(f"{os.path.basename(path)} [{mark}] max={res['max_cell']} "
              f"ink={res['max_ink']:.3f} rival={res['runner_up_ink']:.3f} "
              f"expect={res['expect']}")
    if args.json:
        json.dump({os.path.basename(p): r for p, r in results},
                  open(args.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
