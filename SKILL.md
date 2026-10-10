---
name: riso-slides
description: Create editable Risograph slide decks and standalone posters from user content, with spot inks, print texture, measured typography, and composed graphics. Use for riso reports, proposals, course slides, event, data, or typography posters.
---

# Riso slides and posters

Read only the route needed now. Run scripts without reading their implementation;
query small CLI outputs before opening catalogues. Keep outputs outside this skill.

## Choose a route

- **Deck:** read [scenarios](references/scenarios.md), then only the relevant
  [archetype](references/archetypes.md). Use `scripts/build_deck.py --schema`.
  Scenario defaults to report; page count follows content, not a duration quota.
- **Poster:** read [poster](references/poster.md). Use
  `scripts/build_poster.py --schema`. Plan graphics alongside type and grid:
  a supplied image, source-grounded diagram, or a coherent generated graphic
  group plus subordinate accents. Judge their balance from purpose, content,
  viewing distance and available space. Texture alone is not a graphic concept.
  Pure typography is an intentional choice, not the default shortcut.
- A deck's `scenario: poster` changes its character; only `artifact: poster`
  selects the independent poster canvas/families and removes deck chrome.

## Shared constraints

1. Preserve supplied facts, quotes and roles. Ask if usable content is missing;
   never invent labels/numbers to populate a design. Retain incidental deck
   detail in notes. Do not truncate copy or add pages to satisfy rhythm.
2. Use limited palette inks, generated paper/ink texture, and misregistration
   or overprint. Choose one primary dialect and a subordinate secondary dialect.
   User choices win; defaults handle unspecified settings.
3. Establish readable hierarchy, reserve visual regions, then measure type and
   place graphics. Each accent needs an anchor, emphasis, rhythm, metaphor or
   component function. Budgets are ceilings. Preserve quiet space; omit illegal
   decorations, never shrink a substantial graphic into confetti or loosen QA.
4. Measure with resolved fonts and shared `typefit`/Canvas geometry. Rearrange
   regions before reducing readable type. Explicit fonts must resolve; reported
   fallback is not validation of the missing font. Display layers share content,
   breaks and alignment; print/reverse offsets scale with fitted type.
5. No finished-artwork dependency: never scan old outputs or the web for a
   composition to imitate. Supplied photos use duotone/print treatment. An explicit
   style reference supplies color, grain/dot density and offset amplitude only;
   record those under `calibrated_from_reference`, content choices under `from_content`.
6. Preserve seed, palette, canvas, fonts and dialect in spec/sidecar. Input paths
   are spec-relative. Use `<stem>.style.json` and `<stem>-media/`; generated files,
   previews and reports stay outside the package. History/renderer state is per-user.

## Build and verify

Run from the skill directory with OUTPUT elsewhere. Deck background preparation
is in scenarios; poster builds generate their own background.

```bash
python scripts/build_deck.py --spec OUTPUT/deck.json --out OUTPUT/deck.pptx
python scripts/build_poster.py --spec OUTPUT/poster.json --plan --summary
python scripts/build_poster.py --spec OUTPUT/poster.json --out OUTPUT/poster.pptx
python scripts/qa.py --deck OUTPUT/artifact.pptx --json OUTPUT/qa.json
python scripts/layout_check.py --deck OUTPUT/artifact.pptx --json OUTPUT/layout.json
python scripts/render.py --deck OUTPUT/artifact.pptx --out OUTPUT/preview --keep-pdf --autodiscover
```

Choose the relevant builder. Fix geometry failures, rebuild, then render and
inspect hierarchy, print craft, important glyphs and graphic/text balance.
Rerun QA with `--render OUTPUT/preview --require-render` when previews exist.
Missing/stale previews are unverified, not passed; `--describe` proves renderer
discovery only. A missing renderer does not prevent editable PPTX delivery.
Do not claim PowerPoint verification from LibreOffice. No numeric aesthetic
score replaces judgment. Run non-render regression suites after engine changes.

Deliver PPTX, source spec, sidecar/media, reports and available PNG/PDF. Briefly
explain content/palette choices and the checks actually run.

## Load only when needed

- Palette/dialect selection: [palettes](references/palettes.md),
  [dialects](references/dialects.md); [motifs](references/motifs.md) for composition ideas.
- Graphic selection: `python scripts/elements.py catalogue --dialect C --safe --limit 8`.
  Add `--role hero` or `--json` as needed; [elements](references/elements.md) is an index.
- Fit/collision debugging: [geometry](references/geometry.md),
  [typography](references/typography.md). Decoration: [anti-clutter](references/anti-clutter.md).
- Engine edits: [design-system](references/design-system.md), `build_deck.py --design-system`.
- Delivery details: [checklist](references/checklist.md). Legacy failures:
  [anti-patterns](references/anti-patterns.md), only for the relevant symptom.
