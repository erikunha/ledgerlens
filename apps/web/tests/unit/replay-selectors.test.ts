/**
 * The test of the projections of the recorded run into the facts the interface shows.
 *
 * Why this test exists: the published recording of the scenario `S01` carries only the events of the spans, and the
 * events of the spans carry the evidence, the verdicts, the amounts and the answer inside the outputs of the spans.
 * There is no `evidence.added` event and no `claim.verdict` event to read, so the selectors project those facts out of
 * what the recording really carries. A selector is a projection and never a decision: it never fills a gap, never
 * repairs a value and never invents a fact.
 *
 * The fixture of the test is the recorded bundle of the repository, built event by event from
 * `site/replay/s01/events.jsonl`: the four tools, the three verdicts of the verifier and the answer of the run, with
 * the payloads and the sequence numbers the capture wrote.
 *
 * Every case runs with no key and no network: the fixture is a value of the test.
 */

import { describe, expect, it } from "vitest";

import type { TraceEvent } from "@/lib/api/schemas";
import { reduceEvents, type SpanState, type ToolCallState } from "@/lib/replay/reducer";
import {
  buildRunSteps,
  buildTimeline,
  buildTraceTree,
  collectAmounts,
  collectCurrency,
  collectEvidence,
  collectVerdicts,
  findCurrentStep,
  findFinalAnswer,
} from "@/lib/replay/selectors";

/** The answer of the run, word for word as the capture wrote it. */
const ANSWER =
  "The payment came to BRL 566.79 and the refund to BRL 549.31, a difference of BRL 17.48. [sql:1, calc:1] Of that, BRL 3.40 comes from the FX movement and BRL 14.08 is the markup over the day's reference rate. [calc:1] The reference rate on 2026-10-20 was 5.6339. [fx:2026-10-20:EUR-BRL]";

/** One event of the recording, with the shape the contract publishes. */
function traceEvent(seq: number, eventType: TraceEvent["event_type"], payload: Record<string, unknown>): TraceEvent {
  return {
    schema_version: "1",
    run_id: "replay-s01",
    seq,
    at: "2026-11-14T11:00:14.051+00:00",
    event_type: eventType,
    span_id: null,
    parent_span_id: null,
    payload,
    snapshot_sha256: "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
    mode: "deterministic_sandbox",
  };
}

/** One event of the recording that belongs to a span, with its parent. */
function spanEvent(
  seq: number,
  eventType: "span.started" | "span.ended",
  spanId: string,
  parentSpanId: string | null,
  payload: Record<string, unknown>,
): TraceEvent {
  return { ...traceEvent(seq, eventType, payload), span_id: spanId, parent_span_id: parentSpanId };
}

/**
 * The events of the recorded bundle, in the order of the recording.
 *
 * The sequence numbers are the ones of `site/replay/s01/events.jsonl`, so the tree, the timeline and the projections
 * are exercised on the shape of the real artifact.
 */
const EVENTS: readonly TraceEvent[] = [
  spanEvent(1, "span.started", "span-investigate", null, {
    name: "investigate",
    run_type: "chain",
    inputs: { question: "Why was the BRL refund for TX-2048 lower than the EUR payment?" },
  }),
  spanEvent(2, "span.started", "span-triage", "span-investigate", { name: "triage", run_type: "chain" }),
  spanEvent(3, "span.ended", "span-triage", "span-investigate", {
    name: "triage",
    run_type: "chain",
    status: "ok",
    latency_ms: 3,
  }),
  spanEvent(4, "span.started", "span-tools", "span-investigate", { name: "tools", run_type: "chain" }),
  spanEvent(5, "span.started", "span-query-ledger", "span-tools", {
    name: "query_ledger",
    run_type: "tool",
    inputs: { question: "FX rates applied to TX-2048" },
  }),
  spanEvent(6, "span.ended", "span-query-ledger", "span-tools", {
    name: "query_ledger",
    run_type: "tool",
    status: "ok",
    latency_ms: 12,
    outputs: {
      data: {
        columns: ["kind", "applied_rate", "applied_at"],
        row_count: 2,
        rows: [
          ["charge", "5.6679", "2026-10-15T09:12:04Z"],
          ["refund", "5.4931", "2026-10-20T14:30:00Z"],
        ],
        sql: "SELECT * FROM (SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at) LIMIT 50",
        truncated: false,
      },
      evidence_ids: ["sql:1"],
      ok: true,
    },
  }),
  spanEvent(7, "span.started", "span-fx", "span-tools", {
    name: "get_reference_fx",
    run_type: "tool",
    inputs: { date: "2026-10-20", from_currency: "EUR", to_currency: "BRL" },
  }),
  spanEvent(8, "span.ended", "span-fx", "span-tools", {
    name: "get_reference_fx",
    run_type: "tool",
    status: "ok",
    latency_ms: 11,
    outputs: {
      data: {
        from_cache: false,
        from_currency: "EUR",
        note: "ECB reference rate (Frankfurter v1). It is a reference, not the rate any acquirer applied.",
        rate: "5.6339",
        rate_date: "2026-10-20",
        requested_date: "2026-10-20",
        source: "frankfurter",
        to_currency: "BRL",
      },
      evidence_ids: ["fx:2026-10-20:EUR-BRL"],
      ok: true,
    },
  }),
  spanEvent(9, "span.started", "span-calculate", "span-tools", {
    name: "calculate",
    run_type: "tool",
    inputs: {
      operation: "fx_gap_breakdown",
      values: {
        charge_rate: "5.6679",
        refund_applied_rate: "5.4931",
        refund_reference_rate: "5.6339",
        units: "100.00",
      },
    },
  }),
  spanEvent(10, "span.ended", "span-calculate", "span-tools", {
    name: "calculate",
    run_type: "tool",
    status: "ok",
    latency_ms: 1,
    outputs: {
      data: {
        formula:
          "charge = 100.00 * 5.6679; refund = 100.00 * 5.4931; gap = charge - refund; markup = 100.00 * (5.6339 - 5.4931)",
        operation: "fx_gap_breakdown",
        result: {
          charge: "566.79",
          gap: "17.48",
          markup: "14.08",
          markup_pct: "2.50",
          rate_move: "3.40",
          refund: "549.31",
        },
      },
      evidence_ids: ["calc:1"],
      ok: true,
    },
  }),
  spanEvent(11, "span.ended", "span-tools", "span-investigate", {
    name: "tools",
    run_type: "chain",
    status: "ok",
    latency_ms: 2,
  }),
  spanEvent(12, "span.started", "span-policies", "span-tools", {
    name: "search_policies",
    run_type: "tool",
    inputs: { query: "refund in another currency", transform: "none" },
  }),
  spanEvent(13, "span.ended", "span-policies", "span-tools", {
    name: "search_policies",
    run_type: "tool",
    status: "ok",
    latency_ms: 714,
    outputs: {
      data: {
        query_used: ["refund in another currency"],
        results: [
          {
            chunk_id: "cross-currency-refunds#overview",
            document: "cross-currency-refunds",
            score: 0.34091562032699585,
            section: "Overview",
            text: "Overview\nThis policy explains what happens when the customer pays in one currency and gets the refund in another.",
            topic: "fx",
            version: "2026-10-01",
          },
        ],
        transform: "none",
      },
      evidence_ids: ["policy:cross-currency-refunds#overview"],
      ok: true,
    },
  }),
  spanEvent(14, "span.ended", "span-tools", "span-investigate", {
    name: "tools",
    run_type: "chain",
    status: "ok",
    latency_ms: 718,
  }),
  spanEvent(15, "span.started", "span-verify", "span-investigate", { name: "verify", run_type: "verifier" }),
  spanEvent(16, "span.ended", "span-cl1", "span-verify", {
    name: "CL1",
    run_type: "verifier",
    status: "ok",
    outputs: {
      claim_id: "CL1",
      evidence_ids: ["calc:1", "sql:1"],
      label: "supported",
      method: "numeric",
      note: "Matches 566.79, 549.31, 17.48, 3.40, 14.08, 2.50 (calc:1, sql:1).",
      scores: null,
    },
  }),
  spanEvent(17, "span.ended", "span-cl2", "span-verify", {
    name: "CL2",
    run_type: "verifier",
    status: "ok",
    outputs: {
      claim_id: "CL2",
      evidence_ids: ["calc:1"],
      label: "supported",
      method: "numeric",
      note: "Matches 566.79, 549.31, 17.48, 3.40, 14.08, 2.50 (calc:1).",
      scores: null,
    },
  }),
  spanEvent(18, "span.ended", "span-cl3", "span-verify", {
    name: "CL3",
    run_type: "verifier",
    status: "ok",
    outputs: {
      claim_id: "CL3",
      evidence_ids: ["fx:2026-10-20:EUR-BRL"],
      label: "supported",
      method: "numeric",
      note: "Every stated number is a value of the cited ledger or FX evidence.",
      scores: null,
    },
  }),
  spanEvent(19, "span.ended", "span-verify", "span-investigate", {
    name: "verify",
    run_type: "verifier",
    status: "ok",
    latency_ms: 9,
    outputs: {
      coherence: { issues: [], passed: true },
      verdicts: { contradicted: 0, not_enough_evidence: 0, supported: 3 },
    },
  }),
  spanEvent(20, "span.ended", "span-escalation", "span-investigate", {
    name: "escalation",
    run_type: "verifier",
    status: "ok",
    outputs: { reasons: [], recommended_action: "explain_to_customer", requires_human_review: false },
  }),
  spanEvent(21, "span.ended", "span-investigate", null, {
    name: "investigate",
    run_type: "chain",
    status: "ok",
    latency_ms: 831,
    outputs: {
      answer: ANSWER,
      plan_deviations: [],
      recommended_action: "explain_to_customer",
      requires_human_review: false,
      summary: "Checked 4 sources in 0.8 s: 3 claims supported",
      tokens: 0,
      tool_calls: 4,
    },
  }),
  // An event whose type the interface does not know. The recording of a later export may carry one, and the timeline
  // has to show it anyway, so that no event of the bundle ever disappears silently.
  {
    ...traceEvent(22, "span.started" as TraceEvent["event_type"], { name: "retry" }),
    event_type: "span.retried" as unknown as TraceEvent["event_type"],
  },
  // A call of a tool that carries a claim identifier in its output. It is not a span of the verifier, so it is not a
  // verdict, and it is not an evidence and not an amount either.
  spanEvent(23, "span.ended", "span-check-claim", "span-tools", {
    name: "check_claim",
    run_type: "tool",
    status: "ok",
    latency_ms: 2,
    outputs: { claim_id: "CL9", label: "supported", method: "numeric" },
  }),
];

/** The state of the recording at the end of it, which is what the projections read. */
const REDUCED = reduceEvents(EVENTS);

/** The spans of the recording, as the reducer assembled them. */
const SPANS: readonly SpanState[] = REDUCED.state.spans;

/** The calls of the tools, as the reducer assembled them. */
const TOOL_CALLS: readonly ToolCallState[] = REDUCED.state.toolCalls;

/**
 * Builds a call of the calculation that carries the given result.
 *
 * Why the helper exists: the unit of a value is read out of the name of the value, so a case needs a result with
 * names the published recording does not carry. The call is the shape the reducer assembles, so the projection reads
 * it exactly as it reads a call of the recording.
 */
function calculationWith(result: Record<string, string>): ToolCallState {
  return {
    spanId: "span-calculate",
    name: "calculate",
    inputs: null,
    outputs: { data: { operation: "fx_gap_breakdown", result }, evidence_ids: ["calc:1"], ok: true },
    error: null,
    latencyMs: 1,
    status: "ok",
    evidenceIds: ["calc:1"],
    seq: 10,
  };
}

/** Finds a node of the tree by its identifier. */
function findNode(nodes: readonly { spanId: string; children: readonly any[] }[], spanId: string): any | null {
  for (const node of nodes) {
    if (node.spanId === spanId) {
      return node;
    }
    const found = findNode(node.children, spanId);
    if (found !== null) {
      return found;
    }
  }
  return null;
}

describe("the projections of the recorded run", () => {
  it("nests the spans of the recording by their parent", () => {
    // It proves that the tree of the investigation shows the chain of the spans and not a flat list.
    const trees = buildTraceTree(SPANS);

    expect(trees).toHaveLength(1);
    expect(trees[0]?.spanId).toBe("span-investigate");
    expect(trees[0]?.children.map((child) => child.spanId)).toContain("span-tools");
    expect(findNode(trees, "span-query-ledger")?.parentSpanId).toBe("span-tools");
  });

  it("makes a span whose parent is not in the recording a root", () => {
    // It proves that a span whose parent was lost is shown and never hidden under a parent that does not exist.
    const orphan: SpanState = {
      spanId: "span-orphan",
      parentSpanId: "a-parent-that-was-not-recorded",
      name: "orphan",
      runType: "chain",
      status: "ok",
      latencyMs: 1,
      error: null,
      startedSeq: 1,
      endedSeq: 2,
      inputs: null,
      outputs: null,
    };

    const trees = buildTraceTree([...SPANS, orphan]);

    expect(trees.map((tree) => tree.spanId)).toContain("span-orphan");
    expect(findNode(trees, "span-orphan")?.depth).toBe(0);
  });

  it("measures the depth of a node as its distance from a root", () => {
    // It proves that the tree shows how deep a span sits in the chain of the run.
    const trees = buildTraceTree(SPANS);

    expect(findNode(trees, "span-investigate")?.depth).toBe(0);
    expect(findNode(trees, "span-tools")?.depth).toBe(1);
    expect(findNode(trees, "span-query-ledger")?.depth).toBe(2);
  });

  it("builds one row per event of the recording, in the order of the recording", () => {
    // It proves that the count of the rows of the timeline is the count of the events of the bundle, so that no event
    // of the recording ever disappears silently.
    const rows = buildTimeline(EVENTS);

    expect(rows).toHaveLength(EVENTS.length);
    expect(rows.map((row) => row.seq)).toEqual(EVENTS.map((event) => event.seq));
  });

  it("keeps the events the interface does not know in the timeline", () => {
    // It proves that an event of a later export is shown as an event and never dropped.
    const rows = buildTimeline(EVENTS);
    const unknown = rows.find((row) => row.eventType === "span.retried");

    expect(unknown).toBeDefined();
    expect(unknown?.seq).toBe(22);
    expect(unknown?.label).toBe("retry");
  });

  it("reads the evidence out of the outputs of the tool calls", () => {
    // It proves that the evidence of the published recording is projected from the outputs of the tools, because the
    // recording carries no `evidence.added` event at all.
    const evidence = collectEvidence(TOOL_CALLS);

    expect(evidence.map((item) => item.evidenceId)).toEqual([
      "sql:1",
      "fx:2026-10-20:EUR-BRL",
      "calc:1",
      "policy:cross-currency-refunds#overview",
    ]);
    expect(evidence.find((item) => item.evidenceId === "sql:1")?.tool).toBe("query_ledger");
    expect(evidence.find((item) => item.evidenceId === "fx:2026-10-20:EUR-BRL")?.tool).toBe("get_reference_fx");
    expect(evidence.find((item) => item.evidenceId === "calc:1")?.tool).toBe("calculate");
  });

  it("reads the content of the evidence out of the outputs of the tool calls", () => {
    // It proves that the panel of the evidence shows what the tool published and not a sentence of its own.
    const evidence = collectEvidence(TOOL_CALLS);

    for (const item of evidence) {
      expect(item.content).not.toBeNull();
      expect((item.content as string).length).toBeGreaterThan(0);
    }
    expect(evidence.find((item) => item.evidenceId === "sql:1")?.content).toContain("fx_applied");
    expect(evidence.find((item) => item.evidenceId === "calc:1")?.content).toContain("charge = 100.00 * 5.6679");
  });

  it("reads the verdicts out of the spans of the verifier", () => {
    // It proves that only the spans of the verifier that carry a claim identifier are verdicts, and that the label,
    // the method, the note and the cited identifiers come out of the output of the span.
    const verdicts = collectVerdicts(SPANS);

    expect(verdicts.map((verdict) => verdict.claimId)).toEqual(["CL1", "CL2", "CL3"]);
    expect(verdicts[0]?.label).toBe("supported");
    expect(verdicts[0]?.method).toBe("numeric");
    expect(verdicts[0]?.note).toContain("566.79");
    expect(verdicts[0]?.evidenceIds).toEqual(["calc:1", "sql:1"]);
    expect(verdicts[2]?.evidenceIds).toEqual(["fx:2026-10-20:EUR-BRL"]);
  });

  it("never shows a span of the verifier that carries no claim as a verdict", () => {
    // It proves that the span of the summary of the verification and the span of the escalation are not verdicts.
    const verdicts = collectVerdicts(SPANS);

    expect(verdicts).toHaveLength(3);
    expect(verdicts.map((verdict) => verdict.claimId)).not.toContain("verify");
    expect(verdicts.map((verdict) => verdict.claimId)).not.toContain("escalation");
  });

  it("never shows a span that is not of the verifier as a verdict", () => {
    // It proves that the kind of the span is what makes a verdict: a call of a tool that happens to carry a claim
    // identifier in its output is not a verdict, and it is neither an evidence nor an amount.
    const verdicts = collectVerdicts(SPANS);

    expect(verdicts.map((verdict) => verdict.claimId)).not.toContain("CL9");
    expect(collectEvidence(TOOL_CALLS).map((item) => item.evidenceId)).not.toContain("CL9");
    expect(collectAmounts(TOOL_CALLS).map((amount) => amount.name)).not.toContain("CL9");
  });

  it("keeps the decimal text of the amounts exactly as it was written", () => {
    // It proves that the amount of the charge is the text of the recording and not a number of the browser, and that
    // the name of every amount is the key of the result of the tool, exactly as it came.
    const amounts = collectAmounts(TOOL_CALLS);

    expect(amounts.map((amount) => amount.name)).toEqual([
      "charge",
      "gap",
      "markup",
      "markup_pct",
      "rate_move",
      "refund",
    ]);
    expect(amounts.map((amount) => amount.amount)).toEqual([
      "566.79",
      "17.48",
      "14.08",
      "2.50",
      "3.40",
      "549.31",
    ]);
    for (const amount of amounts) {
      expect(typeof amount.amount).toBe("string");
    }
  });

  it("carries no currency in the amounts, because the currency is another fact", () => {
    // It proves that the value and the currency are two separate facts: the projection never attaches to an amount a
    // currency that it did not read with it.
    const amounts = collectAmounts(TOOL_CALLS);

    for (const amount of amounts) {
      expect(amount.currency).toBeNull();
    }
  });

  it("tells a percentage apart from a money value", () => {
    // It proves that the panel of the amounts knows which values are money and which are a percentage, because a
    // percentage is never money and never carries the currency of the run.
    const amounts = collectAmounts(TOOL_CALLS);

    expect(amounts.find((amount) => amount.name === "markup_pct")?.unit).toBe("percentage");
    for (const name of ["charge", "gap", "markup", "rate_move", "refund"]) {
      expect(amounts.find((amount) => amount.name === name)?.unit).toBe("money");
    }
  });

  it("gives no currency to a percentage", () => {
    // It proves that the currency of the run never reaches a percentage: the percentage is not money.
    const amounts = collectAmounts(TOOL_CALLS);
    const percentage = amounts.find((amount) => amount.name === "markup_pct");

    expect(percentage?.unit).toBe("percentage");
    expect(percentage?.currency).toBeNull();
  });

  it("reads the unit of a value out of the name of the value", () => {
    // It proves that the name of the value is the signal the projection uses: a name that declares a percentage is a
    // percentage, and every other name is money.
    const call = calculationWith({
      charge: "566.79",
      gap: "17.48",
      markup_pct: "2.50",
      markup_percent: "2.50",
      pct_change: "1.25",
      rate_move: "3.40",
      share_pct: "4",
    });
    const amounts = collectAmounts([call]);

    expect(amounts.find((amount) => amount.name === "markup_pct")?.unit).toBe("percentage");
    expect(amounts.find((amount) => amount.name === "markup_percent")?.unit).toBe("percentage");
    expect(amounts.find((amount) => amount.name === "pct_change")?.unit).toBe("percentage");
    expect(amounts.find((amount) => amount.name === "share_pct")?.unit).toBe("percentage");
    expect(amounts.find((amount) => amount.name === "charge")?.unit).toBe("money");
    expect(amounts.find((amount) => amount.name === "gap")?.unit).toBe("money");
    expect(amounts.find((amount) => amount.name === "rate_move")?.unit).toBe("money");
  });

  it("keeps the text of a percentage exactly as it was written", () => {
    // It proves that the unit of a value changes nothing of the value itself.
    const amounts = collectAmounts([calculationWith({ markup_pct: "2.50" })]);

    expect(amounts[0]?.amount).toBe("2.50");
    expect(amounts[0]?.unit).toBe("percentage");
  });

  it("reads the currency of the run out of the exchange rate tool", () => {
    // It proves that the currency is the one the recording read, and never the currency of another amount.
    expect(collectCurrency(TOOL_CALLS)).toBe("BRL");
  });

  it("gives no currency when the recording read none", () => {
    // It proves that the interface never assumes the currency of the run.
    const calculation = TOOL_CALLS.filter((call) => call.name === "calculate");

    expect(collectCurrency(calculation)).toBeNull();
  });

  it("reads the answer out of the output of the last investigate span", () => {
    // It proves that the answer panel shows the answer of the recording, with the action it recommends and the flag
    // of the human review.
    const answer = findFinalAnswer(SPANS);

    expect(answer?.answer).toBe(ANSWER);
    expect(answer?.recommendedAction).toBe("explain_to_customer");
    expect(answer?.requiresHumanReview).toBe(false);
    expect(answer?.summary).toBe("Checked 4 sources in 0.8 s: 3 claims supported");
  });

  it("gives no answer when the recording carries no investigate span", () => {
    // It proves that the interface never writes an answer of its own.
    const withoutInvestigation = SPANS.filter((span) => span.name !== "investigate");

    expect(findFinalAnswer(withoutInvestigation)).toBeNull();
  });
});

describe("the steps of the run", () => {
  it("keeps the spans of the kind tool in the order the reducer opened them", () => {
    // It proves that the steps of the run are the calls of the tools and that they keep the order of the recording: the
    // reducer appends a span when the recording opens it, so the order of the steps is the order of the calls.
    const steps = buildRunSteps(SPANS);

    expect(steps.map((step) => step.name)).toEqual([
      "query_ledger",
      "get_reference_fx",
      "calculate",
      "search_policies",
      "check_claim",
    ]);
    expect(steps.map((step) => step.number)).toEqual([1, 2, 3, 4, 5]);
  });

  it("leaves the spans that are not calls of a tool out", () => {
    // It proves that the life of the run is not a step of it: the chain and the verifier spans are not calls, and the
    // stepper never shows them.
    const steps = buildRunSteps(SPANS);

    expect(steps.map((step) => step.name)).not.toContain("investigate");
    expect(steps.map((step) => step.name)).not.toContain("tools");
    expect(steps.map((step) => step.name)).not.toContain("verify");
  });

  it("carries the moment and the status of every call", () => {
    // It proves that the step carries what the capture recorded about the call: the event that opened it, the event
    // that closed it and the status it ended with.
    const steps = buildRunSteps(SPANS);
    const first = steps[0];

    expect(first?.startedSeq).toBe(5);
    expect(first?.endedSeq).toBe(6);
    expect(first?.status).toBe("ok");
  });

  it("finds the step the recording stands at", () => {
    // It proves that the current step is the last call the recording has opened: the recording stands at the call it is
    // inside.
    const steps = buildRunSteps(SPANS);

    expect(findCurrentStep(steps, 5)?.name).toBe("query_ledger");
    expect(findCurrentStep(steps, 13)?.name).toBe("search_policies");
    expect(findCurrentStep(steps, 23)?.name).toBe("check_claim");
  });

  it("finds no step before the first call", () => {
    // It proves that a recording that stands before its first call has no current step, and that the stepper then says
    // that the recording has not called a tool yet.
    const steps = buildRunSteps(SPANS);

    expect(findCurrentStep(steps, null)).toBeNull();
    expect(findCurrentStep(steps, 1)).toBeNull();
  });
});
