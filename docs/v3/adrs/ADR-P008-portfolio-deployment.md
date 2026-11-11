# ADR-P008: Single bounded API host with static replay fallback

**Status:** proposed. **Context:** recruiter-facing demo traffic is low and variable; availability and predictable maintenance matter more than scale.

**Decision:** CDN/static Next pages and versioned public replay; one bounded Dockerized FastAPI instance for sandbox/BYOK with per-session tempfile database, hard resource limits, TTL cleanup. Multiple replicas only after actual scaling need and shared session design.

**Alternatives:** full Kubernetes/Redis/Postgres stack (cost), client-only simulation (loses existing Python behavior), serverless CPU-NLI cold starts (latency). **Trade-off:** backend restarts lose ephemeral branches; explicit UI disclosure. **Rollback:** static demo stays online.
