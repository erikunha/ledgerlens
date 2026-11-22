/**
 * The controls of the playback of a recorded run.
 *
 * Why this file exists: a visitor watches a recording at their own pace, so the reader offers the
 * play, the pause, the step forward, the step back, the reset and the speed. The controls only
 * ask the reader to move; they never move the reader themselves, because the state of the machine
 * belongs to the provider (ADR-043).
 *
 * Why the speed is a control of its own: the speed changes only how long the browser waits
 * between two events. It never changes the order of the events and never changes the timing the
 * panels show (FR-010, FR-011).
 */

"use client";

import type { ReactElement } from "react";

import { Button } from "@/components/ui/Button";
import type { ReplayPhase } from "@/features/replay/ReplayProvider";
import { usePrefersReducedMotion } from "@/features/replay/usePlaybackClock";
import { isPlaybackSpeed, PLAYBACK_SPEEDS, type PlaybackSpeed } from "@/lib/state/urlState";

/**
 * The props of the controls.
 *
 * Why every action is a function of the caller: the controls hold no state of their own, so the
 * same controls always show the same thing for the same position. The position, the total and the
 * seek belong to the reader that shows them: the slider of the reader is the jump of the
 * recording, and the position is written next to it, so that it is never written twice.
 */
export interface ReplayControlsProps {
  /** Where the reading of the recording stands. */
  readonly phase: ReplayPhase;
  /** The position of the visitor inside the recording. */
  readonly position: number;
  /** The number of events of the recording. */
  readonly total: number;
  /** The speed the playback runs at. */
  readonly speed: PlaybackSpeed;
  /** Called when the visitor asks for the recording to play. */
  readonly onPlay: () => void;
  /** Called when the visitor asks for the recording to pause. */
  readonly onPause: () => void;
  /** Called when the visitor asks for the next or for the previous event. */
  readonly onStep: (delta: -1 | 1) => void;
  /** Called when the visitor asks for another position of the recording. */
  readonly onSeek: (position: number) => void;
  /** Called when the visitor asks for the recording to start again. */
  readonly onReset: () => void;
  /** Called when the visitor asks for another speed. */
  readonly onSpeedChange: (speed: PlaybackSpeed) => void;
}

/** The identifier of the text that says why the play control cannot act. */
const PLAY_REASON_ID = "ledgerlens-replay-play-reason";

/** The identifier of the text that says why the pause control cannot act. */
const PAUSE_REASON_ID = "ledgerlens-replay-pause-reason";

/** The identifier of the text that says why the step back control cannot act. */
const PREVIOUS_REASON_ID = "ledgerlens-replay-previous-reason";

/** The identifier of the text that says why the step forward control cannot act. */
const NEXT_REASON_ID = "ledgerlens-replay-next-reason";

/** The identifier of the note that says that the automatic playback is off. */
const REDUCED_MOTION_NOTE_ID = "ledgerlens-replay-reduced-motion-note";

/**
 * The reason why the play control cannot act.
 *
 * Why the reason is a sentence and not a word: a control that says it cannot act has to say why,
 * because a visitor who pressed it and nothing happened deserves an answer.
 */
function playReason(phase: ReplayPhase): string {
  switch (phase) {
    case "playing":
      return "The recording is already playing.";
    case "completed":
      return "The recording has finished. Restart the recording to play it again.";
    case "idle":
    case "loading":
      return "The recording is not ready yet.";
    default:
      return "";
  }
}

/**
 * The reason why the pause control cannot act.
 *
 * Why the reason is empty when the recording plays: the pause control acts, so it has nothing to
 * explain.
 */
function pauseReason(phase: ReplayPhase): string {
  return phase === "playing" ? "" : "The recording is not playing.";
}

/**
 * The reason why the step back control cannot act.
 *
 * Why the reason names the limit the visitor stands at: a visitor who pressed the control at the
 * first event of the recording and nothing happened deserves to hear that the recording starts
 * there, and not that the control is broken. The reason is empty when the step can act, because
 * a control that acts has nothing to explain.
 *
 * Why the reason does not repeat the count of the events: the region of the step already says
 * where the visitor stands, and a reason that repeats it says the same thing twice.
 */
function previousReason(position: number, total: number): string {
  if (total === 0) {
    return "The recording carries no event yet.";
  }
  if (position > 0) {
    return "";
  }
  return "The recording stands at its first event, so there is no event before it.";
}

/**
 * The reason why the step forward control cannot act.
 *
 * Why the reason names the limit the visitor stands at: a visitor who pressed the control at the
 * last event of the recording and nothing happened deserves to hear that the recording ends
 * there, and not that the control is broken.
 */
function nextReason(position: number, total: number): string {
  if (total === 0) {
    return "The recording carries no event yet.";
  }
  if (position < Math.max(total - 1, 0)) {
    return "";
  }
  return "The recording stands at its last event, so there is no event after it.";
}

/**
 * The controls of the playback of a recorded run.
 *
 * The play and the pause are never removed from the page. A control that disappears under the
 * focus of the visitor takes the focus with it, and the next Tab starts again at the top of the
 * document. The control that would do nothing stays where it is and says so with
 * `aria-disabled`, with the reason next to it, so that the visitor keeps the place and the
 * keyboard keeps its order.
 *
 * The steps are always there: the machine keeps the position inside the range of the events, so a
 * step past the end is a step that does not move. A step that does not move says so the way the
 * play and the pause say so: the control stays in the keyboard, it carries `aria-disabled`, and it
 * points at the limit the visitor stands at.
 */
export function ReplayControls(props: ReplayControlsProps): ReactElement {
  const { phase, position, total, speed, onPlay, onPause, onStep, onReset, onSpeedChange } = props;

  const reducedMotion = usePrefersReducedMotion();
  const canPlay = phase === "ready" || phase === "paused";

  // the automatic playback is off when the visitor asked for less motion, so the play cannot act
  const playIsBlocked = !canPlay || reducedMotion;
  const pauseIsBlocked = phase !== "playing";

  const playText = reducedMotion ? "" : playReason(phase);
  const pauseText = pauseReason(phase);
  const previousText = previousReason(position, total);
  const nextText = nextReason(position, total);

  const handlePlay = (): void => {
    if (playIsBlocked) {
      return;
    }
    onPlay();
  };

  const handlePause = (): void => {
    if (pauseIsBlocked) {
      return;
    }
    onPause();
  };

  /**
   * Moves the recording one event back or one event forward.
   *
   * Why a step that cannot move is not sent to the machine: the machine would keep the position
   * where it is, and the visitor would hear nothing at all. The control says why with
   * `aria-disabled` and with the reason it points at.
   */
  const handleStep = (delta: -1 | 1): void => {
    if (delta < 0 ? previousText !== "" : nextText !== "") {
      return;
    }
    onStep(delta);
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="primary"
        size="sm"
        onClick={handlePlay}
        aria-disabled={playIsBlocked ? "true" : undefined}
        aria-describedby={
          reducedMotion
            ? REDUCED_MOTION_NOTE_ID
            : playText !== ""
              ? PLAY_REASON_ID
              : undefined
        }
        className="aria-disabled:border-line aria-disabled:bg-surface-muted aria-disabled:text-text-muted"
      >
        Play the recording
      </Button>
      <Button
        variant="secondary"
        size="sm"
        onClick={handlePause}
        aria-disabled={pauseIsBlocked ? "true" : undefined}
        aria-describedby={pauseText !== "" ? PAUSE_REASON_ID : undefined}
        className="aria-disabled:border-line aria-disabled:bg-surface-muted aria-disabled:text-text-muted"
      >
        Pause the recording
      </Button>
      <Button
        variant="secondary"
        size="sm"
        onClick={() => handleStep(-1)}
        aria-disabled={previousText !== "" ? "true" : undefined}
        aria-describedby={previousText !== "" ? PREVIOUS_REASON_ID : undefined}
        className="aria-disabled:border-line aria-disabled:bg-surface-muted aria-disabled:text-text-muted"
      >
        Previous event
      </Button>
      <Button
        variant="secondary"
        size="sm"
        onClick={() => handleStep(1)}
        aria-disabled={nextText !== "" ? "true" : undefined}
        aria-describedby={nextText !== "" ? NEXT_REASON_ID : undefined}
        className="aria-disabled:border-line aria-disabled:bg-surface-muted aria-disabled:text-text-muted"
      >
        Next event
      </Button>
      <Button variant="ghost" size="sm" onClick={onReset}>
        Restart the recording
      </Button>

      <div className="flex items-center gap-2">
        <label className="text-sm font-medium" htmlFor="ledgerlens-replay-speed">
          Speed of the playback
        </label>
        <select
          id="ledgerlens-replay-speed"
          className="rounded border border-line-strong bg-background px-2 py-1 text-sm"
          value={speed}
          onChange={(event) => {
            const chosen = Number(event.target.value);
            // the options of the control carry the three speeds of the contract, and nothing else is accepted
            if (isPlaybackSpeed(chosen)) {
              onSpeedChange(chosen);
            }
          }}
        >
          {PLAYBACK_SPEEDS.map((value) => (
            <option key={value} value={value}>
              {value}x
            </option>
          ))}
        </select>
      </div>

      <p className="text-xs text-text-subtle">
        The speed changes how long the browser waits between two events. It never changes the order
        of the events, and it never changes the timing the panels show.
      </p>

      {reducedMotion ? (
        <p id={REDUCED_MOTION_NOTE_ID} className="text-xs text-text-subtle">
          The automatic playback is off because this device asks for less motion. Step through the
          events with Previous event and Next event, or move the recording with the slider.
        </p>
      ) : null}

      {playText !== "" ? (
        <p id={PLAY_REASON_ID} className="ll-visually-hidden">
          {playText}
        </p>
      ) : null}

      {pauseText !== "" ? (
        <p id={PAUSE_REASON_ID} className="ll-visually-hidden">
          {pauseText}
        </p>
      ) : null}

      {previousText !== "" ? (
        <p id={PREVIOUS_REASON_ID} className="ll-visually-hidden">
          {previousText}
        </p>
      ) : null}

      {nextText !== "" ? (
        <p id={NEXT_REASON_ID} className="ll-visually-hidden">
          {nextText}
        </p>
      ) : null}
    </div>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the controls at once. */
export const __all__ = ["ReplayControlsProps", "ReplayControls"] as const;
