---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-089: The studio stays off in the shipped configuration, and the comparison that measured it was registered before it ran

Status: accepted. Date: 2026-11-24.

## Context

[ADR-P007](../design/adrs/ADR-P007-no-multiagent-by-default.md) is a red line: the runtime of the repository stays a
single agent with a deterministic verifier until a paired comparison measures a gain, and the studio of
[specs/013](../../specs/013-r11-multiagent-orchestration-studio/spec.md) is the experimental variant that the
comparison measures. The parts A, B and C of the milestone built the baseline that is frozen
([the page of the baseline](../orchestration/baseline.md)), the dispatcher behind the flag and the journal with
the resume. What the milestone still owed was the comparison itself: the measurement of the two arms over the
same cases, with the same snapshot, and the publication of the result with the decision that follows it.

The package asks for a pre-registered comparison and for a published result, including the result that keeps the
flag off. The repository publishes the failures of its catalog on purpose
([ADR-068](ADR-068-the-published-catalogue-holds-the-failures-and-not-only-the-cases-the-agent-resolves.md)), and
a study that hides its negative result is not a study.

## Decision

**The studio stays off in the shipped configuration, the comparison was registered before it ran, the result was
published with the decision that follows it, and the verifier stayed deterministic.**

1. **The studio is off in the shipped configuration.** The flag `LEDGERLENS_ORCHESTRATION_STUDIO` is off, and a
   run that asks for the studio without a registered experiment is refused. The measurement of this decision does
   not change the shipped runtime: the runtime stays a single agent with a deterministic verifier.
2. **The comparison was registered before it ran.** The manifest of the experiment lives in
   `data/runtime/orchestration/comparison.json`, it names the set, the denominator, the snapshot, the two arms,
   the measures, the rule and the uncertainty, and the first run pinned its digest in
   `data/runtime/orchestration/runs.jsonl`. A manifest written after the first run is refused, because a
   registration that may be rewritten after the run is not a registration.
3. **The result was published with the decision that follows it.** The page of the comparison
   ([the page](../orchestration/comparison.md)) carries the measures of the two arms with their denominator, the
   uncertainty of the difference and the decision. Over the 31 cases of the set, with the model `gpt-4.1-mini`,
   the single agent resolved 21 cases and the studio resolved 23, with an interval of the difference that does
   not cover zero, and the cost per correct case of the studio was not higher than the cost per correct case of
   the single agent. The decision of the registered rule is a gain, and the flag of the studio may open for the
   experiment that is registered and for nothing else.
4. **The verifier stayed deterministic.** The verifier of `ledgerlens/verify/` ran on the claims of the joined
   steps of the studio before the summary, as it runs on the answer of the single agent, and it is code and a
   local cross-encoder in both arms. The studio never replaced it and no model decided an amount.
5. **The answer of the studio is composed and not written by a model.** The summary of the studio renders the
   lines of the evidence that the verifier supported, and the page says so, because a reader has to know what the
   arm answered before it reads the number.
6. **The number is not a generalization.** It was measured over the 31 cases of the set, with this model and with
   this snapshot, one run per case. The page says what the number is allowed to claim, and the threshold of 2
   cases is a decision of the repository and not a statistical significance.

## Alternatives considered

- **To open the flag in the shipped configuration after the gain.** Refused. The rule of the manifest opens the
  flag for the experiment that is registered and for nothing else, and a flag that becomes the default by inertia
  is the risk the plan of the milestone names. The shipped runtime stays a single agent.
- **To publish only the measures and not the decision.** Refused. The package asks for the decision that follows
  the result, and a result without its decision is a result that every reader decides again in its own way.
- **To measure the comparison offline.** Refused. The single agent replays the script of the case when the model
  is scripted, and a comparison over scripted answers measures the plumbing and not the runtime. The script of the
  measurement refuses to run offline and says why.
- **To settle the money of a model whose price was never verified as zero.** Refused. Unknown is never zero
  (ADR-078), and the first run of the comparison was published with the money unknown and the flag off, before
  the price of the served name of the model was read as the price of the alias the deployment declared.

## Consequences

- **The repository has the measurement of the studio**, in `ledgerlens/orchestration/comparison.py` and in
  `scripts/measure_orchestration.py`, with the tests in `tests/orchestration/test_measure_orchestration.py` and
  `tests/orchestration/test_comparison_is_published.py`: the script refuses to run offline, the first run pins
  the digest of the manifest, a manifest written after the first run is refused, the decision is the rule of the
  manifest and the page of the result exists with the decision it carries.
- **The result is published**, in [the page of the comparison](../orchestration/comparison.md) and in
  `data/runtime/orchestration/result.json`, with the record of the runs in
  `data/runtime/orchestration/runs.jsonl`.
- **The flag of the studio may open for the registered experiment and for nothing else.** A second experiment of
  the studio is a second registration, with its own manifest written before it runs.
- **The answer of the studio is composed.** A reader who compares the two arms reads the page of the comparison
  first, because the two arms do not write the answer the same way.
- **The red line of ADR-P007 stands.** The runtime of the shipped configuration is a single agent with a
  deterministic verifier, and the measurement of this decision is the comparison that the red line asked for.

## Links

- [ADR-P007, no multi-agent by default](../design/adrs/ADR-P007-no-multiagent-by-default.md)
- [ADR-068, the published catalogue holds the failures](ADR-068-the-published-catalogue-holds-the-failures-and-not-only-the-cases-the-agent-resolves.md)
- [ADR-078, the model of each slot is chosen by the work it does](ADR-078-the-model-of-each-slot-is-chosen-by-the-work-it-does.md)
- [the page of the comparison](../orchestration/comparison.md)
- [the page of the baseline](../orchestration/baseline.md)
- [the measurement of the comparison](../../ledgerlens/orchestration/comparison.py)
- [the script of the measurement](../../scripts/measure_orchestration.py)
- [the specification of the milestone](../../specs/013-r11-multiagent-orchestration-studio/spec.md)
