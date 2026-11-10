"""Compatibility composition policies for legacy poster specs."""

import random


import elements as E
from element_runtime import (append_history, apply_plan, content_obstacles,
                             free_rects, history_path, load_history)


DIALECTS = {
    "A": {
        "name": "拼贴剪贴",
        "en": "collage",
        "pools": {
            "hero": ["torn_paper", "handcut_polygon", "grain_fade", "polaroid",
                     "newspaper_clipping", "airmail_envelope"],
            "support": ["washi_tape", "stamp_postmark", "ticket_stub",
                        "layered_stack", "luggage_tag", "rubber_stamp",
                        "zigzag_strip"],
            "micro": ["paperclip", "ransom_word", "stamp_postmark"],
        },
        "motifs": ["tabletop", "sticker_sheet", "spread", "band_split"],
        "grammar": {"header": "line", "footer": "line", "reg_marks": True},
        "stroke": "torn",
        "density_bias": 1.0,
        "palettes": ["C", "A", "E"],
    },
    "B": {
        "name": "涂鸦手帐",
        "en": "doodle journal",
        "pools": {
            "hero": ["scribble_circle", "scribble_fill", "thought_cloud",
                     "marker_frame", "speech_bubble", "sticky_note"],
            "support": ["wavy_underline", "hand_arrow", "asterisk", "spiral",
                        "checklist", "hand_brace", "double_underline",
                        "scribble_redact"],
            "micro": ["mini_doodle", "doodle_face", "starburst", "asterisk"],
        },
        "motifs": ["notebook_page", "annotation", "sticker_sheet", "list_form"],
        "grammar": {"header": "hand", "footer": "hand", "reg_marks": False},
        "stroke": "drawn",
        "density_bias": 1.15,
        "palettes": ["B", "F", "D"],
    },
    "C": {
        "name": "瑞士几何",
        "en": "swiss geometric",
        "pools": {
            "hero": ["arch", "blob", "circle_text_badge", "quarter_tiles",
                     "outline_letter", "stairs"],
            "support": ["pill", "stripe_band", "checkerboard", "zigzag_band",
                        "plus_grid", "scallop_block", "triangle_strip", "ring",
                        "line_screen"],
            "micro": ["plus_grid", "ring", "stripe_band", "circled_number"],
        },
        "motifs": ["band_split", "diagonal_cut", "badge_centre", "pure_type",
                   "swiss_grid"],
        "grammar": {"header": "line", "footer": "line", "reg_marks": True},
        "stroke": "precise",
        "density_bias": 0.95,
        "palettes": ["D", "C", "E"],
    },
    "D": {
        "name": "杂志模块",
        "en": "magazine grid",
        "pools": {
            "hero": ["newspaper_clipping", "paper_sheet", "blob", "ring",
                     "colour_bar"],
            "support": ["crop_marks", "fold_line", "caption_label",
                        "issue_stamp", "line_screen", "zigzag_strip",
                        "barcode"],
            "micro": ["printed_note", "caption_label", "circled_number",
                      "colour_bar"],
        },
        "motifs": ["magazine_grid", "spread", "list_form", "band_split"],
        "grammar": {"header": "rule", "footer": "rule", "reg_marks": True},
        "stroke": "precise",
        "density_bias": 1.05,
        "palettes": ["D", "C", "A"],
    },
    "E": {
        "name": "复古 OS / Y2K",
        "en": "retro OS",
        "pools": {
            "hero": ["os_window", "dialog_box", "pixel_icon", "progress_bar",
                     "grain_fade"],
            "support": ["progress_bar", "pixel_icon", "dot_screen",
                        "square_dot_screen", "barcode"],
            "micro": ["cursor_arrow", "pixel_icon", "printed_note"],
        },
        "motifs": ["stacked_windows", "band_split", "list_form", "badge_centre"],
        "grammar": {"header": "rule", "footer": "rule", "reg_marks": False},
        "stroke": "pixel",
        "density_bias": 1.0,
        "palettes": ["B", "F", "E"],
    },
    "F": {
        "name": "Zine 漫画",
        "en": "zine comic",
        "pools": {
            "hero": ["starburst", "speech_bubble", "marquee_band",
                     "scribble_fill", "handcut_polygon"],
            "support": ["starburst", "zigzag_strip", "loop_border", "asterisk",
                        "scribble_circle", "marquee_band"],
            "micro": ["mini_doodle", "starburst_badge", "circled_number",
                      "asterisk"],
        },
        "motifs": ["comic_panels", "badge_centre", "band_split", "pure_type"],
        "grammar": {"header": "marquee", "footer": "line", "reg_marks": False},
        "stroke": "loud",
        "density_bias": 1.25,
        "palettes": ["F", "B", "E"],
    },
}


DOMAIN_MAP = [
    (("财务", "数据", "汇报", "finance", "data", "report", "quarter", "kpi"),
     ("D", "E")),
    (("教育", "学习", "笔记", "课程", "讲义", "education", "course", "note",
      "lecture", "study"), ("B", "A")),
    (("科技", "ai", "软件", "产品", "tech", "software", "product", "launch",
      "app"), ("E", "C")),
    (("环保", "自然", "地理", "能源", "climate", "energy", "nature"),
     ("C", "A")),
    (("文学", "人文", "演讲", "语言", "literature", "speech", "language",
      "humanities"), ("A", "C")),
    (("活动", "音乐", "青春", "社团", "music", "event", "festival", "club"),
     ("F", "C")),
]


POSTER_DENSITY = {
        "font_scale": 1.15, "hero_frac": (0.36, 0.58), "attached": (1, 3),
        "free": (1, 3), "element_scale": 1.30, "max_area": 0.38,
        "hero_min_room": 0.10,
        "note": "海报：满版、冲击力优先",
    }


MOOD_ARCHETYPES = {"cover", "statement", "quote", "closing", "divider"}


ATTACH_NEAR = 60.0


TEXT_BEARING = {
    "colour_bar",       # labelled swatch strip: grass green / overprint / rice white
    "issue_stamp",      # VOL. 03 / ISSUE 07 / MAR 2024
    "ransom_word",      # spells R E T U R N
    "caption_label",    # FIG. 01 — PRESS SHEET
    "printed_note",     # RISOGRAPH · LIMITED EDITION
    "newspaper_clipping",
    "barcode",
    "ticket_stub", "polaroid", "luggage_tag", "rubber_stamp", "outline_letter",
    "circle_text_badge", "marquee_band", "vertical_text", "drop_cap",
    "os_window", "progress_bar", "dialog_box",
}


NUMBER_BEARING = {"circled_number", "asterisk", "mini_doodle", "starburst_badge",
                  "doodle_face"}


ELEMENT_SETS = {
    "D": {                       # magazine: plates, marks, rules
        "hero": ["paper_sheet", "layered_stack", "blob"],
        "support": ["ring", "line_screen", "crop_marks", "fold_line"],
        "micro": ["zigzag_strip", "plus_grid"],
    },
    "A": {                       # collage: pasted paper, stamps, tape
        "hero": ["handcut_polygon", "layered_stack"],
        "support": ["stamp_postmark", "rubber_stamp", "washi_tape"],
        "micro": ["paperclip", "zigzag_strip"],
    },
    "B": {
        "hero": ["scribble_circle", "scribble_fill", "marker_frame", "sticky_note"],
        "support": ["wavy_underline", "hand_arrow", "hand_brace", "double_underline"],
        "micro": ["spiral"],
    },
    "C": {
        "hero": ["arch", "blob", "ring", "stairs", "quarter_tiles", "outline_letter"],
        "support": ["pill", "stripe_band", "checkerboard", "zigzag_band",
                    "plus_grid", "scallop_block", "triangle_strip", "line_screen"],
        "micro": ["plus_grid", "ring", "stripe_band"],
    },
    "E": {
        "hero": ["pixel_icon", "cursor_arrow"],
        "support": ["progress_bar", "pixel_icon", "dot_screen", "square_dot_screen"],
        "micro": ["cursor_arrow"],
    },
    "F": {
        "hero": ["starburst", "speech_bubble", "marquee_band", "scribble_fill",
                 "handcut_polygon"],
        "support": ["zigzag_strip", "loop_border", "marquee_band"],
        "micro": ["zigzag_strip"],
    },
}


def _norm(s):
    return (s or "").lower()


def pick_dialects(text_blob, scenario, seed, history=None, forced=None,
                  self_key=None):
    """Choose a primary and a secondary dialect.

    Rule from the brief: user choice > content domain > seeded random, and never
    reuse the primary+major-motif combination of the last three decks.
    """
    rnd = random.Random(seed)
    if forced:
        primary = forced[0]
        secondary = forced[1] if len(forced) > 1 else _other(primary, rnd)
        return primary, secondary, "user"
    # A rebuild keeps its recorded choice even after unrelated builds intervene.
    if self_key:
        for rec in reversed((history or {}).get("decks", [])):
            if (rec.get("deck"), rec.get("seed")) == self_key:
                if rec.get("primary") in DIALECTS and rec.get("secondary") in DIALECTS:
                    return rec["primary"], rec["secondary"], rec.get("chosen_by", "domain")
    blob = _norm(text_blob)
    scored = []
    for keys, (a, b) in DOMAIN_MAP:
        hit = sum(1 for k in keys if k in blob)
        if hit:
            scored.append((hit, a, b))
    recent = set()
    for rec in (history or {}).get("decks", [])[-3:]:
        # rebuilding the same deck (same title + seed) is not a "recent deck" —
        # otherwise a second build of one spec drifts to another dialect and the
        # deck stops being reproducible
        if self_key and (rec.get("deck"), rec.get("seed")) == self_key:
            continue
        recent.add((rec.get("primary"), rec.get("secondary")))

    def fresh(pair):
        return pair not in recent

    if scored:
        scored.sort(key=lambda x: -x[0])
        # walk every domain match before falling back to random, so the same
        # content does not produce the same dialect three decks in a row
        for hit, a, b in scored:
            for cand in ((a, b), (b, a)):
                if fresh(cand):
                    return cand[0], cand[1], "domain"
    letters = list(DIALECTS)
    rnd.shuffle(letters)
    for a in letters:
        b = _other(a, rnd)
        if (a, b) not in recent:
            return a, b, "random"
    return letters[0], _other(letters[0], rnd), "random"


def _other(primary, rnd):
    pool = [d for d in DIALECTS if d != primary]
    rnd.shuffle(pool)
    return pool[0]


def element_pool(primary, secondary, exclusions=(), candidates=None):
    """Primary supplies 3/4 of the pool, the secondary the rest — that is what
    keeps a deck from looking like a single style sampler.

    Two filters run before an element is allowed on a page:

    1. `TEXT_BEARING` — a few library elements render their own copy, which no
       spec can edit. `colour_bar` is a labelled swatch strip ("grass green /
       overprint / rice white"), `issue_stamp` is "VOL. 03 / ISSUE 07 / MAR
       2024", `ransom_word` spells RETURN. Using one puts a stranger's sentence
       on the page.
    2. `circled_number` / `asterisk` / `mini_doodle` / `starburst_badge` draw a
       number or glyph the spec never chose — a "53" in a circle next to a page
       title is decoration made of a fact that does not exist. Sets that are
       decoration rather than data are curated per dialect in `ELEMENT_SETS`;
       anything not listed there falls back to the dialect pool as before.
    """
    def take(d, share):
        curated = ELEMENT_SETS.get(d)
        if curated:
            return [(role, n) for role, names in curated.items()
                    for n in names if n in E.REGISTRY and n not in TEXT_BEARING | NUMBER_BEARING] * (2 if share > 0.5 else 1)
        out = []
        for role, names in DIALECTS[d]["pools"].items():
            for n in names:
                if n in TEXT_BEARING or n in NUMBER_BEARING:
                    continue
                if n in E.REGISTRY:
                    out += [(role, n)] * (2 if share > 0.5 else 1)
        return out
    pool = take(primary, 1.0)
    pool += take(secondary, 0.0)
    # An intentionally empty pool is valid; no fallback adds unprovided copy.
    if candidates is not None:
        unknown=set(candidates)-set(E.REGISTRY)
        if unknown:raise ValueError(f'Unknown decoration candidates: {sorted(unknown)}')
        pool=[(r,n) for r,n in pool if n in candidates]
    unknown=set(exclusions)-set(E.REGISTRY)
    if unknown:raise ValueError(f'Unknown element exclusions: {sorted(unknown)}')
    return [(r,n) for r,n in pool if n not in exclusions]


def plan_page(archetype, primary, secondary, scenario, rnd, text_rects,
              taken_area=0.0, protection=None, archetype_kind=None, canvas=None,
              exclusions=(), candidates=None, graphic_rect=None, graphic_element=None, graphic_recipe='auto'):
    """Decide what to draw on this page — delegates to place_decor.Placer.

    Anchor-first, never hole-filling: the whole protocol lives in place_decor
    (anti-clutter rules A–F) — tiered budgets from the page's real word count,
    one protagonist, grouped elements, function tags, and a quiet-zone
    invariant checked after every placement.

    `text_rects` may be bare (x0,y0,x1,y1) tuples — then the page counts as
    wordless (T0) — or dicts {"rect", "text", "size"} as build_deck produces
    from tm.audit().
    """
    import place_decor as pd
    if canvas is None or canvas.artifact != 'poster':
        raise ValueError('A poster canvas is required')

    dens = POSTER_DENSITY
    kind = archetype_kind or archetype
    mood = kind in MOOD_ARCHETYPES

    items = []
    for t in text_rects:
        if isinstance(t, dict):
            items.append(t)
        else:
            items.append({"rect": tuple(t), "text": "", "size": 0.0})
    # the tier listens to the COPY, not the chrome: header/footer labels and
    # page numbers are not content words
    words = sum(pd.word_count(it.get("text", "")) for it in items if not it.get('duplicate_layer')
                if canvas.artifact == "poster" or
                50 <= (it["rect"][1] + it["rect"][3]) / 2.0 <= 478)

    placer = pd.Placer(items, scenario, primary, secondary, rnd,
                       words=words, taken_area=taken_area, mood=mood, canvas=canvas)
    valid=element_pool(primary,secondary,exclusions,candidates)
    allowed={name for _role,name in valid}
    placer._pools={key:[(role,name) for role,name in pool if name in allowed]
                   for key,pool in placer._pools.items()}
    placer.precise = DIALECTS[primary]["stroke"] == "precise"
    # the scenario profile stays as a second ceiling (rule B caps win when
    # tighter); chrome area counts into the budget (rule E)
    placer.area_cap = min(dens["max_area"], placer.area_cap)
    scale = dens["element_scale"] * DIALECTS[primary]["density_bias"]

    if graphic_rect:
        composed=False
        if canvas.artifact=='poster' and not graphic_element:
            import graphic_recipes
            composed=graphic_recipes.place(placer,graphic_rect,primary,graphic_recipe)
        if not composed:
            placer.place_composition(graphic_rect, graphic_element)
    att_lo, att_hi = dens["attached"]
    composition_items=[p for p in placer.placed if p.get('group')=='composition']
    attached_count=rnd.randint(att_lo, att_hi)
    if composition_items:
        # A planned figure already supplies the main graphic. A singleton counts
        # as a standalone detail in layout QA; budget it before adding accents.
        attached_count=min(attached_count,max(0,placer.micro_cap-(len(composition_items)==1)))
    placer.attach(max_count=attached_count, element_scale=scale)
    if not composition_items:
        placer.place_hero(element_scale=scale,
                          min_room=dens.get("hero_min_room", 0.12))
        placer.place_group(element_scale=scale)
    main_names={n for _,n in placer._pools['main']}
    for item in placer.placed:
        item['dialect']=primary if item['name'] in main_names else secondary
    return placer.placed
