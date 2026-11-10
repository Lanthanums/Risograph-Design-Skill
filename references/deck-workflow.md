# English PowerPoint workflow

## Read the brief and sources

Determine audience, viewing conditions, purpose, and decision or takeaway. Distinguish
sources of factual copy from examples of visual style and from templates the user
asked to match. Inventory the material with the deck planner. Keep the original
source, SHA, atoms and coverage ledger. Use verbatim for approved copy and adapt for
speeches, prose and rough briefs. Keep exact quotes, names, figures, units, dates and
qualifications. Set `meta.lang: en`.

## Storyboard before production

Read [storyboard](deck-storyboard.md) and [deck composition](deck-composition.md).
Use [English typography and dense copy](deck-typography-and-lists.md) to plan
title breaks, list density and any information-bearing paper panel before rendering.
Write one complete storyboard in the deck content plan before building any slides,
including a short deck-wide rationale and a page row for each intended slide.
For every page, decide what the viewer sees first, what evidence stays visible,
how the eye moves, what the print treatment does, and how the next slide follows.
Nominate the single most important standalone quotation for the classic treatment
when appropriate. For charts, plan the data columns and source line together.
For sparse cases, decide whether a localized paper cutaway adds a meaningful visual.
Use purpose, source content and constraints to choose the composition. Review a
few consecutive slides on paper before committing to the full sequence. Save
the complete storyboard and share its path and sequence before building when
the interface supports progress messages. For a planning-only request, deliver
the storyboard. Continue to production when the request includes a deck, with
a review checkpoint when the user asks for one.

Use explicit module `page` IDs and `page_directions` to connect the storyboard to
the compiler. The plan carries English visible text and narration separately.
Run the prebuild lint on the actual plan. Fix mismatches in the plan before generating
the deck.

```bash
python scripts/deck_content_plan.py --plan deck-content-plan.json --require-storyboard --lint --storyboard-out storyboard.md
python scripts/deck_run.py --plan deck-content-plan.json --require-storyboard --out DECK_OUTPUT --auto
```

Use [scenarios](scenarios.md) and the relevant [archetypes](archetypes.md) for
classic input or to see alternate compositions. To reproduce an existing deck
spec, use `deck_content_plan.py --from-spec INPUT.json --out PLAN.json`.
The migration preserves existing page types and does not author a storyboard.
Use `--skip-plan` only for explicit compatibility runs.

## Produce and inspect

Use `python scripts/doctor.py --out DECK_OUTPUT` once per environment if needed.
The system renderer is the default. See [performance](performance.md) and
[harnesses](harnesses.md) for cache and renderer setup. `--draft` gives a quick
text/geometry check. Use rendered PNGs for review of texture, composition and
actual type. Native text and source evidence stay editable. Read [typography](typography.md)
for measurement and [palettes](palettes.md) for ink choices.

Inspect the contact sheet, every full image and any relevant thumbnail or blur.
Check source coverage, reading order, meaningful content density, readable type,
print craft, varied pacing and the match between storyboard and deck. Revise the
storyboard with the layout if they diverge. When reviewing independently, use the
requested model and reasoning settings and record actual image inspection. A
technical pass or a cache hit does not establish visual approval. Deliver the
editable PPTX, storyboard and source plan, and available preview and verification
evidence. Name the renderer actually used.
