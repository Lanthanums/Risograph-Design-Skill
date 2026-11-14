# Deck paper collage

Content pages of an English storyboard deck are set on torn paper. The cover,
section dividers and the one classic quotation keep their v4.5 design, and
`collage: off` returns any page, or the whole deck, to v4.5.

## What is on the page

Each collage page has three kinds of material, in this order of weight.

1. **One dominant field.** A large torn sheet in a spot ink, kraft, or a
   halftone screen. It sits behind the copy and gives the page its colour.
2. **Reading faces.** Light sheets under the measured copy. Text and data
   marks are printed on a face, with a clear inset on every side. Faces are
   bone white, newsprint for charts, or faint grid paper for notes.
3. **Small things.** A sliver of a second colour under one corner, a strip of
   masking tape, a cut paper spot, a pencil mark. Use few of these.

A torn edge shows the white fibre core of the sheet and wanders at several
scales. A cut edge is nearly straight. Most sheets have one or two torn edges
and the rest cut. Sheets cast a tight contact shadow and a soft wider one,
with the light from the upper left on every page. Sheets lie a degree or two
off square, and the copy on a reading face turns with its sheet.

Ink on paper behaves like riso ink. A flood has uneven density and pinholes.
A screen is a field of round dots that fades across the sheet. Two inks that
overlap multiply. Data marks carry a second plate slightly out of register.

## Page families

| Page | Composition |
| --- | --- |
| Points with a cue and a detail | One torn card per point, scattered across two uneven lanes over the field. Three or four points. Ordered lists keep their numerals. |
| Short checklist | One reading sheet over a larger sheet that shows on two sides, with a paper scene beside it. |
| Chart | A newsprint clipping. Bars are thick with bold values on hairlines. A trend line has a fading screen under it. More of the newspaper shows behind and beside the clipping. A short companion note sits on grid paper. |
| Statement, case, definition, single figure | Copy keeps a reading measure of about 60% of the width on one sheet. A paper scene fills the opening. |
| Comparison | One sheet per side, the second a little lower. |
| Steps and timelines | One long strip under the sequence. |
| Supporting quotation | The words on a torn sheet, a large quotation mark hanging across its top edge, the credit on a small taped slip. |
| Several modules | One sheet per module. The first gets the field and the rest stay quiet. |

A paper scene is a small abstract composition for a large opening: torn strata
under a paper sun, a fanned stack of offcuts, a spot rising behind a torn
sheet, or a corner of the newspaper. Scenes and field colours rotate through
the deck so neighbouring pages differ. A scene is skipped when the opening is
too small to hold it comfortably.

## Controls

Set `meta.collage` for the deck and `page_directions.<id>.collage` for a page.

| Value | Result |
| --- | --- |
| `auto` | The default. Collage on every eligible content page. |
| `rich` | Request the full composition on this page. |
| `quiet` | Reading faces, field and tape, without a paper scene. Use for a dense page or a deliberate pause. |
| `off` | The v4.5 page, with no paper. |

An empty `element_pool`, `paper_collage: off` or `case_collage: off` also
keeps a page at v4.5 unless `collage` is set on it. `meta.elements: false`
turns collage off across the deck. `list_order`, `list_layout`,
`paper_layout: single | staggered`, `quote_layout` and `quote_priority` keep
their meaning and choose among the collage layouts.

Paper needs room. When a page is tight the builder gives room back in this
order: body size down to the 18 pt floor, tighter insets, one sheet instead of
cards, a smaller page title, then papers beside open copy. If nothing fits,
the page falls back to v4.5 and the reason is recorded in
`refinement_fallbacks` in the style sidecar. Shorten the headline, split the
page, or set `collage: quiet` when a page you care about falls back.

## What stays editable

Text, chart marks, rules and the large quotation mark are native PowerPoint
objects. The papers are printed into the slide's background picture, together
with the page's paper texture and dot field. Editing the wording in PowerPoint
does not resize a sheet, so rebuild from the plan after a change that alters
line counts. The style sidecar lists every piece under `paper_collage` with
its role, stock, rectangle and rotation.

## Review

Look at the contact sheet first, then each page at full size.

- The assertion reads first at thumbnail size. The field supports it and does
  not compete with it.
- Every line of copy sits fully on its face with a clear inset. No dot screen
  runs under body text.
- The page has one dominant sheet, a clear second level, and only a few small
  things.
- Neighbouring pages use different fields and scenes.
- The cover, dividers and classic quotation match the v4.5 render of the same
  plan. Compare them pixel by pixel when maintaining the skill.

## Maintaining the look

`paper_stock.py` draws sheets, `deck_collage.py` arranges them, and
`deck_plate.py` prints them onto the page. To study a new stock or edge,
render a proof sheet of pieces on a deck background and judge it at slide
size before wiring it into a page family. Useful things to look at in
reference collages: how far a tear wanders compared with its fine fuzz, how
wide the exposed core gets where a flap tore away, how tight the shadow is
where sheets touch, and how few colours a good page uses.

The builder first draws every page exactly as v4.5 did, then redraws the
content of collage pages. Keep that order. It holds the random sequence
steady, which is what keeps the cover, dividers and classic quotation stable
from one release to the next.
