# Failure modes and remedies

This is a debugging reference, not a mandatory preflight reading list.

| Failure | Cause | Remedy |
|---|---|---|
| An unrelated report inherits an earlier speech poster | Finished artwork became a template | No shipped finished artwork; derive grammar from current content, record reference parameters only |
| A successful preview wraps differently in PowerPoint | A no-wrap frame used a nominal grid width | Measure the entire line with shared no-wrap slack; keep explicit line breaks |
| Paper text vanishes on a paper page | Color was tied to archetype rather than page background | Use Theme front/back roles and reversal state |
| Small display type becomes muddy | Excess shadows and low contrast | Shared stack logic selects offsets/layers; inspect actual rendered contrast |
| Elements scatter into confetti | Free-space filling and an area floor | Anchor first; ceilings only; remove functionless pieces |
| Title loses dominance | Decoration competes with autofitted small type | Fix content hierarchy first, omit rival decoration |
| A quote/bar misses its last word | Character-count approximation | Real glyph spans and measured coverage |
| Every page has the same skeleton | Page-local checking only | Whole-deck signatures and zones; vary existing content pages |
| An artificial statement appears just for pacing | Rhythm was treated as a quota | Emphasize only a supplied thesis, quote, number, or turning point; never add pages |
| A portrait cover is called a poster | Scenario confused with artifact | Use poster-specific grammar and Canvas policy |
| Running a skill dirties its repository | History or cache was stored next to scripts | Per-user state, external outputs, no bytecode during builders |

Three review questions: Does the layout still make sense with decoration hidden?
Can every number/quote be traced to the source? Would replacing the content with
unrelated material force the layout grammar to change? If not, inspect whether
an old design was inherited.
