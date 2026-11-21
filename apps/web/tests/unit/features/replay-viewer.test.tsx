/**
 * The test of the reader of the recorded run.
 *
 * Why this test exists: the recorded demo is the half of the demo that works with no key and no
 * network, so the reader has to be honest about what it shows. It shows the mode of the manifest it
 * read and the note of the capture, and it never presents a recorded run as a live one. And when
 * the artifact is broken, it shows the reason instead of a half drawn run.
 *
 * Every case runs with no key and no network: the fetch of the case is a fake that answers with
 * the artifacts the repository publishes. The manifest of the case is the manifest of
 * `site/replay/s01/manifest.json` and the card of the case is the card of
 * `site/replay/index.json`, field by field, so that the test asserts the shape the site really
 * serves (ADR-042).
 */

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { loadReplay } from "@/features/replay/loadReplay";
import { ReplayViewer } from "@/features/replay/ReplayViewer";
import type { ReplayBundleManifest, ScenarioIndexEntry, TraceEvent } from "@/lib/api/schemas";

/** The manifest of the published bundle of the scenario S01, as `site/replay/s01/manifest.json` holds it. */
const MANIFEST: ReplayBundleManifest = {
  bundle_schema_version: "1",
  capture_kind: "scripted_fixture",
  code_sha: "9dc3af946b223496c7ed2e897b1e4152bbf9234f",
  created_at: "2026-11-14T11:00:14+00:00",
  events: 57,
  files: { "events.jsonl": "577939e532327f3af1a3897612f622d96edc27a620646437fb02c5fa5318de13" },
  mode: "deterministic_sandbox",
  model_profile: "scripted-fixture",
  note: "Deterministic execution of the scenario S01, account C-0412, with the scripted model and the recorded exchange rate. This is not a live execution and it calls no model.",
  policy_version: "policies-v1",
  recorded_at: "2026-11-14T11:00:14+00:00",
  run_id: "replay-s01",
  scenario: "S01",
  snapshot_sha256: "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
};

/** The card of the scenario in the catalog of the site, as `site/replay/index.json` holds it. */
const SCENARIO: ScenarioIndexEntry = {
  id: "S01",
  name: "fx_markup_refund",
  question: "Why was the BRL refund for TX-2048 lower than the EUR payment?",
  concepts: [
    "read_only_ledger_query",
    "policy_retrieval",
    "exchange_rate_reference",
    "decimal_calculation",
  ],
  data_origin: "UCI Online Retail II",
  status: "Recorded",
  capture_kind: "scripted_fixture",
  bundle_path: "s01",
};

/** One event of the recording, with the shape the contract publishes. */
function traceEvent(seq: number, eventType: TraceEvent["event_type"], payload: Record<string, unknown>): TraceEvent {
  return {
    schema_version: "1",
    run_id: "replay-s01",
    seq,
    at: "2026-11-14T11:00:13.128+00:00",
    event_type: eventType,
    payload,
    snapshot_sha256: "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
    mode: "deterministic_sandbox",
  };
}

/** The events of the recording: the plan, one tool call, the verdict and the end of the run. */
const EVENTS: TraceEvent[] = [
  traceEvent(1, "run.started", { question: SCENARIO.question }),
  traceEvent(2, "span.started", { name: "read_ledger", run_type: "tool", inputs: { transaction_id: "TX-2048" } }),
  traceEvent(3, "span.ended", {
    name: "read_ledger",
    run_type: "tool",
    status: "ok",
    latency_ms: 12,
    outputs: { evidence_ids: ["ev-1"] },
  }),
  traceEvent(4, "run.completed", { answer: "the answer of the agent" }),
];

/** A fake answer of the fetch, with only what the loader reads. */
function fakeResponse(body: string, ok = true): Response {
  return {
    ok,
    status: ok ? 200 : 404,
    text: async () => body,
  } as unknown as Response;
}

/** The fetch of the case: it answers with the artifacts of the repository. */
function fakeFetch(manifest: unknown, events: TraceEvent[]): typeof fetch {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("manifest.json")) {
      return fakeResponse(JSON.stringify(manifest));
    }
    if (url.endsWith("events.jsonl")) {
      return fakeResponse(events.map((event) => JSON.stringify(event)).join("\n"));
    }
    return fakeResponse("", false);
  }) as unknown as typeof fetch;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the reader of the recorded run", () => {
  it("shows the mode of the manifest and the note of the capture", async () => {
    vi.stubGlobal("fetch", fakeFetch(MANIFEST, EVENTS));

    render(<ReplayViewer scenario={SCENARIO} />);

    expect(await screen.findByText(/deterministic_sandbox/)).toBeInTheDocument();
    expect(screen.getByText(MANIFEST.note)).toBeInTheDocument();
  });

  it("never presents the recorded run as a live one", async () => {
    vi.stubGlobal("fetch", fakeFetch(MANIFEST, EVENTS));

    render(<ReplayViewer scenario={SCENARIO} />);

    const note = await screen.findByText(MANIFEST.note);
    const rest = (document.body.textContent ?? "").replace(note.textContent ?? "", "");
    expect(rest).not.toMatch(/live/i);
  });

  it("shows the reason of a refused artifact instead of a partial render", async () => {
    vi.stubGlobal("fetch", fakeFetch({ ...MANIFEST, mode: "not_a_mode" }, EVENTS));

    render(<ReplayViewer scenario={SCENARIO} />);

    expect(await screen.findByText(/refused/i)).toBeInTheDocument();
    expect(screen.queryByText(MANIFEST.note)).toBeNull();
  });

  it("refuses a bundle whose events are not trace events", async () => {
    const broken = [traceEvent(1, "run.started", {}), { ...traceEvent(2, "run.completed", {}), seq: 0 }];

    const loaded = await loadReplay(SCENARIO, fakeFetch(MANIFEST, broken));

    expect("error" in loaded).toBe(true);
  });

  it("reads the manifest and the events of the published bundle", async () => {
    const loaded = await loadReplay(SCENARIO, fakeFetch(MANIFEST, EVENTS));

    if (!("error" in loaded)) {
      expect(loaded.manifest.mode).toBe("deterministic_sandbox");
      expect(loaded.manifest.bundle_schema_version).toBe("1");
      expect(loaded.manifest.capture_kind).toBe("scripted_fixture");
      expect(loaded.events).toHaveLength(4);
      return;
    }
    throw new Error(`the loader refused the published bundle: ${loaded.error}`);
  });

  it("refuses a manifest that spells the version of the contract in another way", async () => {
    const otherSpelling: Record<string, unknown> = { ...MANIFEST, schema_version: "1" };
    delete otherSpelling["bundle_schema_version"];

    const loaded = await loadReplay(SCENARIO, fakeFetch(otherSpelling, EVENTS));

    expect("error" in loaded).toBe(true);
    if ("error" in loaded) {
      expect(loaded.error).toContain("bundle_schema_version");
    }
  });
});
