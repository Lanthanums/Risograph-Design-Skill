# Riso Design Skill

从用户内容生成可编辑的 Risograph 幻灯片或独立海报：有限专色、纸张/印刷肌理、
错位文字与叠印。用真实字体度量和几何检查处理越界、碰撞和装饰预算。
内容与图形关系共同规划，小元素最后落位；预算只有上限，没有配额。

## 安装

Python 3.9+，依赖 `python-pptx Pillow numpy`。将本目录复制为
`~/.codex/skills/riso-slides/` 等 skill 目录。Agent 读取精简的 SKILL.md，
再按 deck/poster 任务加载对应 reference。renderer 可选；PPTX 构建不依赖它。

## Deck

旧 JSON、CLI、默认画布和 12 个页型保持兼容。生成背景后调用：

```bash
python scripts/build_deck.py --schema
python scripts/build_deck.py --spec OUTPUT/deck.json --out OUTPUT/deck.pptx
python scripts/qa.py --deck OUTPUT/deck.pptx --media OUTPUT/media --json OUTPUT/qa.json
python scripts/layout_check.py --deck OUTPUT/deck.pptx --json OUTPUT/layout.json
```

layout 报告新增套级 `deck` section：页型序列、文字 tier、主角区域、布局 signature。
连续近乎相同的构图、极长同质 run、整套大量重复骨架会失败；两页相同页型可以合法。
节奏调整只能强调已有引语、数字、论点或转折，不增加页面，不编造金句。

## Poster

独立 artifact，单页自定义尺寸 PPTX。五种构图语法：`type_led`、`image_led`、
`editorial_event`、`data_poster`、`manifesto_quote`。默认没有 deck 页码或 chrome。

默认启用主图形与辅助元素。`layout.graphic` 可选 `auto`、`band`、`none`，
`graphic_position` 可选 `auto`、`after_title`、`after_content`；由内容与阅读关系决定。
`meta.graphic_element` 指定主方言内的合法图形，`meta.elements: false` 则明确选择纯文字。
用 `--plan --summary` 查看简短诊断；完整 `--plan` 仍可作为 build 输入。

```json
{
  "artifact": "poster",
  "canvas": {"preset": "a3_portrait"},
  "family": "type_led",
  "meta": {"lang": "zh", "palette": "A", "seed": 29, "elements": true},
  "content": {"title": "用户提供的标题"}
}
```

```bash
python scripts/build_poster.py --spec OUTPUT/poster.json --out OUTPUT/poster.pptx
python scripts/build_poster.py --schema
python scripts/build_poster.py --describe-spec
python scripts/build_poster.py --spec OUTPUT/poster.json --plan
python scripts/qa.py --deck OUTPUT/poster.pptx --media OUTPUT/media --json OUTPUT/qa.json
python scripts/layout_check.py --deck OUTPUT/poster.pptx --json OUTPUT/layout.json
python scripts/render.py --deck OUTPUT/poster.pptx --out OUTPUT/preview --keep-pdf
```

画布支持默认 A3 竖版、A4/A2 竖版、4:5、正方形，以及 pt/mm/in 自定义尺寸和比例。
尺寸统一定义在 `canvas.py`，`--describe-spec` 可查询。自定义示例：
`"canvas":{"width":210,"height":297,"unit":"mm"}`。
`--schema` 直接输出可构建的最小 spec，不需要另加 envelope；旧 envelope 仍兼容。
`--plan` 输出可复用的 `{"spec":...,"plan":...}` JSON，不写 PPTX、media、history，
也不创建输出目录。未知字段、非法尺寸/family 和缺输入文件会明确失败。
内容角色除了 title 均可省略；图片必须经过 duotone/halftone，记录处理哈希。
有 renderer 时导出 PNG/PDF；`--render` 导出失败不影响已有 PPTX。
具体字段和 full-bleed 策略见 [poster.md](references/poster.md)。

`layout` 支持：`columns`（`auto`/1/2）、`structure`（`rules`/`none`）、
`title_size`、`body_size`、`alignment`（`l`/`c`/`r`）、
`footer_anchor`（`content`/`edge`）、`vertical_alignment`（`balanced`/`top`）。
字号是最大请求值，仍受可读性下限和区域测量约束。模块按内容采用不等高排版；
balanced 使用有界、可重复的纵向位移，不要求填满。默认 footer 随实测内容末端落位，
edge 是明确的贴边选择。源内容提供 `comparison` 或有序 `process` 标签时才绘制
可编辑比较/流程图；普通正文不自动创造关系。显式 family 下保留 quote/key number，
必要时记录 role demotion；reading order 对应实际绘制对象及 block index。

Poster planning：已提供的目的与观看距离 → 内容角色/层级 → family/构图 →
字体、网格、内容尺度 → 图片/信息图 → 印刷处理 → 最后装饰 → geometry QA → 渲染人工检查。
可选 `brief` 只记录已有约束和来源。

## 实测文字与文件路径

Deck/poster 共用 `typefit.py`：真实字体、显式换行/多段文字、英文单词和中文标点
换行规则；前后标题层共享 fitting 与换行，正文保持 editable。无法容纳时不截断、不丢字，
错误说明 role、block index、可用区域、请求/最低字号及测量需求。先调整合法区域/布局，
必要时由用户明确修订源内容。纸色 print 偏移随字号连续变化且更贴近套印；reverse
允许更强层次；显式 offset 可以覆盖。

spec 内图片、背景目录和 manifest 相对于 spec 文件目录解析，不依赖 cwd。
输出自动创建父目录。`one.pptx` 使用 `one.style.json`、`one-media/`，
`two.pptx` 使用自己的 sidecar/media，可以位于同一目录。QA 优先读取产物独立文件；
兼容 `style.json`、`media/` alias 仅在缺失时创建，不覆盖旧内容。
Deck 每页支持 `exclude_elements`、`element_pool`；poster 放在 `meta`。
空候选池合法，自动装饰过滤带默认文字/数字的元素，显式信息元素必须提供文字字段。

## 状态、测试和视觉证据

运行状态迁到用户目录，优先 `RISO_DESIGN_STATE_DIR`，否则使用系统 app-data/state
路径下的 `riso-design`。history 和 renderer 注册不写入 skill 包。同标题/seed 重建
保留选定 dialect；新作品避开最近的组合。默认目录实际写入失败时警告并使用按用户区分的
系统临时目录，继续读取较新的有效历史；显式 override 不可写则报错，不偷偷换位置。
CLI 构建及内部 import 不依赖外部 `PYTHONDONTWRITEBYTECODE` 保持 skill tree 不变。
同 spec/seed/字体环境的 PPTX、形状和 media 可重复。

字体发现检查 Windows/macOS/Linux 实际文件及 collection face，显式缺字体失败，
自动 fallback 记录诊断。普通 QA 不下载字体，包内不携带完整字体。
`render.py --work-dir PATH` 指定可写转换目录；exit 3 表示尚未解析到路线（可能未搜索 kit），exit 4 表示
执行/工作目录失败。失败保留 PPTX，不发布损坏预览，也不提权绕过执行限制。

`render.py --describe` 只报告发现状态：找到、已搜索未找到、未执行 kit 自动搜索；
不带 flag 时明确提示 `--autodiscover`。发现不等于能执行，必须用真实转换探针验证。
Windows 新建工作和发布目录继承父目录 ACL，避免预览保留私有临时目录的权限。

```bash
python scripts/render.py --describe --autodiscover
python scripts/render.py --deck OUTPUT/deck.pptx --out OUTPUT/preview --keep-pdf --autodiscover
python scripts/qa.py --deck OUTPUT/deck.pptx --render OUTPUT/preview --require-render --json OUTPUT/qa.json
python scripts/layout_check.py --deck OUTPUT/deck.pptx
```

无 `--render` 时，QA 明确报告像素项 **SKIPPED / UNVERIFIED**；结构通过不代表像素通过。
JSON 包含 `pixel_checks`、计划/实测项数、说明和不适用项。`--require-render` 要求完整、
可读的既有预览；缺失、残缺、不可读或新预览源哈希与 PPTX 不符时 exit 3，不自动渲染。
新预览的 `render.json` 记录 PPTX SHA256，旧预览仍兼容。像素采样匹配底层 XML 对象，
使用实测 glyph 区域，不能用空文本框代替。反白页网点与 poster raster-safe-area 的
既有例外明确标注原因，不计入通过数；几何文字安全检查仍执行，亮度差阈值不变。
`layout_check.py` 继续负责 geometry/rhythm。

`test_contract.py --render` 可用时真实渲染三个 fixture；执行失败使测试失败，缺路线
明确报告未验证。可用 `--out PATH` 将验证样例保留在 skill 外。两个 demo 入口的
`--render` 要求渲染和像素 QA 成功。元素颗粒噪声从自身 seed 派生；回归验证所有元素
PNG，以及 deck/poster 连续三次构建的完整字节一致性。

测试入口和完整 CLI 见 [英文 README](README.md)。新增 poster、rhythm、state、export
回归测试，以及 `test_feedback.py` 的反馈坏例/合法例。原 anti-overfit contract 继续禁止
包内成品图和 deck、参考图构图模仿及示例文案泄漏。
gallery demo 必须生成到包外，上传为 [GitHub Release assets](https://github.com/Lanthanums/Risograph-Design-Skill/releases)。

几何检查不代替画面审查。印刷质感、字形、真实对比度、远距离可读性和节奏仍需人工判断；
LibreOffice 预览不等于 PowerPoint 实测。renderer 不可用时须明确标注未执行的检查。

[MIT](LICENSE)。
