# Scenario Expansion and Educational Experiments

The existing `data/scenarios.json` includes 12 planted scenarios S01 - S12. **Preserve those identifiers** and their ground truth. Add new scenarios under separate versioned namespaces (`X-*`, `SEC-*`, `ECON-*`, `DOC-*`), never silently change an old expected answer. Existing S11 (FX outage) and S12 (past-case memory) are especially valuable for systems thinking.

## Existing scenarios → extended experiments

| Base | User experiment | What changes | Invariant / insight |
|---|---|---|---|
| S01 FX refund TX-2048 | Rate changed, markup changed, reference rate date unavailable | sandbox `FxRateOverride` and policy version | actual applied FX is distinct from ECB reference |
| S02 TX-2051/TX-2052 | move second event outside 5-min window | event timestamp | duplicate heuristic can change; never prove fraud |
| S03 CB-0310 | move internal cutoff, simulate holiday/calendar | deadline policy and time | escalation cannot depend on host local time |
| S04 TX-9999 | create near-match ID, keep absent original | branch transaction ID | avoid hallucinated row |
| S05 ambiguous customer | remove one transaction/merchant mapping | source records | clarifying question vs confident result |
| S06 refund outside window | version policy to 45 days | versioned policy | contract temporal precedence |
| S07 no discrepancy | inject one-cent discrepancy | exact minor unit | no floating point drift |
| S08 ST-0044 | modify fee, weekend and holiday | fee schedule, date | settlement reconciliation with monetary invariants |
| S09 prompt injection | wrap malicious instruction as policy note | lower-trust content | never acquire tool rights |
| S10 unsupported ARS | route to disabled vs supported alternate source | tool catalog/availability | unknown is preferable to guessed FX |
| S11 upstream down | recover or retry provider in fixed time | fault injector | bounded retries, partial result |
| S12 past case memory | poison/forget/restore approved case | memory snapshot | provenance and scope win over repetition |

## Extended case families

- `X01` split refund across two methods; `X02` negative fee correction; `X03` duplicate settlement id; `X04` refund after partial chargeback; `X05` wrong currency precision; `X06` merchant-specific vs global policy collision; `X07` conflicting payment and API statuses; `X08` late arrival of event; `X09` out-of-order reversal; `X10` ambiguous merchant alias; `X11` stale FX reference after data refresh; `X12` policy with missing effective date; `X13` rate stale but available; `X14` numeric claim without matching currency; `X15` retrieval returns plausible wrong clause; `X16` similar case from another account; `X17` aggregate SQL approaches max rows; `X18` 2-second SQL timeout; `X19` tool response malformed; `X20` NLI contradiction false positive.
- `SEC01` fake system instructions in note; `SEC02` forged evidence ID; `SEC03` hostile policy excerpt; `SEC04` memory contamination; `SEC05` unauthorized account ref; `SEC06` unauthorized tool; `SEC07` fabricated tool output; `SEC08` expired model key; `SEC09` oversized input; `SEC10` malicious PDF metadata; `SEC11` inter-agent spoof; `SEC12` side-channel secret check.
- `ECON01` fast but inaccurate chain; `ECON02` costly multiagent that offers no benefit; `ECON03` low-cost router that over-escalates; `ECON04` review queue saturation; `ECON05` incorrect policy leading to modeled loss; `ECON06` uncertain model with abstention; `ECON07` caching saves tokens but returns stale policy; `ECON08` human-review constrained by staffing; `ECON09` failed provider with expensive retries; `ECON10` new model version degrades tool trajectory.
- `DOC01` synthetic bank statement vs ledger; `DOC02` screenshot with erroneous amount; `DOC03` policy PDF revision; `DOC04` unreadable document; `DOC05` OCR confusing decimal separator; `DOC06` multilingual customer email.

## Experiment structure

Every scenario stores `id`, `parent`, `snapshot_hash`, `source_licenses`, `question`, `fixture_version`, `mutations`, `oracle`, `allowed_outcomes`, `safety_tier`, `learning_objective`, `difficulty`, `cost_budget`, `expected_trace_pattern`, `status`. Oracle must be recomputed by deterministic code for changed data or explicitly marked invalid; never reuse a recorded answer as if it matched a changed branch.

## Laboratory pedagogy

**Predict → intervene → observe → explain → compare → retain.** Before showing a replay conclusion, ask the visitor what they expect. Let them change one variable, then show the factual diff, tool trace diff and verified decision. Store visitor's learning preference locally only if opted in, not in agent long-term case memory.
