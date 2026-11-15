# Deck paper collage

Torn paper is the container for pages that list information. The other
content pages take turns between copy on a sheet and open copy with a paper
scene. The cover and section dividers keep their v4.5 design, and
`collage: off` returns any page, or the whole deck, to v4.5.

## Where paper appears

| Page | Default |
| --- | --- |
| Three or four points with a cue and a detail | One torn card per point over a field of colour |
| Five to eight points with a cue and a detail | Two ruled sheets side by side, the second a little lower |
| Points without a detail | One ruled sheet with a paper scene beside it |
| Comparison | One sheet per side |
| Chart | A newsprint clipping, with more of the newspaper beside it |
| Statement, case, definition, figure, steps, timeline | These pages take turns. The first sets its copy on a sheet with a scene beside it, the next keeps open copy with a scene, and so on through the deck. A page with no room for either stays open |
| Featured quotation | The classic composition on a flooded ink field with a dot screen |
| Other quotations | The open page with a large mark and overprinted circles |

A deck carries at most two flooded pages. When the dividers or the close
already use them, or a flooded page sits next to the featured quotation, the
quotation keeps its paper and takes the circles instead.

## Inside a sheet

A sheet of copy needs more than one voice and a little printed structure.

- **Ledger lines** run in the gaps between the rows of a list.
- **A margin line** in spot ink stands between the numerals and the points of
  an ordered list. The numerals are set larger than on the open page.
- **A lead-in.** A point written as `cue: rest` or `cue — rest` sets the cue
  in the heading face and ink, and the rest as body copy.
- **A column head.** A sheet of running copy opens with a short bar of spot
  ink on a hairline.
- **A highlighter.** The words named in `emphasis` get a dry stroke of spot
  ink under them. On the open page the same words print in spot ink. Without
  `emphasis`, a short closing phrase after a colon or dash is used.

The lines and bars are printed on the sheet, so they turn and tear with it.
The copy stays native text. Nothing is printed under body copy.

## Material

A torn edge shows the white fibre core of the sheet and wanders at several
scales. A cut edge is nearly straight. Most sheets have one or two torn edges.
Sheets cast a tight contact shadow and a soft wider one, with the light from
the upper left. They lie a degree or two off square, and the copy on a sheet
turns with it. A flood has uneven density and pinholes. A screen is a field
of round dots that fades across the sheet. Data marks carry a second plate
slightly out of register.

A paper scene is a small abstract composition: torn strata under a paper sun,
a fanned stack of offcuts, a spot rising behind a torn sheet, or a corner of
the newspaper. Scenes and field colours rotate so neighbouring pages differ.

## Controls

Set `meta.collage` for the deck and `collage` in a page's direction.

| Value | Result |
| --- | --- |
| `auto` | The default described above |
| `lists` | For `meta.collage` only: paper on pages that list, and an occasional scene elsewhere |
| `rich` | Put this page's copy on paper as well, with a scene |
| `quiet` | Paper under the copy, without a scene |
| `scene` | Open copy with a paper scene beside it |
| `off` | The v4.5 page |

`meta.collage: rich` sets every content page on paper. An empty
`element_pool`, `paper_collage: off` or `case_collage: off` keeps a page open.
`meta.elements: false` turns paper off across the deck. `paper_layout: single`
asks for one sheet and `staggered` for cards. A `background` or `reverse`
written for a quotation page replaces its default field.

Paper needs room. The builder gives room back in this order: body size down
to the 18 pt floor, tighter insets, one sheet instead of cards, a smaller
title, then open copy with a scene. A page the builder adjusted is listed in
the run output and under `refinement_fallbacks` in the style sidecar. Shorten
the headline or split the page when a page you care about loses its paper.

## Pictures

A content page may carry `image`: a file path, or `{path, treatment}`. The
picture takes the place of the paper scene. It is cropped to fill a print,
separated into the deck inks as halftone screens, and taped to the page with
a torn lower edge and a sliver of colour behind it.

| Treatment | Result |
| --- | --- |
| `duotone` | The default. The second ink carries the middle tones and the first ink closes the shadows |
| `mono` | One ink |
| `keep` | The source colours laid on the stock |

A page with no room for the print is built without it and listed as adjusted.
The picture is part of the background plate, like the other papers.

## What stays editable

Text, chart marks, rules and quotation marks are native PowerPoint objects.
The papers and their printed lines are part of the slide background picture.
Editing wording in PowerPoint does not move a sheet or a highlighter, so
rebuild after a change that alters line breaks.

## Maintaining the look

`deck_paper_stock.py` draws sheets, `deck_collage.py` arranges them,
`deck_sheet_type.py` sets the type and furniture inside a sheet,
`deck_picture.py` re-inks a supplied picture, and `deck_plate.py` prints the
result onto the page. The builder first draws
every page exactly as v4.5 did and then redraws the pages that take paper.
Keep that order: it holds the random sequence steady, which keeps the cover
and dividers identical from release to release. After a change, render the
same plan with `meta.collage: off` and compare every page with the v4.5
render pixel by pixel, then compare the cover and dividers of the default
render. `collage: off` also keeps the v4.5 title size, so it is the whole
v4.5 page.

Deck work stays in deck files. Deck-only code lives in `deck_*.py`,
`build_deck.py` and `compose.py`. Do not change `source_profile.py`,
`chart_qa.py`, `make_textures.py`, `content_plan.py` or any poster module for
a deck feature: fork what you need into a `deck_` module, as
`deck_source_profile.py` and `deck_chart_qa.py` do. In `qa.py`, a deck rule
sits behind an explicit `canvas.artifact == 'deck'` branch that calls a deck
module. After deck changes, build the same poster plan with the previous
release and the working tree and compare `poster.plan.json`,
`compiled-spec.json`, `qa.json`, `layout.json` and the background image.
