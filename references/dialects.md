# Dialects

Choose one primary and one secondary: explicit user choice, content domain,
then seeded choice. `meta.dialect: ["B", "A"]` pins the pair. The primary supplies
the graphic vocabulary and deck chrome; at most one secondary accent is placed.
Posters share the vocabulary, but never inherit deck chrome.

| ID | Character | Useful graphic language | Typical domain |
|---|---|---|---|
| A | Collage | Torn paper, cut polygons, tape, layered print | Humanities, reflection |
| B | Doodle journal | Variable-width circles, scribbles, arrows, spirals | Education, workshops |
| C | Swiss geometry | Arches, rings, stairs, stripes, precise blocks | Nature, structure |
| D | Magazine grid | Paper forms, fold/crop marks, modular geometry | Reports, finance |
| E | Retro OS | Windows, pixels, cursors, dot screens | Software, technology |
| F | Zine/comic | Starbursts, bubbles, bold cut shapes, marquee bands | Music, events |

Query `elements.py catalogue --dialect B --safe --limit 8` for usable candidates.
The registry includes some self-lettered demonstrations; `--safe` returns the
copy-free automatic pool. Never add a fake issue/date/number from an element.
Use `meta.element_pool` and `exclude_elements` to narrow choices. An empty pool
intentionally disables decoration. A poster's `meta.graphic_element` can choose
a specific allowed primary graphic; see [poster.md](poster.md).

Keep stroke character coherent: torn edges in A, jitter and varying width in B,
precise edges in C/D, pixel alignment in E, bold shapes in F. Placement respects
content anchors, reserved composition regions, aligned groups and quiet space.

The engine records choices in the artifact sidecar and per-user history. New
artifacts avoid recent pairs; rebuilding the same title/seed reuses its recorded
choice. Pin dialect explicitly for reproducibility across empty history stores.
History stays outside the skill (`RISO_DESIGN_STATE_DIR` can override its location).
