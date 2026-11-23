/**
 * The state of the view that the URL carries.
 *
 * Why this file exists: the URL of the replay carries the scenario identifier and the harmless preferences of the
 * view, and nothing else. The scenario identifier lives in the path, because a scenario is a place and not a
 * filter. The preferences live in the query string, and the query string carries exactly two keys: `tab` and
 * `speed`. Every other parameter is ignored, whatever it holds, so nothing a visitor can put in the URL ever reaches
 * the state of the interface.
 */

/**
 * The tabs of the replay, in the order they are shown.
 *
 * Why the ledger sits between the execution and the evidence: the reader sees what the run did, then
 * the rows it read, then what it gathered, then what it concluded and then the proof of the
 * recording (ADR-045).
 */
export const REPLAY_TABS = ["execution", "ledger", "evidence", "decision", "provenance"] as const;

/** One of the tabs of the replay. */
export type ReplayTab = (typeof REPLAY_TABS)[number];

/** The speeds the playback runs at. */
export const PLAYBACK_SPEEDS = [1, 2, 4] as const;

/** One of the speeds of the playback. */
export type PlaybackSpeed = (typeof PLAYBACK_SPEEDS)[number];

/** The preferences of the view that the URL carries. */
export interface ViewPreferences {
  /** The tab the visitor is looking at. */
  readonly tab: ReplayTab;
  /** The speed the playback runs at. */
  readonly speed: PlaybackSpeed;
}

/** The preferences of a visitor who changed nothing. */
export const DEFAULT_VIEW_PREFERENCES: ViewPreferences = { tab: "execution", speed: 1 };

/** The prefix of the path of a scenario. */
const SCENARIO_PATH_PREFIX = "/replay/scenario/";

/**
 * Says whether a word is one of the tabs of the replay.
 */
export function isReplayTab(value: string): value is ReplayTab {
  return (REPLAY_TABS as readonly string[]).includes(value);
}

/**
 * Says whether a number is one of the speeds of the playback.
 */
export function isPlaybackSpeed(value: number): value is PlaybackSpeed {
  return (PLAYBACK_SPEEDS as readonly number[]).includes(value);
}

/**
 * Reads the preferences of the view out of a query string.
 *
 * Only the keys `tab` and `speed` are read. Every other parameter is ignored, whatever it holds, and a field that is
 * absent or that carries a value the contract does not define falls back to its default.
 */
export function readViewPreferences(search: string): ViewPreferences {
  const params = new URLSearchParams(typeof search === "string" ? search : "");

  const tab = params.get("tab");
  const speed = params.get("speed");
  const parsedSpeed = speed === null ? Number.NaN : Number(speed);

  return {
    tab: tab !== null && isReplayTab(tab) ? tab : DEFAULT_VIEW_PREFERENCES.tab,
    speed: isPlaybackSpeed(parsedSpeed) ? parsedSpeed : DEFAULT_VIEW_PREFERENCES.speed,
  };
}

/**
 * Writes the preferences of the view as a query string, with the question mark in front.
 *
 * The keys are written in the order `tab` and then `speed`, and the query string is empty when the preferences are the
 * defaults, so that the URL of a visitor who changed nothing stays clean. The question mark is part of the returned
 * string, because the reader of the query string is the `search` of a location, and a browser always writes the
 * question mark in front of it: the write and the read are the inverse of one another, and the caller does not have
 * to know whether it has to add the question mark.
 */
export function writeViewPreferences(preferences: ViewPreferences): string {
  if (
    preferences.tab === DEFAULT_VIEW_PREFERENCES.tab &&
    preferences.speed === DEFAULT_VIEW_PREFERENCES.speed
  ) {
    return "";
  }
  const params = new URLSearchParams();
  params.set("tab", preferences.tab);
  params.set("speed", String(preferences.speed));
  return `?${params.toString()}`;
}

/**
 * Builds the path of a scenario, with the identifier as the catalog publishes it.
 */
export function scenarioPath(scenarioId: string): string {
  return `${SCENARIO_PATH_PREFIX}${encodeURIComponent(scenarioId)}`;
}

/**
 * Reads the identifier of a scenario out of a path.
 *
 * A path that is not the path of a scenario gives `null`, and so does a path whose identifier cannot be read.
 */
export function parseScenarioId(pathname: string): string | null {
  if (typeof pathname !== "string") {
    return null;
  }
  // The path of a location never carries a query string, but a caller may hand over a whole URL.
  const path = pathname.split("?")[0]?.split("#")[0] ?? "";
  const match = /^\/?replay\/scenario\/([^/]+)\/?$/.exec(path);
  const raw = match?.[1];
  if (raw === undefined || raw === "") {
    return null;
  }
  try {
    return decodeURIComponent(raw);
  } catch {
    // A path with a broken escape is not a path of a scenario.
    return null;
  }
}

/** Every symbol this module exports, so that a reader sees the whole surface of the helpers at once. */
export const __all__ = [
  "REPLAY_TABS",
  "ReplayTab",
  "PLAYBACK_SPEEDS",
  "PlaybackSpeed",
  "ViewPreferences",
  "DEFAULT_VIEW_PREFERENCES",
  "isReplayTab",
  "isPlaybackSpeed",
  "readViewPreferences",
  "writeViewPreferences",
  "scenarioPath",
  "parseScenarioId",
] as const;
