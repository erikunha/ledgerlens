/**
 * The test of the reducer of the recorded events.
 *
 * Why this test exists: the state the reader sees at a position of a recording is built by one function, and that
 * function has to survive the three awkward cases of a recording: an event that arrives twice, an event that never
 * arrived and an event whose type the interface does not know. A visitor has to see what the recording says, and a hole
 * in a recording has to be shown out loud instead of being hidden, so every case of this test says three things: what the
 * state becomes, what the issue says to the reader, and what stays untouched.
 *
 * Why the purity has cases of its own: a visitor can seek back and forth, and the state at event 12 has to be the state
 * the visitor saw before, every time. A reducer that read a clock, drew a random number or kept a state between two
 * calls would break that promise without a single case failing, so the cases below prove that the same events give the
 * same state, that the events are never changed and that a position never depends on the events that come after it.
 *
 * Every case runs with no key and no network: the events of the test are values.
 */

import { describe, expect, it } from "vitest";

import type { TraceEvent } from "@/lib/api/schemas";
import { emptyState, reduceEvents, reduceToIndex, reduceToSeq } from "@/lib/replay/reducer";

/** The identifier of the run of the fixture, as the published recording of the scenario S01 carries it. */
const RUN_ID = "replay-s01";

/** The hash of the snapshot of the fixture, the one the published recording of the scenario S01 carries. */
const SNAPSHOT_SHA256 = "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f";

/**
 * One event of the recording, with the shape the contract publishes.
 *
 * Why the fixture carries a snapshot hash and a mode: a real event of the published bundle carries both, and a fixture
 * that left them out would exercise a shape the reader never meets.
 */
function event(
  seq: number,
  eventType: TraceEvent["event_type"],
  payload: Record<string, unknown> = {},
): TraceEvent {
  return {
    schema_version: "1",
    run_id: RUN_ID,
    seq,
    at: "2026-11-14T11:00:14.051+00:00",
    event_type: eventType,
    span_id: null,
    parent_span_id: null,
    payload,
    snapshot_sha256: SNAPSHOT_SHA256,
    mode: "deterministic_sandbox",
  };
}

/**
 * One event whose type the interface does not know.
 *
 * Why the type is cast: the contract of the trace knows eleven types, and a recording of a later export can carry a
 * twelfth one. The reducer has to survive the type that the contract does not publish yet, so the fixture builds it.
 */
function unknownEvent(seq: number, eventType: string): TraceEvent {
  return { ...event(seq, "run.started"), seq, event_type: eventType } as unknown as TraceEvent;
}

/** The question of the plan of the fixture, as the published recording of the scenario S01 carries it. */
const QUESTION = "Why was the BRL refund for TX-2048 lower than the EUR payment?";

/** The event that opens the run. */
const RUN_STARTED = event(1, "run.started");

/** The event that carries the plan of the run. */
const PLAN = event(2, "plan.created", { question: QUESTION, steps: ["read the ledger", "read the policy"] });

/** The event that carries the evidence the run collected. */
const EVIDENCE = event(3, "evidence.added", {
  evidence_id: "sql:1",
  source_type: "sql",
  tool: "query_ledger",
  ref: "sql:1",
  content: "refund of BRL 549.31 on 2026-10-20",
});

/** The event that carries the verdict of the verifier. */
const VERDICT = event(4, "claim.verdict", {
  claim_id: "CL1",
  label: "supported",
  method: "numeric",
  evidence_ids: ["sql:1"],
});

/**
 * The events of the fixture, in the order of the recording.
 *
 * Why these four events: they are the four kinds of event the cases of this test need, a run that starts, a plan that
 * is written, an evidence that is collected and a verdict that is produced.
 */
const EVENTS: readonly TraceEvent[] = [RUN_STARTED, PLAN, EVIDENCE, VERDICT];

describe("the duplicated event", () => {
  it("ignores the second event of the same run and the same sequence number", () => {
    // It proves that a recording that carries the same event twice is played once: the state the reader sees is the
    // state of the recording without the duplicate, and the plan of the first event is the plan that stays.
    const duplicate = event(2, "plan.created", { question: "a question the duplicate brought" });
    const withDuplicate = reduceEvents([RUN_STARTED, PLAN, duplicate]);

    expect(withDuplicate.state.events).toHaveLength(2);
    expect(withDuplicate.state.plan?.question).toBe(QUESTION);
    expect(withDuplicate.state.lastSeq).toBe(2);
  });

  it("says out loud that the event was already applied, and does not refuse the recording", () => {
    // It proves that the reader is told about the duplicate and that the recording still plays: a duplicated event is
    // ignored, not a refusal.
    const duplicate = event(2, "plan.created", { question: "a question the duplicate brought" });
    const withDuplicate = reduceEvents([RUN_STARTED, PLAN, duplicate]);
    const issue = withDuplicate.issues[0];

    expect(withDuplicate.issues).toHaveLength(1);
    expect(issue?.kind).toBe("duplicate");
    expect(issue?.seq).toBe(2);
    expect(issue?.message).toContain("2");
    expect(issue?.message).toContain(RUN_ID);
    expect(withDuplicate.refused).toBe(false);
    expect(withDuplicate.reasons).toEqual([]);
  });

  it("leaves the state of the events that came after the duplicate untouched", () => {
    // It proves that a duplicate does not damage the rest of the recording: the evidence and the verdict of the run are
    // still there, and the state is the state of the same recording without the duplicate.
    const duplicate = event(2, "plan.created", { question: "a question the duplicate brought" });
    const withDuplicate = reduceEvents([...EVENTS.slice(0, 2), duplicate, ...EVENTS.slice(2)]);
    const withoutDuplicate = reduceEvents(EVENTS);

    expect(withDuplicate.state.evidence.map((item) => item.evidenceId)).toEqual(["sql:1"]);
    expect(withDuplicate.state.verdicts.map((item) => item.claimId)).toEqual(["CL1"]);
    expect(withDuplicate.state.status).toBe("running");
    // The two states are compared without the issues, because the issues are what the duplicate adds.
    expect({ ...withDuplicate.state, issues: [] }).toEqual({ ...withoutDuplicate.state, issues: [] });
  });
});

describe("the gap in the sequence", () => {
  it("refuses the recording and names the event that never arrived", () => {
    // It proves that a hole in the sequence is said out loud: the reader is told which event is missing and the
    // recording is refused, because a hole in a recording is exactly what a reader has to know about.
    const withGap = reduceEvents([RUN_STARTED, EVIDENCE]);
    const issue = withGap.issues[0];

    expect(withGap.refused).toBe(true);
    expect(withGap.reasons).toHaveLength(1);
    expect(withGap.reasons[0]).toBe(issue?.message);
    expect(issue?.kind).toBe("gap");
    expect(issue?.seq).toBe(3);
    expect(issue?.message).toContain("Event 2");
    expect(issue?.message).toContain("missing");
  });

  it("names every missing event when the recording skips more than one", () => {
    // It proves that the reason of the refusal counts the events that were lost, so that a reader knows how much of the
    // recording is missing and not only that something is.
    const withGap = reduceEvents([RUN_STARTED, event(5, "run.completed")]);
    const issue = withGap.issues[0];

    expect(issue?.kind).toBe("gap");
    expect(issue?.message).toContain("Events 2 to 4");
    expect(issue?.message).toContain("missing");
    expect(withGap.refused).toBe(true);
  });

  it("keeps the state of the events it did receive and invents nothing for the one it did not", () => {
    // It proves that a refusal does not throw the state away: the events that arrived are still there, and the plan of
    // the event that was lost stays empty instead of being made up.
    const withGap = reduceEvents([RUN_STARTED, EVIDENCE]);

    expect(withGap.state.events).toHaveLength(2);
    expect(withGap.state.status).toBe("running");
    expect(withGap.state.evidence.map((item) => item.evidenceId)).toEqual(["sql:1"]);
    expect(withGap.state.plan).toBeNull();
    expect(withGap.state.lastSeq).toBe(3);
  });

  it("refuses a recording whose events arrive out of order", () => {
    // It proves that a recording that goes backwards is refused too: the sequence of a recording has to grow.
    const outOfOrder = reduceEvents([PLAN, RUN_STARTED]);
    const issue = outOfOrder.issues[1];

    expect(outOfOrder.refused).toBe(true);
    expect(outOfOrder.reasons).toHaveLength(2);
    expect(issue?.kind).toBe("gap");
    expect(issue?.message).toContain("out of order");
  });
});

describe("the event type the interface does not know", () => {
  it("keeps the unknown event in the bucket of the unknown events and in the list of the events", () => {
    // It proves that a recording of a later export does not break the page and does not make its event disappear: the
    // unknown event is kept, so that the timeline can show it as an event the interface does not know.
    //
    // Why no case of this file asks for an issue of the kind `unknown-type`: the reducer declares that kind of issue and
    // does not emit one today. The unknown event is kept and the run is not refused, and that is what the cases below
    // say. A case that asked for the issue would be a case that asked for behaviour the reducer does not have.
    const unknown = unknownEvent(5, "span.retried");
    const withUnknown = reduceEvents([...EVENTS, unknown]);

    expect(withUnknown.state.other).toHaveLength(1);
    expect(withUnknown.state.other[0]?.seq).toBe(5);
    expect(withUnknown.state.other[0]?.event_type).toBe("span.retried");
    expect(withUnknown.state.events.map((item) => item.seq)).toEqual([1, 2, 3, 4, 5]);
    expect(withUnknown.state.lastSeq).toBe(5);
  });

  it("does not refuse the recording and does not damage the state of the other events", () => {
    // It proves that an event the interface cannot read is kept without breaking the run: the plan, the evidence and
    // the verdict of the recording are the ones the recording carries.
    const unknown = unknownEvent(5, "span.retried");
    const withUnknown = reduceEvents([...EVENTS, unknown]);

    expect(withUnknown.refused).toBe(false);
    expect(withUnknown.reasons).toEqual([]);
    expect(withUnknown.state.plan?.question).toBe(QUESTION);
    expect(withUnknown.state.evidence.map((item) => item.evidenceId)).toEqual(["sql:1"]);
    expect(withUnknown.state.verdicts.map((item) => item.claimId)).toEqual(["CL1"]);
    expect(withUnknown.state.spans).toEqual([]);
    expect(withUnknown.state.toolCalls).toEqual([]);
  });

  it("keeps the amount of the ledger as the decimal text the recording carries", () => {
    // It proves that the reducer never turns a money into a number: the content of the evidence is copied word for word,
    // because the money of the interface is the text of the ledger and a float of an amount is another amount.
    const reduced = reduceEvents(EVENTS);

    expect(reduced.state.evidence[0]?.content).toBe("refund of BRL 549.31 on 2026-10-20");
  });
});

describe("the purity of the reduction", () => {
  it("gives the same state for the same events, every time", () => {
    // It proves that the state at a position does not depend on how many times the reader asked for it: two reductions
    // of the same events give the same state, the same issues and the same reasons.
    const first = reduceEvents(EVENTS);
    const second = reduceEvents(EVENTS);

    expect(second.state).toEqual(first.state);
    expect(second.issues).toEqual(first.issues);
    expect(second.reasons).toEqual(first.reasons);
    expect(second.refused).toBe(first.refused);
  });

  it("gives no state that one reduction can change for the next one", () => {
    // It proves that the state of a reduction is not shared with the state of another one, so that a reader who seeks
    // back and forth never sees the state of another position change under the reader's feet.
    const first = reduceEvents(EVENTS);
    const second = reduceEvents(EVENTS);

    expect(first.state.evidence).not.toBe(second.state.evidence);
    expect(first.state.events).not.toBe(second.state.events);
    expect(first.state.spans).not.toBe(second.state.spans);
  });

  it("does not change the events it was given", () => {
    // It proves that the recording is read and never written: the events the caller gave are the same events when the
    // reduction is over.
    const events = [...EVENTS];
    const before = JSON.parse(JSON.stringify(events)) as TraceEvent[];

    reduceEvents(events);

    expect(events).toEqual(before);
  });

  it("starts every reduction from the empty state", () => {
    // It proves that no reduction inherits the state of the reduction before it: the empty state is the state before
    // the first event, and every reduction begins there.
    const first = reduceEvents(EVENTS);
    const second = reduceEvents(EVENTS);

    expect(emptyState().events).toEqual([]);
    expect(emptyState().status).toBe("idle");
    expect(first.state).not.toEqual(emptyState());
    expect(second.state).toEqual(first.state);
  });

  it("gives the state of a position that does not depend on the events that come after it", () => {
    // It proves that a seek to a position gives the state of the prefix of the recording and nothing else: the events
    // that come after the position change nothing about it.
    const byIndex = reduceToIndex(EVENTS, 1);
    const bySeq = reduceToSeq(EVENTS, 2);
    const prefix = reduceEvents(EVENTS.slice(0, 2));

    expect(byIndex.state).toEqual(prefix.state);
    expect(bySeq.state).toEqual(prefix.state);
    expect(byIndex.state.events.map((item) => item.seq)).toEqual([1, 2]);
  });
});
