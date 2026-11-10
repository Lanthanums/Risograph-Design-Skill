# Poster content before composition

Every runner build requires a passing content-plan.json bound to its source and spec.
Use `--skip-plan` only for an explicit legacy reproduction; the manifest records it.
No network or language model is called by the planning utility.

1. State purpose (standalone / talk support / posted), audience, thesis and CTA.
   Read the source profile and [evidence policy](evidence-scaling.md) before selecting forms.
2. Inventory source fields as atoms. Keep source text and its SHA256 in the plan.
3. Annotate each atom: statistic, claim, process_step, comparison, part_whole,
   timeline, definition, quote, example, cta, logistics, source.
4. Give equivalent claims a common `fact_key`; present each fact once.
   A statistic belongs in its visual data, not repeated in a prose paragraph.
5. Assign L1 title + evidence-supported hero (≤2), evidence-scaled L2 primary modules,
   L3 supporting modules (≤8), L4 footer information.
6. Metadata uses weight ≤.35 in a footer ticket. It must not compete with evidence.
7. Group parallel modules with the same `group` and consecutive `order`.
   Process order is explicit. The compiler retains `keep_together`.
8. Use the continuously interpolated word/module/text-fraction budget from source
   evidence; body ≥18pt for A3. Include headings and visual labels, excluding L4 citations.
   Preflight measures the actual font/canvas; change geometry before reducing copy.

| Information | Default editable form |
|---|---|
| qualified statistic | big-number + label, source integer pictogram-row |
| source comparison | comparable same-unit bars, or textual contrast-pair |
| process_step | step-flow with connected numbered badges |
| part_whole | ring or stacked-bar |
| timeline | track + dated nodes |
| quote | pull-quote with attribution |
| definition / claim / example | definition-card, summary-box, key-statement |
| cta | stamp |
| logistics / source | footer ticket |

## Copy modes

`verbatim`: final poster copy. Every atom must be kept unchanged. Overflow
does not authorize paraphrasing or deletion. Use editorial for dense legacy copy.
Duplicate source copy warns in verbatim mode; removing it requires author adaptation.
`adapt`: default choice when the input is a speech, article or rough summary.
The authoring agent condenses it into modules and records every kept, merged,
condensed or cut atom. The script validates; it never invents a summary.
Put quotations and proper names in each atom's `protected` list.
Every output number must occur in that module's source atoms. A derived number
needs `{value, expression, reason}` in `derived`; the author verifies the calculation.
Do not convert illustrative assumptions into externally verified statistics.

## Single invocation

For lossless migration:

```bash
python scripts/content_plan.py --from-spec INPUT.json --out content-plan.json --to-spec planned-spec.json
```

This generates + lints + converts once. Migration defaults to verbatim/editorial;
it does not pretend to infer semantic duplicates. For new adapted work, write the
plan directly, then lint and compile in one call:

```bash
python scripts/content_plan.py --plan content-plan.json --out content-plan.json --to-spec planned-spec.json
python scripts/poster_run.py --plan content-plan.json --out OUTPUT --auto
```

Plan shape:

```json
{
  "schema_version":"1.0", "target":"poster", "mode":"infographic", "copy_mode":"adapt",
  "purpose":"posted", "audience":"supplied audience", "thesis":"supplied central claim",
  "cta":"supplied action", "source":{}, "source_sha256":"generated from source",
  "atoms":[], "modules":[], "ledger":[]
}
```

Each module has id, level, role, info_type, visual, headline, body, weight, group,
order, atoms, and optional visual_data. Atom IDs come from the original source field
paths. If visual is omitted, the compiler chooses the information-type default.
Ledger entries have atom, status, into (module ID array), reason.
Use `content_plan.scaffold` to obtain the inventory and source hash; do not handwrite hashes.
An output mutation invalidates the binding. Recompile after modifying the plan.

## Gate boundaries

Lint detects exact/fact-key duplicates, source/ledger inconsistencies, missing labels,
numeric provenance, text budgets, metadata weight, group contiguity and hierarchy.
It cannot prove semantic equivalence of arbitrary paraphrases or identify every proper
name automatically. Author `fact_key` and `protected` annotations are part of planning.
Warnings are not aesthetic approval. Source qualifications must survive adaptation.
