"use client";

/**
 * The panel of the calls, the tokens and the elapsed time of a live run.
 *
 * Why this file exists: a visitor has to see what the run is doing while it is doing it, and the
 * numbers of that panel are the ones the server reported in the events of the stream. The panel
 * computes nothing: it shows the counters as they arrived.
 */

import { Badge } from "@/components/ui/Badge";
import { Table } from "@/components/ui/Table";
import type { RunCounters } from "@/features/live/useLiveRun";
import type { TraceEvent } from "@/lib/api/schemas";

/** One measure of the run, as the panel shows it. */
interface Measure {
  /** The name of the measure. */
  name: string;
  /** The value the server reported. */
  value: number;
}

/**
 * The panel of the live run.
 *
 * The table is the accessible one of the design system: it carries a caption, the first column is
 * the row header, and the values are the ones of the server.
 */
export function RunTimeline({
  counters,
  events = [],
}: {
  /** What the run consumed, or `null` while the server reported nothing. */
  counters: RunCounters | null;
  /** The events the stream carried, in the order it carried them. */
  events?: TraceEvent[];
}) {
  const measures: Measure[] = counters
    ? [
        { name: "Calls of the model", value: counters.modelCalls },
        { name: "Calls of the tools", value: counters.toolCalls },
        { name: "Tokens read", value: counters.inputTokens },
        { name: "Tokens written", value: counters.outputTokens },
        { name: "Seconds of elapsed time", value: counters.elapsedSeconds },
      ]
    : [];

  const columns = [
    {
      key: "name",
      header: "Measure",
      rowHeader: true,
      render: (measure: Measure) => measure.name,
    },
    {
      key: "value",
      header: "Value",
      align: "right" as const,
      render: (measure: Measure) => measure.value,
    },
  ];

  return (
    <div className="rounded-lg border border-line bg-background">
      <div className="flex flex-col gap-1 border-b border-line px-4 py-3">
        <h3 className="text-base font-semibold">What the run did so far</h3>
        <p className="text-sm text-text-muted">
          The numbers are the ones the server reported in the events of the run.
        </p>
      </div>

      <Table
        caption="The calls, the tokens and the elapsed time of the run"
        columns={columns}
        rows={measures}
        emptyMessage="The run has not reported anything yet."
      />

      {events.length > 0 ? (
        <div className="flex flex-col gap-2 border-t border-line px-4 py-3">
          <h4 className="text-sm font-semibold">Events of the run</h4>
          <ul className="flex flex-col gap-1 text-sm text-text-muted">
            {events
              .slice()
              .reverse()
              .slice(0, 12)
              .map((event) => (
                <li key={`${event.seq}-${event.event_type}`} className="flex items-center gap-2">
                  <Badge>{event.event_type}</Badge>
                  <span className="font-mono text-xs">event {event.seq}</span>
                </li>
              ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
