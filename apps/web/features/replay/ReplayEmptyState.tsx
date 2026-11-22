/**
 * The empty state of the reader of a recorded run.
 *
 * Why this file exists: a bundle that carries no event is a bundle with nothing to play, and the
 * reader has to say so instead of drawing an empty run. A reader who cannot tell whether the
 * recording is empty or broken reads a lie in both cases, so the state says which one it is and
 * names the scenario it is about (ADR-043).
 *
 * Why the heading of the state is an `h3`: the state is drawn inside the section of the reader,
 * and the reader prescribes that the heading of a section is an `h3`, so the outline of the page
 * walks from the route to the empty recording one level at a time.
 */

import type { ReactElement } from "react";


/**
 * The props of the empty state.
 *
 * Why the state carries the identifier of the scenario: a visitor who arrives at a broken
 * recording has to be able to say which one it was, and the identifier is what the catalog
 * publishes.
 */
export interface ReplayEmptyStateProps {
  /** The identifier of the scenario whose bundle carries no event. */
  readonly scenarioId: string;
}

/**
 * The empty state of the reader of a recorded run.
 *
 * The state says that the bundle carries no event and that the reason is in the manifest of the
 * bundle, because that is where the recording put it. It never guesses a reason of its own.
 */
export function ReplayEmptyState({ scenarioId }: ReplayEmptyStateProps): ReactElement {
  return (
    <div role="status" className="rounded-lg border border-line bg-background p-4">
      <h3 className="text-base font-semibold">The recording of the scenario has no event</h3>
      <p className="text-sm text-text-muted">
        The bundle of the scenario {scenarioId} carries no event, so there is nothing to play. The
        reason is written in the manifest of the bundle.
      </p>
    </div>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the state at once. */
export const __all__ = ["ReplayEmptyStateProps", "ReplayEmptyState"] as const;
