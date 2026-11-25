---
description: "Task list for cost per correctly resolved case and risk weighted decision utility"
---

# Tasks: Cost per correctly resolved case and risk weighted decision utility

**Input**: Design documents from `specs/011-r9-cost-per-case-and-decision-utility/`

**Prerequisites**: plan.md (required), spec.md (required), the cost of a live run that already exists
(`ledgerlens/byok/budget.py`), the registry of the prices (`ledgerlens/byok/registry.py`), the labels of the cohort
(`ledgerlens/eval/evaluators.py`, `ledgerlens/verify/escalation.py`) and the decisions
[ADR-034](../../docs/decisions/ADR-034-the-registry-the-budget-and-the-endpoint.md),
[ADR-054](../../docs/decisions/ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md),
[ADR-072](../../docs/decisions/ADR-072-a-currency-the-reference-source-does-not-publish-is-missing-data-and-the-case-goes-to-a-person.md)
and [ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md)

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side `scripts/gate.sh` is green before the commit. A test that must fail before the change names the
file it lives in and what it refuses.

**Organization**: Tasks are grouped by the milestone that delivers them, and the tasks of a milestone touch disjoint
files so that they can be worked on in parallel. The ids of this specification start at T861, above the highest id
used by `specs/001-*` through `specs/006-*`, and they never collide with them. The package
`ledgerlens/economics/` is created by T862, and the queue of the review that lives in the same package belongs to
`specs/012-r10-human-review-and-approval`.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## Milestone A, the assumptions

**Purpose**: the numbers that the repository cannot measure, held in one place and carried by every result.

- [x] T861 Write the test in `tests/economics/test_assumptions.py` that fails while a report of the cost does not
  name the assumptions it used, and that fails while the minutes of a review or the rate of an hour are constants
  of the code and not a field of the assumptions - **DELIVERED**: the test is in `tests/economics/test_assumptions.py`:
  the minutes of a review and the rate of an hour are fields of the assumptions and not constants of the code,
  every assumption names its source and the day it was stated, and the money of an assumption is a `Decimal`.
- [x] T862 Create the package `ledgerlens/economics/` with the module `ledgerlens/economics/assumptions.py` that
  holds the assumptions of an economics run, the minutes of a review, the rate of an hour, the price snapshot and
  their sources, with the docstring of the module saying that an assumption is a number the repository cannot
  measure and that every result that uses one carries it - **DELIVERED**: the package and the module hold the
  assumptions of a run, the minutes of a review, the rate of an hour and the price snapshot with its source and its
  day, and the docstring says that an assumption is a number the repository cannot measure and that every result
  that uses one carries it.

## Milestone B, the cost of a case

**Purpose**: the money of a case, the total of a cohort and the cost per correctly resolved case.

- [x] T863 Write the test in `tests/economics/test_cost.py` that fails while a total is a float, that fails while a
  price carries no provenance, that fails while two categories of the cost count the same money twice, that fails
  while a cohort with no resolved case produces a zero, that fails while a case that went to a person is in the
  denominator, that fails while a total is printed without a verified price, and that fails while a dollar amount
  is printed with no dated rate. The fixture is written by hand in `tests/economics/fixtures/` - **DELIVERED**: the
  test is in `tests/economics/test_cost.py` with the fixtures written by hand in the test itself: a float is
  refused, a price carries its provenance, two categories of the same name count the same money twice and are
  refused, a cohort with no resolved case produces no number and the reason, a case that went to a person is not in
  the denominator and pays the money of its review, and a total with an unknown price prints no amount and names
  the price that is missing.
- [x] T864 Write the module `ledgerlens/economics/cost.py` with the cost of a case, the four non overlapping
  categories, the total of a cohort, the cost per correctly resolved case and the refusal of an unknown price, with
  the docstring of the module saying that every amount is a `Decimal`, that the oracle of a resolved case comes from
  the code and that a case that went to a person is not a resolved case - **DELIVERED**: the module holds the cost of
  a case, the four non overlapping categories, the total of a cohort, the cost per correctly resolved case and the
  refusal of an unknown price, and the docstring says that every amount is a `Decimal`, that the oracle of a
  resolved case comes from the code and that a case that went to a person is not a resolved case.
- [x] T865 [P] Write the test in `tests/economics/test_cost.py` that reads the modules of `ledgerlens/economics/`
  with `ast` and fails while a module imports `ledgerlens.api`, and fails while a module that computes money holds
  a binary float literal - **DELIVERED**: the test reads every module of `ledgerlens/economics/` with `ast` and
  refuses an import of `ledgerlens.api`, of `ledgerlens.offline` or of `ledgerlens.config`, and refuses a binary
  float literal in any module of the package.
- [x] T866 [P] Write the test in `tests/economics/test_comparison.py` that fails while a comparison over two
  cohorts is computed, and that reads the modules of `ledgerlens/economics/` with `ast` and fails while a module
  imports a model or a registry that calls one, under ADR-037 and the FR-013 it carries - **DELIVERED**: the test is
  in `tests/economics/test_comparison.py`: a comparison over two cohorts is refused and the refusal is checked
  against the digest of the cohort and not against its name, and the second test reads the modules of
  `ledgerlens/economics/` with `ast` and refuses an import of a model, of a registry that calls one or of the API.
- [x] T867 [P] Write the comparison of two architectures in `ledgerlens/economics/cost.py`, over the same cohort,
  with the same snapshot and with the same criteria of evaluation, with the docstring saying that the comparison
  reads the results of the runs that already happened and that it never chooses a model - **DELIVERED**: the
  comparison is `compare_cohorts`, over the same cohort, with the denominator of each arm published apart, and the
  docstring says that the comparison reads the results of the runs that already happened and that it never chooses
  a model.

## Milestone C, the risk weighted utility

**Purpose**: the expected loss of a policy, with the classes kept apart and the unknowns named.

- [x] T868 Write the test in `tests/economics/test_utility.py` that fails while the utility computes a verdict of
  its own, that fails while the sum of two overlapping classes is published, that fails while the false accept and
  the false reject share one number, that fails while an uncalibrated probability is published as a point, that
  fails while a missing loss is treated as zero, that fails while two policies are compared over different mixes
  of cases, that fails while the curve is drawn over labels with no probability, and that fails while a return is
  published. The fixture holds four classes with known counts and known losses, so that the expected loss is
  computed by hand and written in the test - **DELIVERED**: the test is in `tests/economics/test_utility.py` with a
  fixture of four classes with known counts and known losses and the expected loss computed by hand in the test:
  the sum of two overlapping classes is refused before it is published, the false accept and the false reject are
  published apart, an uncalibrated probability is unknown and not a point, a missing loss is unknown and not a
  zero, the three policies are compared over the same mix of cases, the curve is drawn over the labels that carry
  a probability and names the ones it left out, and no return is published.
- [x] T869 Write the module `ledgerlens/economics/utility.py` with the confusion of the typed labels, the
  expected loss of a policy, the comparison of the automatic resolution, of the review and of the abstention, the
  risk coverage curve and the refusal to publish a return, with the docstring of the module saying that a
  probability that was never calibrated is published as unknown and that a loss that nobody knows leaves the total
  unknown - **DELIVERED**: the module holds the confusion of the typed labels, the expected loss of a policy, the
  comparison of the automatic resolution, of the review and of the abstention, the risk coverage curve and the
  refusal to publish a return, and the docstring says that a probability that was never calibrated is published as
  unknown and that a loss that nobody knows leaves the total unknown.
- [x] T870 [P] Write the test in `tests/economics/test_utility.py` that fails while the expected loss of a policy
  is published without the assumptions that produced it, and that fails while the result does not name the source
  of its probabilities - **DELIVERED**: the test is in `tests/economics/test_utility.py`: the expected loss carries
  the assumptions that produced it, and the result names the source of the probability of each class.

## Milestone D, the published result and the record of the milestone

**Purpose**: the numbers published as artifacts, and the decisions written down.

- [x] T871 Write the test in `tests/economics/test_published_economics.py` that fails while the export of a result
  of the economics is not byte identical when it runs twice, and that fails while the artifact carries no hash and
  no digest of the cohort it was computed over - **DELIVERED**: the test is in
  `tests/economics/test_published_economics.py`: the export of a result is byte identical when it runs twice, the
  artifact carries the hash of its content and the digest of the cohort it was computed over, and the export copies
  the content and never changes it.
- [x] T872 Write the export in `ledgerlens/economics/publish.py` and the script
  `scripts/export_economics.py`, with the docstring saying that the export copies, hashes and labels and never
  changes the recorded content, and that it refuses a cohort whose digest moved - **DELIVERED**: the export is in
  `ledgerlens/economics/publish.py` and the script is `scripts/export_economics.py`, and the docstring says that the
  export copies, hashes and labels and never changes the recorded content, and that it refuses a cohort whose digest
  moved. The script publishes the economics of the two arms of the published measurement of the comparison of the
  routes, into `data/eval/`.
- [x] T873 Write the record of the milestone in `docs/decisions/` with the next number after ADR-077, which states
  that the economics module computes and never calls a model, that an unknown price and an uncalibrated probability
  are published as unknown and never as a zero, that the oracle of a resolved case comes from the code, that the
  module publishes no return, and that a router that picks a model by cost stays behind a flag until a paired
  comparison measures a gain under ADR-P007, and link it from `docs/decisions/README.md` with
  `uv run python scripts/build_docs_index.py` - **DELIVERED**: the record of the milestone is
  `docs/decisions/ADR-086-the-economics-module-computes-and-never-calls-a-model-and-an-unknown-stays-unknown.md`, and
  it states the five things the task names. The number is ADR-086 and not the one after ADR-077, because the numbers
  between them are taken by the decisions that came after it.
