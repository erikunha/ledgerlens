# Feature Specification: Cost per correctly resolved case and risk weighted decision utility

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: [ADR-034](../../docs/decisions/ADR-034-the-registry-the-budget-and-the-endpoint.md),
[ADR-054](../../docs/decisions/ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md),
[ADR-072](../../docs/decisions/ADR-072-a-currency-the-reference-source-does-not-publish-is-missing-data-and-the-case-goes-to-a-person.md),
[ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md),
[ADR-077](../../docs/decisions/ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md) and the
design packages [LL-V3-R9-03, cost per correctly resolved case](../../docs/design/advanced-specs/R9-03-cost-per-correctly-resolved-case.md)
and [LL-V3-R9-06, risk weighted decision utility](../../docs/design/advanced-specs/R9-06-risk-weighted-decision-utility.md).
The milestone that promised the economics module is
[specs/005](../005-r4-runtime-latency-and-cost-per-case/spec.md).

The package was written for a greenfield plan. The repository has since built the cost of a live run, the registry of
the prices with their provenance, the evaluators that say whether a case was resolved and the code that decides the
case. The economics module that the milestone of [specs/005](../005-r4-runtime-latency-and-cost-per-case/spec.md)
promised does not exist. This specification builds it, and it adds the part of the package that has no equivalent at
all: the risk weighted utility of a decision.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The reader knows what one investigation cost (Priority: P1)

A reader asks what a case cost. The answer names the calls of the model, the tokens, the price of the model, where
the price comes from and the day it was last checked, and the total in the currency of the run. The money is exact.
When the price of the model was never verified, the answer says that the price is unknown and prints no amount.

**Why this priority**: the cost of a run is already computed for the live mode, and it is the base of every other
number of the economics. A total that came from a guessed price is worse than no total.

**Independent test**: read the cost of a run whose model has a verified price and read the cost of a run whose
model does not. The first prints the exact total of the calls and the tokens and names the source and the date of
the price, and the second prints that the price is unknown and prints no amount.

### User Story 2 - The reader knows what a correctly resolved case cost (Priority: P1)

The reader asks what a case cost when it was resolved and what it cost when it was not. The number is the total of
the cohort divided by the number of the cases that were resolved, the denominator is shown next to it, and the cases
that went to a person are not in the denominator and do pay their cost of the review. When no case was resolved, the
number does not exist and the reason says why.

**Why this priority**: the cost per case without the denominator is a token count with a better name, and the cost of
a case that a human had to read is a cost that the repository does not count today.

**Independent test**: compute the cost per correctly resolved case over a cohort with a known price, a known rate of
a review and a known number of resolved cases, and then over a cohort where no case was resolved. The first prints
the exact division with the denominator visible, and the second prints no number and names the reason.

### User Story 3 - The reader compares two architectures over the same cases (Priority: P1)

The reader asks which architecture is cheaper. The answer compares the two over the same cases, with the same
snapshot and with the same criteria of evaluation, and it refuses the comparison when the cohorts are different. The
refusal names the two cohorts and their digests.

**Why this priority**: the cheapest architecture over one set of cases and the cheapest over another set of cases
are two numbers with no relation, and most of the misleading comparisons in the literature are exactly that.

**Independent test**: compare two architectures over the same cohort and read the result, then compare them over two
different cohorts. The first names the number of the cases, the totals and the cost per resolved case of each one,
and the second is refused with the digests of the two cohorts.

### User Story 4 - The reader changes the assumptions of the review and sees the number move (Priority: P2)

The reader believes that a review takes six minutes and that an hour of a reviewer costs a certain amount. The
report shows the assumptions it used, the reader changes them, and the number moves. The assumptions are never
constants of the code and they are never presented as a fact of the world.

**Why this priority**: the cost of the human review is the part of the cost that the repository cannot measure, and
the only honest way to publish it is as an assumption with its source.

**Independent test**: compute the cost per correctly resolved case with the default assumptions and with other
assumptions, and assert that the report names the minutes and the rate that produced the number in both cases and
that the two numbers differ.

### User Story 5 - The reader sees the risk of a policy in money (Priority: P1)

A reader asks what happens when the system resolves the cases itself, when every case goes to a person, and when
the system abstains on the uncertain ones. The answer gives the expected loss of each policy in money, with the
cases separated: a case that the system accepted and that was wrong is not the same case as one that it sent to a
person and that was not needed. The answer says how the probabilities were obtained, and it says that a probability
that was never calibrated cannot be read as a probability.

**Why this priority**: this is the part of the package with no equivalent in the repository, and it is the part that
decides whether a cheaper agent is actually a worse one. The whole question of the milestone is here.

**Independent test**: compute the expected loss of the three policies over the same mix of cases, with a calibrated
probability and with an uncalibrated one, and assert that the false accepts and the false rejects appear apart, that
the expected loss of the uncalibrated run is published as unknown or as a range and never as a point, and that the
assumptions of the mix travel with the result.

### User Story 6 - The reader sees where abstaining starts to pay (Priority: P2)

The reader asks at which level of confidence the system should stop and send the case to a person. The answer is a
curve: for each level of coverage, the risk that remains and the cost that was paid. The curve is drawn over the
same cases and with the same losses.

**Why this priority**: the curve is the picture that turns the confusion counts into a decision, and it is the
figure that a reader of the design package expects.

**Independent test**: compute the risk coverage curve over a cohort with known labels and assert that the points are
ordered by coverage, that each point names the cases it covered and the risk it left, and that the curve is empty
and says so when the labels carry no probability.

### User Story 7 - The reader does not read a claim of a return that nobody measured (Priority: P2)

A reader asks whether a change is worth it. The answer refuses to state a return and states what it can state: the
cost of the cohort, the number of the cases that changed, the direction of the difference and the interval of the
uncertainty. A claim of a saving, of a return or of a benefit appears only when a measurement produced it.

**Why this priority**: the design package says no magic return claims, and the repository says the same about
everything else. A number that nobody measured is the fastest way to lose the trust of a technical reader.

**Independent test**: ask the module for a return and assert that the answer refuses with the reason, and that the
answer carries the numbers it can carry.

### Edge Cases

- A model with no verified price: the total in dollars is not published as a measurement, and the report says which
  price is missing.
- Two cohorts with different digests: the comparison is refused.
- A case that was cut by a cap: it is scored as a case that was cut and not as a wrong answer, and the report shows
  the two apart.
- A case that went to a person: it is not in the denominator of the cost per resolved case and it pays the cost of
  the review.
- A review of a case that never happened: it costs nothing, and no minute is invented.
- Two error classes that overlap: the summation is refused and the overlap is named.
- A probability that was never calibrated: it is published as a range or as unknown, and never as a point.
- A loss of a class that nobody knows: the expected loss of that class is unknown, and the total is published as
  unknown rather than as a number that hides the gap.
- Two currencies and no dated rate between them: the normalisation is refused and no dollar amount is printed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every amount of the economics is a `Decimal` and never a float, and every amount that comes from a
  price names the source of the price and the day it was last verified.
  - Test: `tests/economics/test_cost.py` fails while a total is a float or while a price carries no provenance.
- **FR-002**: The cost of a case is the sum of the non overlapping categories of the model, of the compute, of the
  review and of the error assumption, and a category that overlaps another is refused.
  - Test: `tests/economics/test_cost.py` fails while two categories count the same money twice.
- **FR-003**: The cost per correctly resolved case is the total of the cohort divided by the number of the cases
  that were resolved, the denominator travels with the number, and a cohort with no resolved case produces no number
  and a reason.
  - Test: `tests/economics/test_cost.py` fails while a cohort with no resolved case produces a zero.
- **FR-004**: A case that went to a person is not a resolved case and pays the cost of its review, and the review
  that never happened costs nothing.
  - Test: `tests/economics/test_cost.py` fails while a case that went to a person is in the denominator.
- **FR-005**: The minutes of a review and the rate of an hour are assumptions that travel with every number they
  produce, and they are never constants of the code.
  - Test: `tests/economics/test_assumptions.py` fails while a report of the cost does not name the assumptions it
    used.
- **FR-006**: A price that was never verified leaves the total unmeasured, and the report says which price is
  missing.
  - Test: `tests/economics/test_cost.py` fails while a total is printed without a verified price.
- **FR-007**: A comparison of two architectures is computed only over the same cohort, with the same snapshot and
  with the same criteria of evaluation, and it is refused otherwise.
  - Test: `tests/economics/test_comparison.py` fails while a comparison over two cohorts is computed.
- **FR-008**: The normalisation of a currency into dollars uses a dated rate, and a rate that is missing refuses the
  normalisation instead of assuming one.
  - Test: `tests/economics/test_cost.py` fails while a dollar amount is printed with no dated rate.
- **FR-009**: The utility consumes the typed labels of the decision that the code produced, and it never recomputes
  a verdict of its own.
  - Test: `tests/economics/test_utility.py` fails while the utility computes a verdict.
- **FR-010**: The expected loss is the sum over the mutually exclusive error classes, and two classes that overlap
  make the summation refused with the overlap named.
  - Test: `tests/economics/test_utility.py` fails while the sum of two overlapping classes is published.
- **FR-011**: A false accept and a false reject are two classes and never one, and they carry their own losses.
  - Test: `tests/economics/test_utility.py` fails while the two classes share one number.
- **FR-012**: A probability that was never calibrated is published as unknown or as a range, and never as a point
  that a reader would read as a measurement.
  - Test: `tests/economics/test_utility.py` fails while an uncalibrated probability is published as a point.
- **FR-013**: A loss that nobody knows leaves the expected loss of that class unknown, and the total is published as
  unknown with the class that is missing named.
  - Test: `tests/economics/test_utility.py` fails while a missing loss is treated as zero.
- **FR-014**: The comparison of the automatic resolution, of the review and of the abstention uses the same mix of
  cases and the same capacities.
  - Test: `tests/economics/test_utility.py` fails while two policies are compared over different mixes.
- **FR-015**: The risk coverage curve is drawn over the cases and with the losses of the same run, and it is empty
  with a reason when the labels carry no probability.
  - Test: `tests/economics/test_utility.py` fails while the curve is drawn over labels with no probability.
- **FR-016**: The module never publishes a return, a saving or a benefit that no measurement produced, and it
  refuses the question with the numbers it can state.
  - Test: `tests/economics/test_utility.py` fails while a return is published.
- **FR-017**: The module never chooses a model and never changes the model of a run. The comparison is over the
  results of the runs that already happened, under ADR-037 and the FR-013 it carries.
  - Test: `tests/economics/test_comparison.py` reads the modules of `ledgerlens/economics/` with `ast` and fails
    while a module imports a model or a registry that calls one.
- **FR-018**: The economics module lives in the domain and never imports the API.
  - Test: `tests/economics/test_cost.py` reads the modules of `ledgerlens/economics/` with `ast` and fails while a
    module imports `ledgerlens.api`.

### Key Entities

- **Cost of a case**: the money of one case, split into the categories of the model, of the compute, of the review and
  of the error assumption.
- **Cost per correctly resolved case**: the total of a cohort divided by the number of the cases that were resolved.
- **Assumption**: a number that the repository cannot measure, such as the minutes of a review, that travels with
  every result it produces.
- **Price**: the price of a model, with the source that publishes it and the day it was last verified.
- **Error class**: a typed label of an outcome, such as a false accept or a false reject, with its own loss.
- **Policy**: one way of treating the cases, such as the automatic resolution, the review or the abstention.
- **Expected loss**: the sum of the probability of each class times the loss of that class.
- **Risk coverage curve**: the risk that remains at each level of coverage.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every amount printed by the economics module is a `Decimal`, and every price carries its source and
  the day it was last verified.
- **SC-002**: The cost per correctly resolved case is the exact division of the total by the number of the resolved
  cases, and a cohort with no resolved case produces no number and a reason.
- **SC-003**: A comparison over two cohorts is refused, and a comparison over the same cohort names the number of
  the cases.
- **SC-004**: A model with no verified price produces no dollar amount, and the report names the price that is
  missing.
- **SC-005**: Every report of the cost names the assumptions it used.
- **SC-006**: The expected loss of a policy separates the false accepts from the false rejects, refuses the sum of
  two overlapping classes and names the overlap.
- **SC-007**: An uncalibrated probability is published as unknown or as a range and never as a point.
- **SC-008**: The module publishes no return, no saving and no benefit that a measurement did not produce.
- **SC-009**: No module of `ledgerlens/economics/` imports the API, and none of them calls a model.

## Assumptions

- The economics module does not exist. The milestone of [specs/005](../005-r4-runtime-latency-and-cost-per-case/spec.md)
  promised it and did not build it. This specification builds it and does not rewrite the promise.
- The cost of a live run is already computed by `ledgerlens/byok/budget.py`, with the two costs, the observed and
  the estimated, and the refusal to print a guessed amount. The economics module reads that computation and does not
  compute it again.
- The oracle of a resolved case is the one the code already produces: the correctness evaluator finds the expected
  facts, the groundedness evaluator finds the claims supported, and the case was not sent to a person. A case that
  was cut by a cap is scored as a case that was cut and not as a wrong answer.
- The probabilities of the error classes are calibrated somewhere else. The module reads them when they exist and
  says that they are unknown when they do not. It never calibrates a probability itself, because a calibration is a
  measurement and this module is an accounting.
- The losses of the classes are hypotheses of the reader. They are assumptions that travel with the result, in the
  same way the minutes and the rate of a review do.
- The comparison is over the results of the runs that already happened. It never calls a model, it never chooses one
  and it never changes the model of a run, under ADR-037 and the FR-013 it carries.
- The module is not a router. A design that picks a model by cost inside a run is a different piece of work, it is
  behind a flag, and it is published only after a paired comparison measures a gain, under ADR-P007.

## Out of scope

- The cost of a live run and the two costs of the run, which belong to
  `ledgerlens/byok/budget.py` and to [ADR-034](../../docs/decisions/ADR-034-the-registry-the-budget-and-the-endpoint.md).
- The latency of a turn, which belongs to
  [specs/005](../005-r4-runtime-latency-and-cost-per-case/spec.md).
- The queue of the review and the capacity of the reviewers, which belong to
  [specs/012](../012-r10-human-review-and-approval/spec.md).
- The paired comparison between two architectures, which belongs to
  [specs/009](../009-r4-paired-evaluation-arena/spec.md). This specification consumes its cohort and its labels and
  does not build it.
- The calibration of the verifier and the pin of the thresholds.
- Any advice on regulation, on staffing or on a business decision. The module computes and it never recommends.

## Design documents

| Document | What it decides for this specification |
|---|---|
| [ADR-034](../../docs/decisions/ADR-034-the-registry-the-budget-and-the-endpoint.md) | The two costs of a run and the price with its provenance, which the economics module reads and never recomputes. |
| [ADR-054](../../docs/decisions/ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md) | The ceiling of the loop, so a case that a cap cut is scored as a case that was cut. |
| [ADR-072](../../docs/decisions/ADR-072-a-currency-the-reference-source-does-not-publish-is-missing-data-and-the-case-goes-to-a-person.md) | A currency that the reference source does not publish is missing data, so the case goes to a person and the reader sees why. |
| [ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md) | The decision belongs to the code, so the utility consumes the labels of the code and computes no verdict of its own. |
| [ADR-077](../../docs/decisions/ADR-077-the-published-bundle-is-verified-against-the-answer-the-run-verified.md) | The published bundle is verified against the answer the run verified, so the cohort and its labels come from a verified artifact. |
| [LL-V3-R9-03](../../docs/design/advanced-specs/R9-03-cost-per-correctly-resolved-case.md) | The design package of the cost per case. |
| [LL-V3-R9-06](../../docs/design/advanced-specs/R9-06-risk-weighted-decision-utility.md) | The design package of the risk weighted utility. |
| [specs/005](../005-r4-runtime-latency-and-cost-per-case/spec.md) | The milestone that promised the economics module and the cost per resolved case. |
| [specs/009](../009-r4-paired-evaluation-arena/spec.md) | The milestone that builds the cohort and the paired comparison this specification consumes. |

## Status

| Part | State in the repository on 2026-11-23 |
|---|---|
| The cost of a live run | Built. `ledgerlens/byok/budget.py` computes the observed and the estimated cost, counts the calls of every model, and refuses to print a guessed amount. |
| The registry of the prices | Built. `ledgerlens/byok/registry.py` carries the price, the source that publishes it and the day it was last verified, and refuses a price that was not verified. |
| The panel that shows the cost | Built. `apps/web/features/evals/CostPanel.tsx` presents the report of the server and computes nothing. |
| The economics module | Not built. `ledgerlens/economics/` does not exist, and the milestone of [specs/005](../005-r4-runtime-latency-and-cost-per-case/spec.md) promised it. |
| The cost of a case over the evaluation | Not built. `data/eval/report_online.md` holds the scores and no cost. |
| The cost per correctly resolved case | Not built. |
| The oracle of a resolved case | Built. `ledgerlens/eval/evaluators.py` scores the correctness and the groundedness, and `ledgerlens/verify/escalation.py` says when a case went to a person. |
| The labels of the decision | Built. The verdict of a claim and the recommended action of a case are computed by the code, under ADR-074. |
| The risk weighted utility | Not built. There is no confusion matrix, no expected loss and no risk coverage curve in the repository. |
| The probabilities of the error classes | Not built and not calibrated. The module will publish them as unknown until a calibration exists. |
| The assumptions of the review | Not built. The minutes and the rate of a review are nowhere in the repository today. |
