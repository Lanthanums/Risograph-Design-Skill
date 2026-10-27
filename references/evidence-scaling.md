# Source evidence and continuous policy

`scripts/source_profile.py --plan content-plan.json --out source-profile.json`
uses source text, not agent-selected info_type, to measure qualified quantities.
Each tag records kind, strength 0–1, exact atom/offset/quote provenance. English and
Chinese quantities and 百分之 are supported. Years, dates, times, phone/IDs,
enumerations, list counts, ranks and idioms are excluded with recorded reasons.
Unqualified bare numbers are conservatively excluded; source unit context matters.
No parser can prove the meaning/truth of arbitrary prose: inspect exclusions.

Density is .7(1−exp(−N/4)) + .2(1−exp(−C/4)) + .1(1−exp(−P/3)), where N is
qualified quantities, C is comparable extra points and P is explicit part-whole
groups. Non-numeric quote/contrast/definition/sequence evidence is tagged but does
not inflate data density. Adding non-data text does not dilute existing evidence.

The only numerical policy table is `scripts/evidence_scale.py:TABLE`:

| e | words | L2 | words/L2 | max text fraction | bounds presence target | density score |
|---|---|---|---|---|---|---|
| 0 | 140–320 | 1–6 | 100 | 1 | 0–.12 | 0 |
| .25 | 120–260 | 2–6 | 80 | .9 | .02–.22 | .25 |
| .5 | 100–210 | 2–6 | 64 | .7 | .08–.32 | .5 |
| .75 | 90–170 | 3–6 | 48 | .5 | .14–.42 | .75 |
| 1 | 90–140 | 3–5 | 36 | 1/3 | .20–.50 | 1 |

All numeric values interpolate linearly; count bounds round outward at the end.
Sparse/normal/rich is the quantized output of a continuous density score, not the
evidence classifier. Body remains >=18pt. Budget warnings never request padding.
Bounds targets are provisional engineering calibration bands, not aesthetic gates
or a claim of empirically validated ink coverage. Raster evidence is reported
separately and cannot be directly compared to the bounds target.

Plans store `evidence: {profile,level,override_reason}`, modules store
`evidence_basis`. `content_plan.annotate` computes both. Overrides require a
nonempty reason and do not bypass local source evidence rules. Data forms need
source quantities; comparable points need one unit; rings need part-whole;
process order needs source order; relationship forms need exact relation phrases.
Each chart point has `atom` and exact numeric value. Derived values retain the old
expression/reason requirement and never count as source evidence.

Low-data forms: takeaway-list, key-statement, contrast-pair, definition-card,
summary-box, keyword-band, concept-stack and hub-spoke. Nodes/phrases must come
from bound atoms; numbering is navigation, never an asserted measurement.
For adapt, author L1 thesis, condensed L2 and retained L3 source sentences; record
each destination and condensation reason in the ledger. The script never calls a
model or fabricates a rewritten summary.

Missing evidence on v3.7 input is computed with a deprecation diagnostic. Old
explicit forms remain constructible but are marked legacy/unverified. Re-annotate
to opt into strict fabricated_evidence checks, then correct any unsupported form.
