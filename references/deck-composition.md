# English deck composition

Use this guide for English PowerPoint decks.

Before composing, distinguish projected talk support from a standalone reading deck.
Inventory required claims, examples and qualifications. Use explicit module `page`
assignments: the compiler's fallback groups atoms, not arguments. A short source
usually needs fewer pages; do not turn every sentence into a slide. Preserve the
source ledger and never invent data or remove qualifications to simplify a layout.

For each page, sketch its reading order and choose a visual anchor. The anchor may
be a typographic phrase, comparison, annotated diagram, image or data figure. A
large title alone is not necessarily an anchor. Keep support legible and close to
the evidence it explains. Move layout and grouping before shrinking text. Do not
put necessary evidence only in notes; notes carry narration, not missing claims.

Compare two compositions for representative content before extending the system:
for example an editorial spread and a diagram-led explanation. These are choices,
not mandatory templates. Use hierarchy, scale contrast, alignment and controlled
layering to create visual presence. Extra isolated badges and random motifs do
not repair weak composition. Avoid equal card grids as a default for prose.

Review the deck at full size and as a contact sheet. Check meaningful fullness,
reading order, evidence completeness, typographic contrast, relation of visual
forms to the argument, and rhythm between adjacent slides. Quiet emphasis pages
are valid if supported by the narrative. Neither word count nor occupied-area
quota establishes quality. Do not fill all whitespace or impose a fixed number
of elements per page.

Reference transfer: describe principles (scale hierarchy, visual weight, rhythm),
then apply them to a different topic and palette. The verified SkillHub 2.1.0
reference uses editable Georgia display type with measured offset plates,
small registration furniture, quiet paper fields, and quote-attribution groups.
Adapt their relative visual weights and reading order to the current brief.
Choose new coordinates, motifs, palette, and slide sequence for the material.

When independent review is requested, use the user's chosen reviewers and model
settings. Ask for a brief first-impression judgment before detailed inspection:
which slide feels empty, crowded or monotonous, and what specific change helps?
Review actual renders, not JSON or a verbal description. Record the requested
settings separately from verified runtime settings; a prompt is not proof of a
runtime setting. A reviewer without image access provides structural feedback,
not a visual verdict. Compare identical source content before and after, and test
at least one different topic. Keep disagreements visible rather than averaging
away located defects. Technical QA does not establish aesthetic quality.

## Deck-only controls

Use `page_directions` in the content plan to override a particular page's art
direction, keyed by its explicit module `page` id. For example:
`"page_directions": {"comparison": {"title_rule": false, "vertical_align": "center", "columns": 2}}`.
Unknown page ids fail instead of silently ignoring the author's choices.
Use `composition: cover` or `composition: quote` for source-bound editorial
frames. See [the storyboard controls](deck-storyboard.md).
`quote_layout: auto` reserves the classic pull-quote treatment for at most one
standalone quotation in the deck. Decide which quotation carries the argument
and set `quote_priority: featured` on that page. Use `supporting` for a page that
should never receive the automatic classic treatment. An explicit `classic`
request is a nomination for the same single slot. Leave the slot unused when
the source or rhythm calls for a quieter treatment. Other quotes use a
centered `broadside` (best for short excerpts), a `margin` with separate credit,
or a `folio` with a paper face. Keep a visible opening quotation mark in every
layout, including an inline pull quote, and keep source words and credits exact.
The fitter can choose another layout when the copy or credit needs more room.
`vertical_align` accepts top, balanced (default), center or bottom within measured
remaining space. `title_rule: false` removes the title underline. Body/title sizes
and columns can also be overridden per page. Source content and ledger stay bound.
Use `content_width` from `.45` to `1` to set the evidence band's share of the
safe width. A narrower left-aligned band can group chart labels and leave a
continuous margin for a quiet field. Keep a wide band when comparison labels
need it. The title and footer retain their own width.

## Statistical pages as printed spreads

Start with the comparison the audience needs to make. Give bars a common zero,
use aligned label and value columns, and leave units and qualifications where
the data is read. Use a short rule, a fine row separator, direct values, and a
clipped ink screen inside bars as newspaper furniture. Keep dot patterns off
the value text and the quantitative edges. Use a boundary where consecutive
part-to-whole segments share ink. For a trend, keep ordered labels and reserve
headroom for point values. Keep a source or caveat line close to the graphic.

When the source provides a companion measure, exception, or second small
comparison, put it alongside the main graphic as a narrower column or directly
below with a shared baseline. Give the more important chart the wider column.
Use two columns only if the smallest labels still fit. If a slide has only two
numbers, make their comparison clear and leave a calm field. Do not manufacture
additional statistics, categories, or interpretations to fill the page.

On sparse case pages, use a small anchored cutaway when it supports the story
and there is a measured opening. `case_collage: off` keeps a deliberate pause,
and `on` requests the treatment if it fits. `case_collage_glyph` accepts a native
glyph from the catalogue when the author can tie it to the source. See
[paper construction and prompts](deck-paper-collage.md).

Use explicit module `page` assignments to compose arguments. Parallel members of
one semantic group may share a row; `keep_together: true` preserves a column lock.
Four to six step-flow items use two columns by default; set visual_data.orientation
explicitly to horizontal or vertical when the content needs that reading order.
Do not create filler steps to reach a grid count. The typography fitter may enlarge
short content while preserving the body floor; an explicit large title remains an
author choice. Review wraps after rendering, especially for mixed scripts.

## Title plates and print marks

New storyboard decks use two independently offset plates under the editable
front text. Covers and reversed evidence pages default to `type_plates: spot`.
Other evidence-page titles default to `quiet`. Use `spot` on a deliberate
headline or `off` for a quiet factual title. Text under 30pt stays a single
impression. Inspect the plate edges at thumbnail and presentation size.

`print_marks: rich` is the default for new storyboard decks. It places up to
three groups of editable spot-ink accents in measured open regions. Use
`balanced`, `quiet`, or `off` for a different page rhythm. Pick the ink field,
accent role and visual anchor together. A small registration tick can continue
the frame, a screen can cue an entry point, and a two-ink swatch can show the
palette near a focal title. Change geometry when important copy competes with
a mark. The sidecar records each group's bounds, position and page role.

Use `meta.elements: false` to turn decoration off across the deck. An empty
`element_pool` keeps a page quiet by default. An explicit `print_marks` can
still enable native print accents on that page. The pool controls the existing
catalogue elements. The layout protects text and data from decoration.

## Composition pass before building a new deck

The automatically compiled outline is a content arrangement, not finished art
direction. For each content page, record (in the working plan, not on the slide):
its visual protagonist, the relation the viewer should see, the reading order,
and the evidence that must remain visible. Choose the protagonist's scale before
placing supporting copy. A repeated title strip above small prose is not a default
finished composition, even if it fits and passes geometry checks.

For a short source, first compare a larger source-bound typographic composition,
a relationship diagram, and merging adjacent content. Do not select the same
solution for every page. Distinguish title size from content presence: enlarging
all headings can leave the evidence visually weak. An illustration or expressive
native shape may carry the protagonist when it explains the content; several tiny
unrelated symbols do not perform that role.

Render representative contrasting pages early. Inspect at presentation size and
in a compact contact sheet: can the audience see the relationship without reading
every sentence, and can it find the supporting detail? Revise content geometry
before adding print effects. Do not use source-atom count, a decoration quota, or
a technical pass to substitute for this judgment. Preserve deliberate pauses and
emphasis slides rather than filling every page mechanically.


## Print treatments

Treat the v4.5 shared print system as the compatibility baseline. When tuning a
page family, keep the existing cover, section divider, paper backgrounds,
overprint pairings, dot fields and deck-wide mark density. Limit new geometry
to the requested page families. For maintenance, render the same English
source with both versions and the same renderer and DPI. Compare protected
pages pixel by pixel and check the background plates by hash.

Use the classic archetypes for deliberately authored report, lecture and
narrative compositions. The 2.1.0 report fixture pairs a misregistered cover,
a dominant data numeral, a quiet comparison grid and reversed closing pages.
Carry the sequence and relative scale across subjects. Pick inks and corner
positions for the current material.

For content-plan pages, the evidence form controls the layout. A short single
statement gets a wider title and a measured focal column. A chart, sequence
or comparison keeps its native editable form. The printed substrate is
chosen from the page archetype, and measured text regions receive a quiet
paper field.

Use `backgrounds` in a legacy spec, keyed by the one-based slide number, or
`background` in an authored page. A field accepts a named `preset` and
explicit overrides such as `reverse`. External media is used when declared.
Storyboard decks default to full print grammar and use the resolved display
serif for headings. The other English roles already use Georgia where available.
Choose a quieter `meta.print_grammar` or override font roles with `meta.fonts`
when the subject, a template, or the labels call for a different system.
Classic text and print settings remain available with the current renderer
and full-run cache.
