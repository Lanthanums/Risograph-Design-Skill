# Input formats

Use one Python interpreter for every command; keep outputs outside the skill.
Start with [content planning](content-planning.md). Bind numbers, names and quotes
to the supplied source and record adaptations in the coverage ledger.

## Existing specs

```bash
python scripts/content_plan.py --from-spec INPUT.json --out content-plan.json --to-spec planned-spec.json
python scripts/poster_run.py --plan content-plan.json --out OUTPUT --auto
```

For decks add `--target deck` to conversion and use `scripts/deck_run.py`.
Conversion preserves supplied content and existing page types. Dense unchanged
poster specs use editorial mode; new information posters use infographic mode.
Budgets and forms follow the [source evidence profile](evidence-scaling.md).
Approved copy uses `verbatim`; authorized condensation uses `adapt`.
`--skip-plan` records that planning was skipped; it does not certify planning.

## New plans

```bash
python scripts/poster_run.py --plan content-plan.json --out OUTPUT --auto
python scripts/deck_run.py --plan deck-content-plan.json --out DECK_OUTPUT --auto
```

Use `target: poster` or `target: deck`. Each deck content page has one assertion
and one to four source-bound modules. Assign the same `page` to group modules,
use `slide_kind: section` for sections and keep narration in notes.

## Preview and review

`--draft` avoids LibreOffice. Poster drafts stop at planning; deck drafts also
build and check the editable PPTX. Drafts simplify typography and omit full print
materials. Use final renders for visual judgment. Poster `--variants --draft`
compares columns one through three.

`--auto` builds, checks, renders and writes rendered QA, timings and a manifest.
Both runners support `--system`, `--autodiscover` or `--kit PATH --node PATH`.
System LibreOffice is the default. Single-page posters support dimension-checked
direct PNG; decks keep PDF and rasterize all pages.

Inspect full images, thumbnails and blur. Scaffolds never assign scores.
Missing/stale images remain unverified; LibreOffice does not certify PowerPoint
appearance. See [performance and cache](performance.md) for fast/audit behavior.
