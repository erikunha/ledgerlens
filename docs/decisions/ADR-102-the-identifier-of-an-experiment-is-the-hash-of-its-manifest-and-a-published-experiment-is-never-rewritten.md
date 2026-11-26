---
type: adr
status: accepted
date: 2026-11-25
---

# ADR-102: The identifier of an experiment is the hash of its manifest, and a published experiment is never rewritten

Status: accepted. Date: 2026-11-25.

## Context

The evaluation of the repository measured the variants A, B and C and published the reports, and the design
package of the paired arena ([specs/009](../../specs/009-r4-paired-evaluation-arena/spec.md)) asks for the
measurement of two variants over the same cohort to be a publishable, reproducible object: a manifest that pins
every input, a comparison that reads the runs and never calls a model, a gallery of the failures that never
leaks the key of the held out set, and a rerun that a third party can execute.

## Decision

**The identifier of an experiment is the hash of its manifest, a published experiment is never rewritten, a
comparison is refused over two cohorts, the method of the uncertainty is declared, the comparison never calls a
model under ADR-037, and the multi agent variant D of ADR-P007 stays behind a flag until a comparison of this
kind measures a gain.**

### The identifier of an experiment is the hash of its manifest

The manifest of an experiment pins the cohort, the variants, the judge, the seed, the commit, the command, the
goal and the method of the uncertainty. The identifier is the hash of the canonical form of the manifest, so two
manifests that differ in any field are two experiments and never one, and the identifier is computed and never
written.

### A published experiment is never rewritten

A result that can be rewritten is a result that can be tuned after the fact. The writer of the manifest and the
script of the experiment refuse to overwrite a published one, and the experiment lives under
`data/eval/experiments/`, so the historical reports of the variants A, B and C keep the 0.73 of the trajectory
with equivalent tools against the goal of 0.80.

### A comparison is refused over two cohorts

Two variants over the same cohort are compared case by case, and the runs must name the same cohort. A case that
one variant did not run, or whose run failed, is excluded from the pairing and named with the reason, so the mean
of a variant is never lowered by a run that did not happen.

### The method of the uncertainty is declared

The method of the milestone is the paired difference, with the standard error of the differences and the normal
approximation of 95 percent. The reason: the method is closed form and deterministic, it is the method the
orchestration comparison already declares, and a paired bootstrap would buy a resampling that the cohorts of the
repository do not need. The normal approximation needs no repetitions; a bootstrap of the same comparison would
need ten thousand resamples, and the repository declares the method that needs none. The interval of the result
names the method, because an interval without the method that computed it is a number without a measurement.

### The comparison never calls a model

The comparison reads the results of the runs that already happened, under ADR-037. The script of the experiment
computes and publishes, and it never calls a model and never chooses one.

### The variant D stays behind a flag

The multi agent variant D of ADR-P007 stays behind a flag until a comparison of this kind measures a gain, and
the comparison of the orchestration studio over the corrected corpus is the measurement that keeps it off: both
arms resolved 22 of 31, the difference is 0, and the flag stays off.

## Consequences

- The manifest of an experiment is one pinned object, and the identifier of the experiment is the hash of it.
- The gallery of the failures of a held out cohort is refused, because the key of the held out set is never
  published (ADR-069).
- A third party runs one command and gets the same bytes, and the rerun of a published experiment is a test of
  the repository.

## Links

- [the specification of the milestone](../../specs/009-r4-paired-evaluation-arena/spec.md)
- [ADR-037, the live mode and the one model](ADR-037-the-case-of-the-demo-runs-on-a-bridge-over-the-caller.md)
- [ADR-069, the key of the set is not published](ADR-069-the-reservation-follows-the-content-of-the-case-and-the-key-of-the-set-is-not-published.md)
- [ADR-P007, no multiagent by default](../design/adrs/ADR-P007-no-multiagent-by-default.md)
