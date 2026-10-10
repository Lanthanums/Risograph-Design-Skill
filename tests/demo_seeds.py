#!/usr/bin/env python3
"""demo_seeds.py — the acceptance test the brief asks for.

Same Chinese product-report content, three different seeds, four pages each:
the decks must differ in dialect and in element vocabulary, every page must meet
the element budget, and the text must stay readable and editable.
"""
import json
import os
import subprocess
import sys
import argparse
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
PY = sys.executable
OUT = os.path.join(tempfile.gettempdir(), "riso_deck_seed_demo")

PAGES = [
    {"archetype": "cover",
     "question": ["Q：", "这一季度，真正把用户留下来的是什么？"],
     "title": "云栖", "title_en": "YUNQI",
     "thesis": [["留存升到 46%", {"bold": True}], ["，付费转化同步上行。", {}]],
     "highlight": "留存升到 46%", "sticker": "Q3", "star": True,
     "bullets": ["经营数据", "用户之声", "竞品对比", "Q4 规划"],
     "subtitle": "云栖笔记 —— 面向大学生的 AI 辅助笔记 App",
     "aside": "( 2026 · Q3 )",
     "notes": "开场：本季度最值得说的是留存和付费同时改善。"},
    {"archetype": "data",
     "label": "月活跃用户 · MONTHLY ACTIVE USERS", "hero": "12.4", "unit": " 万",
     "hero_size": 148, "caption": "较上季度的 8.1 万，净增 4.3 万。",
     "delta": "+53%", "delta_label": "QUARTER ON QUARTER",
     "side": {"title": "增长的来源",
              "items": ["九月开学季的校园推广", "「手写转文字」的口碑传播"],
              "aside": "( two causes )"},
     "bars": [{"label": "Q2", "value": "8.1 万", "pct": 8.1, "color": "inkB"},
              {"label": "Q3", "value": "12.4 万", "pct": 12.4, "color": "inkA"}],
     "notes": "月活 12.4 万，环比 +53%。"},
    {"archetype": "grid",
     "title": "竞品对比",
     "columns": [{"label": "云栖", "ours": True}, {"label": "A · 老牌笔记"},
                 {"label": "B · 新兴 AI"}],
     "row_h": 72,
     "rows": [
         {"label": "手写识别准确率", "cells": [
             {"text": "96%", "size": 32, "ours": True},
             {"text": "89%", "size": 26}, {"text": "93%", "size": 26}]},
         {"label": "复习功能", "cells": [
             {"text": "自动生成复习卡片", "size": 17, "display": False, "ours": True},
             {"text": "无", "size": 17, "display": False},
             {"text": "需手动整理", "size": 17, "display": False}]},
         {"label": "价格（每月）", "cells": [
             {"text": "¥12", "size": 28, "ours": True},
             {"text": "¥18", "size": 24}, {"text": "¥15", "size": 24}]}],
     "note": "( 三个维度：识别 · 复习 · 价格 )",
     "notes": "手写识别领先，价格最低，复习功能是差异点。"},
    {"archetype": "closing",
     "quote": "把 20 万月活，建在稳定的地基上。",
     "target": "Q4 目标：月活 20 万 · 崩溃率 < 1%",
     "big": "THANK YOU", "sticker": "Q & A",
     "notes": "收尾：Q4 的功课是把规模建立在稳定性上。"},
]

BACKGROUNDS = {
    "1": {"preset": "cover-bleed-tr"},
    "2": {"preset": "corner-fade-br"},
    "3": {"preset": "corner-speckle-tr"},
    "4": {"reverse": True, "preset": "reverse-circle-tr"},
}
REVERSED = [4]

SEEDS = [101, 202, 303]


def spec_for(seed):
    return {
        "meta": {
            "title": "云栖笔记 季度产品汇报", "lang": "zh", "scenario": "report",
            "palette": "G", "print_grammar": "light", "seed": seed,
            "total": len(PAGES),
            "footer": "YUNQI NOTES - QUARTERLY REVIEW",
            "header_right": "季度产品汇报", "header_left": "产品汇报",
        },
        "backgrounds": BACKGROUNDS,
        "pages": PAGES,
    }


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--render', action='store_true')
    args = ap.parse_args()
    OUT = os.path.abspath(args.out)
    root = os.path.dirname(HERE)
    if Path(root).resolve() == Path(OUT).resolve() or Path(root).resolve() in Path(OUT).resolve().parents:
        ap.error('Gallery demos must be outside the skill package')
    os.makedirs(OUT, exist_ok=True)
    summary = []
    for seed in SEEDS:
        work = os.path.join(OUT, f"seed{seed}")
        media = os.path.join(work, "media")
        os.makedirs(media, exist_ok=True)
        spec = spec_for(seed)
        spec_path = os.path.join(work, "deck.json")
        spec["meta"]["media"] = media
        spec["meta"]["bg_manifest"] = os.path.join(media, "manifest.json")
        json.dump(spec, open(spec_path, "w", encoding="utf-8"), ensure_ascii=False)
        plan = os.path.join(work, "plan.json")
        json.dump({"pages": BACKGROUNDS}, open(plan, "w"))
        r = run([PY, os.path.join(SCRIPTS, "make_textures.py"), "bg", "--out", media,
                 "--pages", str(len(PAGES)), "--palette", "G", "--seed", str(seed),
                 "--plan-file", plan, "--manifest", spec["meta"]["bg_manifest"],
                 "--scale", "1.5"])
        if r.returncode:
            print("bg failed", r.stderr[-400:])
            return 1
        deck = os.path.join(work, "deck.pptx")
        r = run([PY, os.path.join(SCRIPTS, "build_deck.py"), "--spec", spec_path,
                 "--out", deck])
        if r.returncode:
            print("build failed", (r.stdout + r.stderr)[-600:])
            return 1
        rendered = False
        if args.render:
            r = run([PY, os.path.join(SCRIPTS, "render.py"), "--deck", deck,
                     "--out", os.path.join(work, "preview"), '--keep-pdf', '--autodiscover'])
            rendered = r.returncode == 0
            if not rendered:
                print("render requested but failed; pixel QA UNVERIFIED", (r.stdout + r.stderr)[-700:])
                return r.returncode
        qa_cmd = [PY, os.path.join(SCRIPTS, "qa.py"), "--deck", deck, "--media", media,
                  "--json", os.path.join(work, "qa.json"),
                  "--expect-pages", str(len(PAGES))]
        if rendered:
            qa_cmd += ['--render', os.path.join(work, 'preview'), '--require-render']
        r = run(qa_cmd)
        if r.returncode:
            print('QA failed', (r.stdout + r.stderr)[-800:])
            return 1
        r = run([PY, os.path.join(SCRIPTS, 'layout_check.py'), '--deck', deck,
                 '--json', os.path.join(work, 'layout.json')])
        if r.returncode:
            print('Layout/rhythm failed', (r.stdout + r.stderr)[-1200:])
            return 1
        style = json.load(open(os.path.join(work, "style.json"), encoding="utf-8"))
        qa = json.load(open(os.path.join(work, "qa.json"), encoding="utf-8"))
        fails = [i for i in qa["items"] if not i["ok"] and i["severity"] == "fail"]
        warns = [i for i in qa["items"] if not i["ok"] and i["severity"] == "warn"]
        d = style["dialect"]
        els = {}
        for e in style["elements"]:
            els.setdefault(e["page"], []).append(f"{e['role'][:4]}:{e['element']}")
        print(f"\n=== seed {seed}: {d['name']}  (primary {d['primary']} / "
              f"secondary {d['secondary']}, by {d['chosen_by']})")
        print(f"    scenario={style['density']['scenario']}  "
              f"qa: {len(fails)} fail / {len(warns)} warn of {len(qa['items'])}")
        for pg in sorted(els):
            print(f"    p{pg}: " + ", ".join(els[pg]))
        summary.append({"seed": seed, "dialect": d["name"],
                        "primary": d["primary"], "secondary": d["secondary"],
                        "fail": len(fails), "warn": len(warns),
                        "deck": deck, "preview": os.path.join(work, "preview") if rendered else None})
        for f in fails[:6]:
            print(f"      FAIL p{f['page']}: {f['check']} — {f['detail']}")
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n{len(SEEDS)} decks -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
