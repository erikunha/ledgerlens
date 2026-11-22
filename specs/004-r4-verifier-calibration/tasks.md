---
description: "Task list for the verifier calibration and the integrity of the benchmarks"
---

# Tasks: Verifier calibration and benchmark integrity

**Input**: Design documents from `specs/004-r4-verifier-calibration/`

**Prerequisites**: plan.md (required), spec.md (required), the decision of the first milestone
(`docs/decisions/ADR-052-the-manifest-of-the-eval-datasets.md`)

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side and the gate of the frontend are green before the commit.

**Organization**: Tasks are grouped by the milestone that delivers them, and the tasks of a milestone touch
disjoint files so that they can be worked on in parallel.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/` at repository root
- **Web app**: `apps/web/`
- Paths shown below assume single project

## Milestone 19, the manifest of the datasets and the check in the gate

**Purpose**: every dataset of `data/eval/` is pinned, and the gate refuses when one moves.

- [x] T091 [P] Create `ledgerlens/eval/manifest.py` with the frozen record `EvalDatasetManifest`, the roles
  `SPLIT_ROLES`, the exception `ManifestError` and the functions `fingerprint_dataset`, `load_manifests`,
  `verify_manifests`, `render_manifests` and `update_fingerprints` - **DELIVERED**: the module exists with the
  ten fields of the record, a complete `__all__`, and a record that is a nonblank line that parses as a JSON
  object. A line that does not parse raises `ManifestError` naming the file and the line, and it is not a record.
- [x] T092 [P] Create `data/eval/datasets.json` with one entry per dataset of `data/eval/`, with the sha256, the
  record count, the source, the labeling version, the split role, the scenario seed, the contamination policy and
  the honest caveat of each one - **DELIVERED**: the five datasets are declared, the file is the canonical text
  written by `render_manifests`, and the sha256 and the count of every entry were computed from the disk with the
  module itself. The roles are all `tuning`, and the evidence for each one is in the notes of the entry.
- [x] T093 [P] Write `tests/eval/test_dataset_manifest.py` with the fingerprint, the malformed manifest, the
  undeclared file, the order of the problems, the canonical text, the update and the five real entries - **DELIVERED**:
  the file has the tests, they were written first and were seen failing without the module, and every fixture uses
  `tmp_path`.
- [x] T094 [P] Create `scripts/check_eval_datasets.py` with the mode that verifies and the mode that writes, and
  wire it into `scripts/gate.sh` between the tests and the export check - **DELIVERED**: the script asks the module
  and prints what the module says, the manifest path follows the root, a manifest outside the root is refused, and
  the write never changes a role and says out loud when it could not compare the roles with the commit.
- [x] T095 [P] Write `tests/eval/test_check_eval_datasets.py` with the exit code and the message of the failing
  case and of the passing case, the refusal that re-roles and the refusal of a manifest outside the root -
  **DELIVERED**: the file has the tests, they were written first and were seen failing without the script, and the
  case of the refusal that re-roles builds a temporary git repository and proves the refusal.

- [x] T096 [P] Write `tests/eval/test_dataset_documentation.py` that reads the README, in both languages, and
  `docs/verification_sets.md`, and that fails when a public number stops naming the dataset it comes from, the
  role of that dataset and the restriction that applies to it - **DELIVERED**: the file reads the two READMEs and
  the canonical document, and it holds the numbers to the dataset, the role and the decision that says what a
  role means. The lens of the documentation of the milestone found that no test read those documents, and this
  is that test.

## Milestone 20, the held out set and the pin of the calibration

**Purpose**: a set that no decision was taken against, and a calibration that says what it was measured over.

- [ ] T097 Write the cases of the held out set in `data/eval/verification_heldout.jsonl`, with different templates,
  different text and different source structures from the sets of the tuning, including the negative controls: a
  claim with no evidence, a claim whose evidence contradicts itself and a benign claim the evidence does not support
- [ ] T098 Read the labels of the held out cases by hand, one label per case, with the rule of ADR-007, and record
  the labeling version in the manifest - the agent that writes a case does not label it
- [ ] T099 Declare the held out set in `data/eval/datasets.json` with the role `held_out`, with the sha256 and the
  count of the file, and commit the manifest BEFORE any threshold is chosen against it
- [ ] T100 Add to `ledgerlens/eval/manifest.py` the guard that refuses to tune against a dataset whose role is not
  `tuning`, with a readable reason and a non zero exit code, and the test that proves it
- [ ] T101 Pin the calibration of `ledgerlens/verify/thresholds.json` to the sha256 of the manifest it was measured
  over, to the version of the NLI model and to the sweep log, and add the test that the pin and the manifest agree
- [ ] T102 Write `scripts/sweep_nli_thresholds.py` that recomputes the sweep of ADR-007 over the sets of the role
  `tuning`, refuses to run when the manifest of the disk is not the one the calibration names, and refuses to read
  a held out dataset
- [ ] T103 Write the ADR of the milestone, which decides how the cases are written, who labels them and what a
  tuning script is allowed to read

## Milestone 21, the reports that show the cases that failed

**Purpose**: the aggregate sits next to the per case list, and the two never mix.

- [ ] T104 Recompute the calibration over the sets of the role `tuning` and preserve the reports of the past under
  versioned ids, and mark the corpus of the old report as unrecoverable when it cannot be recovered
- [ ] T105 Write the per case report of the verifier: the claim, the evidence, the expected verdict, the verdict
  that came out, the false supported, the false contradicted and the case without a verdict
- [ ] T106 Write the per case report of the evaluation of the agent, and keep the correctness of the agent apart
  from the accuracy of the verifier in every sentence that publishes one of them
- [ ] T107 Report a change of the prompt parser, with the model output unchanged, as a change of the extraction, and
  never as a rewrite of the reports of the past
- [ ] T108 Add the `verification_status = unavailable` rule, so that a missing NLI model is not a pass

## Milestone 22, the Eval Lab of the interface

**Purpose**: the reader of the interface sees the dataset, the restriction and the cases that failed.

- [ ] T109 Build the page of the Eval Lab with the numbers of the verification and of the evaluation, each one with
  the dataset it comes from and the restriction that applies to it
- [ ] T110 Build the list of the cases that failed, with the claim and the evidence of each one, and the drill into
  one case
- [ ] T111 Show the confusion matrix of the verifier with its denominator, and the note that a missing model is not
  a pass
- [ ] T112 Write the end to end cases of the Eval Lab, and add the structural baseline of the pages of the milestone
