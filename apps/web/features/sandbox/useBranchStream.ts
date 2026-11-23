"use client";

/**
 * The hook that owns the connection to the stream of the lifecycle of the branch.
 *
 * Why this file exists: the lifecycle of a branch travels as a stream of named events on the route
 * `GET /v1/sandboxes/{sandbox_id}/events`, and the browser has to follow it (ADR-047). The client of
 * that stream, `apps/web/features/sandbox/api/branchStream.ts`, arrived with the milestone of the
 * backend and NOTHING called it; this hook is that caller, and it is the only one.
 *
 * Why the connection has a hook of its own: the panel draws what the state holds, and the state of the
 * BRANCH lives in the hook of the branch, `useBranch.ts`. The stream is NOT a phase of that machine:
 * the machine keeps its four phases, `idle`, `opening`, `ready` and `refused`, and the connection has
 * a state of its own, which lives here (ADR-047, decision eight).
 *
 * Why the hook never changes the state of the branch: the truth of a branch is the answer of
 * `GET /v1/sandboxes/{sandbox_id}` and never the stream (ADR-047). The hook says what the stream
 * said and it asks the caller to read the branch again; it never invents a state of the branch.
 *
 * Why the hook keeps ONE source open and never opens a second one by itself: the browser sends the
 * header `Last-Event-ID` by itself when it opens a source again, and it sends the exact text of the
 * last `id:` line it holds. A source that the hook closes and opens again is a source that starts
 * from the beginning, and the resume that the hub can prove is lost with it (ADR-047, decision two).
 * So the hook survives a drop by keeping the source open and by watching the browser open it again.
 *
 * Why the hook counts the events of the LIFECYCLE and nothing else: the counter of the branch counts
 * `branch.opened`, `branch.mutation.committed`, `branch.undone`, `branch.reset` and
 * `branch.expired`, and the three other names, `stream.resync`, `stream.closed` and
 * `stream.heartbeat`, belong to the connection that concerns them and move no counter (ADR-047,
 * decision three).
 *
 * Why the hook never computes a wait: the front shows the number of seconds the server wrote and it
 * never counts them with the clock of the browser, for the same reason it never counts the time that
 * is left of the expiry (FR-031, ADR-047).
 *
 * Why the state of the connection lives in the memory of the page and nowhere else: not in the URL,
 * not in the `localStorage`, not in the `sessionStorage` and not in a cookie (ADR-044).
 */

import { useEffect, useRef, useState } from "react";

import {
  formatLastEventId,
  openBranchStream,
  type BranchStreamEvent,
  type BranchStreamHandle,
  type BranchStreamOptions,
} from "@/features/sandbox/api/branchStream";
import { apiBaseUrl } from "@/lib/api/config";

/**
 * The states of the connection to the stream of the branch.
 *
 * Why the list is its own and not a phase of the branch: the machine of the branch has four phases
 * and the stream does not grow a fifth one (ADR-047, decision eight).
 *
 * Why there is a state for every word the panel shows: `idle` is the connection of a page that has
 * no branch to follow, `connecting` is the connection that is opening, `connected` is the connection
 * that is open, `reconnecting` is the connection that dropped, `closed` is the connection the server
 * ended and `refused` is the connection the front refused.
 */
export type BranchConnectionPhase =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "closed"
  | "refused";

/**
 * The options of the hook of the connection.
 *
 * Why the caller gives the branch and not the whole state of the branch: the hook follows a branch
 * and it does not read the state of the machine, so a caller that has no branch to follow gives it
 * no branch at all.
 */
export interface UseBranchStreamOptions {
  /** The identifier of the branch to follow, or null when there is no branch to follow. */
  readonly branchId: string | null;
  /**
   * Whether the branch is GONE, so that the connection was refused and not opened.
   *
   * Why the caller says it and the hook does not guess it: a branch that is not there is never half
   * drawn, and the state of the branch knows that before the hook does.
   */
  readonly branchRefused?: boolean;
  /** The origin of the backend. The default is the origin of the configuration of the site. */
  readonly baseUrl?: string;
  /**
   * The builder of the source of the stream.
   *
   * Why the caller can give it: the unit test of the hook uses a fake source and never opens a
   * socket, exactly like the unit test of the client of the stream.
   */
  readonly eventSourceFactory?: BranchStreamOptions["eventSourceFactory"];
  /** Called when the lifecycle of the branch moves, so that the caller can read the branch again. */
  readonly onLifecycleEvent?: (event: BranchStreamEvent) => void;
  /** Called when the resume could not be proven, so that the caller can read the branch again. */
  readonly onResync?: (event: BranchStreamEvent) => void;
  /** Called when the branch died, so that the caller can stop drawing it. */
  readonly onExpired?: (event: BranchStreamEvent) => void;
}

/**
 * What the page gets from the hook of the connection.
 *
 * Why the sequence of the last event is here and not in the state of the branch: the sequence
 * belongs to the connection and it is the text that the browser sends in the header `Last-Event-ID`
 * when it opens the source again.
 */
export interface UseBranchStreamResult {
  /** Where the connection stands. */
  readonly phase: BranchConnectionPhase;
  /** The last sequence of the lifecycle that this page holds, as the bare decimal integer. */
  readonly lastEventId: string | null;
  /** The last sequence of the lifecycle that this page holds, as the number of the server. */
  readonly lastSeq: number | null;
  /** The sentence that says what the connection is doing, in the words of the front. */
  readonly message: string | null;
}

/** The sentence of the connection of a page that has no branch to follow. */
const MESSAGE_IDLE = "There is no branch to follow, so the page opens no stream.";

/** The sentence of a connection that is opening. */
const MESSAGE_CONNECTING = "The stream of the branch is opening.";

/** The sentence of a connection that is open. */
const MESSAGE_CONNECTED = "The stream of the branch is open.";

/**
 * The sentence of a connection that dropped.
 *
 * Why it says what the page KEEPS and not what the browser will do: a connection that the server
 * refuses for good never comes back, and a sentence that promised a come back would be a promise the
 * front cannot keep. The page keeps the last event of the branch, and that is what the browser sends
 * in the header `Last-Event-ID` when it opens the source again (ADR-047, decision two).
 */
const MESSAGE_RECONNECTING =
  "The connection of the stream dropped. The page keeps the last event of the branch, so the stream can come back with it.";

/** The sentence of a connection that the server ended. */
const MESSAGE_CLOSED = "The server ended the stream of the branch.";

/** The sentence of a connection that ended because the branch died. */
const MESSAGE_EXPIRED = "The branch died and the stream of the branch is over.";

/** The sentence of a connection that missed an event of the branch. */
const MESSAGE_RESYNC =
  "This page missed an event of the branch, so the branch has to be read again.";

/** The sentence of a connection that the front refused because the branch is not there. */
const MESSAGE_REFUSED_BRANCH = "The branch is not there any more, so the page follows no stream.";

/** The sentence of a connection that the browser could not open. */
const MESSAGE_REFUSED_BROWSER = "The browser could not open the stream of the branch.";

/**
 * The hook of the connection to the stream of the lifecycle of the branch.
 *
 * The hook opens the source when the branch is ready, it keeps it open while the branch lives, and it
 * closes it when the branch is gone, when the branch dies, when the server ends the connection and
 * when the page goes away. It never opens a second source by itself, because the browser sends the
 * header `Last-Event-ID` by itself when it opens the source again (ADR-047).
 */
export function useBranchStream(options: UseBranchStreamOptions): UseBranchStreamResult {
  const { branchId, branchRefused = false } = options;
  const baseUrl = options.baseUrl ?? apiBaseUrl();

  const [phase, setPhase] = useState<BranchConnectionPhase>("idle");
  const [lastEventId, setLastEventId] = useState<string | null>(null);
  const [lastSeq, setLastSeq] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(MESSAGE_IDLE);

  // The options live in a reference as well, so that a caller that gives a new function on every
  // render does not make the hook open the stream again and again.
  const latest = useRef(options);
  latest.current = options;

  useEffect(() => {
    if (branchId === null) {
      // There is no branch to follow: the connection is idle, and it is refused when the branch is
      // gone and not when it was never there.
      setPhase(branchRefused ? "refused" : "idle");
      setMessage(branchRefused ? MESSAGE_REFUSED_BRANCH : MESSAGE_IDLE);
      return;
    }

    let stopped = false;
    let handle: BranchStreamHandle | null = null;

    setPhase("connecting");
    setMessage(MESSAGE_CONNECTING);
    // The sequence belongs to the branch: a branch that is not the one of before holds no sequence yet.
    setLastEventId(null);
    setLastSeq(null);

    /** Reads one event of the stream and tells the caller what it means. */
    const onEvent = (event: BranchStreamEvent): void => {
      if (stopped) {
        return;
      }
      switch (event.name) {
        case "branch.expired": {
          // The branch died: the connection is over and the front opens it no more.
          setPhase("closed");
          setMessage(MESSAGE_EXPIRED);
          handle?.close();
          latest.current.onExpired?.(event);
          return;
        }
        case "stream.closed": {
          // The server ended THIS connection: it is over and the front opens it no more.
          setPhase("closed");
          setMessage(MESSAGE_CLOSED);
          return;
        }
        case "stream.resync": {
          // The resume could not be proven: this page missed something, and the branch has to be read
          // again because the truth of a branch is its status and never the stream.
          setMessage(MESSAGE_RESYNC);
          latest.current.onResync?.(event);
          return;
        }
        case "stream.heartbeat": {
          // The heartbeat says that the connection is alive and NOTHING else.
          return;
        }
        default: {
          // An event of the lifecycle: the counter of the branch moves and the resume moves with it.
          const id = formatLastEventId(event.seq);
          if (id !== null) {
            setLastEventId(id);
            setLastSeq(event.seq);
          }
          latest.current.onLifecycleEvent?.(event);
          return;
        }
      }
    };

    try {
      handle = openBranchStream({
        baseUrl,
        branchId,
        eventSourceFactory: latest.current.eventSourceFactory,
        onEvent,
        onOpen: () => {
          if (stopped) {
            return;
          }
          setPhase("connected");
          setMessage(MESSAGE_CONNECTED);
        },
        onError: (_message) => {
          if (stopped) {
            return;
          }
          // The connection dropped. The browser opens the source again by itself and it sends the
          // header `Last-Event-ID` with the last event of the lifecycle that it holds, so the hook
          // keeps the source open and it keeps the sequence it holds.
          setPhase("reconnecting");
          setMessage(MESSAGE_RECONNECTING);
        },
      });
    } catch {
      // The browser could not open the stream at all, so the connection is refused.
      setPhase("refused");
      setMessage(MESSAGE_REFUSED_BROWSER);
      return;
    }

    return () => {
      // The page goes away or the branch changed: the source is closed, because a page that leaves a
      // stream open keeps the connection of the backend alive.
      stopped = true;
      handle.close();
    };
  }, [branchId, baseUrl, branchRefused]);

  return { phase, lastEventId, lastSeq, message };
}

/** Every symbol this module exports, so that a reader sees the whole surface of the hook at once. */
export const __all__ = [
  "BranchConnectionPhase",
  "UseBranchStreamOptions",
  "UseBranchStreamResult",
  "useBranchStream",
] as const;
