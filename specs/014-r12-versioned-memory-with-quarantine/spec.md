# Feature Specification: The versioned memory with a poisoning quarantine

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: `docs/design/advanced-specs/R12-04-versioned-memory-with-poisoning-quarantine.md`,
`docs/design/ai/04-MEMORY-RETRIEVAL-AND-KNOWLEDGE.md`, `docs/design/ai/02-SPECIALIST-ROSTER.md`, and the decisions
already in force: `docs/decisions/ADR-015-run-context-in-the-core.md`,
`docs/decisions/ADR-030-case-memory-scoped-to-the-session.md`,
`docs/decisions/ADR-029-the-expiry-and-the-cleanup-job.md`,
`docs/decisions/ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md`,
`docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md`.
User description: "The package proposes a memory that is versioned, that carries a trust tier and an approval
state, and that quarantines what a poisoned case put in it. The repository has a case memory that only accepts
what was verified and that lives in the folder of its session. This specification ports the versioning, the
trust tier, the approval and the quarantine, and says plainly what the repository already guarantees."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read that the memory of the repository only accepts what was verified (Priority: P1)

A reader asks what a past case can put in the memory of the agent. The answer is the rule that
`ledgerlens/memory/long_term.py` already holds: an investigation with any verdict that is not `supported` is
refused, and a broken coherence is refused too. The reader is told that the versioning, the trust tier and
the approval state of this specification do not exist yet, and that the rule that is already there is the
floor they will be built on.

**Why this priority**: the memory of the repository is the only thing that carries the conclusion of a past
case into a new one, and the rule that keeps an unverified conclusion out of it is the rule the whole
specification rests on.

**Independent test**: write an investigation with a verdict that is not `supported` and call `write_case`, and
expect the write to be refused and the memory to hold nothing.

### User Story 2 - Carry the version, the trust tier, the owner and the approval state on every record (Priority: P1)

A record of the memory is read. It says which version of the record it is, which tier of trust it was written
at, which session owns it and whether it was approved and by whom. Two cases that made the same assertion
produce one record with two sources, because the assertion is the same and the source is not. A record of an
old run points to the version of the memory that run read, so the record of the run stays true after the
memory has moved on.

**Why this priority**: a memory that cannot say which version it is cannot be reproduced, and the published
bundle of the repository promises that the evidence of a verdict is reproducible
(`docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md`).

**Independent test**: write the same assertion from two cases, read the memory, and expect one record with two
source references, a version, a trust tier, an owner and an approval state.

### User Story 3 - Read that a recalled text never widens the rights of a tool (Priority: P1)

A case whose refund note says that the tools of the agent may approve refunds is stored and later recalled.
Nothing changes: the text arrives as the output of the tool `recall_cases`, the system prompt of the agent
is the one of the repository, and the allowlist of the tools is decided by the code and not by a text. The
record is quarantined when it is proposed, and it never reaches a tool manifest, a prompt or a policy.

**Why this priority**: the package names it as the rule that no recalled text may influence the policy of the
system or of the tools, and the repository already treats the text of a tool as data
(`ledgerlens/agents/retrieval_agent.py` says it in the prompt of the agent).

**Independent test**: store a record whose text claims tool authority, recall it, and expect the tools of the
agent to be the same before and after, the system prompt to be unchanged and the record to be quarantined.

### User Story 4 - Quarantine a poisoned record even when it is the most relevant answer (Priority: P1)

A record is proposed whose text was meant to steer the agent. The record is not refused outright and it is not
used: it is quarantined, with the reason, and a retrieval over the memory never returns a quarantined record,
not even when it is the best match of the set. A quarantine is reversible by a person, and the reason of the
quarantine stays in the record.

**Why this priority**: a quarantine that only rejects the worst cases is not a quarantine. The package asks
for it explicitly, and a memory that returns the poisoned record is worse than a memory that never had it.

**Independent test**: quarantine a record, retrieve over a query it answers best, and expect no quarantined
record in the result, and expect the reason of the quarantine to be readable.

### User Story 5 - Delete the memory of a branch and touch nothing else (Priority: P1)

A visitor ends the session of the sandbox. The memory of the session is removed, because the case memory of a
session lives in the folder of the session and dies with it. A deletion removes only the records of that
owner, and the record of a branch of another session is untouched. A record of a visitor is never kept forever:
the expiry of the session takes it with it.

**Why this priority**: the repository already scopes the case memory of a session to the folder of that
session (`docs/decisions/ADR-030-case-memory-scoped-to-the-session.md`) and already cleans the expired
sessions up (`docs/decisions/ADR-029-the-expiry-and-the-cleanup-job.md`). The versioned memory may not
become a place where the text of a visitor survives the session.

**Independent test**: delete the memory of one session and expect no record of that session to be retrievable,
every record of another session to be intact, and the folder of the session to be gone.

### User Story 6 - Replay an old run with the memory of its generation (Priority: P2)

A published recording of a case is replayed. The answer of the replay is the answer of the generation, because
the run reads the snapshot of the memory that its generation read and not the memory of today. The bundle of
the replay carries the snapshot of the memory with its digest, so a reader can check it.

**Why this priority**: the published bundle of the repository is a promise of reproducibility, and a replay
that read a memory of today would be a different case wearing the name of an old one.

**Independent test**: replay a published bundle and expect the memory it reads to be the snapshot of its
generation, and expect the digest of the snapshot to be in the bundle.

### User Story 7 - See who proposed a record, who approved it and when (Priority: P2)

A reader of a recall wants to know how a fact entered the memory. The record names the case that proposed it,
the reviewer that approved it, the date it was written and the tier of trust it carries.

**Why this priority**: a memory whose provenance is invisible cannot be audited, and the whole value of the
laboratory of this repository is that a reader can check.

**Independent test**: read a promoted record and expect the source, the approver, the date and the trust tier
to be present and to match the record of the approval.

### Edge Cases

- A record proposed by a case whose verdict was not `supported`: the case memory refuses it, and a proposal
  of the versioned memory refuses it too.
- Two records that say the same thing with different scopes: the record with the narrower scope wins, and the
  other stays with its own scope.
- A record whose source case was deleted: the record loses its source, is marked as such and stops being
  retrieved, because a fact with no source is not a fact of the repository.
- A record whose validity expired: it is not retrieved and it is not deleted, because the history of the
  memory is part of the history of the run.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** (the repository today and the floor of this specification): The case memory of
  `ledgerlens/memory/long_term.py` refuses an investigation whose verdict is not `supported` or whose
  coherence is broken, and the versioned memory refuses a proposal that carries no verified source.
  - Test: `tests/memory/test_verified_only.py` expects the refusal of the write of an unverified
    investigation and the refusal of a proposal without a verified source.
- **FR-002** (the package): Every record of the memory carries a version, a trust tier, an owner and an
  approval state, and a record of an old run points to the version of the memory that run read.
  - Test: `tests/memory/test_record_fields.py` expects the four fields on every record and expects the
    version of a run of an old case to be the version it read.
- **FR-003** (the package): The same assertion proposed by two cases is deduplicated by the hash of the
  source and of the fact, and the record keeps both sources.
  - Test: `tests/memory/test_deduplication.py` expects one record with two source references for the same
    assertion and expects a different assertion to make a second record.
- **FR-004** (the package and the repository): A recalled text never influences the policy of the system or
  of the tools: it arrives as the output of a tool, the system prompt of the agent is the one of the
  repository, and the allowlist of the tools is decided by the code.
  - Test: `tests/memory/test_memory_is_data.py` expects the tools of the agent and its system prompt to be
    the same before and after a recall of a record that claims tool authority.
- **FR-005** (the package): A poisoned record is quarantined with a reason, and a retrieval never returns a
  quarantined record, not even when it is the best match.
  - Test: `tests/memory/test_quarantine.py` expects a quarantined record to be absent from every retrieval and
    expects the reason of the quarantine to be readable.
- **FR-006** (the package and ADR-030): A deletion removes only the records of its own owner, and the text
  of a visitor is never kept beyond the session that owns it.
  - Test: `tests/memory/test_delete_own_scope.py` expects the records of the deleted owner to be gone, the
    records of another owner to be intact and the folder of the session to be gone.
- **FR-007** (the package and ADR-073): A replay reads the snapshot of the memory of its generation, and the
  bundle of the replay carries the digest of that snapshot.
  - Test: `tests/memory/test_frozen_memory_snapshot.py` expects the digest of the snapshot of the generation
    in the bundle and expects the retrieval of the replay to read that snapshot.
- **FR-008** (the package and ADR-015): A record of one session is never visible in the retrieval of another
  session, and the memory of a sandbox branch lives in the folder of the session that owns the branch.
  - Test: `tests/memory/test_isolation.py` expects no record of one session in the retrieval of another, and
    expects the folder of the memory of a branch to be the folder of its session.
- **FR-009** (the package): A record carries its provenance: the case that proposed it, the reviewer that
  approved it, the date and the tier of trust.
  - Test: `tests/memory/test_provenance.py` expects the source, the approver, the date and the tier on a
    promoted record.
- **FR-010** (the package): A promotion to a higher trust tier needs an approval, and the approval is
  recorded as such. The repository has no human approval queue, so the first version uses a simulated
  reviewer in the offline path and says so in the record of the approval.
  - Test: `tests/memory/test_promotion_needs_approval.py` expects a promotion without an approval to be
    refused and expects the approval of a promotion to name that it was simulated.

### Key Entities

- **Memory record**: one versioned assertion with its trust tier, its owner, its approval state and its
  provenance.
- **Proposal**: the request that a case may add a record, with its source evidence, its scope and its period
  of validity.
- **Trust tier**: the level of a record, from a fact that a single case observed to a fact that a reviewer
  approved for a scope.
- **Approval**: the record that a named reviewer promoted a record to a tier, with its date and whether it was
  simulated.
- **Quarantine**: the state of a record that was refused as an attempt to steer the agent, with the reason and
  the person who may release it.
- **Memory snapshot**: the frozen set of records a run read, with its digest.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An unverified investigation is refused by the case memory and a proposal without a verified
  source is refused by the versioned memory.
- **SC-002**: Every record carries a version, a trust tier, an owner and an approval state, and the record of
  an old run points to the version it read.
- **SC-003**: The same assertion from two cases is one record with two sources.
- **SC-004**: The tools and the system prompt of the agent are the same before and after a recall of a record
  that claims tool authority.
- **SC-005**: A quarantined record is never returned by a retrieval, and its reason is readable.
- **SC-006**: A deletion takes the records of its owner and nothing else, and the folder of the session is
  gone.
- **SC-007**: A replay reads the snapshot of the memory of its generation, and the digest of that snapshot is
  in the bundle.
- **SC-008**: No record of one session is visible in the retrieval of another session.
- **SC-009**: The approval of a promotion names that it was simulated, because the repository has no human
  approval queue.

## Design documents

- [R12-04 Versioned memory with poisoning quarantine](../../docs/design/advanced-specs/R12-04-versioned-memory-with-poisoning-quarantine.md)
- [Memory, RAG, Knowledge and Data Provenance Research Program](../../docs/design/ai/04-MEMORY-RETRIEVAL-AND-KNOWLEDGE.md)
- [Agent Roles and Boundaries](../../docs/design/ai/02-SPECIALIST-ROSTER.md)
- [ADR-015: The run context enters the core, and the case memory is no longer global](../../docs/decisions/ADR-015-run-context-in-the-core.md)
- [ADR-030: The case memory of a sandbox session lives in the folder of the session](../../docs/decisions/ADR-030-case-memory-scoped-to-the-session.md)
- [ADR-029: The expiry has one home, and the cleanup is a job of the process](../../docs/decisions/ADR-029-the-expiry-and-the-cleanup-job.md)
- [ADR-061: The corpus of the policies is the contract of a fictional company](../../docs/decisions/ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md)
- [ADR-073: The published bundle carries the evidence its verdict was computed on](../../docs/decisions/ADR-073-the-published-bundle-carries-the-evidence-its-verdict-was-computed-on-and-it-is-reproducible.md)

## Status

**What exists in the repository today.** The case memory of `ledgerlens/memory/long_term.py` holds the episodic
and the semantic memory of the cases, it refuses anything the verifier did not support, it keeps the
excerpts of the cases, and it writes the case memory of a session in the folder of that session
(`ledgerlens/sandbox/memory.py`, ADR-030). The working memory of a turn lives in SQLite
(`ledgerlens/memory/history.py`). The expiry of a sandbox session exists and the cleanup job takes the folder
of the session with it (ADR-029). The `recall_cases` tool is one of the six tools of the agent, so a recalled
text reaches the model as the output of a tool and never as an instruction.

**What the package proposes.** A record with a version, a trust tier, an owner and an approval state, a
proposal interface with a source evidence and a validity period, a promotion that needs an approver,
deduplication by the hash of the source and of the fact, a quarantine for a poisoned record, a memory that is
ephemeral per branch or an approved public fixture or a research experiment, and a snapshot that freezes the
memory of a run.

**What this specification changes.** The approver of a promotion is a simulated reviewer, because the
repository has no human approval queue and no review service. The quarantine is a state of a record and not a
deletion, so the reason of a quarantine is readable and a person may release it. The deduplication is by the
hash of the source and of the fact, so the same assertion from two cases is one record with two sources and
not a loss of provenance. The deletion is scoped to the owner of the record, because the repository already
scopes the memory of a session to the folder of that session and the versioned memory may not become a place
where the text of a visitor outlives the session.

**What is still to be built.** The versioned store of the records, the trust tier, the approval state, the
proposal interface, the promotion, the deduplication, the quarantine and the frozen snapshot. None of it
exists, and the case memory of today keeps its own file format and its own index.

## Assumptions

- The trust tier and the approval state are new, and the case memory of today carries neither. The migration
  of the existing records is a decision of the implementation and not of this specification.
- The repository has no human approval queue, so the promotion is simulated in the offline path and the
  approval says so in its own record. A real review service is another milestone.
- The package speaks of a research experiment of memory and of an approved public fixture. The first version of
  this specification is neither: it is the memory of the case of the repository, versioned.
- No number of this specification says that the versioned memory recalls better than the memory of today.
  The measure is the attribution precision and the count of quarantined records, over the set that the
  manifest of the datasets names.

## Out of scope

- The retrieval experiments of the package: the comparison of dense retrieval with BM25, with the hybrids and
  with the rerankers. The baseline of the repository stays the dense FAISS index, and the package says
  itself that a comparison must be measured and not declared.
- The graph of the knowledge and the document ingestion. The corpus of the policies is the contract of a
  fictional company and it is not a document to ingest (ADR-061).
- The human approval queue and the review service.
- The frontend of `apps/web/`. The interface of the memory is the trace and the published bundle.
