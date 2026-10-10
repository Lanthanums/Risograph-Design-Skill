# Frozen print language

Read when modifying shared design logic. The numeric source of truth is Python:
`riso_kit.DESIGN`, `canvas.CanvasSpec`, `place_decor.TEXT_TIERS`,
`compose.DENSITY`, and `make_textures.FIELD_PRESETS`.

```bash
python scripts/build_deck.py --design-system
python scripts/make_textures.py presets
```

## Color roles

`paper` is warm textured substrate. `inkA` leads, `inkB` supports, `ink` and
charcoal carry readable copy. `ink_deep` strengthens offset type; `inkAB` is
the multiply overprint. `tintA`/`tintB` are washes. `accent1` and `accent2`
punctuate sparingly; a bright accent is a backing for dark type, not faint
foreground copy on paper. These are derived print roles, not extra spot inks.

## Type and print effects

The shared type scale names `display_xl`, `display_l`, `page_title`,
`hero_label`, `body`, `caption`, `label`, and `note`. Density decides body
readability; poster grammar establishes distance hierarchy. All text remains
editable. `misreg_offsets()` and `stack()` adapt layers to fitted type size,
preserve neighboring contrast, and reserve the same font/anchor across copies.
No external artwork is consulted to recalibrate these settings.

## Geometry and decoration

Canvas defines trim, safe content, registration footprint, bleed, and optional
chrome bands. Deck keeps its original canvas and archetype coordinates; poster
has independent families. Decoration is placed after measured type. Budgets
are ceilings with no minimum count. Read `geometry.md` or `anti-clutter.md`
only for the relevant implementation/debugging task.

## Calibrated field catalogue

Presets below are identifiers, not duplicated parameter tables. Query the CLI
for centers/radius/density and recommended archetypes. Field radius bounds the
ink; grain alone is valid when no legal field room remains.

- `cover-bleed-tr`: 封面：两枚叠印圆自右上角出血
- `cover-bleed-bl`: 封面变体：左下角出血，封面正文止于 y≈365 时可用
- `corner-fade-br`: 数据页：右下角大颗粒渐隐，左重版式
- `corner-fade-bl-sm`: 数据页：左下角小渐隐，右重版式
- `corner-fade-tr-sm`: 列表/占比页：右上角细密点，避开中部图表
- `corner-fade-tr-xs`: 引语页：右上角极轻点，几乎只是纸纹
- `corner-speckle-tr`: 表格/对比页：只占右上角一小块，页面主体保持干净
- `edge-fade-left`: 图解页：左边缘一条墨迹，配合右侧留白
- `edge-fade-right`: 风险页：右边缘下半段渐隐，避开左侧大数字
- `band-bottom`: 占比/条形页：沿底边积墨，正文止于 y≈400 时可用
- `blob-corner-tl`: 通用：左上角有界斑点（radius 保证不铺满整页）
- `blob-corner-br`: 通用：右下角有界斑点
- `reverse-blob-bl`: 反白页：左下角墨点（点在油墨 A 底上用油墨 B）
- `reverse-circle-br`: 反白章节页：右下角黑圆出血 + 叠印深红
- `reverse-circle-tr`: 反白结尾页：右上角黑圆出血 + 叠印深红

## Provenance

This package carries frozen constraints and generators, never finished reference
artwork or example copy. User photos pass through duotone. A user-supplied style
reference can supply only color/texture/offset parameters, recorded separately
from content decisions. Changing calibration requires code and regression checks;
ordinary tasks must not reopen an old artifact to derive a new skeleton.

## Measured display layers

`DESIGN.misregistration` defines continuous size ratios and caps separately for
paper `print` registration and stronger `reverse` separation. Explicit user
offsets win; one-argument `misreg_offsets(size)` preserves legacy tier queries.
The ordinary-paper calibration sits between the original large tier offsets and
the overly tight repaired offsets; reverse calibration is retained. Query the
code for numeric values. The visible layer can be the middle plate when contrast
filtering removes the deepest plate, so inspect actual output as well as offsets.
Stack layers share text, line breaks, alignment, and fitting, with intentional
layer names for QA. A layer exception never licenses body/rule collisions.
Shared `typefit` and `artifact_io` serve the genuine deck/poster intersections;
canvas, rhythm, history, and the independent poster families remain the v2 engines.
