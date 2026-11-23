# Implementation Plan: Verifier calibration and benchmark integrity

**Branch**: `feature/v3` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-r4-verifier-calibration/spec.md`

## Summary

The release makes the numbers of the repository say what they are. It starts with the pin: every dataset of
`data/eval/` gets a manifest entry that names its digest, its count, its origin and the role it plays, and the
gate refuses when a dataset moves without the manifest moving. It continues with the hold out: a set of
verification cases that no decision of the repository was taken against, and a sweep of the thresholds that refuses
to read it. It ends with the report: the cases that failed, with the claim and the evidence, in the documents and
in the interface.

The technical approach keeps the Python core as the authority. The manifest lives in `ledgerlens/eval/manifest.py`,
the check in `scripts/check_eval_datasets.py`, and both are offline, deterministic and free of a key. The held out
set is a JSONL file beside the other datasets, declared in the same manifest with the role `held_out`. The sweep of
the thresholds is a script that runs the real NLI model, so it is slow and it does NOT run in the gate: the gate
runs the GUARD that refuses to tune against a set that is not `tuning`, and the slow sweep runs by hand.

## Technical Context

**Language/Version**: Python 3.12 for the core, TypeScript for the web application

**Primary Dependencies**: the existing `ledgerlens` core, `transformers` for the NLI model, `fastembed` for the
index of the policies, and the Next.js application under `apps/web`

**Architecture**: the manifest is a file of the repository and the module that reads it is the only place that
decides what is wrong between the manifest and the disk. The check in `scripts/` asks the module and prints what it
says, so there is one definition of the order of the problems and not two.

## The milestones of the release

| Milestone | What it delivers | State |
|---|---|---|
| M19 | The manifest of the datasets, the check in the gate, the ADR and the numbers that name their dataset | DONE |
| M20 | The held out set, the pin of the calibration and the guard that refuses to tune against it | Next |
| M21 | The recomputation of the calibration, the confusion matrices, the per case report and the versioned ids | Later |
| M22 | The Eval Lab of the interface, with the limitations next to the numbers | Later |

## The order, and why it is that order

A held out set that is created in the same milestone that publishes the numbers of the tuning sets is useless: the
set and the numbers arrive together and the reader cannot tell which one was there first. The manifest comes first,
because a set that is not declared is a set that a tuning script may read, and because the pin of the calibration
needs the manifest to point at. The report comes last, because a report over a set that may still move is a report
that has to be done again.

## The rules that apply to every milestone of this release

1. The role of a dataset is decided by EVIDENCE of what the repository did with it, and the conservative role wins
   when the evidence is not clean. A role is never chosen to make a number look better.
2. An agent that writes a case does not label it. The labels of a held out set are read by a person.
3. No number of the calibration changes without a recalibration that says what it was measured over.
4. The exact money rules are decided by code, and the NLI never overrules a deterministic contradiction.
5. A missing NLI model is `unavailable`, and it is not a pass.
6. Every decision that restricts the future becomes an ADR in `docs/decisions/`.

## The risks

- **A number that looks better and means less.** The guard against it is the role of the dataset: the tuning set
  says what may be tuned against, and the held out set says what may not.
- **A held out set that is contaminated before it is used.** The guard is the order of the work: the set is
  declared, the manifest is committed and the labels are read before any threshold is chosen against it, and the
  sweep refuses to read it.
- **A report that becomes another aggregate.** The guard is the per case list beside the aggregate, and the rule
  that a case with no evidence appears in the list even when the aggregate rises.
- **The cost of the slow sweep.** The sweep of the thresholds needs the real NLI model and it takes minutes. It
  runs by hand and it is recorded, and the guard that it depends on runs in the gate in milliseconds.

## The strategy for the validation

Each milestone ships its test before its code, and each claim of the release has a test that fails without the
code. The gate of the Python side is the one that runs everywhere, including in the continuous integration, and the
gate of the frontend is a job of its own. The end to end suite of the interface is a third check, and the demo of
the public replay site is the fourth: the product has to run, not only its tests.
