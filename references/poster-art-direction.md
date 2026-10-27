# Composition controls and measured fitting

Query poster_run.py --describe-spec for authoritative types, domains, units and nesting.
Poster controls live in art_direction; recipe/seed in meta. meta.dialect A–F is
the legacy element vocabulary, distinct from art_direction.dialect.

body_size is preferred pt (16–32); autofit may reduce to 16, never grow to fill space.
title_size defaults to 64pt; title_leading to .98em (measured glyph clearance wins).
hero_share .18–.65 is a retained advisory control; actual hero size follows content.
Named graphics use a compact group, at most 6% page area, within 36pt of a source
anchor. They do not absorb surplus. columns 1/2/3 means content columns, capped by
source module count. Short prose can select one compact column by default.
effective_controls records requests, results and overriding rules.

Deterministic fitting: preferred sizes; reduce gaps; meaningful title/hero minima;
body down to floor; finally bands within the same dialect. No silent dialect change,
source deletion or content approval. Surplus goes to bounded gaps (<=32pt), padding
(additional <=8pt), then outer margins. Micro marks are bounded, not scaled to
consume whitespace. Bands report min/pref/max/actual heights in pt.
--no-autofit disables the search.

T1: title/figure/quote/CTA. T2: parallel modules. T3: supporting prose/metadata/sources.
Exact-source tiers overrides require an author decision; T3 retains 16pt floor.
Errors contain tallest modules, every column stack, and measured alternative-column
deficits. Suggested shorter summaries require approval; the engine never edits text.

Reading graph: header/hero; columns top-to-bottom, left-to-right; CTA/footer.
Module partitions are contiguous. Numbers only for source processes. QA checks
graph coverage and inversions against actual saved object geometry.
Quiet means low texture behind text and consistent margins, not a large empty
rectangle. Full-width interior gaps >8% page height fail. The new grid gate also
checks enclosed internal holes >8% page area and reserved graphic hero gaps >4%.
Ragged outside margins and title/masthead are excluded from the global grid;
abstract graphics cannot disguise a hero gap. intentional_voids accepts
{rect:[x,y,x1,y1],reason:"..."} as explicit design exceptions.

meta.graphic_recipe: micro (default), off, auto, echo/canopy/terraces/cut-paper/hand-drawn/editorial/signal/festival.
New posters use native vector interpretations of the same lead/pattern/detail
descriptors. Old deck bitmap generators remain unchanged. Abstract motifs are not
factual diagrams. Explicit pools/exclusions/disabled graphics/conflicts fail.
Check graphic_design.status, placement and meaning.

Exact title_lines/statement_lines preserve all source and order. highlights (max 2)
use {source,text,kind}: highlight/circle/underline/wave/bracket; unsafe marks fail.
annotations quote exact phrases in measured supporting modules.
revision/review_changes record actual edits.

Inspect full/10%/blur in one contact sheet. Fill 9 scores and 0–5 real weaknesses.
Template contains hash/dialect/metrics; stale evidence fails. Fast caches rendering;
audit rerenders and retains evidence. Neither automates visual judgment.
