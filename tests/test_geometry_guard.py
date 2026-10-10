#!/usr/bin/env python3
"""test_geometry_guard.py — prove the geometry checks actually catch the three
defects that showed up in a produced deck.

A checker that passes on a good deck proves nothing; it has to fail on a broken
one. Each case below takes the same clean page and injects one defect:

  1. text runs past the canvas edge
  2. a caption is half-covered by a sticker
  3. a highlight bar misses the word it is supposed to mark
  4. a decorative element is dropped on top of the text protection zone
  5. two unrelated text blocks overlap

Run: python tests/test_geometry_guard.py
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)
for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pptx.util import Pt          # noqa: E402
import riso_kit as rk             # noqa: E402
import qa as qamod                # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def qa_args():
    return argparse.Namespace(
        edge_tol=1.5, text_protection=9.0, media=None,
        max_elements=14, max_element_area=0.35, max_hero_area=0.60)


def run_geometry(slide):
    rep = qamod.Report()
    qamod.geometry_checks(rep, slide, 1, qa_args())
    return [i for i in rep.items if not i["ok"]], [i["check"] for i in rep.items]


def clean_page():
    th = rk.Theme(palette="G", print_grammar="light", lang="zh")
    prs = rk.new_deck()
    slide = rk.add_page(prs, None)
    rk.page_title(slide, 48, 92, "版面自检", th, size=34)
    body = rk.body(slide, 48, 200, 500, 30,
                   ["这一行是正文，用来验证文字保护区。"], th, size=20)
    bar = rk.rect(slide, 48, 320, 60, 40, fill=th.inkA)      # a sticker
    rk.sticker(slide, 700, 300, 170, 110, "OK", th, size=34)
    return th, prs, slide, body, bar


def main():
    print("geometry guard: the checker must fail on a broken page\n")
    th, prs, slide, body, bar = clean_page()
    fails, checks = run_geometry(slide)
    check("clean page passes", not fails,
          "; ".join(f"{f['check']}: {f['detail']}" for f in fails))

    # 1. text past the canvas edge
    th, prs, slide, body, bar = clean_page()
    rk.text(slide, 700, 200, 400, 40,
            [dict(runs=[("A caption that is far too long to fit", {})],
                  font=th.f_body, size=20, ls=1.2)], wrap=False)
    fails, _ = run_geometry(slide)
    check("catches text running off the canvas",
          any(f["check"] == "text stays on the canvas" for f in fails),
          "; ".join(f["detail"] for f in fails if f["check"] == "text stays on the canvas"))

    # 2. a sticker half-covering a caption
    th, prs, slide, body, bar = clean_page()
    rk.rect(slide, 120, 196, 200, 60, fill=th.inkB)          # overlaps body at y=200
    fails, _ = run_geometry(slide)
    check("catches a caption clipped by a solid shape",
          any(f["check"] == "text does not clip decorations" for f in fails),
          "; ".join(f["detail"] for f in fails
                    if f["check"] == "text does not clip decorations"))

    # 3. highlight bar offset from its word
    th, prs, slide, body, bar = clean_page()
    shape = rk.text(slide, 48, 420, 600, 30,
                    [dict(runs=[("the quick brown fox", {})], font=th.f_body,
                          size=22, ls=1.2)], wrap=False)
    rk.rect(slide, 150, 404, 60, 26, fill=th.accent1)        # wrong x and y
    fails, _ = run_geometry(slide)
    caught = [f["check"] for f in fails
              if f["check"].startswith("highlight covers")]
    check("catches a highlight bar that misses its word", bool(caught),
          "; ".join(f["detail"] for f in fails
                    if f["check"].startswith("highlight")))

    # 3b. the measured helper must place it correctly
    th, prs, slide, body, bar = clean_page()
    shape = rk.text(slide, 48, 420, 600, 30,
                    [dict(runs=[("the quick brown fox", {})], font=th.f_body,
                          size=22, ls=1.2)], wrap=False)
    rk.highlight_word(slide, shape, "the quick brown fox", "brown", th, ls=1.2)
    fails, _ = run_geometry(slide)
    check("measured highlight passes the same check",
          not [f for f in fails if f["check"].startswith("highlight")],
          "; ".join(f["detail"] for f in fails
                    if f["check"].startswith("highlight")))

    # 4. decorative picture dropped on the text protection zone
    th, prs, slide, body, bar = clean_page()
    import tempfile
    from PIL import Image
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "el.png")
    Image.new("RGBA", (160, 160), (215, 38, 30, 255)).save(p)
    slide.shapes.add_picture(p, Pt(150), Pt(196), Pt(80), Pt(80))
    fails, _ = run_geometry(slide)
    check("catches an element invading the text protection zone",
          any(f["check"] == "elements respect the text protection zone"
              for f in fails),
          "; ".join(f["detail"] for f in fails
                    if f["check"] == "elements respect the text protection zone"))

    # 5. two unrelated text blocks on top of each other
    th, prs, slide, body, bar = clean_page()
    rk.text(slide, 60, 205, 500, 30,
            [dict(runs=[("另一段互不相关的文字", {})], font=th.f_body, size=20,
                  ls=1.2)], wrap=False)
    fails, _ = run_geometry(slide)
    check("catches two text blocks overlapping",
          any(f["check"] == "text blocks do not overlap" for f in fails),
          "; ".join(f["detail"] for f in fails
                    if f["check"] == "text blocks do not overlap"))

    # 6. the misregistration stack must NOT be reported as a collision
    th, prs, slide, body, bar = clean_page()
    rk.stack(slide, 48, 420, 700, 90,
             [("MISREGISTERED", th.f_display, 64, False)], th)
    fails, _ = run_geometry(slide)
    check("three-layer title is not reported as a collision",
          not [f for f in fails if f["check"] == "text blocks do not overlap"],
          "; ".join(f["detail"] for f in fails
                    if f["check"] == "text blocks do not overlap"))

    bad = [r for r in results if not r[1]]
    print(f"\n{len(bad)} failure(s) out of {len(results)} check(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
