/**
 * The failure state of the reader of a recorded run.
 *
 * Why this file exists: a bundle the validators or the integrity check refused has to be shown as
 * a refusal, with the reason the reader can act on, and never as a half drawn run. A reader who
 * cannot tell which parts of a run are true is worse off than a reader who sees nothing
 * (ADR-043).
 *
 * Why the reasons are a list of their own: a bundle can carry more than one problem, and a
 * reader who sees only the first one does not know how many there are.
 *
 * Why the heading of the state is an `h3`: the state is drawn inside the section of the reader,
 * and the reader prescribes that the heading of a section is an `h3`, so the outline of the page
 * walks from the route to the refusal one level at a time.
 */

import type { ReactElement } from "react";


/**
 * The props of the failure state.
 *
 * Why the reasons are optional: a refusal with one reason needs no list, and a refusal with
 * several reasons shows them all.
 */
export interface ReplayErrorStateProps {
  /** The reason the bundle was refused. */
  readonly reason: string;
  /** Every reason the bundle was refused, when there is more than one. */
  readonly reasons?: readonly string[];
}

/**
 * The failure state of the reader of a recorded run.
 *
 * The state shows the reason of the refusal and the reasons that came with it. A reason that the
 * reason already carries is not repeated, because a reason shown twice reads like two problems.
 */
export function ReplayErrorState({ reason, reasons }: ReplayErrorStateProps): ReactElement {
  const extra = (reasons ?? []).filter((item) => !reason.includes(item));

  return (
    <div role="alert" className="rounded-lg border border-danger/40 bg-danger-light p-4">
      <h3 className="text-base font-semibold text-danger-dark">The recorded run was refused</h3>
      <p className="text-sm text-danger-dark">{reason}</p>
      {extra.length > 0 ? (
        <ul className="mt-2 flex list-disc flex-col gap-1 pl-5 text-sm text-danger-dark">
          {extra.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the state at once. */
export const __all__ = ["ReplayErrorStateProps", "ReplayErrorState"] as const;
