/**
 * The test of the provenance and of the integrity in the state of the replay.
 *
 * Why this test exists: the panel of the provenance reads the digest of the bundle and the state of the check of the
 * integrity from the STATE of the replay, and the state is the only place those two facts can live. The digest of the
 * bundle is published by the file of the provenance and by nothing else, and the state of the check is a fact about the
 * browser that computed the digests. A state that drops either of them makes the panel say "Not available" about a
 * digest that the artifact publishes, or say that a bundle was not verified when its digests were really compared
 * (ADR-043).
 *
 * Why the rule is checked twice: once on the reducer, which is the pure machine that holds the state, and once on the
 * provider, which is the state as the interface of the site reads it. A rule that only the provider honours is a rule
 * the machine can break without anybody noticing.
 *
 * Every case runs with no key and no network: the loader of the case is a function of the test that answers with a
 * bundle the test holds.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReplayProvider, replayReducer, useReplay, type ReplayState } from "@/features/replay/ReplayProvider";
import type { LoadedReplay } from "@/lib/api/replay";
import type { ReplayBundleManifest, ScenarioIndexEntry, TraceEvent } from "@/lib/api/schemas";

/** The card of the scenario in the published catalog, as `site/replay/index.json` holds it. */
const SCENARIO: ScenarioIndexEntry = {
  id: "S01",
  name: "fx_markup_refund",
  question: "Why was the BRL refund for TX-2048 lower than the EUR payment?",
  concepts: ["read_only_ledger_query", "policy_retrieval"],
  data_origin: "UCI Online Retail II",
  status: "Recorded",
  capture_kind: "scripted_fixture",
  bundle_path: "s01",
};

/** The manifest of the published bundle, as `site/replay/s01/manifest.json` holds it. */
const MANIFEST: ReplayBundleManifest = {
  bundle_schema_version: "1",
  capture_kind: "scripted_fixture",
  code_sha: "9dc3af946b223496c7ed2e897b1e4152bbf9234f",
  created_at: "2026-11-14T11:00:14+00:00",
  events: 2,
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

/** One event of the recording, with the shape the contract publishes. */
function traceEvent(seq: number, eventType: TraceEvent["event_type"]): TraceEvent {
  return {
    schema_version: "1",
    run_id: "replay-s01",
    seq,
    at: "2026-11-14T11:00:14.051+00:00",
    event_type: eventType,
    span_id: "span-investigate",
    parent_span_id: null,
    payload: { name: "investigate", run_type: "chain" },
    snapshot_sha256: "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
    mode: "deterministic_sandbox",
  };
}

/** The two events of the fixture, as the recording carries them. */
const EVENTS: readonly TraceEvent[] = [traceEvent(1, "span.started"), traceEvent(2, "span.ended")];

/**
 * The digest of the bundle, as the file of the provenance publishes it.
 *
 * Why the digest is the one of the published bundle: the panel of the provenance shows the digest that the artifact
 * publishes, and a case that invented one would prove nothing about the rule.
 */
const BUNDLE_DIGEST = "bbbe1e54fcae712df66a3a6096838ab5b7f8c938e2e47b7ef6681e43cafa84ac";

/** The provenance file of the fixture, with the digest of the bundle that it publishes. */
const PROVENANCE: Record<string, unknown> = {
  bundle_digest: BUNDLE_DIGEST,
  files: { "events.jsonl": "577939e532327f3af1a3897612f622d96edc27a620646437fb02c5fa5318de13" },
};

/** The state the machine starts in, before anything was loaded. */
const IDLE: ReplayState = {
  phase: "idle",
  scenario: null,
  manifest: null,
  events: [],
  position: 0,
  error: null,
  refusalReasons: [],
};

/**
 * A probe that shows the provenance and the integrity of the state of the machine.
 *
 * Why the probe reads the state and not the panel: the rule is about the state, and the panel is only one of the
 * readers of it.
 */
function Probe(): React.ReactElement {
  const { state } = useReplay();
  const digest = state.provenance?.["bundle_digest"];
  return (
    <div>
      <span data-testid="digest">{typeof digest === "string" ? digest : ""}</span>
      <span data-testid="integrity">{state.integrity ?? ""}</span>
      <span data-testid="provenance">{state.provenance === null ? "none" : "some"}</span>
    </div>
  );
}

describe("the provenance in the state of the replay", () => {
  it("keeps the provenance of the bundle when the bundle was loaded", () => {
    // It proves that the action `loaded` carries the provenance of the bundle into the state, because the digest of the
    // bundle lives in that file and in nowhere else. A state that drops it shows "Not available" about a digest that the
    // artifact publishes, and that panel says something false about the artifact (ADR-043).
    const ready = replayReducer(IDLE, {
      type: "loaded",
      manifest: MANIFEST,
      events: EVENTS,
      provenance: PROVENANCE,
    });

    expect(ready.provenance).not.toBeNull();
    expect(ready.provenance?.["bundle_digest"]).toBe(BUNDLE_DIGEST);
  });

  it("empties the provenance of the bundle when the artifact is refused", () => {
    // It proves that a refused artifact leaves no provenance behind: a stale digest is a claim about a bundle that is
    // not on the screen (ADR-043).
    const ready = replayReducer(
      replayReducer(IDLE, {
        type: "loaded",
        manifest: MANIFEST,
        events: EVENTS,
        provenance: PROVENANCE,
      }),
      { type: "refused", reason: "the bundle did not pass the contract" },
    );

    expect(ready.provenance).toBeNull();
  });

  it("hands the provenance of the bundle to the state of the provider", async () => {
    // It proves that the state as the interface of the site reads it carries the digest that the artifact publishes.
    const loader = vi.fn(async (): Promise<LoadedReplay> => ({
      manifest: MANIFEST,
      events: EVENTS,
      provenance: PROVENANCE,
      integrity: "checked",
    }));

    render(
      <ReplayProvider scenario={SCENARIO} loader={loader}>
        <Probe />
      </ReplayProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("provenance")).toHaveTextContent("some");
    });
    expect(screen.getByTestId("digest")).toHaveTextContent(BUNDLE_DIGEST);
  });
});

describe("the integrity in the state of the replay", () => {
  it("keeps the state of the check when the digests were compared", () => {
    // It proves that the state carries the verdict of the check: a bundle whose digests were compared is a bundle
    // whose integrity was checked, and the panel never says the opposite (ADR-043).
    const ready = replayReducer(IDLE, {
      type: "loaded",
      manifest: MANIFEST,
      events: EVENTS,
      provenance: PROVENANCE,
      integrity: "checked",
    });

    expect(ready.integrity).toBe("checked");
  });

  it("keeps the state of the check unknown when the bundle carries none", () => {
    // It proves that a bundle that carries no integrity is a bundle whose integrity is UNKNOWN: never a bundle that
    // was checked and never a bundle that was refused (ADR-043).
    const ready = replayReducer(IDLE, {
      type: "loaded",
      manifest: MANIFEST,
      events: EVENTS,
      provenance: PROVENANCE,
    });

    expect(ready.integrity).toBe("unknown");
  });

  it("empties the state of the check when the artifact is refused", () => {
    // It proves that a refused artifact leaves no integrity behind, because a stale integrity is a claim about a bundle
    // that is not on the screen (ADR-043).
    const ready = replayReducer(
      replayReducer(IDLE, {
        type: "loaded",
        manifest: MANIFEST,
        events: EVENTS,
        provenance: PROVENANCE,
        integrity: "checked",
      }),
      { type: "refused", reason: "the bundle did not pass the contract" },
    );

    expect(ready.integrity).toBeUndefined();
  });

  it("hands the state of the check to the state of the provider", async () => {
    // It proves that the state as the interface of the site reads it carries the verdict of the check of the digests.
    const loader = vi.fn(async (): Promise<LoadedReplay> => ({
      manifest: MANIFEST,
      events: EVENTS,
      provenance: PROVENANCE,
      integrity: "checked",
    }));

    render(
      <ReplayProvider scenario={SCENARIO} loader={loader}>
        <Probe />
      </ReplayProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("integrity")).toHaveTextContent("checked");
    });
  });
});
