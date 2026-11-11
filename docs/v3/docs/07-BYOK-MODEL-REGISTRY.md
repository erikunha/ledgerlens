# Bring Your Own Key (BYOK) and model selection

## Purpose and boundaries

Let visitors compare genuine model behavior using their own provider credentials **without making LedgerLens a paid model gateway** or assuming their secrets are safe by default. BYOK is an optional advanced feature; replay must fully communicate the project's value without any key.

Initial supported provider should be **OpenAI only**, because the current requirements already include `langchain-openai` and OpenAI configuration. Support Anthropic/Google only after optional dependencies and adapter tests are added. Never show a model as runnable simply because its name appears in a static list.

## Recommended credential flow

1. Frontend displays a privacy/cost disclosure and lets user choose provider/model, time budget and token/call cap.
2. User enters key in `<input type="password">` over HTTPS; never embed in query string, URL fragment, analytics or logs. Turn off password-manager save where feasible without making it inaccessible.
3. `POST /v1/session/provider-credentials` validates provider ID + key syntax for basic hygiene and stores key **only in the backend process memory** associated with an opaque short-lived handle bound to the signed session. Do not persist in Redis, DB, file, exception or trace. Never return the raw key.
4. Optional minimal provider metadata/probe may incur usage; label when it does. Return `credential_handle` + `expires_at` + `provider` + `validation_status`; bind it to session, NOT transferable.
5. `POST /v1/runs` references the handle and a model-profile ID. Backend creates SDK client instance with per-run credential; do not change global `os.environ` or `get_settings()` for arbitrary users.
6. On `Forget key`, expiry, explicit session reset, server restart or too many failures, invalidate/evict reference. Python cannot promise guaranteed memory zeroization; document that limitation.

**Alternative not chosen:** direct browser-provider calls. They would expose the key to client-side extensions/scripts and complicate evidence/tool auth; browser cannot safely perform the server-only scoped ledger tools. A backend proxy still processes visitor secrets transiently, and must be described honestly.

## ProviderRegistry contract

Each provider/model entry includes:

```json
{
  "profile_id": "openai-verified-small",
  "provider": "openai",
  "model_id": "gpt-4.1-mini",
  "display_name": "OpenAI small tool-calling example",
  "capabilities": ["chat", "tool_calling", "structured_output"],
  "status": "experimental",
  "required_extra": "langchain-openai",
  "pricing": { "source": "provider", "last_verified": null, "input_per_1m_usd": null, "output_per_1m_usd": null },
  "enabled_in_public_demo": false
}
```

This is an **example shape**, not a verified model catalog or live pricing. `profile_id` is an internal stable identifier, `model_id` is exact provider ID; status enum `tested`/`experimental`/`disabled`/`retired`; deployed registry must list only versions actually tested with tool calling + parser + verifier. Pricing must have verified time/source or show unknown. Model availability/capabilities change; support a controlled registry refresh rather than assuming historical IDs remain callable.

## Architecture-specific model requirements

| Variant | Requirements |
|---|---|
| A fixed baseline | chat completion or deterministic scripted |
| B ReAct | native tool calling or tested compatible adapter |
| C evidence-first | tool calling, bounded outputs; optional structured format; verifier separate |
| D optional multiagent | above + parallel/budget constraints |

Reject model selection when missing required capabilities, rather than silently switch to another model. User-requested model ID is not sufficient authorization to call any endpoint; strict allowlist validated server-side.

## Budget semantics

`RunBudget` hard stops: max provider calls, max tool calls, max input/output tokens where SDK reports them, wall-clock timeout and allowed scenarios. `max_estimated_cost_usd` is meaningful only when rates and usage estimates are available; if unknown, show "cost cannot be estimated reliably" and use technical limits. The client never assumes tokens are billable units one-to-one across providers. Include retry consumption, cached tokens, model-specific price tiers and provider responses when known.

UI displays **Estimated before**, **Observed token usage**, **Estimated/verified actual after** (if available) separately, including provider type and timestamp. Disclose that provider charges the visitor, not LedgerLens.

## Safety controls

- Per-IP and per-session rate limits, per-run concurrency lock, arbitrary prompt and maximum size limits.
- No arbitrary base URLs in public BYOK (prevents SSRF and credential exfiltration). Local compatible endpoints only when self-hosting with explicit configuration.
- Credential handle cannot be read or reused from another cookie/session, run ID or branch.
- Sensitive provider errors undergo structured normalization; redact known secret substrings and token-like patterns before telemetry, client response and persistence.
- Do not send keys to LangSmith or analytics; tracing content off by default for BYOK. Any outbound observability is opt-in and scrubbed.
- Disable persistent conversation storage for public BYOK; on reset scrub history. Strict CSP; forbid browser extension assumptions.
- No full cross-provider history transfer without user consent; the selected model receives only account-scoped simulated data and question.
- Terminal/self-hosted visitors can use `.env`, but public UI ignores deploy-time private owner keys and cannot reveal them.

## Adversarial acceptance tests

A: visitor A registers key and runs OpenAI while B requests same handle → B must receive 404/403 and make zero provider calls. B: provider error containing synthetic marker `sk-test-secret-marker` → marker never appears in trace/log/response. C: `POST /runs` with `model_id` outside allowlist → 422, zero SDK calls. D: key revoked during live run → further new calls prevented, running calls cancelled best-effort, run marked stopped. E: simultaneous providers do not cross-contaminate auth through global environment. F: wrong key produces actionable error without exposing request headers or token. G: no key typed at all → guided demo works in full.
