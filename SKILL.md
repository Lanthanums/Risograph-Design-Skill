---
name: riso-slides
description: Create editable English Risograph PowerPoint decks and standalone posters, with editorial typography, spot inks, print texture, diagrams and charts. Defaults to PowerPoint. Use the poster workflow when the requested deliverable is a standalone poster.
---

# Riso Slides

Choose the deliverable **from the user's request before opening any source, reference image, or example file**.

- **PowerPoint by default.** Use the [PowerPoint workflow](references/deck-workflow.md) for a presentation, an unspecified Riso deliverable, or a slide modeled on a poster.
- **Standalone poster by request.** Use the [poster workflow](references/poster-workflow.md) when the user asks for an independent poster, print sheet, or single-image infographic as the deliverable. A poster supplied as a reference does not select this route.
- **Both.** Run each workflow separately. Read and interpret the sources for each deliverable in that workflow. Keep separate plans, output directories, and review records.

English is the authored language for both workflows. A request or source can be in
another language. Translate with source traceability when the brief permits it.
Set `meta.lang: en`. Use explicit attribution for translated quotations and preserve
the original in the source ledger. Honor requested verbatim copy and clarify any
conflict with the English deliverable before drafting.

Keep output outside the skill. Use one Python interpreter. The routes share
rendering, font measurement, and file utilities. Each route owns its planning,
composition, design decisions, and review.
