# Poster print collage

Read this to change the look of an infographic poster after seeing a render.
The default needs no settings. Controls go in the outline's `look`, or in
`art_direction` when you write a full plan.

## What the builder sets

| Part | Treatment |
|---|---|
| Ground | Paper grain, a spot-ink disc and halftone screens off two corners, crop marks, a colour bar. Ink stays clear of every line of copy. |
| Masthead | Display title with a second ink out of register, a short accent bar on a hairline, and a torn-paper scene to its right. A long title, or a full sheet, runs the title across the width and drops the scene. |
| Lead | A wide torn sheet over a larger field, taped, with a highlighter on the emphasis words. A figure prints its numeral in two inks with its unit beside it. |
| Charts | A newsprint clipping with more of the page behind it. Bars share one zero and one line each. A ring or stacked bar keys each part with a swatch. |
| Quotation | A squared note, taped at its head, with one opening mark. |
| Plain modules | Alternate between a card on paper and open ground, across each gutter and down each column. |
| Steps, timelines, figures | Open ground under a printed column head. A percentage gets a ring. |
| Action | Reversed type on a torn strip of the first ink, with an accent spot. |
| Footer | A kraft stub that runs off the foot of the sheet. It deepens when the sheet has room. |

Copy, bars, rings, badges and rules are native and editable. Paper is one
picture above the printed ground. Deleting it in PowerPoint leaves a valid
plain poster.

The builder also chooses the sizes. The title takes the largest size the
masthead holds while the body stays near 20pt. A full sheet gives up title
size before the body goes to its 18pt floor, and a sparse sheet sets larger
body type before it leaves space. Steps, timelines, two-sided comparisons and
long charts take the full width. Other modules share two columns, and a module
left alone moves up beside a neighbour. These sizes are for A3 and smaller;
a larger sheet scales every size with its width (A2: body floor 25pt), so it
reads from the same distance and holds the same copy.

## Controls

| Field | Values | Use |
|---|---|---|
| `ink` | `cobalt-vermilion`, `plum-ochre`, `teal-coral` | The two spot inks and accent. |
| `masthead` | `auto`, `open`, `band` | `band` reverses the title out of a torn ink band. `auto` follows the seed. |
| `scene` | `auto`, `moon`, `stack`, `press`, `horizon`, `off` | The paper scene beside the title. |
| `display` | `serif`, `grotesque` | Title and heading face. |
| `collage_variant` | integer | Another arrangement of papers for the same layout. Defaults to `meta.seed`. |
| `paper` | `auto`, `none` | `none` keeps every module off paper. |
| `title_lines` | exact title fragments | Choose where the title breaks. |
| `columns` | 1, 2, 3 | Text columns for the module grid. |
| `keep_order` | `true` | Stop a column module moving up beside a lone neighbour. |
| `body_size` | points, at least the sheet's floor | The largest body size the builder may set. |
| `print` | `collage`, `flat` | `flat` is the plain sheet: no paper, ink fields or masthead. It takes `ornament`, `element_density` and the `collage` and `doodle` dialects. |

A module can set `"paper": "sheet"` or `"paper": "open"` to override the
alternation. `meta.scale` sets raster pixels per point for the paper and
ground (default 2; use 3 or more for a print file).

## Fixing a render

| Seen | Change |
|---|---|
| Title small, or no scene beside it | Shorten the title, set `title_lines`, or cut a module. |
| `adjusted:` says the body is at its floor | Cut or merge a module. A larger canvas does not help. |
| The run says the sheet stays half empty | Choose a smaller `canvas` or add a module. |
| Two heavy papers side by side | Set `"paper": "open"` on one module. |
| Sheet reads cold or busy | Try another `ink`, `scene` or `collage_variant`. |
| Reading order changed | The `adjusted:` line names the module that moved. Set `keep_order`. |
