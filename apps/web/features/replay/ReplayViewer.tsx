"use client";

/**
 * The reader of the recorded run.
 *
 * Why this file exists: the recorded demo is the half of the demo that works with no key and no
 * network, and it has to be honest about what it shows. The mode it shows is the mode of the
 * manifest it read, and the note it shows is the note of the capture, word for word. A recorded run
 * is never presented as a live one.
 *
 * When the artifact is broken the reader shows the reason and nothing else: a half drawn run is
 * worse than no run, because a reader cannot tell which parts of it are true.
 */

import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Table } from "@/components/ui/Table";
import { loadReplay, type LoadedReplay } from "@/features/replay/loadReplay";
import type { ScenarioIndexEntry } from "@/lib/api/schemas";
import { reduceToIndex, type ToolCallState } from "@/lib/replay/reducer";

/**
 * The props of the reader.
 *
 * Why the reader takes the card of the scenario and not the bundle: the card is what the catalog
 * of the site publishes, and the reader finds the bundle of the scenario on its own.
 */
export interface ReplayViewerProps {
  /** The card of the scenario in the catalog of the site. */
  scenario: ScenarioIndexEntry;
}

/**
 * The reader of the recorded run.
 *
 * The seek moves through the events of the recording, and the state at that position comes from the
 * reducer of the repository, so the same position always produces the same state.
 */
export function ReplayViewer({ scenario }: ReplayViewerProps) {
  const [loaded, setLoaded] = useState<LoadedReplay | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [position, setPosition] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoaded(null);
    setError(null);
    setPosition(0);

    void loadReplay(scenario).then((result) => {
      if (!alive) {
        return;
      }
      if ("error" in result) {
        setError(result.error);
        return;
      }
      setLoaded(result);
    });

    return () => {
      alive = false;
    };
  }, [scenario]);

  const reduced = useMemo(
    () => (loaded ? reduceToIndex(loaded.events, position) : null),
    [loaded, position],
  );

  if (error) {
    return (
      <div role="alert" className="rounded-lg border border-danger/40 bg-danger-light p-4">
        <h2 className="text-base font-semibold text-danger-dark">The recorded run was refused</h2>
        <p className="text-sm text-danger-dark">{error}</p>
      </div>
    );
  }

  if (!loaded || !reduced) {
    return <p className="text-sm text-text-muted">The recorded run is loading.</p>;
  }

  const lastPosition = Math.max(loaded.events.length - 1, 0);
  const calls: ToolCallState[] = reduced.state.toolCalls;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>mode: {loaded.manifest.mode}</Badge>
        <Badge>scenario: {loaded.manifest.scenario}</Badge>
        <Badge>run: {loaded.manifest.run_id}</Badge>
        {loaded.manifest.capture_kind ? <Badge>capture: {loaded.manifest.capture_kind}</Badge> : null}
      </div>

      <p className="text-sm text-text-subtle">{loaded.manifest.note}</p>

      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium" htmlFor="ledgerlens-replay-position">
          Position of the recording
        </label>
        <input
          id="ledgerlens-replay-position"
          className="w-full max-w-md"
          type="range"
          min={0}
          max={lastPosition}
          step={1}
          value={position}
          onChange={(event) => setPosition(Number(event.target.value))}
        />
        <p className="text-sm text-text-muted">
          Event {reduced.state.lastSeq ?? 0} of {loaded.events.length}. The status of the run is:{" "}
          {reduced.state.status}.
        </p>
      </div>

      {reduced.state.plan ? (
        <div className="rounded-lg border border-line bg-background p-4">
          <h3 className="text-base font-semibold">The plan of the agent</h3>
          <p className="text-sm text-text-muted">{reduced.state.plan.question}</p>
          <ol className="list-decimal pl-5 text-sm text-text-muted">
            {reduced.state.plan.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
      ) : null}

      <div className="rounded-lg border border-line bg-background">
        <div className="flex flex-col gap-1 border-b border-line px-4 py-3">
          <h3 className="text-base font-semibold">The calls of the tools</h3>
          <p className="text-sm text-text-muted">
            The calls are the ones the capture recorded, with the arguments and the result it wrote.
          </p>
        </div>
        <Table
          caption="The calls of the tools of the recorded run"
          columns={[
            {
              key: "name",
              header: "Tool",
              rowHeader: true,
              render: (call: ToolCallState) => call.name,
            },
            {
              key: "status",
              header: "Status",
              render: (call: ToolCallState) => call.status ?? "unknown",
            },
            {
              key: "latency",
              header: "Latency in milliseconds",
              align: "right",
              render: (call: ToolCallState) => call.latencyMs ?? "",
            },
          ]}
          rows={calls}
          emptyMessage="The recording has no call of a tool yet."
        />
      </div>

      {reduced.state.evidence.length > 0 ? (
        <div className="rounded-lg border border-line bg-background p-4">
          <h3 className="text-base font-semibold">The evidence the run collected</h3>
          <ul className="flex flex-col gap-2">
            {reduced.state.evidence.map((evidence) => (
              <li key={evidence.evidenceId} className="text-sm text-text-muted">
                <Badge>{evidence.sourceType ?? "evidence"}</Badge>{" "}
                <span className="font-mono text-xs">{evidence.evidenceId}</span>
                {evidence.content ? <span className="ml-2">{evidence.content}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {reduced.state.verdicts.length > 0 ? (
        <div className="rounded-lg border border-line bg-background p-4">
          <h3 className="text-base font-semibold">The verdicts of the verification</h3>
          <ul className="flex flex-col gap-2">
            {reduced.state.verdicts.map((verdict) => (
              <li key={verdict.claimId} className="flex flex-wrap items-center gap-2 text-sm">
                <Badge>{verdict.label ?? "not verified"}</Badge>
                <span className="font-mono text-xs">{verdict.claimId}</span>
                {verdict.note ? <span className="text-text-muted">{verdict.note}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
