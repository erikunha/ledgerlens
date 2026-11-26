/**
 * The TypeScript types of the published contracts of the design package.
 *
 * Why this file exists: the web application never invents a shape of its own. Every type below is transcribed field by
 * field from a JSON Schema file that the Python core also reads, so a change in the contract shows up here as a type
 * error instead of as a silent disagreement between the two sides.
 *
 * The comments name the schema file each type comes from. The transcription is manual on purpose: the file has to
 * stay readable and has to explain what each field means for whoever opens the replay for the first time.
 */

/** The schema version of the trace contract. From `docs/design/contracts/schemas/trace-event.schema.json`. */
export const TRACE_SCHEMA_VERSION = "1" as const;

/** The schema version of the bundle contract. From `docs/design/contracts/schemas/replay-bundle.schema.json`. */
export const BUNDLE_SCHEMA_VERSION = "1" as const;

/** The schema version of the result contract. From `docs/design/contracts/schemas/public-investigation-result.schema.json`. */
export const RESULT_SCHEMA_VERSION = "1" as const;

/**
 * The eleven event types of the trace contract.
 * From `docs/design/contracts/schemas/trace-event.schema.json`, property `event_type`.
 */
export const TRACE_EVENT_TYPES = [
  "run.started",
  "plan.created",
  "span.started",
  "span.ended",
  "evidence.added",
  "claim.verdict",
  "run.status",
  "run.completed",
  "run.failed",
  "run.cancelled",
  "heartbeat",
] as const;

/** One of the eleven event types of the contract. */
export type TraceEventType = (typeof TRACE_EVENT_TYPES)[number];

/**
 * The three modes of the contract.
 * From `docs/design/contracts/schemas/trace-event.schema.json`, property `mode`.
 */
export const TRACE_MODES = ["recorded_replay", "deterministic_sandbox", "live_agent"] as const;

/** One of the three modes of the contract. */
export type TraceMode = (typeof TRACE_MODES)[number];

/**
 * The two capture kinds of the bundle contract.
 * From `docs/design/contracts/schemas/replay-bundle.schema.json`, property `capture_kind`.
 */
export const CAPTURE_KINDS = ["real_model_recorded", "scripted_fixture"] as const;

/** One of the two capture kinds of the bundle contract. */
export type CaptureKind = (typeof CAPTURE_KINDS)[number];

/**
 * One observable step of a recorded execution.
 * From `docs/design/contracts/schemas/trace-event.schema.json`, title `TraceEvent`.
 *
 * The optional fields are optional in the schema: the Python writer emits `span_id`, `parent_span_id` and `mode` on
 * every event, but a bundle written by an older tool may leave them out, and the reader has to cope with that.
 */
export interface TraceEvent {
  /** Always `"1"`. */
  schema_version: typeof TRACE_SCHEMA_VERSION;
  /** The identifier of the run the event belongs to. */
  run_id: string;
  /** The monotonic sequence number, starting at 1. */
  seq: number;
  /** The moment of the event, in ISO 8601 with a time zone. */
  at: string;
  /** One of the eleven event types of the contract. */
  event_type: TraceEventType;
  /** The span the event belongs to, or `null` when the event has no span. */
  span_id?: string | null;
  /** The parent of the span, or `null` for a root span. */
  parent_span_id?: string | null;
  /** The payload of the event. Its shape depends on the event type and is never re-interpreted here. */
  payload: Record<string, unknown>;
  /** The hash of the dataset snapshot the event was recorded against, in 64 lowercase hexadecimal characters. */
  snapshot_sha256?: string;
  /** The mode the recorded execution was in. */
  mode?: TraceMode;
}

/**
 * One statement of the answer, with the evidence it cites.
 * From `docs/design/contracts/schemas/public-investigation-result.schema.json`, property `claims`.
 */
export interface PublicClaim {
  /** The canonical identifier of the claim. */
  id: string;
  /** The text of the claim, as the Python core wrote it. */
  text: string;
  /** The kind of the claim. */
  kind: "fact" | "numeric" | "policy" | "inference";
  /** The identifiers of the evidence the claim cites. */
  evidence_ids: string[];
}

/**
 * One source that supports a claim.
 * From `docs/design/contracts/schemas/public-investigation-result.schema.json`, property `evidence`.
 */
export interface PublicEvidence {
  /** The canonical identifier of the evidence. */
  id: string;
  /** The kind of the source. */
  source_type: "sql" | "ledger_api" | "policy" | "fx" | "calc" | "case";
  /** The tool that produced the evidence. */
  tool: string;
  /** The origin reference of the source. */
  ref: string;
  /** The sanitized content of the source. */
  content: string;
  /** The moment the source was retrieved, in ISO 8601 with a time zone. */
  retrieved_at: string;
}

/**
 * The verification decision about one claim.
 * From `docs/design/contracts/schemas/public-investigation-result.schema.json`, property `verdicts`.
 */
export interface PublicVerdict {
  /** The claim the decision is about. */
  claim_id: string;
  /** The decision itself. */
  label: "supported" | "contradicted" | "not_enough_evidence";
  /** The method that produced the decision. */
  method: "nli" | "numeric" | "rule" | "none";
  /** The identifiers of the evidence the decision used. */
  evidence_ids: string[];
  /** The note of the verifier, when there is one. */
  note?: string | null;
}

/**
 * The result of the recorded investigation.
 * From `docs/design/contracts/schemas/public-investigation-result.schema.json`, title `PublicInvestigationResult`.
 */
export interface PublicInvestigationResult {
  /** Always `"1"`. */
  schema_version: typeof RESULT_SCHEMA_VERSION;
  /** The identifier of the run the result belongs to. */
  run_id: string;
  /** The mode of the run. */
  mode: TraceMode;
  /** The hash of the dataset snapshot the run read. */
  snapshot_sha256: string;
  /** The account the investigation was about. */
  account_id?: string;
  /** The final answer of the agent. */
  answer: string;
  /** The claims of the answer, with the evidence they cite. */
  claims: PublicClaim[];
  /** The evidence the claims cite. */
  evidence: PublicEvidence[];
  /** The verdicts the verifier produced. */
  verdicts: PublicVerdict[];
  /** Whether the verification ran to the end. */
  verification_status: "complete" | "partial" | "unavailable" | "timed_out";
  /** Whether a human has to look at the case. */
  requires_human_review: boolean;
  /** The action the result recommends. */
  recommended_action:
    | "none"
    | "explain_to_customer"
    | "issue_refund"
    | "reject_refund"
    | "submit_chargeback_evidence"
    | "escalate_to_human"
    | "ask_for_clarification";
  /** What the run could not find out. */
  missing_information?: string[];
  /** The extra metadata of the run. */
  metadata?: Record<string, unknown>;
}

/**
 * The whole recorded bundle, as one document.
 * From `docs/design/contracts/schemas/replay-bundle.schema.json`, title `RecordedReplayBundle`.
 */
export interface ReplayBundle {
  /** Always `"1"`. */
  schema_version: typeof BUNDLE_SCHEMA_VERSION;
  /** The identifier of the bundle. */
  replay_id: string;
  /** How the execution was captured. */
  capture_kind: CaptureKind;
  /** The moment of the capture, in ISO 8601 with a time zone. */
  recorded_at: string;
  /** The identifier of the scenario, in the shape `S` followed by two digits. */
  scenario_id: string;
  /** The hash of the dataset snapshot the run read. */
  snapshot_sha256: string;
  /** The hash of the code commit that produced the run. */
  code_sha: string;
  /** The profile of the model the run used. */
  model_profile: string;
  /** The hash of the prompt, when the capture recorded one. */
  prompt_hash?: string;
  /** The version of the policy the run read. */
  policy_version?: string;
  /** The version of the redaction the capture went through. */
  redaction_version?: string;
  /** The result of the recorded investigation. */
  run_result: PublicInvestigationResult;
  /** The events of the recorded execution, in sequence order. */
  events: TraceEvent[];
}

/**
 * The manifest that says what a bundle is.
 *
 * From the `BundleManifest` of `ledgerlens/replay/bundle.py`, which writes `manifest.json` next to `events.jsonl`.
 * The optional fields at the end are the extras a static export adds so that the site can show the provenance of the
 * artifact without opening the whole bundle.
 */
export interface ReplayBundleManifest {
  /** The version of the manifest contract. */
  bundle_schema_version: string;
  /** The identifier of the run the bundle holds. */
  run_id: string;
  /** The mode of the recorded execution. */
  mode: TraceMode;
  /** The identifier of the scenario, in the shape `S` followed by two digits. */
  scenario: string;
  /** The number of events the bundle holds. */
  events: number;
  /** The digest of each file of the bundle, by file name. */
  files: Record<string, string>;
  /** The hash of the dataset snapshot the run read. */
  snapshot_sha256?: string;
  /** The moment the bundle was written, in ISO 8601 with a time zone. */
  created_at: string;
  /** The note that says in words what the bundle is. */
  note: string;
  /** How the execution was captured, when the export declares it. */
  capture_kind?: CaptureKind;
  /** The moment of the capture, when the export declares it. */
  recorded_at?: string;
  /** The profile of the model the run used, when the export declares it. */
  model_profile?: string;
  /**
   * The model that ran each task of the run, when the run used more than one.
   *
   * Why the field is optional: a run with one model in every slot declares no map, and a manifest that
   * declares no map says nothing about a division of work that did not happen (ADR-078).
   */
  model_profiles?: Record<string, string>;
  /** The hash of the code commit, when the export declares it. */
  code_sha?: string;
  /** The hash of the prompt, when the export declares it. */
  prompt_hash?: string;
  /** The version of the policy, when the export declares it. */
  policy_version?: string;
  /** The version of the redaction, when the export declares it. */
  redaction_version?: string;
}

/**
 * The statuses a scenario card can carry.
 * From the `Scenario` entity of `specs/001-r1-public-replay/spec.md`. The union keeps the known labels and still
 * accepts a label a later export adds, so an unknown label is displayed as it is instead of breaking the catalog.
 */
export const SCENARIO_STATUSES = ["Editable", "Live-compatible", "Recorded"] as const;

/** One of the known scenario statuses. */
export type KnownScenarioStatus = (typeof SCENARIO_STATUSES)[number];

/** A scenario status, known or published by a later export. */
export type ScenarioStatus = KnownScenarioStatus | (string & {});

/**
 * One card of the scenario catalog.
 * From the `Scenario` entity of `specs/001-r1-public-replay/spec.md`. The contract of the design package has no JSON
 * Schema for the catalog yet, so the fields follow the entity of the specification and the export owns the values.
 */
export interface ScenarioIndexEntry {
  /** The identifier of the scenario, in the shape `S` followed by two digits. */
  id: string;
  /** The short name of the scenario. */
  name: string;
  /** The question the scenario asks. */
  question: string;
  /** The concepts the scenario demonstrates. */
  concepts?: string[];
  /** Where the data of the scenario comes from. */
  data_origin?: string;
  /** The status label of the card, read exactly as it is. */
  status?: ScenarioStatus;
  /** The difficulty of the scenario. */
  difficulty?: string;
  /** The identifiers of the rows the scenario involves. */
  row_ids?: {
    transaction_ids?: string[];
    refund_ids?: string[];
    customer_ids?: string[];
    merchant_ids?: string[];
  };
  /** How the scenario was captured, when the export declares it. */
  capture_kind?: CaptureKind;
  /** The path of the bundle of the scenario, relative to the artifact root. */
  bundle_path?: string;
  /**
   * The digest of the bundle of the scenario, when the export declares it.
   *
   * Why the field is optional: the digest is the name of the capture, and a card of a scenario
   * whose bundle was never sealed carries none.
   */
  bundle_digest?: string;
  /**
   * The digest of the file of the ledger of the scenario, when the export published one.
   *
   * Why the field is optional: a scenario whose recording read no ledger publishes no file of the
   * ledger, and a card that carries no digest is a card that publishes no ledger.
   */
  ledger_sha256?: string;
  /**
   * The model that ran each task of the run, when the run used more than one.
   *
   * Why the field is optional: a run with one model in every slot publishes no division of work, and
   * a card that carries no map is a card that says nothing about it (ADR-078).
   */
  model_profiles?: Record<string, string>;
}

/**
 * One movement of the ledger of an account.
 *
 * From the artifact of the ledger of the recorded demo, `site/replay/<scenario>/ledger.json`. The
 * six fields are the six fields of `_ledger_items` of `ledgerlens/sandbox/branch.py`, so that one
 * table draws the ledger of the recorded demo and the ledger of the branch of the sandbox.
 *
 * Why the amount is a string: the amount is the decimal text the ledger wrote, and a binary float
 * of a financial amount is a different amount. The browser never turns it into a number.
 */
export interface LedgerRow {
  /** The kind of the movement: `transaction`, `refund` or `chargeback`. */
  kind: string;
  /** The identifier of the movement, as the ledger wrote it. */
  id: string;
  /** The moment of the movement, in ISO 8601 with a time zone. */
  at: string;
  /** The amount of the movement, as the decimal text of the ledger. */
  amount: string;
  /** The currency of the amount, as the ledger wrote it. */
  currency: string;
  /** The status of the movement, as the ledger wrote it. */
  status: string;
}

/**
 * One row a read of the ledger returned.
 *
 * Why the shape is open: the columns of a read are the columns the recording declared, so the
 * values are named with them and the type carries the names as strings. A rate is not money and
 * carries no currency, and the text of the value is never changed.
 */
export type LedgerReadRow = Readonly<Record<string, string>>;

/**
 * One read of the ledger that the recording made.
 *
 * From the artifact of the ledger of the recorded demo. One read per call of the tool
 * `query_ledger` that the recording made.
 */
export interface LedgerRead {
  /** The citation of the evidence of the read, as the recording wrote it. */
  evidence_id: string;
  /** The sequence number of the event that closed the read. */
  seq: number;
  /** The name of the tool that made the read. */
  tool: string;
  /** The statement the read ran. */
  sql: string;
  /** The names of the columns the read asked for. */
  columns: string[];
  /** The number of rows the read returned. */
  row_count: number;
  /** Whether the result of the read was cut. */
  truncated: boolean;
  /** The identifiers of the records the statement named. */
  records: string[];
  /** The rows the read returned, named with the columns of the read. */
  rows: LedgerReadRow[];
}

/**
 * One account of the ledger of a recording.
 *
 * From the artifact of the ledger of the recorded demo. The account carries its movements and the
 * reads of the recording that named them.
 */
export interface LedgerAccount {
  /** The identifier of the account, as the ledger wrote it. */
  id: string;
  /** The kind of the account, as the ledger wrote it. */
  kind: string;
  /** The name of the account, as the ledger wrote it. */
  name: string;
  /** The movements of the account, oldest first. */
  rows: LedgerRow[];
  /** The reads of the recording that named the movements of the account. */
  reads: LedgerRead[];
}

/**
 * The artifact of the ledger of a recorded demo.
 *
 * From `site/replay/<scenario>/ledger.json`, the file the export publishes beside the manifest,
 * the events and the provenance of the bundle. The artifact is a SIDECAR: a bundle without it is
 * still a bundle, and the reader says in words what the site did not publish.
 */
export interface LedgerArtifact {
  /** The version of the shape of the artifact. */
  schema_version: string;
  /** The identifier of the scenario the artifact belongs to. */
  scenario: string;
  /** The digest of the ledger the recording read, as the manifest of the bundle declares it. */
  snapshot_sha256: string;
  /** The number of rows of a page of the table. */
  page_size: number;
  /** The accounts the artifact publishes, even when it publishes one. */
  accounts: LedgerAccount[];
}

/**
 * What the interface shows about where a bundle came from.
 * From the provenance requirements of `specs/001-r1-public-replay/spec.md` (FR-009) and from the fields the bundle
 * contract and the manifest carry. Every field is optional because a field the artifact does not carry is rendered as
 * unavailable, never invented.
 */
export interface Provenance {
  /** The mode the recorded execution was in. */
  mode?: TraceMode;
  /** How the execution was captured. */
  capture_kind?: CaptureKind;
  /** The moment of the capture. */
  recorded_at?: string;
  /** The profile of the model the run used. */
  model_profile?: string;
  /** The hash of the code commit that produced the run. */
  code_sha?: string;
  /** The hash of the dataset snapshot the run read. */
  snapshot_sha256?: string;
  /** The hash of the prompt. */
  prompt_hash?: string;
  /** The version of the policy the run read. */
  policy_version?: string;
  /** The version of the redaction the capture went through. */
  redaction_version?: string;
  /** The digest of each file of the bundle, by file name. */
  files?: Record<string, string>;
  /** The moment the bundle was written. */
  created_at?: string;
  /** The note that says in words what the bundle is. */
  note?: string;
}

/** Every symbol this module exports, so that a reader sees the whole surface of the types at once. */
export const __all__ = [
  "TRACE_SCHEMA_VERSION",
  "BUNDLE_SCHEMA_VERSION",
  "RESULT_SCHEMA_VERSION",
  "TRACE_EVENT_TYPES",
  "TraceEventType",
  "TRACE_MODES",
  "TraceMode",
  "CAPTURE_KINDS",
  "CaptureKind",
  "TraceEvent",
  "PublicClaim",
  "PublicEvidence",
  "PublicVerdict",
  "PublicInvestigationResult",
  "ReplayBundle",
  "ReplayBundleManifest",
  "SCENARIO_STATUSES",
  "KnownScenarioStatus",
  "ScenarioStatus",
  "ScenarioIndexEntry",
  "LedgerRow",
  "LedgerReadRow",
  "LedgerRead",
  "LedgerAccount",
  "LedgerArtifact",
  "Provenance",
] as const;
