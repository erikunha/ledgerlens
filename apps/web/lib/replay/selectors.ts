/**
 * The projections of the recorded run into the facts the interface shows.
 *
 * Why this file exists: the published recording of the scenario `S01` carries only the events of the spans, and the
 * events of the spans carry the evidence, the verdicts, the amounts and the answer inside the outputs of the spans.
 * There is no `evidence.added` event, no `claim.verdict` event and no `run.completed` event to read. The interface
 * therefore projects those facts out of what the recording does carry.
 *
 * Every function here is a projection and never a decision. A selector reads what the artifact published and returns
 * it. It never fills a gap, never repairs a value and never infers a fact the recording does not carry. Every read of
 * an output is guarded, because the outputs are typed as `unknown` and a bundle written by another tool may carry
 * anything there.
 */

import type { TraceEvent } from "@/lib/api/schemas";
import type { SpanState, ToolCallState } from "@/lib/replay/reducer";

/** One span of the recorded execution, with the spans it opened nested under it. */
export interface TraceTreeNode {
  /** The identifier of the span. */
  readonly spanId: string;
  /** The identifier of the parent span, when the recording carried one. */
  readonly parentSpanId: string | null;
  /** The name of the span, as the capture recorded it. */
  readonly name: string | null;
  /** The kind of the span, for instance `tool`, `chain` or `verifier`. */
  readonly runType: string | null;
  /** The distance of the node from the root of its tree. */
  readonly depth: number;
  /** The sequence number of the event that opened the span. */
  readonly startedSeq: number | null;
  /** The sequence number of the event that closed the span. */
  readonly endedSeq: number | null;
  /** The spans the span opened. */
  readonly children: readonly TraceTreeNode[];
}

/** One row of the timeline: one event of the recording, in the order of the recording. */
export interface TimelineRow {
  /** The sequence number of the event. */
  readonly seq: number;
  /** The type of the event, as the contract names it. */
  readonly eventType: string;
  /** The label of the row: the name of the span, or the type of the event. */
  readonly label: string;
  /** The moment of the event, in ISO 8601. */
  readonly at: string;
  /** The duration the capture measured, in milliseconds. */
  readonly latencyMs: number | null;
  /** The error the event carried, when it carried one. */
  readonly error: string | null;
  /** Whether the event belongs to a tool call. */
  readonly isTool: boolean;
}

/** One piece of evidence the run collected, as the outputs of the tools reported it. */
export interface EvidenceSummary {
  /** The identifier of the evidence, the one the result of the run uses. */
  readonly evidenceId: string;
  /** The tool that produced the evidence. */
  readonly tool: string;
  /** The content of the source, as the tool published it. */
  readonly content: string | null;
  /** The reference of the origin of the source, when the tool published one. */
  readonly ref: string | null;
  /** The sequence number of the event that closed the tool call. */
  readonly seq: number;
}

/** The decision of the verifier about one claim, as the output of the verifier span carries it. */
export interface VerdictSummary {
  /** The identifier of the claim the decision is about. */
  readonly claimId: string;
  /** The decision itself, as the verifier wrote it. */
  readonly label: string | null;
  /** The method that produced the decision. */
  readonly method: string | null;
  /** The note of the verifier, when there was one. */
  readonly note: string | null;
  /** The identifiers of the evidence the decision cited. */
  readonly evidenceIds: readonly string[];
  /** The sequence number of the event that closed the span of the verifier. */
  readonly seq: number;
}

/**
 * The unit of a value of the breakdown of the answer.
 *
 * Why the unit exists: a value of the result of the calculation is not always money. A percentage is not an amount: it
 * carries no currency and the interface writes it with the symbol of the percentage. The unit is the fact that tells
 * the panel of the amounts how to write each value, so that a percentage is never published with the currency of the
 * run.
 */
export type AmountUnit = "money" | "percentage";

/** One amount of the breakdown, with the decimal text exactly as the recording wrote it. */
export interface AmountSummary {
  /** The name of the amount, for instance `charge` or `markup`. */
  readonly name: string;
  /** The amount, as the decimal text the recording carries. */
  readonly amount: string;
  /** The currency of the amount, when the recording read one with it. */
  readonly currency: string | null;
  /** The unit of the value: money, or a percentage that never carries a currency. */
  readonly unit: AmountUnit;
  /** The sequence number of the event that closed the tool call. */
  readonly seq: number;
}

/** The answer of the run, as the output of the last investigate span carries it. */
export interface FinalAnswer {
  /** The text of the answer. */
  readonly answer: string;
  /** The action the run recommends, when it recommends one. */
  readonly recommendedAction: string | null;
  /** Whether the run says a human has to look at the case. */
  readonly requiresHumanReview: boolean | null;
  /** The summary of the run, when the run wrote one. */
  readonly summary: string | null;
  /** The sequence number of the event that closed the span of the answer. */
  readonly seq: number;
}

/** Reads a value as a record, when it is one, and returns null otherwise. */
function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

/** Reads a non empty string out of a record, whatever it holds. */
function readString(record: Record<string, unknown> | null, key: string): string | null {
  if (!record) {
    return null;
  }
  const value = record[key];
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

/** Reads a finite number out of a record, whatever it holds. */
function readNumber(record: Record<string, unknown> | null, key: string): number | null {
  if (!record) {
    return null;
  }
  const value = record[key];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  return value;
}

/** Reads a boolean out of a record, whatever it holds. */
function readBoolean(record: Record<string, unknown> | null, key: string): boolean | null {
  if (!record) {
    return null;
  }
  const value = record[key];
  return typeof value === "boolean" ? value : null;
}

/** Reads a list of strings out of a record, dropping whatever is not a string. */
function readStringList(record: Record<string, unknown> | null, key: string): string[] {
  if (!record) {
    return [];
  }
  const value = record[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string");
}

/** The sequence number a span is closed at, falling back to the one it was opened at. */
function spanSeq(span: SpanState): number {
  return span.endedSeq ?? span.startedSeq ?? 0;
}

/**
 * Nests the spans of the recording into the trees of the run.
 *
 * A span whose parent is not in the recording is a root, and the depth of a node is its distance from that root. The
 * order of the roots and of the children is the order of the recording, so the tree is always the same tree.
 */
export function buildTraceTree(spans: readonly SpanState[]): TraceTreeNode[] {
  const byId = new Map<string, SpanState>();
  for (const span of spans) {
    // The reducer keeps one span per identifier, but a bundle read from a file could repeat one. The first one wins,
    // because the first one is the one the recording opened.
    if (!byId.has(span.spanId)) {
      byId.set(span.spanId, span);
    }
  }

  const childrenOf = new Map<string, SpanState[]>();
  const roots: SpanState[] = [];
  for (const span of byId.values()) {
    const parent = span.parentSpanId;
    if (parent !== null && parent !== undefined && parent !== span.spanId && byId.has(parent)) {
      const siblings = childrenOf.get(parent);
      if (siblings) {
        siblings.push(span);
      } else {
        childrenOf.set(parent, [span]);
      }
      continue;
    }
    roots.push(span);
  }

  const visited = new Set<string>();

  const build = (span: SpanState, depth: number, path: ReadonlySet<string>): TraceTreeNode => {
    visited.add(span.spanId);
    const children: TraceTreeNode[] = [];
    for (const child of childrenOf.get(span.spanId) ?? []) {
      // A recording whose parents form a loop would otherwise nest forever, so a child already on the path is left
      // out of the tree instead of being rendered twice.
      if (path.has(child.spanId)) {
        continue;
      }
      children.push(build(child, depth + 1, new Set([...path, child.spanId])));
    }
    return {
      spanId: span.spanId,
      parentSpanId: span.parentSpanId ?? null,
      name: span.name ?? null,
      runType: span.runType ?? null,
      depth,
      startedSeq: span.startedSeq ?? null,
      endedSeq: span.endedSeq ?? null,
      children,
    };
  };

  const trees = roots.map((root) => build(root, 0, new Set([root.spanId])));

  // A span that no root reaches would never be shown, so it is added as a root of its own. That happens only when
  // the recording declares a loop of parents, which no valid bundle does.
  for (const span of byId.values()) {
    if (!visited.has(span.spanId)) {
      trees.push(build(span, 0, new Set([span.spanId])));
    }
  }
  return trees;
}

/**
 * Builds one row per event of the recording, in the order of the recording.
 *
 * The rows include the events the interface does not know, so that the number of the rows is the number of the events
 * of the bundle and no event ever disappears silently.
 */
export function buildTimeline(events: readonly TraceEvent[]): TimelineRow[] {
  return events.map((event) => {
    const payload = asRecord(event.payload);
    const name = readString(payload, "name");
    const latencyMs = readNumber(payload, "latency_ms") ?? readNumber(payload, "duration_ms");
    return {
      seq: event.seq,
      eventType: event.event_type,
      label: name ?? event.event_type,
      at: typeof event.at === "string" ? event.at : "",
      latencyMs,
      error: readString(payload, "error"),
      isTool: readString(payload, "run_type") === "tool",
    };
  });
}

/**
 * One step of the run: one call of a tool that the recording made.
 *
 * Why a step of the run is a call of a tool: the run of LedgerLens is the calls its tools made, and the
 * recording already carries them. The step is a fact of the artifact and not a sentence of the interface.
 */
export interface RunStep {
  /** The number of the step, counted from one. */
  readonly number: number;
  /** The name of the tool, as the capture recorded it. */
  readonly name: string;
  /** The sequence number of the event that opened the call. */
  readonly startedSeq: number;
  /** The sequence number of the event that closed the call, null while it is open. */
  readonly endedSeq: number | null;
  /** The status the call ended with, when it has ended. */
  readonly status: string | null;
}

/**
 * Builds the steps of the run out of the spans of the recording.
 *
 * Why only the spans of the kind `tool`: the steps of the run are the calls of the tools, and the spans of
 * the other kinds are the life of the run and not steps of it. Why the order is the order of the reducer:
 * the reducer appends a span when the recording opens it, so the order of the array is the order of the
 * calls.
 *
 * The projection never invents a step and never repairs one: a span of the kind `tool` that carries no
 * name is shown with the same name the table of the calls gives it, and a span that the capture closed
 * without ever opening it is dated by the event that closed it, because that is the only moment the
 * capture published about it.
 */
export function buildRunSteps(spans: readonly SpanState[]): RunStep[] {
  const steps: RunStep[] = [];

  for (const span of spans) {
    if (span.runType !== "tool") {
      continue;
    }
    steps.push({
      number: steps.length + 1,
      name: span.name ?? "tool",
      startedSeq: span.startedSeq ?? span.endedSeq ?? 0,
      endedSeq: span.endedSeq ?? null,
      status: span.status ?? null,
    });
  }

  return steps;
}

/**
 * Finds the step the recording stands at.
 *
 * Why the last step that was opened: the recording stands at the call it is inside, and the calls are
 * opened one after the other. The step of a recording that stands before its first call is null, because
 * there is no call to be at yet.
 */
export function findCurrentStep(steps: readonly RunStep[], lastSeq: number | null): RunStep | null {
  if (lastSeq === null) {
    return null;
  }

  let current: RunStep | null = null;
  for (const step of steps) {
    // the steps are in the order they were opened, so the first step that was not opened yet ends the walk
    if (step.startedSeq > lastSeq) {
      break;
    }
    current = step;
  }
  return current;
}

/** Finds the chunk of a policy search that an evidence identifier names. */
function findPolicyChunk(results: unknown, evidenceId: string): Record<string, unknown> | null {
  if (!Array.isArray(results)) {
    return null;
  }
  // The identifier of a policy piece carries the identifier of the chunk after the prefix of the kind.
  const named = evidenceId.includes(":") ? evidenceId.slice(evidenceId.indexOf(":") + 1) : evidenceId;
  for (const result of results) {
    const record = asRecord(result);
    if (!record) {
      continue;
    }
    const chunkId = readString(record, "chunk_id");
    if (chunkId === evidenceId || chunkId === named) {
      return record;
    }
  }
  return null;
}

/**
 * Reads the content of one piece of evidence out of the data of the tool that produced it.
 *
 * The content is the text of the source as the tool published it. A tool the projection does not know is rendered as
 * the JSON of its data, which shows what the tool returned without inventing a sentence around it.
 */
function readEvidenceContent(tool: string, evidenceId: string, data: Record<string, unknown> | null): string | null {
  if (!data) {
    return null;
  }
  switch (tool) {
    case "query_ledger": {
      return readString(data, "sql");
    }
    case "search_policies": {
      const chunk = findPolicyChunk(data.results, evidenceId);
      return chunk ? readString(chunk, "text") : null;
    }
    case "get_reference_fx": {
      return readString(data, "note") ?? readString(data, "rate");
    }
    case "calculate": {
      return readString(data, "formula");
    }
    default: {
      return JSON.stringify(data);
    }
  }
}

/**
 * Reads the reference of the origin of one piece of evidence.
 *
 * A tool that publishes a reference of its own is believed, and a tool that publishes none falls back to the
 * identifier of the evidence, which is the only reference the recording then carries.
 */
function readEvidenceRef(tool: string, evidenceId: string, data: Record<string, unknown> | null): string | null {
  if (!data) {
    return evidenceId;
  }
  switch (tool) {
    case "query_ledger": {
      return evidenceId;
    }
    case "search_policies": {
      const chunk = findPolicyChunk(data.results, evidenceId);
      const chunkId = chunk ? readString(chunk, "chunk_id") : null;
      return chunkId ?? evidenceId;
    }
    case "get_reference_fx": {
      const from = readString(data, "from_currency");
      const to = readString(data, "to_currency");
      const date = readString(data, "rate_date");
      return from && to && date ? `${from}->${to}@${date}` : evidenceId;
    }
    case "calculate": {
      return readString(data, "operation") ?? evidenceId;
    }
    default: {
      return evidenceId;
    }
  }
}

/**
 * Collects the evidence the run gathered, out of the outputs of the tool calls.
 *
 * The published recording carries no `evidence.added` event, so the identifiers and the content of the evidence are
 * read out of the outputs of the tools. An identifier that no tool reported is not shown, because an evidence the
 * recording does not carry is not evidence.
 */
export function collectEvidence(toolCalls: readonly ToolCallState[]): EvidenceSummary[] {
  const summaries: EvidenceSummary[] = [];
  const seen = new Set<string>();

  for (const call of toolCalls) {
    const outputs = asRecord(call.outputs);
    if (!outputs) {
      continue;
    }
    const data = asRecord(outputs.data);
    for (const evidenceId of readStringList(outputs, "evidence_ids")) {
      // The same identifier reported twice is the same evidence, so it is shown once.
      if (seen.has(evidenceId)) {
        continue;
      }
      seen.add(evidenceId);
      summaries.push({
        evidenceId,
        tool: call.name,
        content: readEvidenceContent(call.name, evidenceId, data),
        ref: readEvidenceRef(call.name, evidenceId, data),
        seq: call.seq,
      });
    }
  }
  return summaries;
}

/**
 * Collects the verdicts of the verifier, out of the outputs of the spans of the verifier.
 *
 * Only a span whose kind is `verifier` and whose output carries a claim identifier is a verdict. The label, the
 * method, the note and the cited identifiers are read from that output, and a claim the recording does not carry is
 * never shown as supported.
 */
export function collectVerdicts(spans: readonly SpanState[]): VerdictSummary[] {
  const verdicts: VerdictSummary[] = [];

  for (const span of spans) {
    if (span.runType !== "verifier") {
      continue;
    }
    const outputs = asRecord(span.outputs);
    if (!outputs) {
      continue;
    }
    const claimId = readString(outputs, "claim_id");
    if (claimId === null) {
      continue;
    }
    verdicts.push({
      claimId,
      label: readString(outputs, "label"),
      method: readString(outputs, "method"),
      note: readString(outputs, "note"),
      evidenceIds: readStringList(outputs, "evidence_ids"),
      seq: spanSeq(span),
    });
  }
  return verdicts;
}

/**
 * The shape of a decimal number written as text: digits, with an optional sign and an optional point.
 *
 * Why the shape is checked: the panel of the amounts shows money and percentages, and a word is neither. The check
 * is the same on both sides of the platform, where the calculator never writes a word as a number.
 */
const DECIMAL_TEXT = /^-?\d+(\.\d+)?$/;

/**
 * Reads an amount as the decimal text it is, keeping the text exactly as the recording wrote it.
 *
 * Only the text branch counts. A JSON number of money is already a binary float, so it is not a value of the domain:
 * when a recording publishes one, the amount simply does not appear in the panel of the amounts, and it never appears
 * repaired either.
 *
 * A text that is not a decimal number is not an amount either. The result of the calculation of the markup of a
 * refund carries the answer of the check as a word (`yes` or `no`), and the panel of the amounts never dresses a
 * word as money.
 */
function readDecimalText(value: unknown): string | null {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return DECIMAL_TEXT.test(trimmed) ? trimmed : null;
  }
  return null;
}

/**
 * The words of the name of a value that declare that the value is a percentage.
 *
 * Why the words are these: the published recording names its percentage `markup_pct`, and the interface reads the name
 * of the value because the name is what the reader sees in the panel of the amounts.
 */
const PERCENTAGE_WORDS: readonly string[] = ["pct", "percent", "percentage"];

/**
 * Says whether the name of a value declares that the value is a percentage.
 *
 * A name declares a percentage when one of its words is `pct`, `percent` or `percentage`, or when it carries the symbol
 * of the percentage. Every other name is money.
 *
 * Why the name is the signal: the recording declares the unit of a value in the name of the value and in the formula
 * that produced it, and the name is the one of the two the reader sees. The projection never guesses the unit from the
 * size of the number, because a number of the same size can be money or a percentage, and the interface never
 * invents a fact the recording does not carry.
 */
function declaresPercentage(name: string): boolean {
  if (name.includes("%")) {
    return true;
  }
  const words = name.toLowerCase().split(/[^a-z0-9]+/).filter((word) => word !== "");
  return words.some((word) => PERCENTAGE_WORDS.includes(word));
}

/**
 * Collects the amounts of the breakdown, out of the result of the calculation.
 *
 * The amounts are read out of the result of the `calculate` tool, and out of no other tool, because the breakdown of
 * the gap is what that tool produced. The amount is the decimal text of the recording, kept exactly as it was written.
 * The currency is left empty on purpose: the currency of the run is another fact, read by `collectCurrency`, and the
 * projection never attaches a currency to an amount it did not read with it.
 *
 * The unit is read out of the name of the value, because the name is where the recording declares it. A percentage is
 * never money, so it never carries the currency of the run, and the panel of the amounts writes it with the symbol of
 * the percentage.
 */
export function collectAmounts(toolCalls: readonly ToolCallState[]): AmountSummary[] {
  const amounts: AmountSummary[] = [];

  for (const call of toolCalls) {
    if (call.name !== "calculate") {
      continue;
    }
    const outputs = asRecord(call.outputs);
    const data = outputs ? asRecord(outputs.data) : null;
    const result = data ? asRecord(data.result) : null;
    if (!result) {
      continue;
    }
    for (const [name, value] of Object.entries(result)) {
      const amount = readDecimalText(value);
      if (amount === null) {
        continue;
      }
      amounts.push({
        name,
        amount,
        currency: null,
        unit: declaresPercentage(name) ? "percentage" : "money",
        seq: call.seq,
      });
    }
  }
  return amounts;
}

/**
 * Says whether the name of a call is the name of a tool that reads an exchange rate.
 *
 * A tool that reads a rate publishes the currency it converted to, and only such a tool can tell the currency of the
 * run. The name is what carries that fact, so the name is what the projection looks at.
 */
function isExchangeRateTool(name: string): boolean {
  const lowered = name.toLowerCase();
  return lowered.includes("fx") || lowered.includes("rate") || lowered.includes("exchange");
}

/**
 * Reads the currency of the run out of the output of the exchange rate tool.
 *
 * The currency is the `to_currency` of the rate the run read. The tool that reads the rate is believed first, and the
 * fallback only accepts another tool that reads a rate as well, because a tool that publishes a `to_currency` for
 * another reason does not define the currency of the run. A recording that read no currency gives `null`, because the
 * interface never assumes the currency of the run.
 */
export function collectCurrency(toolCalls: readonly ToolCallState[]): string | null {
  const readFrom = (call: ToolCallState): string | null => {
    const outputs = asRecord(call.outputs);
    const data = outputs ? asRecord(outputs.data) : null;
    return readString(data, "to_currency");
  };

  // The exchange rate tool is believed first, and any other tool that read a rate is the fallback.
  for (const call of toolCalls) {
    if (call.name === "get_reference_fx") {
      const currency = readFrom(call);
      if (currency) {
        return currency;
      }
    }
  }
  for (const call of toolCalls) {
    if (!isExchangeRateTool(call.name)) {
      continue;
    }
    const currency = readFrom(call);
    if (currency) {
      return currency;
    }
  }
  return null;
}

/**
 * Reads the answer of the run out of the output of the last investigate span.
 *
 * A recording with no investigate span gives `null`, and so does a recording whose last investigate span carries no
 * answer, because the interface never writes an answer of its own.
 */
export function findFinalAnswer(spans: readonly SpanState[]): FinalAnswer | null {
  const candidates = spans
    .filter((span) => (span.name ?? "").trim().toLowerCase() === "investigate")
    .sort((left, right) => spanSeq(right) - spanSeq(left));

  for (const span of candidates) {
    const outputs = asRecord(span.outputs);
    if (!outputs) {
      continue;
    }
    const answer = readString(outputs, "answer");
    if (answer === null) {
      continue;
    }
    return {
      answer,
      recommendedAction: readString(outputs, "recommended_action"),
      requiresHumanReview: readBoolean(outputs, "requires_human_review"),
      summary: readString(outputs, "summary"),
      seq: spanSeq(span),
    };
  }
  return null;
}

/** Every symbol this module exports, so that a reader sees the whole surface of the projections at once. */
export const __all__ = [
  "TraceTreeNode",
  "TimelineRow",
  "RunStep",
  "EvidenceSummary",
  "VerdictSummary",
  "AmountUnit",
  "AmountSummary",
  "FinalAnswer",
  "buildTraceTree",
  "buildTimeline",
  "buildRunSteps",
  "findCurrentStep",
  "collectEvidence",
  "collectVerdicts",
  "collectAmounts",
  "collectCurrency",
  "findFinalAnswer",
] as const;
