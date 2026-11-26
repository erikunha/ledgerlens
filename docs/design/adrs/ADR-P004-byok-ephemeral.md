# ADR-P004: Ephemeral, scoped BYOK for optional live model runs

**Status:** proposed. **Context:** public owner-paid model usage creates unbounded billing risk; visitor keys need serious isolation and trust safeguards.

**Decision:** short-lived process-memory credential handles bound to anonymous session and model provider; strict allowlist, no arbitrary endpoint, no key in localStorage/DB/trace. Bounded calls/tokens/timeout/concurrency, revocation, explicit provider billing/privacy notice. OpenAI adapter first, expand only after tests.

**Alternatives:** browser-only provider key (cannot support server-only scoped tools securely), encrypted persistent storage (unnecessary for demo, increases risks), require every visitor to key (unfriendly). **Trade-offs:** server processes transient secrets; memory zeroization not guaranteed. **Rollback:** disable live BYOK and rely on replay.
