# Poster input and workflow

New work: artifact: poster, art_direction: {"archetype":"auto"}.
Use poster_run.py --spec source.json --out OUTPUT --render. Fast mode renders once;
unchanged runs reuse verified cache. Audit mode forces a fresh render.
Use plan wireframes during geometry iterations.

content.title is required. Optional exact-source fields:

| Field | Type |
|---|---|
| subtitle, body, cta, footer, date, venue, attribution | string |
| blocks | strings or objects {title,text} |
| process, comparison | strings or {label,text} |
| key_number | string or {value,label}; preserve qualifier/unit |
| quote | string or {text,attribution} |
| data | list of {value,label}; not implicit proportional bars |
| chart | {title,unit,items:[{label,value}]}; 2–6 finite nonnegative values, one unit, zero baseline |
| metadata | string, list or object |

Chart item provenance may include source/status/derivation; preserve qualifications
visibly. Do not infer comparisons from unrelated numbers. Supplied images require
the explicit legacy image_led route.

Poster copy is an approved summary. Never shorten supplied copy to make it fit.
Preflight counts semantic leaves and words, names T3 candidates, and flags pressure;
the measured plan decides capacity.

Output: source.json, poster.pptx, poster.plan.json, plan-summary.json,
poster.style.json, poster-media/, wireframe.png, preflight.json, qa.json,
layout.json, run.json, timings.json. With --render: preview/ PNG+PDF/render.json,
qa-rendered.json, visual/contact.png, visual/review.json.
Scores stay null until inspection. review_valid checks record completeness and
hashes, not aesthetic quality.

build_poster.py --plan --summary remains available. Legacy geometry is in
[poster API](poster-api.md); new geometry belongs in art_direction. columns governs
all content columns including blocks. layout.process_style is reported as requested;
column flows use an explicitly reported numbered chain.
