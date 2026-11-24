---
description: "Task list for paired evaluation arena"
---

# Tasks: Paired evaluation arena

**Input**: Design documents from `specs/009-r4-paired-evaluation-arena/`

**Prerequisites**: plan.md (required), spec.md (required), the evaluation that already exists
(`ledgerlens/eval/run.py`, `ledgerlens/eval/evaluators.py`, `ledgerlens/eval/manifest.py`,
`ledgerlens/eval/heldout.py`), the reports `data/eval/report_offline.md` and `data/eval/report_online.md`, and the
decisions [ADR-008](../../docs/decisions/ADR-008-evaluation-design.md),
[ADR-052](../../docs/decisions/ADR-052-the-manifest-of-the-eval-datasets.md),
[ADR-062](../../docs/decisions/ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md),
[ADR-069](../../docs/decisions/ADR-069-the-reservation-follows-the-content-of-the-case-and-the-key-of-the-set-is-not-published.md)
and [ADR-074](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md)

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side `scripts/gate.sh` is green before the commit. A test that must fail before the change names the
file it lives in and what it refuses.

**Organization**: Tasks are grouped by the milestone that delivers them, and the tasks of a milestone touch disjoint
files so that they can be worked on in parallel. The ids of this specification start at T781, above the highest id
used by `specs/001-*` through `specs/006-*`, and they never collide with them.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## Milestone A, the manifest of an experiment

**Purpose**: one pinned object that says what a measurement was made of.

- [ ] T781 Write the test in `tests/eval/test_experiment_manifest.py` that fails while a field of the manifest is
  missing, that fails while two manifests that differ in the judge have the same identifier, and that fails while a
  published experiment under `data/eval/experiments/` is rewritten
- [ ] T782 Write the module `ledgerlens/eval/experiment.py` with the manifest of an experiment, the hash that is
  its identifier, the reader of a published manifest and the writer that refuses to overwrite one, with the
  docstring of the module saying that the manifest pins every input of a measurement and that the identifier of the
  experiment is the hash of the manifest
- [ ] T783 [P] Write the test in `tests/eval/test_experiment_manifest.py` that fails while a new experiment
  rewrites `data/eval/report_online.md`, and that expects the historical reports of the variants A, B and C to keep
  the 0.73 of the trajectory with equivalent tools against the goal of 0.80
- [ ] T784 Decide the method that computes the uncertainty of a paired comparison: a paired bootstrap or another
  method that is declared. Write the choice down in the record of the milestone of T792, with the reason and the
  number of the repetitions it needs

## Milestone B, the paired comparison

**Purpose**: the difference of two variants over the same cases, case by case.

- [ ] T785 Write the test in `tests/eval/test_paired.py` that fails while a comparison over two cohorts is
  computed, that fails while a missing run of one case lowers the mean of the variant that ran it, that fails while a
  result hides an excluded case, that fails while a result carries an interval and names no method, and that fails
  while the target of 0.80 is reported as met over a score of 0.73. The fixture is written by hand in
  `tests/eval/fixtures/` and holds a case that both variants ran, a case that only one ran and a run that failed
- [ ] T786 Write the module `ledgerlens/eval/paired.py` with the comparison of two variants over a cohort, the
  count of the paired cases, the count and the reason of the excluded cases, the difference case by case, the
  interval by the declared method and the check of the goal, with the docstring of the module saying that the
  comparison reads the results of the runs that already happened and never calls a model
- [ ] T787 [P] Write the test in `tests/eval/test_paired.py` that fails while a stratum below the declared minimum
  carries a mean and no mark, that fails while a stratum does not name its count, and that fails while the totals of
  the strata do not add up to the cohort
- [ ] T788 [P] Write the stratification in `ledgerlens/eval/paired.py` by intent and by complexity, with the
  minimum number of cases of a stratum declared in the result and the docstring saying why a stratum that is too
  small carries no mean

## Milestone C, the gallery of the failures

**Purpose**: the cases a variant lost and the runs that failed, published without the key of the set.

- [ ] T789 Write the test in `tests/eval/test_failure_gallery.py` that fails while the gallery holds a label of the
  held out set, that fails while a run that failed is published as a score of zero, and that fails while a lost case
  is published without the expected facts and without the evidence its answer cited
- [ ] T790 Write the module `ledgerlens/eval/failures.py` with the gallery of an experiment, with the docstring of
  the module saying that the gallery holds what a variant lost and that it never holds the key of the held out set
  under ADR-069
- [ ] T791 Write the script `scripts/run_paired_experiment.py` that reads a manifest, computes the comparison and
  writes the result, the gallery and the manifest of the experiment under `data/eval/experiments/`, with the
  docstring saying that the script refuses to overwrite an experiment that was published
- [ ] T792 Write the record of the milestone in `docs/decisions/` with the next number after ADR-077, which states
  that the identifier of an experiment is the hash of its manifest, that a published experiment is never rewritten,
  that a comparison is refused over two cohorts, that the method of the uncertainty is declared, that the
  comparison never calls a model under ADR-037, and that the multi agent variant D of ADR-P007 stays behind a flag
  until a comparison of this kind measures a gain, and link it from `docs/decisions/README.md` with
  `uv run python scripts/build_docs_index.py`

## Milestone D, the reproduction of a published experiment

**Purpose**: a third party runs one command and gets the same bytes.

- [ ] T793 Write the test in `tests/eval/test_experiment_rerun.py`, marked with the marker of the slow tests, that
  fails while the rerun of a published experiment differs from the published result, and that expects the manifest to
  carry the commit, the seed, the digest of the cohort and the command that produces the result
- [ ] T794 [P] Write the test in `tests/eval/test_experiment_rerun.py` that fails while the published result
  carries no hash of its own and no command that reproduces it
