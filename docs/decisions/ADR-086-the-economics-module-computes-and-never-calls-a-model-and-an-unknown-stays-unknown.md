---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-086: The economics module computes and never calls a model, and an unknown stays unknown

Status: accepted. Date: 2026-11-24.

## Context

The repository knows what a single live run cost. The coordinator of the budget counts the calls of every model, the
registry carries the price of each model with the source that publishes it and the day it was last verified, and the
report of the run refuses to print a dollar amount when the price was never checked (FR-010, FR-011).

That is the cost of one run. What the repository had no answer for is the cost of a cohort, the cost of a case that
was actually resolved, the cost of a review by a person and the loss a policy carries when it is wrong. The
milestone of [specs/005](../../specs/005-r4-runtime-latency-and-cost-per-case/spec.md) promised an economics module and
did not build it, and the design packages
[LL-V3-R9-03, cost per correctly resolved case](../v3/advanced-specs/R9-03-cost-per-correctly-resolved-case.md)
and [LL-V3-R9-06, risk weighted decision utility](../v3/advanced-specs/R9-06-risk-weighted-decision-utility.md)
say what the module has to do.

Two things were true of the numbers the repository published until now, and both were limits of what could be
measured. The comparison of the routes published a cost per correct case whose denominator was a number of cases with
a full score, and it published no cost per case that was escalated to a person, because the money of a review is an
assumption that nobody had stated. And nothing anywhere weighed the loss of a wrong decision against the money of
the run that made it, because the losses of the classes of the error are assumptions too.

The design of the module had three rules that had to survive the implementation: the oracle of a resolved case comes
from the code that resolved it, an unknown is never a zero, and the module never chooses a model.

## Decision

**The economics of a run is a package that computes over the results of the runs that already happened, and every
number it publishes carries the assumptions that produced it.**

1. **The package is a leaf of the domain and it never calls a model.** `ledgerlens/economics/` computes, and it reads
   the results of the runs that already happened. It imports no model, no registry that calls one and nothing of the
   API, and the test reads the modules with `ast` and refuses the import. One run has one model under ADR-037 and the
   FR-013 it carries, and a module that could call a model would be a second way of calling one, outside the budget
   and outside the trace of the run.
2. **The oracle of a resolved case comes from the code.** The module reads the label that the evaluator of the
   repository produced and never recomputes a verdict. A case is resolved when its label is a full score, and a case
   that went to a person is not a resolved case: it pays the money of its review and it is not in the denominator.
3. **An unknown is never a zero.** A price that was never verified leaves the money of a category unmeasured, and
   the total of the cohort with it, and the report names the category that is missing. A probability that was never
   calibrated leaves the expected loss unknown, and a loss that nobody knows leaves it unknown with the class named.
   A cohort with no resolved case produces no cost per resolved case and the reason why.
4. **The four categories of the cost do not overlap.** The money of the calls of the models, the money of the
   compute, the money of the review and the money assumed for the error are four parts, and a case with two parts of
   the same name is refused because it would count the same money twice.
5. **The assumptions are fields and they travel.** The minutes of a review, the rate of an hour and the price
   snapshot are assumptions of the reader, and they live in `ledgerlens/economics/assumptions.py` and never in the
   code. Every result that uses one carries it, and every assumption names the source it came from and the day it
   was stated.
6. **The comparison is over the same cohort, and the refusal is checked against the digest.** Two cohorts over
   different cases are not comparable, and the digest of the cases is what says that they are the same, because two
   runs can carry the same name over different cases. The denominator of each arm is published apart, because the two
   arms resolved a different number of cases.
7. **The false accept and the false reject never share a number.** The two classes of the error cost different
   things, and a number that merged them would hide which one hurt. Two classes that overlap are refused before the
   sum, because a case that is in both of them would be counted twice.
8. **The module publishes no return.** A return is a claim about the future, and the module computes over the runs
   that already happened. It publishes the loss, the coverage and the assumptions, and the reader decides what they
   are worth.
9. **The export copies, hashes and labels and never changes the content.** The artifact of a cohort carries the hash
   of its content and the digest of the cohort it was computed over, and the export is byte identical when it runs
   twice. A cohort whose digest moved is refused.
10. **A router that picks a model by cost stays behind a flag.** The economics module compares the results of the
    runs that already happened and it never chooses a model. A design that routes between models by cost is a
    different piece of work, it stays behind a flag, and it is published only after a paired comparison measures a
    gain, under ADR-P007.

## Alternatives considered

- **To recompute the verdict of a case inside the economics module.** Refused. The oracle of a resolved case comes
  from the code that resolved it, and a module that recomputed the verdict would be a second oracle that could
  disagree with the first.
- **To publish the cost per correct case with the denominator of the cases with any score.** Refused. A case with a
  partial score was not settled, and a denominator that holds it hides the cost of the cases the system did not
  settle.
- **To treat an unverified price as a zero and to publish the total.** Refused. A zero would say that the call was
  free (FR-011).
- **To let the economics module call a model to price a case.** Refused. One run has one model (ADR-037), and a call
  of the module would be outside the budget and outside the trace of the run.
- **To publish a return, a payback or a recommendation of staffing.** Refused. A return is a claim about the future,
  and the assumptions that would carry it are the reader's and not the repository's.

## Consequences

- **The repository has the economics module**, in `ledgerlens/economics/` (`assumptions.py`, `cost.py`, `utility.py`
  and `publish.py`), with the tests in `tests/economics/`: the assumptions are fields, every amount is a `Decimal`,
  the categories do not overlap, the denominator holds only the cases the code resolved, a cohort with no resolved
  case produces no number and the reason, the comparison over two cohorts is refused, the two classes of the error
  never share a number, an uncalibrated probability is unknown, and the export is byte identical and carries the
  hash and the digest.
- **The published economics of the measured cohort are in `data/eval/`.** The cost per correctly resolved case of the
  arm of one model is 0.005076 dollars over 22 resolved cases of the 31 of the cohort, which is the same number the
  comparison of the routes publishes. The arm of the cascade has no cost per resolved case, because the price of
  `gpt-4.1` was never verified, and the artifact says so and prints no amount (FR-011, ADR-078).
- **The comparison of the two arms has no difference**, because the money of one of them is unknown, and the
  artifact names the reason instead of printing a difference of nothing.
- **The script `scripts/export_economics.py` publishes the artifacts** from the published measurement of the
  comparison of the routes, and it never calls a model.
- **The cost of a review is an assumption and not a fact**, and the cohort of the published measurement holds no case
  that went to a person, so no review money enters the published total. The assumption travels with the artifact
  anyway.
- **The utility of the three policies is computed and not measured.** The automatic resolution, the review of
  everything and the abstention are compared over the same mix of cases, and the losses of the classes of the error
  are the reader's. The module publishes the three losses and no recommendation.

## Links

- [ADR-034, the registry of the tested models, the two costs of a run and the endpoint](ADR-034-the-registry-the-budget-and-the-endpoint.md)
- [ADR-037, the case of the demo runs on a bridge over the caller](ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md)
- [ADR-054, the agent loop has a ceiling in every path](ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md)
- [ADR-072, a currency the reference source does not publish is missing data and the case goes to a person](ADR-072-a-currency-the-reference-source-does-not-publish-is-missing-data-and-the-case-goes-to-a-person.md)
- [ADR-074, a case ends in a decision and the decision belongs to the code](ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md)
- [ADR-078, the model of each slot is chosen by the work it does](ADR-078-the-model-of-each-slot-is-chosen-by-the-work-it-does.md)
- [ADR-083, the routing is measured against one model over the same cases, and every number carries its set](ADR-083-the-routing-is-measured-against-one-model-over-the-same-cases-and-every-number-carries-its-set.md)
- [ADR-P007, no multi-agent by default](../v3/adrs/ADR-P007-no-multiagent-by-default.md)
- [the page of the routing](../routing.md)
- [the package of the economics](../../ledgerlens/economics/)
- [the test of the cost](../../tests/economics/test_cost.py)
