"use client";

/**
 * The drawer of a tool call of the recording.
 *
 * Why this file exists: the table of the calls tells the visitor that a call happened, and the
 * drawer tells him what the call received, what it returned and what statement it ran. The call
 * is a fact of the recording, so the drawer shows that fact and nothing else (ADR-048).
 *
 * Why the drawer is built on the primitive of the design system: the sheet is a dialog of Radix,
 * so the drawer carries `role="dialog"` and `aria-modal="true"`, the focus is trapped while it
 * is open, the Escape key closes it and the focus goes back to the control that opened it. A
 * drawer written by hand would be that dialog again, and it would be that dialog worse.
 *
 * Why the drawer holds the call it was opened with: a call of the recording never changes, and a
 * drawer whose content changes under the eyes of the reader is a drawer that lies. The drawer
 * keeps the call it was given when it opened, so the recording can keep moving behind it.
 *
 * Why the drawer never dispatches an action: opening it does not move the recording, does not
 * pause it and does not change the position of the visitor. The calls of the table already
 * happened, and reading one of them changes nothing.
 *
 * Why the money of the drawer is text: the calculator of the core works with `Decimal` and the
 * recording carries the amounts as text. The drawer never calls `Number`, never multiplies an
 * amount and never rounds one, so it never writes a value that the core did not write.
 *
 * Why the statement is shown as it was recorded: a literal of a statement is a value of the
 * ledger, and the backend does not sanitise the literals today. The rule about what a published
 * recording may carry belongs to the Python core, in `ledgerlens/tools/sql.py` and in the
 * recorder that carries every statement of every span (ADR-048, decision 5). The drawer never
 * masks a literal and never says that a statement was sanitised.
 *
 * Why the drawer announces nothing: the dialog announces itself and the reader of the replay
 * keeps the one polite region of the page, so a region inside the drawer would say the same
 * thing twice (ADR-048, decision 9).
 *
 * Why the drawer reads its props only: the site is a static export with no server, and the call
 * comes from the state of the reader (ADR-048, decision 10).
 */

import { useEffect, useRef, useState } from "react";
import type { ReactElement, RefObject } from "react";

import { Badge } from "@/components/ui/Badge";
import { Sheet } from "@/components/ui/Sheet";
import { SqlCodePane } from "@/features/agent-trace/SqlCodePane";
import { formatOriginalDuration } from "@/lib/format/duration";
import { formatToolStatus } from "@/lib/format/status";
import type { ToolCallState } from "@/lib/replay/reducer";

/**
 * The props of the drawer of a tool call.
 *
 * Why the drawer is controlled by its caller: the reader of the replay owns the call that is open
 * and the state of the drawer, the way it owns the state of the engineering drawer. A drawer
 * that owned the state would force the reader to give it a state it does not have.
 */
export interface ToolCallDrawerProps {
  /** Whether the drawer is open. */
  readonly open: boolean;
  /** The function that is called with the state the visitor asked for. */
  readonly onOpenChange: (open: boolean) => void;
  /** The call the drawer shows, when it shows one. */
  readonly call: ToolCallState | null;
  /**
   * The control that opened the drawer, so that the focus goes back to it when the drawer closes.
   *
   * Why the drawer needs it: the sheet is controlled and it is opened by a cell that lives
   * outside of it, so the primitive of the dialog does not know which control opened it and the
   * focus lands on the body of the page when the drawer closes. The caller hands the cell here,
   * because the cell is the stop of the keyboard of the table and the focus has to come back to
   * it (ADR-048, decision 7).
   */
  readonly returnFocusTo?: RefObject<HTMLElement | null>;
}

/**
 * The name of the drawer when it holds no call of the recording.
 *
 * Why the name exists: the sheet always carries a title, and a title of a drawer that holds
 * nothing must still say what the drawer is.
 */
const EMPTY_TITLE = "The call of the tool";

/**
 * Tells whether a value of the recording is a dictionary.
 *
 * Why the guard exists: the outputs of a tool are typed as `unknown` in the state of the reader,
 * because a bundle written by another producer may carry anything there. Every read of an
 * output is guarded.
 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Reads the statement of a call out of the result that the recording carried.
 *
 * Why the statement is read at `data.sql`: that is where the tool of the ledger writes the
 * statement it ran (`ledgerlens/tools/sql.py`), and it is where the projection of the evidence
 * reads it (`apps/web/lib/replay/selectors.ts`). The drawer reads the same place and shows the
 * text as it was written.
 */
function readStatement(outputs: unknown): string | null {
  if (!isRecord(outputs)) {
    return null;
  }
  const data = outputs["data"];
  if (!isRecord(data)) {
    return null;
  }
  const sql = data["sql"];
  if (typeof sql !== "string" || sql.trim() === "") {
    return null;
  }
  return sql;
}

/**
 * Writes a value of the recording as the JSON text of that value, indented.
 *
 * Why the value is written as JSON and never as a number: the result of a call is whatever the
 * tool returned, and the drawer shows it exactly as the recording wrote it. A value the recording
 * does not carry is shown as nothing at all.
 */
function readJsonText(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  try {
    const text = JSON.stringify(value, null, 2);
    return text === undefined ? null : text;
  } catch {
    // a value that the JSON of the runtime cannot write is a value the drawer does not show
    return null;
  }
}

/**
 * Keeps the call the drawer was opened with.
 *
 * Why the call is captured when the drawer opens: a call of the recording is a fact, and the
 * drawer has to show that fact even when the recording moves on while the drawer is open. The
 * reader owns which call is open; the drawer only keeps the one it was given.
 */
function useHeldCall(open: boolean, call: ToolCallState | null): ToolCallState | null {
  const [held, setHeld] = useState<ToolCallState | null>(null);
  const wasOpen = useRef(false);

  useEffect(() => {
    if (!open) {
      wasOpen.current = false;
      setHeld(null);
      return;
    }
    if (!wasOpen.current) {
      wasOpen.current = true;
      // the call is taken at the moment the drawer opens and it is never replaced while the
      // drawer stays open
      setHeld(call);
    }
  }, [open, call]);

  return held ?? call;
}

/**
 * The drawer of a tool call of the recording.
 *
 * The drawer shows the identity of the call, its arguments, its result, the statement when the
 * call carries one and the error when the call ended with one. It shows them as the text of the
 * recording, and it never computes a value of its own.
 */
export function ToolCallDrawer(props: ToolCallDrawerProps): ReactElement {
  const { open, onOpenChange, call, returnFocusTo } = props;

  const shown = useHeldCall(open, call);
  const status = formatToolStatus(shown?.status ?? null);
  const statement = shown === null ? null : readStatement(shown.outputs);
  const argumentsText = shown === null ? null : readJsonText(shown.inputs);
  const resultText = shown === null ? null : readJsonText(shown.outputs);
  const error = shown?.error ?? null;
  const title = shown === null ? EMPTY_TITLE : `The call of ${shown.name}`;

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      returnFocusTo={returnFocusTo}
      title={title}
      side="right"
    >
      {shown === null ? (
        <p className="text-sm text-text-muted">The drawer carries no call of the recording.</p>
      ) : (
        <section
          aria-label={`The details of the call of ${shown.name}`}
          className="flex flex-col gap-4"
        >
          {/*
            The identity of the call: the name of the tool, the number of the event, the status
            and the duration the capture measured. It carries no heading of its own, because the
            sections of the drawer are the arguments, the result, the statement and the error, and
            the outline of the page never skips a level.
          */}
          <dl className="flex flex-col gap-1 text-sm">
            <div className="flex gap-2">
              <dt className="w-28 shrink-0 text-text-muted">Tool</dt>
              <dd className="font-medium text-foreground">{shown.name}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-28 shrink-0 text-text-muted">Event</dt>
              <dd className="font-medium text-foreground">{shown.seq}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-28 shrink-0 text-text-muted">Status</dt>
              <dd>
                <Badge tone={status.tone}>{status.label}</Badge>
              </dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-28 shrink-0 text-text-muted">Duration</dt>
              <dd className="font-medium text-foreground">
                {formatOriginalDuration(shown.latencyMs)}
              </dd>
            </div>
          </dl>

          {/*
            The arguments and the result are text that wraps, so they never push the drawer
            sideways. Only the statement scrolls, in the pane of the SQL (ADR-048, decision 4).
          */}
          <div className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold text-foreground">The arguments of the call</h3>
            {argumentsText === null ? (
              <p className="text-sm text-text-muted">
                The recording carries no argument for this call.
              </p>
            ) : (
              <pre className="min-w-0 whitespace-pre-wrap break-words rounded border border-line bg-surface-muted p-3 font-mono text-xs text-foreground">
                {argumentsText}
              </pre>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold text-foreground">The result of the call</h3>
            {resultText === null ? (
              <p className="text-sm text-text-muted">
                The recording carries no result for this call.
              </p>
            ) : (
              <pre className="min-w-0 whitespace-pre-wrap break-words rounded border border-line bg-surface-muted p-3 font-mono text-xs text-foreground">
                {resultText}
              </pre>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold text-foreground">The statement of the call</h3>
            {statement === null ? (
              <p className="text-sm text-text-muted">This call carries no statement of SQL.</p>
            ) : (
              <>
                {/*
                  The drawer says out loud that the statement is the one the capture recorded.
                  It never claims that a statement was sanitised, because it does not know it, and
                  a drawer that promises a sanitising that nobody did is a drawer that lies.
                */}
                <p className="text-sm text-text-muted">
                  This is the statement the capture recorded, exactly as it was written.
                </p>
                <SqlCodePane
                  sql={statement}
                  label={`The statement of the call of ${shown.name}`}
                />
              </>
            )}
          </div>

          {error === null || error === "" ? null : (
            <div className="flex flex-col gap-1">
              <h3 className="text-sm font-semibold text-foreground">The error of the call</h3>
              <pre className="min-w-0 whitespace-pre-wrap break-words rounded border border-line bg-surface-muted p-3 font-mono text-xs text-foreground">
                {error}
              </pre>
            </div>
          )}
        </section>
      )}
    </Sheet>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the drawer at once. */
export const __all__ = ["ToolCallDrawerProps", "ToolCallDrawer"] as const;
