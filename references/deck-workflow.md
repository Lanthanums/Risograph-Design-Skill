# English PowerPoint workflow

This file is enough for a normal deck. Open another reference only when the
table at the end sends you there.

## 1. Read the brief

Settle the audience, how the deck is viewed (live talk or read alone), the one
takeaway and the action you want. Separate sources of fact from examples of
style. Keep quotations, names, figures, units and dates exact. The deck is
written in English and `meta.lang` is `en`.

Let the argument set the page count. Give each page one job. A short source
needs fewer pages, and not every sentence is a slide.

## 2. Write the outline

Write one JSON outline. Each page states its copy once. The builder derives
the source inventory, the coverage ledger and the storyboard from it.

```json
{
  "meta": {"title": "The Night Line", "palette": "F", "seed": 7, "scenario": "report"},
  "thesis": "Approve a twelve-week late-shift trial.",
  "audience": "Transit board members",
  "purpose": "Support a decision session",
  "rationale": "Decision first, then the evidence, then the vote.",
  "art_direction": "Editorial serif on warm paper. Plum carries voice, orange marks evidence.",
  "pages": [
    {"id": "cover", "kind": "cover", "title": "The Night Line", "body": "A twelve-week trial"},
    {"id": "why", "title": "Why the late shift goes unfilled",
     "list": [["Shifts outlast the timetable.", "Most rosters release after the last departure."],
              ["The walk is the unsafe part.", "Riders name the unlit quay transfer."],
              ["Taxis take the raise.", "A ride home costs more than the night premium."]],
     "job": "Give the three causes.", "look": "Three torn cards, cue then detail."}
  ]
}
```

`palette` is A to G (A green, B cobalt and pink, C orange and navy, D teal and
coral, E wine and pink, F purple and orange, G red and black). `scenario` is
`report`, `course`, `proposal` or `speech`. Change `seed` for another
arrangement of the same design.

A page has an `id`, usually a `title`, and one block. A content page also
needs `job` (what the page adds to the argument) and `look` (what the viewer
sees first and how the page is composed). Write both as one plain line. These
two lines are the storyboard, so decide them before you write the copy.

| Block | Value | Renders as |
| --- | --- | --- |
| `statement` | text, optional `emphasis` | One large statement on the open page |
| `text` | text, optional `emphasis` | A measured column of copy |
| `list` | strings or `[cue, detail]` pairs, optional `ordered: true` | Torn cards, two ruled sheets or one ruled sheet |
| `stat` | `{value, unit, label, body}` | A dominant figure with its label and one sentence |
| `chart` | `{type, unit, points: [[label, number]]}`; type is `bars`, `columns`, `line`, `ring` or `stacked` | A newsprint clipping |
| `versus` | two `[label, text]` pairs | Two sheets side by side |
| `steps` | strings or pairs | A numbered sequence |
| `timeline` | `[label, text]` pairs | Dated nodes on a line |
| `quote` | the exact words, optional `by`, `context`, `featured` | A quotation page |

Other page keys: `kind` (`cover`, `section`, `closing`), `note` (a source line
at the foot), `notes` (speaker notes), `next`, `takeaway`, and `direction`
for the controls below. A page with several blocks uses
`"blocks": [{...}, {...}]`; give later blocks a `heading` when they need one.

Choices that decide how the deck looks:

- **Lists carry the torn paper.** Three or four points with a cue and a
  detail get one card each. Five to eight get two ruled sheets. Points
  without a detail share one ruled sheet, and a cue before a colon is set as
  a lead-in. Keep a cue to a few words.
- **Other pages take turns.** Of the pages that state, explain or show one
  figure, one sets its copy on a sheet and the next keeps open copy with a
  small paper scene beside it. Neither kind is left bare.
- **Titles are modest.** A page title is set near 36 pt with clear room under
  its rule. Write it in nine words or fewer.
- **Name the words that carry a statement.** Put two to five exact words in
  `emphasis`. They print in spot ink, or under a highlighter on a sheet.
- **One quotation is featured.** Set `featured: true` on the quotation that
  carries the argument. It gets a flooded ink field with a dot screen. Other
  quotations keep their paper and take overprinted circles. Keep a quotation
  to 30 words or fewer: quote the strongest sentence, not the paragraph.
- **Vary the sequence.** Do not put the same block on three pages in a row.
  A quiet page is a valid pause.

Controls in `direction` (per page) or `meta` (whole deck):

| Control | Values |
| --- | --- |
| `collage` | `auto` (default), `rich` (copy on a sheet), `quiet` (a sheet without a scene), `scene` (open copy with a paper scene), `off` (the v4.5 page). In `meta` also `lists`: paper only on pages that list |
| `paper_layout` | `auto`, `single` (one sheet), `staggered` (cards) |
| `quote_layout` | `auto`, `classic`, `broadside`, `margin`, `folio` |
| `vertical_align` | `balanced`, `top`, `center`, `bottom` |
| `content_width` | `.45` to `1`, the share of the width the evidence takes |
| `title_size`, `body_size` | points; body never goes below 18 |

### Pictures

If you can generate or source images, a page may carry one:
`"image": "art/zircon.png"`, or `{"path": ..., "treatment": "mono"}`. The path
is relative to the outline. The builder never places the file as it came. It
separates the picture into the two deck inks as halftone screens and tapes
it into the page as a torn print, where a paper scene would otherwise go.

- Use a picture where it shows the subject: a specimen, a place, an object,
  a person at work. Leave it off pages that only need a mood. About one page
  in three is plenty.
- Ask the image model for one clear subject on a plain light background,
  strong light and shade, no text, no border and no frame. Colour is
  discarded by the default `duotone` treatment. `mono` prints one ink and
  `keep` prints the source colours.
- Supply at least 400 px on the short side; 1200 px or more is better.
- A generated picture is an illustration, not evidence. Say so in the page's
  `note` when a viewer could take it for a photograph of the real thing.

Without an image tool, leave `image` out. The paper scenes fill those places.

## 3. Build

```bash
python scripts/deck_run.py --outline outline.json --out DECK_OUTPUT --auto
```

Keep output outside the skill folder. Run `python scripts/doctor.py --out
DECK_OUTPUT` once in a new environment. The run prints the status, one line
that maps every page, any page it adjusted, advice on copy that will not look
its best, and the review sheets. A failure names
the page and what to change. Fix the outline and run again. Use `--draft`
for a fast geometry check without rendering.

`deck_outline.py --outline outline.json` checks an outline without building.

## 4. Review

Look at `visual/sheet-01.png` and the sheets after it. Each shows six slides
at a size where body copy is readable. Open a full page from `preview/` only
to confirm a defect you suspect, or for a page the run listed as adjusted.
You do not need to read the style sidecar, the logs or the storyboard file.

Check that the assertion reads first on every page, that each line of copy
sits fully on its sheet, that neighbouring pages differ, and that no page
feels empty or crowded. Change the outline and rebuild. A technical pass is
not visual approval, and LibreOffice does not certify PowerPoint.

## 5. Deliver

Give the user `deck.pptx`, the outline and `storyboard.md`. Name the renderer
used and say which checks you ran. Text, charts and marks are native and
editable. Torn paper is printed into the slide background.

## Read more only when

| You need | Read |
| --- | --- |
| A ledger against an external source document, or a module form the blocks do not cover | [storyboard](deck-storyboard.md), [content planning](content-planning.md) |
| Fine control of one page family, charts as spreads, title plates, print marks | [deck composition](deck-composition.md) |
| Rules for dense copy, title breaks and long lists | [typography and lists](deck-typography-and-lists.md) |
| How the paper is made and how to maintain it | [deck paper collage](deck-paper-collage.md) |
| Custom inks or fonts | [palettes](palettes.md), [typography](typography.md) |
| Caches, timing, restricted environments | [performance](performance.md), [harnesses](harnesses.md) |
| A classic hand-authored spec | [scenarios](scenarios.md), [archetypes](archetypes.md) |
