# LL-V3-R12-04 - Versioned memory with poisoning quarantine

**Status:** design proposed; not yet implemented. **Strategic lens:** Compounding and Inversion. **Audience:** AI researcher. **Dependencies:** R8 evidence and R12 retrieval research.

## User outcome

Inspect how past cases affect current inference, and safely reject unapproved instructions in memory.

## Ownership and compatibility

Extend existing `ledgerlens/memory` with scoped record version, trust tier, owner and approval state. Memory can be ephemeral per branch, approved synthetic public fixture, or research experimental.

## Typed interfaces and persisted state

Memory proposal interface has `{scope,source_evidence,assertion,valid_from,approved_by_simulated_reviewer}`; retrieval returns typed refs and trust levels; delete only own experiment branch.

## Algorithm and execution contract

Propose memory from verified case, require approver for promotion, enforce semantic and temporal scope, deduplicate by source+fact hash, retrieve matching approved records; records of old runs point to old memory versions.

## Security, invalid states and recovery

Never let recalled text influence system/tool policy. Poisoned memory quarantined, even when highly relevant. No leaking case data into another account; no permanent retention of visitor text.

## Acceptance scenarios (Given / When / Then)

- Insert malicious memory claiming tool authority -> downstream tool rights unchanged.
- Delete branch memory -> retrieval returns none.
- Same assertion repeated across cases -> deduplicated with multiple source refs.
- Replay older run -> uses frozen memory snapshot, not current memory.

## Metrics, evidence and regression gates

Memory attribution precision, cross-scope access denied, poison detection, retrieval impact on case outcomes.

## Definition of done and rollback

Property tests, anonymized screenshot, memory snapshot provenance. Rollback to existing read-only case memory.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
