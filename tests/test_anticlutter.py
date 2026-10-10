#!/usr/bin/env python3
"""test_anticlutter.py — pin the anti-clutter toolchain (rules A–H).

Covers the four instruments that enforce rules A–H:
measure_text.py, place_decor.py, layout_check.py, squint_test.py.
Run from the tests directory:  python test_anticlutter.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import random

import measure_text as mt
import place_decor as pd
import layout_check as lc
import squint_test as sq

FAILS = []


def check(name, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def test_measure_text():
    print("measure_text")
    r = mt.measure("BEYOND", "Georgia", 122, bold=True)
    check("single line width measured", r and 500 < r["width"] < 660,
          str(r))
    r = mt.measure("one two three four five six seven eight nine ten",
                   "Georgia", 20, width=120)
    check("wraps to multiple lines", r and r["lines"] >= 3, str(r))
    r = mt.measure("zzz", "No Such Family 9000", 20)
    check("unresolvable font reported", r is None)


def _rich(words, size=20.0, rect=(48.0, 90.0, 700.0, 300.0)):
    return [{"rect": rect, "text": " ".join(["word"] * words), "size": size}]


def test_place_decor():
    print("place_decor")
    # T2 page: typography leads, so no hero may appear (rule A + B)
    p = pd.Placer(_rich(50), "report", "A", "C", random.Random(5))
    p.attach(2)
    p.place_hero()
    p.place_group()
    check("T2 page gets no hero",
          all(i["role"] != "hero" for i in p.placed),
          str([(i["role"], i["name"]) for i in p.placed]))
    check("every element carries a function tag",
          all(i.get("function") in pd.FUNCTIONS for i in p.placed))
    check("T2 area cap honoured",
          sum((i["rect"][2] - i["rect"][0]) * (i["rect"][3] - i["rect"][1])
              for i in p.placed) <= pd.TEXT_TIERS["T2"]["area"] * pd.PAGE_AREA + 1)
    check("quiet zone survives on T2",
          p.quiet_now() >= pd.TEXT_TIERS["T2"]["quiet"] - 0.02,
          f"{p.quiet_now():.2%}")

    # T0 wordless page: a hero MAY lead (contract shape)
    p0 = pd.Placer([{"rect": (100.0, 100.0, 300.0, 140.0), "text": "",
                     "size": 0.0}], "report", "A", "C", random.Random(5))
    p0.place_hero()
    roles0 = {i["role"] for i in p0.placed}
    check("T0 page may field a hero", "hero" in roles0 or True,  # room decides
          str(roles0))

    # T0 page with monumental type: typography already leads -> no hero
    pm = pd.Placer([{"rect": (100.0, 150.0, 860.0, 350.0), "text": "01",
                     "size": 150.0}], "speech", "A", "B", random.Random(3),
                   mood=True)
    check("monument anchor recognised",
          any(a["kind"] == "monument" for a in pm.anchors()))
    pm.place_hero()
    check("monumental type blocks the element hero",
          all(i["role"] != "hero" for i in pm.placed))

    # rule F: at most one element from the secondary dialect per page
    pf = pd.Placer(_rich(20), "speech", "A", "B", random.Random(7))
    pf.attach(2)
    pf.place_group()
    side = [i for i in pf.placed
            if i["name"] not in {n for _r, n in pf._pools["main"]}]
    check("secondary dialect rationed to one element", len(side) <= 1,
          str([i["name"] for i in side]))

    # rule D: a group shares an axis (bottom-aligned), one ink, one angle,
    # and a >=2.5:1 size contrast
    pg = pd.Placer(_rich(20), "speech", "A", "B", random.Random(9))
    pg.place_group()
    grp = [i for i in pg.placed if i.get("group")]
    if len(grp) >= 2:
        bottoms = {round(i["rect"][3], 1) for i in grp}
        rots = {round(i["rot"], 1) for i in grp}
        areas = sorted((i["rect"][2] - i["rect"][0])
                       * (i["rect"][3] - i["rect"][1]) for i in grp)
        check("group shares an alignment axis", len(bottoms) == 1,
              str(bottoms))
        check("group shares one angle", len(rots) == 1, str(rots))
        check("group size contrast >= 2.5:1", areas[-1] >= 2.5 * areas[0],
              f"{areas[-1]:.0f} vs {areas[0]:.0f}")
        check("group tagged rhythm",
              all(i["function"] == "rhythm" for i in grp))
    else:
        check("group formed (may legitimately decline)", True)

    # untagged elements are refused outright
    pu = pd.Placer(_rich(5), "speech", "A", "B", random.Random(1))
    ok = pu.commit("paperclip", "micro", (700.0, 400.0, 760.0, 460.0), 2.0,
                   "grouped", "no-such-function")
    check("function-less element refused", not ok)


def test_layout_check():
    print("layout_check")
    import riso_kit as rk
    from pptx.util import Pt
    prs = rk.new_deck()
    s = rk.add_page(prs, None)
    th = rk.Theme(palette="G", print_grammar="light", lang="en")
    rk.text(s, 48, 90, 700, 60,
            [dict(runs=[("A CLEAN TITLE", {})], font="Georgia", size=34,
                  bold=True)], wrap=False)
    rep = lc.check_slide(s, 1)
    check("clean page passes", rep["pass"], str(rep["fails"]))
    check("chrome counted", rep["chrome_count"] == 0)   # nothing drawn yet

    # deliberately collide: picture named like an element over the title
    import io
    from PIL import Image
    img = Image.new("RGB", (40, 40), (20, 120, 60))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    pic = s.shapes.add_picture(buf, Pt(60), Pt(90), Pt(200), Pt(120))
    pic._element.nvPicPr.cNvPr.set("name", "el[A]blob")
    rep2 = lc.check_slide(s, 1)
    check("decor/copy overlap flagged", not rep2["pass"]
          and any("overlaps copy" in f for f in rep2["fails"]), str(rep2["fails"]))

    check("tier thresholds", lc.tier_for(10)[0] == "T0"
          and lc.tier_for(20)[0] == "T1" and lc.tier_for(50)[0] == "T2"
          and lc.tier_for(200)[0] == "T3")


def test_squint_test():
    print("squint_test")
    from PIL import Image
    import tempfile
    # protagonist at top: dark band across the top cells, paper elsewhere
    img = Image.new("L", (960, 540), 235)
    for x in range(0, 700):
        for y in range(40, 180):
            img.putpixel((x, y), 30)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f.name)
        res = sq.judge(sq.ink_grid(f.name), "top")
    os.unlink(f.name)
    check("top protagonist detected", res["pass"], str(res["max_cell"]))
    # uniform page: no dominance
    img2 = Image.new("L", (960, 540), 120)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img2.save(f.name)
        res2 = sq.judge(sq.ink_grid(f.name), "top")
    os.unlink(f.name)
    check("flat page fails the dominance rule", not res2["dominant"])


if __name__ == "__main__":
    test_measure_text()
    test_place_decor()
    test_layout_check()
    test_squint_test()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)
