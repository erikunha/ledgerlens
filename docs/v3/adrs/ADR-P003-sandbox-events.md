# ADR-P003: Branch simulated events, never directly edit the published ledger

**Status:** proposed. **Context:** existing simulator uses append-only events and constrained SQLite projections. `@st.cache_resource` shares resources across UI sessions. Exposing direct table edits could corrupt the sample and cause cross-visitor leaks.

**Decision:** immutable published snapshot; visitor-owned short-lived sandbox branch; typed domain events and tool fault overlays; transactional validation/projection; idempotency and revision compare; reset to baseline hash. Per-account scoped copy is derived from same branch revision used by agent.

**Alternatives:** copy entire DB then `UPDATE` from UI (simpler but breaks event invariants); frontend-only JS editing (not truthful); multi-tenant DB upfront (unnecessary). **Cost:** implementation/migrations for new event types. **Rollback:** disable scenario mutation, keep Replay and ledger read-only.
