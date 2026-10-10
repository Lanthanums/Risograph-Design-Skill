# Validation and delivery

## Machine gates

Run `qa.py` and `layout_check.py` on the complete PPTX. Include `--render` in QA
when previews exist. Optional deck `squint_test.py` checks coarse emphasis; use
documented overrides for distributed diagrams. Geometry detects overflow,
collisions, protection gaps, highlight coverage, fonts, palette compliance,
decoration ceilings, quiet space, and artifact policy. Layout reports include
deck sequence/signatures or poster hierarchy and chrome checks.

All numeric limits belong to Python. No aesthetic or semantic total score is
reported. Fix failures, rebuild, and rerun affected checks. A renderer's absence
must not stop PPTX creation; disclose skipped pixel/craft checks.

Renderer discovery must distinguish an unrequested kit search from a completed
search with no route. Use `--autodiscover` or explicit/registered paths, then a
real conversion probe; `--describe` alone leaves execution UNVERIFIED. Without
previews QA reports pixel checks SKIPPED in console and JSON. CI uses
`qa.py --render PREVIEW --require-render`; missing/invalid/stale previews exit 3.
Keep explained non-applicable slots separate from passed checks. Do not lower
contrast limits, delete failed checks or treat execution failures as missing
renderers. Compare PNG and full PPTX bytes across repeated seeded builds.

## Human review

- Trace facts and quotes to the source; verify claim/support/anchor relations.
- Hide decoration mentally: hierarchy must already work. Explain each element's
  function. Judge whether print texture, strokes, and offsets look deliberate.
- For posters, check the intended image/diagram/graphic actually appears and
  contributes to the composition. Review `poster.graphic` and element errors;
  texture alone is not a substitute. A pure-type choice should be deliberate.
- Review deck pacing across pages; adjacent equal archetypes can be legitimate.
  Check poster title/quote/number readability at the intended viewing distance.
- Inspect important CJK/Latin glyphs, multiline wraps, image treatment, and
  actual foreground/background contrast. Review in the target app when possible.

## Deliver

Editable PPTX, content spec, `<stem>.style.json`, `<stem>-media/manifest.json`, QA/layout reports,
available PNG and PDF. Explain palette and content-density choices briefly.
Say which renderer was used and what remains unverified. A LibreOffice render
does not prove matching appearance in PowerPoint. Store finished gallery demos
outside the runtime package ; publish release assets only when requested.

Regression must inject a body/rule collision and an out-of-ellipse Venn label,
and also accept a legal long line and an intentional display stack. Check spec-
relative input resolution, multiple outputs in one directory, pure planning,
empty decoration pools, and copied-package hashes before/after real builds.
Use resolved CJK and Latin fonts. Disclose missing renderer, denied execution,
and which target application was actually inspected; do not equate mocked export
tests with visual inspection. Human review also covers source organization,
whitespace, paper rhythm, color contrast, and print/reverse offsets.
