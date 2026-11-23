---
type: adr
status: accepted
date: 2026-11-11
---

# ADR-011: The v3 roadmap in verifiable slices

Status: accepted. Date: 2026-11-11.

## Context

The design package that drives the next cycle of work is wide open. It lists 24 release stages, 234 candidate
capabilities and 161 candidate tasks, and it explicitly says that most of them are not implementation ready. A plan of
that size cannot be executed as one piece of work: nothing would be verifiable, and a reader could not tell which part
of the plan is real and which is an idea.

The repository already has a gate that runs the lint and the offline test suite. That gate is the only thing that turns
a claim into a fact. The plan has to be built on top of it.

## Decision

The v3 work is organised as verifiable slices. Each slice is one task of the backlog of the package, it delivers
evidence a third party can rerun, and it lands as one commit with the gate green.

The evidence of a slice is, per the package itself, one of:

- for the engineering tasks, "reproducible test + trace/fixture + source link";
- for the economic tasks, "economic/functional oracle + paired test + assumptions".

A slice that cannot state its evidence is not ready to be planned.

The releases are ordered by what makes the next one possible:

- **R0** freezes the truth: the baseline, the public trace contract, the replay bundle, the verifier denominators and
  the run context. No behaviour change enters R0.
- **R1** is the visitor without a key: the public interface and the recorded replay.
- **R2** is the sandbox: an isolated branch per visitor.
- **R3** is bring your own key, and it comes last because it is the only one that handles a secret and spends money.

Each release has a specification folder under `specs/`, written with the specification toolkit, with the user
stories, the functional requirements, the technical plan and the ordered task list. The roadmap in
`docs/roadmap-v3.md` is the index of those folders.

## Alternatives considered

- **Execute the package backlog as one large change.** Nothing would be independently verifiable, and a reviewer would
  have to read the whole diff to judge any part of it.
- **Keep the plan outside the repository, in a local folder.** The plan would drift from the code, and nobody else could
  read it. The package itself lives outside git because it is material of a course, but the plan that drives this
  repository is part of the repository.
- **Order the releases by business value instead of by dependency.** The sandbox depends on the run context, and the
  live mode depends on the session isolation. A value order would start R3 before R2 and build the secret handling on
  top of a context that does not exist yet.
- **Use the specification toolkit for every task.** The toolkit produces a specification folder per feature. With 161
  candidate tasks that is more ceremony than work. It is used per release, where the user stories are real and the
  boundaries are known.

## Consequences

- Every commit states what it delivers and how to rerun the evidence.
- The gate is the arbiter. A slice with a red gate is not done.
- The plan is readable next to the code, in the language of the repository.
- A slice that turns out to be wrong is cheap to undo, because it is small.
- The plan carries a declared gap: the central economic number of the project, the cost per correctly resolved case,
  has no measurement yet. The roadmap says so, and any published cost number needs a measurement with the right
  denominator first.
