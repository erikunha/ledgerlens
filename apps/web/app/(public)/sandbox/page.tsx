"use client";

/**
 * The route of the sandbox of the visitor.
 *
 * Why this file exists: the sandbox is the third room of the demo, and this route is its door. The visitor picks a
 * case of the published catalog, opens a branch of it and works on the branch: the visitor previews a typed mutation,
 * commits it, reads the difference between the published base and the branch, reads the log of the branch, undoes
 * the last mutation and ends the session (ADR-044).
 *
 * Why the route is a client component: the state of the branch lives in the hook of the branch, and the hook is a
 * hook of React. The site is a static export, so the page is one file, `out/sandbox.html`, and it needs no parameter.
 *
 * Why the route reads the catalog at run time: the catalog is the published file of the site, and the ONE loader of
 * the artifacts is `loadScenarioCatalog` of `lib/api/replay.ts`. The route reads it through the provider of the
 * catalog, the way the catalog of the recorded demo does, and it adds no call of its own.
 *
 * Why the URL of the route carries NOTHING: the identifier of the branch, the identifier of the scenario and the
 * revision live in the memory of the page. A reload loses them, and the fork brings the branch back.
 *
 * Why the outline of the headings is a contract: the route carries the `h1` of the page, the panel of the branch
 * carries its own `h2`, the three sections of the page carry their `h3` and the verdict of the case carries its `h4`
 * inside the section of the difference. From the `h1` to the `h4`, one level at a time, and the list of the cases
 * carries no heading of its own so that the outline starts at the `h1`.
 *
 * Why this module carries no `__all__`: a page of the App Router of Next.js may only export the fields that the
 * framework knows, and a constant of its own is an invalid export that stops the build.
 */

import Link from "next/link";
import { useMemo } from "react";
import type { ReactElement } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button, buttonClasses } from "@/components/ui/Button";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Table } from "@/components/ui/Table";
import type { TableColumn } from "@/components/ui/Table";
import { BranchPanel } from "@/features/sandbox/BranchPanel";
import { DiffView } from "@/features/sandbox/DiffView";
import { MutationForm } from "@/features/sandbox/MutationForm";
import { createSandboxClient } from "@/features/sandbox/api/sandboxClient";
import type { BranchHistoryEvent } from "@/features/sandbox/types";
import type { BranchState } from "@/features/sandbox/useBranch";
import { useBranch } from "@/features/sandbox/useBranch";
import { loadScenarioCatalog } from "@/lib/api/replay";
import { ScenarioCatalogProvider, useScenarioCatalog } from "@/lib/api/provider";

/** The identifier of the reason of the fork, so that the control points at it. */
const FORK_REASON_ID = "sandbox-fork-reason";

/** The identifier of the reason of the undo, so that the control points at it. */
const UNDO_REASON_ID = "sandbox-undo-reason";

/** The identifier of the reason of the read of the difference, so that the control points at it. */
const DIFF_REASON_ID = "sandbox-diff-reason";

/** The identifier of the reason of the read of the history, so that the control points at it. */
const HISTORY_REASON_ID = "sandbox-history-reason";

/** The sentence that says why the fork of another case cannot happen while the branch is opening. */
const OPENING_REASON = "The branch is opening, so the branch of another case cannot be opened yet.";

/** The sentence that says why the undo would do nothing when there is no branch. */
const NO_BRANCH_UNDO = "There is no branch to undo, so open a scenario first.";

/** The sentence that says why the difference cannot be read when there is no branch. */
const NO_BRANCH_DIFF = "There is no branch to read, so open a scenario first.";

/** The sentence that says why the history cannot be read when there is no branch. */
const NO_BRANCH_HISTORY = "There is no branch to read, so open a scenario first.";

/**
 * The columns of the table of the log of the branch.
 *
 * Why the events carry no revision: the revision of the branch is shown in the panel and not in the row, and the
 * place the branch stands at is the last event that is not undone (ADR-044).
 */
const HISTORY_COLUMNS: Array<TableColumn<BranchHistoryEvent>> = [
  {
    key: "event",
    header: "Event",
    rowHeader: true,
    render: (event) => event.event_uid,
  },
  {
    key: "kind",
    header: "Kind of the event",
    render: (event) => event.event_type,
  },
  {
    key: "record",
    header: "Record",
    render: (event) => event.aggregate_id,
  },
  {
    key: "moment",
    header: "Moment",
    render: (event) => event.occurred_at,
  },
  {
    key: "state",
    header: "State of the event",
    // Why the state is a word and not a tint: the state is never only a colour.
    render: (event) => (event.undone ? "Undone" : "Not undone"),
  },
];

/**
 * Says where the branch stands at, in the log of the branch.
 *
 * Why the LAST event that is not undone: an undone event is not part of the branch any more, and the row of the event
 * that was taken back carries no mark at all.
 */
function currentEventIndex(events: readonly BranchHistoryEvent[]): number {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index]?.undone === false) {
      return index;
    }
  }
  return -1;
}

/**
 * The one sentence the polite region says about the last change.
 *
 * Why the region carries one sentence and not the whole state: a reader of a screen reader has to hear what changed,
 * and a region that carries a page of text is a region nobody listens to.
 *
 * Why the sentences are ordered from the most recent change to the oldest: the sentence of the region is the last
 * thing that happened, so the visitor hears what the page just did and not what it did two steps ago.
 *
 * Why the refusal is not in this sentence: the refusal of the server is announced by the alert of the panel, and the
 * two regions never overlap.
 */
function announcementOf(state: BranchState): string {
  if (state.phase === "opening") {
    return "The branch is opening.";
  }
  if (state.phase !== "ready") {
    return "";
  }
  if (state.preview !== null) {
    return state.preview.valid
      ? "The preview is ready."
      : "The preview says that the command would break a rule of the domain.";
  }
  if (state.history !== null) {
    return "The history has been read.";
  }
  if (state.diff !== null) {
    return "The difference has been read.";
  }
  if (state.revision !== null) {
    return `The branch is at revision ${state.revision}.`;
  }
  return "";
}

/**
 * The route of the sandbox of the visitor.
 *
 * The route mounts the provider of the catalog and the room of the sandbox. The catalog is read once, at run time,
 * through the one loader of the published artifacts.
 */
export default function SandboxPage(): ReactElement {
  return (
    <ScenarioCatalogProvider loader={loadScenarioCatalog}>
      <SandboxRoom />
    </ScenarioCatalogProvider>
  );
}

/**
 * The room of the sandbox: the cases, the branch and the three sections of the work on the branch.
 *
 * Why the client of the branch is built once: the client holds the origin of the backend and nothing else, and a
 * client built again on every render would be a client that nobody waits for.
 */
function SandboxRoom(): ReactElement {
  const { scenarios, error, status } = useScenarioCatalog();
  const client = useMemo(() => createSandboxClient(), []);
  const branch = useBranch({ client });
  const { state } = branch;

  const hasBranch = state.branchId !== null;
  const opening = state.phase === "opening";
  const current = currentEventIndex(state.history?.events ?? []);

  return (
    <div className="mx-auto flex w-full max-w-content flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>mode: visitor_sandbox</Badge>
        </div>
        <h1 className="text-3xl font-semibold">The sandbox of the visitor</h1>
        <p className="max-w-2xl text-text-muted">
          The sandbox is a simulation of the work of the demo: it forks a published case into a branch of your own
          session, and you build a typed mutation on it, read what it would do and commit it. It asks no provider and
          it spends no money of your own.
        </p>
        <p className="text-sm text-text-subtle">
          The recorded demo and the live mode are the two other rooms of the demo:{" "}
          <Link className={buttonClasses("ghost", "sm")} href="/replay">
            Open the recorded demo
          </Link>{" "}
          <Link className={buttonClasses("ghost", "sm")} href="/live">
            Open the live mode
          </Link>
        </p>
      </header>

      <p role="status" aria-live="polite" aria-atomic="true" className="text-sm text-text-muted">
        {announcementOf(state)}
      </p>

      <section aria-label="The published scenarios" className="flex flex-col gap-4">
        {error === null ? null : (
          <div role="alert" className="rounded-lg border border-danger/40 bg-danger-light p-4">
            <p className="text-sm text-danger-dark">{error}</p>
          </div>
        )}

        <p className="text-sm text-text-muted">
          {status === "ready"
            ? "Pick a case of the published catalog and open its branch. The branch lives on the origin of the backend, in the session of your visit."
            : error === null
              ? "The catalog of the scenarios is being read."
              : "The catalog of the scenarios could not be read."}
        </p>

        {/*
          The catalog is read in the browser, and the reading takes a moment. The placeholder of the
          reading is on the screen while it lasts, because a section with no case in it reads as a
          catalog with no case in it.
        */}
        {status === "idle" || status === "loading" ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-24 w-full" label="The catalog of the scenarios is being read" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : null}

        <ul className="flex flex-col gap-3">
          {scenarios.map((scenario) => (
            <li key={scenario.id}>
              <Card>
                <CardHeader>
                  <p className="text-base font-semibold text-foreground">
                    {scenario.id} - {scenario.question}
                  </p>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap items-center gap-3">
                    <Button
                      aria-disabled={opening ? true : undefined}
                      aria-describedby={opening ? FORK_REASON_ID : undefined}
                      onClick={() => void branch.open(scenario.id)}
                    >
                      Open the branch of {scenario.id}
                    </Button>
                    {scenario.data_origin === undefined ? null : (
                      <span className="text-xs text-text-subtle">data: {scenario.data_origin}</span>
                    )}
                    {scenario.status === undefined ? null : <Badge>{scenario.status}</Badge>}
                  </div>
                  {/*
                    The concepts of the scenario are part of what the catalog publishes (FR-003), and a
                    card that throws them away hides what the scenario demonstrates. They are words and
                    not a tint, so a reader that does not see the badge reads the concept all the same.
                  */}
                  {scenario.concepts !== undefined && scenario.concepts.length > 0 ? (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className="text-xs text-text-subtle">concepts:</span>
                      {scenario.concepts.map((concept) => (
                        <Badge key={concept}>{concept}</Badge>
                      ))}
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>

        {opening ? (
          <p id={FORK_REASON_ID} className="text-sm text-text-muted">
            {OPENING_REASON}
          </p>
        ) : null}
      </section>

      <BranchPanel
        state={state}
        onReset={() => void branch.reset()}
        onEndSession={() => void branch.endSession()}
      />

      <section aria-labelledby="sandbox-mutation-heading" className="flex flex-col gap-3">
        <h3 id="sandbox-mutation-heading" className="text-lg font-semibold">
          The mutation
        </h3>
        <MutationForm
          state={state}
          canCommit={branch.canCommit}
          commitReason={branch.commitReason}
          onPreview={(command) => void branch.preview(command)}
          onCommit={() => void branch.commit()}
        />
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            aria-disabled={hasBranch ? undefined : true}
            aria-describedby={hasBranch ? undefined : UNDO_REASON_ID}
            onClick={() => void branch.undo()}
          >
            Undo the last mutation
          </Button>
        </div>
        {hasBranch ? null : (
          <p id={UNDO_REASON_ID} className="text-sm text-text-muted">
            {NO_BRANCH_UNDO}
          </p>
        )}
      </section>

      <section aria-labelledby="sandbox-difference-heading" className="flex flex-col gap-3">
        <h3 id="sandbox-difference-heading" className="text-lg font-semibold">
          The difference
        </h3>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            aria-disabled={hasBranch ? undefined : true}
            aria-describedby={hasBranch ? undefined : DIFF_REASON_ID}
            onClick={() => void branch.readDiff()}
          >
            Read the difference
          </Button>
        </div>
        {hasBranch ? null : (
          <p id={DIFF_REASON_ID} className="text-sm text-text-muted">
            {NO_BRANCH_DIFF}
          </p>
        )}
        <DiffView diff={state.diff} />
      </section>

      <section aria-labelledby="sandbox-history-heading" className="flex flex-col gap-3">
        <h3 id="sandbox-history-heading" className="text-lg font-semibold">
          The history
        </h3>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            aria-disabled={hasBranch ? undefined : true}
            aria-describedby={hasBranch ? undefined : HISTORY_REASON_ID}
            onClick={() => void branch.readHistory()}
          >
            Read the history
          </Button>
        </div>
        {hasBranch ? null : (
          <p id={HISTORY_REASON_ID} className="text-sm text-text-muted">
            {NO_BRANCH_HISTORY}
          </p>
        )}
        {state.history === null ? (
          <p className="ll-sandbox-empty text-sm text-text-muted">The history has not been read yet.</p>
        ) : (
          <Table
            caption="The log of the branch"
            columns={HISTORY_COLUMNS}
            rows={state.history.events}
            rowAttributes={(_event, index) => (index === current ? { "aria-current": "true" } : {})}
            emptyMessage="The branch holds no event yet."
          />
        )}
      </section>
    </div>
  );
}
