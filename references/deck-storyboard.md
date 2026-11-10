# PowerPoint storyboard

Write the storyboard after reading the brief and the sources, before authoring any
slide objects. Draft the whole argument first. The storyboard is a production plan
and a review artifact. Keep its language English, including when source material
or the user's message is in another language.

## Deck decisions

- Record audience, use (live talk, projected class, or standalone reading),
  requested length or time, single takeaway, and intended action. Derive the page
  count from the argument and any explicit limit. A one-slide request already
  has its opening and ending. Use a cover or section divider only if it earns space.
- Sequence what the audience needs to understand first, what changes its mind,
  where an example makes the idea concrete, and what it should do or remember.
  An evidence-led report, a lecture and a proposal need different rhythms.
- Build the source ledger before sketching. Locate every essential claim and
  qualification on a slide. Put delivery cues, fuller explanations, and verbal
  transitions in notes. A deck read without its presenter needs enough context
  on the slide itself. Keep units, uncertainty, evidence labels, and quotation
  attribution with what they qualify.
- Choose an English type system and two working inks. Georgia works especially
  well for an editorial deck. Use a tested fallback or explicit alternatives for
  chart labels, technical notation, and branding as needed. Decide where paper,
  small repeated marks, overprint and reversed ink fields support navigation or
  emphasis. A system can recur while individual compositions change.

## Plan each slide as a shot

Write what happens on the page and how it will read, with a decision the builder
can act on. Link each page to explicit module IDs from the source plan. Preserve
the user’s page count and the intended order. Mark the exact words to quote and
keep source names, places and chronology intact.

| Decision | What to specify |
| --- | --- |
| Job and takeaway | What this page adds to the argument and the one sentence the audience should retain |
| Evidence and notes | Which modules and facts are visible, the key labels and caveats, and what the speaker adds |
| Composition and reading order | Focal object and its relative size, alignment/grid, spatial relationship and where the eye moves next |
| Print treatment | Paper or ink field, accent ink, and one or more intentional microdetails with their function and location |
| Density | What earns space and where empty space helps. If thin, merge adjacent material, enlarge the evidence, or give the pause a clear purpose |
| Transition | What question, contrast or progression carries into the next page |
| Risks and fallback | Likely wrap, overlap, contrast, dense data, absent image or weak relationship, and a specific alternate composition |

Decide reading distance and approximate scale before placing support. Prefer a
purposeful hierarchy to a fixed component count. Let a chart or an example be
bigger than the slide title when it carries the message. Check a sequence of
thumbnails for sameness. Change the weight, alignment, ink field or visual form
when consecutive content pages begin to feel interchangeable. Quiet slides work
when they create a deliberate pause or let one consequential line stand alone.

## Composition by job

| Job | Design decision and fallback |
| --- | --- |
| Cover | Give the subject a clear first read. Plan meaningful title breaks, an optional short deck, and a small context cue when the source supplies one. Reserve a quiet field for glyphs. A second and third offset ink layer work at display scale. Move the field or reduce the offset when letterforms lose definition. |
| Unordered points | Group by meaning. Use one sheet for a compact checklist or stagger separate cards for substantial independent points. Specify the left-right reading path, per-card text measure, and which edge receives texture. Use one sheet when the measured columns crowd the copy. See [English typography and dense copy](deck-typography-and-lists.md). |
| Ordered points or process | Let position or a continuous line reveal order. Make entry, direction, and outcome explicit. Reserve numbering and arrows for real sequence or causality. Branches need labeled exits and a reading path. |
| Quotation | Give the exact words a dominant block and keep credit attached. Try a centered broadside for a short line, a separate credit rail for a speaker-led medium excerpt, or a wide paper folio for a long excerpt. Vary placement and ink emphasis across consecutive quotes. Check line breaks and leave enough room for the full quote and credit. |
| Figure or KPI | Pair a dominant value with metric, unit, population and time frame. Provide the baseline or comparison only when sourced. Use the secondary area for what it explains. Keep the explanation beside the number it qualifies. |
| Comparison or decision | Align comparable dimensions on a shared baseline. Name the difference or decision up front. Use a bar only for commensurate values. A parallel text spread or a compact table works when tradeoffs are qualitative. |
| Trend or part-to-whole | Label scales, units and the denominator. Mark the consequential change with an anchored caption. Use a chronological axis only when the source establishes time order. Keep uncertain or missing observations distinct. |
| Definition or teaching example | Pair the definition with the instance or a small annotated model. Use a contrast or non-example only when supported. Reserve a separate practice slide when the activity changes the audience's task. |
| Photograph, specimen or case | Crop for the relevant detail and keep the label or source close. Apply ink treatment where it preserves the evidence. Without a usable visual, use the example, comparison or quote the source actually contains. |
| Dense table or appendix | Keep row labels, precision and units readable. Show the key slice on the argument page and put the full evidence in a requested appendix or a follow-on page. Honor exact slide counts and required visible details. |
| Section break or close | Use a tonal change to mark a real shift. Close with a decision, named next step, synthesis or open question that follows from the content. Keep decorative emphasis off the terms of the ask. |

For a case outside this table, name the relation the audience must perceive and
sketch two ways to show it. A cycle may call for a loop with an entry marker, a
counterexample for a labeled exception beside the rule, and a timeline with
uncertain dates for intervals rather than precise dots. Pick the sketch that
communicates the relation with the least reading effort. Document its fallback.
When the compiled forms cannot express the design, use a supported classic
archetype or an editable deck-native composition with a recorded source mapping
and the same geometry and rendered review. Preserve the page count, copy,
source ledger, and QA. Update the storyboard when a different composition wins.

## Check before generating

Read the planned pages in order with only their job and takeaway visible.
Check the progression and whether any page is doing the work of two. Read
the storyboard again with the on-slide evidence and design notes visible.
Resolve vague instructions such as "add graphics" by naming the evidence,
its spatial role, and the reading order. A title and visual anchor must have
room at their intended size. Check that the chosen form receives the data it
needs. A step flow needs individual actions, and a takeaway list needs items
with their own labels. Read headings, labels, and body text together and give
each fact one visible role. For example, a definition can sit beside a worked
case while the corresponding exception appears once.
If the brief is too sparse for the requested
length, use the supported examples, distinctions or exercises it contains
and preserve any deliberately quiet moments. Keep uncertainty explicit.

## Content-plan fields

Use `deck_content_plan.scaffold(source)` to obtain the source SHA and atom inventory,
then author and bind your own modules and ledger. Set `target: deck`,
`mode: storyboard`, and `meta.lang: en` for new slides. Modules use the existing
fields `id`, `level`, `info_type`, `visual`, `headline`, `body`, `atoms`, and
optional `visual_data`, `order` and `notes`. Assign every module a string `page`.
The first occurrence of each content page sets slide order. Level 4 is for
source/footer material, and still needs an explicit destination. Use
`deck_content_plan.annotate(plan)` to populate computed evidence. Use the actual
coverage ledger to distinguish retained, merged, condensed and cut atoms.
For an adapted `step-flow`, bind each node with `visual_data.items[].atom`
and keep nodes in source order. A source `content.process` array records an
ordered procedure. Preserve the order and meaning when shortening node labels.

Add `storyboard` to the same JSON. This abbreviated example shows one page row.
The page ID and module IDs must match the compiled pages in order.

```json
{
  "rationale": "Frame the survey decision before showing the sampling protocol and field evidence.",
  "art_direction": "Editorial serif on warm paper. Plum carries voice; ochre marks procedure.",
  "pages": [
    {
      "id": "opening",
      "purpose": "Establish the survey subject and give the audience a reason to listen.",
      "takeaway": "Consistent sampling makes observations comparable across sites.",
      "modules": ["survey-title"],
      "layout": "Left editorial stack, large two-line title above a short subtitle.",
      "reading_order": ["subject title", "survey scope"],
      "visual_role": "The broken title is the focal object, followed by the scope line.",
      "print_role": "Offset plum plates on the title. Keep the ink field at the upper right.",
      "density": "light",
      "density_reason": "Leave space for the opening spoken example.",
      "transition": "The next page shows how to keep site observations comparable.",
      "risk": "A third title line could crowd the subtitle.",
      "fallback": "Widen the type region or select a quieter field before reducing title scale."
    }
  ]
}
```

Use `light`, `medium`, or `dense` for `density`. Supply `density_reason` when a
specific constraint or deliberate pause affects the page. Put narration in the
modules' `notes`. The storyboard Markdown shows those notes separately.

Under `page_directions`, key executable controls by page ID. Select
`composition: cover` for one module with a headline and optional body, plus
optional source-bound `visual_data.kicker` and `visual_data.context`.
Use `title_size` on that page when a different display scale suits the title.
Select `composition: quote` for one `pull-quote` module with exact `body`,
optional `visual_data.attribution` and `visual_data.context`. Keep both with
the quote in that module. Use the heading
for a short section label when the brief supplies one. The quotation writer
can omit its ink swatch with `quote_screen: false`. These two writers reserve
the main anchor for the title or quotation. Plan spots for the native print
accents with `print_marks` and choose `type_plates` for the title treatment.
Use `element_pool` for catalogue elements. The `background` object can choose a
named preset or use plain paper. Other pages use `composition: auto` and the
[deck layout controls](deck-composition.md).

The compiler checks the storyboard structure and page/module mapping. The
author checks English copy, factual equivalence, rhythm, the quality of each
fallback, and whether the composition communicates the intended relation.
