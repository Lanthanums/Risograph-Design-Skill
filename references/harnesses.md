# Runtime and execution profiles

Select capabilities, not a guessed product name. Never infer installed runtimes,
shell dialect or spawn permissions from the model name. No profile changes the
source facts, readability floors, palette or QA rules.

## Resolve once, then keep the same interpreter

If the harness exposes a workspace-dependency/runtime discovery tool, call it
once and use its returned Python path. Otherwise check an existing project venv,
then the shell's Python (`Get-Command python,py` in PowerShell; `command -v python3`
in bash). Run that interpreter's `scripts/doctor.py --out OUTPUT_DIR`. It saves
`OUTPUT_DIR/doctor-report.json`. The stdlib-only
doctor imports the three core modules, probes output with one exclusive write,
tests a child Python with a 10-second timeout, and shares render.py's configured
and automatic route discovery. With --out it then executes a real conversion and
verifies a nonblank raster probe. ready_build and ready_render are separate.
It does not install anything; discovery alone is not execution verification.

When core imports fail, create a workspace venv with that Python and run its
`-m pip install -r SKILL/requirements.txt`. Install `requirements-render.txt` only
when using PyMuPDF; LibreOffice plus poppler also works. Never install the unrelated
package named `fitz`. Core builds do not require a renderer. Python 3.10+ is the
supported target; use the same interpreter for build, QA and tests.

PowerShell (substitute the paths actually discovered):

```powershell
$risoPython = 'ABSOLUTE/PATH/TO/python.exe'
$env:PYTHONUTF8 = '1'
$env:RISO_DESIGN_STATE_DIR = 'WORKSPACE/.riso-state'
& $risoPython 'SKILL/scripts/doctor.py' --out 'WORKSPACE/output'
& $risoPython 'SKILL/scripts/build_poster.py' --spec 'WORKSPACE/poster.json' --plan --summary
```

Bash:

```bash
RISO_PY='/absolute/path/to/python'
export PYTHONUTF8=1 RISO_DESIGN_STATE_DIR='/workspace/.riso-state'
"$RISO_PY" '/skill/scripts/doctor.py' --out '/workspace/output'
```

Use argument arrays or proper shell quoting. Windows paths containing spaces
require PowerShell's call operator `&`. A Git Bash shell still needs the selected
Windows interpreter; it is not proof that a Linux Python exists.

## Renderer and sandbox

Prefer a supplied compatible LibreOffice kit when available; pass `--kit` and
`--node`, or set `RISOSLIDES_KIT` / `RISOSLIDES_NODE`. For a known LibreOffice binary,
set `RISOSLIDES_SOFFICE` to its absolute path. Avoid repeated recursive discovery.
Renderer work defaults beside the preview output; `--work-dir` overrides it.
The system LibreOffice route gets an isolated profile inside that workspace.
Subprocess calls have a 180-second timeout. EPERM/access denied/crash/timeout is
an execution failure, not evidence that no renderer is installed. Respect the
harness permission boundary; never retry indefinitely or bypass it.

`render.py --describe` only discovers. A real PPTX -> PDF -> PNG conversion proves
execution. Read `render.json`; PNG names are `page-0001.png`, etc. Keep the editable
artifact when rendering fails and report which visual checks remain unverified.
State writes use one exclusive-create attempt, then the documented user/temp
fallback. An explicit unwritable `RISO_DESIGN_STATE_DIR` fails immediately.

## Capability-derived profiles

Use observed capabilities, never model or product names. Record the explicit
input in a JSON file with can_view_images (boolean), command_timeout_seconds
(number), and background_jobs (boolean). Run
`python scripts/run_manifest.py --capabilities CAPABILITIES.json`.

| Observed capability | Execution rule |
|---|---|
| Every environment | Plan synchronously with poster_run --plan-only; inspect its compact files. |
| Command timeout >=180 seconds | One foreground --render command after geometry is settled. |
| Short timeout, background jobs supported | Start the render once, retain its job ID, poll that job. Never wrap cheap planning in a background job. |
| Short timeout, no background jobs | Use an external renderer or a longer command limit; retain editable PPTX and mark rendered QA unverified. |
| Can inspect images | Inspect full/10%/blur contact; fill nine scores and only observed weaknesses. |
| Cannot inspect images | Request human visual inspection; geometry/pixels cannot substitute for aesthetic approval. |

Export measured trials using references/trial-template.json or
`python scripts/run_manifest.py --template`. failures[] records call_index,
error, cause, calls_to_resolve, skill_defect; keep doc_mismatch and deviations.
Count reads/writes/image views/job polls as calls, not only successful builds.
Separate engine_seconds from wall_seconds (agent reasoning and tool round trips).
An experienced replay is not evidence of independent first-use performance.

## Keep the fast path fast

Read SKILL plus the selected route; query `--describe-spec` only for unfamiliar
fields. Choose one content-grounded composition, run `--plan --summary` (poster)
or `--check` (deck), then build. On failure, use the named role/region/deficit;
change one structural cause. Do not enumerate hundreds of seeds or silently
delete content. Render after geometry passes; rerender after a visible change.
Stop iterating when content, geometry and the visual review satisfy the brief.
Do not run regression tests, generate an element contact sheet, or read all source
files for ordinary design work. Warm fitting uses bounded process-local caches.
Process-local entries are not shared; persistent metrics and verified render/input
caches support later commands. See [performance](performance.md).
# Renderer recovery

Run `python scripts/doctor.py --out OUTPUT` once. `ready_build` and `ready_render`
are separate; the latter requires a real PDF→PNG probe (or a clearly labelled
single-slide direct PNG fallback). Package integrity is checked before rendering.
Windows uses `soffice.com` when it is next to the discovered executable.
Runner routing flags are the same as render.py: `--system`, `--autodiscover`,
`--kit PATH --node PATH`. System is exclusive with kit/autodiscover.

If pip/ensurepip cannot write its temporary directory, obtain a compatible wheel
for the selected interpreter/platform through your approved offline distribution.
Do not rename a wheel built for a different Python ABI.

```powershell
New-Item -ItemType Directory -Force OUTPUT/pylibs | Out-Null
python -m zipfile -e PyMuPDF-compatible.whl OUTPUT/pylibs
$env:PYTHONPATH = (Resolve-Path OUTPUT/pylibs).Path
python scripts/doctor.py --out OUTPUT
```

This fallback extracts a previously acquired wheel; it does not install globally.
LibreOffice's `impress_png_Export` accepts PixelWidth/PixelHeight. The fallback
checks actual PNG dimensions and supports only one slide. It does not imply a
working PDF raster backend for multi-page decks.
Reference: [LibreOffice graphic export parameters](https://help.libreoffice.org/latest/en-US/text/shared/guide/graphic_export_params.html).
