/**
 * The event reducer: the single place where the recorded events become the state the interface renders.
 *
 * Why this file exists: a visitor can seek anywhere in the recording, and the state they see at event 12 has to be
 * exactly the state they saw before, every time. The only way to guarantee that is to rebuild the state from the
 * events instead of mutating it in place, so the reducer takes the ordered events and returns the state at a given
 * position. The same position always produces the same state, because the function is pure: it reads no clock, it
 * draws no random number and it touches nothing outside its arguments.
 *
 * The reducer also carries the three awkward cases of the contract. A duplicated event, which carries a sequence
 * number that was already seen, is ignored. A gap in the sequence, which means an event was lost, is refused with a
 * reason a reader can act on instead of being hidden. An event type the interface does not know is kept in a bucket
 * of its own, so that a newer bundle does not break an older page and does not make the event disappear either.
 */

import type { TraceEvent, TraceMode } from "@/lib/api/schemas";

/** The status of the run, as the interface shows it. */
export type RunStatus = "idle" | "running" | "completed" | "failed" | "cancelled";

/** The kind of problem the reducer found while it reduced the events. */
export type ReduceIssueKind = "duplicate" | "gap" | "unknown-type";

/** One problem the reducer found, with a reason written for whoever reads it. */
export interface ReduceIssue {
  /** What kind of problem it is. */
  kind: ReduceIssueKind;
  /** The sequence number the problem was found at. */
  seq: number;
  /** The reason, written in words. */
  message: string;
}

/** The state of one span of the recorded execution. */
export interface SpanState {
  /** The identifier of the span. */
  spanId: string;
  /** The identifier of the parent span, when the recorded event carried one. */
  parentSpanId: string | null;
  /** The name of the span, as the capture recorded it. */
  name: string | null;
  /** The kind of the span, for instance `tool`, `chain` or `llm`. */
  runType: string | null;
  /** The status the span ended with. */
  status: string | null;
  /** The duration the capture measured, in milliseconds. */
  latencyMs: number | null;
  /** The error the span ended with, when there was one. */
  error: string | null;
  /** The sequence number of the event that opened the span. */
  startedSeq: number | null;
  /** The sequence number of the event that closed the span. */
  endedSeq: number | null;
  /** The arguments the span received. */
  inputs: unknown;
  /** The result the span produced. */
  outputs: unknown;
}

/** The plan the agent wrote, as the capture recorded it. */
export interface PlanState {
  /** The question the plan answers. */
  question: string | null;
  /** The steps of the plan, as the capture recorded them. */
  steps: string[];
  /** The sequence number of the event that carried the plan. */
  seq: number;
}

/** One evidence the run collected, as the capture recorded it. */
export interface EvidenceState {
  /** The canonical identifier of the evidence, the one the published result uses. */
  evidenceId: string;
  /** The kind of the source, when the capture recorded it. */
  sourceType: string | null;
  /** The tool that produced the evidence, when the capture recorded it. */
  tool: string | null;
  /** The origin reference of the source, when the capture recorded it. */
  ref: string | null;
  /** The sanitized content of the source, when the capture recorded it. */
  content: string | null;
  /** The sequence number of the event that carried the evidence. */
  seq: number;
}

/** The verdict the verifier produced about one claim, as the capture recorded it. */
export interface ClaimVerdictState {
  /** The identifier of the claim the verdict is about. */
  claimId: string;
  /** The decision itself. */
  label: string | null;
  /** The method that produced the decision. */
  method: string | null;
  /** The identifiers of the evidence the decision used. */
  evidenceIds: string[];
  /** The note of the verifier, when there was one. */
  note: string | null;
  /** The sequence number of the event that carried the verdict. */
  seq: number;
}

/** One tool call the run made, assembled from the span that opened it and the span that closed it. */
export interface ToolCallState {
  /** The identifier of the span the call ran in. */
  spanId: string;
  /** The name of the tool. */
  name: string;
  /** The arguments the tool received. */
  inputs: unknown;
  /** The result the tool returned. */
  outputs: unknown;
  /** The error the tool ended with, when there was one. */
  error: string | null;
  /** The duration the capture measured, in milliseconds. */
  latencyMs: number | null;
  /** The status the call ended with. */
  status: string | null;
  /** The identifiers of the evidence the call produced, when it reported any. */
  evidenceIds: string[];
  /** The sequence number of the event that closed the call. */
  seq: number;
}

/** The whole state of the replay at one position of the recording. */
export interface ReplayState {
  /** The identifier of the run. */
  runId: string | null;
  /** The mode the recorded execution was in. */
  mode: TraceMode | null;
  /** The status of the run at this position. */
  status: RunStatus;
  /** The plan of the run, when it was already written. */
  plan: PlanState | null;
  /** The spans that were already opened, in the order they were opened. */
  spans: SpanState[];
  /** The evidence that was already collected, in the order it was collected. */
  evidence: EvidenceState[];
  /** The verdicts that were already produced, in the order they were produced. */
  verdicts: ClaimVerdictState[];
  /** The tool calls that were already made, in the order they were made. */
  toolCalls: ToolCallState[];
  /** The events whose type the interface does not know, kept so that they are never silently dropped. */
  other: TraceEvent[];
  /** The events that were applied, in the order they were applied. */
  events: TraceEvent[];
  /** The problems the reducer found. */
  issues: ReduceIssue[];
  /** The sequence number of the last event that was applied. */
  lastSeq: number | null;
  /** Whether the reduction was refused, which happens when the sequence has a gap. */
  refused: boolean;
  /** The reasons of the refusal. */
  reasons: string[];
}

/** The outcome of a reduction. */
export interface ReduceResult {
  /** The state at the requested position. */
  state: ReplayState;
  /** Whether the reduction was refused, which happens when the sequence has a gap. */
  refused: boolean;
  /** The reasons of the refusal, written for whoever reads them. */
  reasons: string[];
  /** Every problem the reducer found, gaps and duplicates among them. */
  issues: ReduceIssue[];
}

/** The empty state, the state before the first event. */
export function emptyState(): ReplayState {
  return {
    runId: null,
    mode: null,
    status: "idle",
    plan: null,
    spans: [],
    evidence: [],
    verdicts: [],
    toolCalls: [],
    other: [],
    events: [],
    issues: [],
    lastSeq: null,
    refused: false,
    reasons: [],
  };
}

/**
 * The key that identifies an event for the duplicate check.
 *
 * The contract says that a duplicated event shares the run identifier and the sequence number with the one that came
 * before, so the key is exactly those two.
 */
export function eventKey(event: TraceEvent): string {
  return `${event.run_id}:${event.seq}`;
}

/** Reads a string out of a payload, whatever the capture named it. */
function readString(payload: Record<string, unknown>, ...names: string[]): string | null {
  for (const name of names) {
    const value = payload[name];
    if (typeof value === "string" && value.length > 0) {
      return value;
    }
  }
  return null;
}

/** Reads a number out of a payload, whatever the capture named it. */
function readNumber(payload: Record<string, unknown>, ...names: string[]): number | null {
  for (const name of names) {
    const value = payload[name];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
  }
  return null;
}

/** Reads a list of strings out of a payload, whatever the capture named it. */
function readStringList(payload: Record<string, unknown>, ...names: string[]): string[] {
  for (const name of names) {
    const value = payload[name];
    if (Array.isArray(value)) {
      return value.filter((item): item is string => typeof item === "string");
    }
  }
  return [];
}

/** The status the run reaches with a terminal event. */
const TERMINAL_STATUS: Record<string, RunStatus> = {
  "run.completed": "completed",
  "run.failed": "failed",
  "run.cancelled": "cancelled",
};

/**
 * Reduces the ordered events into the state at the last of them.
 *
 * The reduction always starts from the empty state and always walks the events in order, so the result depends only
 * on the events themselves and never on how the caller reached them.
 */
export function reduceEvents(events: readonly TraceEvent[]): ReduceResult {
  let state = emptyState();
  const seen = new Set<string>();
  const issues: ReduceIssue[] = [];
  const reasons: string[] = [];
  let expectedSeq = 1;

  for (const event of events) {
    const key = eventKey(event);

    // A duplicated event is ignored: the state it would produce is already there, and applying it twice would make
    // the same position produce two different states depending on how the file was read.
    if (seen.has(key)) {
      issues.push({
        kind: "duplicate",
        seq: event.seq,
        message: `Event ${event.seq} of the run ${event.run_id} was already applied and was ignored.`,
      });
      continue;
    }
    seen.add(key);

    // A gap in the sequence means an event was lost. The reduction says so out loud, because a hole in the sequence
    // is exactly what a reader has to know about before trusting what is on the screen.
    if (event.seq > expectedSeq) {
      const missing = event.seq - expectedSeq;
      const message =
        missing === 1
          ? `Event ${expectedSeq} of the run is missing: the recording jumps from event ${expectedSeq - 1} to event ${event.seq}.`
          : `Events ${expectedSeq} to ${event.seq - 1} of the run are missing: the recording jumps from event ${expectedSeq - 1} to event ${event.seq}.`;
      issues.push({ kind: "gap", seq: event.seq, message });
      reasons.push(message);
    } else if (event.seq < expectedSeq) {
      const message = `Event ${event.seq} of the run arrived after event ${expectedSeq - 1}: the recording is out of order.`;
      issues.push({ kind: "gap", seq: event.seq, message });
      reasons.push(message);
    }
    expectedSeq = Math.max(expectedSeq, event.seq + 1);

    state = applyEvent(state, event);

    if (state.lastSeq === null || event.seq > state.lastSeq) {
      state = { ...state, lastSeq: event.seq };
    }
  }

  return {
    state: { ...state, issues, refused: reasons.length > 0, reasons },
    refused: reasons.length > 0,
    reasons,
    issues,
  };
}

/**
 * Reduces the events up to a position, which is what a seek does.
 *
 * The position is the index of the event in the ordered list, counted from zero, and the event at that index is
 * included. Seeking to the same position twice gives the same state, because the reduction of the prefix does not
 * depend on anything else.
 */
export function reduceToIndex(events: readonly TraceEvent[], index: number): ReduceResult {
  if (index < 0) {
    return reduceEvents([]);
  }
  return reduceEvents(events.slice(0, index + 1));
}

/**
 * Reduces the events up to a sequence number, which is the other way a caller can address a position.
 *
 * The events that carry a sequence number above the target are left out, and the events without one are left in.
 */
export function reduceToSeq(events: readonly TraceEvent[], seq: number): ReduceResult {
  return reduceEvents(events.filter((event) => event.seq <= seq));
}

/** Applies one event to the state and returns the new state. */
function applyEvent(state: ReplayState, event: TraceEvent): ReplayState {
  const payload = event.payload ?? {};
  const next: ReplayState = {
    ...state,
    runId: state.runId ?? event.run_id,
    mode: state.mode ?? event.mode ?? null,
    events: [...state.events, event],
  };

  switch (event.event_type) {
    case "run.started": {
      return { ...next, status: "running" };
    }
    case "run.status": {
      const reported = readString(payload, "status", "state");
      const status = reported === "running" || reported === "completed" || reported === "failed" || reported === "cancelled" ? reported : next.status;
      return { ...next, status };
    }
    case "run.completed":
    case "run.failed":
    case "run.cancelled": {
      return { ...next, status: TERMINAL_STATUS[event.event_type] ?? next.status };
    }
    case "plan.created": {
      const plan: PlanState = {
        question: readString(payload, "question", "complaint"),
        steps: readPlanSteps(payload),
        seq: event.seq,
      };
      return { ...next, plan };
    }
    case "span.started": {
      const spanId = event.span_id ?? `span-${event.seq}`;
      const existing = next.spans.find((span) => span.spanId === spanId);
      const span: SpanState = {
        spanId,
        parentSpanId: event.parent_span_id ?? null,
        name: readString(payload, "name"),
        runType: readString(payload, "run_type"),
        status: null,
        latencyMs: null,
        error: null,
        startedSeq: event.seq,
        endedSeq: existing?.endedSeq ?? null,
        inputs: payload.inputs ?? null,
        outputs: existing?.outputs ?? null,
      };
      return {
        ...next,
        spans: existing ? next.spans.map((item) => (item.spanId === spanId ? span : item)) : [...next.spans, span],
      };
    }
    case "span.ended": {
      const spanId = event.span_id ?? `span-${event.seq}`;
      const existing = next.spans.find((span) => span.spanId === spanId);
      const outputs = payload.outputs ?? null;
      const evidenceIds = readStringList(outputs && typeof outputs === "object" ? (outputs as Record<string, unknown>) : {}, "evidence_ids");
      const error = readString(payload, "error");
      const span: SpanState = {
        spanId,
        parentSpanId: event.parent_span_id ?? existing?.parentSpanId ?? null,
        name: readString(payload, "name") ?? existing?.name ?? null,
        runType: readString(payload, "run_type") ?? existing?.runType ?? null,
        status: readString(payload, "status") ?? existing?.status ?? null,
        latencyMs: readNumber(payload, "latency_ms", "duration_ms") ?? existing?.latencyMs ?? null,
        error: error ?? existing?.error ?? null,
        startedSeq: existing?.startedSeq ?? null,
        endedSeq: event.seq,
        inputs: existing?.inputs ?? null,
        outputs: outputs ?? existing?.outputs ?? null,
      };
      const spans = existing
        ? next.spans.map((item) => (item.spanId === spanId ? span : item))
        : [...next.spans, span];

      // A tool call is a span of the kind `tool`. The interface shows the arguments and the result of every call,
      // and it shows them because the capture recorded them, never because the interface recomputed them.
      if (span.runType === "tool") {
        const toolCall: ToolCallState = {
          spanId,
          name: span.name ?? "tool",
          inputs: span.inputs,
          outputs: span.outputs,
          error: span.error,
          latencyMs: span.latencyMs,
          status: span.status,
          evidenceIds,
          seq: event.seq,
        };
        const withoutCall = next.toolCalls.filter((call) => call.spanId !== spanId);
        return { ...next, spans, toolCalls: [...withoutCall, toolCall] };
      }
      return { ...next, spans };
    }
    case "evidence.added": {
      const evidenceId = readString(payload, "evidence_id", "id");
      if (evidenceId === null) {
        return next;
      }
      const evidence: EvidenceState = {
        evidenceId,
        sourceType: readString(payload, "source_type", "source_kind"),
        tool: readString(payload, "tool"),
        ref: readString(payload, "ref", "source_ref"),
        content: readString(payload, "content", "excerpt"),
        seq: event.seq,
      };
      const withoutSame = next.evidence.filter((item) => item.evidenceId !== evidenceId);
      return { ...next, evidence: [...withoutSame, evidence] };
    }
    case "claim.verdict": {
      const claimId = readString(payload, "claim_id", "id");
      if (claimId === null) {
        return next;
      }
      const verdict: ClaimVerdictState = {
        claimId,
        label: readString(payload, "label", "verdict"),
        method: readString(payload, "method"),
        evidenceIds: readStringList(payload, "evidence_ids"),
        note: readString(payload, "note"),
        seq: event.seq,
      };
      const withoutSame = next.verdicts.filter((item) => item.claimId !== claimId);
      return { ...next, verdicts: [...withoutSame, verdict] };
    }
    case "heartbeat": {
      return next;
    }
    default: {
      // The event type is not one the interface knows. It is kept, so that the timeline can show it as an
      // unrecognized event instead of dropping it silently.
      return { ...next, other: [...next.other, event] };
    }
  }
}

/** Reads the steps of a plan out of a payload that carries them as objects. */
function readPlanSteps(payload: Record<string, unknown>): string[] {
  const value = payload.steps;
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((step) => {
      if (typeof step === "string") {
        return step;
      }
      if (step && typeof step === "object") {
        const record = step as Record<string, unknown>;
        const role = readString(record, "role", "name", "description");
        const stepId = readString(record, "step_id", "id");
        if (role && stepId) {
          return `${stepId}: ${role}`;
        }
        return role ?? stepId;
      }
      return null;
    })
    .filter((step): step is string => step !== null);
}
