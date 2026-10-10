#!/usr/bin/env python3
"""measure_text.py — real font measurement, as a command-line tool.

Everything geometric in this skill is decided from measured ink, never from
estimates (anti-clutter rule C1/G). This is the CLI front end of
textmetrics.py so the agent can measure a line before placing anything:

    python measure_text.py --text "BEYOND" --font Georgia --size 122 --bold
    python measure_text.py --text "Why AI will never ..." --font "Noto Serif SC" \
        --size 24 --width 700            # wrapped: reports lines + height
    python measure_text.py --text "612" --font Georgia --size 148 \
        --fit 700                        # largest size that fits 700pt

Output: one JSON object {"width", "height", "lines", "size", "font_file"}.
Exit code 2 = the requested family could not be resolved (substitution risk).
"""
import argparse
import json
import os
import sys
sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textmetrics as tm


def measure(text, family, size, width=None, bold=False, spc=0.0, ls=1.2):
    """Measured extent of `text`. With `width`, wraps greedily and reports
    line count and stack height; without it, reports the single-line advance."""
    f = tm.font(family, size, bold)
    if f is None:
        return None
    asc, desc = f.getmetrics()
    line_h = (asc + desc) * ls
    if not width:
        w = tm.advance(text, family, size, bold, spc)
        return {"width": round(w, 1), "height": round(line_h, 1), "lines": 1,
                "size": size}
    from typefit import lines_of
    wrapped = lines_of(text, family, size, width, bold, spc)
    max_w = max(tm.advance(t,family,size,bold,spc) for t in wrapped)
    return {"width": round(max_w,1), "height": round(len(wrapped)*line_h,1),
            "lines": len(wrapped), "line_text": wrapped, "size": size}


def main():
    ap = argparse.ArgumentParser(description="riso-slides text measurement")
    ap.add_argument("--text", required=True)
    ap.add_argument("--font", default="Georgia")
    ap.add_argument("--size", type=float, default=20)
    ap.add_argument("--bold", action="store_true")
    ap.add_argument("--width", type=float, help="wrap width in pt")
    ap.add_argument("--fit", type=float, help="largest size fitting this width")
    ap.add_argument("--spc", type=float, default=0.0)
    ap.add_argument("--ls", type=float, default=1.2)
    args = ap.parse_args()

    resolved = tm.resolve(args.font, args.bold)
    if args.fit:
        size = tm.fit_size(args.text, args.font, args.size, args.fit,
                           args.bold, args.spc)
        out = measure(args.text, args.font, size, None, args.bold, args.spc,
                      args.ls)
        if out:
            out["fit_into"] = args.fit
    else:
        out = measure(args.text, args.font, args.size, args.width, args.bold,
                      args.spc, args.ls)
    if out is None:
        print(json.dumps({"error": f"font not resolvable: {args.font}",
                          "font_file": None}))
        return 2
    out["font_file"] = resolved
    out["substituted"] = resolved is None
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
