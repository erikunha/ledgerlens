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

- [x] T097 Write the cases of the held out set in `data/eval/verification_heldout.jsonl`, with different templates,
  different text and different source structures from the sets of the tuning, including the negative controls: a
  claim with no evidence, a claim whose evidence contradicts itself and a benign claim the evidence does not support
  - **DELIVERED**: the generator `ledgerlens/eval/heldout.py` writes the blind file `data/eval/heldout/cases.jsonl`
  with the forty eight cases over the synthetic ledger of the seed 7301, in six templates of eight instances each,
  and the recipes live in `data/eval/heldout/recipes.jsonl`, a file the readers were forbidden to open and that the
  tree does not publish (ADR-062). The three negative
  controls are there: the case with no evidence, the case whose evidence contradicts itself and the benign claim the
  evidence does not support. The file the manifest will declare is built by the reading of T098, so that no file of
  this repository carries a label that a machine wrote
- [x] T098 Read the labels of the held out cases in two independent blind machine readings with an adjudication of the
  divergences, with the rule of ADR-007, and record the labeling version in the manifest - the agent that writes a case
  does not label it, and the agent that reads it does not see the recipe - **DELIVERED**: the instrument is
  `scripts/label_heldout.py`, it shows one case at a time, it saves every label as it is given, it compares two readings
  with the mode `compare` without ever opening the recipes, and it compares the labels with the recipes afterwards. The
  readings were machine readings, because the owner of the repository does not read the cases by hand, and ADR-059 decides
  that two readings and an adjudication stand where one person stood. The first reading answered 19 supported, 23
  contradicted and 6 without enough evidence, the second answered 20, 24 and 4, and the adjudication decided the two cases
  where they diverged, both of them by the rule that evidence which contradicts itself says nothing, so the label of the
  set is 19, 23 and 6. The push of this tree was held until the reading was done, so the public repository never showed
  the answer key before the cases were read without it
- [x] T099 Declare the held out set in `data/eval/datasets.json` with the role `held_out`, with the sha256 and the
  count of the file, and commit the manifest BEFORE any threshold is chosen against it - **DELIVERED**: the manifest
  declares two datasets with the role `held_out`, the labelled set `data/eval/verification_heldout.jsonl` and the answer
  key of the generator `data/eval/heldout/recipes.jsonl`, so the guard that refuses a tuning script covers the key as
  well as the set. No threshold was chosen against either of them: the pin of the calibration was rewritten after the
  manifest moved and names the same five tuning datasets as before
- [x] T100 Add to `ledgerlens/eval/manifest.py` the guard that refuses to tune against a dataset whose role is not
  `tuning`, with a readable reason and a non zero exit code, and the test that proves it - **DELIVERED**: the guard
  is `may_be_tuned_against` and `require_tuning_dataset` in `ledgerlens/eval/manifest.py`, with the exception
  `TuningRefusal`, and the test is `tests/eval/test_tuning_guard.py`
- [x] T101 Pin the calibration of `ledgerlens/verify/thresholds.json` to the sha256 of the manifest it was measured
  over, to the version of the NLI model and to the sweep log, and add the test that the pin and the manifest agree
  - **DELIVERED**: the pin is in `ledgerlens/verify/thresholds.json` with the keys `tuning_manifest_sha256`,
  `tuning_datasets`, `nli_model` and `sweep_log`, the script that writes it is `scripts/pin_calibration.py` and the
  test is `tests/verify/test_calibration_pin.py`
- [x] T102 Write `scripts/sweep_nli_thresholds.py` that recomputes the sweep of ADR-007 over the sets of the role
  `tuning`, refuses to run when the manifest of the disk is not the one the calibration names, and refuses to read
  a held out dataset - **DELIVERED**: the script exists with the three refusals, the shared logic is
  `ledgerlens/verify/sweep.py` and the test is `tests/verify/test_verification_live.py`
- [x] T103 Write the ADR of the milestone, which decides how the cases are written, who labels them and what a
  tuning script is allowed to read - **DELIVERED**: `docs/decisions/ADR-053-the-held-out-set-and-the-blind-labelling.md`
- [ ] T113 Build the held out set of the RETRIEVAL, with the same three properties this milestone gave to the held out
  set of the verification: the questions written by a generator, the relevance labels read by one person blind to the
  recipe, and the guard that refuses a tuning script that reads them. The twelve questions of
  `data/eval/policy_questions.jsonl` are a tuning set, because ADR-006 chose the embedding and the query transform
  with the recall over them, so the comparison of `LL-V3-R12-03` has no set to compare over today
- [x] T114 Write the measurement over the held out set: the forty eight cases, the forty seven that go to the NLI model
  and the one that no evidence reaches, decided by code, with the denominator, the table by template, the count of the
  disagreements of the reader with the recipes, and the rate of the false supported. The sweep of ADR-007 reads only
  the datasets of the role `tuning`, so this measurement is a path of its own and it is the first number of this
  repository that is not measured over data a decision was taken against. Beside the count of the disagreements with the
  recipes, the measurement publishes the four counts of ADR-059: the divergence between the two readings, the divergence
  of each reading against the recipes, and the adjudicated accuracy over the set - **DELIVERED**: the script is
  `scripts/measure_heldout.py`, the test is `tests/verify/test_measure_heldout.py` and the report is
  `data/eval/report_heldout.md`. The verifier gets 24 of the 48 cases right (0,500), 23 of the 47 that go through the
  model and one that the code decides, the false `supported` is 4 and the false `contradicted` is 0, and the three
  counts of the reading are 2 of 48 against the other reading, 2 of 48 against the recipes and 2 of 48 against the
  recipes from the second reading
- [x] T146 Test in `tests/eval/test_label_heldout.py` that the mode `compare` never opens the recipes, that the build
  writes the origin of ADR-059 in every line, and that an incomplete reading is refused - **DELIVERED**: four tests in
  `tests/eval/test_label_heldout.py`, one that compares two readings on a tree that holds no recipe at all, one that
  reads the source of the comparison and finds no path to the key, one that refuses an incomplete reading naming the
  missing case, and one that holds the origin of ADR-059 in every line of the labelled set
- [x] T147 Run the first reading: a fresh session, blind to the recipes, over the forty eight cases of
  `data/eval/heldout/cases.jsonl`, writing `data/eval/heldout/labels_reader_a.jsonl` - **DELIVERED**: the reading
  answered 19 supported, 23 contradicted and 6 without enough evidence, and the file holds the note of the reader in
  every one of the 48 lines
- [x] T148 Run the second reading: another fresh session, blind to the recipes and blind to the first reading, over the
  same cases, writing `data/eval/heldout/labels_reader_b.jsonl` - **DELIVERED**: the reading answered 20 supported,
  24 contradicted and 4 without enough evidence, and it diverged from the first reading in 2 of the 48 cases
- [x] T149 Compare the two readings with the mode `compare` and adjudicate every case where they diverge into
  `data/eval/heldout/labels_adjudicated.jsonl`, with the reason of every decision - **DELIVERED**: the comparison found
  the two divergences, `ho-013` and `ho-035`, and the adjudication decided both by the rule that evidence which
  contradicts itself says two things and so says nothing, so the label of the two cases is `not_enough_evidence`
- [x] T150 Build the labelled set with the origin of ADR-059, declare the role `held_out` in `data/eval/datasets.json`,
  and publish the four counts of the section 7 of ADR-059 in the two READMEs and in `docs/evaluation.md` - **DELIVERED**:
  the labelled set is `data/eval/verification_heldout.jsonl` with the origin in every line, the manifest declares the
  role `held_out`, and the four counts are in the two READMEs, in `docs/evaluation.md` and in
  `docs/verification_sets.md`

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
