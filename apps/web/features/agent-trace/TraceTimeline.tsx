/**
 * The timeline of a recorded run.
 *
 * Why this file exists: a reader has to see the whole recording, not only the part the playback
 * has reached. The timeline has one row per event of the bundle, in the order of the recording,
 * including the events the interface does not know, so that the number of the rows is the number
 * of the events of the bundle and no event ever disappears silently (SC-013).
 *
 * Why the moment and the duration are two columns: the moment is when the event was recorded and
 * the duration is how long the capture measured. The offset of the playback is neither of them,
 * and it never stands in for one of them (ADR-043).
 *
 * Why the table is one navigation group: the table of the design system walks its cells with the
 * arrow keys, and the event number is not a button of its own, because fifty seven buttons of the
 * first column would put fifty seven stops of the keyboard on the page (FR-031).
 *
 * Why the row the visitor stands at wears a mark that is not only a colour: a tint of the
 * background alone is a mark a reader with low vision cannot see, and a tint that a hovered row
 * also wears tells the reader nothing. The row of the position wears a border on its left and a
 * heavier event number, the mark the tree of the investigation wears as well, and the weight
 * survives the forced colours mode of the system, where a tint of the background does not.
 */

"use client";

import { useCallback } from "react";
import type { KeyboardEvent, ReactElement } from "react";

import { Table, type TableColumn } from "@/components/ui/Table";
import { cn } from "@/lib/design/cn";
import { formatObservedMoment, formatOriginalDuration } from "@/lib/format/duration";
import type { TimelineRow } from "@/lib/replay/selectors";

/**
 * The props of the timeline.
 *
 * Why the position is a number of the recording and not a number of the rows: the position is the
 * place the visitor is inside the recording, and the rows are the events of the recording in
 * order, so the two count the same thing.
 */
export interface TraceTimelineProps {
  /** One row per event of the recording. */
  readonly rows: readonly TimelineRow[];
  /** The position of the visitor inside the recording. */
  readonly position: number;
  /** Called with the position the visitor asked for. */
  readonly onSeek: (position: number) => void;
}

/**
 * The timeline of a recorded run.
 *
 * The row of the position the visitor is at is the one the reader marks: the row carries
 * `aria-current`, so a reader with a screen reader knows which event of the recording the
 * playback is at, and the event number of that row moves the recording to that event. The visitor
 * reaches the event number with the keyboard through the cells of the table, and the Enter key
 * on the cell of the event number moves the recording there.
 *
 * The mark of that row is a border on its left and a heavier event number, and never a tint of the
 * background alone: a tint is a mark a reader with low vision cannot see, and the weight of the
 * name survives the forced colours mode of the system.
 */
export function TraceTimeline({ rows, position, onSeek }: TraceTimelineProps): ReactElement {
  /**
   * Moves the recording to the event of the cell that holds the focus.
   *
   * Why the cell carries the row in its name: the table of the design system writes the row and
   * the column of every cell in the attribute of the cell, so the timeline reads the row of the
   * focused cell without keeping a second copy of the rows.
   */
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>): void => {
      if (event.key !== "Enter") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (!target || typeof target.closest !== "function") {
        return;
      }
      const cell = target.closest("[data-cell]");
      // only the cell itself answers, never the button inside it, which answers on its own
      if (!cell || cell !== target) {
        return;
      }
      const place = cell.getAttribute("data-cell");
      if (place === null) {
        return;
      }
      const separator = place.indexOf(":");
      if (separator < 0) {
        return;
      }
      // only the column of the event number moves the recording
      if (place.slice(separator + 1) !== "0") {
        return;
      }
      const row = Number.parseInt(place.slice(0, separator), 10);
      if (!Number.isFinite(row)) {
        return;
      }
      event.preventDefault();
      onSeek(row);
    },
    [onSeek],
  );

  const columns: Array<TableColumn<TimelineRow>> = [
    {
      key: "event",
      header: "Event",
      rowHeader: true,
      render: (row, index) => {
        const isCurrent = index === position;
        return (
          <button
            type="button"
            // the button is not a stop of the keyboard: the cell of the table is the one that is walked
            tabIndex={-1}
            onClick={() => onSeek(index)}
            className={cn(
              // the border is on every row of the column, so the event numbers stay in one line and
              // the row that is not the current one wears no visible mark of its own
              "rounded border-l-2 px-1",
              isCurrent
                ? "border-foreground bg-surface-muted font-semibold text-foreground"
                : "border-transparent font-medium text-foreground underline-offset-2 hover:underline",
            )}
          >
            {row.seq}
          </button>
        );
      },
    },
    {
      key: "label",
      header: "What happened",
      render: (row) => row.label,
    },
    {
      key: "moment",
      header: "Moment of the event",
      render: (row) => formatObservedMoment(row.at),
    },
    {
      key: "duration",
      header: "Duration the capture measured",
      align: "right",
      render: (row) => formatOriginalDuration(row.latencyMs),
    },
    {
      key: "error",
      header: "Error",
      render: (row) => row.error ?? "",
    },
  ];

  return (
    <section
      aria-label="The timeline of the recording"
      className="rounded-lg border border-line bg-background"
    >
      <div className="flex flex-col gap-1 border-b border-line px-4 py-3">
        <h4 className="text-base font-semibold">The timeline of the recording</h4>
        <p className="text-sm text-text-muted">
          One row per event of the recording, with the moment it was recorded, the duration the
          capture measured and the error it ended with. The event number moves the recording to that
          event: click it, or put the focus on the cell of the event number and press Enter.
        </p>
      </div>
      <div onKeyDown={handleKeyDown}>
        <Table
          caption="The events of the recorded run"
          columns={columns}
          rows={[...rows]}
          // the row the visitor stands at is the one the reader hears as the current one, so the
          // attribute sits on the row and not on the button of the cell of the event number
          rowAttributes={(_row, index) => (index === position ? { "aria-current": "true" } : {})}
          emptyMessage="The recording carries no event yet."
        />
      </div>
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the timeline at once. */
export const __all__ = ["TraceTimelineProps", "TraceTimeline"] as const;
