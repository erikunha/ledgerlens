"use client";

import type { ReactElement } from "react";

import { cn } from "@/lib/design/cn";
import { formatToolStatus } from "@/lib/format/status";
import type { RunStep } from "@/lib/replay/selectors";

/**
 * The stepper of the run of a recorded run.
 *
 * Why this file exists: the tree of the investigation answers which span opened which span, and the timeline answers
 * what happened event by event. Neither of them answers the question a visitor asks first: how far along the run am I,
 * and which call is the current one. The stepper is the piece that answers it, with the four calls of the recording of
 * the scenario S01 and nothing else.
 *
 * Why the stepper is an indicator and never a control: it never seeks, it never opens the drawer of a call, and it adds
 * no stop of the keyboard. The tree and the timeline already move the recording, and a third place that moves it is a
 * third keyboard model for the same action (ADR-050, decision 2).
 *
 * Why the stepper computes nothing: the steps of the run and the step the recording stands at come from the library,
 * which projects them out of what the reducer already holds. The stepper draws them and never builds one.
 *
 * Why the state of a step is said in words: the step the recording stands at says that it is the current one, a step
 * the recording is over says that it is finished with the status the capture wrote, and a step the recording has not
 * reached says that it has not started yet. The status comes from the formatter of the status of a tool, the same one
 * the table of the calls uses, so the two can never disagree about the state of a call.
 *
 * Why the current step wears a border and a heavier name: a tint of the background is a mark a reader with low vision
 * cannot see, and the weight of the name survives the forced colours mode of the system.
 */

/** The props of the stepper of the run. */
export interface RunStepperProps {
  /** The steps of the run, in the order the recording made them. */
  readonly steps: readonly RunStep[];
  /** The step the recording stands at, or null when it stands before the first call. */
  readonly current: RunStep | null;
}

/**
 * The words that say the state of a step the recording is over.
 *
 * Why the status is left out when the call has no status: a call that carries no status has not ended with one, and a
 * word the capture never wrote is not a word the interface may say.
 */
function finishedSentence(step: RunStep): string {
  if (step.status === null) {
    return "Finished.";
  }
  // the sentence of the step ends with a period, the way the sentence of the current step ends
  return `Finished. ${formatToolStatus(step.status).label}.`;
}

/**
 * The stepper of the run of a recorded run.
 *
 * The stepper shows the calls of the recording as an ordered list. The step the recording stands at carries
 * `aria-current="step"` and the words "The current step.", so a reader of a screen reader knows where the recording is
 * and a visitor who does not see the screen reads the same thing in the same words.
 */
export function RunStepper({ steps, current }: RunStepperProps): ReactElement {
  const total = steps.length;

  return (
    <section
      aria-label="The steps of the run"
      className="rounded-lg border border-line bg-background"
    >
      <div className="flex flex-col gap-1 border-b border-line px-4 py-3">
        <h4 className="text-base font-semibold">The steps of the run</h4>
        <p className="text-sm text-text-muted">
          One step per call of a tool, in the order the recording made the calls. The step the
          recording stands at is the current one.
        </p>
      </div>

      {steps.length === 0 ? (
        <p className="px-4 py-3 text-sm text-text-muted">The recording made no call of a tool yet.</p>
      ) : (
        <ol className="flex flex-col gap-1 px-4 py-3">
          {steps.map((step) => {
            const isCurrent = current !== null && step.number === current.number;
            const isOver = current !== null && step.number < current.number;
            const state = isCurrent
              ? "The current step."
              : isOver
                ? finishedSentence(step)
                : "Not started yet.";

            return (
              <li
                key={step.number}
                // the attribute of the current item of a sequence tells a reader of a screen reader where the
                // recording stands, and the words below tell the visitor who does not see the screen
                aria-current={isCurrent ? "step" : undefined}
                className={cn(
                  "border-l-2 pl-3",
                  isCurrent ? "border-foreground" : "border-transparent",
                )}
              >
                <span
                  className={cn(
                    "text-sm",
                    // the weight of the name is the mark that survives the forced colours mode of the system
                    isCurrent ? "font-semibold text-foreground" : "font-medium text-foreground",
                  )}
                >
                  Step {step.number} of {total}: {step.name}.
                </span>{" "}
                <span className="text-sm text-text-muted">{state}</span>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the stepper at once. */
export const __all__ = ["RunStepperProps", "RunStepper"] as const;
