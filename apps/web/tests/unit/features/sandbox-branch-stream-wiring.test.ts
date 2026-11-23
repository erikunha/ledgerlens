/**
 * The tests of the wiring of the stream of the branch into the browser.
 *
 * Why this file exists: the lifecycle of a branch travels as a stream of named events on the route
 * `GET /v1/sandboxes/{sandbox_id}/events`, and the client of that stream existed with NOTHING calling
 * it (ADR-047). These cases hold what the hook of the connection promises: it opens the stream when
 * the branch is ready, it survives a drop of the connection with the resume that the hub can prove,
 * it stops when the branch dies, it never leaks a connection, and it writes nothing outside the
 * memory of the page.
 *
 * Why the stream is a fake and not a server: the shape of the stream is a contract, and a contract
 * that can only be checked with a socket open is a contract that is never checked. The fake source
 * answers the events the server writes, and the case drives them by hand.
 *
 * Why the state of the branch is not touched by any of these cases: the stream is a CONNECTION and
 * not a phase of the machine of the branch, and the machine keeps its four phases, `idle`, `opening`,
 * `ready` and `refused` (ADR-047, decision eight).
 */

import { act, render, renderHook, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BranchPanel } from "@/features/sandbox/BranchPanel";
import type { BranchStreamOptions } from "@/features/sandbox/api/branchStream";
import { useBranchStream } from "@/features/sandbox/useBranchStream";
import { branchReducer } from "@/features/sandbox/useBranch";

/** The identifier of the branch, as the server writes it. */
const BRANCH_ID = "sb_0123456789abcdef01234567";

/** The moment of an event, as the server writes it. */
const AT = "2026-11-22T12:00:00+00:00";

/** The origin of the backend, as the configuration of the site names it. */
const BASE_URL = "http://localhost:8010";

/**
 * The fake source of the stream.
 *
 * Why the fake holds the listeners by name: the client of the stream adds one listener for each of
 * the eight names, and a case that wanted to fire an event has to find the listener of that name.
 */
class FakeSource {
  /** The listener of every name of the eight. */
  readonly listeners = new Map<string, (event: MessageEvent<string>) => void>();

  /** Called when the source opens. */
  onopen: (() => void) | null = null;

  /** Called when the connection drops. */
  onerror: ((event: Event) => void) | null = null;

  /** Whether the source was closed. */
  closed = false;

  /** Adds the listener of one name of the stream. */
  addEventListener(name: string, listener: (event: MessageEvent<string>) => void): void {
    this.listeners.set(name, listener);
  }

  /** Closes the source. */
  close(): void {
    this.closed = true;
  }

  /** The browser opens the source. */
  open(): void {
    this.onopen?.();
  }

  /** The connection of the source drops. */
  drop(): void {
    this.onerror?.(new Event("error"));
  }

  /** The server writes an event of the stream. */
  emit(name: string, payload: unknown, lastEventId = ""): void {
    const listener = this.listeners.get(name);
    listener?.({ data: JSON.stringify(payload), lastEventId } as unknown as MessageEvent<string>);
  }
}

/**
 * The fake of the source of the browser, for the cases that let the panel open the stream itself.
 *
 * Why the global is stubbed and not a factory: the panel opens the stream through the client of the
 * repository, and the client builds the source of the browser when the caller gives no factory. The
 * case that proves the panel wires the stream has to walk that very path.
 */
class FakeEventSource extends FakeSource {
  /** The source that the last call built. */
  static last: FakeEventSource | null = null;

  constructor(_url: string) {
    super();
    FakeEventSource.last = this;
  }
}

/**
 * The harness of the cases: the sources that were built and the urls they were built with.
 *
 * Why the harness exists: a case has to prove that the hook opened ONE source and that it opened it
 * on the route of the stream, and the only way to see that is to hold what the client built.
 */
function harness(): {
  readonly sources: FakeSource[];
  readonly urls: string[];
  readonly factory: NonNullable<BranchStreamOptions["eventSourceFactory"]>;
} {
  const sources: FakeSource[] = [];
  const urls: string[] = [];
  const factory = (url: string): EventSource => {
    urls.push(url);
    const source = new FakeSource();
    sources.push(source);
    return source as unknown as EventSource;
  };
  return { sources, urls, factory };
}

/** The payload of an event with the four fields that every event carries. */
function envelopeOf(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema_version: "1",
    branch_id: BRANCH_ID,
    seq: 1,
    at: AT,
    ...overrides,
  };
}

/** The payload of the event of the commit, as the server writes it. */
function committedOf(seq: number): Record<string, unknown> {
  return envelopeOf({
    seq,
    revision: seq,
    canonical_hash: "hash_of_the_branch",
    command_id: "cmd_0001",
    kind: "refund.apply_fx_adjustment",
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  FakeEventSource.last = null;
});

describe("the hook of the stream of the branch", () => {
  it("opens the stream of the branch when the branch is ready and closes it when the branch is gone", () => {
    const { sources, urls, factory } = harness();
    const { rerender } = renderHook(
      ({ branchId }: { readonly branchId: string | null }) =>
        useBranchStream({ branchId, eventSourceFactory: factory }),
      { initialProps: { branchId: BRANCH_ID as string | null } },
    );

    // The route of the stream is the route of the facade, and the identifier of the branch travels in it.
    expect(urls).toEqual([`${BASE_URL}/v1/sandboxes/${BRANCH_ID}/events`]);
    expect(sources).toHaveLength(1);
    expect(sources[0]?.closed).toBe(false);

    rerender({ branchId: null });

    // The branch is gone: the connection is closed and the source is not left open on the server.
    expect(sources[0]?.closed).toBe(true);
  });

  it("forgets the sequence of the branch when the branch changes", () => {
    // The sequence of the counter belongs to the branch: the page that follows another branch holds
    // no sequence of the branch before, and showing it would be a number the server never wrote.
    const { sources, factory } = harness();
    const { result, rerender } = renderHook(
      ({ branchId }: { readonly branchId: string }) =>
        useBranchStream({ branchId, eventSourceFactory: factory }),
      { initialProps: { branchId: BRANCH_ID } },
    );

    act(() => {
      sources[0]?.open();
      sources[0]?.emit("branch.mutation.committed", committedOf(3), "3");
    });

    expect(result.current.lastEventId).toBe("3");

    rerender({ branchId: "sb_abcdef0123456789abcdef01" });

    expect(result.current.lastEventId).toBeNull();
    expect(result.current.lastSeq).toBeNull();
    expect(result.current.phase).toBe("connecting");
    expect(sources).toHaveLength(2);
    expect(sources[0]?.closed).toBe(true);
  });

  it("says that the connection is connected when the source opens", () => {
    const { sources, factory } = harness();
    const { result } = renderHook(() =>
      useBranchStream({ branchId: BRANCH_ID, eventSourceFactory: factory }),
    );

    expect(result.current.phase).toBe("connecting");

    act(() => {
      sources[0]?.open();
    });

    expect(result.current.phase).toBe("connected");
  });

  it("survives a drop of the connection and keeps the resume that the hub can prove", () => {
    const { sources, factory } = harness();
    const { result } = renderHook(() =>
      useBranchStream({ branchId: BRANCH_ID, eventSourceFactory: factory }),
    );

    act(() => {
      sources[0]?.open();
      sources[0]?.emit("branch.mutation.committed", committedOf(3), "3");
    });

    // The counter of the branch moved with the event of the lifecycle, and the text of the resume is the
    // bare decimal integer that the server accepts.
    expect(result.current.lastEventId).toBe("3");
    expect(result.current.lastSeq).toBe(3);

    act(() => {
      sources[0]?.drop();
    });

    // The browser opens the source again and it sends the header `Last-Event-ID` by itself, so the hook
    // does NOT close the source: a source that the hook closes and opens again loses the resume.
    expect(result.current.phase).toBe("reconnecting");
    expect(sources).toHaveLength(1);
    expect(sources[0]?.closed).toBe(false);
    expect(result.current.lastEventId).toBe("3");

    act(() => {
      sources[0]?.open();
    });

    expect(result.current.phase).toBe("connected");
  });

  it("lets the three events of the stream alone and keeps the counter where the lifecycle put it", () => {
    const { sources, factory } = harness();
    const { result } = renderHook(() =>
      useBranchStream({ branchId: BRANCH_ID, eventSourceFactory: factory }),
    );

    act(() => {
      sources[0]?.open();
      sources[0]?.emit("branch.mutation.committed", committedOf(3), "3");
      // The heartbeat carries the sequence of the last event of the lifecycle, and it moves nothing.
      sources[0]?.emit(
        "stream.heartbeat",
        envelopeOf({ seq: 9, last_seq: 9 }),
      );
      // The resync belongs to the connection and moves no counter either.
      sources[0]?.emit(
        "stream.resync",
        envelopeOf({ seq: 9, last_event_id: "3", reason: "not_current" }),
      );
    });

    expect(result.current.lastEventId).toBe("3");
    expect(result.current.lastSeq).toBe(3);
  });

  it("stops on the expiry of the branch and does not open the stream again", () => {
    const { sources, factory } = harness();
    const onExpired = vi.fn();
    const { result } = renderHook(() =>
      useBranchStream({ branchId: BRANCH_ID, eventSourceFactory: factory, onExpired }),
    );

    act(() => {
      sources[0]?.open();
      sources[0]?.emit(
        "branch.expired",
        envelopeOf({ seq: 4, expires_at: AT, state: "expired" }),
        "4",
      );
    });

    expect(result.current.phase).toBe("closed");
    expect(sources[0]?.closed).toBe(true);
    expect(onExpired).toHaveBeenCalledTimes(1);

    // The connection is over: the hook opens no second source and it never reconnects on its own.
    act(() => {
      sources[0]?.drop();
    });

    expect(sources).toHaveLength(1);
  });

  it("stops on the close of the stream and does not open the stream again", () => {
    const { sources, factory } = harness();
    const { result } = renderHook(() =>
      useBranchStream({ branchId: BRANCH_ID, eventSourceFactory: factory }),
    );

    act(() => {
      sources[0]?.open();
      sources[0]?.emit("stream.closed", envelopeOf({ seq: 4, reason: "branch_gone" }));
    });

    expect(result.current.phase).toBe("closed");
    expect(sources[0]?.closed).toBe(true);
    expect(sources).toHaveLength(1);
  });

  it("asks the caller to read the branch again when the resume cannot be proven", () => {
    const { sources, factory } = harness();
    const onResync = vi.fn();
    const onLifecycleEvent = vi.fn();
    const { result } = renderHook(() =>
      useBranchStream({ branchId: BRANCH_ID, eventSourceFactory: factory, onResync, onLifecycleEvent }),
    );

    act(() => {
      sources[0]?.open();
      sources[0]?.emit(
        "stream.resync",
        envelopeOf({ seq: 2, last_event_id: "1", reason: "not_current" }),
      );
    });

    expect(result.current.phase).toBe("connected");
    expect(result.current.message).toMatch(/missed an event of the branch/i);
    expect(onResync).toHaveBeenCalledTimes(1);
    // The truth of a branch is the answer of the status of the branch and never the stream.
    expect(onLifecycleEvent).not.toHaveBeenCalled();
  });

  it("tells the caller that the branch moved when the lifecycle of the branch moves", () => {
    const { sources, factory } = harness();
    const onLifecycleEvent = vi.fn();
    const { result } = renderHook(() =>
      useBranchStream({ branchId: BRANCH_ID, eventSourceFactory: factory, onLifecycleEvent }),
    );

    act(() => {
      sources[0]?.open();
      sources[0]?.emit("branch.mutation.committed", committedOf(2), "2");
    });

    expect(onLifecycleEvent).toHaveBeenCalledTimes(1);
    expect(result.current.lastEventId).toBe("2");
  });

  it("refuses the connection when the branch is gone", () => {
    const { sources, factory } = harness();
    const { result, rerender } = renderHook(
      ({ branchId, branchRefused }: { readonly branchId: string | null; readonly branchRefused: boolean }) =>
        useBranchStream({ branchId, branchRefused, eventSourceFactory: factory }),
      { initialProps: { branchId: BRANCH_ID as string | null, branchRefused: false } },
    );

    act(() => {
      sources[0]?.open();
    });

    rerender({ branchId: null, branchRefused: true });

    // The branch is gone: the connection is refused and the source of the branch before is closed.
    expect(result.current.phase).toBe("refused");
    expect(result.current.message).toMatch(/the branch is not there any more/i);
    expect(sources[0]?.closed).toBe(true);
    expect(sources).toHaveLength(1);
  });

  it("refuses the connection when the browser cannot open the stream", () => {
    const factory = (): EventSource => {
      throw new Error("the runtime has no stream of events");
    };
    const { result } = renderHook(() =>
      useBranchStream({ branchId: BRANCH_ID, eventSourceFactory: factory }),
    );

    expect(result.current.phase).toBe("refused");
    expect(result.current.message).not.toBeNull();
  });

  it("closes the source when the page goes away", () => {
    const { sources, factory } = harness();
    const { unmount } = renderHook(() =>
      useBranchStream({ branchId: BRANCH_ID, eventSourceFactory: factory }),
    );

    unmount();

    // A page that leaves a stream open keeps the connection of the backend alive.
    expect(sources[0]?.closed).toBe(true);
  });

  it("writes nothing to the URL, to the localStorage, to the sessionStorage and to a cookie", () => {
    const { sources, factory } = harness();
    const href = window.location.href;
    const { result } = renderHook(() =>
      useBranchStream({ branchId: BRANCH_ID, eventSourceFactory: factory }),
    );

    act(() => {
      sources[0]?.open();
      sources[0]?.emit("branch.mutation.committed", committedOf(2), "2");
    });

    expect(window.location.href).toBe(href);
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
    // The hook carries no wait of its own: the front never computes a wait with the clock of the browser.
    expect(Object.keys(result.current).sort()).toEqual([
      "lastEventId",
      "lastSeq",
      "message",
      "phase",
    ]);
  });

  it("does not add a phase to the state of the branch", () => {
    // The stream is a connection and not a phase of the machine of the branch: the machine keeps its
    // four phases and the connection has a state of its own (ADR-047, decision eight).
    const seen = new Set<string>();
    let state = branchReducer(undefined, { type: "sessionEnded" });
    seen.add(state.phase);
    state = branchReducer(state, { type: "fork" });
    seen.add(state.phase);
    state = branchReducer(state, {
      type: "forked",
      branchId: BRANCH_ID,
      revision: 0,
      expiresAt: AT,
      canonicalHash: "hash_of_the_base",
      branchState: "active",
      created: true,
    });
    seen.add(state.phase);
    state = branchReducer(state, {
      type: "lost",
      refusal: {
        code: "BRANCH_EXPIRED",
        message: "the branch died",
        retryable: false,
        request_id: "req_01",
      },
    });
    seen.add(state.phase);

    expect([...seen].sort()).toEqual(["idle", "opening", "ready", "refused"]);
  });
});

describe("the panel of the branch with the stream", () => {
  it("shows the state of the connection to the visitor", () => {
    vi.stubGlobal("EventSource", FakeEventSource);

    render(
      createElement(BranchPanel, {
        state: {
          phase: "ready",
          branchId: BRANCH_ID,
          revision: 3,
          expiresAt: AT,
          canonicalHash: "hash_of_the_base",
          branchState: "active",
          created: true,
          preview: null,
          diff: null,
          history: null,
          refusal: null,
        },
        onReset: () => {},
        onEndSession: () => {},
      }),
    );

    // The panel opens the stream of the branch through the client of the repository.
    expect(FakeEventSource.last).not.toBeNull();

    act(() => {
      FakeEventSource.last?.open();
    });

    const term = screen.getByText("State of the connection");
    const value = term.nextElementSibling?.textContent ?? "";
    expect(value).toBe("Connected");
    expect(screen.getByText(/the stream of the branch is open/i)).toBeInTheDocument();
  });

  it("says that there is no stream when there is no branch to follow", () => {
    vi.stubGlobal("EventSource", FakeEventSource);

    render(
      createElement(BranchPanel, {
        state: {
          phase: "idle",
          branchId: null,
          revision: null,
          expiresAt: null,
          canonicalHash: null,
          branchState: null,
          created: null,
          preview: null,
          diff: null,
          history: null,
          refusal: null,
        },
        onReset: () => {},
        onEndSession: () => {},
      }),
    );

    expect(FakeEventSource.last).toBeNull();
    expect(screen.getByText(/there is no branch to follow/i)).toBeInTheDocument();
  });
});
