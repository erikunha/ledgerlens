/**
 * The test of the formatters of the two timings of the replay.
 *
 * Why this test exists: the replay carries two different timings and a visitor who confuses them reads a lie. The
 * ORIGINAL timing is what the capture measured: how long the agent took and when the event was recorded. The PLAYBACK
 * timing is how far the visitor has moved inside the recording. They are formatted by separate functions on purpose,
 * and neither of them ever stands in for the other.
 *
 * Every case runs with no key and no network: the formatters are pure functions of the value they are given, and they
 * never read the clock of the browser.
 */

import { describe, expect, it } from "vitest";

import {
  DURATION_UNAVAILABLE,
  formatObservedMoment,
  formatOriginalDuration,
  formatPlaybackOffset,
} from "@/lib/format/duration";

describe("the formatters of the timings", () => {
  it("shows a duration below one second in milliseconds", () => {
    // It proves that the reader sees the duration the capture measured, and not a rounded number of seconds.
    expect(formatOriginalDuration(831)).toBe("831 ms");
  });

  it("shows a duration of one second or more in seconds with one decimal", () => {
    // It proves that the same duration is not shown in two different units depending on where it is read.
    expect(formatOriginalDuration(1200)).toBe("1.2 s");
  });

  it("says that the duration is not available when the recording carries none", () => {
    // It proves that the offset of the playback is never used in the place of a missing duration.
    expect(formatOriginalDuration(null)).toBe(DURATION_UNAVAILABLE);
    expect(formatOriginalDuration(undefined)).toBe(DURATION_UNAVAILABLE);
  });

  it("shows the offset of the playback as minutes and seconds", () => {
    // It proves that the distance of the visitor is rendered as a position and not as a duration.
    expect(formatPlaybackOffset(0)).toBe("00:00");
    expect(formatPlaybackOffset(65000)).toBe("01:05");
  });

  it("shows the moment of the event exactly as the recording wrote it", () => {
    // It proves that the moment comes from the artifact and never from the clock of the browser.
    expect(formatObservedMoment("2026-11-14T11:00:14.051+00:00")).toBe("2026-11-14T11:00:14.051+00:00");
  });

  it("says that the moment is not available when the recording carries none", () => {
    // It proves that a missing moment is rendered as unavailable and never as the moment of the browser.
    expect(formatObservedMoment(null)).toBe(DURATION_UNAVAILABLE);
  });

  it("never shows the original timing in the place of the offset", () => {
    // It proves that the two timings are two separate facts: a visitor that confuses them reads a lie.
    expect(formatOriginalDuration(831)).not.toBe(formatPlaybackOffset(831));
    expect(formatPlaybackOffset(831)).toBe("00:00");
  });
});
