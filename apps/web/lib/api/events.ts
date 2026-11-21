/**
 * The client of the stream of a run.
 *
 * Why this file exists: the trace of a live run reaches the browser as a stream of server sent
 * events, on the route of the backend (`GET /v1/live-runs/{run_id}/events`). The browser cannot
 * read a stream with `fetch`, so it uses `EventSource`, and `EventSource` has two rules of its
 * own.
 *
 * The first rule: the source is opened with the credentials, so the browser sends the cookie of
 * the session of the backend origin. The cookie is the identity of the visitor.
 *
 * The second rule: the source is closed on the terminal event. The backend closes the stream when
 * the run ends, and a browser that reconnects would receive the whole stream of the run again,
 * from the beginning, forever.
 *
 * The client never sends a header with the source, because `EventSource` cannot: the stream needs
 * no handle, the cookie of the session is the identity.
 */

import { apiUrl } from "@/lib/api/config";
import { TERMINAL_EVENT_TYPES } from "@/lib/api/live";
import { TRACE_EVENT_TYPES, type TraceEvent } from "@/lib/api/schemas";

/**
 * The options of the stream.
 *
 * Why the source can be built by the caller: the unit test of the stream uses a fake source and
 * never opens a socket.
 */
export interface LiveStreamOptions {
  /** The origin of the backend. */
  baseUrl: string;
  /** The identifier of the run, the one that travels in the path of the route. */
  runId: string;
  /** Whether the source carries the credentials. It does, unless the caller says otherwise. */
  withCredentials?: boolean;
  /** The builder of the source. The default is the `EventSource` of the browser. */
  eventSourceFactory?: (url: string, init?: EventSourceInit) => EventSource;
  /** Called once per event of the stream, with the event the server sent. */
  onEvent: (event: TraceEvent) => void;
  /** Called when the stream opens. */
  onOpen?: () => void;
  /** Called when the stream fails, with the reason in words. */
  onError?: (message: string) => void;
}

/**
 * The handle of an open stream.
 *
 * Why the handle: the caller closes the stream when the visitor leaves the page, and a browser
 * that leaves a stream open keeps the connection of the backend alive.
 */
export interface LiveStreamHandle {
  /** Closes the stream. */
  close: () => void;
}

/**
 * Opens the stream of the events of a run.
 *
 * Why one listener per name: the server names every event, and a named event never reaches the
 * generic `message` listener of the browser, so a client that only listens to `message` would
 * never see an event at all.
 */
export function openRunStream(options: LiveStreamOptions): LiveStreamHandle {
  const build =
    options.eventSourceFactory ?? ((url: string, init?: EventSourceInit) => new EventSource(url, init));
  const url = apiUrl(`/v1/live-runs/${encodeURIComponent(options.runId)}/events`, options.baseUrl);
  const source = build(url, { withCredentials: options.withCredentials ?? true });

  let closed = false;
  const close = (): void => {
    if (closed) {
      return;
    }
    closed = true;
    source.close();
  };

  for (const name of TRACE_EVENT_TYPES) {
    source.addEventListener(name, (event) => {
      const message = event as MessageEvent<string>;
      let parsed: TraceEvent;
      try {
        parsed = JSON.parse(message.data) as TraceEvent;
      } catch {
        options.onError?.("the stream carried an event that is not a trace event");
        return;
      }
      options.onEvent(parsed);
      if (TERMINAL_EVENT_TYPES.includes(parsed.event_type)) {
        close();
      }
    });
  }

  source.onopen = () => {
    options.onOpen?.();
  };
  source.onerror = () => {
    options.onError?.("the stream of the run failed");
  };

  return { close };
}
