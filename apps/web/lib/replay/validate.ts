/**
 * The runtime validation of the published artifacts.
 *
 * Why this file exists: the interface must never render an artifact it does not understand. A bundle that comes from
 * a file, from a network or from a hand edited folder can carry a sequence number below 1, a snapshot hash that is not
 * a sha256 in lowercase hexadecimal, a mode the contract does not define or an event type the contract does not
 * define. The contract refuses those, so the interface refuses them too, with a reason a reader can act on.
 *
 * Every function here returns a result and never throws at the caller. The caller decides what to do with a refused
 * artifact, and the reason travels with the refusal so that the interface can show it instead of guessing.
 */

import { z } from "zod";

import {
  BUNDLE_SCHEMA_VERSION,
  CAPTURE_KINDS,
  RESULT_SCHEMA_VERSION,
  TRACE_EVENT_TYPES,
  TRACE_MODES,
  TRACE_SCHEMA_VERSION,
  type LedgerArtifact,
  type PublicInvestigationResult,
  type ReplayBundle,
  type ReplayBundleManifest,
  type ScenarioIndexEntry,
  type TraceEvent,
} from "@/lib/api/schemas";

/**
 * The outcome of a validation: the value when the artifact is accepted, the reasons when it is refused.
 *
 * The reasons are plain strings on purpose. They end up in an error panel that a visitor reads, and a structured
 * error would only be formatted back into a sentence anyway.
 */
export type ValidationResult<T> =
  | { ok: true; value: T }
  | { ok: false; reasons: string[] };

/** The pattern of a sha256 in lowercase hexadecimal, as the contract demands it. */
const SHA256_PATTERN = /^[a-f0-9]{64}$/;

/** The pattern of the code commit hash, as the bundle contract demands it. */
const CODE_SHA_PATTERN = /^[a-f0-9]{40}$/;

/** The pattern of a scenario identifier, as the bundle contract demands it. */
const SCENARIO_ID_PATTERN = /^S[0-9]{2}$/;

/** The pattern of an ISO 8601 moment with a time zone. */
const DATE_TIME_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

/** The schema of one trace event, transcribed from `trace-event.schema.json`. */
const traceEventSchema = z.object({
  schema_version: z.literal(TRACE_SCHEMA_VERSION),
  run_id: z.string().min(1),
  seq: z.number().int().min(1, "the sequence number starts at 1"),
  at: z.string().regex(DATE_TIME_PATTERN, "the moment must be an ISO 8601 date and time"),
  event_type: z.enum(TRACE_EVENT_TYPES),
  span_id: z.string().nullable().optional(),
  parent_span_id: z.string().nullable().optional(),
  payload: z.record(z.string(), z.unknown()),
  snapshot_sha256: z.string().regex(SHA256_PATTERN, "the snapshot hash must be 64 lowercase hexadecimal characters").optional(),
  mode: z.enum(TRACE_MODES).optional(),
});

/** The schema of one claim, transcribed from `public-investigation-result.schema.json`. */
const claimSchema = z.object({
  id: z.string().min(1),
  text: z.string().min(1),
  kind: z.enum(["fact", "numeric", "policy", "inference"]),
  evidence_ids: z.array(z.string().min(1)),
});

/** The schema of one evidence, transcribed from `public-investigation-result.schema.json`. */
const evidenceSchema = z.object({
  id: z.string().min(1),
  source_type: z.enum(["sql", "ledger_api", "policy", "fx", "calc", "case"]),
  tool: z.string().min(1),
  ref: z.string().min(1),
  content: z.string(),
  retrieved_at: z.string().regex(DATE_TIME_PATTERN, "the retrieval moment must be an ISO 8601 date and time"),
});

/** The schema of one verdict, transcribed from `public-investigation-result.schema.json`. */
const verdictSchema = z.object({
  claim_id: z.string().min(1),
  label: z.enum(["supported", "contradicted", "not_enough_evidence"]),
  method: z.enum(["nli", "numeric", "rule", "none"]),
  evidence_ids: z.array(z.string().min(1)),
  note: z.string().nullable().optional(),
});

/** The schema of the result, transcribed from `public-investigation-result.schema.json`. */
const resultSchema = z.object({
  schema_version: z.literal(RESULT_SCHEMA_VERSION),
  run_id: z.string().min(1),
  mode: z.enum(TRACE_MODES),
  snapshot_sha256: z.string().regex(SHA256_PATTERN, "the snapshot hash must be 64 lowercase hexadecimal characters"),
  account_id: z.string().min(1).optional(),
  answer: z.string(),
  claims: z.array(claimSchema),
  evidence: z.array(evidenceSchema),
  verdicts: z.array(verdictSchema),
  verification_status: z.enum(["complete", "partial", "unavailable", "timed_out"]),
  requires_human_review: z.boolean(),
  recommended_action: z.enum([
    "none",
    "explain_to_customer",
    "issue_refund",
    "reject_refund",
    "submit_chargeback_evidence",
    "escalate_to_human",
    "ask_for_clarification",
  ]),
  missing_information: z.array(z.string()).optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

/** The schema of the bundle, transcribed from `replay-bundle.schema.json`. */
const bundleSchema = z.object({
  schema_version: z.literal(BUNDLE_SCHEMA_VERSION),
  replay_id: z.string().min(1),
  capture_kind: z.enum(CAPTURE_KINDS),
  recorded_at: z.string().regex(DATE_TIME_PATTERN, "the capture moment must be an ISO 8601 date and time"),
  scenario_id: z.string().regex(SCENARIO_ID_PATTERN, "the scenario identifier must be a letter S and two digits"),
  snapshot_sha256: z.string().regex(SHA256_PATTERN, "the snapshot hash must be 64 lowercase hexadecimal characters"),
  code_sha: z.string().regex(CODE_SHA_PATTERN, "the code hash must be 40 lowercase hexadecimal characters"),
  model_profile: z.string().min(1),
  prompt_hash: z.string().optional(),
  policy_version: z.string().optional(),
  redaction_version: z.string().optional(),
  run_result: resultSchema,
  events: z.array(traceEventSchema),
});

/** The schema of the manifest, transcribed from `BundleManifest` of `ledgerlens/replay/bundle.py`. */
const manifestSchema = z.object({
  bundle_schema_version: z.string().min(1),
  run_id: z.string().min(1),
  mode: z.enum(TRACE_MODES),
  scenario: z.string().regex(SCENARIO_ID_PATTERN, "the scenario identifier must be a letter S and two digits"),
  events: z.number().int().min(0),
  files: z.record(z.string(), z.string()),
  snapshot_sha256: z.string().regex(SHA256_PATTERN, "the snapshot hash must be 64 lowercase hexadecimal characters").optional(),
  created_at: z.string(),
  note: z.string(),
  capture_kind: z.enum(CAPTURE_KINDS).optional(),
  recorded_at: z.string().optional(),
  model_profile: z.string().optional(),
  code_sha: z.string().optional(),
  prompt_hash: z.string().optional(),
  policy_version: z.string().optional(),
  redaction_version: z.string().optional(),
});

/** The schema of one card of the catalog, transcribed from the `Scenario` entity of the specification. */
const scenarioIndexEntrySchema = z.object({
  id: z.string().regex(SCENARIO_ID_PATTERN, "the scenario identifier must be a letter S and two digits"),
  name: z.string().min(1),
  question: z.string().min(1),
  concepts: z.array(z.string()).optional(),
  data_origin: z.string().optional(),
  status: z.string().optional(),
  difficulty: z.string().optional(),
  row_ids: z
    .object({
      transaction_ids: z.array(z.string()).optional(),
      refund_ids: z.array(z.string()).optional(),
      customer_ids: z.array(z.string()).optional(),
      merchant_ids: z.array(z.string()).optional(),
    })
    .optional(),
  capture_kind: z.enum(CAPTURE_KINDS).optional(),
  bundle_path: z.string().optional(),
  ledger_sha256: z.string().optional(),
});

/**
 * The pattern of a decimal amount, as the ledger writes it.
 *
 * Why the amount is checked and not accepted as any text: the money of the interface is the decimal
 * text of the ledger, and a text that is not a decimal is a text that a reader would read as money
 * and that is not money.
 */
const DECIMAL_PATTERN = /^-?\d+(?:\.\d+)?$/;

/** The schema of one movement of the ledger, transcribed from the artifact of the recorded demo. */
const ledgerRowSchema = z.object({
  kind: z.string().min(1),
  id: z.string().min(1),
  at: z.string().regex(DATE_TIME_PATTERN, "the moment must be an ISO 8601 date and time"),
  amount: z
    .string()
    .regex(DECIMAL_PATTERN, "the amount must be the decimal text of the ledger, and never a number"),
  currency: z.string().min(1),
  status: z.string().min(1),
});

/** The schema of one read of the ledger, transcribed from the artifact of the recorded demo. */
const ledgerReadSchema = z.object({
  evidence_id: z.string(),
  seq: z.number().int().min(0),
  tool: z.string().min(1),
  sql: z.string(),
  columns: z.array(z.string()),
  row_count: z.number().int().min(0),
  truncated: z.boolean(),
  records: z.array(z.string()),
  rows: z.array(z.record(z.string(), z.string())),
});

/** The schema of one account of the ledger, transcribed from the artifact of the recorded demo. */
const ledgerAccountSchema = z.object({
  id: z.string().min(1),
  kind: z.string().min(1),
  name: z.string().min(1),
  rows: z.array(ledgerRowSchema),
  reads: z.array(ledgerReadSchema),
});

/** The schema of the artifact of the ledger, transcribed from the artifact of the recorded demo. */
const ledgerArtifactSchema = z.object({
  schema_version: z.string().min(1),
  scenario: z.string().regex(SCENARIO_ID_PATTERN, "the scenario identifier must be a letter S and two digits"),
  snapshot_sha256: z.string().regex(SHA256_PATTERN, "the snapshot hash must be 64 lowercase hexadecimal characters"),
  page_size: z.number().int().min(1, "the page holds at least one row"),
  accounts: z.array(ledgerAccountSchema),
});

/** Turns the issues of zod into readable reasons, one per line, with the path of the field that failed. */
function toReasons(error: z.ZodError, prefix: string): string[] {
  return error.issues.map((issue) => {
    const path = issue.path.length > 0 ? issue.path.join(".") : "(root)";
    return `${prefix}${path}: ${issue.message}`;
  });
}

/**
 * Validates one trace event against the published schema.
 *
 * The event is refused when its sequence number is below 1, when its snapshot hash is not 64 lowercase hexadecimal
 * characters, when its mode is not one of the three of the contract or when its type is not one of the eleven.
 */
export function validateTraceEvent(input: unknown): ValidationResult<TraceEvent> {
  const parsed = traceEventSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, reasons: toReasons(parsed.error, "event: ") };
  }
  return { ok: true, value: parsed.data as TraceEvent };
}

/**
 * Validates the list of events of a bundle.
 *
 * Every event is checked on its own, and the reasons of all of them come back together, so that a bundle with more
 * than one problem is refused with the whole list and not only with the first problem.
 */
export function validateTraceEvents(input: unknown): ValidationResult<TraceEvent[]> {
  if (!Array.isArray(input)) {
    return { ok: false, reasons: ["events: the events must be a list"] };
  }
  const reasons: string[] = [];
  const events: TraceEvent[] = [];
  input.forEach((candidate, index) => {
    const parsed = traceEventSchema.safeParse(candidate);
    if (parsed.success) {
      events.push(parsed.data as TraceEvent);
      return;
    }
    reasons.push(...toReasons(parsed.error, `events[${index}]: `));
  });
  if (reasons.length > 0) {
    return { ok: false, reasons };
  }
  return { ok: true, value: events };
}

/**
 * Validates the manifest of a bundle against the published shape.
 *
 * The manifest is what says in words what the bundle is, so the mode and the scenario identifier are checked with
 * the same rules the events are checked with.
 */
export function validateManifest(input: unknown): ValidationResult<ReplayBundleManifest> {
  const parsed = manifestSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, reasons: toReasons(parsed.error, "manifest: ") };
  }
  return { ok: true, value: parsed.data as ReplayBundleManifest };
}

/**
 * Validates the result of the recorded investigation against the published shape.
 *
 * The result carries the verdicts and the amounts, so it is the artifact the interface trusts the most and the one
 * that has to be refused the most eagerly.
 */
export function validateResult(input: unknown): ValidationResult<PublicInvestigationResult> {
  const parsed = resultSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, reasons: toReasons(parsed.error, "result: ") };
  }
  return { ok: true, value: parsed.data as PublicInvestigationResult };
}

/**
 * Validates a whole bundle against the published schema.
 *
 * The bundle of the contract holds the events and the result in one document. The static export of the site ships
 * them in separate files, and both shapes end here, one through this function and one through
 * `validateManifest` plus `validateTraceEvents`.
 */
export function validateBundle(input: unknown): ValidationResult<ReplayBundle> {
  const parsed = bundleSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, reasons: toReasons(parsed.error, "bundle: ") };
  }
  return { ok: true, value: parsed.data as ReplayBundle };
}

/** Validates one card of the scenario catalog. */
export function validateScenarioIndexEntry(input: unknown): ValidationResult<ScenarioIndexEntry> {
  const parsed = scenarioIndexEntrySchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, reasons: toReasons(parsed.error, "scenario: ") };
  }
  return { ok: true, value: parsed.data as ScenarioIndexEntry };
}

/**
 * Validates the whole catalog of scenarios.
 *
 * The reasons of every card come back together, so that a catalog with one broken card is refused with the name of
 * that card instead of with a generic message.
 */
export function validateScenarioIndex(input: unknown): ValidationResult<ScenarioIndexEntry[]> {
  if (!Array.isArray(input)) {
    return { ok: false, reasons: ["scenarios: the catalog must be a list"] };
  }
  const reasons: string[] = [];
  const entries: ScenarioIndexEntry[] = [];
  input.forEach((candidate, index) => {
    const parsed = scenarioIndexEntrySchema.safeParse(candidate);
    if (parsed.success) {
      entries.push(parsed.data as ScenarioIndexEntry);
      return;
    }
    reasons.push(...toReasons(parsed.error, `scenarios[${index}]: `));
  });
  if (reasons.length > 0) {
    return { ok: false, reasons };
  }
  return { ok: true, value: entries };
}

/**
 * Validates the artifact of the ledger of a recorded demo.
 *
 * Why the artifact is validated like every other published artifact: the interface must never render
 * an artifact it does not understand, and the money of the ledger is the decimal text of the artifact,
 * so a text that is not a decimal is refused here and never drawn as an amount.
 */
export function validateLedgerArtifact(input: unknown): ValidationResult<LedgerArtifact> {
  const parsed = ledgerArtifactSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, reasons: toReasons(parsed.error, "ledger: ") };
  }
  return { ok: true, value: parsed.data as LedgerArtifact };
}

/** Every symbol this module exports, so that a reader sees the whole surface of the validators at once. */
export const __all__ = [
  "ValidationResult",
  "validateTraceEvent",
  "validateTraceEvents",
  "validateManifest",
  "validateResult",
  "validateBundle",
  "validateScenarioIndexEntry",
  "validateScenarioIndex",
  "validateLedgerArtifact",
] as const;
