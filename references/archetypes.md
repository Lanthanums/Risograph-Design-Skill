# 页面类型库

页型固定成 **12 个可执行的实现**（`scripts/build_deck.py` 的 `ARCHETYPES`），每个都由同一份几何
与同一套 token 渲染，风格不会飘。修辞型（提问 / 大声明 / 引语 / 大数字）必须只占少数：
这类页型一多，"汇报、讲义、提案"就没有可用配方，agent 只能即兴发挥。

## 页型清单（`archetype` 取值）

| archetype | 用途 | 关键 slot | 推荐背景预设 |
|---|---|---|---|
| `cover` | 封面 | `question` `title` `title_en` `thesis` `highlight` `sticker` `bullets` `subtitle` `aside` | `cover-bleed-tr` |
| `divider` | 章节分隔（反白） | `index` `title` `title_en` `aside` | `reverse-circle-br` / `reverse-blob-bl` |
| `data` | 一个主角数字 + 可选对比条 / 来源块 | `label` `hero` `unit` `caption` `delta` `side` `bars` | `corner-fade-br` / `corner-fade-bl-sm` |
| `features` | 占比排序（一个英雄占比 + 若干条） | `hero` `hero_label` `rows[{label,pct}]` | `corner-fade-tr-sm` / `band-bottom` |
| `quote` | 引语 / 用户原话 | `lines` `highlight` `attribution` `source` | `corner-fade-tr-xs` |
| `grid` | 竞品/方案对比网格（列可高亮"我们"） | `columns[{label,ours}]` `rows[{label,cells}]` `note` | `corner-speckle-tr` |
| `venn` | 两个概念的关系，带真叠印透镜 | `left` `right` `centre` `gap_label` `gap_items` `takeaway` | `edge-fade-left` / `blob-corner-tl` |
| `numbered` | 编号论点 + 对标刻度 | `hero` `label` `gauge{rows}` `takeaway` | `edge-fade-right` / `corner-fade-bl-sm` |
| `timeline` | 流程 / 路线图 / 历史 | `items[{month,unit,name,desc}]` | `blob-corner-tl` / `band-bottom` |
| `ask` | 诉求 + 目标横条 | `asks[{value,unit,name,desc}]` `target` `aside` | `corner-speckle-tr` / `blob-corner-br` |
| `statement` | 大声明（极少字 + 贴纸） | `lines[[text,size]]` `sticker` `body` `note` | `cover-bleed-bl` / `blob-corner-br` |
| `closing` | 结尾页（反白） | `quote` `target` `big` `sticker` | `reverse-circle-tr` |

完整字段见 `build_deck.py --schema`；背景预设的参数见 `design-system.md` §5，
或 `make_textures.py presets`。**不要在页面代码里手写坐标**——用预设名。

## 内容 → 页型映射

| 内容信号 | 页型 |
|---|---|
| 问句（？/?） | `cover` 的开场问句 或 `statement` |
| "总之 / 核心观点 / 答案是" | `statement` |
| 三句以内并列论点 | `numbered`（每点一页，左偏/右偏交替） |
| 比喻 / 名言 / 金句 / 用户原话 | `quote` |
| 两个概念的关系 | `venn` |
| 流程、步骤、路线图、历史 | `timeline` |
| 关键数字 | `data` |
| 占比 / 排序 | `features` |
| 三家以上横向比较 | `grid` |
| 诉求 + 目标 | `ask` |
| 章节切换 | `divider`（反白） |
| 收尾 | `closing`（反白） |

## 页型序列（先排序列，再填内容）

1. 先写出整份 deck 的页型序列，例如
   `cover, data, data, divider, features, quote, grid, venn, numbered, numbered, timeline, ask, closing`。
3. 再往每个 slot 里填内容。填不进去说明页型选错了，回去改序列——不要为了塞内容加小字。

`tests/test_contract.py` 用三份 fixture（英文汇报 / 中文汇报 / 双语讲义）验证：
不同内容的页型序列必须不同，且三份 deck 之间不得共享任何一句 ≥12 字的文案。

## 版式规则

- 构图非对称、有张力：大色块出血、元素叠压、数字特别大、留白不均匀；不要居中堆叠。
- 演讲类每页 ≤30 英文词 / ≤50 中文字；汇报、讲义类可到约 60 词，但必须有明确层级。
- 投影可读：正文 ≥17pt、标签 ≥12pt，大标题要极大；宁可少放内容。
- 每页一个核心观点。一页里出现两个"最重要"的数字，就是该拆页了。

Adjacent equal archetypes are legal. Rhythm is measured across composition signatures and protagonist zones; see scenarios.md. Numeric readability/budget limits are defined in Python.

## Measured region allocation

Cover titles wrap into larger measured multiline regions after reserving supplied
support/stickers. No internal decorative separator fills space. Closing and
statement rules follow the measured content, with statement stickers reserved
first. Venn side/intersection labels fit the actual ellipses; bottom captions and
takeaways have separate regions. Unfit labels fail instead of drifting outside.

Grid `column_weights` (alias `weights`, or per-column `weight`) must be positive
finite numbers and allocate real widths. Timeline descriptions measure against
their own columns' remaining height. Numbered gauges reserve four data rows
separately from the takeaway/support region. Long source text is never silently
cut to a fixed number of lines. See `typefit.py` for diagnostic fitting.
