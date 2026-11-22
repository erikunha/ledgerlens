/**
 * The reader of a recorded run.
 *
 * Why this file exists: the recorded demo is the half of the demo that works with no key and no
 * network, and it has to be honest about what it shows. The mode it shows is the mode of the
 * manifest it read, and the note it shows is the note of the capture, word for word. A recorded
 * run is never presented as a live one.
 *
 * Why the reader reads the provider and loads nothing by itself: the bundle of the scenario is
 * read once, by the state machine, and the machine refuses a broken bundle with a reason. The
 * reader draws what the machine holds, so the reader and the machine can never disagree about
 * what is on the screen (ADR-043).
 *
 * Why the reader shows the failure state and nothing else: a half drawn run is worse than no run,
 * because a reader cannot tell which parts of it are true.
 *
 * Why the sections are real tabs: a row of buttons that only looks like a tablist leaves the
 * reader with a list of panels that are all open at once and a row of tabs that the arrow keys do
 * not move. The reader uses the primitive of the design system, so the arrow keys move the focus,
 * the panel of the chosen tab is the only one in the page, and the panel carries the name of the
 * tab that chose it.
 *
 * Why the reader announces the step in a polite region: a recording that advances in silence is a
 * recording a reader of a screen reader cannot follow. The region carries the step and nothing
 * else, because a region that carried the status of the run would interrupt the reader on every
 * event of the recording (FR-032, FR-033).
 *
 * Why the row of the tabs sits under the controls of the playback: the controls are the same in
 * every section of the replay, and the primitive draws the row of the tabs and the panel it opens
 * together, so the row stays right above the panel it chooses.
 *
 * Why the panels keep their identifier: a link to the reader can point at the panel of a section.
 */

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactElement } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Table, type TableColumn } from "@/components/ui/Table";
import { Tabs, type TabItem } from "@/components/ui/Tabs";
import { TraceTimeline } from "@/features/agent-trace/TraceTimeline";
import { TraceTree } from "@/features/agent-trace/TraceTree";
import { AnswerPanel } from "@/features/evidence/AnswerPanel";
import { ClaimList } from "@/features/evidence/ClaimList";
import { EngineeringDrawer } from "@/features/architecture/EngineeringDrawer";
import { LedgerPanel } from "@/features/ledger/LedgerPanel";
import { useReplay, type ReplayPhase, type ReplayState } from "@/features/replay/ReplayProvider";
import { ReplayControls } from "@/features/replay/ReplayControls";
import { ReplayEmptyState } from "@/features/replay/ReplayEmptyState";
import { ReplayErrorState } from "@/features/replay/ReplayErrorState";
import { RunOverview } from "@/features/replay/RunOverview";
import { usePlaybackClock } from "@/features/replay/usePlaybackClock";
import { ProvenancePanel } from "@/features/shell/ProvenancePanel";
import type { LedgerArtifact, ScenarioIndexEntry } from "@/lib/api/schemas";
import type { BundleIntegrity } from "@/lib/api/replay";
import { formatOriginalDuration } from "@/lib/format/duration";
import { formatMoney, formatPercentage } from "@/lib/format/money";
import { formatRunStatus, formatToolStatus } from "@/lib/format/status";
import { summarizeProvenance } from "@/lib/replay/provenance";
import { reduceToIndex, type ToolCallState } from "@/lib/replay/reducer";
import {
  buildTimeline,
  buildTraceTree,
  collectAmounts,
  collectCurrency,
  collectEvidence,
  collectVerdicts,
  findFinalAnswer,
  type TraceTreeNode,
} from "@/lib/replay/selectors";
import {
  DEFAULT_VIEW_PREFERENCES,
  isReplayTab,
  readViewPreferences,
  writeViewPreferences,
  type PlaybackSpeed,
  type ReplayTab,
  type ViewPreferences,
} from "@/lib/state/urlState";
import { loadViewPreferences, saveViewPreferences } from "@/lib/state/viewPreferences";

/**
 * The props of the reader.
 *
 * Why the reader takes the card of the scenario: the card is what the catalog of the site
 * publishes, and the provider has already read the bundle of the scenario it names.
 *
 * Why the reader takes the commit of the checkout: the reader opens the engineering drawer, and
 * the links of the drawer open the tree of that commit, so the drawer never points at a tree that
 * the site did not describe. The route reads the commit while the export is built and hands it
 * over here (ADR-046).
 */
export interface ReplayViewerProps {
  /** The card of the scenario in the catalog of the site. */
  readonly scenario: ScenarioIndexEntry;
  /** The commit of the checkout that the links of the engineering drawer open. */
  readonly commit: string;
}

/**
 * The identifier of the sentence that says why the drawer of the engineering tour is not tied to
 * one call of the recording.
 *
 * Why the sentence has an identifier: the control that opens the drawer points at it with
 * `aria-describedby`, so a reader of a screen reader hears the reason of the control and not only
 * its name.
 */
const ENGINEERING_DRAWER_REASON_ID = "ledgerlens-replay-engineering-drawer-reason";

/**
 * Reads the preferences of the visit out of the query string of the location.
 *
 * Why the question mark is removed: the helper of the URL contract reads a query string, and a
 * browser writes the question mark in front of it. The shape that carries a preference wins, so
 * the reader of the preferences works with either shape of the query string.
 */
function readPreferences(search: string): ViewPreferences {
  const withoutMark = search.startsWith("?") ? search.slice(1) : search;
  const plain = readViewPreferences(withoutMark);
  if (
    plain.tab !== DEFAULT_VIEW_PREFERENCES.tab ||
    plain.speed !== DEFAULT_VIEW_PREFERENCES.speed
  ) {
    return plain;
  }
  return readViewPreferences(search);
}

/**
 * Finds a span of the tree, by its identifier.
 *
 * Why the tree is walked here and not in the tree: the tree knows how to draw itself, and the
 * reader knows what selecting a span means.
 */
function findNode(nodes: readonly TraceTreeNode[], spanId: string): TraceTreeNode | null {
  for (const node of nodes) {
    if (node.spanId === spanId) {
      return node;
    }
    const found = findNode(node.children, spanId);
    if (found !== null) {
      return found;
    }
  }
  return null;
}

/**
 * Reads the artifact of the ledger and the reason of its absence out of the state.
 *
 * Why the reader does not read the network: the artifact of the ledger is read by the library of
 * the artifacts, and the reader draws what the machine holds (ADR-045).
 */
function readLedgerState(state: ReplayState): {
  readonly ledger: LedgerArtifact | null;
  readonly error: string | null;
  readonly integrity: BundleIntegrity | null;
} {
  return {
    ledger: state.ledger ?? null,
    error: state.ledgerError ?? null,
    integrity: state.ledgerIntegrity ?? null,
  };
}

/**
 * The reader of a recorded run.
 *
 * The reader draws the state of the machine: the overview of the capture, the controls of the
 * playback, the position of the visitor, the step that is announced, the tree of the
 * investigation, the timeline, the evidence of the answer, the claims of the answer and the
 * provenance of the recording.
 */
export function ReplayViewer({ scenario, commit }: ReplayViewerProps): ReactElement {
  const { state, dispatch } = useReplay();

  // The ledger of the recording, and the reason of its absence when the site published no ledger.
  const { ledger, error: ledgerError, integrity: ledgerIntegrity } = readLedgerState(state);

  const [tab, setTab] = useState<ReplayTab>(DEFAULT_VIEW_PREFERENCES.tab);
  const [speed, setSpeed] = useState<PlaybackSpeed>(DEFAULT_VIEW_PREFERENCES.speed);
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  // The drawer of the engineering tour, and the state of the visit that opens it. The drawer is
  // the same drawer that the page of the tour opens, and it is opened from here without the
  // context of a call, because the drawer of a call of the recording waits for T048.
  const [engineeringDrawerOpen, setEngineeringDrawerOpen] = useState(false);
  // The control that opened the engineering drawer, so that the focus goes back to it when the
  // drawer closes. The drawer is controlled and it is opened by a control that lives outside of
  // it, so the primitive of the dialog does not know which control opened it (ADR-046).
  const engineeringDrawerTriggerRef = useRef<HTMLButtonElement | null>(null);

  // The region that announces the step, and the phase the reader saw the last time it looked.
  const statusRegionRef = useRef<HTMLParagraphElement | null>(null);
  const previousPhaseRef = useRef<ReplayPhase | null>(null);

  // The preferences of the visit: the URL wins for the fields it carries, and the store of the
  // origin wins for the fields it does not.
  useEffect(() => {
    const stored = loadViewPreferences();
    const fromUrl = readPreferences(window.location.search);
    const params = new URLSearchParams(
      window.location.search.startsWith("?")
        ? window.location.search.slice(1)
        : window.location.search,
    );

    setTab(params.has("tab") ? fromUrl.tab : stored.tab);
    setSpeed(params.has("speed") ? fromUrl.speed : stored.speed);
  }, []);

  const applyPreferences = useCallback((nextTab: ReplayTab, nextSpeed: PlaybackSpeed) => {
    const preferences: ViewPreferences = { tab: nextTab, speed: nextSpeed };
    const search = writeViewPreferences(preferences);
    saveViewPreferences(preferences);
    // The query string of the helper carries the question mark in front, or is empty for the defaults.
    // The fragment of the address comes along, because it is a part of the address the visitor
    // brought and not a preference of the view: a deep link that points at a panel of a section
    // still points at it after the visitor changed a preference. The fragment stays the fragment and
    // is never written into the query string.
    const fragment = window.location.hash;
    window.history.replaceState(null, "", `${window.location.pathname}${search}${fragment}`);
  }, []);

  const selectSection = useCallback(
    (next: ReplayTab) => {
      setTab(next);
      applyPreferences(next, speed);
    },
    [applyPreferences, speed],
  );

  const onTabChange = useCallback(
    (value: string) => {
      // The primitive hands back the value of the tab it opened, and only the four values of the
      // contract are ever accepted.
      if (isReplayTab(value)) {
        selectSection(value);
      }
    },
    [selectSection],
  );

  const onSeek = useCallback(
    (position: number) => {
      dispatch({ type: "seek", position });
    },
    [dispatch],
  );

  const onTick = useCallback(
    (position: number) => {
      dispatch({ type: "seek", position });
    },
    [dispatch],
  );

  const onComplete = useCallback(() => {
    dispatch({ type: "completed" });
  }, [dispatch]);

  const onSpeedChange = useCallback(
    (next: PlaybackSpeed) => {
      setSpeed(next);
      applyPreferences(tab, next);
    },
    [applyPreferences, tab],
  );

  const total = state.events.length;
  const reduced = useMemo(
    () => reduceToIndex(state.events, state.position),
    [state.events, state.position],
  );

  const spans = reduced.state.spans;
  const calls: ToolCallState[] = reduced.state.toolCalls;

  const tree = useMemo(() => buildTraceTree(spans), [spans]);
  const timeline = useMemo(() => buildTimeline(state.events), [state.events]);
  const evidence = useMemo(() => collectEvidence(calls), [calls]);
  const verdicts = useMemo(() => collectVerdicts(spans), [spans]);
  const amounts = useMemo(() => collectAmounts(calls), [calls]);
  const currency = useMemo(() => collectCurrency(calls), [calls]);
  const answer = useMemo(() => findFinalAnswer(spans), [spans]);

  usePlaybackClock({
    phase: state.phase,
    position: state.position,
    total,
    speed,
    onTick,
    onComplete,
  });

  // The focus moves to the status region once, when the playback starts, and never again while the
  // recording runs: a reader that is pulled back to the region on every event of the recording
  // never hears the recording at all (FR-032).
  useEffect(() => {
    const previous = previousPhaseRef.current;
    previousPhaseRef.current = state.phase;
    if (state.phase !== "playing" || previous === "playing") {
      return;
    }
    statusRegionRef.current?.focus();
  }, [state.phase]);

  const handleSelectSpan = useCallback(
    (spanId: string) => {
      setSelectedSpanId(spanId);
      const node = findNode(tree, spanId);
      const seq = node?.startedSeq ?? null;
      if (seq === null) {
        return;
      }
      const index = state.events.findIndex((event) => event.seq === seq);
      if (index >= 0) {
        onSeek(index);
      }
    },
    [onSeek, state.events, tree],
  );

  if (state.error !== null) {
    return (
      <section aria-label="The recorded run" className="flex flex-col gap-4">
        <ReplayErrorState reason={state.error} reasons={state.refusalReasons} />
      </section>
    );
  }

  if (state.manifest === null) {
    return (
      <section aria-label="The recorded run" className="flex flex-col gap-4">
        <p className="text-sm text-text-muted">The recorded run is loading.</p>
      </section>
    );
  }

  if (total === 0) {
    return (
      <section aria-label="The recorded run" className="flex flex-col gap-4">
        <ReplayEmptyState scenarioId={scenario.id} />
      </section>
    );
  }

  const lastPosition = Math.max(total - 1, 0);
  const status = formatRunStatus(reduced.state.status);
  const provenance = summarizeProvenance({
    manifest: state.manifest,
    provenance: state.provenance ?? null,
    integrity: state.integrity,
  });

  const columns: Array<TableColumn<ToolCallState>> = [
    {
      key: "name",
      header: "Tool",
      rowHeader: true,
      render: (call) => call.name,
    },
    {
      key: "status",
      header: "Status",
      render: (call) => {
        const toolStatus = formatToolStatus(call.status);
        return <Badge tone={toolStatus.tone}>{toolStatus.label}</Badge>;
      },
    },
    {
      key: "latency",
      // the header says what the column holds, the way the header of the timeline says it: the
      // duration the capture measured, written by the formatter of the durations
      header: "Duration the capture measured",
      align: "right",
      render: (call) => formatOriginalDuration(call.latencyMs),
    },
  ];

  // The step the recording stands at, the one thing the live region announces.
  const step = reduced.state.lastSeq ?? 0;

  const items: TabItem[] = [
    {
      value: "execution",
      label: "Execution",
      content: (
        <section id="ledgerlens-section-execution" tabIndex={-1} className="flex flex-col gap-4">
          <h3 className="text-base font-semibold">The execution of the recording</h3>
          <TraceTree nodes={tree} selectedSpanId={selectedSpanId} onSelect={handleSelectSpan} />
          <TraceTimeline rows={timeline} position={state.position} onSeek={onSeek} />

          <div className="rounded-lg border border-line bg-background">
            <div className="flex flex-col gap-1 border-b border-line px-4 py-3">
              <h4 className="text-base font-semibold">The calls of the tools</h4>
              <p className="text-sm text-text-muted">
                The calls are the ones the capture recorded, with the arguments and the result it
                wrote.
              </p>
            </div>

            {/*
              The control that opens the engineering drawer. It sits in the section of the calls of
              the tools, in the tab of the execution, because that is where the visitor reads what
              the run did.

              Why the control is never disabled: the rule of the repository is that a control never
              leaves the keyboard and never carries the attribute `disabled`. The drawer of the
              engineering tour opens with no context, because it is not tied to one call of the
              recording, and the control says so with the sentence that `aria-describedby` points
              at, so a visitor that presses it and finds a drawer that is not about a call reads why
              (ADR-046).

              Why the control announces the drawer: `aria-haspopup="dialog"` tells a reader of a
              screen reader that the control opens a window, and a control that opens a window
              without saying so is a control that lies about what it does.
            */}
            <div className="flex flex-col gap-2 border-b border-line px-4 py-3">
              <div>
                <Button
                  ref={engineeringDrawerTriggerRef}
                  variant="secondary"
                  size="sm"
                  aria-haspopup="dialog"
                  aria-describedby={ENGINEERING_DRAWER_REASON_ID}
                  onClick={() => setEngineeringDrawerOpen(true)}
                >
                  Open the engineering drawer
                </Button>
              </div>
              <p id={ENGINEERING_DRAWER_REASON_ID} className="text-sm text-text-muted">
                The drawer explains the guard, the arithmetic and the verification, and it is not
                tied to one call of the recording.
              </p>
            </div>

            <Table
              caption="The calls of the tools of the recorded run"
              columns={columns}
              rows={calls}
              emptyMessage="The recording has no call of a tool yet."
            />
          </div>
        </section>
      ),
    },
    {
      value: "ledger",
      label: "Ledger",
      content: (
        <section id="ledgerlens-section-ledger" tabIndex={-1} className="flex flex-col gap-4">
          <h3 className="text-base font-semibold">The ledger of the recording</h3>
          <LedgerPanel ledger={ledger} error={ledgerError} integrity={ledgerIntegrity} />
        </section>
      ),
    },
    {
      value: "evidence",
      label: "Evidence",
      content: (
        <section id="ledgerlens-section-evidence" tabIndex={-1} className="flex flex-col gap-4">
          <h3 className="text-base font-semibold">The evidence of the recording</h3>
          <AnswerPanel answer={answer} verdicts={verdicts} evidence={evidence} />
        </section>
      ),
    },
    {
      value: "decision",
      label: "Decision",
      content: (
        <section id="ledgerlens-section-decision" tabIndex={-1} className="flex flex-col gap-4">
          <h3 className="text-base font-semibold">The decision of the recording</h3>
          <ClaimList verdicts={verdicts} />

          <section
            aria-label="The amounts of the answer"
            className="rounded-lg border border-line bg-background p-4"
          >
            <h4 className="text-base font-semibold">The amounts of the answer</h4>
            {amounts.length === 0 ? (
              <p className="mt-2 text-sm text-text-muted">The recording carries no amount yet.</p>
            ) : (
              <ul className="mt-2 flex flex-col gap-1">
                {amounts.map((amount) => (
                  <li
                    key={`${amount.name}-${amount.seq}`}
                    className="flex flex-wrap items-center gap-2 text-sm"
                  >
                    <span className="text-text-muted">{amount.name}</span>
                    <span className="font-medium text-foreground">
                      {/*
                        A percentage is not money, so it never wears the currency of the run: it is written with the
                        symbol of the percentage, and the money values keep the currency the recording read.
                      */}
                      {amount.unit === "percentage"
                        ? formatPercentage(amount.amount)
                        : formatMoney(amount.amount, amount.currency ?? currency)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </section>
      ),
    },
    {
      value: "provenance",
      label: "Provenance",
      content: (
        <section id="ledgerlens-section-provenance" tabIndex={-1}>
          <ProvenancePanel summary={provenance} />
        </section>
      ),
    },
  ];

  return (
    <section aria-label="The recorded run" className="flex flex-col gap-4">
      <RunOverview scenario={scenario} manifest={state.manifest} />

      <ReplayControls
        phase={state.phase}
        position={state.position}
        total={total}
        speed={speed}
        onPlay={() => dispatch({ type: "play" })}
        onPause={() => dispatch({ type: "pause" })}
        onStep={(delta) => dispatch({ type: "step", delta })}
        onSeek={onSeek}
        onReset={() => dispatch({ type: "reset" })}
        onSpeedChange={onSpeedChange}
      />

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
          value={state.position}
          onChange={(event) => onSeek(Number(event.target.value))}
        />

        {/*
          The live region of the step. It is polite, so it never interrupts the reader, and it
          carries the step alone, so the announcement of every event of the recording is a short
          summary and never the whole state of the run (FR-033).
        */}
        <p
          ref={statusRegionRef}
          role="status"
          aria-live="polite"
          aria-atomic="true"
          tabIndex={-1}
          className="text-sm font-medium text-foreground"
        >
          Event {step} of {total}.
        </p>

        {/*
          The status of the run stays out of the live region: it changes with the run, and it is
          read as the text of the page, not as an announcement of every event.
        */}
        <p className="text-sm text-text-muted">The status of the run is: {status.label}.</p>
      </div>

      <Tabs label="The sections of the replay" items={items} value={tab} onValueChange={onTabChange} />

      {/*
        The drawer of the engineering tour. It is the same drawer that the page of the tour opens,
        and it is opened from here without the context of a call, so it says in words that it is
        not tied to one call (ADR-046).
      */}
      <EngineeringDrawer
        open={engineeringDrawerOpen}
        onOpenChange={setEngineeringDrawerOpen}
        commit={commit}
        context={null}
        returnFocusTo={engineeringDrawerTriggerRef}
      />
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the reader at once. */
export const __all__ = ["ReplayViewerProps", "ReplayViewer"] as const;
