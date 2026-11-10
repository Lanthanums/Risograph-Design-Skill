# Riso Slides v4.5

Create editable English Risograph presentations and standalone posters from supplied
content. Runtime version **4.5**. Start with [SKILL.md](SKILL.md).
[中文说明](README_zh.md).

Use Python 3.10+ and install requirements.txt. Final previews need LibreOffice
and a supported PDF raster route; single-page posters also support verified
direct PNG export. See [environment setup](references/harnesses.md).

```bash
python scripts/doctor.py --out OUTPUT
python scripts/poster_run.py --plan content-plan.json --out OUTPUT --auto
python scripts/deck_run.py --plan deck-content-plan.json --require-storyboard --out DECK_OUTPUT --auto
```

Select the deliverable before opening source material. Use the
[PowerPoint storyboard workflow](references/deck-workflow.md) by default.
Use the [poster workflow](references/poster-workflow.md) for a requested
standalone poster. Each workflow has its own source plan, design and review.
Approved copy stays verbatim. Adaptations retain an atom inventory and coverage
ledger. See [input formats](references/input-formats.md) for compatibility.

Use --draft while planning. Both runners default to system LibreOffice; choose
--autodiscover or an explicit kit when needed. Verified input and render caches
avoid repeated work; --mode audit rebuilds, converts and checks afresh. See
[performance and cache](references/performance.md) for boundaries and benchmarks.

Native text, diagrams, charts and anchored glyphs remain editable. Inspect full
PNG, thumbnail and blur before assigning scores. Automated QA does not establish
aesthetics or Microsoft PowerPoint fidelity. Sparse A3 content and some dialect
and graphic-area targets can still fail; diagnostics retain those limits.

The blank runtime contains scripts, references and dependency lists. It excludes
generated artwork, source examples, test/evaluation history, fonts, caches and
machine state. Keep outputs outside this directory. No external images,
downloaded fonts or network services are required by the build pipeline.
Licensed under [MIT](LICENSE).
