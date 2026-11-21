# Evidence, tracing, recorded artifacts and investigation playback

## Main educational message

The important difference is not whether an LLM produces a confident answer; it is whether a financial explanation can be **reconstructed from its actual inputs, rules, tool outputs and verification decisions**.

## Evidence vocabulary

- **Source fact:** immutable data row, timestamped rate fixture, policy chunk or Decimal computation, with stable reference and origin.
- **Derived claim:** statement made by an agent using one or more sources.
- **Verifier decision:** `supported`, `contradicted`, `not_enough_evidence` with method `rule|numeric|nli|none`, threshold/model metadata where applicable.
- **Agent recommendation:** business action proposal, never automatic payment instruction.
- **Unresolved information:** what must be checked by a human.

A green verdict is about the particular validation protocol, not proof of absolute truth. NLI is probabilistic; numeric checks require correctly bound evidence and source integrity.

## Evidence IDs and source context

Existing source prefixes `sql:`, `api:`, `policy:`, `fx:`, `calc:`, `case:` should be maintained. Add opaque stable `evidence_uid` scoped to `run_id` and source hash; distinguish `retrieved_at` from the original event time. A display may link `CL1` to `sql:1` row TX-2048, `policy:refund-fx` and `calc:1`. Clicking source opens the actual sanitized passage/row and its provenance.

## Trace event protocol

Use `run_id`, `seq` (monotonic), `schema_version`, `time`, `event_type`, `span_id`, `parent_span_id`, `payload`. Events include: `run.started`, `plan.created`, `span.started`, `span.ended`, `evidence.added`, `claim.verdict`, `run.status`, `run.completed`, `run.failed`, `run.cancelled`. Double delivery/reconnect dedupe by `(run_id, seq)`.

Preserve native Span schema as internal implementation; introduce a **normalizer adapter** for stable public protocol rather than coupling React to `langchain` callback internals. Map relevant spans to OpenTelemetry GenAI conventions as an adapter, explicitly noting that GenAI semantic conventions evolve; keep external schema version independent.

Use an SSE stream for live updates (`event` + `data` + `id`). Provide 15-second heartbeat while active, bounded buffers, subscription auth and graceful shutdown. UI never animates absent events as if they came from model.

## Redaction and integrity

- Read schema and field names and allowlist; never log full provider key, request headers, signed URLs, cookies or session tokens.
- Pseudonymize any identifying data if user-uploaded data are ever introduced (not in current scope).
- Preserve visible business identifiers only from the public simulated dataset; published artifacts are reviewed before commit.
- Capture `code_sha`, `snapshot_hash`, `prompt_hash`, `model_profile`, `provider_version when available`, `policy_version`, `sim_seed`, `run_mode`, `eval_suite_version`, `run_timestamp`, `redaction_version`.
- Artifact is immutable and hashed. `content_sha256` validates transport; it is **not a signature or proof of historical truth** unless signed by a trusted authority.

## Replay recording protocol

1. Run a real supported model offline in a controlled local environment on each curated public scenario.
2. Capture complete observable trace events, generated SQL, final answer, verifier report, input data references and cost/token measurements. Redact secrets and review content.
3. Normalize/validate schema; hash artifact; attach model/provider/seed/hash provenance.
4. Store public sanitized bundles under `data/replay/v1` and publish in demo. Prefer gzip or CDN compression.
5. UI plays *recorded events* at selectable 1×/2× speed; actual original latency shown separately from playback duration.
6. Refresh bundles when model/prompt changes. Stale artifacts remain available only with explicit old-version labels.

Playback controls: pause, step, skip, expand tools, collapse model calls, view evidence, compare with another recorded variant, download sanitized JSON. The replay must not write to long-term case memory, incur provider cost or mutate the ledger.

## Evidence graph component

Use a typed graph (not a full graph database): transaction → refund → applied FX rate → policy paragraph → calculated amount → claim/verdict. Edges have source and direction; nodes click into details. Render small interactive SVG/React Flow if accessible, with an equivalent table and keyboard list. Avoid graph layout that moves unpredictably during live execution; animate only after nodes arrive.

## Three perspective comparison

Default explain view: "What happened?" (plain-language) → "How do we know?" (evidence) → "What did the agent do?" (trace). Advanced view offers SQL, raw envelopes, model configuration and verifier metadata.

## Capture quality / trust

Include *at least one published failure*: e.g., a run with insufficient FX source or unsupported ARS currency; show escalation rather than concealing. Link every benchmark claim from README to `data/eval` with exact dates/trials. Chart and diagrams are representations of data, not independent evidence.

## Acceptance tests

- Replay start produces zero provider HTTP calls and zero data mutations.
- Trace sequences monotonic even with nested concurrency; reconnection duplicates are ignored.
- Every displayed claim references a source existing in the run artifact; missing evidence shows unknown.
- A verifier outage cannot render a `supported` badge.
- A changed branch hash cannot reuse an old trace with fresh badge.
- Secrets and private handles never occur in recorded bundle/log output.
- Example timestamps are the actual captured run time; playback does not alter provenance.
