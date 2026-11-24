# Feature Specification: Paired evaluation arena

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: [ADR-008](../../docs/decisions/ADR-008-evaluation-design.md),
[ADR-052](../../docs/decisions/ADR-052-the-manifest-of-the-eval-datasets.md),
[ADR-053](../../docs/decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md),
[ADR-059](../../docs/decisions/ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md),
[ADR-062](../../docs/decisions/ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md),
[ADR-067](../../docs/decisions/ADR-067-the-measurement-of-the-held-out-set-is-published-without-its-answer-key.md),
[ADR-069](../../docs/decisions/ADR-069-the-reservation-follows-the-content-of-the-case-and-the-key-of-the-set-is-not-published.md),
[ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md) and the
design package [LL-V3-R4-04, paired evaluation arena](../../docs/v3/advanced-specs/R4-04-paired-evaluation-arena.md).
The milestones of the same area are [specs/004](../004-r4-verifier-calibration/spec.md) and
[specs/005](../005-r4-runtime-latency-and-cost-per-case/spec.md).

The package was written for a greenfield plan. The repository has since built the three variants, the evaluators,
the manifest of the datasets, the held out set and the reports of the offline and the online runs. This specification
covers the part of the package that is still missing: an immutable manifest of an experiment, a paired comparison
between two variants over the same cohort, the stratification of the comparison, the gallery of the failures and the
refusal to publish a result whose comparator is missing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The reader compares two variants over the same cases (Priority: P1)

A reader asks whether the full agent is better than the chain with no tools. The answer is a paired comparison: the
same cases, the same snapshot, the same criteria of evaluation, one number per case, and the difference of the
numbers case by case. The comparison says how many cases it covers and how the uncertainty was computed.

**Why this priority**: a comparison over different cases, or over a different judge, or over a different number of
repetitions, is not a comparison. Without the pairing the reader cannot tell a gain from a change of the set.

**Independent test**: run the comparison of two variants over the same cohort and read the result. The result names
the cohort and its digest, the two variants, the number of the cases that were paired, the difference of the mean of
the metric case by case, the method that computed the uncertainty, and the goal it was compared against.

### User Story 2 - The reader sees a target that was not met (Priority: P1)

The reader opens the comparison of the trajectory of the full agent and reads that the score with equivalent tools
is 0.73 against a goal of 0.80, and that the goal was not met. The number is not rounded up, not hidden behind a
pass mark and not dropped from the report.

**Why this priority**: the report of the repository already says that the 0.73 does not meet the 0.80 minimum. A
surface that showed the goal as met would contradict the number that the report publishes, and a reader who trusts
the surface would be misled.

**Independent test**: read the comparison of the trajectory with equivalent tools and assert that the target is
reported as failed, that the number 0.73 and the goal 0.80 both appear, and that no field of the result says that
the target was met.

### User Story 3 - A case that one variant did not run is marked missing (Priority: P1)

One variant failed on one case. The comparison excludes that case from the pair and says so, with the count of the
cases that were paired and the count that were excluded. It never counts the missing case as a zero and never as a
failure of the variant that ran it.

**Why this priority**: a zero in the place of a missing run turns an infrastructure failure into a quality signal,
and it drags the mean of the comparison down without saying anything.

**Independent test**: remove the run of one case for one variant and read the comparison. The result names the
number of the paired cases, the number of the excluded cases, the reason of the exclusion, and the mean of the
variant that ran the case carries no contribution from the case that is missing.

### User Story 4 - The judge that produced a number cannot change under it (Priority: P1)

The reader changes the version of the evaluator and runs the comparison again. The experiment id is different, the
output is different, and the number that was published before is still where it was, with the judge that produced
it. A leaderboard that was shown with a judge cannot be silently re-scored under another.

**Why this priority**: the number of a leaderboard is meaningless without the judge that produced it, and a judge
that changes under a published number makes every comparison before it wrong.

**Independent test**: compute the id of an experiment with two judges and assert that the ids differ, that the
manifest of each one names its judge, and that the published result of the first judge is unchanged after the
second one was computed.

### User Story 5 - The reader opens the gallery of the failures (Priority: P2)

The reader wants to know where the variant lost. The gallery holds the cases that a variant lost, with the answer
of the variant, the expected facts and the evidence the answer cited, and it holds the failures of the run itself,
labelled as failures and not as scores of zero.

**Why this priority**: a mean with no case behind it cannot be acted on, and the repository already refuses to
publish a catalog that holds only the cases the agent resolves.

**Independent test**: build the gallery over a cohort with at least one case a variant lost and at least one failed
run, and assert that both appear, that the failed run is labelled as a failure, and that the answer of every lost
case carries its expected facts and its evidence.

### User Story 6 - The reader sees the comparison split by the kind of the case (Priority: P2)

The reader asks whether the gain is in the simple cases or in the hard ones. The comparison is stratified by intent
and by complexity, and every stratum says how many cases it holds. A stratum with too few cases says so and is not
given a number that would read as a measurement.

**Why this priority**: a mean over a mixed cohort hides the case where the system fails, and a stratum of three
cases read as a number is a number nobody can use.

**Independent test**: stratify the comparison over a cohort with cases of two intents and two complexities, and
assert that every stratum names its count, that a stratum below the declared minimum is marked as too small and
carries no mean, and that the totals of the strata add up to the cohort.

### User Story 7 - The reader reruns the comparison with one command (Priority: P2)

The reader wants to check a published comparison. The manifest of the experiment carries the command that produces
it, the digest of the dataset, the seed, the commit of the code and the identifier of the judge. Running the command
on the same commit produces the same result, byte for byte.

**Why this priority**: a published number that nobody can reproduce is an assertion, and the repository publishes
only what a third party can check with a hash.

**Independent test**: read the manifest of a published experiment, run the command it carries and compare the
result with the published one. The two are byte identical, and the manifest carries the commit, the seed and the
digest of the dataset.

### Edge Cases

- A comparator that was never run: the comparison publishes no result at all and says which variant is missing.
- A cohort with one case: the comparison publishes the case and no mean, because a mean over one case is the case.
- A metric with no scale, such as the number of the calls of a tool: the comparison reports the difference and no
  percentage, because a percentage of a count that starts at zero is not a number.
- A provider that refused the run: the run is labelled failed, its cases are excluded from the pair and the count
  of the exclusions says why.
- A dataset that moved since the experiment: the manifest holds the digest of the cohort it used, and a comparison
  over a dataset with another digest is refused.
- The held out set: the answer key of the set is never published by the gallery, under ADR-069.
- A judge that is not reproducible: the experiment is refused, because a number that a second run cannot produce is
  not a measurement.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: An experiment is described by a manifest that pins the cohort and its digest, the role of the cohort
  in the manifest of the datasets, the commit of the code, the seed, the model and its price snapshot, the judge and
  its version, the number of the repetitions, the identifiers of the runs of each variant and the goal of each
  metric.
  - Test: `tests/eval/test_experiment_manifest.py` fails while a field of the manifest is missing.
- **FR-002**: The identifier of an experiment is a hash of its manifest, so two experiments that differ in any
  pinned field have different identifiers.
  - Test: `tests/eval/test_experiment_manifest.py` fails while two manifests that differ in the judge have the
  same identifier.
- **FR-003**: A published experiment is immutable, and a new experiment with a different manifest never overwrites
  one that was published.
  - Test: `tests/eval/test_experiment_manifest.py` fails while a published experiment is rewritten.
- **FR-004**: A comparison is only computed between two variants that ran the same cohort, with the same snapshot
  and with the same criteria of evaluation, and it is refused otherwise.
  - Test: `tests/eval/test_paired.py` fails while a comparison over two cohorts is computed.
- **FR-005**: The result of a comparison names the number of the paired cases, the number of the excluded cases and
  the reason of every exclusion.
  - Test: `tests/eval/test_paired.py` fails while a result hides an excluded case.
- **FR-006**: A case that one variant did not run is excluded and is never counted as a zero.
  - Test: `tests/eval/test_paired.py` fails while a missing run lowers the mean of the variant that ran the case.
- **FR-007**: The method that computed the uncertainty is declared in the result, and the result carries no
  interval that was not computed by that method.
  - Test: `tests/eval/test_paired.py` fails while the result carries an interval and names no method.
- **FR-008**: A target that was not met is reported as a target that was not met, and the goal and the number both
  appear in the result.
  - Test: `tests/eval/test_paired.py` fails while the target of 0.80 is reported as met over a score of 0.73.
- **FR-009**: The comparison is stratified by intent and by complexity, every stratum names its count, and a
  stratum below the declared minimum is marked as too small and carries no mean.
  - Test: `tests/eval/test_paired.py` fails while a stratum of three cases carries a mean and no mark.
- **FR-010**: The gallery holds the cases a variant lost and the runs that failed, and it never holds the answer
  key of the held out set.
  - Test: `tests/eval/test_failure_gallery.py` fails while the gallery holds a label of the held out set.
- **FR-011**: The manifest carries the command that reproduces the experiment, and running it on the same commit
  produces the same bytes.
  - Test: `tests/eval/test_experiment_rerun.py` fails while the rerun differs from the published result.
- **FR-012**: The historical reports of the variants A, B and C are preserved as they are, with the known shortfall
  of the trajectory with equivalent tools, and they are never rewritten by a new experiment.
  - Test: `tests/eval/test_experiment_manifest.py` fails while a new experiment rewrites
    `data/eval/report_online.md`.
- **FR-013**: A comparison never changes the model of a run. The manifest names one model per variant and the
  comparison reads the results of the runs that already happened.
  - Test: `tests/eval/test_paired.py` fails while the comparison calls a model.

### Key Entities

- **Experiment**: one run of one cohort with one judge, described by a manifest that pins every input of it.
- **Experiment manifest**: the pinned description of an experiment, and the hash that is its identifier.
- **Variant**: one of the architectures compared, with the identifier of the runs that produced its results.
- **Paired case**: a case that both variants ran, with the metric of each one.
- **Stratum**: a group of the cohort by intent or by complexity, with its count.
- **Gallery**: the set of the cases a variant lost and the runs that failed.
- **Goal**: the threshold a metric is compared against, with the name of the metric it belongs to.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The identifier of an experiment changes when the judge, the cohort, the seed, the model or the number
  of the repetitions changes, and it does not change otherwise.
- **SC-002**: A published experiment is never rewritten, and the historical reports of the variants A, B and C keep
  the 0.73 of the trajectory with equivalent tools.
- **SC-003**: A comparison over two cohorts is refused, and a comparison over two variants of the same cohort
  names the number of the paired cases.
- **SC-004**: A missing run of one case is excluded and named, and it never enters the mean of the variant that ran
  it.
- **SC-005**: The target of 0.80 over a score of 0.73 is reported as a target that was not met, and the test that
  says so fails while it is reported as met.
- **SC-006**: Every stratum names its count, and a stratum below the minimum carries no mean.
- **SC-007**: The gallery holds the failed runs, labels them as failures and holds no label of the held out set.
- **SC-008**: The rerun of a published experiment on the same commit produces the same bytes.

## Assumptions

- The three variants, the evaluators and the reports exist. The package mentions a report at
  `data/eval/report_online.md`, and the repository has it with the numbers of the three runs per case and per
  variant.
- The comparison is computed over the results of runs that already happened. It never calls a model and never
  decides to run one, because a run that decides which model to use inside a visitor run is forbidden by ADR-037
  and by the FR-013 it carries.
- The uncertainty of the comparison is computed by a method that the result names. The package offers a paired
  bootstrap or an explicitly declared method, and the first task of the milestone chooses one and writes the
  choice down.
- The historical reports of the variants A, B and C are preserved with their known shortfall. The package says so
  and the repository says so, and nothing of this milestone rewrites them.
- The gallery never holds the answer key of the held out set, under ADR-069.
- The number of the repetitions and the model of the report of today are the ones the manifest pins. The manifest
  does not claim that they are the best ones.

## Out of scope

- The calibration of the verifier and the pin of the thresholds, which belong to
  [specs/004](../004-r4-verifier-calibration/spec.md).
- The latency and the cost of a turn, which belong to
  [specs/005](../005-r4-runtime-latency-and-cost-per-case/spec.md), and the cost per correctly resolved case, which
  belongs to [specs/011](../011-r9-cost-per-case-and-decision-utility/spec.md).
- The publication of the held out set and of its key.
- The interface of the arena. The first milestone publishes the result as an artifact and reads it in the report;
  a page that compares two variants side by side is a later milestone.
- The multi agent variant D of ADR-P007. It stays behind a flag and out of the runtime, and it is published only
  if a paired comparison of this specification measures a gain that outweighs the extra cost, the extra latency and
  the extra risk.

## Design documents

| Document | What it decides for this specification |
|---|---|
| [ADR-008](../../docs/decisions/ADR-008-evaluation-design.md) | The evaluation design of the three variants and of the report, which the arena compares. |
| [ADR-052](../../docs/decisions/ADR-052-the-manifest-of-the-eval-datasets.md) | Every dataset carries a digest, a count and a role, so a number says what it was measured over. |
| [ADR-053](../../docs/decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md) | The held out set and the way it was labelled. |
| [ADR-059](../../docs/decisions/ADR-059-the-held-out-set-is-read-by-two-blind-machines-and-adjudicated.md) | The reading of the held out set by two blind machines, so the gallery cannot leak the key. |
| [ADR-062](../../docs/decisions/ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md) | The role `held_out` exists, so a number over the held out set is not a number over the tuning set. |
| [ADR-067](../../docs/decisions/ADR-067-the-measurement-of-the-held-out-set-is-published-without-its-answer-key.md) | The measurement of the held out set is published without its answer key. |
| [ADR-069](../../docs/decisions/ADR-069-the-reservation-follows-the-content-of-the-case-and-the-key-of-the-set-is-not-published.md) | The key of the held out set is not published. |
| [ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md) | The decision of a case belongs to the code, so the gallery shows the code and not the prose of a model. |
| [LL-V3-R4-04](../../docs/v3/advanced-specs/R4-04-paired-evaluation-arena.md) | The design package this specification ports. |
| [specs/004](../004-r4-verifier-calibration/spec.md) | The calibration of the verifier and the thresholds of the metrics. |
| [specs/005](../005-r4-runtime-latency-and-cost-per-case/spec.md) | The latency and the cost of a turn, measured with its hardware and its denominator. |

## Status

| Part | State in the repository on 2026-11-23 |
|---|---|
| The three variants and the runner | Built. `ledgerlens/eval/run.py` runs A, B and C, offline and online, with three repetitions per case and per variant. |
| The evaluators | Built. `ledgerlens/eval/evaluators.py` scores correctness, groundedness, the trajectory in four modes and the equivalent modes, the explanation and the human review. |
| The manifest of the datasets | Built. `ledgerlens/eval/manifest.py` pins the digest, the count and the role of every dataset, and `scripts/check_eval_datasets.py` refuses a dataset that moved. |
| The held out set and its blind reading | Built. `ledgerlens/eval/heldout.py` and `heldout_reader.py`, with the reservation rules of ADR-065 and ADR-069. |
| The reports | Built. `data/eval/report_offline.md` and `data/eval/report_online.md`, with the 0.73 of the trajectory with equivalent tools against the goal of 0.80, stated as a goal that was not met. |
| An immutable manifest of an experiment | Not built. The report names the model, the temperature, the set and the number of the runs, and it does not carry the seed, the commit, the judge version, the identifiers of the runs and the goal of each metric in one pinned object. |
| A paired comparison | Not built. The report holds the mean of each variant over the three runs, and it does not hold the difference case by case. |
| The stratification by intent and by complexity | Not built. |
| The gallery of the failures | Not built. The report names the failures of the infrastructure in prose, and it does not publish the cases a variant lost. |
| The command that reproduces an experiment | Not built. `ledgerlens/eval/run.py` can be run, and the report does not carry the command, the seed and the commit that produce it. |
| The interface of the arena | Not built. |
