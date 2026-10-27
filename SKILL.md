---
name: riso-slides
description: Create editable Risograph information posters and slide decks from source content, with spot inks, print texture, measured type, diagrams and charts. Use for one-image explainers, event/data posters, reports, proposals or course presentations.
---

# Riso Design v4.0

Resolve one Python interpreter and reuse it. Keep outputs outside this skill.
Run `python scripts/doctor.py --out OUTPUT` once per environment; real renderer
probe results are cached. Read [harnesses](references/harnesses.md) only for setup failures.

## Stage 0 — mandatory, shared by poster and deck

Read [content planning](references/content-planning.md) before authoring.
State purpose, audience, thesis and CTA; inventory source atoms, then group and rank them.
Use `verbatim` for final copy, `adapt` for speeches/articles. Never invent facts or labels.
Retain every kept/merged/condensed/cut atom in the ledger; protect numbers, names and quotes.
Write content-plan.json; the command below lints, compiles and runs with source binding.
Existing-spec conversion uses `--from-spec INPUT.json` in place of `--plan content-plan.json`.
`--skip-plan` is an explicit, recorded reproduction escape; never claim Stage 0 passed.

```bash
python scripts/poster_run.py --plan content-plan.json --out OUTPUT --auto
```

## Poster

New content plans default to `mode: infographic`; dense unchanged old specs use
`mode: editorial`. [Input formats](references/input-formats.md) describes compatibility.
Read the computed source profile first; never add data to make an infographic.
Budgets and text/data balance interpolate with evidence level; body ≥18pt on A3.
See [evidence scaling](references/evidence-scaling.md); overrides need a recorded reason.
Low-data sources use source-bound typography, definitions, quotes and contrasts.
Change grouping/columns before reducing copy. Adaptation requires ledger entries.

Information types choose native evidence forms: statistic, comparison, process,
part-whole, timeline, quote and logistics. Data drives drawing; do not place shapes manually.
**Default elements are enabled: use them, do not omit them.** Set only
`art_direction.element_density: sparse | normal | rich` (default normal).
See [element catalogue](references/elements-catalog.md) for data forms and glyphs.

- Do bind a glyph to a claim; do not float an unrelated motif in empty space.
- Do provide ordered step data; do not draw connectors one tool call at a time.
- Do inspect quota warnings; do not cover reading text to satisfy an element count.

Use `--draft` for a text/geometry PNG without LibreOffice. It is not a final render.
Use `--variants --draft` to compare columns once; `--variants --auto` batches conversion.
Use `--preflight` for capacity diagnostics. `--describe-spec` exposes controls.
Routing flags: `--system` or `--autodiscover`, or `--kit PATH --node PATH`.
`--mode audit` bypasses render cache. Detailed evidence lives in files; summary.json is the entrypoint.
Both runners default to the system route. See [performance and cache](references/performance.md).
For editorial overrides read [art direction](references/poster-art-direction.md).

## Deck

Use the same Stage 0 with `target: deck`: one assertion and 1–4 source-bound modules
per slide; use module `page` to group explicitly and keep narration in notes.
Evidence selects page types; all new pages share the poster form writer. `--draft` skips LibreOffice.
Existing page types remain available; read [scenarios](references/scenarios.md)
and only the relevant [archetype](references/archetypes.md).

```bash
python scripts/deck_run.py --plan content-plan.json --out OUTPUT --auto
```

## Final inspection and delivery

Inspect full PNG, thumbnail and blur. Scaffold only prefills provenance, never scores:

```bash
python scripts/poster_review.py --png OUTPUT/preview/page-0001.png --out OUTPUT/visual --plan OUTPUT/poster.plan.json --review OUTPUT/visual/review.json
```

Fill reviewer/viewed fields, 9 scores and 0–5 located weaknesses after inspection.
Keep the hash-bound spec/plan/style/QA/manifest/review chain. Missing or stale PNG is UNVERIFIED.
Deliver editable PPTX, source + content plan/ledger, plan/style/media, QA, timings,
summary and available PNG/PDF/review. Geometry metrics do not establish aesthetics.
LibreOffice does not establish Microsoft PowerPoint rendering.
No external images, downloaded fonts or network calls are needed by the pipeline.
Maintenance tests live in the source checkout, outside the blank runtime package.
After engine edits, run its regression suite and render representative poster/deck inputs.
On demand: [design system](references/design-system.md), [palettes](references/palettes.md),
[typography](references/typography.md), [delivery checklist](references/checklist.md).
