# Classic PowerPoint archetypes

Use the [storyboard](deck-storyboard.md) to select a composition by the job it
does. This catalog describes classic spec slots for reproducing existing decks
or arranging an unusual slide. The storyboard compiler can also use dedicated
cover and quotation writers, plus editable evidence forms.

| Archetype | Use | Main spec slots | Background preset |
| --- | --- | --- | --- |
| `cover` | Editorial opening | `question`, `title`, `title_en`, `thesis`, `subtitle`, `aside`, `sticker` | `cover-bleed-tr` |
| `divider` | A change of subject or act | `index`, `title`, `title_en`, `aside` | `reverse-circle-br` |
| `data` | A dominant value with supporting context | `label`, `hero`, `unit`, `caption`, `delta`, `side`, `bars` | `corner-fade-br` |
| `features` | Rank a set against a focal proportion | `hero`, `hero_label`, `rows[{label,pct}]` | `corner-fade-tr-sm` |
| `quote` | Verbatim excerpt and provenance | `lines`, `attribution`, `source`, `highlight` | `corner-fade-tr-xs` |
| `grid` | A comparable set of options | `columns[{label,ours}]`, `rows[{label,cells}]`, `note` | `corner-speckle-tr` |
| `venn` | A meaningful intersection, printed as a lens | `left`, `right`, `centre`, `gap_label`, `gap_items`, `takeaway` | `edge-fade-left` |
| `numbered` | A numbered result or benchmark | `hero`, `label`, `gauge{rows}`, `takeaway` | `edge-fade-right` |
| `timeline` | A process or chronology | `items[{month,unit,name,desc}]` | `blob-corner-tl` |
| `ask` | A concrete decision or resource request | `asks[{value,unit,name,desc}]`, `target`, `aside` | `corner-speckle-tr` |
| `statement` | A thesis, pivot, or synthesis with few words | `lines[[text,size]]`, `sticker`, `body`, `note` | `cover-bleed-bl` |
| `closing` | A decision, next action, or final synthesis | `quote`, `target`, `big`, `sticker` | `reverse-circle-tr` |

Use `build_deck.py --schema` for complete slots and `make_textures.py presets`
for background options. A shared grid, page furniture and type scale establish
continuity. Shift visual weight when two adjacent pages have the same layout.
Group related points on one page when the audience benefits from reading them
together. See [scenarios](scenarios.md) for rhythm and word-band diagnostics.

## Measured region allocation

Cover titles wrap into larger measured multiline regions after reserving supplied
support/stickers. No internal decorative separator fills space. Closing and
statement rules follow the measured content, with statement stickers reserved
first. Venn side/intersection labels fit the actual ellipses; bottom captions and
takeaways have separate regions. Unfit labels fail instead of drifting outside.

Grid `column_weights` (alias `weights`, or per-column `weight`) must be positive
finite numbers and allocate real widths. Timeline descriptions measure against
their own columns' remaining height. Numbered gauges reserve four data rows
separately from the takeaway/support region. Long source text is never silently
cut to a fixed number of lines. See `typefit.py` for diagnostic fitting.
