/**
 * The clock of the playback of a recorded run.
 *
 * Why this file exists: the playback advances the recording by itself, and the rule that says how
 * it advances has to live in one place. The clock only dispatches: it asks the machine to move to
 * the next position and it asks the machine to finish, and it never writes the state of the
 * machine itself, because a clock that rewrites the state would make the same position produce
 * two different states (FR-012).
 *
 * Why the speed only changes the interval: the speed changes how long the browser waits between
 * two events. It never changes the order of the events and it never changes the timing the panels
 * show, because a visitor who sees the measured duration change with the speed reads a lie
 * (FR-010, FR-011).
 *
 * Why the preference for reduced motion stops the clock: a recording that moves by itself is an
 * animation, and a visitor who asked the browser for less motion asked for the recording to wait
 * for them (FR-036, SC-011).
 */

"use client";

import { useEffect, useState } from "react";

import type { ReplayPhase } from "@/features/replay/ReplayProvider";
import type { PlaybackSpeed } from "@/lib/state/urlState";

/**
 * The options of the clock.
 *
 * Why the clock takes the position and the total: the clock has to know when the recording ends,
 * and it has to know which position comes next. It reads them from the caller, so it never keeps
 * a position of its own that could disagree with the machine.
 */
export interface PlaybackClockOptions {
  /** Where the reading of the recording stands. */
  readonly phase: ReplayPhase;
  /** The position of the visitor inside the recording. */
  readonly position: number;
  /** The number of events of the recording. */
  readonly total: number;
  /** The speed the playback runs at. */
  readonly speed: PlaybackSpeed;
  /** The interval the browser waits between two events at the speed of one. */
  readonly intervalMs?: number;
  /** Called with the position that comes next. */
  readonly onTick: (position: number) => void;
  /** Called when the recording reached its end. */
  readonly onComplete: () => void;
}

/** The interval the browser waits between two events at the speed of one, in milliseconds. */
export const DEFAULT_PLAYBACK_INTERVAL_MS = 500;

/**
 * The shortest interval the clock waits, in milliseconds.
 *
 * Why there is a floor: a speed of four on an interval of a few milliseconds would ask the browser
 * for more frames than it can draw, and the reader would show a recording nobody can follow.
 */
const MINIMUM_INTERVAL_MS = 16;

/**
 * The media query that carries the preference of the visitor for less motion.
 *
 * Why the query is a constant: the clock and the controls of the playback have to read the same
 * preference, and two spellings of the same query could disagree.
 */
export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/**
 * The preference of the visitor for less motion, kept up to date.
 *
 * Why the preference is read again when it changes: a visitor can change the preference of the
 * system while the page is open, and the playback has to answer the preference that is in force
 * now, not the one that was in force when the page opened.
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    // a browser without the media query knows nothing about the preference, so the playback runs as it does today
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const query = window.matchMedia(REDUCED_MOTION_QUERY);
    const sync = (): void => setReduced(query.matches);

    sync();

    if (typeof query.addEventListener === "function") {
      query.addEventListener("change", sync);
      return () => {
        query.removeEventListener("change", sync);
      };
    }

    // the older engines of Safari only know the listener of the old name
    query.addListener(sync);
    return () => {
      query.removeListener(sync);
    };
  }, []);

  return reduced;
}

/**
 * The clock of the playback of a recorded run.
 *
 * The clock runs only while the recording plays, and it stops as soon as the visitor pauses it or
 * the recording reaches its end. The interval it waits is the interval of the caller divided by the
 * speed, and nothing else about the recording changes.
 *
 * The clock does not run at all when the visitor asked for less motion. The recording then waits
 * for the visitor, who steps through it with the buttons and moves it with the slider.
 */
export function usePlaybackClock(options: PlaybackClockOptions): void {
  const {
    phase,
    position,
    total,
    speed,
    intervalMs = DEFAULT_PLAYBACK_INTERVAL_MS,
    onTick,
    onComplete,
  } = options;

  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (phase !== "playing") {
      return;
    }

    // the visitor asked for less motion: the recording waits for the visitor instead of moving
    if (reducedMotion) {
      return;
    }

    if (total <= 0) {
      onComplete();
      return;
    }

    const delay = Math.max(MINIMUM_INTERVAL_MS, Math.round(intervalMs / speed));

    const timer = window.setInterval(() => {
      if (position + 1 >= total) {
        onComplete();
        return;
      }
      onTick(position + 1);
    }, delay);

    return () => {
      window.clearInterval(timer);
    };
  }, [phase, position, total, speed, intervalMs, onTick, onComplete, reducedMotion]);
}

/** Every symbol this module exports, so that a reader sees the whole surface of the clock at once. */
export const __all__ = [
  "PlaybackClockOptions",
  "DEFAULT_PLAYBACK_INTERVAL_MS",
  "REDUCED_MOTION_QUERY",
  "usePrefersReducedMotion",
  "usePlaybackClock",
] as const;
