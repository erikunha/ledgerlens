/**
 * The test of the contract of the URL of the replay.
 *
 * Why this test exists: the URL of the replay carries the scenario identifier and the harmless preferences of the
 * view, and nothing else. The identifier lives in the path, because a scenario is a place and not a filter. The query
 * string carries exactly two keys, `tab` and `speed`, and every other parameter is ignored, whatever it holds, so a
 * key, a handle or an answer that a visitor put in the URL never reaches the state of the interface.
 *
 * Every case runs with no key and no network: the helpers are pure functions of the string they are given.
 */

import { describe, expect, it } from "vitest";

import {
  DEFAULT_VIEW_PREFERENCES,
  PLAYBACK_SPEEDS,
  REPLAY_TABS,
  isPlaybackSpeed,
  isReplayTab,
  parseScenarioId,
  readViewPreferences,
  scenarioPath,
  writeViewPreferences,
} from "@/lib/state/urlState";

describe("the contract of the URL", () => {
  it("allows exactly the four tabs of the replay", () => {
    // It proves that the list of the tabs is closed, so that a tab of a later export never appears out of nowhere.
    expect(REPLAY_TABS).toEqual(["execution", "evidence", "decision", "provenance"]);
  });

  it("allows exactly the three speeds of the playback", () => {
    // It proves that the speed of the playback is one of the three of the contract.
    expect(PLAYBACK_SPEEDS).toEqual([1, 2, 4]);
  });

  it("starts from the defaults of a visitor who changed nothing", () => {
    // It proves that the defaults are the first tab and the normal speed.
    expect(DEFAULT_VIEW_PREFERENCES).toEqual({ tab: "execution", speed: 1 });
  });

  it("reads the preferences of a query string that carries them", () => {
    // It proves that a visitor who chose a tab and a speed gets them back. The two forms are accepted, because the
    // search of a location of a browser always carries the question mark and a caller may hand over a bare query.
    expect(readViewPreferences("?tab=evidence&speed=4")).toEqual({ tab: "evidence", speed: 4 });
    expect(readViewPreferences("tab=evidence&speed=4")).toEqual({ tab: "evidence", speed: 4 });
  });

  it("falls back to the default of every field that carries a value the contract does not define", () => {
    // It proves that a word the contract does not know never reaches the state of the interface.
    expect(readViewPreferences("?tab=nonsense&speed=9")).toEqual({ tab: "execution", speed: 1 });
  });

  it("ignores every parameter that is not in the allow list, whatever it holds", () => {
    // It proves that a key, a handle and an answer that a visitor put in the URL are dropped before they reach the
    // state of the interface.
    expect(readViewPreferences("?api_key=sk-secret&handle=abc&answer=hello")).toEqual({
      tab: "execution",
      speed: 1,
    });
  });

  it("never reads the position of the recording out of the query string", () => {
    // It proves that the position of the playback is the state of the machine of the reader and never a number that
    // a visitor put in the URL: the URL is the address of the page and the position is the state of the playback.
    const alone = readViewPreferences("?position=50");
    expect(alone).toEqual({ tab: "execution", speed: 1 });
    expect(Object.keys(alone).sort()).toEqual(["speed", "tab"]);
    expect("position" in alone).toBe(false);

    // The same rule holds when the query string carries the two keys that the contract does define: the position is
    // still dropped, and the tab and the speed still reach the state of the interface.
    const together = readViewPreferences("?position=50&tab=evidence&speed=4");
    expect(together).toEqual({ tab: "evidence", speed: 4 });
    expect(Object.keys(together).sort()).toEqual(["speed", "tab"]);
    expect("position" in together).toBe(false);
  });

  it("writes the preferences in the order of the tab and then of the speed", () => {
    // It proves that the query string of the interface is written in one order and not in the order of a map, and that
    // it is the inverse of the reading: the question mark is there because the search of a location carries it.
    expect(writeViewPreferences({ tab: "evidence", speed: 4 })).toBe("?tab=evidence&speed=4");
    expect(writeViewPreferences({ tab: "evidence", speed: 1 })).toBe("?tab=evidence&speed=1");
  });

  it("reads back exactly what it writes", () => {
    // It proves that the writing and the reading are the two ends of one contract.
    expect(readViewPreferences(writeViewPreferences({ tab: "evidence", speed: 4 }))).toEqual({
      tab: "evidence",
      speed: 4,
    });
    expect(readViewPreferences(writeViewPreferences({ tab: "execution", speed: 1 }))).toEqual({
      tab: "execution",
      speed: 1,
    });
  });

  it("writes an empty query string when the preferences are the defaults", () => {
    // It proves that the URL of a visitor who changed nothing stays clean.
    expect(writeViewPreferences({ tab: "execution", speed: 1 })).toBe("");
  });

  it("puts the identifier of the scenario in the path", () => {
    // It proves that the route of a scenario is the path of the contract, with the identifier of the catalog.
    expect(scenarioPath("S01")).toBe("/replay/scenario/S01");
  });

  it("reads the identifier of the scenario out of the path", () => {
    // It proves that the path of a scenario gives its identifier back.
    expect(parseScenarioId("/replay/scenario/S01")).toBe("S01");
  });

  it("gives nothing back for a path that is not the path of a scenario", () => {
    // It proves that the reader of the path never guesses an identifier.
    expect(parseScenarioId("/replay")).toBeNull();
    expect(parseScenarioId("/replay/scenario/")).toBeNull();
  });

  it("says whether a word is a tab of the replay", () => {
    // It proves that the guard of the tab accepts the four tabs and nothing else.
    expect(isReplayTab("execution")).toBe(true);
    expect(isReplayTab("provenance")).toBe(true);
    expect(isReplayTab("nonsense")).toBe(false);
  });

  it("says whether a number is a speed of the playback", () => {
    // It proves that the guard of the speed accepts the three speeds and nothing else.
    expect(isPlaybackSpeed(1)).toBe(true);
    expect(isPlaybackSpeed(4)).toBe(true);
    expect(isPlaybackSpeed(3)).toBe(false);
  });
});
