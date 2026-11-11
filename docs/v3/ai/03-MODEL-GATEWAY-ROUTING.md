# Model Gateway, Provider Selection and Agent FinOps

## Runtime promises

Public landing never requires a key; BYOK is optional. Providers and versions are not blindly enumerated or presumed compatible. A server-side allowlist declares `provider`, `model_id`, `supports_tools`, `supports_structured`, `supports_json`, `context_limit` (only if verified), `pricing_snapshot_at`, `pricing_known`, `healthcheck_status`, `max_output_tokens`. Unsupported or untested models appear disabled with the reason. A locally supplied OpenAI-compatible URL, when offered, is constrained to a client-side/local mode; never let an anonymous server send requests to an arbitrary visitor-specified address (SSRF).

## Routing modes

1. Manual choice - visitor selects one supported model.
2. Fixed cascade - small model for triage, robust model for investigation, deterministic verifier.
3. Rule router - intent/risk/budget partitioning defined by code.
4. Adaptive policy - learn route from observed paired evaluation under fixed constraints (future research).
5. Ensembles - multiple models only if independent evaluation demonstrates benefit.
6. Local mode - user-run model adapters, no misleading promise of free compute.

## Budget enforcement

Per run cap provider calls, tokens, wall time, retrieved documents, tool executions, parallelism, max USD and total sandbox sessions per IP/session (privacy-appropriate). Increment spend from provider-returned usage when available; otherwise mark estimated. A `BudgetExceeded` error terminates safely. Cancellation does not guarantee refund for already executed provider requests.

## Ephemeral credential architecture

Browser submits key over TLS directly to dedicated backend endpoint; backend validates minimal format without logging value; stores only a short-lived in-memory encrypted reference if necessary, with one-session scope, TTL and explicit forget; never in database, localStorage, logs, model prompts, traces or generated share links. Cookies scoped Secure/HttpOnly/SameSite. Provider requests originate server-side. Note that providers may independently retain content according to their policy: explain clearly. Require backend owner to prove redaction and isolate concurrent sessions before public launch.

## Pricing and unit economics

A model price cache is versioned and cited with effective timestamp; without price, display tokens but not invented USD. Include input/output, cached reads, retries, reasoning where reported, and overhead. Show `total_cost`, `cost/correct`, `marginal_quality_gain_per_1k_tokens`, `quality_by_case_complexity`, `p95_latency`, `human_review_minutes`, with denominators and provenance.

## Provider adapter conformance

Tests: structurally valid tool calls, refusal, malformed JSON, output truncation, timeout, 429, 5xx, rate-limit reset, token accounting, cancellation, missing per-call usage, tool batching, no-structured-output fallback. Mock adapters must not call real APIs and must be labeled simulated.
