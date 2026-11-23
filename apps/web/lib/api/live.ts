/**
 * The types of the published contracts of the live mode.
 *
 * Why this file exists: the browser has to know the shape of what the backend answers before it
 * answers anything. Every type below is transcribed field by field from a JSON Schema file of
 * `specs/003-r3-bring-your-own-key/contracts/` or from a route of `ledgerlens/api/byok.py`, so
 * a change of the contract shows up here as a type error instead of as a silent disagreement
 * between the two sides. The unit test `tests/unit/api-live-types.test.ts` reads the contracts
 * and checks the transcription field by field.
 *
 * The money travels as a text or as `null`, never as a number: a price is money, and money is
 * never a binary float. The frontend renders the decimal text the server sent and renders
 * nothing where the server sent `null`.
 */

import type { TraceEventType } from "@/lib/api/schemas";

/**
 * The four providers the allowlist of the server holds.
 * From `specs/003-r3-bring-your-own-key/contracts/model-profile.schema.json`, property `provider`.
 */
export type Provider = "openai" | "anthropic" | "google" | "local";

/**
 * The four statuses of a model profile.
 * From `specs/003-r3-bring-your-own-key/contracts/model-profile.schema.json`, property `status`.
 */
export type ModelStatus = "tested" | "experimental" | "disabled" | "retired";

/**
 * The four capabilities of a model profile.
 * From `specs/003-r3-bring-your-own-key/contracts/model-profile.schema.json`, property `capabilities`.
 */
export type ModelCapability = "chat" | "tool_calling" | "structured_output" | "reasoning";

/**
 * The two modes of a run.
 * From `specs/003-r3-bring-your-own-key/contracts/live-run-request.schema.json`, property `mode`.
 */
export type LiveRunMode = "live_agent" | "deterministic_sandbox";

/**
 * The four variants of a case.
 * From `specs/003-r3-bring-your-own-key/contracts/live-run-request.schema.json`, property `variant`.
 */
export type RunVariant = "A" | "B" | "C" | "D";

/**
 * The price of a model, with its provenance.
 * From `specs/003-r3-bring-your-own-key/contracts/model-profile.schema.json`, title `pricing`.
 *
 * Why the amounts are texts and not numbers: the domain parses them into a `Decimal`, because
 * money is never a binary float. The frontend renders them as they are and never computes with
 * them.
 */
export interface Pricing {
  /** Where the price comes from: the provider, a human, or nobody knows. */
  source: "provider" | "manual" | "unknown";
  /** The day the price was verified, or `null` when it never was. */
  last_verified: string | null;
  /** The price of a million input tokens, as a text, a number, or nothing at all. */
  input_per_1m_usd: string | number | null;
  /** The price of a million output tokens, as a text, a number, or nothing at all. */
  output_per_1m_usd: string | number | null;
}

/**
 * One model of the catalogue of the server.
 * From `specs/003-r3-bring-your-own-key/contracts/model-profile.schema.json`, title `ModelProfile`.
 */
export interface ModelProfile {
  /** The identifier of the profile, the one the visitor sends back to the server. */
  profile_id: string;
  /** The provider of the model. */
  provider: Provider;
  /** The name the provider gives to the model. */
  model_id: string;
  /** The name the visitor reads. */
  display_name: string;
  /** What the model can do. */
  capabilities: ModelCapability[];
  /** How much the model was tested. */
  status: ModelStatus;
  /** Whether the model may be picked in the public demo. */
  enabled_in_public_demo: boolean;
  /** The price of the model, with its provenance. */
  pricing: Pricing;
}

/**
 * The answer of the route of the catalogue of the models.
 * From the route `GET /v1/models` of `ledgerlens/api/byok.py`.
 */
export interface ModelCatalogueResponse {
  /** The models the visitor may pick. */
  models: ModelProfile[];
}

/**
 * The answer of the route of the price of a model.
 * From the route `GET /v1/models/{profile_id}` of `ledgerlens/api/byok.py`.
 */
export interface ModelPriceResponse {
  /** The profile the price belongs to. */
  model: ModelProfile;
  /** Whether the price of the model was verified. */
  price_known: boolean;
  /** The note that says in words where the price comes from. */
  price_note: string;
}

/**
 * The handle of a credential: the only thing the browser keeps of the key.
 * From `specs/003-r3-bring-your-own-key/contracts/credential-handle.schema.json`, title `CredentialHandle`.
 *
 * Why the handle and not the key: the key never travels back from the server, not in a field and
 * not in a header (FR-004). The handle identifies the secret in the vault and means nothing else.
 */
export interface CredentialHandle {
  /** The opaque handle of the credential. */
  handle: string;
  /** The provider the key belongs to. */
  provider: Provider;
  /** The moment the server accepted the key. */
  created_at: string;
  /** The moment the credential dies. */
  expires_at: string;
}

/**
 * The caps of a run.
 * From `specs/003-r3-bring-your-own-key/contracts/live-run-request.schema.json`, title `limits`.
 *
 * Why the cap of money is a text or nothing: the cap bounds the run, and a bound of money is
 * money, so the domain parses it into a `Decimal` and never into a float.
 */
export interface RunLimits {
  /** How many calls of a model the run may make. */
  max_model_calls: number;
  /** How many calls of a tool the run may make. */
  max_tool_calls: number;
  /** How many seconds the run may take. */
  max_wall_seconds: number;
  /** How many tokens the answer of the run may hold. */
  max_output_tokens: number;
  /** How many tokens the run may read, when the deployment sets that cap. */
  max_input_tokens?: number | null;
  /** How much the run may spend, as a text or as nothing at all. */
  max_estimated_usd?: string | number | null;
}

/**
 * The body of the request that starts a live run.
 * From `specs/003-r3-bring-your-own-key/contracts/live-run-request.schema.json`, title `RunRequest`.
 *
 * Why the body carries a handle and not a key: the key is in the vault of the server, and the
 * body of the request never holds a secret (FR-007, SC-012).
 */
export interface LiveRunRequest {
  /** The mode of the run. The live route runs the live mode only. */
  mode: "live_agent";
  /** The identifier of the scenario, in the shape `S` followed by two digits. */
  scenario_id: string;
  /** The identifier of the branch of the visitor. */
  sandbox_id: string;
  /** The revision the branch is expected to be at. */
  expected_revision: number;
  /** The account the case is about. */
  account_id: string;
  /** The question the visitor asks. */
  question: string;
  /** The variant of the case. */
  variant: RunVariant;
  /** The profile of the model the run uses. */
  model_profile_id: string;
  /** The handle of the credential of the visitor. */
  credential_handle: string;
  /** The caps of the run. */
  limits: RunLimits;
}

/**
 * The answer of the route that starts a live run.
 * From the route `POST /v1/live-runs` of `ledgerlens/api/byok.py`.
 */
export interface LiveRunAccepted {
  /** The identifier of the run, the one that travels in the path of the other routes. */
  run_id: string;
  /** The status of the run when it was accepted. */
  status: string;
  /** The mode of the run. */
  mode: "live_agent";
}

/**
 * The state of a run.
 * From the route `GET /v1/live-runs/{run_id}` of `ledgerlens/api/byok.py`.
 */
export interface LiveRunState {
  /** The identifier of the run. */
  run_id: string;
  /** The status of the run. */
  status: string;
  /** The answer of the agent, empty while the run is going. */
  answer: string;
  /** The reason the run ended badly, or `null`. */
  error: string | null;
  /** Whether the answer was produced without everything it wanted. */
  best_effort: boolean;
  /** Whether the visitor asked for the run to stop. */
  cancel_requested: boolean;
  /** The provider that answered, or `null` while the run is going. */
  provider: string | null;
  /** The profile of the model that answered, or `null`. */
  model_profile_id: string | null;
  /** The name of the model that answered, or `null`. */
  model_id: string | null;
}

/**
 * What the run consumed: the calls, the tokens, the elapsed time and the two costs.
 * From the route `GET /v1/live-runs/{run_id}/cost` of `ledgerlens/api/byok.py`.
 *
 * Why the costs are texts and not numbers: the observed cost and the estimated cost come from
 * the domain, where money is a `Decimal`. The frontend renders them as they are and never
 * computes a money amount of its own (FR-011).
 */
export interface CostReportBody {
  /** The identifier of the run. */
  run_id: string;
  /** The status of the run when the report was written. */
  status: string;
  /** How many calls of a model the run made. */
  model_calls: number;
  /** How many calls of a tool the run made. */
  tool_calls: number;
  /** The calls of the run, by model. */
  calls_by_model: Record<string, number>;
  /** How many tokens the run read. */
  input_tokens: number;
  /** How many tokens the run wrote. */
  output_tokens: number;
  /** How many seconds the run took. */
  elapsed_seconds: number;
  /** The cost the provider reported, or `null` when the provider reported none. */
  observed_cost_usd: string | null;
  /** The cost the server estimated from the price of the model, or `null`. */
  estimated_cost_usd: string | null;
  /** Whether the price of the model was verified. */
  price_known: boolean;
  /** Whether the cap of money is the one the server applied. */
  money_cap_authoritative: boolean;
  /** What cut the run short, or `null`. */
  cut_by: string | null;
  /** The usage that was not reserved. */
  usage_without_reservation: string[];
  /** The note of the server. */
  note: string;
}

/**
 * The branch of the visitor, forked from the published case.
 * From the route `POST /v1/sandboxes` of `ledgerlens/api/sandbox.py`.
 */
export interface SandboxBody {
  /** The identifier of the branch. */
  id: string;
  /** The identifier of the snapshot the branch was forked from. */
  base_snapshot_id: string;
  /** The hash of the snapshot the branch was forked from. */
  snapshot_sha256: string;
  /** The revision the branch is at. */
  revision: number;
  /** The moment the branch dies. */
  expires_at: string;
}

/**
 * The session of the visitor.
 * From the route `POST /v1/sessions` of `ledgerlens/api/byok.py`.
 */
export interface SessionBody {
  /** The identifier of the session. */
  id: string;
  /** The moment the session dies. */
  expires_at: string;
  /** What the session may do. */
  mode_capabilities: string[];
}

/**
 * The refusal of the server.
 * From the exception handler of `ledgerlens/api/byok.py`, which writes the resource `Error`.
 *
 * Why the frontend keeps the code of the refusal: a refusal is rendered where the action was,
 * with the words of the server and never with a text the frontend invented.
 */
export interface ApiErrorBody {
  /** The code of the refusal, for instance `LIVE_MODE_OFFLINE`. */
  code: string;
  /** The message of the server, in words a visitor can read. */
  message: string;
  /** Whether the same request may work later. */
  retryable: boolean;
  /** The identifier of the request, the one the logs of the server carry. */
  request_id: string;
}

/**
 * The three disclosures of the server, read from the headers of the answer.
 * From the headers `X-LedgerLens-Billing-Disclosure`, `X-LedgerLens-Key-Storage` and
 * `X-LedgerLens-Key-Erasure` of `ledgerlens/api/byok.py`.
 *
 * Why they are null when the header is absent: the frontend never invents a disclosure, and a
 * header the browser may not read is a header the server did not send.
 */
export interface DisclosureHeaders {
  /** What the server says about the billing of the calls. */
  billing: string | null;
  /** What the server says about the storage of the key. */
  keyStorage: string | null;
  /** What the server says about the erasure of the key. */
  keyErasure: string | null;
}

/**
 * The three event types that end a run.
 * From the trace contract `docs/v3/contracts/schemas/trace-event.schema.json`.
 *
 * Why the list is fixed here: the client of the stream closes the source on a terminal event, and
 * a browser that reconnects would receive the whole stream of the run again, from the beginning,
 * forever.
 */
export const TERMINAL_EVENT_TYPES: readonly TraceEventType[] = [
  "run.completed",
  "run.failed",
  "run.cancelled",
];

/**
 * The caps of a run when the visitor does not change them.
 *
 * Why these values: they sit inside the range the published contract allows, they are small
 * enough for a run to end in a minute of the visitor's attention, and the cap of money is left
 * open, because the price of the model may be unknown (FR-011).
 */
export const DEFAULT_RUN_LIMITS: RunLimits = {
  max_model_calls: 8,
  max_tool_calls: 12,
  max_wall_seconds: 60,
  max_output_tokens: 2048,
  max_input_tokens: null,
  max_estimated_usd: null,
};
