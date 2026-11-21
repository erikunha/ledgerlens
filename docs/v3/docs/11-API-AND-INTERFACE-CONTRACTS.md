# HTTP/SSE API contract v1 - public demo facade

A first-draft OpenAPI file is at [`../contracts/openapi.yaml`](../contracts/openapi.yaml). **Code-generated validation is required before implementation; schema examples are design contracts, not deployed endpoints.**

## Authentication / session

Anonymous sessions use server-issued signed opaque HttpOnly cookies. No account creation. Every resource is session-owned except static published replay and public evaluations. Mutations require CSRF/Origin check. Do not use visitor-selected `account_id` as authorization: resolve it against selected simulated account and session branch.

## Endpoint inventory

| Method | Path | Mode | Outcome |
|---|---|---|---|
| GET | `/v1/public/scenarios` | public | versioned scenario catalog |
| GET | `/v1/public/replays/{replay_id}` | public | sanitized replay bundle metadata + events |
| GET | `/v1/public/evaluations` | public | benchmark manifests and summaries |
| POST | `/v1/sessions` | public → session | issue cookie and session capabilities |
| DELETE | `/v1/sessions/current` | session | revoke credentials and expire branches |
| POST | `/v1/sandboxes` | session | fork immutable base snapshot |
| GET | `/v1/sandboxes/{id}` | owner | branch status/revision/hash |
| GET | `/v1/sandboxes/{id}/ledger` | owner | account-scoped payments, refunds, disputes, payouts |
| POST | `/v1/sandboxes/{id}/mutations/preview` | owner | validate and calculate no-write diff |
| POST | `/v1/sandboxes/{id}/mutations` | owner | atomic typed event append; return new revision |
| POST | `/v1/sandboxes/{id}/reset` | owner | reset to immutable base; clear scoped memory |
| POST | `/v1/sessions/current/provider-credentials` | session | register ephemeral provider key; opaque handle |
| DELETE | `/v1/sessions/current/provider-credentials/{handle}` | owner | revoke ephemeral key |
| GET | `/v1/public/model-profiles` | public | supported models and capabilities |
| POST | `/v1/runs` | owner | start bounded Live execution or deterministic check |
| GET | `/v1/runs/{id}` | owner | run status, result when available |
| GET | `/v1/runs/{id}/events` | owner | SSE trace events, bounded replay/resume |
| POST | `/v1/runs/{id}/cancel` | owner | best-effort cancel; hard server deadline |
| GET | `/healthz` | public | lightweight backend readiness without internals |

## HTTP semantics

- 200 read/preview; 201 created; 202 accepted async run; 204 reset/revoke if no body.
- 400 invalid input; 401 missing session for protected routes; 403 forbidden; 404 not found or unauthorized opaque resource; 409 revision conflict or idempotency mismatch; 410 expired; 413 oversized input; 422 invalid domain command; 429 quota/rate limit; 503 live provider down.
- Error payload `{code, message, retryable, request_id}`. Never include raw provider exception/stack or key.
- Header `Idempotency-Key` for POST mutations/runs. Header `If-Match` or body `expected_revision` for branch writes. Commit transaction atomically; no partial event state on failure.
- Cursor pagination for ledger rows; bounded page size, deterministic sort with tie-breaker. Use explicit currency codes and normalized ISO time.
- `Cache-Control: no-store` for authenticated/session/credential responses; public replays cacheable with content-addressed version and ETag.

## Run start payload

```json
{
  "mode": "live_agent",
  "scenario_id": "S01",
  "sandbox_id": "sb_opaque123",
  "expected_revision": 0,
  "account_id": "C-0412",
  "question": "Why was the refund lower?",
  "variant": "C",
  "model_profile_id": "openai-verified-small",
  "credential_handle": "cred_ephemeral",
  "limits": {"max_model_calls": 8, "max_tool_calls": 12, "max_wall_seconds": 60, "max_output_tokens": 2500}
}
```

`credential_handle` is never a raw API key and cannot be used without a matching session cookie. The server resolves the effective run context from trusted session, branch and allowlists and returns canonical `run_id`, `status=queued/running`, `events_url`, `result_url`. Do not accept arbitrary file path or URL in payload.

## SSE envelope

```text
id: 17
event: span.ended
data: {"schema_version":"1","run_id":"run_123","seq":17,"at":"2026-11-11T12:00:00Z","event_type":"span.ended","span_id":"s17","parent_span_id":"s1","payload":{"name":"query_ledger","status":"ok","duration_ms":19}}
```

The source of truth is trace envelope schema v1. Use increasing IDs, dedupe on client, heartbeat, secure reconnection and `run.completed` only after verifier. A transport disconnect cannot turn a failed run into success.

## Versioning

Start `/v1`, include schema version on stored artifacts and SSE events, maintain OpenAPI client generation and contract tests. Deprecate fields behind minor compatible changes; schema breaking changes require `/v2` or explicit converter. Provide migration readers for recorded v1 traces, since old portfolio links must continue working.

## Sensitive data flows

Secret registration request accepts a key, but response/logs never echo it. Use `no-store`; suppress request-body telemetry at proxy and app. Do not include the key in a synthetic `RunStarted` event, trace attributes or exception. Block arbitrary provider URL selection.
