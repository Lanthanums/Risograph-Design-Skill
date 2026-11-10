# English standalone poster workflow

Read the brief and sources for an independent poster. Identify audience, viewing
distance, canvas and action. Read [poster content planning](content-planning.md)
before authoring. Keep a separate source inventory, SHA, coverage ledger and plan.
Use `meta.lang: en`. Preserve final copy in verbatim mode. Adapt prose with
coverage and reasons for cuts. Protect quotations, proper names, and quantities.

```bash
python scripts/poster_run.py --plan content-plan.json --out POSTER_OUTPUT --auto
```

New plans default to `mode: infographic`. Use `mode: editorial` for dense
unchanged legacy copy. For migration see [input formats](input-formats.md).
Use the computed source profile and [evidence scaling](evidence-scaling.md)
before choosing the forms and density. Keep A3 body at least 18pt. Adapt grouping
and columns before cutting copy. Use source-bound typography, definitions,
quotations and contrasts for low-data sources. Charts need supported data.

Use native evidence forms for statistics, comparisons, sequences, part-whole,
timelines, quotes and logistics. Bind glyphs to their evidence. The English
infographic default uses one measured title rule with editable evidence graphics.
Set `art_direction.ornament: classic` for the anchored ornament treatment and
`element_density: sparse | normal | rich` when the brief calls for a density
override. See [elements](elements-catalog.md) and [poster art direction](poster-art-direction.md).

Use `--preflight` for capacity, `--describe-spec` for controls and `--draft` for a
geometry preview. `--variants --draft` compares columns and `--variants --auto`
batches conversion. The default is the system route. See [performance](performance.md)
and [harnesses](harnesses.md) for renderer setup and audit mode. Use an isolated
output directory. `--skip-plan` is a recorded compatibility escape.

Inspect the full PNG, thumbnail and blur for hierarchy at reading distance,
evidence completeness, ink and paper, graphic balance and edge tension. Review
unused space against the brief and format.

```bash
python scripts/poster_review.py --png POSTER_OUTPUT/preview/page-0001.png --out POSTER_OUTPUT/visual --plan POSTER_OUTPUT/poster.plan.json --review POSTER_OUTPUT/visual/review.json
```

Complete the review fields only after viewing the render. Keep the hash-bound
plan, style, QA, manifest and review. Deliver the editable PPTX, poster preview,
source/ledger, and verification evidence. Identify the renderer actually used.
