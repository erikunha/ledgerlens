# ADR-P007: Prefer one evidence-first agent; multiagent requires a measured win

**Status:** proposed. **Context:** the goal is portfolio credibility and career impact, not a multiagent demonstration with more calls for no benefit.

**Decision:** main runtime remains evidence-first agent with deterministic verifier. A specialist graph variant D is a controlled experiment only after C baseline, held-out set and cost metrics. Publish it only if improvement outweighs extra latency/cost/risk.

**Alternatives:** supervisor + many specialized agents now (complexity and harder eval), no future agent variations (misses learning). **Trade-off:** fewer flashy nodes, stronger engineering rigor. **Rollback:** D off behind feature flag.
