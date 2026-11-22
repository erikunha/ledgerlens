/**
 * The test of the validation of the published artifacts.
 *
 * Why this test exists: the interface must never render an artifact it does not understand. A bundle that comes from a
 * file, from a network or from a hand edited folder can carry a sequence number below 1, a snapshot hash that is not a
 * sha256 in lowercase hexadecimal, a mode the contract does not define or an event type the contract does not define.
 * The contract refuses those, so the interface refuses them too, and it refuses them with a reason a reader can act on
 * instead of with an exception the caller has to catch.
 *
 * Why every validator has to answer instead of throwing: the caller of a validator is a page that has to show something
 * to a visitor. A validator that threw would leave the page with nothing to show, so the reasons travel with the refusal
 * and the caller decides what the visitor reads.
 *
 * Why the count of the events has a case of its own: the manifest declares how many events its bundle holds, and the
 * count that the events really have has to agree with it. The case below pins down what the web does today, and it says
 * out loud that the web does not compare the two counts yet.
 *
 * Why the metadata of the route of a scenario is asserted in this file: the route of a scenario names the scenario it
 * publishes, and the name it publishes comes from the catalog of the published artifacts, which is the artifact this file
 * is about. The route has no test file of its own, and this file is one of the two unit test files of this work.
 *
 * Every case runs with no key and no network: the artifacts of the test are values.
 */

import { describe, expect, it } from "vitest";
import type { Metadata } from "next";

import type { TraceEvent } from "@/lib/api/schemas";
import {
  validateBundle,
  validateManifest,
  validateResult,
  validateScenarioIndex,
  validateScenarioIndexEntry,
  validateTraceEvent,
  validateTraceEvents,
  type ValidationResult,
} from "@/lib/replay/validate";

/** The hash of the snapshot of the fixtures, the one the published bundle of the scenario S01 carries. */
const SNAPSHOT_SHA256 = "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f";

/** The hash of the code commit of the fixtures, the one the published bundle of the scenario S01 carries. */
const CODE_SHA = "9dc3af946b223496c7ed2e897b1e4152bbf9234f";

/** One event of the recording, with the shape the contract publishes. */
const VALID_EVENT: TraceEvent = {
  schema_version: "1",
  run_id: "replay-s01",
  seq: 1,
  at: "2026-11-14T11:00:14.051+00:00",
  event_type: "run.started",
  span_id: null,
  parent_span_id: null,
  payload: {},
  snapshot_sha256: SNAPSHOT_SHA256,
  mode: "deterministic_sandbox",
};

/**
 * One event with a field of the fixture changed.
 *
 * Why the fixture is changed instead of written again: a case of this test has to break one field and keep the rest of
 * the event exactly as the contract publishes it, so that the reason of the refusal is the reason of that field.
 */
function eventWith(overrides: Record<string, unknown>): unknown {
  return { ...VALID_EVENT, ...overrides };
}

/** The manifest of the published bundle of the scenario S01, as `site/replay/s01/manifest.json` holds it. */
const VALID_MANIFEST = {
  bundle_schema_version: "1",
  run_id: "replay-s01",
  mode: "deterministic_sandbox",
  scenario: "S01",
  events: 1,
  files: { "events.jsonl": "577939e532327f3af1a3897612f622d96edc27a620646437fb02c5fa5318de13" },
  snapshot_sha256: SNAPSHOT_SHA256,
  created_at: "2026-11-14T11:00:14+00:00",
  note: "Deterministic execution of the scenario S01, with the scripted model.",
};

/** The result of the recorded investigation, as the published bundle of the scenario S01 carries it. */
const VALID_RESULT = {
  schema_version: "1",
  run_id: "replay-s01",
  mode: "deterministic_sandbox",
  snapshot_sha256: SNAPSHOT_SHA256,
  answer: "The refund of BRL 549.31 was lower than the payment because of the exchange rate and the markup.",
  claims: [
    {
      id: "CL1",
      text: "The refund was BRL 549.31.",
      kind: "numeric",
      evidence_ids: ["sql:1"],
    },
  ],
  evidence: [
    {
      id: "sql:1",
      source_type: "sql",
      tool: "query_ledger",
      ref: "sql:1",
      content: "refund of BRL 549.31 on 2026-10-20",
      retrieved_at: "2026-11-14T11:00:14+00:00",
    },
  ],
  verdicts: [
    {
      claim_id: "CL1",
      label: "supported",
      method: "numeric",
      evidence_ids: ["sql:1"],
      note: null,
    },
  ],
  verification_status: "complete",
  requires_human_review: false,
  recommended_action: "explain_to_customer",
};

/** The bundle of the published recording of the scenario S01, in the shape of the one document contract. */
const VALID_BUNDLE = {
  schema_version: "1",
  replay_id: "replay-s01",
  capture_kind: "scripted_fixture",
  recorded_at: "2026-11-14T11:00:14+00:00",
  scenario_id: "S01",
  snapshot_sha256: SNAPSHOT_SHA256,
  code_sha: CODE_SHA,
  model_profile: "scripted-fixture",
  run_result: VALID_RESULT,
  events: [VALID_EVENT],
};

/**
 * The metadata of the route of a scenario, as the framework asks the route for it.
 *
 * Why the route is loaded inside the case: the route is a module of the framework, and loading it here keeps the case
 * of this file from depending on the whole tree of the interface at the moment the file is read.
 */
async function scenarioMetadata(scenario: string): Promise<Metadata> {
  const page = await import("@/app/(public)/replay/scenario/[scenario]/page");
  return page.generateMetadata({ params: Promise.resolve({ scenario }) });
}

describe("the sequence number of an event", () => {
  it("refuses an event whose sequence number is below 1, and says what the rule is", () => {
    // It proves that the first rule of the sequence is enforced: a sequence number below 1 is refused, and the reason
    // says where the sequence starts.
    const result = validateTraceEvent(eventWith({ seq: 0 }));

    expect(result.ok).toBe(false);
    expect(result.ok ? [] : result.reasons).toHaveLength(1);
    expect(result.ok ? "" : result.reasons[0]).toContain("seq");
    expect(result.ok ? "" : result.reasons[0]).toContain("starts at 1");
  });

  it("refuses an event whose sequence number is not a whole number", () => {
    // It proves that the sequence of a recording is made of whole numbers: a sequence number of 1.5 is refused with the
    // reason that names the field.
    const result = validateTraceEvent(eventWith({ seq: 1.5 }));

    expect(result.ok).toBe(false);
    expect(result.ok ? "" : result.reasons[0]).toContain("seq");
    expect(result.ok ? "" : result.reasons[0]).toContain("int");
  });

  it("accepts an event whose sequence number starts at 1", () => {
    // It proves that the refusal of the case above is the refusal of the rule and not the refusal of the shape of the
    // event: the same event with the first sequence number of the contract is accepted.
    const result = validateTraceEvent(eventWith({ seq: 1 }));

    expect(result.ok).toBe(true);
    expect(result.ok ? result.value.seq : 0).toBe(1);
  });
});

describe("the snapshot hash of an event", () => {
  it("refuses an event whose snapshot hash is not 64 lowercase hexadecimal characters", () => {
    // It proves that a hash in another case is refused: the hash of a snapshot is the key of the artifact, and a key
    // that is written in another case is a key that does not match.
    const result = validateTraceEvent(eventWith({ snapshot_sha256: SNAPSHOT_SHA256.toUpperCase() }));

    expect(result.ok).toBe(false);
    expect(result.ok ? "" : result.reasons[0]).toContain("snapshot_sha256");
    expect(result.ok ? "" : result.reasons[0]).toContain("64 lowercase hexadecimal characters");
  });

  it("refuses an event whose snapshot hash is too short", () => {
    // It proves that the rule is about the shape of the hash and not only about its case: a hash of three characters is
    // refused with the same reason.
    const result = validateTraceEvent(eventWith({ snapshot_sha256: "abc" }));

    expect(result.ok).toBe(false);
    expect(result.ok ? "" : result.reasons[0]).toContain("snapshot_sha256");
    expect(result.ok ? "" : result.reasons[0]).toContain("64 lowercase hexadecimal characters");
  });

  it("accepts an event whose snapshot hash is 64 lowercase hexadecimal characters", () => {
    // It proves that the hash of the published bundle is accepted word for word.
    const result = validateTraceEvent(eventWith({ snapshot_sha256: SNAPSHOT_SHA256 }));

    expect(result.ok).toBe(true);
    expect(result.ok ? result.value.snapshot_sha256 : "").toBe(SNAPSHOT_SHA256);
  });
});

describe("the mode", () => {
  it("refuses a manifest whose mode is undefined", () => {
    // It proves that the mode of a bundle is never left undefined: the manifest says in words what the recording was,
    // and a manifest without a mode says nothing.
    const result = validateManifest({ ...VALID_MANIFEST, mode: undefined });

    expect(result.ok).toBe(false);
    expect(result.ok ? "" : result.reasons[0]).toContain("mode");
    expect(result.ok ? "" : result.reasons[0]).toContain("recorded_replay");
  });

  it("refuses a bundle whose result has no mode", () => {
    // It proves that the result of a recorded run also carries its mode, because the mode is the label that tells a
    // recording from a live run.
    const result = validateBundle({
      ...VALID_BUNDLE,
      run_result: { ...VALID_RESULT, mode: undefined },
    });

    expect(result.ok).toBe(false);
    expect(result.ok ? "" : result.reasons[0]).toContain("run_result.mode");
  });

  it("refuses an event whose mode is not one of the three modes of the contract", () => {
    // It proves that a mode the contract does not publish is refused, and that the reason names the three modes a
    // reader can choose from.
    const result = validateTraceEvent(eventWith({ mode: "teleport" }));

    expect(result.ok).toBe(false);
    expect(result.ok ? "" : result.reasons[0]).toContain("mode");
    expect(result.ok ? "" : result.reasons[0]).toContain("deterministic_sandbox");
  });

  it("accepts an event that carries no mode, because the trace contract makes the mode optional", () => {
    // It proves what the contract really says: the mode of a single event is optional, so an event of a bundle that
    // was written without a mode is accepted and simply carries none.
    const result = validateTraceEvent(eventWith({ mode: undefined }));

    expect(result.ok).toBe(true);
    expect(result.ok ? result.value.mode : "a mode").toBeUndefined();
  });
});

describe("the type of an event", () => {
  it("refuses an event whose type is undefined", () => {
    // It proves that an event without a type is refused: the interface reads the type to know what to do with the event,
    // and an event without a type says nothing.
    const result = validateTraceEvent(eventWith({ event_type: undefined }));

    expect(result.ok).toBe(false);
    expect(result.ok ? "" : result.reasons[0]).toContain("event_type");
    expect(result.ok ? "" : result.reasons[0]).toContain("run.started");
  });

  it("refuses an event whose type is not one of the eleven types of the contract", () => {
    // It proves that a type the contract does not publish is refused with the list of the types it does publish, so that
    // the reader of the reason knows what a valid type looks like.
    const result = validateTraceEvent(eventWith({ event_type: "span.retried" }));

    expect(result.ok).toBe(false);
    expect(result.ok ? "" : result.reasons[0]).toContain("event_type");
    expect(result.ok ? "" : result.reasons[0]).toContain("heartbeat");
  });
});

describe("the count of the events against the count the manifest declares", () => {
  it("refuses a manifest whose count of events is not a whole number", () => {
    // It proves that the count a manifest declares is a whole number: a count of 2.5 is refused and the reason names
    // the field.
    const result = validateManifest({ ...VALID_MANIFEST, events: 2.5 });

    expect(result.ok).toBe(false);
    expect(result.ok ? "" : result.reasons[0]).toContain("events");
  });

  it("refuses a manifest that declares a negative count of events", () => {
    // It proves that a manifest cannot declare less than no event at all.
    const result = validateManifest({ ...VALID_MANIFEST, events: -1 });

    expect(result.ok).toBe(false);
    expect(result.ok ? "" : result.reasons[0]).toContain("events");
  });

  it("does not compare the count of the events of a bundle with the count its manifest declares", () => {
    // It proves the state of the contract in the web today, and it says out loud that this is a gap: the manifest and
    // the events are two artifacts that the validator checks one by one, and nothing in the web compares the count that
    // the manifest declares with the count of the events that were read. The rule that refuses a bundle whose count does
    // not match lives in the Python core (`ledgerlens/replay/bundle.py`), and the web does not have it yet. The case
    // pins that gap down, so that the day the web gains the rule, the case says so.
    const manifest = validateManifest({ ...VALID_MANIFEST, events: 5 });
    const events = validateTraceEvents([VALID_EVENT]);

    expect(manifest.ok).toBe(true);
    expect(events.ok).toBe(true);
    expect(manifest.ok ? manifest.value.events : 0).toBe(5);
    expect(events.ok ? events.value.length : 0).toBe(1);
  });
});

describe("the reasons of a refusal", () => {
  it("gives every refusal a reason that names the field that failed and the rule it broke", () => {
    // It proves that every refusal of the module carries a reason a reader can act on: the reason names the artifact,
    // the field and the rule, so that a visitor is never told only that something is wrong.
    const refusals: ReadonlyArray<{ readonly outcome: unknown; readonly prefix: string }> = [
      { outcome: validateTraceEvent(eventWith({ seq: 0 })), prefix: "event: " },
      { outcome: validateTraceEvent(eventWith({ snapshot_sha256: "abc" })), prefix: "event: " },
      { outcome: validateTraceEvent(eventWith({ mode: "teleport" })), prefix: "event: " },
      { outcome: validateTraceEvent(eventWith({ event_type: "span.retried" })), prefix: "event: " },
      { outcome: validateManifest({ ...VALID_MANIFEST, mode: undefined }), prefix: "manifest: " },
      { outcome: validateManifest({ ...VALID_MANIFEST, events: 2.5 }), prefix: "manifest: " },
      { outcome: validateBundle({ ...VALID_BUNDLE, scenario_id: "s1" }), prefix: "bundle: " },
      { outcome: validateResult({ ...VALID_RESULT, verification_status: "unknown" }), prefix: "result: " },
      { outcome: validateScenarioIndexEntry({ id: "S1", name: "a", question: "a" }), prefix: "scenario: " },
    ];

    for (const refusal of refusals) {
      const result = refusal.outcome as ValidationResult<unknown>;
      const reasons = result.ok ? [] : result.reasons;

      expect(result.ok).toBe(false);
      expect(reasons.length).toBeGreaterThan(0);
      for (const reason of reasons) {
        expect(reason.startsWith(refusal.prefix)).toBe(true);
        expect(reason).toMatch(/: [a-zA-Z_][a-zA-Z_0-9]*(\.[a-zA-Z_][a-zA-Z_0-9]*)*(\[[0-9]+\])?: .+/);
      }
    }
  });

  it("never throws at the caller, whatever it is given", () => {
    // It proves that the validators answer and never raise: the page that calls them has to show a reason to a visitor
    // and not an exception to a log.
    const validators: ReadonlyArray<(input: unknown) => unknown> = [
      validateTraceEvent,
      validateTraceEvents,
      validateManifest,
      validateResult,
      validateBundle,
      validateScenarioIndex,
      validateScenarioIndexEntry,
    ];
    const hostile: readonly unknown[] = [
      null,
      undefined,
      42,
      "a text",
      [],
      {},
      { schema_version: "1" },
      { run_id: "" },
      { events: "not a list" },
    ];

    for (const validator of validators) {
      for (const input of hostile) {
        let outcome: unknown;
        expect(() => {
          outcome = validator(input);
        }).not.toThrow();

        const result = outcome as ValidationResult<unknown>;
        expect(typeof result.ok).toBe("boolean");
        if (!result.ok) {
          expect(result.reasons.length).toBeGreaterThan(0);
          expect(result.reasons.every((reason) => typeof reason === "string" && reason.length > 0)).toBe(true);
        }
      }
    }
  });

  it("carries the reasons with the refusal and no value", () => {
    // It proves that a refusal travels with its reasons: the caller reads the reasons from the refusal and never from a
    // value that is not there.
    const result = validateTraceEvent(eventWith({ seq: 0 }));

    expect(result.ok).toBe(false);
    expect("value" in result).toBe(false);
    expect(result.ok ? [] : result.reasons.length).toBeGreaterThan(0);
  });

  it("gives the reasons of every event of a list with the refusal of the list", () => {
    // It proves that a list with more than one broken event is refused with the whole list of reasons and not only with
    // the first one, so that a reader sees every problem of the recording.
    const result = validateTraceEvents([
      eventWith({ seq: 0 }),
      VALID_EVENT,
      eventWith({ event_type: "span.retried" }),
    ]);
    const reasons = result.ok ? [] : result.reasons;

    expect(result.ok).toBe(false);
    expect(reasons).toHaveLength(2);
    expect(reasons[0]).toContain("events[0]: ");
    expect(reasons[1]).toContain("events[2]: ");
  });

  it("refuses a list of events that is not a list", () => {
    // It proves that the list of the events of a bundle is a list, and that the reason of the refusal says so.
    const result = validateTraceEvents("not a list");

    expect(result.ok).toBe(false);
    expect(result.ok ? "" : result.reasons[0]).toContain("the events must be a list");
  });
});

describe("the metadata of the route of a scenario", () => {
  it("gives the route a title and a description that name the scenario", async () => {
    // It proves that the route of a scenario names the scenario it publishes: the title carries the identifier of the
    // scenario and the question of the catalog, and the description says what the page is.
    const metadata = await scenarioMetadata("S01");

    expect(typeof metadata.title).toBe("string");
    expect(metadata.title as string).toContain("S01");
    expect(metadata.title as string).toContain("TX-2048");
    expect(typeof metadata.description).toBe("string");
    expect(metadata.description as string).toContain("S01");
  });

  it("gives a title and a description to a scenario the catalog does not publish", async () => {
    // It proves that the route answers for an identifier the catalog does not publish, because the metadata of a route
    // is read before the page decides that the scenario does not exist.
    const metadata = await scenarioMetadata("S99");

    expect(typeof metadata.title).toBe("string");
    expect((metadata.title as string).length).toBeGreaterThan(0);
    expect(typeof metadata.description).toBe("string");
    expect(metadata.description as string).toContain("S99");
  });
});
