# Performance and cache

Run `doctor.py --out OUTPUT` once per environment; use `--refresh` after changes.
Choose `--draft` while planning and `--auto` for final checks.

## Fast and audit

Both runners default to `--mode fast`. A verified complete-input cache can restore
a successful run before importing presentation/image libraries. Keys include
source bytes, assets, runtime code, dependencies, renderer identity, environment
options and the shared font catalog. Used fonts and cached files are SHA-256
checked. Corrupt entries are misses.

A separate shared render cache reuses PNG/PDF outputs when saved PPTX, renderer,
route, fonts, DPI and options match. Structural and rendered QA still run on
this path. Verified local previews take precedence over copying the shared entry.
Changed input with identical PPTX can reuse rendering without reusing its source
and coverage approval.

`--mode audit` skips both caches for actual conversion and fresh QA.
`INPUT_CACHE_HIT` means cached QA was SHA-verified; `CACHE_HIT` means rendering
was reused but QA ran again. Neither grants visual approval. Matching hash-bound
poster/deck-page reviews survive cache restore; changed artifacts invalidate them.

State stays outside the skill. Set `RISO_DESIGN_STATE_DIR` to a writable workspace
directory to isolate jobs. Conversions share an isolated, locked LibreOffice
profile. Use a distinct `RISO_RENDER_PROFILE` for separately isolated sessions.
Never share an output directory between writers.

## Measure whole commands

```bash
python scripts/bench.py --plan content-plan.json --target poster --out BENCH --repeats 3
python scripts/bench.py --plan deck-content-plan.json --target deck --out DECK_BENCH --repeats 3
```

Reports separate subprocess wall time from internal stages. Fresh output does not
imply cold OS/font/LibreOffice state. Compare equivalent profiles and DPI; never
present cache reuse as faster cold conversion. Font metadata/digests are memoized
within a process by path, size and timestamp; full-input cache integrity still
reads file bytes. Text audits reuse line measurements within a single call, so
shape edits are observed immediately.

Remaining limits: short copy can fail A3 whitespace gates; choose a suitable
format or obtain more source content. Evidence-area/dialect warnings remain
diagnostics, not quality guarantees. Variants still repeat build/binding work
around batched rendering. Deck renders are cached as a whole, not by page.
Fixed command latency and cold-render speedups are not guaranteed.
