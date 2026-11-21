# LL-V3-R8-02 - Evidence graph and provenance

**Status:** design proposed; not yet implemented. **Strategic lens:** Compounding and Proof of Work. **Audience:** Human reviewer and AI engineer. **Dependencies:** R0,R2,R4 and baseline claim schema.

## User outcome

Each claim can be traced to exact ledger rows, policy versions, FX source, calculator result and validation without fabricated citations.

## Ownership and compatibility

Do not add graph DB by default. Start with relational `evidence_nodes` and `evidence_edges` in sandbox metadata; use existing `Evidence`, `Claim`, `Verdict` models as mapping; source origin remains immutable.

## Typed interfaces and persisted state

`EvidenceRef` schema v3; `GET /runs/{id}/evidence/graph` returns `{nodes, edges, snapshot_hash, coverage}`; edges typed `supports`, `contradicts`, `derived_from`, `retrieved_from`, `supersedes`, `in_scope_of`.

## Algorithm and execution contract

Resolve tool-cited IDs against read-only source; hash normalized source; version effective time; compile typed claim→evidence links; mark orphans and conflicts; visual graph highlights original source, derivation and gaps; cross-snapshot edges must be explicitly cross-version references.

## Security, invalid states and recovery

Forged refs denied, account scope at query not just presentation, avoid embedding full private data in graph nodes. Treat LLM rationale as untrusted hypothesis.

## Acceptance scenarios (Given / When / Then)

- Missing evidence ID: unsupported rather than connected to nearest string match.
- FX source rate date mismatch: conflict visible.
- Policy version changed: historical case still points to prior document.
- Cross-account ref: 403/filtered before graph assembly.

## Metrics, evidence and regression gates

Reference resolution %, graph correctness on test fixtures, orphan count, user comprehension and latency.

## Definition of done and rollback

Schema unit tests, graph snapshot tests, source-linked code tour; fallback to list view. Rollback visualization without altering primary evidence.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
