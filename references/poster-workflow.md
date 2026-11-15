# English standalone poster workflow

This file is enough for a normal poster. Open another reference only when the
table at the end sends you there.

## 1. Read the brief

Settle the audience, where the poster hangs and from how far it is read, the
one takeaway and the action. Separate sources of fact from examples of style.
Keep quotations, names, figures, units and dates exact. The poster is written
in English and `meta.lang` is `en`. A poster is a summary: choose what earns
its place and leave the rest out.

## 2. Write the outline

Write one JSON outline. Each part states its copy once. The builder derives
the source inventory, the coverage ledger and the layout from it.

```json
{
  "title": "Fix it, don't bin it",
  "audience": "Neighbours walking past the hall",
  "purpose": "Posted on a noticeboard",
  "meta": {"seed": 1},
  "lead": {"stat": {"value": "1,240", "unit": "kg", "label": "of household goods kept out of landfill"}},
  "modules": [
    {"id": "mix", "title": "What comes through the door",
     "chart": {"type": "bars", "unit": "%", "points": [["Small electricals", 41], ["Clothing", 27], ["Bikes", 19], ["Furniture", 13]]}},
    {"id": "visit", "title": "How a visit works", "steps": ["Bring one broken item", "Sit with a volunteer fixer", "Take it home working"]},
    {"id": "why", "title": "Why it matters", "text": "Repair is the quietest form of recycling."},
    {"id": "quote", "quote": "If you can't open it, you don't own it.", "by": "Maker's Bill of Rights"}
  ],
  "action": "Bring one broken thing",
  "footer": "Riverside Hall, 14 Mill Lane. First Saturday, 10:00 to 13:00. Free."
}
```

`lead` and each module carry one block. A module also has an `id` and usually
a `title`.

| Block | Value | Renders as |
| --- | --- | --- |
| `statement` | text, optional `emphasis` | A large sentence. As the lead, its closing phrase is highlighted |
| `text` | text | A heading and one or two sentences |
| `list` | strings or `[cue, detail]` pairs | Numbered points with ledger lines |
| `stat` | `{value, unit, label, body}` | A figure in two inks with its unit, a ring for a percentage |
| `chart` | `{type, unit, points: [[label, number]]}`; type is `bars`, `columns`, `line`, `ring` or `stacked` | A newsprint clipping |
| `versus` | two `[label, text]` pairs | Two sides across the sheet |
| `steps` | strings or `[label, text]` pairs | A numbered sequence across the sheet |
| `timeline` | `[label, text]` pairs | Dated nodes on a line |
| `quote` | the exact words, optional `by` | A squared note with an opening mark |

Choices that decide how the poster looks:

- **Title: two to five words.** It is set as large as the masthead holds,
  beside a torn-paper scene. A long title loses the scene and its size. Put
  the qualifier in the lead.
- **Lead: the one thing to take away.** A `stat` or a `statement`, read from
  across a room. It gets its own wide sheet.
- **Three to five modules.** Mix the blocks: one chart at most, one
  quotation, step labels of six words or fewer. Plain modules alternate
  between paper and open ground, and the builder may move one up beside a
  lone neighbour.
- **Close with `action` and `footer`.** The action prints reversed on an ink
  strip. Date, place and credits share one footer line on a kraft stub.

Optional keys: `canvas` (`a3_portrait` by default, also `a2_portrait`,
`a4_portrait`, `4:5`, `square`), `look` for the controls in
[print collage](poster-print-collage.md), and `"paper": "sheet"` or `"open"`
on a module.

## 3. Build

```bash
python scripts/poster_run.py --outline outline.json --out POSTER_OUTPUT --auto
```

The run prints a few lines. `sheet:` gives the masthead, the title size and
where each module sits. `adjusted:` names a module that moved or a sheet at
its body floor. `advice:` notes copy that builds but will not look its best.
A failure prints what to change: copy that does not fit names the tallest
rows, and a sheet that stays half empty asks for a smaller canvas. Type is
set for the sheet and scales with it (18pt body floor on A3, 25pt on A2), so
copy that does not fit is cut or merged; a larger canvas gains no room. Do not
open the logs or the plan to learn what happened. Keep output outside the
skill and give each poster its own folder.

## 4. Look once

Open the image on the `review:` line. It shows the full sheet, a 10% thumbnail
and a blur. Check that the title and lead read first, that every figure and
label is the source's, and that no module is crowded or lost. Change the
outline and rebuild; an unchanged outline is restored from the cache.

Deliver `poster.pptx`, the preview PNG and the outline. Copy, bars, rings and
badges are native and editable. Say which renderer made the preview.

## Other cases

| Case | Read |
| --- | --- |
| Change ink, masthead, scene, paper, or get the plain sheet | [print collage](poster-print-collage.md) |
| A ledger against an external source document, adapted copy, or a legacy spec | [content planning](content-planning.md), [input formats](input-formats.md) |
| Dense unchanged copy (`mode: editorial`) and its controls | [poster art direction](poster-art-direction.md) |
| Renderer setup, audit mode, cache, timings | [harnesses](harnesses.md), [performance](performance.md) |
| A hash-bound review record | `python scripts/poster_review.py --png POSTER_OUTPUT/preview/page-0001.png --out POSTER_OUTPUT/visual --plan POSTER_OUTPUT/poster.plan.json --review POSTER_OUTPUT/visual/review.json` |
