---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-083: The routing is measured against one model over the same cases, and every number carries its set

Status: accepted. Date: 2026-11-24.

## Context

ADR-078 decided that the model of each slot of a run is chosen by the task the slot does, and it wrote the
decision down before the run starts. The decision was right about the shape of the work: the triage reads a
sentence, the rewrite of the search of the policies is one sentence, the statement has to be correct against a
schema nobody sees, and the answer is made of tool calls.

The decision was a hypothesis about the money, and nobody measured it. The published report of the evaluation
(`data/eval/report_online.md`) measured one model in every slot, which is the behaviour before the router existed,
so the repository had no number that said what the cascade costs against that behaviour. The recordings of the
catalogue name the model of each slot, and a reader could see the division of the work, but nobody could say what
it bought.

The design package asks for exactly this. `R15-02-model-router-with-budgeted-fallback.md` asks for a comparison of
two routes over the same cohort of cases, with the same snapshot, and every number with its denominator and the
set it was measured over. The roadmap of the repository names the same thing as the next one of the evaluation:
the measurement of what the cascade costs against one model for the whole run.

Two facts of the repository constrain the measurement:

- **ADR-037 says that a run of the live mode has exactly one model.** The four slots of the live path are four
  views of the same model of the visitor, and the router does not touch that path. The comparison is a measurement
  of the routing and not of the live mode of a visitor, and it runs over the cohort of the evaluation.
- **The price of `gpt-4.1` was never verified in this repository.** The allowlist carries the price of
  `gpt-4.1-mini`, transcribed by hand on the day of the published evaluation, and the price of `gpt-4.1` is
  absent. ADR-078 says that an absent price is unknown and that unknown is never zero, so the money of the calls of
  that model cannot be stated, and the comparison says so instead of stating a number nobody checked.

Three ways were open to the repository, and two of them were refused for the same reason:

- **To publish the price of `gpt-4.1` from the list price of the provider.** Refused, at least for now. The price
  of a model is a number this repository checks, and the check of the price of `gpt-4.1` has not happened here.
  A price written from a page that no longer lists the model is not a verified price.
- **To compare the two routes with the tokens and not with the money.** Refused as the whole of the comparison. The
  tokens are the comparable number and the report publishes them, but the money is what the reader of the page
  asks about, and the report has to say that the money of one of the arms is unknown.
- **To measure the comparison over the cohort of the evaluation, with the ledger of the sample, and to publish
  every number with its denominator.** Accepted.

## Decision

**The routing is measured against one model over the same cohort of cases, with the same ledger, and every number
of the measurement carries the set it was measured over. Until that measurement runs, the comparison of the routes
is a hypothesis.**

1. **Two arms, one cohort, one ledger.** The arm of one model puts one model in the four slots of the run, and
   the arm of the cascade puts the model of each slot, read from the cascade of the deployment. Both arms run over
   the same cases of `data/eval/eval_cases.jsonl` and over the same ledger, built once from the versioned sample.
2. **The numbers are the ones the package names.** The accuracy by intent, the cost per correct case, the p95 of
   the latency, the rate of fallback and the mix of the models, each one with the number of cases behind it.
3. **The money is text or nothing.** The dollars of the models whose price the allowlist verified are stated, and
   the money of the others is unknown with the reason named. A price that was never verified never becomes a
   price of zero, and a run that reported no usage never becomes a run that was free.
4. **The judge is the deterministic one.** The comparison is about the routing, and the two arms have to be
   judged by the same judge for the numbers to mean something.
5. **The page exists before the measurement.** `docs/routing.md` publishes the cascade, the nine fields of the
   decision and the rules of the honesty before any number exists, and the numbers join the page when the
   measurement runs. A page that exists only when the numbers exist is a page that says nothing while the work
   is going on.
6. **The router reads the registry and the budget and never writes them.** The allowlist of the server and the
   ceiling of the run are read at the start of the run and are not changed by the routing.

## Alternatives considered

- **To publish the cascade as a gain before the measurement.** Refused. ADR-P007 asks for a paired comparison
  before any claim of a gain, and the comparison of the routes is the same rule in the same shape: the routing
  is a preference until it is measured.
- **To run the comparison over a cohort of its own.** Refused. A cohort of its own would make the reader of the two
  reports translate a case of one into a case of the other, and the comparison runs over the cases of the
  evaluation. The refusal carries a limit that the page has to say: the comparison shares the cases of the
  evaluation and not the run of the evaluation, so its numbers are not the numbers of
  `data/eval/report_online.md`, which ran three times per case and judged the answers with the real model of the
  NLI. The two arms of the comparison are the ones that are comparable with each other.
- **To leave the money out of the comparison.** Refused. The money is the question the reader of the page asks,
  and the answer "unknown, because the price of `gpt-4.1` was never verified in this repository" is an answer.

## Consequences

- **The repository has a number where it had a preference**, with the cohort and the ledger it was measured over,
  and the page of the routing says how the number was obtained.
- **The money of the calls of `gpt-4.1` is unknown**, and the page says so. The price of that model is the price
  this repository has to verify before the money of the cascade can be stated.
- **The live mode of the visitor is untouched**, and the four slots of a live run keep being four views of the
  one model of the visitor (ADR-037).
- **The comparison is one run per case**, so the numbers are a trend and not a statistical significance, and the
  page says that too.
- **The numbers of the comparison are not the numbers of the published online report.** The comparison runs once
  per case and judges the answers with the stub of the NLI of the repository, and the published report ran three
  times per case and judged them with the real model. The report of the comparison carries the judge in the field
  `judge`, so a reader of the JSON alone knows what scored the arms.

### What the measurement found

The measurement ran on 2026-11-24 over the 31 cases of the cohort, with the ledger of the sample, and the numbers
are in `data/eval/routing_comparison.json` and in [the page of the routing](../routing.md).

- The arm of one model was the more accurate one over the cohort: 22 of the 31 cases against 21 of the cascade.
- The cascade used fewer tokens per correct case, 10461 against 11528, its p95 of the latency was lower, 6412 ms
  against 10612 ms, and it made 14 calls less over the same cohort.
- The money of the arm of the cascade is unknown, because the price of `gpt-4.1` was never verified here, so the
  comparison cannot say that the cascade is cheaper in dollars. The tokens say that it used less of them.
- The rate of fallback was zero in the two arms, and the number was not measured, because the repository does not
  have a fallback with a budget in this path, so the zero says that the question was not asked.
- The comparison ran twice over the same cohort and the two runs disagreed about which arm was more accurate: the
  first run gave the cascade 21 of the 31 cases against 18 of the one model, and the second gave the one model 22
  and the cascade 21. The difference of the accuracy of the two arms is therefore not established, and the tokens
  and the latency of the cascade are the numbers that both runs agree on.

The comparison is therefore measured, and it is still not a claim of a gain: a measurement over one run per case
shows what happened, and the router stays a preference until a paired comparison over more runs says more.

## Links

- [ADR-037, the case of the demo runs on a bridge over the caller of the run](ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md)
- [ADR-078, the model of each slot is chosen by the work it does](ADR-078-the-model-of-each-slot-is-chosen-by-the-work-it-does.md)
- [the page of the routing](../routing.md)
- [the comparison of the routes](../../ledgerlens/eval/routing_comparison.py)
- [the script of the measurement](../../scripts/measure_routing.py)
