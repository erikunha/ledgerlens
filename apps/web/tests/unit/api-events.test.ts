/**
 * The tests of the client of the stream.
 *
 * Why this file exists: the stream of a live run is the only part of the transport that the
 * browser opens by itself, and it has two rules of its own. The source is opened with the
 * credentials, because the cookie of the session is the identity of the visitor, and the source
 * is closed on the terminal event, because a browser that reconnects would receive the whole
 * stream of the run again, from the beginning, forever.
 *
 * Every case runs with no key and no network: the `EventSource` of the test is a fake that
 * records the listeners and never opens a socket.
 */

import { describe, expect, it, vi } from "vitest";

import { openRunStream } from "@/lib/api/events";
import { TRACE_EVENT_TYPES, type TraceEvent } from "@/lib/api/schemas";

/** The fake source: it keeps the listeners and never talks to a server. */
class FakeEventSource {
  /** Every source that was built, so that a case can look at them. */
  static readonly instances: FakeEventSource[] = [];

  /** The URL the source was opened with. */
  readonly url: string;

  /** The options the source was opened with. */
  readonly init: EventSourceInit | undefined;

  /** Whether the source was closed. */
  closed = false;

  /** The listeners, by the name of the event. */
  readonly listeners = new Map<string, Set<(event: MessageEvent) => void>>();

  onopen: ((this: EventSource, event: Event) => unknown) | null = null;

  onerror: ((this: EventSource, event: Event) => unknown) | null = null;

  constructor(url: string, init?: EventSourceInit) {
    this.url = url;
    this.init = init;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void): void {
    const known = this.listeners.get(type) ?? new Set<(event: MessageEvent) => void>();
    known.add(listener);
    this.listeners.set(type, known);
  }

  removeEventListener(type: string, listener: (event: MessageEvent) => void): void {
    this.listeners.get(type)?.delete(listener);
  }

  close(): void {
    this.closed = true;
  }

  /** Delivers one event of the stream, the way the server writes it. */
  emit(type: string, event: TraceEvent): void {
    const message = { type, data: JSON.stringify(event) } as MessageEvent;
    for (const listener of this.listeners.get(type) ?? []) {
      listener(message);
    }
  }
}

/** One trace event, with the shape the contract of the trace publishes. */
function anEvent(eventType: string, seq: number): TraceEvent {
  return {
    schema_version: "1",
    run_id: "run_0123456789abcdef",
    seq,
    at: "2026-11-21T10:00:00+00:00",
    event_type: eventType as TraceEvent["event_type"],
    payload: {},
    mode: "live_agent",
  };
}

describe("the client of the stream", () => {
  it("opens the route of the backend with the identifier of the run", () => {
    const factory = (url: string, init?: EventSourceInit) =>
      new FakeEventSource(url, init) as unknown as EventSource;

    openRunStream({
      baseUrl: "http://localhost:8010",
      runId: "run_0123456789abcdef",
      eventSourceFactory: factory,
      onEvent: () => {},
    });

    const built = FakeEventSource.instances[FakeEventSource.instances.length - 1];
    expect(built?.url).toBe("http://localhost:8010/v1/live-runs/run_0123456789abcdef/events");
  });

  it("opens the source with the credentials of the session", () => {
    const factory = (url: string, init?: EventSourceInit) =>
      new FakeEventSource(url, init) as unknown as EventSource;

    openRunStream({
      baseUrl: "http://localhost:8010",
      runId: "run_0123456789abcdef",
      eventSourceFactory: factory,
      onEvent: () => {},
    });

    const built = FakeEventSource.instances[FakeEventSource.instances.length - 1];
    expect(built?.init?.withCredentials).toBe(true);
  });

  it("registers one listener per name of the event", () => {
    const factory = (url: string, init?: EventSourceInit) =>
      new FakeEventSource(url, init) as unknown as EventSource;

    openRunStream({
      baseUrl: "http://localhost:8010",
      runId: "run_0123456789abcdef",
      eventSourceFactory: factory,
      onEvent: () => {},
    });

    const built = FakeEventSource.instances[FakeEventSource.instances.length - 1];
    for (const name of TRACE_EVENT_TYPES) {
      expect(built?.listeners.has(name)).toBe(true);
    }
    expect(built?.listeners.size).toBe(TRACE_EVENT_TYPES.length);
  });

  it("delivers the event to the caller", () => {
    const factory = (url: string, init?: EventSourceInit) =>
      new FakeEventSource(url, init) as unknown as EventSource;
    const onEvent = vi.fn();

    openRunStream({
      baseUrl: "http://localhost:8010",
      runId: "run_0123456789abcdef",
      eventSourceFactory: factory,
      onEvent,
    });

    const built = FakeEventSource.instances[FakeEventSource.instances.length - 1];
    built?.emit("span.started", anEvent("span.started", 1));

    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent.mock.calls[0]?.[0]).toMatchObject({ event_type: "span.started", seq: 1 });
  });

  it("closes the source on a terminal event", () => {
    const factory = (url: string, init?: EventSourceInit) =>
      new FakeEventSource(url, init) as unknown as EventSource;
    const onEvent = vi.fn();

    openRunStream({
      baseUrl: "http://localhost:8010",
      runId: "run_0123456789abcdef",
      eventSourceFactory: factory,
      onEvent,
    });

    const built = FakeEventSource.instances[FakeEventSource.instances.length - 1];
    built?.emit("span.started", anEvent("span.started", 1));
    expect(built?.closed).toBe(false);

    built?.emit("run.completed", anEvent("run.completed", 2));

    expect(built?.closed).toBe(true);
    expect(onEvent).toHaveBeenCalledTimes(2);
  });

  it("closes the source when the caller closes the handle", () => {
    const factory = (url: string, init?: EventSourceInit) =>
      new FakeEventSource(url, init) as unknown as EventSource;

    const handle = openRunStream({
      baseUrl: "http://localhost:8010",
      runId: "run_0123456789abcdef",
      eventSourceFactory: factory,
      onEvent: () => {},
    });

    const built = FakeEventSource.instances[FakeEventSource.instances.length - 1];
    handle.close();

    expect(built?.closed).toBe(true);
  });
});
