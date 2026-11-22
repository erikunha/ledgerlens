/**
 * The types of the branch of the visitor.
 *
 * Why this file exists: the browser of the sandbox has to know the shape of what the backend
 * answers before it answers anything, and it has to know it exactly. Every type below is
 * transcribed field for field from the facade of `ledgerlens/api/sandbox.py`, from the domain of the
 * branch in `ledgerlens/sandbox/` and from the published schema of the command, so a change of the
 * server shows up here as a type error instead of as a silent disagreement between the two sides.
 *
 * Why the money is a text and never a number: the domain writes an amount as a decimal text, and
 * the browser renders it as it was sent. A float would carry a rounding error that a money value
 * must not have, and the browser never calculates a value (ADR-044).
 *
 * Why three of the answers are here and not in the contract of the design package: the answer of
 * the diff, the answer of the history and the answer of the undo are paths that ADR-023 declared
 * beyond the package, and the package cannot be edited. The shapes below come from the code of the
 * domain instead.
 */

/**
 * The codes the published schema declares for the outage of the tool.
 *
 * Why the list is the enum of the schema: the schema `scenario-mutation.schema.json` declares the
 * field `error_code` with the single code `UPSTREAM_UNAVAILABLE`, and the type of the front is
 * that enum and not a plain text.
 */
type FxOutageErrorCode = "UPSTREAM_UNAVAILABLE";

/**
 * The number of seconds that the published schema declares.
 *
 * Why the union names every number of the range: the schema declares the field `elapsed_seconds`
 * as an integer between 1 and 300, and the union says exactly that, so a body that carries a
 * number outside the range is a type error of the front and not a refusal of the server.
 */
type ElapsedSeconds =
  | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20
  | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | 31 | 32 | 33 | 34 | 35 | 36 | 37 | 38
  | 39 | 40 | 41 | 42 | 43 | 44 | 45 | 46 | 47 | 48 | 49 | 50 | 51 | 52 | 53 | 54 | 55 | 56
  | 57 | 58 | 59 | 60 | 61 | 62 | 63 | 64 | 65 | 66 | 67 | 68 | 69 | 70 | 71 | 72 | 73 | 74
  | 75 | 76 | 77 | 78 | 79 | 80 | 81 | 82 | 83 | 84 | 85 | 86 | 87 | 88 | 89 | 90 | 91 | 92
  | 93 | 94 | 95 | 96 | 97 | 98 | 99 | 100 | 101 | 102 | 103 | 104 | 105 | 106 | 107 | 108
  | 109 | 110 | 111 | 112 | 113 | 114 | 115 | 116 | 117 | 118 | 119 | 120 | 121 | 122 | 123
  | 124 | 125 | 126 | 127 | 128 | 129 | 130 | 131 | 132 | 133 | 134 | 135 | 136 | 137 | 138
  | 139 | 140 | 141 | 142 | 143 | 144 | 145 | 146 | 147 | 148 | 149 | 150 | 151 | 152 | 153
  | 154 | 155 | 156 | 157 | 158 | 159 | 160 | 161 | 162 | 163 | 164 | 165 | 166 | 167 | 168
  | 169 | 170 | 171 | 172 | 173 | 174 | 175 | 176 | 177 | 178 | 179 | 180 | 181 | 182 | 183
  | 184 | 185 | 186 | 187 | 188 | 189 | 190 | 191 | 192 | 193 | 194 | 195 | 196 | 197 | 198
  | 199 | 200 | 201 | 202 | 203 | 204 | 205 | 206 | 207 | 208 | 209 | 210 | 211 | 212 | 213
  | 214 | 215 | 216 | 217 | 218 | 219 | 220 | 221 | 222 | 223 | 224 | 225 | 226 | 227 | 228
  | 229 | 230 | 231 | 232 | 233 | 234 | 235 | 236 | 237 | 238 | 239 | 240 | 241 | 242 | 243
  | 244 | 245 | 246 | 247 | 248 | 249 | 250 | 251 | 252 | 253 | 254 | 255 | 256 | 257 | 258
  | 259 | 260 | 261 | 262 | 263 | 264 | 265 | 266 | 267 | 268 | 269 | 270 | 271 | 272 | 273
  | 274 | 275 | 276 | 277 | 278 | 279 | 280 | 281 | 282 | 283 | 284 | 285 | 286 | 287 | 288
  | 289 | 290 | 291 | 292 | 293 | 294 | 295 | 296 | 297 | 298 | 299 | 300;

/**
 * The five kinds of the catalog of the mutations of the sandbox.
 *
 * From the catalog `CATALOG` of `ledgerlens/sandbox/mutation.py`. Every kind of the list is
 * enabled, because a kind is enabled only when it has a round trip test and a coherent domain
 * event (ADR-021).
 */
export type SandboxCommandKind =
  | "refund.apply_fx_adjustment"
  | "payment.simulate_duplicate"
  | "chargeback.change_deadline"
  | "tool.fx_outage"
  | "record.inject_untrusted_note";

/**
 * The catalog of the kinds, in the order of the domain.
 *
 * Why the list travels with the front: the form of the mutation offers the kinds of the sandbox and
 * not a list the interface invented, so the visitor never sends a kind the server does not know.
 */
export const MUTATION_KINDS: readonly SandboxCommandKind[] = [
  "refund.apply_fx_adjustment",
  "payment.simulate_duplicate",
  "chargeback.change_deadline",
  "tool.fx_outage",
  "record.inject_untrusted_note",
];

/**
 * The adjustment of the rate that a refund was paid with.
 *
 * From the published schema `scenario-mutation.schema.json` and from the rules of the kind in
 * `ledgerlens/sandbox/mutation.py`.
 */
export interface FxAdjustmentCommand {
  /** The kind of the command. */
  kind: "refund.apply_fx_adjustment";
  /** The data of the command, the payload the domain reads. */
  data: {
    /** The refund the adjustment is about, in the shape `R` followed by four digits. */
    refund_id: string;
    /** The rate of the adjustment, as a decimal text with at most eight decimals. */
    applied_rate: string;
    /** The moment the adjustment takes effect, as an ISO 8601 text with a time zone. */
    effective_at: string;
    /**
     * The assertion of the visitor about the currency of the record.
     *
     * Why it is optional and why the schema does not declare it: the published schema refuses any
     * other field, and the domain checks this assertion against the record before the shape of the
     * payload is checked. A currency that does not match the record is refused with its own code.
     */
    currency?: string;
  };
  /** The reason of the visitor, the note that travels with the command. */
  reason?: string;
}

/**
 * The second charge of a payment that was already charged.
 *
 * From the published schema `scenario-mutation.schema.json` and from the rules of the kind in
 * `ledgerlens/sandbox/mutation.py`.
 */
export interface DuplicatePaymentCommand {
  /** The kind of the command. */
  kind: "payment.simulate_duplicate";
  /** The data of the command, the payload the domain reads. */
  data: {
    /** The transaction that is charged again, in the shape `TX` followed by four digits. */
    transaction_id: string;
    /**
     * How many seconds passed since the first charge.
     *
     * Why the type names the range of the schema: the published schema declares an integer
     * between 1 and 300, and the type says exactly that, so a body that carries 0 or 301 is a
     * type error of the front and not a refusal of the server.
     */
    elapsed_seconds: ElapsedSeconds;
    /** The assertion of the visitor about the currency of the record. */
    currency?: string;
  };
  /** The reason of the visitor, the note that travels with the command. */
  reason?: string;
}

/**
 * The new deadline of a chargeback.
 *
 * From the published schema `scenario-mutation.schema.json` and from the rules of the kind in
 * `ledgerlens/sandbox/mutation.py`.
 */
export interface DeadlineCommand {
  /** The kind of the command. */
  kind: "chargeback.change_deadline";
  /** The data of the command, the payload the domain reads. */
  data: {
    /** The chargeback the deadline belongs to, in the shape `CB` followed by four digits. */
    chargeback_id: string;
    /** The new deadline, as a day of the calendar in the shape `YYYY-MM-DD`. */
    new_deadline: string;
    /** The assertion of the visitor about the currency of the record. */
    currency?: string;
  };
  /** The reason of the visitor, the note that travels with the command. */
  reason?: string;
}

/**
 * The outage of the tool of the rate of the branch.
 *
 * From the published schema `scenario-mutation.schema.json` and from the rules of the kind in
 * `ledgerlens/sandbox/mutation.py`.
 */
export interface FxOutageCommand {
  /** The kind of the command. */
  kind: "tool.fx_outage";
  /** The data of the command, the payload the domain reads. */
  data: {
    /** Whether the tool goes down or comes back. */
    enabled: boolean;
    /**
     * The error code the tool answers with while it is down.
     *
     * Why the type is the literal of the schema: the published schema declares the enum with one
     * code, `UPSTREAM_UNAVAILABLE`, and a plain text would let the front build a body the
     * contract does not declare.
     */
    error_code: FxOutageErrorCode;
  };
  /** The reason of the visitor, the note that travels with the command. */
  reason?: string;
}

/**
 * The untrusted note injected on a record of the branch.
 *
 * From the published schema `scenario-mutation.schema.json` and from the rules of the kind in
 * `ledgerlens/sandbox/mutation.py`.
 */
export interface UntrustedNoteCommand {
  /** The kind of the command. */
  kind: "record.inject_untrusted_note";
  /** The data of the command, the payload the domain reads. */
  data: {
    /** The record the note is injected on. */
    record_id: string;
    /** The text of the note. */
    text: string;
  };
  /** The reason of the visitor, the note that travels with the command. */
  reason?: string;
}

/**
 * A typed command of the visitor: the kind, the payload and the reason.
 *
 * The union is the body the facade reads, field for field: the kind, the data and the optional
 * reason. The commit sends the very same body that the preview sent, so what the visitor read is
 * what the server received (ADR-044).
 */
export type SandboxCommand =
  | FxAdjustmentCommand
  | DuplicatePaymentCommand
  | DeadlineCommand
  | FxOutageCommand
  | UntrustedNoteCommand;

/**
 * The branch of the visitor, the resource `Sandbox` of the contract.
 *
 * From the resource `Sandbox` of `docs/v3/contracts/openapi.yaml` and from the answer of the
 * facade in `ledgerlens/api/sandbox.py`. The resource has no field for the canonical hash of the
 * branch and none for its state, and those two travel in the headers of the answer.
 */
export interface SandboxResource {
  /** The identifier of the branch, the prefix `sb_` and twenty four hexadecimal characters. */
  id: string;
  /** The identifier of the published snapshot the branch was forked from. */
  base_snapshot_id: string;
  /** The hash of the published snapshot the branch was forked from. */
  snapshot_sha256: string;
  /** The revision the branch is at. */
  revision: number;
  /** The moment the branch dies, as an ISO 8601 text. */
  expires_at: string;
}

/**
 * The state of the branch, the answer of `GET /v1/sandboxes/{sandbox_id}`.
 *
 * Why the answer carries the two headers of the branch: the resource `Sandbox` of the contract has
 * no field for the canonical hash of the branch and none for its state, so the two travel in the
 * headers `X-LedgerLens-Branch-Hash` and `X-LedgerLens-Branch-State` (ADR-044).
 */
export interface SandboxStatusAnswer extends SandboxResource {
  /** The current canonical hash of the branch, read from the header of the answer. */
  branchHash: string | null;
  /**
   * The state of the branch, read from the header of the answer.
   *
   * Why it is a text and not a closed list: the client carries the text of the server as it is, and
   * the domain writes `active` and `expired` today.
   */
  branchState: string | null;
}

/**
 * The answer of the fork of the branch.
 *
 * Why the answer says whether the branch was created: the fork answers `201` when it creates a
 * branch and `200` when the reuse rule returns the branch that already exists, and the difference
 * tells the visitor that the work of the branch is still there after a reload of the page.
 */
export interface SandboxForkAnswer extends SandboxStatusAnswer {
  /** Whether the fork created the branch (`201`) or found the one that already existed (`200`). */
  created: boolean;
}

/**
 * An amount of money as the interface reads it: a decimal text and the currency it is in.
 *
 * From the class `MoneyValue` of `ledgerlens/sandbox/mutation.py`. Why the value is a text: the
 * domain writes money as a decimal text, and the browser renders it as it was sent.
 */
export interface MoneyValue {
  /** The amount, as a decimal text. */
  value: string;
  /** The currency of the amount, as a code. */
  currency: string;
}

/**
 * One value that changed between two projections of the branch.
 *
 * From the class `DiffEntry` of `ledgerlens/sandbox/projector.py`. The values before and after are
 * texts, so the interface never reads a number and never calculates one.
 */
export interface BranchDiffEntry {
  /** The table of the row that changed. */
  record: string;
  /** The identifier of the row that changed. */
  record_id: string;
  /** The column that changed. */
  field: string;
  /** The value before the change, as a text. */
  before: string;
  /** The value after the change, as a text. */
  after: string;
  /** Whether the value is an amount of money (`monetary`) or anything else (`non_monetary`). */
  value_kind: string;
  /** The currency of the value, when the value is an amount of money. */
  currency: string | null;
}

/**
 * The verdict of the case over a state of the branch.
 *
 * From the class `Verdict` of `ledgerlens/sandbox/projector.py`. The label is one of the four
 * labels of the domain of the sandbox (`within_expected_range`, `below_expected_range`,
 * `above_expected_range` and `not_available`), and the interface renders the label as it was sent
 * and never a label of its own.
 */
export interface BranchVerdict {
  /** The label of the verdict, one of the four labels of the domain. */
  label: string;
  /** The measure the verdict was computed from. */
  measure: string;
  /** The value of the measure, as a text. */
  value: string | null;
  /** The lower bound of the measure, as a text. */
  low: string | null;
  /** The upper bound of the measure, as a text. */
  high: string | null;
  /** The note of the server about the verdict. */
  detail: string;
}

/**
 * One rule of the domain and the outcome of the rule over a state of the branch.
 *
 * From the class `InvariantResult` of `ledgerlens/sandbox/invariants.py`. A rule that does not
 * hold says its own name in the reason, so the refusal names the rule that failed.
 */
export interface BranchInvariant {
  /** The name of the rule. */
  identifier: string;
  /** What the rule says, in words. */
  description: string;
  /** Whether the rule holds over the state. */
  passed: boolean;
  /** Why the rule does not hold, empty when it holds. */
  reason: string;
}

/**
 * The answer of the preview of a mutation: what the command would do, and nothing that happened.
 *
 * From the class `MutationPreview` of `ledgerlens/sandbox/mutation.py`. The eleven fields are the
 * ones the domain writes, and the flag `valid` is the truth of the domain: it is true when every
 * invariant holds over the state the command would produce.
 */
export interface MutationPreviewBody {
  /** Whether the command would produce a state the domain accepts. */
  valid: boolean;
  /** The kind of the command that was previewed. */
  kind: string;
  /** The revision the branch is at now. */
  revision: number;
  /** The canonical hash the branch holds now. */
  current_canonical_hash: string;
  /** The canonical hash the branch would hold after the command. */
  projected_canonical_hash: string;
  /** The value before the command. */
  before: MoneyValue;
  /** The value after the command. */
  after: MoneyValue;
  /** The rows the command would write. */
  records: BranchDiffEntry[];
  /** The difference the command would make. */
  diff: BranchDiffEntry[];
  /** The rules of the domain over the state the command would produce. */
  invariants: BranchInvariant[];
  /** The verdict of the case over the state the command would produce. */
  verdict: BranchVerdict;
}

/**
 * The answer of the commit of a mutation, and the answer of the undo of the last one.
 *
 * From the class `MutationResult` of `ledgerlens/sandbox/mutation.py`. The marks of the answer
 * (`stale`, `undone`) are derived from the log of the branch, so they cannot drift away from the
 * truth of the log.
 */
export interface MutationResultBody {
  /** The identifier of the request that produced the answer. */
  command_id: string;
  /** The kind of the command that was committed. */
  kind: string;
  /** The revision the branch is at now. */
  revision: number;
  /** The canonical hash the branch holds now. */
  canonical_hash: string;
  /** The difference THIS mutation made. */
  diff: BranchDiffEntry[];
  /** The rules of the domain over the state the branch holds now. */
  invariants: BranchInvariant[];
  /** The verdict of the case over the state the branch holds now. */
  verdict: BranchVerdict;
  /** Whether the answer was stored before and the request was delivered twice. */
  replayed: boolean;
  /** Whether the answer was produced in a generation that a reset has closed. */
  stale: boolean;
  /** The hash of the original snapshot the answer was computed against. */
  stale_against: string | null;
  /** Whether the mutation this answer describes was undone afterwards. */
  undone: boolean;
  /** The identifier of the event that the request undid. */
  undone_event_uid: string | null;
}

/**
 * The answer of the diff of the branch: the difference between the published base and the state of
 * the branch as it is now.
 *
 * From the class `BranchDiff` of `ledgerlens/sandbox/branch.py`. This path is NOT in the contract
 * of the design package: ADR-023 declared it beyond the package, and the front writes against the
 * route of the code.
 */
export interface BranchDiffBody {
  /** The revision the branch is at now. */
  revision: number;
  /** The canonical hash of the published base of the branch. */
  base_canonical_hash: string;
  /** The canonical hash the branch holds now. */
  canonical_hash: string;
  /** The entries of the difference. */
  diff: BranchDiffEntry[];
  /** The rules of the domain over the current state of the branch. */
  invariants: BranchInvariant[];
  /** The verdict of the case over the current state of the branch. */
  verdict: BranchVerdict;
}

/**
 * One event of the log of the branch, with the mark that says it was undone.
 *
 * From the event the branch layer writes in `ledgerlens/sandbox/branch.py`.
 */
export interface BranchHistoryEvent {
  /** The identifier of the event. */
  event_uid: string;
  /** The type of the event. */
  event_type: string;
  /** The record the event is about. */
  aggregate_id: string;
  /** The moment the event happened, as an ISO 8601 text. */
  occurred_at: string;
  /** The payload of the event, as the domain wrote it. */
  payload: Record<string, unknown>;
  /** Whether the event was undone afterwards. */
  undone: boolean;
}

/**
 * One answer the branch remembers, with the mark of the staleness and the mark of the undo.
 *
 * From the class `RecordedAnswer` of `ledgerlens/sandbox/branch.py`.
 */
export interface BranchRecordedAnswer {
  /** The branch the answer belongs to. */
  branch_id: string;
  /** The key that named the request. */
  idempotency_key: string;
  /** The digest of the payload of the request. */
  payload_digest: string;
  /** The revision the branch was at when the answer was produced. */
  revision: number;
  /** The canonical hash the branch held when the answer was produced. */
  canonical_hash: string;
  /** The difference the request made. */
  response_diff: BranchDiffEntry[];
  /** The verdict the request produced. */
  response_verdict: BranchVerdict;
  /** The rules of the domain the request produced. */
  response_invariants: BranchInvariant[];
  /** The generation of the branch the answer was produced in. */
  generation: number;
  /** Whether the answer was produced in a generation behind the one of the branch. */
  stale: boolean;
  /** The hash of the original snapshot the answer was computed against. */
  stale_against: string | null;
  /** Whether the mutation this answer describes was undone afterwards. */
  undone: boolean;
  /** The identifier of the event that the request undid. */
  undone_event_uid: string | null;
}

/**
 * The answer of the history of the branch: the log of the branch and the answers it remembers.
 *
 * From the class `BranchHistory` of `ledgerlens/sandbox/branch.py`. This path is NOT in the
 * contract of the design package: ADR-023 declared it beyond the package.
 */
export interface BranchHistoryBody {
  /** The revision the branch is at now. */
  revision: number;
  /** The canonical hash the branch holds now. */
  canonical_hash: string;
  /** The events of the log, in the order of the log. */
  events: BranchHistoryEvent[];
  /** The answers the branch remembers. */
  answers: BranchRecordedAnswer[];
}

/**
 * The refusal of the server, the resource `Error` of the contract.
 *
 * From the resource `Error` of `docs/v3/contracts/openapi.yaml` and from the body that
 * `ledgerlens/api/sandbox.py` writes for every refusal. The four fields are always there, and the
 * interface shows the code and the message of the server and never a sentence of its own.
 */
export interface SandboxErrorBody {
  /** The code of the refusal, for instance `REVISION_CONFLICT`. */
  code: string;
  /** The message of the server, in words a visitor can read. */
  message: string;
  /** Whether the same request may work later. */
  retryable: boolean;
  /** The identifier of the request, the one the logs of the server carry. */
  request_id: string;
  /**
   * The wait of the server, in seconds, when the server wrote one.
   *
   * Why it is the text of the server: the browser never computes a wait, the same way it never
   * computes the time that is left of the expiry (ADR-047).
   */
  retryAfter?: string | null;
}

/**
 * The whole surface of the module, so a reader who opens the file sees it at once.
 */
export const __all__ = [
  "SandboxCommand",
  "FxAdjustmentCommand",
  "DuplicatePaymentCommand",
  "DeadlineCommand",
  "FxOutageCommand",
  "UntrustedNoteCommand",
  "SandboxCommandKind",
  "MUTATION_KINDS",
  "SandboxResource",
  "SandboxStatusAnswer",
  "SandboxForkAnswer",
  "MoneyValue",
  "BranchDiffEntry",
  "BranchVerdict",
  "BranchInvariant",
  "MutationPreviewBody",
  "MutationResultBody",
  "BranchDiffBody",
  "BranchHistoryEvent",
  "BranchRecordedAnswer",
  "BranchHistoryBody",
  "SandboxErrorBody",
] as const;
