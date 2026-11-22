"use client";

/**
 * The panel of the branch of the visitor.
 *
 * Why this file exists: the visitor of the sandbox has to know which branch is on the screen
 * before they act on it, and every fact of the panel comes from the server. The panel shows the
 * identifier of the branch, the revision, the expiry, the state of the branch, the hash of the
 * branch, the label of the simulation, and it says in WORDS whether the branch was CREATED by the
 * fork or FOUND by it. A visitor who reloaded the page has to understand that the work of the
 * branch is still there, and a badge of a colour alone would not say it.
 *
 * Why the panel never calculates: the identifier, the revision, the expiry and the hash are the
 * texts of the server, and the panel renders them as they were sent (ADR-044). The wait of a
 * refusal of the limits is the text of the header `Retry-After`, and the panel renders it as it
 * was sent too: the panel never counts the seconds, never counts them down and never asks the
 * clock of the browser how long is left (FR-031).
 *
 * Why the panel never counts the branches of the session: the server names the count and the cap
 * in the message of the refusal, and the panel shows that message as it is. A panel that counted
 * the branches itself would count the branches it knows about and not the ones it does not.
 *
 * Why the act is not offered again after a refusal that is not retryable: the two limits of the
 * facade are told apart by the flag `retryable` and not by the code, and the cap of the branches
 * of the session is not retryable because a retry would be refused again (ADR-047).
 *
 * Why the controls are never `disabled`: a control that would do nothing carries `aria-disabled`
 * and points at its reason with `aria-describedby`, so that a visitor who pressed it and nothing
 * happened gets an answer instead of a control that vanished under the focus.
 *
 * Why the refusal has an `role="alert"`: a refusal is the answer to an act of the visitor and it
 * has to be heard at once. The region of the alert is not the polite region of the changes, and
 * the two never overlap.
 */

import type { ReactElement } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { SandboxErrorBody } from "@/features/sandbox/types";
import type { BranchState } from "@/features/sandbox/useBranch";

import "./sandbox.css";

/** The identifier of the heading of the panel, so that the section names itself. */
const PANEL_HEADING_ID = "sandbox-branch-heading";

/** The identifier of the reason of the reset, so that the control points at it. */
const RESET_REASON_ID = "sandbox-reset-reason";

/** The label of the simulation, the mode of the sandbox of the visitor. */
const SIMULATION_LABEL = "Simulation";

/** The name of the mode of the sandbox, as the card of the home page names it. */
const SIMULATION_MODE = "visitor_sandbox";

/** The sentence that says why the reset would do nothing when there is no branch. */
const RESET_REASON = "There is no branch to put back, so open a scenario first.";

/**
 * The sentence that says why the act is not offered again after a refusal that is not retryable.
 *
 * Why the sentence names the server and not the front: the flag `retryable` is what the server
 * wrote, and the panel says what it means for the visitor (ADR-047).
 */
const RESET_REASON_NOT_RETRYABLE =
  "The server refused this action and says that it will not work later, so the panel does not offer it again.";

/**
 * A refusal of the server, as the panel reads it.
 *
 * Why the wait is here: the wait of the server travels in the header `Retry-After` and it reaches
 * the refusal that the client of the branch carries in the `ApiError`. The panel shows the number
 * of seconds that the server wrote and it NEVER calculates a wait with the clock of the browser,
 * for the same reason it never calculates the time that is left of the expiry (FR-031).
 */
export interface BranchRefusal extends SandboxErrorBody {
  /** The wait the server asked for, as the header `Retry-After` wrote it, or null when it wrote none. */
  readonly retryAfter?: string | null;
}

/**
 * The state of the branch, with the refusal that may carry the wait of the server.
 *
 * Why the state is widened here and not in the hook: the shape of the refusal is the shape of the
 * answer of the server, and the panel reads it. The state of the hook stays the state of the hook.
 */
export type BranchPanelState = Omit<BranchState, "refusal"> & {
  /** The refusal of the server, with the code, the message and the wait the server wrote. */
  readonly refusal: BranchRefusal | null;
};

/**
 * The props of the panel of the branch.
 *
 * Why the panel takes the whole state: every field of the panel is a field of the state of the
 * branch, and a panel that took them one by one would let a caller leave one of them out. The
 * panel never owns the state: the hook of the branch owns it and the panel only reads it.
 */
export interface BranchPanelProps {
  /** The state of the branch, as the hook of the branch holds it. */
  readonly state: BranchPanelState;
  /** Called when the visitor asks to put the branch back at the published base. */
  readonly onReset: () => void;
  /** Called when the visitor asks to end the session of the visitor. */
  readonly onEndSession: () => void;
}

/**
 * The panel of the branch of the visitor.
 *
 * The panel draws what the state holds and it gives its acts back as callbacks. It never reads
 * the network and it never calculates a value.
 */
export function BranchPanel({ state, onReset, onEndSession }: BranchPanelProps): ReactElement {
  const hasBranch = state.branchId !== null;
  const refusal = state.refusal;

  // The wait is the TEXT of the server, and the panel shows it as it was written. A refusal that
  // carries no wait shows no wait at all.
  const wait = refusal?.retryAfter ?? null;

  // The two limits of the facade are told apart by the flag and not by the code: the rate of the
  // requests is retryable and the cap of the branches of the session is not. The panel reads the
  // flag when it decides whether to offer the act again (ADR-047).
  const mayTryAgain = refusal === null || refusal.retryable === true;

  /** Whether the act of the panel is offered, or marked with the reason why it is not. */
  const actIsOffered = hasBranch && mayTryAgain;

  /** Puts the branch back at the base, but only when there is a branch to put back. */
  function handleReset(): void {
    if (!actIsOffered) {
      return;
    }
    onReset();
  }

  return (
    <section
      className="ll-sandbox-panel rounded border border-line bg-background p-4"
      aria-labelledby={PANEL_HEADING_ID}
    >
      <h2 id={PANEL_HEADING_ID} className="text-lg font-semibold">
        The branch of the visitor
      </h2>

      <h3 className="mt-4 text-sm font-semibold uppercase tracking-wide text-text-muted">
        The state of the branch
      </h3>
      <dl className="mt-2 grid gap-2 sm:grid-cols-2">
        <div>
          <dt className="text-xs text-text-subtle">Identifier of the branch</dt>
          <dd className="font-mono text-sm">{state.branchId ?? "No branch yet"}</dd>
        </div>
        <div>
          <dt className="text-xs text-text-subtle">Revision</dt>
          <dd className="text-sm">{state.revision === null ? "No branch yet" : String(state.revision)}</dd>
        </div>
        <div>
          <dt className="text-xs text-text-subtle">Expires at</dt>
          <dd className="font-mono text-sm">{state.expiresAt ?? "No branch yet"}</dd>
        </div>
        <div>
          <dt className="text-xs text-text-subtle">State of the branch</dt>
          <dd className="text-sm">{state.branchState ?? "Not available"}</dd>
        </div>
        <div>
          <dt className="text-xs text-text-subtle">Canonical hash</dt>
          <dd className="font-mono text-sm break-all">{state.canonicalHash ?? "Not available"}</dd>
        </div>
        <div>
          <dt className="text-xs text-text-subtle">Mode of the page</dt>
          <dd className="flex items-center gap-2 text-sm">
            <Badge tone="accent">{SIMULATION_LABEL}</Badge>
            <span className="font-mono text-xs text-text-muted">{SIMULATION_MODE}</span>
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs text-text-subtle">Origin of the branch</dt>
          <dd className="flex flex-wrap items-center gap-2 text-sm">
            {state.created === null ? null : (
              <Badge tone={state.created ? "success" : "accent"}>
                {state.created ? "Created" : "Found"}
              </Badge>
            )}
            <span>
              {state.created === null
                ? "No branch yet"
                : state.created
                  ? "This branch was created for this visit."
                  : "This branch was found: it already existed and the work of the visitor is still here."}
            </span>
          </dd>
        </div>
      </dl>

      <h3 className="mt-4 text-sm font-semibold uppercase tracking-wide text-text-muted">
        The actions of the branch
      </h3>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <Button
          variant="secondary"
          aria-disabled={actIsOffered ? undefined : true}
          aria-describedby={actIsOffered ? undefined : RESET_REASON_ID}
          onClick={handleReset}
        >
          Put the branch back at the base
        </Button>
        <Button variant="ghost" onClick={onEndSession}>
          End the session
        </Button>
      </div>
      {actIsOffered ? null : (
        <p id={RESET_REASON_ID} className="mt-2 text-sm text-text-muted">
          {hasBranch ? RESET_REASON_NOT_RETRYABLE : RESET_REASON}
        </p>
      )}

      {refusal === null ? null : (
        <>
          <h3 className="mt-4 text-sm font-semibold uppercase tracking-wide text-text-muted">
            The reason of the refusal
          </h3>
          <div role="alert" className="mt-2 rounded border border-danger/40 bg-danger-light p-3">
            <p className="text-sm font-semibold text-danger-dark">{refusal.code}</p>
            <p className="text-sm text-danger-dark">{refusal.message}</p>
            {wait === null ? null : (
              <p className="text-sm text-danger-dark">
                The server asks to wait {wait} seconds before this request is tried again.
              </p>
            )}
          </div>
        </>
      )}
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the panel at once. */
export const __all__ = ["BranchRefusal", "BranchPanelState", "BranchPanelProps", "BranchPanel"] as const;
