# Shared native elements — use defaults, do not omit

Set `art_direction.element_density` to sparse, normal (default), or rich.
The engine chooses collision-free content anchors and reports actual counts.
Recommendations: sparse 4–7 / 3 families; normal 8–14 / 4; rich 12–20 / 5.
They are warnings, not permission to put marks over reading text.
No single garnish >6% page area; all garnish ≤10%. Every mark has a text anchor.

| Element | Anchor | Information type | Module example |
|---|---|---|---|
| underline | last baseline | claim / title | `{"visual":"icon-bullet"}` |
| pin | heading corner | definition / example | `{"visual":"icon-bullet","visual_data":{"icon":"pin"}}` |
| separator | label end | comparison | `{"visual":"bar-compare","visual_data":{"items":[]}}` |
| corner | module heading | any | `{"element_density":"normal"}` |
| tape | heading edge | quote / example | `{"element_density":"rich"}` |
| number + glyph | source statistic | statistic | `{"visual":"big-number","visual_data":{"value":"source","label":"source"}}` |
| repeated glyph | source count | statistic | `{"visual":"pictogram-row","visual_data":{"count":4,"highlight":2,"icon":"person","label":"source"}}` |
| connected badges | ordered steps | process_step | `{"visual":"step-flow","visual_data":{"items":[{"label":"source"}]}}` |
| ring / stacked bar | part labels | part_whole | `{"visual":"ring","visual_data":{"items":[]}}` |
| track | ordered events | timeline | `{"visual":"timeline","visual_data":{"items":[]}}` |
| footer ticket | metadata | logistics / source | `{"level":4,"visual":"ticket","weight":0.25}` |

Data examples show structure only; substitute source values. Never copy example counts.
Forms also include before-after, versus, pull-quote and stamp. The same module API
is used by the deck `infographic` page archetype.

Geometric glyphs: person, house, tool, clock, coin, leaf, document, chat, check,
cross, arrow, star, bulb, gear, calendar, location, heart, shield, book, flag,
recycle, network, box, pin. All are editable freeforms using current inks.

- Do: bind a tool glyph to a repair claim. Don't: place an unrelated large motif in slack.
- Do: pass sequence data once and let connectors follow order. Don't: draw arrows manually.
- Do: inspect quota warnings and preserve text clearance. Don't: fill blank space to satisfy a count.
