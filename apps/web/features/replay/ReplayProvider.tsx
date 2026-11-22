"use client";

/**
 * The state machine of the replay.
 *
 * Why this file exists: the reader of a recorded run has to show one of six situations, and the
 * rules that say which one it is have to live in one place. The reducer is PURE: it reads no
 * clock, it draws no random number and it touches nothing outside its arguments, so the same
 * sequence of actions always ends in the same state, and a test can prove it without a browser.
 *
 * Why a refused artifact leaves nothing behind: the action `refused` empties the events, empties
 * the manifest and puts the position at zero, so the reader cannot draw half of a run and call it
 * a run. A reader who cannot tell which parts of a run are true is worse off than a reader who
 * sees nothing (ADR-043). The same goes for the state of the integrity: a refused bundle leaves no
 * stale integrity behind, because a stale integrity is a claim about a bundle that is not on the
 * screen.
 *
 * Why the provider takes a loader: a unit test has to be able to answer with a bundle that is
 * broken, or with a refusal, without a network and without the published artifacts.
 */

import { createContext, useContext, useEffect, useMemo, useReducer, useRef } from "react";
import type { ReactElement, ReactNode } from "react";

import { loadReplay } from "@/lib/api/replay";
import type { BundleIntegrity, LoadedReplay } from "@/lib/api/replay";
import type { ReplayBundleManifest, ScenarioIndexEntry, TraceEvent } from "@/lib/api/schemas";

/**
 * The six situations of the reader of a recording.
 *
 * Why they are six and not more: the reader shows a loading, a recording at rest, a recording
 * that plays, a recording that was paused, a recording that reached its end and a failure.
 */
export type ReplayPhase = "idle" | "loading" | "ready" | "playing" | "paused" | "completed";

/**
 * The whole state of the replay.
 *
 * Why every field is there: the phase says what the reader shows, the scenario and the manifest
 * say what it is about, the events and the position say where it is, and the error and the reasons
 * say why there is nothing to show.
 */
export interface ReplayState {
  /** Where the reading of the bundle stands. */
  readonly phase: ReplayPhase;
  /** The scenario of the bundle that is being read. */
  readonly scenario: ScenarioIndexEntry | null;
  /** The manifest of the bundle, when it was read. */
  readonly manifest: ReplayBundleManifest | null;
  /** The events of the recording, in the order they were recorded. */
  readonly events: readonly TraceEvent[];
  /** The position of the visitor inside the recording. */
  readonly position: number;
  /** The reason of the refusal, when the bundle was refused. */
  readonly error: string | null;
  /** The reasons of the refusal, when the bundle carried more than one. */
  readonly refusalReasons: readonly string[];
  /**
   * The provenance file of the bundle, as the client of the artifacts read it.
   *
   * Why the state carries it: the provenance file publishes the digest of the bundle, and the panel
   * of the provenance shows that digest. A digest that the file publishes and the panel does not
   * show is a panel that hides the proof that the artifact is what it says it is.
   *
   * Why the field is optional: the field was added to the state after the state was written down,
   * so a state that was built before the field existed stays valid. The field is null when the
   * bundle publishes no provenance file.
   */
  readonly provenance?: Readonly<Record<string, unknown>> | null;
  /**
   * Whether the integrity of the bundle was really checked.
   *
   * Why the state carries it: the panel of the provenance has to say that the integrity was not
   * checked when the browser offered no Web Crypto, and the panel reads the state of the machine.
   *
   * Why the field is optional: the field was added to the state after the state was written down,
   * so a state that was built before the field existed stays valid. A bundle that carries no field
   * is a bundle whose integrity is unknown.
   */
  readonly integrity?: BundleIntegrity;
}

/**
 * The actions of the machine.
 *
 * Why they are the whole of the vocabulary: every change of the reader comes from one of them,
 * and the clock of the playback is one of them too, so the clock never rewrites the state.
 */
export type ReplayAction =
  | { readonly type: "load"; readonly scenario: ScenarioIndexEntry }
  | {
      readonly type: "loaded";
      readonly manifest: ReplayBundleManifest;
      readonly events: readonly TraceEvent[];
      /**
       * The provenance file of the bundle, when the client of the artifacts read one.
       *
       * Why the field is optional: a bundle that publishes no provenance file is still a bundle,
       * and the action of a loader that reads no file stays valid.
       */
      readonly provenance?: Readonly<Record<string, unknown>> | null;
      /**
       * Whether the integrity of the bundle was really checked.
       *
       * Why the field is optional: a loader that was written before the field existed stays
       * valid, and a bundle that carries no field is a bundle whose integrity is unknown.
       */
      readonly integrity?: BundleIntegrity;
    }
  | { readonly type: "refused"; readonly reason: string; readonly reasons?: readonly string[] }
  | { readonly type: "play" }
  | { readonly type: "pause" }
  | { readonly type: "seek"; readonly position: number }
  | { readonly type: "step"; readonly delta: -1 | 1 }
  | { readonly type: "reset" }
  | { readonly type: "completed" };

/** The state of a machine that has not read anything yet. */
const INITIAL_STATE: ReplayState = {
  phase: "idle",
  scenario: null,
  manifest: null,
  events: [],
  position: 0,
  error: null,
  refusalReasons: [],
  provenance: null,
  integrity: undefined,
};

/**
 * Keeps a position inside the range of the events.
 *
 * Why the range is the range of the events: a position outside it points at an event that does
 * not exist, and the reader would show a moment of the recording that never happened.
 */
function clampPosition(position: number, total: number): number {
  const last = Math.max(total - 1, 0);
  if (!Number.isFinite(position) || position < 0) {
    return 0;
  }
  if (position > last) {
    return last;
  }
  return position;
}

/**
 * The reducer of the machine of the replay.
 *
 * The reducer is pure: it reads no clock, it draws no random number and it touches nothing
 * outside its arguments. The same sequence of actions always ends in the same state.
 */
export function replayReducer(state: ReplayState, action: ReplayAction): ReplayState {
  switch (action.type) {
    case "load":
      return {
        ...state,
        phase: "loading",
        scenario: action.scenario,
        manifest: null,
        events: [],
        position: 0,
        error: null,
        refusalReasons: [],
        provenance: null,
        integrity: undefined,
      };

    case "loaded":
      return {
        ...state,
        phase: "ready",
        manifest: action.manifest,
        events: action.events,
        position: 0,
        error: null,
        refusalReasons: [],
        provenance: action.provenance ?? null,
        integrity: action.integrity ?? "unknown",
      };

    case "refused":
      return {
        ...state,
        phase: "idle",
        manifest: null,
        events: [],
        position: 0,
        error: action.reason,
        refusalReasons: action.reasons ?? [],
        provenance: null,
        integrity: undefined,
      };

    case "play":
      if (state.phase === "ready" || state.phase === "paused") {
        return { ...state, phase: "playing" };
      }
      return state;

    case "pause":
      if (state.phase === "playing") {
        return { ...state, phase: "paused" };
      }
      return state;

    case "seek": {
      const phase = state.phase === "completed" ? "paused" : state.phase;
      return { ...state, phase, position: clampPosition(action.position, state.events.length) };
    }

    case "step": {
      const phase = state.phase === "completed" ? "paused" : state.phase;
      return { ...state, phase, position: clampPosition(state.position + action.delta, state.events.length) };
    }

    case "reset":
      return { ...state, phase: "ready", position: 0, error: null, refusalReasons: [] };

    case "completed":
      if (state.phase === "playing") {
        return { ...state, phase: "completed" };
      }
      return state;

    default:
      return state;
  }
}

/**
 * The props of the provider of the replay.
 *
 * Why the scenario can be null: a page that shows the catalog of the scenarios has no bundle to
 * read yet, and the provider has to say so without a bundle.
 */
export interface ReplayProviderProps {
  /** What the provider renders around the reader. */
  readonly children: ReactNode;
  /** The scenario of the bundle to read, when there is one. */
  readonly scenario: ScenarioIndexEntry | null;
  /** The function that reads the bundle. The default reads the published one. */
  readonly loader?: (index: ScenarioIndexEntry) => Promise<LoadedReplay | { error: string }>;
}

/**
 * What the reader of the replay gets from the provider.
 *
 * Why the state and the view are both there: the state is the truth of the machine and the view is
 * what the screen shows. They are the same thing today, and they stay two names so that a screen
 * can read the one it needs.
 */
export interface UseReplayResult {
  /** The state of the machine. */
  readonly state: ReplayState;
  /** The action that moves the machine. */
  readonly dispatch: (action: ReplayAction) => void;
  /** The state as the screen shows it. */
  readonly view: ReplayState;
}

/** The context that holds the state of the machine. */
const ReplayContext = createContext<UseReplayResult | null>(null);

/**
 * The state of a scenario that the machine has not read yet.
 *
 * Why the state is derived and not only reduced: between the render that carries a new scenario
 * and the effect that reads it, the machine still holds the bundle of the previous scenario. The
 * screen must not draw that bundle under the new scenario, so the state of a scenario the machine
 * has not read is the empty loading state.
 */
function stateForScenario(state: ReplayState, scenarioId: string | null): ReplayState {
  if (scenarioId === null) {
    return {
      ...state,
      phase: "idle",
      manifest: null,
      events: [],
      position: 0,
      error: null,
      refusalReasons: [],
      integrity: undefined,
    };
  }
  if ((state.scenario?.id ?? null) === scenarioId) {
    return state;
  }
  return {
    ...state,
    phase: "loading",
    manifest: null,
    events: [],
    position: 0,
    error: null,
    refusalReasons: [],
    provenance: null,
    integrity: undefined,
  };
}

/**
 * The provider of the replay.
 *
 * The provider reads the bundle of the scenario when the scenario changes, and it reads it once.
 * The machine itself never reads anything: it only moves between the states that the reducer
 * knows.
 */
export function ReplayProvider(props: ReplayProviderProps): ReactElement {
  const { children, scenario, loader } = props;

  const [state, dispatch] = useReducer(replayReducer, INITIAL_STATE);

  // The scenario and the loader are kept in references, so that a caller that hands over a new
  // object does not make the provider read the bundle again. The reading is decided by the
  // identifier of the scenario alone.
  const scenarioRef = useRef<ScenarioIndexEntry | null>(scenario);
  scenarioRef.current = scenario;
  const loaderRef = useRef<ReplayProviderProps["loader"]>(loader);
  loaderRef.current = loader;

  const scenarioId = scenario?.id ?? null;

  useEffect(() => {
    const current = scenarioRef.current;
    if (!current) {
      return;
    }
    // The scenario is copied into a name of its own, so that the reading below keeps the scenario
    // even when the reference changes while the bundle is being read.
    const target: ScenarioIndexEntry = current;

    let alive = true;
    dispatch({ type: "load", scenario: target });

    async function read(): Promise<void> {
      const load = loaderRef.current ?? ((index: ScenarioIndexEntry) => loadReplay(index));

      let result: LoadedReplay | { error: string };
      try {
        result = await load(target);
      } catch {
        result = { error: `the bundle of the scenario ${target.id} could not be read` };
      }

      if (!alive) {
        return;
      }
      if ("error" in result) {
        dispatch({ type: "refused", reason: result.error });
        return;
      }
      dispatch({
        type: "loaded",
        manifest: result.manifest,
        events: result.events,
        provenance: result.provenance,
        integrity: result.integrity,
      });
    }

    void read();

    return () => {
      alive = false;
    };
  }, [scenarioId]);

  const view = stateForScenario(state, scenarioId);

  const value = useMemo<UseReplayResult>(
    () => ({ state: view, dispatch, view }),
    [view],
  );

  return <ReplayContext.Provider value={value}>{children}</ReplayContext.Provider>;
}

/**
 * Reads the state of the machine of the replay.
 *
 * Why it throws outside the provider: a reader that asks for a state that no provider holds has a
 * bug, and a bug that reads a state of nothing is a bug that hides.
 */
export function useReplay(): UseReplayResult {
  const value = useContext(ReplayContext);
  if (!value) {
    throw new Error("useReplay has to be called inside a ReplayProvider");
  }
  return value;
}

/** Every symbol this module exports, so that a reader sees the whole surface of the machine at once. */
export const __all__ = [
  "ReplayPhase",
  "ReplayState",
  "ReplayAction",
  "replayReducer",
  "ReplayProviderProps",
  "ReplayProvider",
  "UseReplayResult",
  "useReplay",
] as const;
