---
description: "Task list for verified feedback to evaluation and training"
---

# Tasks: Verified feedback to evaluation and training

**Input**: Design documents from `specs/021-r20-verified-feedback-to-evaluation-and-training/`

**Prerequisites**: plan.md (required), spec.md (required), the design package of the release
(`docs/v3/advanced-specs/R20-01-verified-feedback-to-evaluation-and-training.md`), ADR-052, ADR-059, ADR-062,
ADR-065, ADR-067, ADR-068, ADR-073, ADR-075 and ADR-077 of `docs/decisions/`, ADR-P007 and ADR-P009 of
`docs/v3/adrs/`, and the code the loop builds on: the two published catalogs `data/eval/replay/` and
`data/eval/replay-real/`, the verifier of `ledgerlens/verify/checks.py`, the manifest and the guard of the tuning
in `ledgerlens/eval/manifest.py`, the reservation of `ledgerlens/eval/heldout.py`, the bundles of
`ledgerlens/replay/bundle.py` and the check of `scripts/check_eval_datasets.py`

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side is green before the commit. The tests of the loop live in `tests/feedback/` and run offline with
`LEDGERLENS_OFFLINE=1`. Every test of this list is written to fail before the code of its task and to pass after
it. The rule that binds every task of this list: no output of a model becomes training data without the
deterministic verdict of `ledgerlens/verify/checks.py` as its gate, and no task of this list writes into
`data/eval/heldout/`, publishes the key of the held out set or trains a model

**Organization**: Tasks are grouped by the stage of the loop that they build, from the decision that starts it to
the archive that closes it. The ids of this list start at T1001 and are unique in the repository; the ids of the
specifications `001` to `006` end at T172, and the blocks of the lists that run in parallel are kept apart, so that
two people can work on this list and on another list at the same time. The tasks marked `[P]` touch disjoint files
and can run in parallel with each other.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## The decision that starts the milestone

**Purpose**: the deterministic verdict is the gate of the training data, the tier of a record and the split of a
dataset are two different axes, and the held out set stays reserved.

- [x] T1001 Write the record of the decision in
  `docs/decisions/ADR-082-the-deterministic-verdict-is-the-gate-of-the-training-data.md`, with the number the index
  shows as free at the time of writing, saying that the verdict of a feedback record is the verdict of the
  deterministic verifier over the published evidence of the bundle, that the verdict of a model never fills that
  field and never promotes a record, that the tier of a record and the split of a dataset are two different axes,
  that the held out set stays reserved and that no model is trained by this milestone. Run
  `uv run python scripts/build_docs_index.py` to regenerate `docs/decisions/README.md` and commit the result. The
  record does not change any accepted record

## The record of a failure

**Purpose**: a published failure becomes a record that names its bundle, its claim, its evidence and its verdict.

  - **DELIVERED**: ADR-096 written and the decisions index regenerated with it; no accepted record changed.
- [x] T1002 Write `ledgerlens/feedback/__init__.py` with the docstring of the package, which says that the loop
  turns a published failure into a reviewed regression and that no output of a model enters a training set without
  the deterministic verdict as its gate
  - **DELIVERED**: `ledgerlens/feedback/__init__.py` carries the docstring of the package: the loop turns a published failure into a reviewed regression, and no output of a model enters a training set without the deterministic verdict.
- [x] T1003 Write `tests/feedback/test_record.py` first, expecting the fields of the record, the refusal of a record
  that misses one of them and the `Decimal` of a corrected amount with an exact comparison against the value of
  the ledger. Then write `ledgerlens/feedback/record.py` with the typed record, with a docstring that says what a
  record is and why it names the bundle and the digest of the bundle
  - **DELIVERED**: `tests/feedback/test_record.py` and `ledgerlens/feedback/record.py`: the typed record, the refusal naming the field, and the Decimal of a corrected amount with the exact comparison.
- [x] T1004 Write `tests/feedback/test_catalog_of_the_origin.py` first, expecting that the record names the catalog
  of its bundle and that a record of the catalog of a real model says that the recording is not reproducible byte
  for byte, under ADR-075. Then extend `ledgerlens/feedback/record.py` with the catalog and the statement of
  reproducibility, with a docstring that says that the two catalogs are not the same kind of thing

## The deterministic gate

**Purpose**: the verdict of a record is a decision of the code and never a proposal of a model.

  - **DELIVERED**: `tests/feedback/test_catalog_of_the_origin.py`: the record names the catalog, and the record of a real model says the recording is not reproducible byte for byte, under ADR-075.
- [x] T1005 Write `tests/feedback/test_deterministic_gate.py` first, expecting that the verdict of a record is the
  one the deterministic verifier of `ledgerlens/verify/checks.py` gives for the published evidence of the bundle,
  computed with no model and no network, and that a record whose NLI verdict disagrees with the deterministic one
  carries the deterministic one. Then write `ledgerlens/feedback/gate.py` with the re-verification of the bundle,
  reusing the reading of `ledgerlens/replay/bundle.py`, with a docstring that says that the gate is the only door
  to the tier `gold`
  - **DELIVERED**: `tests/feedback/test_deterministic_gate.py` and `ledgerlens/feedback/gate.py`: the verdict is the one of the deterministic verifier over the published evidence, and the deterministic one wins over the NLI verdict.
- [x] T1006 Write `tests/feedback/test_model_output_is_not_training_data.py` first, expecting that a record whose
  only support is an output of a model, whether the answer of the agent, the label of the NLI model or a correction
  proposed from a suggestion of the model, stays below the tier `gold` and that the training set does not carry it.
  This test is the red line of ADR-P007 expressed as a test
  - **DELIVERED**: `tests/feedback/test_model_output_is_not_training_data.py`: a record whose only support is a model output stays below gold and the training set does not carry it.
- [x] T1007 Write `tests/feedback/test_tiers.py` first, expecting that a record becomes `gold` only when the
  deterministic verdict supports the correction and a second reader of the repository confirmed it, that a record
  with a verdict of `contradicted` or `not_enough_evidence` is at most `silver` and that a record with no published
  evidence is `unverified`. Then write `ledgerlens/feedback/tiers.py` with the rules of the tier, with a docstring
  that says that the second reader is another person and not the same reader twice

## The registry of the records

**Purpose**: the records live in the repository with their digest, their permission and their tier, and the script
reads the disk and checks them.

  - **DELIVERED**: `tests/feedback/test_tiers.py` and `ledgerlens/feedback/tiers.py`: gold needs the deterministic verdict and a second reader, contradicted or not_enough_evidence is at most silver, no evidence is unverified.
- [x] T1008 Write `tests/feedback/test_registry.py` first, expecting the three fields of every entry of the
  registry, the refusal of an entry whose digest does not match the file it names and the refusal of a record
  whose source is a session of a visitor. Then write `ledgerlens/feedback/registry.py` with the registry and the
  check of the disk, with a docstring that says that a record without a digest is a record that cannot be found
  - **DELIVERED**: `tests/feedback/test_registry.py` and `ledgerlens/feedback/registry.py`: the digest, the permission and the tier of every entry, the refusal of a digest that does not match and of a visitor source.
- [x] T1009 [P] Write `scripts/check_feedback_registry.py` with the check that reads the disk, writes nothing and
  exits with a non zero code and a readable reason, and add the step to `scripts/gate.sh` next to the check of the
  datasets of the evaluation

## The training set and the contamination

**Purpose**: a training set holds only the records of the tier `gold` and never a case of another split.

  - **DELIVERED**: `scripts/check_feedback_registry.py` reads the disk, writes nothing and exits non zero with a readable reason; the step runs in `scripts/gate.sh` next to the check of the datasets.
- [x] T1010 Write `tests/feedback/test_training_set.py` first, expecting that a set built from a mixture of the
  three tiers holds only the records of the tier `gold`, and that a record whose permission is an evaluation never
  enters it. Then write `ledgerlens/feedback/training_set.py` with the build of the set and its digests, with a
  docstring that says that the tier and the permission are the two conditions of the door
  - **DELIVERED**: `tests/feedback/test_training_set.py` and `ledgerlens/feedback/training_set.py`: the set holds only the tier gold, and a record whose permission is an evaluation never enters it.
- [x] T1011 Write `tests/feedback/test_contamination.py` first, expecting that a set that holds a case of the held
  out set under an alias is refused with the name of the case and of the alias, and expecting that the guard of
  the tuning of `ledgerlens/eval/manifest.py` still refuses a tuning against a dataset whose role is `held_out`
  and refuses the published report of the measurement. Then write `ledgerlens/feedback/contamination.py` with the
  check that compares the content of the case and not only its identifier, with a docstring that says why an
  identifier is not enough

## The comparison and the promotion

**Purpose**: a candidate is compared with the baseline once, over the holdout, and the result is written down
whatever it is.

  - **DELIVERED**: `tests/feedback/test_contamination.py` and `ledgerlens/feedback/contamination.py`: the alias of a held out case is refused with the name of the case and of the alias, and the guard of the tuning still refuses the held out set and the published report.
- [x] T1012 Write `tests/feedback/test_promotion.py` first, expecting that a candidate that is worse on the holdout
  is not promoted, that the negative result is kept in the report and that the report names the set, the
  denominator, the role of the set and the digest of the dataset. Then write `ledgerlens/feedback/promotion.py`
  with the comparison and the decision, with a docstring that says that a comparison publishes no number that the
  run did not produce
  - **DELIVERED**: `tests/feedback/test_promotion.py` and `ledgerlens/feedback/promotion.py`: a candidate worse on the holdout is not promoted, the negative result is kept, and the report names the set, the denominator, the role and the digest.
- [x] T1013 [P] Write `tests/feedback/test_no_model_is_trained.py` first, expecting that the folder of the feedback
  holds no weight and no model artifact and that the modules of `ledgerlens/feedback/` import no training
  library. ADR-P007 keeps the runtime a single agent with a deterministic verifier and makes a specialist model a
  controlled experiment behind a flag

## The feedback of a visitor

**Purpose**: the sandbox keeps the feedback of a visitor and the shared set never sees it.

  - **DELIVERED**: `tests/feedback/test_no_model_is_trained.py`: no weight under the feedback folder and no training library imported by the modules of the loop.
- [x] T1014 Write `tests/feedback/test_visitor_feedback_is_sandbox_only.py` first, expecting that a comment sent
  through the sandbox of a visitor writes nothing under `data/eval/feedback/` and that the registry refuses a
  record whose source is a session of a visitor. Then extend the sandbox under `ledgerlens/sandbox/` with the
  feedback of the session, with a docstring that says that ADR-P009 is a safety invariant and not a preference

## The archive of an experiment

**Purpose**: an experiment can be read again and it refuses when the set moved.

  - **DELIVERED**: `tests/feedback/test_visitor_feedback_is_sandbox_only.py` and `ledgerlens/sandbox/feedback.py`: the comment of a visitor lands in the runtime of the sandbox, and the registry refuses a visitor source.
- [x] T1015 Write `tests/feedback/test_archive.py` first, expecting the fields of the archive, the digests of the
  dataset, the commit and the report of the comparison, and expecting the refusal with a reason when the digest of
  the dataset does not match the file. Then write `ledgerlens/feedback/archive.py` with the archive and its check,
  with a docstring that says that an experiment that cannot be reproduced is an anecdote

## The documentation that closes the milestone

**Purpose**: a reader of a record knows why the gate exists and what it forbids.

  - **DELIVERED**: `tests/feedback/test_archive.py` and `ledgerlens/feedback/archive.py`: the archive carries the digests, the commit and the report, and the check refuses when the digest does not match the file.
- [x] T1016 [P] Write `docs/feedback.md` with the four stages of the loop, the three tiers and the rule that
  promotes a record, the three roles of a dataset and the fact that they are a different axis, the relation to the
  two published catalogs and the difference between a reproducible failure and the failure of one run of a model,
  the reservation of the held out set, and the statement that no model is trained by this milestone. Link it from
  `docs/README.md` by running `uv run python scripts/build_docs_index.py`
  - **DELIVERED**: `docs/feedback.md` written with the four stages, the three tiers, the two axes, the two catalogs, the reservation of the held out set and the statement that no model is trained; the index regenerated.
