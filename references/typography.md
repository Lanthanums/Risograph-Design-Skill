# 字体与实测 fitting

先确认字体真实存在，再决定气质。`textmetrics.resolve()` 在 Windows、macOS、Linux
系统及用户字体目录查找真实文件，按 Pillow/FreeType 报告的 family 匹配；TTC/OTC
逐 face 查找，不能假设中文 face 位于 index 0。返回路径及 collection index 才算解析成功。

`riso_kit.FONTS` 定义默认角色，`Theme` 选择可用的安全链。拉丁展示优先 Georgia，
缺失时可用 DejaVu/Liberation 等本地字体；中文标题优先微软雅黑或平台可用 CJK 字体，
中文正文优先 Noto Serif / 宋体等。角色的自动 fallback 会警告并写入
`font_diagnostics`；用户显式指定但不可用的字体直接失败，不假装替换已验证。
字体不足应列出受影响测试与安装建议，不在普通 build/QA 中下载字体，也不随包携带完整字体。

## 排版顺序

先分配文字角色和可用区域，再调用共享 `typefit.fit()`：内容、解析字体、请求字号、
行距、区域宽高与可读性下限一起参与测量。请求字号是上限；先合理换行和调整区域，
允许的范围内再减小字号，不能把极小字号当作万能解法。

英文按单词断行，过长的不可分单词明确失败。中文按字符并将常见闭合标点与前一单元
组合，避免明显的闭合标点落在行首。显式换行和空段保留，多段之间有文字边界。
所有非空白字符保留，不自动截断、不加省略号、不改写事实。

无法 fitting 时错误包含 role、block index（如适用）、区域、请求字号、最低允许字号
以及测量需求/原因。调用者必须重新安排合法布局或由用户明确修订源内容。
字号下限、层级比例和排版参数以 `typefit.py`、builder、QA 的 Python 常量为准。

`typefit.draw()` 输出可编辑文字，显式测量的行对应 native paragraph，前后标题层使用
同一内容、换行、对齐和字号。纸色 print 采用贴近套印的连续偏移，reverse 允许更强
分离，均随字号变化且有上限；显式 offset 覆盖自动值。旧数值查询接口仍兼容。
Builder 与 QA 共用行记录和 glyph bbox。检查实际印字末端，而不是把最后一行未印字的
leading 误当作越界；混合字体/runs 按各自真实度量处理。

## 中英与应用边界

每个 run 同时设置 `a:latin`、`a:ea`、`a:cs`（由 `style_run` 完成），避免中文退回
未声明的主题字体。中文不使用人工斜体，强调通过墨色/高亮。页眉标签语言和密度遵循
内容及 deck print grammar，不额外创造英文 kicker。

可变字体的 named instance、合成粗体和 glyph rasterization 在 Office/LibreOffice
中存在差异。当前度量使用真实的本地 face，PPTX 声明同 family/粗体；未实际验证的
目标程序不能声称完全一致。渲染后核对 missingFonts、字形、换行、标题偏移与对比度。
几何通过仍需目标观看距离的人审；没有 renderer 时明确报告该边界。
