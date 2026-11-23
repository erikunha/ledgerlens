/**
 * The test of the state machine of the replay.
 *
 * Why this test exists: the state of the replay is the promise that the same position of the recording always shows
 * the same thing, and that a broken artifact never shows half of a run. The machine has six phases, its reducer is
 * pure, and a refusal empties the events, the manifest and the position, so that no partial render is possible.
 *
 * Every case runs with no key and no network: the loader of the case is a function of the test that answers with the
 * artifacts the repository publishes.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ReplayProvider,
  replayReducer,
  useReplay,
  type ReplayAction,
  type ReplayState,
} from "@/features/replay/ReplayProvider";
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
 * The provenance file of the fixture, with the digest of the bundle that it publishes.
 *
 * Why the digest is here: the digest of the bundle lives in the provenance file and nowhere else, and the panel of the
 * provenance shows it from there. A state that does not carry the provenance carries no digest, and the panel then says
 * "Not available" about a digest that the artifact publishes (ADR-043).
 */
const PROVENANCE: Record<string, unknown> = {
  bundle_digest: "bbbe1e54fcae712df66a3a6096838ab5b7f8c938e2e47b7ef6681e43cafa84ac",
};

/** The bundle that the loader of the case answers with. */
const LOADED: LoadedReplay = {
  manifest: MANIFEST,
  events: EVENTS,
  provenance: PROVENANCE,
  integrity: "checked",
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
 * A probe that shows the state of the machine and the actions a case can send to it.
 *
 * Why the probe is a component: the state of the machine lives in the provider, and a case has to read it the way a
 * component of the interface reads it.
 *
 * Why the probe shows the provenance and the integrity: the panel of the provenance reads them from the state, and a
 * probe that does not show them cannot tell a state that keeps them from a state that throws them away. The digest
 * shown is the one the provenance file publishes, and the integrity is the state of the check itself.
 */
function Probe(): React.ReactElement {
  const { state, dispatch } = useReplay();
  const digest = state.provenance?.["bundle_digest"];
  return (
    <div>
      <span data-testid="phase">{state.phase}</span>
      <span data-testid="position">{state.position}</span>
      <span data-testid="error">{state.error ?? ""}</span>
      <span data-testid="events">{state.events.length}</span>
      <span data-testid="manifest">{state.manifest?.run_id ?? ""}</span>
      <span data-testid="digest">{typeof digest === "string" ? digest : ""}</span>
      <span data-testid="integrity">{state.integrity ?? ""}</span>
      <button type="button" onClick={() => dispatch({ type: "play" })}>
        play
      </button>
      <button type="button" onClick={() => dispatch({ type: "pause" })}>
        pause
      </button>
      <button type="button" onClick={() => dispatch({ type: "completed" })}>
        completed
      </button>
      <button type="button" onClick={() => dispatch({ type: "step", delta: 1 })}>
        next
      </button>
      <button type="button" onClick={() => dispatch({ type: "step", delta: -1 })}>
        previous
      </button>
      <button type="button" onClick={() => dispatch({ type: "reset" })}>
        reset
      </button>
    </div>
  );
}

/** The loader of the case: it answers with the bundle and counts how many times it was called. */
function countingLoader(answer: LoadedReplay | { error: string }) {
  const calls: ScenarioIndexEntry[] = [];
  const loader = vi.fn(async (index: ScenarioIndexEntry) => {
    calls.push(index);
    return answer;
  });
  return { loader, calls };
}

afterEach(() => {
  // the clock of the case is put back where it was, so that a case that moved it never reaches the case that runs
  // after it
  vi.useRealTimers();
});

describe("the state machine of the replay", () => {
  it("goes from idle to loading to ready", () => {
    // It proves that the machine shows the loading of the bundle before it shows the recording.
    const state = replayReducer(IDLE, { type: "load", scenario: SCENARIO });

    expect(state.phase).toBe("loading");
    expect(state.scenario).toBe(SCENARIO);
    expect(state.events).toEqual([]);
    expect(state.position).toBe(0);
    expect(state.error).toBeNull();
  });

  it("goes from loading to ready with the events of the recording", () => {
    // It proves that the machine is ready once the bundle was read and accepted.
    const loading = replayReducer(IDLE, { type: "load", scenario: SCENARIO });
    const ready = replayReducer(loading, { type: "loaded", manifest: MANIFEST, events: EVENTS });

    expect(ready.phase).toBe("ready");
    expect(ready.manifest).toBe(MANIFEST);
    expect(ready.events).toHaveLength(2);
    expect(ready.error).toBeNull();
  });

  it("is ready even when the bundle carries no event", () => {
    // It proves that the empty state is a state of the reader and not an error of the loader.
    const loading = replayReducer(IDLE, { type: "load", scenario: SCENARIO });
    const ready = replayReducer(loading, { type: "loaded", manifest: MANIFEST, events: [] });

    expect(ready.phase).toBe("ready");
    expect(ready.events).toEqual([]);
    expect(ready.error).toBeNull();
  });

  it("goes from ready to playing, to paused and to completed", () => {
    // It proves that the machine walks through the phases of the playback.
    const ready = replayReducer(
      replayReducer(IDLE, { type: "load", scenario: SCENARIO }),
      { type: "loaded", manifest: MANIFEST, events: EVENTS },
    );

    const playing = replayReducer(ready, { type: "play" });
    expect(playing.phase).toBe("playing");

    const paused = replayReducer(playing, { type: "pause" });
    expect(paused.phase).toBe("paused");

    const completed = replayReducer(playing, { type: "completed" });
    expect(completed.phase).toBe("completed");
  });

  it("moves the position and stays in the same phase", () => {
    // It proves that a seek does not change what the machine is doing.
    const ready = replayReducer(
      replayReducer(IDLE, { type: "load", scenario: SCENARIO }),
      { type: "loaded", manifest: MANIFEST, events: EVENTS },
    );

    const sought = replayReducer(ready, { type: "seek", position: 1 });

    expect(sought.phase).toBe("ready");
    expect(sought.position).toBe(1);
  });

  it("clamps the position to the range of the events", () => {
    // It proves that a position outside the recording never shows a state that does not exist.
    const ready = replayReducer(
      replayReducer(IDLE, { type: "load", scenario: SCENARIO }),
      { type: "loaded", manifest: MANIFEST, events: EVENTS },
    );

    expect(replayReducer(ready, { type: "seek", position: 99 }).position).toBe(1);
    expect(replayReducer(ready, { type: "seek", position: -5 }).position).toBe(0);
  });

  it("moves the completed machine back to paused when the visitor goes back into the recording", () => {
    // It proves that a visitor who steps back into the recording is not told that the recording is over.
    const completed = replayReducer(
      replayReducer(
        replayReducer(
          replayReducer(IDLE, { type: "load", scenario: SCENARIO }),
          { type: "loaded", manifest: MANIFEST, events: EVENTS },
        ),
        { type: "play" },
      ),
      { type: "completed" },
    );

    expect(replayReducer(completed, { type: "step", delta: -1 }).phase).toBe("paused");
  });

  it("returns to ready with the position at zero when it is reset", () => {
    // It proves that the reset goes back to the beginning of the recording.
    const played = replayReducer(
      replayReducer(
        replayReducer(
          replayReducer(IDLE, { type: "load", scenario: SCENARIO }),
          { type: "loaded", manifest: MANIFEST, events: EVENTS },
        ),
        { type: "play" },
      ),
      { type: "seek", position: 1 },
    );

    const reset = replayReducer(played, { type: "reset" });

    expect(reset.phase).toBe("ready");
    expect(reset.position).toBe(0);
    expect(reset.events).toHaveLength(2);
    expect(reset.manifest).toBe(MANIFEST);
  });

  it("empties the events, the manifest and the position when the artifact is refused", () => {
    // It proves that a refused artifact leaves the machine with no events and with the reason, so that no partial
    // render is possible.
    const ready = replayReducer(
      replayReducer(IDLE, { type: "load", scenario: SCENARIO }),
      { type: "loaded", manifest: MANIFEST, events: EVENTS },
    );

    const refused = replayReducer(ready, { type: "refused", reason: "the bundle did not pass the contract" });

    expect(refused.phase).toBe("idle");
    expect(refused.events).toEqual([]);
    expect(refused.manifest).toBeNull();
    expect(refused.position).toBe(0);
    expect(refused.error).toBe("the bundle did not pass the contract");
  });

  it("is pure, so that the same sequence of actions ends in the same state", () => {
    // It proves the purity of the reducer for real: the two walks of the case happen at two different moments of the
    // clock, and the states they end in are the same. A reducer that stamped the state with the clock, or that drew a
    // random number, would end in two different states here, and the case would fail.
    //
    // Why the clock of the case is a fake one: the case holds the clock still and moves it on purpose, so the two walks
    // really happen at two different moments and the difference of the states is the difference of the reducer and
    // nothing else. A case that compared two walks of the same moment would prove nothing at all.
    vi.useFakeTimers();
    const random = vi.spyOn(Math, "random");

    const actions: ReplayAction[] = [
      { type: "load", scenario: SCENARIO },
      { type: "loaded", manifest: MANIFEST, events: EVENTS },
      { type: "play" },
      { type: "seek", position: 1 },
      { type: "pause" },
      { type: "step", delta: -1 },
    ];
    const walk = (): ReplayState => actions.reduce(replayReducer, IDLE);

    vi.setSystemTime(new Date("2026-11-21T12:00:00.000Z"));
    const first = walk();

    vi.setSystemTime(new Date("2026-11-21T12:05:00.000Z"));
    const second = walk();

    // the states themselves are compared, and not two walks of the same moment
    expect(second).toEqual(first);
    expect(JSON.stringify(second)).toBe(JSON.stringify(first));

    // the reducer draws no random number
    expect(random).not.toHaveBeenCalled();
  });

  it("keeps the provenance of the bundle in the state", async () => {
    // It proves that the state carries the provenance of the bundle, because the panel of the provenance needs it: a
    // state that drops it shows "Not available" for a digest that the artifact publishes (ADR-043).
    const { loader } = countingLoader(LOADED);

    render(
      <ReplayProvider scenario={SCENARIO} loader={loader}>
        <Probe />
      </ReplayProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("phase")).toHaveTextContent("ready");
    });
    expect(screen.getByTestId("digest")).toHaveTextContent(
      "bbbe1e54fcae712df66a3a6096838ab5b7f8c938e2e47b7ef6681e43cafa84ac",
    );
  });

  it("keeps the integrity of the bundle in the state when the digests were checked", async () => {
    // It proves that the state carries the state of the check, so that the panel can say that the integrity WAS
    // checked and never that it was not (ADR-043).
    const { loader } = countingLoader(LOADED);

    render(
      <ReplayProvider scenario={SCENARIO} loader={loader}>
        <Probe />
      </ReplayProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("phase")).toHaveTextContent("ready");
    });
    expect(screen.getByTestId("integrity")).toHaveTextContent("checked");
  });

  it("keeps the integrity of the bundle unknown when the bundle carries no state of the check", async () => {
    // It proves that a bundle that carries no integrity is a bundle whose integrity is UNKNOWN: never a bundle that
    // was checked and never a bundle that was refused (ADR-043).
    const { loader } = countingLoader({ manifest: MANIFEST, events: EVENTS, provenance: PROVENANCE });

    render(
      <ReplayProvider scenario={SCENARIO} loader={loader}>
        <Probe />
      </ReplayProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("phase")).toHaveTextContent("ready");
    });
    expect(screen.getByTestId("integrity")).toHaveTextContent("unknown");
  });

  it("loads the bundle of the scenario and shows it ready", async () => {
    // It proves that the provider reads the bundle of the scenario and hands the state to the interface.
    const { loader, calls } = countingLoader(LOADED);

    render(
      <ReplayProvider scenario={SCENARIO} loader={loader}>
        <Probe />
      </ReplayProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("phase")).toHaveTextContent("ready");
    });
    expect(screen.getByTestId("events")).toHaveTextContent("2");
    expect(screen.getByTestId("manifest")).toHaveTextContent("replay-s01");
    expect(calls).toHaveLength(1);
  });

  it("never reloads the bundle when it is reset", async () => {
    // It proves that the reset returns to the beginning of the recording that is already in the machine.
    const { loader, calls } = countingLoader(LOADED);
    const user = userEvent.setup();

    render(
      <ReplayProvider scenario={SCENARIO} loader={loader}>
        <Probe />
      </ReplayProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("phase")).toHaveTextContent("ready");
    });

    await user.click(screen.getByRole("button", { name: "next" }));
    await waitFor(() => {
      expect(screen.getByTestId("position")).toHaveTextContent("1");
    });

    await user.click(screen.getByRole("button", { name: "reset" }));

    await waitFor(() => {
      expect(screen.getByTestId("phase")).toHaveTextContent("ready");
    });
    expect(screen.getByTestId("position")).toHaveTextContent("0");
    expect(calls).toHaveLength(1);
  });

  it("walks through the phases of the playback inside the provider", async () => {
    // It proves that the phases of the machine are the ones the interface of the playback uses.
    const { loader } = countingLoader(LOADED);
    const user = userEvent.setup();

    render(
      <ReplayProvider scenario={SCENARIO} loader={loader}>
        <Probe />
      </ReplayProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("phase")).toHaveTextContent("ready");
    });

    await user.click(screen.getByRole("button", { name: "play" }));
    await waitFor(() => {
      expect(screen.getByTestId("phase")).toHaveTextContent("playing");
    });

    await user.click(screen.getByRole("button", { name: "pause" }));
    await waitFor(() => {
      expect(screen.getByTestId("phase")).toHaveTextContent("paused");
    });

    await user.click(screen.getByRole("button", { name: "play" }));
    await user.click(screen.getByRole("button", { name: "completed" }));
    await waitFor(() => {
      expect(screen.getByTestId("phase")).toHaveTextContent("completed");
    });
  });

  it("leaves the machine with no events and with the reason when the loader refuses the artifact", async () => {
    // It proves that a refused artifact shows the reason and never a partial render.
    const { loader } = countingLoader({ error: "the manifest of the scenario S01 did not pass the contract" });

    render(
      <ReplayProvider scenario={SCENARIO} loader={loader}>
        <Probe />
      </ReplayProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("error")).toHaveTextContent("did not pass the contract");
    });
    expect(screen.getByTestId("events")).toHaveTextContent("0");
    expect(screen.getByTestId("manifest")).toHaveTextContent("");
    expect(screen.getByTestId("phase")).toHaveTextContent("idle");
  });
});
