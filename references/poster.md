# Poster mode

Use `artifact: poster` and `build_poster.py`. A poster is a standalone custom-size
single-page editable PPTX. Its layout families are separate from deck archetypes;
they reuse palette, print treatment, real font metrics, and decoration geometry.

```bash
python scripts/build_poster.py --schema
python scripts/build_poster.py --describe-spec
python scripts/build_poster.py --spec OUTPUT/poster.json --plan
python scripts/build_poster.py --spec OUTPUT/poster.json --out OUTPUT/poster.pptx
python scripts/build_poster.py --spec OUTPUT/poster.json --out OUTPUT/poster.pptx --render
```

`--render` attempts PDF/PNG export; renderer failure never discards the PPTX.
For explicit renderer control, call `render.py --deck ... --keep-pdf` separately.
Each output owns `<stem>-media/manifest.json` and `<stem>.style.json`, including canvas, family, source roles, fonts, dialect,
image-treatment hashes, and decoration records.

## Canvas

`canvas.py` defines the physical presets: `a3_portrait` (default), `a4_portrait`,
`a2_portrait`, `4:5`, and `square`. A-series dimensions follow ISO sheet sizes;
the other presets use point dimensions. Query `--describe-spec` for exact values.
Custom examples: `{"width":210,"height":297,"unit":"mm"}` or
`{"width":720,"ratio":"3:4"}`. Units are `pt`, `mm`, and `in`; ratio also
accepts a number or `[width,height]`. Conflicting dimensions/ratio fail.

Safe bounds, bleed, and registration geometry are Canvas properties. Posters
have no deck chrome bands, header/footer furniture, or page number. `footer`
under content is an optional source role, not deck chrome.

## Content roles and family choice

Supply `content.title`. Everything else is optional: subtitle, body, blocks,
date, venue, metadata, CTA, key number, quote/attribution, data, image, footer.
No role is filled with invented copy. Long content fails when it cannot fit
without sacrificing readable hierarchy; revise allocation/layout or source copy.

| Family | Composition grammar | Semantic trigger |
|---|---|---|
| `type_led` | Monumental title and a subordinate reading region | Title/thesis-led content |
| `image_led` | Large treated image, title, separate supporting column | Supplied user image |
| `editorial_event` | Title, prominent metadata band, supporting details | Date or venue |
| `data_poster` | Key number or data evidence, explanation, source roles | Key number/data |
| `manifesto_quote` | Supplied quote/thesis, attribution, subordinate title | Supplied quote |

Priority is explicit `family`, then content semantics, then seeded family choice.
Explicit alignment is a layout control, defaulting to left. User dialect overrides
win; otherwise the shared domain/history selection runs. History avoids recent
choices for new artifacts while preserving existing title/seed rebuilds.

Title, quote, and number use measured display treatment; body is explicitly
line-broken with CJK/Latin font advances. Poster title has distance hierarchy.
Graphics are part of the composition, not a finishing afterthought. Choose a
supplied treated image, source-grounded diagram, or substantial generated shape
group, then use smaller marks for rhythm/emphasis. A plain paper texture and
tidy text alone do not complete this decision. Balance graphic and text weight
against purpose, distance and content; there is no fixed image/text ratio.

Default `meta.elements: true` uses the same copy-free graphic library as decks.
`layout.graphic: auto` reserves a measured band between display and supporting
copy when room exists; images/diagrams already fulfill that visual role.
Use `band` to require the region (failure asks for reallocation), or `none` to
retain only small automatic accents. `meta.elements: false` is the deliberate
pure-type option and disables the band too. Never silently choose it merely
because typography is easier. Existing area, hierarchy and quiet-space limits
still apply; no minimum element count is imposed.

Choose a relevant main shape with optional `meta.graphic_element` from the
allowed primary dialect pool; it requires a legal band and fails if excluded
or unable to fit. Query `elements.py catalogue --dialect C --role hero --safe`.
Omit it for seeded choices. `element_pool`/`exclude_elements` also filter accents.
Inspect `poster.graphic` in the sidecar: a reserved region without a placed group
needs review (restrictive pools, quiet-space pressure or rendering errors may
prevent placement). Reallocate or choose an intentional alternative; do not
turn budgets off to force artwork into a crowded layout.

## Supplied images and bleed

`content.image` is a path string or `{"path":"photo.jpg"}`. Relative paths
resolve against the spec file's directory. The builder routes this file through
`make_textures.cmd_duotone`, records source and treated-image hashes, and embeds
only the treated result. Ordinary images retain aspect ratio. A full-bleed
image is cropped to fill, with a supplied `full_bleed_reason`; it becomes the
underlay. No finished artwork is searched for or used as a composition reference.

`content.text_bleed` lists explicit text roles allowed to use trim instead of
safe bounds (`--schema` lists valid roles, including singular `block`). It never
allows glyphs beyond trim. The full-bleed image exception permits a content-image
underlay and waives quiet-region requirements only for a real image covering
the page. It does not waive text safety, text/decor collision, overflow, palette, font,
image-treatment provenance, or title hierarchy.

## Planning and layout API

`--schema` prints a minimal spec directly accepted by build. Legacy `spec`
envelopes remain accepted. `--plan` returns a reusable spec/plan JSON envelope;
it measures without a slide or any filesystem writes, including history.
Add `--summary` for compact diagnostics without duplicated source text; this
summary is not a reusable build spec. Use the full plan only when needed.
Input paths are made spec-relative before planning and fail when missing.
Unknown fields, families, dimensions, and layout controls fail with diagnostics.

Planning order is supplied purpose/viewing distance, roles/hierarchy, family,
type/grid and graphic-region allocation, image/information diagram or generated
graphic group, print treatment, subordinate accents,
geometry QA, rendered human review. Optional top-level `brief` accepts provided
`purpose`, `viewing_distance`, `audience`, `constraints`, and `sources` only.

| Layout field | Choices / behavior |
|---|---|
| `graphic` | `auto`, `band`, `none`; planned graphic region, see above |
| `graphic_position` | `auto`, `after_title`, `after_content`; choose the reading relationship |
| `columns` | `auto`, 1, 2; auto uses content count and available width |
| `structure` | `rules`, `none`; never adds copy |
| `title_size`, `body_size` | Maximum requested points, bounded by measured fit and readability |
| `alignment` | `l`, `c`, `r` |
| `footer_anchor` | `content` follows real content end; `edge` reserves bottom space |
| `vertical_alignment` | `balanced` translates within a fixed bound; `top` does not shift |

Modules have measured unequal heights and separate heading/body hierarchy.
No area-fill quota exists. The balancing formula and limits live in
`poster_layouts.py`, not a subjective aesthetic score. Reading-order metadata
contains role, block index, order, rectangle, and names of drawn objects.
Explicit type-led content retains supplied quote/key-number as support and
records the role demotion; no optional source role is silently dropped.

`comparison` and `process` accept source-label lists, either strings or
`{"label":"...","text":"..."}` objects. Comparisons draw parallel framed
alternatives; processes connect the explicitly ordered nodes. Both lists can
coexist. No flow or data relation is guessed from ordinary prose.

Footer, image, and support regions are reserved before drawing. Overflow reports
role/index, available region, requested/floor sizes and measured demand. Reallocate
layout/content; do not truncate text or decrease floors to squeeze a build through.

## QA and boundary

```bash
python scripts/qa.py --deck OUTPUT/poster.pptx --media OUTPUT/media --json OUTPUT/qa.json
python scripts/layout_check.py --deck OUTPUT/poster.pptx --json OUTPUT/layout.json
```

Style metadata routes both checkers automatically. Poster QA measures safe/trim
policy, text fit, text/decor collision, highlight coverage, resolved fonts,
decor ceilings, quiet region, hierarchy, palette, absence of deck chrome, and
treated-image provenance. Canvas dimensions in metadata must match the PPTX.
Numeric thresholds are defined only in code.

Render for craft, glyph appearance, actual contrast, and distance readability.
Structural success is not proof of PowerPoint appearance. If rendering fails,
deliver editable PPTX and reports with the missing visual checks stated clearly.
