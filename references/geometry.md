# Geometry and rendering boundary

All coordinates are points. `canvas.CanvasSpec` owns width/height, aspect ratio,
safe/content bounds, bleed allowance, registration footprint, and optional
chrome bands. `DECK_CANVAS` preserves the first version's slide geometry.
Poster presets/custom dimensions route through `poster_canvas()`; shared
geometry, placement, QA, and rendering receive the actual Canvas. Deck-specific
archetype coordinates remain intentionally deck-specific.

Measure with `textmetrics` and resolved font files, not nominal character widths.
Protect glyph ink, account for rotated decoration footprints, merge offset
copies for hierarchy, and check independent text blocks for collisions. Every
highlight must cover its actual target word; a bar merely fitting within a line
does not establish coverage.

PowerPoint can wrap even with `word_wrap=False` while keeping a fixed frame
height. `riso_kit.text` reserves measured whole-line width using `NO_WRAP`; fixed
columns need explicit measured line breaking. Fit all runs together. Never
silently fit long copy below readability limits. Poster overflow is a hard
failure, requiring copy/layout changes rather than invented or omitted facts.

Missing fonts are not verified geometry. Resolve a supported font, set its
Latin/EA/CS typefaces, and report substitutions. Pixel QA uses actual rendered
foreground/background; nominal ink color cannot prove contrast on a flood.

Poster text is safe by default. Explicit `text_bleed` roles may extend to trim,
never beyond trim; decoration/image can use Canvas bleed. A full-bleed image
must be duotone-treated and recorded in style provenance. Deck page numbers
and header/footer chrome are forbidden in poster mode, even if a text object
looks like an ordinary label. An optional poster footer is source content.

`render.py` routes PPTX through PDF to PNG, checks actual width and height, and
copies the PDF into the preview folder with `--keep-pdf`. Renderer registration
is per-user state. Structural QA remains available without a renderer.

QA joins shape measurements by their stable XML element: python-pptx proxies
change on each traversal. Sampling an unmatched declared text frame dilutes ink
with empty paper and hides the intended glyph measurement. Test both valid ink
and invisible ink; thresholds remain in `qa.py`. Pixel reports separate run,
skipped and explained non-applicability. New previews bind to source SHA256.
Deck chrome gets measured quiet regions in a derived print plate; the manifest
names the exact plate used for render-minus-background checks. Source backgrounds
remain intact. Windows render staging inherits the parent's ACL, rather than
moving owner-only files out of a private directory.

LibreOffice and PowerPoint differ in wrap interpretation, substituted fonts,
and rasterization. Passing geometry proves measured properties under the font
environment, not appearance in every target application. Craft, meaningful
hierarchy, and distance legibility still need human review.

## Shared fitting and geometric evidence

`typefit.fit` and `textmetrics` use real font files, including collection faces.
Latin wrapping preserves words; CJK wrapping groups closing punctuation with its
preceding unit. Explicit paragraphs and every nonspace character survive.
Native text remains editable, with measured line breaks shared by display layers.
Fit errors identify source role/block, region, requested/floor sizes and demand.

Only marked, identical display layers merge into one title. Equal ordinary body
strings are independent and may collide. `layout.measured_issues` is shared by
both checkers: it measures segment-to-glyph-rectangle distance along actual line
paths and accounts for stroke width. It avoids long-line AABB false positives.
Venn labels are measured glyph rectangles tested against the true ellipse or
both ellipses for intersection labels, never merely their outer rectangles.
This is conservative font-bbox geometry, not glyph-outline raster inspection.

Artifact sidecars/media take priority over legacy aliases. `render.py --work-dir`
validates a writable conversion workspace; missing renderer is exit 3,
execution/workspace failure is exit 4. PPTX remains intact. Verified staged
outputs are published after conversion; permissions are never bypassed.
