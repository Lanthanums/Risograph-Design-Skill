#!/usr/bin/env python3
"""test_contract.py — regression suite for riso-slides.

  python tests/test_contract.py            # structural + package tests
  python tests/test_contract.py --render   # also render and run pixel QA

Three things are being guarded here:

1. package hygiene — the skill must not ship, or tell anyone to imitate, a
   finished example. An `assets/README.txt` inviting the agent to "calibrate
   palette + composition" against whatever poster was lying around is how one
   English speech poster turns into the layout template for an unrelated
   Chinese business report.
2. the builder — every fixture must build, hit its declared archetype sequence,
   pass qa.py, be deterministic, and keep its text out of the other fixtures.
3. the generator — make_textures.py selftest (the four fixed bugs).
"""
import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
FIXTURES = os.path.join(HERE, "fixtures")
PY = sys.executable
sys.path.insert(0, SCRIPTS)

# subprocess output and spec text carry CJK and em dashes; a GBK console would
# otherwise kill the run while printing a failure message
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Copy that must never be baked into the toolkit. If someone later "helpfully"
# adds an example deck to the skill, these strings show up and the suite fails.
FORBIDDEN_COPY = [
    "BEYOND TRANSLATION", "TWO-GREEN RISO", "A SPEECH ON AI",
    "a resounding one", "HUMAN HEART", "NEVER OUTSOURCED",
    "A QUARTERLY PRODUCT REVIEW", "RISO EDITION", "AN AI NOTE-TAKING APP",
    "拾页", "SHIYE",
]
# Wording that lets an arbitrary poster become the template.
FORBIDDEN_INSTRUCTIONS = [
    "calibrate palette + composition",
    "Place a reference poster",
    "若 `assets/` 目录中存在用户放入的参考海报",
    "reference poster here",
]

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **kw)


def sh(*args):
    return " ".join(str(a) for a in args)


# --------------------------------------------------------------- 1. package
def test_package():
    print("package hygiene")
    check("assets/ (the poster entry point) is gone",
          not os.path.exists(os.path.join(SKILL, "assets")))
    imgs = []
    for root, _dirs, files in os.walk(SKILL):
        imgs += [os.path.join(root, f) for f in files
                 if os.path.splitext(f)[1].lower() in (".png", ".jpg", ".jpeg", ".webp", ".pptx")]
    check("no images or decks shipped with the skill", not imgs, sh(*imgs[:3]))

    text_files = []
    for root, _dirs, files in os.walk(SKILL):
        text_files += [os.path.join(root, f) for f in files
                       if os.path.splitext(f)[1].lower() in (".md", ".py", ".sh", ".json")]
    blob = {}
    for f in text_files:
        if f.endswith("test_contract.py"):
            continue
        blob[f] = open(f, encoding="utf-8", errors="replace").read()
    hits = [(os.path.basename(f), s) for f, t in blob.items() for s in FORBIDDEN_COPY if s in t]
    check("no example deck copy baked into the toolkit", not hits, sh(*hits[:3]))
    hits = [(os.path.basename(f), s) for f, t in blob.items()
            for s in FORBIDDEN_INSTRUCTIONS if s in t]
    check("no instruction to calibrate against an external poster", not hits,
          sh(*hits[:3]))

    skill_md = blob.get(os.path.join(SKILL, "SKILL.md"), "")
    check("SKILL.md covers non-speech scenarios",
          "report" in skill_md and "proposal" in skill_md and "course" in skill_md)
    check("SKILL.md still tells the agent to ask when content is missing",
          "ask" in skill_md.lower())
    check("SKILL.md runtime footprint <= 10 KB",
          os.path.getsize(os.path.join(SKILL, "SKILL.md")) <= 10 * 1024)


# --------------------------------------------------------------- 2. generator
def test_generator():
    print("texture generator")
    p = run([PY, os.path.join(SCRIPTS, "make_textures.py"), "selftest"])
    ok = p.returncode == 0
    check("make_textures.py selftest (all four fixed bugs)", ok,
          "" if ok else (p.stdout + p.stderr)[-400:])


# --------------------------------------------------------------- 3. fixtures
def build_fixture(fixture, workdir, render=False):
    spec = json.load(open(fixture, encoding="utf-8"))
    media = os.path.join(workdir, "media")
    os.makedirs(media, exist_ok=True)
    plan_file = os.path.join(workdir, "plan.json")
    json.dump({"pages": spec.get("backgrounds", {})}, open(plan_file, "w"))
    manifest = os.path.join(media, "manifest.json")
    pages = len(spec["pages"])
    p = run([PY, os.path.join(SCRIPTS, "make_textures.py"), "bg", "--out", media,
             "--pages", str(pages), "--palette", spec["meta"].get("palette", "G"),
             "--seed", str(spec["meta"].get("seed", 1)), "--plan-file", plan_file,
             "--manifest", manifest, "--scale", "1.5"])
    if p.returncode != 0:
        return None, f"make_textures failed: {(p.stdout + p.stderr)[-300:]}"

    spec["meta"]["media"] = media
    spec["meta"]["bg_manifest"] = manifest
    tmp_spec = os.path.join(workdir, "deck.json")
    json.dump(spec, open(tmp_spec, "w", encoding="utf-8"), ensure_ascii=False)
    deck = os.path.join(workdir, "deck.pptx")
    p = run([PY, os.path.join(SCRIPTS, "build_deck.py"), "--spec", tmp_spec,
             "--out", deck])
    if p.returncode != 0:
        return None, f"build_deck failed: {(p.stdout + p.stderr)[-400:]}"

    qa_out = os.path.join(workdir, "qa.json")
    qa_cmd = [PY, os.path.join(SCRIPTS, "qa.py"), "--deck", deck, "--media", media,
              "--json", qa_out, "--expect-pages", str(pages)]
    preview = os.path.join(workdir, "preview")
    if render:
        r = run([PY, os.path.join(SCRIPTS, "render.py"), "--deck", deck, "--out",
                 preview, "--autodiscover"])
        if r.returncode == 0:
            qa_cmd += ["--render", preview, '--require-render']
        elif r.returncode == 3:
            print('         [SKIPPED / UNVERIFIED] requested pixel checks: ' +
                  (r.stdout + r.stderr)[-700:])
        else:
            return None, 'renderer execution failed (pixel QA UNVERIFIED): ' + (r.stdout + r.stderr)[-900:]
    p = run(qa_cmd)
    if p.returncode != 0:
        return None, "qa failed:\n" + p.stdout[-900:]
    p = run([PY, os.path.join(SCRIPTS, 'layout_check.py'), '--deck', deck,
             '--json', os.path.join(workdir, 'layout.json')])
    if p.returncode != 0:
        return None, 'layout failed:\n' + (p.stdout + p.stderr)[-1200:]
    return {"dir": workdir, "deck": deck, "spec": spec, "media": media,
            "manifest": manifest, "preview": preview if os.path.isdir(preview) else None}, ""


def slide_texts(deck):
    from pptx import Presentation
    prs = Presentation(deck)
    out = []
    for slide in prs.slides:
        for sh in slide.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                out.append(sh.text_frame.text.strip())
    return out


def slide_xml_hash(deck):
    from pptx import Presentation
    prs = Presentation(deck)
    h = hashlib.sha256()
    for slide in prs.slides:
        h.update(slide._element.xml.encode("utf-8"))
    return h.hexdigest()


def test_fixtures(render, output=None):
    print("fixtures")
    files = sorted(f for f in os.listdir(FIXTURES) if f.endswith(".json"))
    built = {}
    if output:
        from pathlib import Path
        target=Path(output).resolve()
        package=Path(SKILL).resolve()
        if target == package or package in target.parents:
            raise ValueError('--out review evidence must be outside the skill package')
        target.mkdir(parents=True,exist_ok=True)
        root = tempfile.mkdtemp(prefix='contract-',dir=target)
    else:
        root = tempfile.mkdtemp(prefix="riso_tests_")
    try:
        for f in files:
            name = os.path.splitext(f)[0]
            work = os.path.join(root, name)
            os.makedirs(work, exist_ok=True)
            info, err = build_fixture(os.path.join(FIXTURES, f), work, render)
            if not check(f"{name}: builds and passes qa", info is not None, err):
                continue
            built[name] = info
            exp = info["spec"].get("expect", {})
            man = json.load(open(info["manifest"], encoding="utf-8"))
            rev = [p["page"] for p in man["pages"] if p["reversed"]]
            check(f"{name}: reversed pages as declared", rev == exp.get("reversed", []),
                  f"{rev} vs {exp.get('reversed')}")
            arch = [p["archetype"] for p in info["spec"]["pages"]]
            check(f"{name}: archetype sequence", arch == exp.get("archetypes", arch),
                  sh(*arch))
            # determinism: same spec -> same slide XML
            work2 = os.path.join(root, name + "_again")
            os.makedirs(work2, exist_ok=True)
            info2, err2 = build_fixture(os.path.join(FIXTURES, f), work2, False)
            if info2:
                check(f"{name}: build is deterministic",
                      slide_xml_hash(info["deck"]) == slide_xml_hash(info2["deck"]))
            if info.get("preview"):
                n = len(glob.glob(os.path.join(info["preview"], "page-*.png")))
                print(f"         rendered {n} pages")
            else:
                print("         (pixel checks SKIPPED / UNVERIFIED; see QA notes)")
        # cross-fixture leakage + coverage
        names = sorted(built)
        for i, a in enumerate(names):
            ta = set(t for t in slide_texts(built[a]["deck"]) if len(t) >= 8)
            for b in names[i + 1:]:
                tb = set(t for t in slide_texts(built[b]["deck"]) if len(t) >= 8)
                shared = {t for t in (ta & tb) if len(t) >= 12}
                check(f"no copy shared between {a} and {b}", not shared,
                      sh(*list(shared)[:2]))
        arches = {p["archetype"] for info in built.values() for p in info["spec"]["pages"]}
        check("fixtures exercise at least 8 archetypes", len(arches) >= 8,
              f"{len(arches)}: {sorted(arches)}")
        langs = {info["spec"]["meta"]["lang"] for info in built.values()}
        check("fixtures span more than one language", len(langs) > 1, sh(*sorted(langs)))
    finally:
        if not output:
            shutil.rmtree(root, ignore_errors=True)
        else:
            print(f'         fixture evidence retained: {root}')
    return built


# --------------------------------------------------------------- 4. grammar
def test_print_grammar():
    print("print-grammar switch")
    import riso_kit as rk
    root = tempfile.mkdtemp(prefix="riso_grammar_")
    try:
        counts = {}
        for level in ("full", "light", "none"):
            prs = rk.new_deck()
            s = rk.add_page(prs, None)
            th = rk.Theme(palette="G", print_grammar=level, lang="zh")
            rk.chrome(s, th, 1, 3, "LEFT LABEL", "RIGHT LABEL", foot_left="FOOTER")
            counts[level] = sum(1 for sh in s.shapes
                                if sh.has_text_frame and sh.text_frame.text.strip())
        check("print grammar full > light > none",
              counts["full"] > counts["light"] > counts["none"], sh(counts))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_design_system():
    """The design language must be self-contained: frozen in the package and
    reachable without opening any finished artifact."""
    print("design system")
    ds = os.path.join(SKILL, "references", "design-system.md")
    if not check("references/design-system.md exists", os.path.exists(ds)):
        return
    doc = open(ds, encoding="utf-8").read()
    check("doc covers the colour roles",
          all(k in doc for k in ("inkA", "inkB", "ink_deep", "inkAB",
                                 "accent1", "accent2", "paper")))
    check("doc routes type scale and offsets to the numeric source",
          all(k in doc for k in ("display_xl", "page_title", "riso_kit.DESIGN",
                                "misreg_offsets()")))

    import make_textures as mt
    import riso_kit as rk
    named = [p for p in mt.FIELD_PRESETS if f"`{p}`" in doc]
    check("doc documents every calibrated dot preset",
          len(named) == len(mt.FIELD_PRESETS),
          f"{len(named)}/{len(mt.FIELD_PRESETS)}; missing "
          f"{sorted(set(mt.FIELD_PRESETS) - set(named))}")
    check("every preset carries a note and a recommended archetype",
          all(s.get("note") for s in mt.FIELD_PRESETS.values())
          and len(mt.RECOMMENDED_PRESET) >= 10)

    m = rk.DESIGN["misregistration"]
    check("offset query matches the single numeric source",
          rk.misreg_offsets(122) == tuple(m["display_xl"])
          and rk.misreg_offsets(30) == tuple(m["page_title"]))
    d = rk.design_system()
    check("design_system() exposes the documented sections",
          {"canvas", "colour_roles", "type_scale", "misregistration",
           "decoration", "dot_fields", "provenance"} <= set(d))
    check("design_system() carries a provenance policy",
          "policy" in d["provenance"] and d["provenance"]["calibrated"])
    check("design_system() embeds the preset catalogue",
          len(d["dot_fields"]["presets"]) == len(mt.FIELD_PRESETS))

    # the hard guarantee: nothing opens a file the user did not hand over
    # (only `duotone --in`, for a photo the user supplied)
    user_inputs, others = [], []
    for root, _dirs, files in os.walk(SKILL):
        for f in files:
            if not f.endswith(".py"):
                continue
            src = open(os.path.join(root, f), encoding="utf-8").read()
            for m2 in re.finditer(r"Image\.open\(([^)]*)\)", src):
                arg = m2.group(1).strip()
                (user_inputs if re.search(r"infile|args\.in\b", arg)
                 else others).append((f, arg))
    check("only duotone opens a user-supplied file",
          len(user_inputs) == 1 and user_inputs[0][0] == "make_textures.py",
          sh(*user_inputs))
    scripts = [os.path.join(r, f) for r, _d, fs in os.walk(SKILL)
               for f in fs if f.endswith(".py") and f != "test_contract.py"]
    check("no script references an assets/ directory",
          not any("assets" in open(p, encoding="utf-8").read() for p in scripts))


def test_artifact_independence():
    """Behavioural guarantee: the output must be byte-identical whether or not
    finished artifacts are lying around. This is the regression test for the
    original failure — a poster in the input folder became the layout template."""
    print("independence from finished artifacts")
    fixture = os.path.join(FIXTURES, "report_en.json")
    root = tempfile.mkdtemp(prefix="riso_decoy_")
    try:
        clean = os.path.join(root, "clean")
        noisy = os.path.join(root, "noisy")
        os.makedirs(clean)
        os.makedirs(noisy)
        # drop the kind of thing that hijacked an earlier run
        decoys = {
            "poster.jpg": b"\xff\xd8\xff\xe0" + b"\x00" * 500,
            "reference-poster.png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 500,
            "previous deck.pptx": b"PK\x03\x04" + b"\x00" * 500,
        }
        for name, blob in decoys.items():
            open(os.path.join(noisy, name), "wb").write(blob)
        os.makedirs(os.path.join(noisy, "preview"), exist_ok=True)
        open(os.path.join(noisy, "preview", "page-0001.png"), "wb").write(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 500)

        a, err_a = build_fixture(fixture, clean, False)
        b, err_b = build_fixture(fixture, noisy, False)
        if not check("both builds succeed", a and b, (err_a or err_b)[:200]):
            return
        check("decoys do not change the deck",
              slide_xml_hash(a["deck"]) == slide_xml_hash(b["deck"]))
        ha = [p["sha256"] for p in json.load(open(a["manifest"], encoding="utf-8"))["pages"]]
        hb = [p["sha256"] for p in json.load(open(b["manifest"], encoding="utf-8"))["pages"]]
        check("decoys do not change a single background", ha == hb)
        # and nothing in the toolkit ever writes to the artifact files
        check("decoys are left untouched",
              all(os.path.getsize(os.path.join(noisy, n)) == len(blob)
                  for n, blob in decoys.items()))
        # a style.json that is an *output* gets regenerated, not inherited
        style = os.path.join(noisy, "style.json")
        check("style.json is regenerated from the spec, not inherited",
              os.path.exists(style)
              and json.load(open(style, encoding="utf-8"))["skill"] == "riso-slides")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dialects_and_elements():
    """The enrichment layer must stay wired: 6 dialects, a generated catalogue,
    and enough elements per category for the pools to mean something."""
    print("dialects and elements")
    import compose
    import elements as E

    check("six dialects are defined", len(compose.DIALECTS) == 6,
          ", ".join(sorted(compose.DIALECTS)))
    missing = []
    for code, d in compose.DIALECTS.items():
        for role in ("hero", "support", "micro"):
            for name in d["pools"].get(role, []):
                if name not in E.REGISTRY:
                    missing.append(f"{code}.{role}:{name}")
    check("every dialect pool entry exists in the registry", not missing,
          sh(*missing[:5]))
    cats = {m["category"] for m in E.REGISTRY.values()}
    check("element categories cover the brief", len(cats) >= 6, sh(*sorted(cats)))
    check("at least 60 elements registered", len(E.REGISTRY) >= 60,
          f"{len(E.REGISTRY)}")
    check("density profiles exist for every scenario",
          {"speech", "report", "course", "proposal", "poster", "zine"}
          <= set(compose.DENSITY))
    check("density profiles are ordered by loudness",
          compose.DENSITY["speech"]["max_area"] > compose.DENSITY["report"]["max_area"],
          f"speech {compose.DENSITY['speech']['max_area']} vs "
          f"report {compose.DENSITY['report']['max_area']}")

    # the generated catalogue must match the registry exactly
    md_path = os.path.join(SKILL, "references", "elements.md")
    if check("references/elements.md exists", os.path.exists(md_path)):
        md = open(md_path, encoding="utf-8").read()
        absent = [n for n in E.REGISTRY if f"`{n}`" not in md]
        check("elements.md documents every registered element", not absent,
              f"missing {absent[:5]}")
        check("elements.md declares the right total",
              f"**{len(E.REGISTRY)}**" in md, f"registry has {len(E.REGISTRY)}")

    # a page plan must respect the text protection zone and the area budget
    import random as _random
    import layout as lay

    def edge_gap(r, a):
        dx = max(a[0] - r[2], r[0] - a[2], 0.0)
        dy = max(a[1] - r[3], r[1] - a[3], 0.0)
        return (dx * dx + dy * dy) ** 0.5

    plan = compose.plan_page("data", "A", "C", "report", _random.Random(5),
                             [(48, 100, 500, 200), (600, 120, 900, 300)])
    text_boxes = [(48, 100, 500, 200), (600, 120, 900, 300)]
    bad = [p for p in plan
           if any(lay.overlaps(p["rect"], t, pad=lay.TEXT_PROTECTION * 0.4)
                  for t in text_boxes)]
    check("planned elements keep clear of text", not bad,
          sh(*[p["name"] for p in bad][:4]))
    area = sum(lay.area(p["rect"]) for p in plan) / (lay.PAGE_W * lay.PAGE_H)
    check("planned decoration stays inside the area budget",
          area <= compose.DENSITY["report"]["max_area"] + 0.02,
          f"{area*100:.1f}%")
    roles = {p["role"] for p in plan}
    check("a page with real room gets a hero",
          "hero" in roles, f"{len(plan)} elements, roles {roles}")
    # there is no area-floor filler loop: a plan decorates what it can
    # explain and stops, it never pads a page to a quota
    check("no hole-filling: a plan stays small",
          len(plan) <= 6, f"{len(plan)} elements")

    # anchor-first: typed copy (title / big number / label) attracts
    # attached decoration sitting one protection-gap away; bare-tuple callers
    # have no anchors and simply get none
    enriched = [{"rect": (48, 90, 448, 140), "text": "RESULTS", "size": 34.0},
                {"rect": (600, 120, 900, 300), "text": "side notes",
                 "size": 19.0}]
    plan2 = compose.plan_page("data", "A", "C", "report", _random.Random(5),
                              enriched)
    att = [p for p in plan2 if p.get("placement") == "attached"]
    check("typed copy attracts attached decoration", len(att) >= 1,
          f"placements: {[p.get('placement') for p in plan2]}")
    bad2 = [p for p in plan2
            if any(lay.overlaps(p["rect"], t["rect"],
                                pad=lay.TEXT_PROTECTION * 0.4)
                   for t in enriched)]
    check("attached elements still respect the protection zone", not bad2,
          sh(*[p["name"] for p in bad2][:4]))
    anchored = [p for p in att if p.get("anchor") == "RESULTS"]
    check("attached elements sit one gap from their anchor, not on it",
          all(lay.TEXT_PROTECTION + 0.5 <= edge_gap(p["rect"], enriched[0]["rect"])
              <= 40 for p in anchored),
          sh(*[round(edge_gap(p["rect"], enriched[0]["rect"]), 1)
               for p in anchored]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true",
                    help="also render previews and run the pixel checks")
    ap.add_argument('--out',help='retain fixture decks/previews/QA outside the skill package')
    args = ap.parse_args()
    print(f"riso-slides contract tests ({SKILL})\n")
    test_package()
    test_design_system()
    test_dialects_and_elements()
    test_artifact_independence()
    test_generator()
    test_print_grammar()
    test_fixtures(args.render,args.out)
    bad = [r for r in results if not r[1]]
    print(f"\n{len(bad)} failure(s) out of {len(results)} check(s)")
    for name, _ok, detail in bad:
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
