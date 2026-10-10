# Riso Design Skill

An agent skill for editable **Risograph slide decks and standalone posters**:
limited spot inks, generated paper/print texture, misregistration and overprint.
Text fit, decoration placement, and artifact geometry are measured with real
font metrics. Plan content and graphic relationships together; decoration budgets
are ceilings, never quotas.

The runtime package contains no finished reference artwork. It never scans old
posters/decks to derive a composition. User photos enter through duotone only.
Gallery evidence belongs to remote GitHub Release assets, separate from the
installed package; generated demos must stay outside this repository.

## Requirements and installation

Python 3.9+ with `python-pptx`, `Pillow`, and `numpy`:

```bash
pip install python-pptx Pillow numpy
```

Copy this package to a skill root as `riso-slides/` (for example
`~/.codex/skills/riso-slides/` or `<project>/.agents/skills/riso-slides/`).
An agent loads the compact `SKILL.md` and only the relevant mode references.
Use filtered catalogue queries and `--plan --summary` to avoid large tool outputs.
Font advances/line heights use bounded process-local caches. A harness that forces
recursive ingestion of the entire package must configure its own loading policy;
the skill cannot override that harness. Start with SKILL.md and follow its links.

Optional renderer: LibreOffice plus PyMuPDF/poppler, or a compatible
libreoffice-kit CLI. Rendering goes **PPTX -> PDF -> PNG**. Missing renderer
support does not prevent editable PPTX generation. Fonts must resolve locally;
poster mode rejects unavailable explicit font choices and records safe fallbacks.

## Slide decks: compatible API

Existing deck JSON works without migration. Default geometry and the twelve deck
archetypes remain unchanged. The deck scenario controls content/density/character.

```bash
python scripts/build_deck.py --schema
python scripts/make_textures.py bg --out OUTPUT/media --pages N --palette G --seed SEED --chrome-set light --plan-file OUTPUT/plan.json --manifest OUTPUT/media/manifest.json
python scripts/build_deck.py --spec OUTPUT/deck.json --out OUTPUT/deck.pptx
python scripts/qa.py --deck OUTPUT/deck.pptx --media OUTPUT/media --json OUTPUT/qa.json
python scripts/layout_check.py --deck OUTPUT/deck.pptx --json OUTPUT/layout.json
```

`layout_check.py` now includes a `deck` section with archetype and text-tier
sequences, protagonist zones, normalized layout signatures, and rhythm verdicts.
Consecutive near-identical compositions fail; very long homogeneous runs
and overwhelming whole-deck skeleton repetition also fail. An identical pair
warns. Two consecutive data pages with different compositions are legal.
Planning records supplied claim/support/anchor roles and emphasis candidates;
it never creates facts, quotes, or extra pages to obtain rhythm.

## Posters: independent artifact mode

One poster is one custom-size editable PPTX. Families are `type_led`, `image_led`,
`editorial_event`, `data_poster`, and `manifesto_quote`; they are composition
grammars, not a portrait cover slide. No deck page number or header/footer chrome
appears. Optional source footer/CTA remains ordinary poster content.

Minimal spec:

```json
{
  "artifact": "poster",
  "canvas": {"preset": "a3_portrait"},
  "family": "type_led",
  "meta": {"lang": "en", "palette": "C", "seed": 17, "elements": true},
  "content": {"title": "YOUR SUPPLIED TITLE"}
}
```

```bash
python scripts/build_poster.py --schema
python scripts/build_poster.py --describe-spec
python scripts/build_poster.py --spec OUTPUT/poster.json --plan
python scripts/build_poster.py --spec OUTPUT/poster.json --out OUTPUT/poster.pptx
python scripts/qa.py --deck OUTPUT/poster.pptx --media OUTPUT/media --json OUTPUT/qa.json
python scripts/layout_check.py --deck OUTPUT/poster.pptx --json OUTPUT/layout.json
python scripts/render.py --deck OUTPUT/poster.pptx --out OUTPUT/preview --keep-pdf
```

Supported canvases: A3 portrait by default, A4/A2 portrait, 4:5 portrait, and
square. Custom dimensions accept points, millimeters, or inches; custom ratios
are supported. Physical sizes, safe bounds, bleed, registration, and chrome
policy are defined in `scripts/canvas.py`; `--describe-spec` lists preset dimensions.
Custom `canvas` example: `{"width":210,"height":297,"unit":"mm"}`.
`--schema` emits a directly buildable minimal spec; no additional envelope is
required. Old spec/envelope inputs remain supported. `--plan` emits reusable
`{"spec":...,"plan":...}` JSON without creating output, media, directories, or history.
Poster output includes PPTX, generated media, and an artifact style sidecar. A working renderer
adds PNG previews and PDF; `build_poster.py --render` attempts both without
failing the editable build when export is unavailable.

Optional roles include subtitle, body/blocks, date/venue/metadata, CTA, key
number, quote, supplied image, and footer. Explicit family wins, followed by
content semantics and seeded choice. User images pass through the shared
duotone/halftone pipeline with treatment hashes; ordinary images preserve aspect
ratio. Full bleed requires an explicit content reason. Details: [poster spec](references/poster.md).

Poster `layout` controls: `columns: "auto"|1|2`, `structure: "rules"|"none"`,
`title_size`, `body_size`, `alignment: "l"|"c"|"r"`,
`footer_anchor: "content"|"edge"`, and `vertical_alignment: "balanced"|"top"`.
`graphic: "auto"|"band"|"none"` reserves a measured graphic region;
`graphic_position: "auto"|"after_title"|"after_content"` chooses its reading
relationship. Default posters use composed graphics and accents. Set
`meta.graphic_element` to an allowed primary-dialect element for an explicit
choice. `meta.elements: false` is the intentional pure-type opt-out.
Use `--plan --summary` for compact diagnostics; full `--plan` remains reusable.
Requested sizes are ceilings with readable floors; modules consume measured,
unequal heights. A bounded deterministic balance shift preserves useful whitespace.
Content footers follow the measured composition; edge footers are explicit.
Supplied `comparison` alternatives or ordered `process` labels produce editable
vector diagrams. Prose alone never invents relations. Explicit family selection
keeps supplied quote/number roles as support and records demotions; reading-order
records refer to the objects actually drawn.

Plan supplied purpose/viewing distance, source roles and hierarchy, family,
type/grid and graphic regions, images/information diagrams/generated shapes,
print treatment, subordinate accents,
geometry QA, then rendered human inspection. Optional `brief` records supplied
constraints and sources; it does not create missing facts.

## Measured fitting and paths

Both builders use `typefit.py`: real resolved font metrics, explicit paragraphs,
Latin word breaks, and CJK punctuation rules. Editable text shares measured line
breaks across display layers. Overflow fails with role, block index, region,
requested/minimum size, and measured demand. Reallocate space, select a legal
layout, or revise source content explicitly; no silent truncation or tiny-type escape.
Print title offsets grow continuously with size and stay close to registration;
reverse offsets allow stronger separation. User offsets override automatic values.

Input images, background directories, and manifests resolve relative to the spec
file, even from another working directory. Missing inputs fail. Output parents
are created. `deck.pptx` owns `deck.style.json` and `deck-media/`; `poster.pptx`
owns `poster.style.json` and `poster-media/`, so artifacts can share a directory.
Both checkers prefer these sidecars/media. Legacy `style.json` and `media/`
aliases are created only when absent, never overwritten.
Per-page deck `exclude_elements` and `element_pool` (poster: under `meta`) can
exclude candidates or provide an empty pool. Automatic pools exclude elements
with default copy/numbers; explicit information elements require supplied fields.

## State and reproducibility

Runtime state never lives in the skill repository. `RISO_DESIGN_STATE_DIR` wins;
otherwise use Windows LOCALAPPDATA, macOS Application Support, or Linux
XDG_STATE_HOME / user state directory, under `riso-design`. `history.json` and
renderer registration live there. History avoids recent dialect pairs for new
artifacts; an existing title/seed keeps its selected pair even after other builds.
The same spec/seed/source-image/font environment yields deterministic content,
shapes, media, and canonical PPTX ZIP bytes. Explicit unavailable fonts fail;
automatic local fallback choices are diagnosed. Font collections are searched
by actual face names on Windows/macOS/Linux. Fonts are not bundled or downloaded
for ordinary build/QA.

If a default state write actually fails, warn and use a per-user system-temp
directory outside the skill tree. Read valid populated history across
default/fallback locations, preferring the newest. An unwritable explicit override
fails with its path. Entry points prevent package bytecode writes without
depending on an external `PYTHONDONTWRITEBYTECODE` setting.

```bash
python scripts/render.py --describe
python scripts/render.py --describe --autodiscover
python scripts/render.py --register /path/to/libreoffice-kit/lib/cli.js
```

Generated outputs never belong in the skill package. Artifact sidecars record
canvas, palette, fonts, dialect, source roles, treatment, and decoration.
`render.py --work-dir PATH` uses an isolated writable conversion workspace.
Exit 3 means no resolved renderer route (kit search may be unrequested); exit 4
means execution/workspace failure. Neither
route discards the editable PPTX; verified PNG/PDF files are published after conversion.
No elevation or execution-permission bypass is attempted.

`--describe` reports discovery only: found, searched without a route, or kit
autodiscovery not requested. It cannot prove execution; run a real conversion
probe before declaring the renderer usable. Without configured/registered paths,
use `--autodiscover` or explicit `--kit` and `--node`. Windows work and publication
directories inherit their parent's ACL so subsequent readers can open previews.

Without `qa.py --render`, scheduled pixel checks are visibly **SKIPPED /
UNVERIFIED**, even when structural checks pass. JSON records `pixel_checks`,
executed/scheduled counts, notes and explicitly explained non-applicable slots.
Use the strict CI gate after rendering:

```bash
python scripts/render.py --deck OUTPUT/deck.pptx --out OUTPUT/preview --keep-pdf --autodiscover
python scripts/qa.py --deck OUTPUT/deck.pptx --render OUTPUT/preview --require-render --json OUTPUT/qa.json
python scripts/layout_check.py --deck OUTPUT/deck.pptx
```

`--require-render` exits 3 for absent, partial, unreadable or stale previews. It
requires existing previews and does not run a renderer itself. New previews
record the PPTX SHA256 in `render.json`; legacy previews remain readable. Pixel
checks sample actual measured glyphs, not empty text frames. Flood dot-field and
poster raster-safe-area exemptions retain their stated reasons and are excluded
from passed counts; geometric text safety still applies. Legibility thresholds
are unchanged. `layout_check.py` remains the geometry/rhythm gate.

## Regression checks

```bash
python tests/test_contract.py
python tests/test_geometry_guard.py
python tests/test_anticlutter.py
python tests/test_poster.py
python tests/test_rhythm.py
python tests/test_state.py
python tests/test_export.py
python tests/test_feedback.py
python tests/test_final.py
python tests/demo_seeds.py --out OUTPUT/deck-seeds
python tests/demo_posters.py --out OUTPUT/posters
```

`test_contract.py --render` discovers the kit and really renders all three
fixtures when available. Missing routes are visibly unverified; execution
failure fails the suite. `--out PATH` retains fixture evidence outside the skill.
Both demo scripts with `--render` require successful rendering and pixel QA.
Element noise uses the element's seeded RNG; feedback regressions compare all
element PNGs and complete deck/poster bytes across three builds. The strict
anti-overfit contract still forbids finished images/PPTX in the runtime package,
copied example prose, and instructions to calibrate composition from artwork.
It also caps SKILL.md runtime bytes and checks the generated design-system and
element catalogue. Poster regressions cover multiple canvases, CJK/English,
dialects, deterministic builds, negative geometry/policy cases, and image
treatment. Rhythm tests distinguish pathological repetition from legal repeats.
State tests snapshot a copied package before/after real CLI builds.

## Gallery and visual boundary

There are no bundled gallery images. Generate review demos with the commands
above, then upload their images to [GitHub Releases](https://github.com/Lanthanums/Risograph-Design-Skill/releases)
and link those remote assets. Do not relax package hygiene to host the gallery.

Geometry success proves measurable properties under resolved font metrics.
Human review still covers print craft, stroke/glyph rendering, source meaning,
distance readability, and pacing. LibreOffice previews cannot prove identical
PowerPoint appearance. Renderer-dependent checks must be explicitly reported as
skipped when no usable renderer is available. There is no aesthetic total score.

## License

[MIT](LICENSE).
