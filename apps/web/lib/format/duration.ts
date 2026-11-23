/**
 * The formatters of the two timings of the replay.
 *
 * Why this file exists: the replay carries two different timings and a visitor who confuses them reads a lie. The
 * ORIGINAL timing is what the capture measured: how long the agent took and when the event was recorded. The
 * PLAYBACK timing is where the visitor is inside the recording. They are formatted by separate functions on purpose,
 * and neither of them ever stands in for the other.
 *
 * The speed of the playback changes only how long the browser waits between two events. It never changes the original
 * timing and it never changes the order of the events.
 */

/** What the interface shows when the recording carries no duration and no moment. */
export const DURATION_UNAVAILABLE = "Not available";

/** The number of milliseconds below which a duration is shown in milliseconds. */
const ONE_SECOND_IN_MS = 1000;

/**
 * Renders the duration the capture measured, for one event.
 *
 * A duration below one second is shown in milliseconds and a duration of one second or more is shown in seconds with
 * one decimal. The number is the one the recording carries, rounded to the millisecond, and the function never reads
 * the clock of the browser.
 *
 * A recording without a duration gives `DURATION_UNAVAILABLE`. The offset of the playback is never used in its place.
 */
export function formatOriginalDuration(latencyMs: number | null | undefined): string {
  if (typeof latencyMs !== "number" || !Number.isFinite(latencyMs)) {
    return DURATION_UNAVAILABLE;
  }

  const rounded = Math.round(latencyMs);
  if (Math.abs(rounded) < ONE_SECOND_IN_MS) {
    return `${rounded} ms`;
  }
  return `${(latencyMs / ONE_SECOND_IN_MS).toFixed(1)} s`;
}

/**
 * Renders how far the visitor has moved inside the recording, as `mm:ss`.
 *
 * The offset is the distance from the first event of the recording. It is not a duration: it says where the visitor
 * is, never how long the agent took.
 */
export function formatPlaybackOffset(offsetMs: number): string {
  const safe = typeof offsetMs === "number" && Number.isFinite(offsetMs) ? Math.max(0, Math.floor(offsetMs)) : 0;
  const totalSeconds = Math.floor(safe / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

/**
 * Renders the moment the event was recorded, in ISO 8601.
 *
 * The moment is shown exactly as the recording wrote it, because the recording is the source of the truth about when
 * the event happened. A recording without a moment gives `DURATION_UNAVAILABLE`.
 */
export function formatObservedMoment(at: string | null | undefined): string {
  const moment = typeof at === "string" ? at.trim() : "";
  if (moment === "") {
    return DURATION_UNAVAILABLE;
  }
  return moment;
}

/** Every symbol this module exports, so that a reader sees the whole surface of the formatters at once. */
export const __all__ = [
  "DURATION_UNAVAILABLE",
  "formatOriginalDuration",
  "formatPlaybackOffset",
  "formatObservedMoment",
] as const;
