# Risks, open decisions and trade-offs

## Ranked risks

| Severity | Risk | Mitigation / decision |
|---|---|---|
| Critical | BYOK key leakage via trace, env, logs or session crossover | no public BYOK until fake-provider adversarial tests pass; in-memory scoped handles |
| Critical | Shared mutable ledger cache | immutable baseline, per-session branch, owner-checked API, zero cross-session test |
| High | Demo implies replay is live | explicit, persistent three-mode labels; verify no provider calls on replay |
| High | LLM claims treated as financial facts | deterministic amounts, source-linked verifier, abstention when missing |
| High | Public backend exposed to free unlimited workloads | rate limits, concurrency, budget, cancel, no owner-paid LLM default |
| High | Verifier overconfidence and calibration leakage | separate sets, live/generalization metrics, unknown status, transparent limitations |
| Medium | React reimplementation diverges from Python | generated API types + Python-only business logic |
| Medium | CPU-heavy NLI slows demo | pre-recorded replays; limited concurrency, optional worker |
| Medium | Too many screens / agent roles delay launch | stage by releases and evidence gates; first demo must work fast |
| Medium | Model API changed / removed | server capability registry, retired flag, record versioned replay |
| Medium | Third-party CDN/hosting unavailable | static fallback and clear error states |
| Medium | Case data licensing/provenance confusion | public-derived vs synthetic tags, NOTICE and source manifest |

## Open choices (assumptions and triggers)

**Backend hosting**: Begin one bounded instance. Upgrade only after concurrent demo users exceed observed capacity. **Realtime**: use SSE for server → browser; WebSockets add unnecessary bidirectional complexity initially. **Tracing platform**: local first, LangSmith optional; avoid requiring hosted quotas to show a replay. **State DB**: SQLite files for demo, not Postgres unless session scale needs it. **Multiagent**: only after measured gain on independent eval. **UI library**: Radix/shadcn + bespoke elements; decide by accessibility maintenance costs and implementation speed. **BYOK providers**: first OpenAI, expand upon adapter test passing. **Pricing telemetry**: if rates unknown, say so instead of fabricating.

## Portfolio versus SaaS conflicts

Do not build multi-user billing, bank-grade compliance certification, real payment operations, full tenant administration, external OAuth integrations, production fraud decision engine, self-hosted GPU fleet, user-supplied live bank statements or customer support SLAs. These could expand attack surface and effort without increasing demonstrable engineering skill.

## Review checkpoints

Every release asks four questions: (1) Does this make technical rigor observable to a visitor? (2) Is it truthful and reproducible? (3) Can it be maintained by one engineer? (4) Does it have a safer/simpler implementation? A feature failing all four should be deleted or deferred.

## Explicit non-claims

- The system is not approved to move money or resolve real financial disputes.
- Existing accuracy results do not establish statistical significance or financial correctness across banks.
- The NLI verifier does not provide mathematical proof of support for arbitrary text claims.
- Offline scripted mode is not autonomous general language understanding.
- Source data are public-derived historical records plus simulation, not true 2026 banking transactions.
- Screens and endpoints described in these docs are planned, not already implemented.
