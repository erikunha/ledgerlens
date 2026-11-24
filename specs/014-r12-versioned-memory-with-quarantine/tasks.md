---
description: "Task list for the versioned memory with a poisoning quarantine"
---

# Tasks: The versioned memory with a poisoning quarantine

**Input**: Design documents from `specs/014-r12-versioned-memory-with-quarantine/`

**Prerequisites**: plan.md (required), spec.md (required), the design package
(`docs/v3/advanced-specs/R12-04-versioned-memory-with-poisoning-quarantine.md`) and the decisions that already
bind: `docs/decisions/ADR-015-run-context-in-the-core.md`,
`docs/decisions/ADR-030-case-memory-scoped-to-the-session.md` and
`docs/decisions/ADR-029-the-expiry-and-the-cleanup-job.md`

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate
of the Python side is green before the commit. The whole suite runs offline with `LEDGERLENS_OFFLINE=1` and no
key. A task that is delivered says so, with **DELIVERED** and the evidence of what it delivered.

**Organization**: Tasks are grouped by the four parts of the plan, and the tasks of a group touch disjoint files
so that they can be worked on in parallel. The ids of this milestone start above the ids of `specs/001-` through
`specs/006-` and they are continuous inside this milestone. The folder `tests/memory/` exists today; the tests
of the versioned memory are added to it.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## Part A, the record and its versions

**Purpose**: a record says which version it is, and the version of a run never disappears.

- [ ] T200 [P] Add the typed record of the versioned memory to `ledgerlens/schemas.py`, with the docstring of
  the class saying what it carries and why, and write the test in `tests/memory/test_record_fields.py` that
  expects the version, the trust tier, the owner and the approval state on every record and that expects the
  version of a run of an old case to still exist
- [ ] T201 [P] Write the module `ledgerlens/memory/versioned_store.py` with the docstring saying that the store
  keeps the versions of the records in the folder of the memory of the session and that a new version never
  overwrites an old one, and write the test in `tests/memory/test_versioned_store.py` that expects two versions
  of one record to coexist and that expects the version of a run of an old case to be readable
- [ ] T202 [P] Write the test in `tests/memory/test_isolation.py` that expects no record of one session in the
  retrieval of another session and that expects the folder of the memory of a branch to be the folder of its
  session, through `ledgerlens/sandbox/memory.py`

## Part B, the proposal and the promotion

**Purpose**: a record enters the memory with a source and leaves the tier of a case only with an approval.

- [ ] T203 [P] Write the module `ledgerlens/memory/proposal.py` with the docstring saying that a proposal
  carries a scope, a source evidence, an assertion, a period of validity and the reviewer that approved it, and
  write the test in `tests/memory/test_verified_only.py` that expects the refusal of a proposal without a
  verified source and that expects `ledgerlens/memory/long_term.py` to keep refusing an investigation whose
  verdict is not `supported`
- [ ] T204 [P] Write the module `ledgerlens/memory/approval.py` with the docstring saying that a promotion
  needs a recorded approval, that the approval names its date and that it says whether it was simulated, and
  write the test in `tests/memory/test_promotion_needs_approval.py` that expects the refusal of a promotion
  without an approval and that expects the approval of a promotion to name that it was simulated
- [ ] T205 [P] Write the module `ledgerlens/memory/dedup.py` with the docstring saying that the same assertion
  proposed by two cases is deduplicated by the hash of the source and of the fact and that the record keeps
  both sources, and write the test in `tests/memory/test_deduplication.py` that expects one record with two
  source references and that expects a different assertion to make a second record
- [ ] T206 [P] Write the test in `tests/memory/test_provenance.py` that reads a promoted record and expects the
  source, the approver, the date and the tier of trust to be present and to match the record of the approval

## Part C, the quarantine

**Purpose**: a record that was meant to steer the agent is held aside with a reason, and it is not retrieved.

- [ ] T207 [P] Write the module `ledgerlens/memory/quarantine.py` with the docstring saying that a poisoned
  record is held in a state with a reason, that the state is not a deletion and that a person may release it,
  and write the test in `tests/memory/test_quarantine.py` that expects a quarantined record to be absent from
  every retrieval, including the query it matches best, and that expects the reason to be readable
- [ ] T208 [P] Write the test in `tests/memory/test_memory_is_data.py` that stores a record whose text claims
  tool authority, recalls it, and expects the tools of the agent of `ledgerlens/agents/integrator.py` and its
  system prompt to be the same before and after the recall
- [ ] T209 [P] Write the module `ledgerlens/memory/retrieval.py` with the docstring saying that the retrieval
  returns typed references with their tier of trust and that it never returns a quarantined record, and extend
  the tool `recall_cases` of `ledgerlens/tools/cases.py` to carry the tier of the record it returns
- [ ] T210 [P] Write the test in `tests/memory/test_delete_own_scope.py` that deletes the memory of one
  session and expects no record of that session to be retrievable, every record of another session to be
  intact and the folder of the session to be gone, with the expiry of `ledgerlens/sandbox/ttl.py`

## Part D, the frozen snapshot of a run

**Purpose**: a replay of an old case reads the memory of its generation.

- [ ] T211 [P] Write the module `ledgerlens/memory/snapshot.py` with the docstring saying that a run reads a
  frozen set of the records and that the digest of the snapshot travels with the run, and write the test in
  `tests/memory/test_frozen_memory_snapshot.py` that expects the digest of the snapshot of the generation in the
  bundle of `ledgerlens/replay/bundle.py` and that expects the retrieval of a replay to read that snapshot
- [ ] T212 [P] Extend the capture of `scripts/capture_replay.py` so that it writes the digest of the snapshot of
  the memory of the run into the bundle, and extend the verifier of `ledgerlens/replay/verdict.py` so that it
  refuses a bundle whose digest does not match the snapshot it names
- [ ] T213 [P] Write the page `docs/memory.md` that names the trust tiers, the states of a record, the reason of
  a quarantine and the rule that a recalled text is data, with the link to the case memory of
  `ledgerlens/memory/long_term.py` that refuses what was not verified
- [ ] T214 [P] Write the record of the milestone in `docs/decisions/` with the next number after ADR-077, which
  writes down that the approver of a promotion is simulated, that a quarantine is a state and not a deletion,
  that a snapshot freezes the memory of a run and that the file format of the case memory of today did not
  change, and link it from `docs/decisions/README.md`
