# Deck content planning and rhythm

Use for deck tasks. Artifact `poster` has separate grammar in `poster.md`.
Scenario controls presentation character; density controls readable text load.
`compose.DENSITY`, `DENSITY_LEVELS`, and `DEFAULT_DENSITY` are the numeric source.

| Scenario | Content/use | Planning |
|---|---|---|
| speech | Script for spoken delivery | Emphasize supplied thesis/quote/number; notes retain the full script |
| report | Review, measurements, status | Evidence, comparison, source labels; conservative unclear-scenario fallback |
| course | Explanation, lecture, tutorial | Definitions, process, diagrams, examples |
| proposal | Problem, evidence, solution, request | Make the existing argument explicit; distinguish evidence from assumptions |
| zine | Short-form editorial reading | Coherent dense groupings without decoration quotas |
| poster (legacy deck scenario) | Loud presentation character | Still a deck; use artifact poster for an actual standalone poster |

Page count follows source content. Duration is an upper bound, not a target.
Never dilute a short source across many sparse pages. Do not add dividers or
blank mood pages for decoration or rhythm. A content page carries claim,
support, and an anchor; planning metadata may record these roles. Word counts
cannot prove meaning. Avoid pseudo-semantic scores and nondeterministic NLP QA.

## Background preparation

Default: omit `meta.media` and `meta.bg_manifest`. The builder generates
scale-2 JPEG plates at quality 70, automatically reverses divider/closing pages
(unless page `reverse` explicitly overrides), and washes measured text regions
including body copy. This removes a separate generation step and avoids lowering
image resolution to meet a file-size budget. Supplied media keeps its own manifest.

For explicit art direction, generate plates outside the skill:

```bash
python scripts/make_textures.py plan-schema
python scripts/make_textures.py bg --out OUTPUT/media --pages N --palette G --seed SEED --scale 2 --quality 70 --plan-file OUTPUT/plan.json --manifest OUTPUT/media/manifest.json
```

Match N, palette and seed to the deck. With external plates, record reverse pages
in that plan; the external manifest is authoritative. Inline presets require
`preset:` (for example `4:reverse+preset:reverse-circle-br`). For a spec in OUTPUT,
set `meta.media: "media"` and `meta.bg_manifest: "media/manifest.json"`.

Run `build_deck.py --spec OUTPUT/deck.json --check` before generating external
plates. It measures all pages in memory and returns all page failures at once,
plus measured slot rectangles. It makes no files/state and is not render QA.
A slot's capacity depends on resolved font, words and line breaks; character
counts cannot guarantee fitting. Page-level `notes: "full supplied script"`
overrides `meta.notes_default`. `notes` does not appear on the slide.

## Rhythm within existing pages

Plan the archetype sequence from semantics. When the source contains a genuine
key quote, key number, thesis, or turning point, an existing page may use quote,
statement, or data emphasis. Keep its support in notes or other content slots;
do not fabricate a sentence or increase page count. User-specified layouts win.
`compose.plan_rhythm()` records eligible emphasis anchors without rewriting copy.

`layout_check.py` reports archetypes, text tiers, measured protagonist zones,
normalized layout signatures, and warnings/failures for the complete deck.
Hard failures detect consecutive near-identical skeletons, very long homogeneous
runs, or overwhelming repetition across the deck. A pair of equal archetypes is
legal: two data pages can place their numbers/content in different zones.
Warnings identify an identical adjacent signature, little tier/zone variation
in a content window, or absent emphasis/breath variation. No rule requires a
T0 page at a fixed interval. Inspect the measured evidence; never insert a page
just to silence a warning.

See `rhythm.py` for exact thresholds and signature tolerance. Decorative ink
balance is omitted unless actual ink area can be measured reliably; picture
bounding boxes are not an ink distribution measurement.

Speech and proposal use their own `SPEECH_WORD_BANDS` proxy rather than report bands. Optional
`meta.word_band: [low, high]` overrides the range; it must be ordered/nonnegative.
Both bands and diagnostics remain word-count proxies, never content meaning.
Explicit paragraph boundaries separate words; display layer copies count once.
