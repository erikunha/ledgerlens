# LedgerLens as a Reference Architecture for Agentic Systems

The portfolio shall support an **open-ended research program** on trusted, financially relevant AI, without pretending the results are production-certified. All capabilities are candidates; each shipped behavior requires proof. The public app is educational and uses synthetic/sanitized data.

## Four synchronized lenses

1. **User experience:** analyst, reviewer, curious learner, engineer, researcher.
2. **Agent runtime:** tool orchestration, deterministic invariants, memory, information retrieval, multimodal input.
3. **System economics:** cost, quality, review burden, queue dynamics, error risk, distribution consequences.
4. **Evidence and safety:** source provenance, experimental integrity, authorization, observability, rollback.

## Foundational rules

- Python owns payment operations and numerical truth. Keep `ledgerlens/schemas.py` v1 public contract working, add adapters and versioned v2 objects.
- A human approval is a **state transition verified by a server-side policy engine**, not a 'yes' added to an LLM prompt.
- Every agent has `agent_id`, `version`, purpose, input/output schema, tool allowlist, evidence requirement, permitted data scope, token/time budget, failure mode and acceptance suite.
- The system can use no model, one model, one agent with tools, a manager plus specialists, fixed DAGs or more agentic patterns. Compare them on equivalent case sets before choosing.
- React/Next.js renders results; it never decides entitlement, monetary arithmetic or authorization.
- A replay is a recorded artifact. A sandbox run executes domain logic; only a live run invokes a provider.
- Never dynamically expose real payment mutations to public agent APIs. A 'refund approval' stays a *proposed* sandbox action and state change.

## Experiment ladder

`Rules only -> Chain A -> Tool agent B -> Verified tool agent C -> Bounded specialist D -> Hybrid adaptive E -> Local/small model F -> multimodal/causal research G`.

Every step is paired on the same immutable batch. Compare correct resolution, coverage, false actions, review load, latency, provider cost, incident potential and auditability. Higher complexity must earn its place; research features remain in the atlas even if rejected for the default runtime.

## Research not productization

Capabilities such as cross-company federation, private fine-tuning, causal inference, A2A, voice and action agents can demonstrate engineering fluency without commercially operating them. Default to synthetic events, sandboxed mock connectors, strict permissions and source attribution.
