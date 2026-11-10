# Riso Slides v4.5

从原稿生成可编辑的英文 Risograph 演示文稿与独立海报。运行时版本 **4.5**。
入口为 [SKILL.md](SKILL.md)，另有 [English README](README.md)。

需要 Python 3.10+，安装 requirements.txt。最终预览需要 LibreOffice 与可用的
PDF 栅格化工具；单页海报支持校验尺寸后直接导出 PNG。参阅[环境配置](references/harnesses.md)。

```bash
python scripts/doctor.py --out OUTPUT
python scripts/poster_run.py --plan content-plan.json --out OUTPUT --auto
python scripts/deck_run.py --plan deck-content-plan.json --require-storyboard --out DECK_OUTPUT --auto
```

在读取参考资料前先确定交付物。默认进入 [PowerPoint 分镜工作流](references/deck-workflow.md)。
明确要求独立海报时进入[海报工作流](references/poster-workflow.md)。
两路分别建立来源绑定、规划内容、设计与验收。定稿保持原文，改写记录合并、
压缩或删除的原因。已有 spec 转换见[输入格式](references/input-formats.md)。

规划阶段使用 --draft。两条管线默认系统 LibreOffice，也可指定 --autodiscover 或 kit。
输入缓存与共享渲染缓存均校验完整性；--mode audit 重新构建、实际转换并运行 QA。
测量方法和边界见[性能与缓存](references/performance.md)。

文字、图表、信息图和锚定元素保持原生可编辑。查看完整图、缩略图和模糊图后再评分。
自动 QA 不代表美观验收或 Microsoft PowerPoint 实机效果。短稿的 A3 留白、部分方言
区别和图形面积目标仍可能不通过，诊断会保留这些限制。

空白运行包只包含脚本、参考文档与依赖清单，排除成品、测试原稿、评测历史、字体、
缓存和本机状态。请将生成文件放在 skill 目录外。构建无需外部图片、下载字体或联网服务。
使用 [MIT 许可证](LICENSE)。
