---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-090: The versioned memory has a quarantine that is a state, a promotion that is simulated and a snapshot that freezes a run

Status: accepted. Date: 2026-11-24.

## Context

The design package
[LL-V3-R12-04, versioned memory with a poisoning quarantine](../design/advanced-specs/R12-04-versioned-memory-with-poisoning-quarantine.md)
proposes a memory that is versioned, that carries a trust tier and an approval state, and that quarantines
what a poisoned case put in it. The repository had a memory already: the case memory of
[`ledgerlens/memory/long_term.py`](../../ledgerlens/memory/long_term.py) holds what a verified case concluded,
it refuses anything the verifier did not support, and it lives in the folder of the session that owns it
([ADR-030](ADR-030-case-memory-scoped-to-the-session.md)). What the memory of today did not have was a version,
a tier, an approval and a quarantine, and the milestone of
[specs/014](../../specs/014-r12-versioned-memory-with-quarantine/spec.md) adds exactly those four things.

Three questions of the milestone had to be answered before the code: who approves a promotion when the
repository has no review service, what a quarantine is when a deletion would teach nothing about the attack,
and what a replay of an old case reads when the memory of today is not the memory of its generation.

## Decision

**The approver of a promotion is simulated and the record says so, a quarantine is a state and not a deletion,
a snapshot freezes the memory of a run, and the file format of the case memory of today did not change.**

1. **Every record carries a version, a trust tier, an owner and an approval state.** The version is monotonic
   per record, and a new version never overwrites an old one, because a run of an old case points at the
   version it read. The tiers are `observed`, `corroborated` and `approved`, and the tier travels with the
   record, because the reader of a recall has to see how the fact entered the memory.
2. **Only what was verified gets in.** A proposal without a verified source is refused, and the case memory
   keeps refusing an investigation whose verdict is not `supported`. The rule of the versioned memory is the
   rule of the case memory read from the other side.
3. **A promotion needs a recorded approval, and the approval is simulated.** The repository has no human
   approval queue, so the first version simulates the reviewer in the offline path, and the approval names its
   date and the flag that says it was simulated. A simulation that hid itself would be a fake reviewer.
4. **The same assertion from two cases is one record with two sources.** The deduplication is by the hash of
   the fact, the record keeps the sources of both cases, and the second source raises the tier to
   `corroborated`. A record that said a fact was observed once when it was observed twice would be believed.
5. **A quarantine is a state and not a deletion.** A record that was meant to steer the agent is held in the
   state of the quarantine with the reason written down, it is absent from every retrieval including the query
   it matches best, and a person may release it. A memory that quietly forgets a poisoned record teaches
   nothing about the attack, and a reason that nobody can read is not a reason.
6. **A recalled text is data.** The recalled text arrives as the output of a tool, and it changes neither the
   tools of the agent nor its system prompt. The boundary between the memory and the policy is not negotiable
   by a text that a case wrote.
7. **A snapshot freezes the memory of a run.** A run reads a frozen snapshot of the memory, the digest of the
   snapshot travels with the run and with the published bundle, and the verifier of the bundle refuses a
   bundle whose digest does not match the snapshot it names. A replay of an old case reads the memory of its
   generation.
8. **The file format of the case memory of today did not change.** The versioned records live in a file of
   their own, beside the file of the case memory, in the folder of the session. The migration of the existing
   records is a decision of a later milestone, and the case memory of today keeps working as it was.
9. **The memory of a session dies with the session.** The deletion of the memory of a session takes the
   records of its owner and nothing else, and the folder of the session is gone with the expiry of the
   session (ADR-029).

## Alternatives considered

- **To let a model detect the attempt to steer the agent.** Refused. A detector that a model could talk out of
  its decision is not a detector, and the patterns that name an attempt are code of the repository.
- **To delete a poisoned record.** Refused. A memory that quietly forgets a poisoned record teaches nothing
  about the attack, and the attempt has to stay readable for the quarantine to be worth something.
- **To let the promotion of a record happen by repetition.** Refused. A record that becomes a policy by
  repetition is the risk the plan of the milestone names, and the guard is the recorded approval.
- **To migrate the records of the case memory of today into the versioned store.** Refused for now. The file
  format of the case memory did not change, and the migration is a decision of a later milestone.
- **To keep the snapshot of the memory out of the bundle.** Refused. A replay that reads the memory of today
  produces an answer that is not the answer of its generation, and the digest of the snapshot is what lets the
  reader of the bundle check it.

## Consequences

- **The repository has the versioned memory**, in `ledgerlens/memory/`: the store of the versions
  (`versioned_store.py`), the proposal (`proposal.py`), the approval (`approval.py`), the deduplication
  (`dedup.py`), the quarantine (`quarantine.py`), the retrieval (`retrieval.py`) and the snapshot
  (`snapshot.py`), with the tests in `tests/memory/`.
- **The tool `recall_cases` carries the tier of the record it returns**, and a record of the case memory of
  today reads as `observed`, which is the tier of what one case observed.
- **The bundle of a capture carries the snapshot of the memory of the run**, and the verifier of the bundle
  refuses a bundle whose digest does not match the snapshot it names. A bundle of the versions before the
  snapshot existed is checked as it always was.
- **The page of the memory is [the page of the versioned memory](../memory.md)**, with the tiers, the states,
  the reason of a quarantine and the rule that a recalled text is data.
- **The approval of a promotion is simulated.** When the repository has a review service, the approval of a
  promotion is a decision of that service, and this record is the one that says why the first version
  simulates it.

## Links

- [ADR-029, the expiry and the cleanup job](ADR-029-the-expiry-and-the-cleanup-job.md)
- [ADR-030, the case memory scoped to the session](ADR-030-case-memory-scoped-to-the-session.md)
- [the page of the versioned memory](../memory.md)
- [the specification of the milestone](../../specs/014-r12-versioned-memory-with-quarantine/spec.md)
- [the design package](../design/advanced-specs/R12-04-versioned-memory-with-poisoning-quarantine.md)
