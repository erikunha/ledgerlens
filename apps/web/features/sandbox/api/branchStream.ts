/**
 * The client of the stream of the branch of the visitor.
 *
 * Why this file exists: the lifecycle of a branch travels as a stream of named events, on the
 * route `GET /v1/sandboxes/{sandbox_id}/events`, and the browser needs a client for that stream
 * (ADR-047). The client of the live mode, `apps/web/lib/api/events.ts`, CANNOT be reused as it is:
 * it is typed to the `TraceEvent` of a run and it closes the source on the terminal events of a
 * run, and the names of the events of a branch and their payloads are another vocabulary. A client
 * of a stream of another vocabulary that reused it would carry the vocabulary of the run into the
 * branch.
 *
 * Why the transport is the transport of the repository: this client SHARES the transport of
 * `apps/web/lib/api/client.ts` and of `apps/web/lib/api/events.ts`, and that transport is the
 * origin of the backend and the joining of the paths, `apiUrl` of `apps/web/lib/api/config.ts`,
 * plus the source of the browser opened with the credentials of the session, exactly like the
 * client of the live mode opens its source. There is no second origin and no second rule
 * (ADR-040).
 *
 * Why the browser does not open the stream yet: this milestone publishes the lifecycle on the
 * server and the front keeps polling by hand, exactly as ADR-044 said it would (ADR-047, decision
 * seven). The function that opens the connection is the API that the milestone of the browser will
 * use, and NOTHING calls it today.
 *
 * Why this file is the conscious exception of the fence of the network: the fence of
 * `apps/web/tests/unit/network-fence.test.ts` holds that every module of the frontend reads
 * nothing of the network, and it names the modules that are allowed to read it. A stream IS the
 * network, so this file has to be NAMED in that fence, the way the client of the branch and the
 * client of the live mode are named. The fence is where an exception is a name and never a
 * silence.
 *
 * Why the reader and the writer are pure: the shape of the stream is a contract between the
 * facade and the browser, and a contract that can only be checked with a socket open is a contract
 * that is never checked. The reader takes a piece of text and gives back the name, the sequence
 * and the payload, and the writer gives back the text that the server writes.
 */

import { apiUrl } from "@/lib/api/config";

/**
 * The eight names of the stream of the branch, and nothing else.
 *
 * Why the list is closed: each name means exactly one thing (ADR-047), and a name that the branch
 * stream does not use is an event of another vocabulary. The client of the live mode closes on the
 * terminal events of a run, and this list is the vocabulary of the branch.
 */
export const BRANCH_EVENT_TYPES = [
  "branch.opened",
  "branch.mutation.committed",
  "branch.undone",
  "branch.reset",
  "branch.expired",
  "stream.resync",
  "stream.closed",
  "stream.heartbeat",
] as const;

/** The name of an event of the branch stream. */
export type BranchEventName = (typeof BRANCH_EVENT_TYPES)[number];

/**
 * The four fields that every event of the branch stream carries.
 *
 * Why the four are always there: a client reads ONE shape, and the sequence travels next to the
 * revision so that the two are never confused (ADR-047). The version of the shape is the text
 * `1`, the identifier of the branch is the one of the branch of the stream, the sequence is the
 * counter of the branch and the moment is the moment of the clock of the server (FR-031).
 */
export type BranchEventEnvelope = {
  /** The version of the shape of the payload, always the text `1`. */
  readonly schema_version: string;
  /** The identifier of the branch the stream belongs to. */
  readonly branch_id: string;
  /** The sequence of the event, the same number the `id:` line carries. */
  readonly seq: number;
  /** The moment of the event, as an ISO 8601 text with a time zone. */
  readonly at: string;
};

/**
 * The first event of every stream of a branch.
 *
 * Why the name is `branch.opened` and not `branch.created`: a stream that opens on a branch that
 * was created a minute ago did not witness the creation, and the payload therefore carries the
 * facts of the creation AND the state of the branch at the moment of the opening.
 */
export type BranchOpenedEvent = BranchEventEnvelope & {
  /** The identifier of the scenario the branch was forked from. */
  readonly scenario_id: string;
  /** The identifier of the published snapshot the branch was forked from. */
  readonly base_snapshot_id: string;
  /** The hash of the published snapshot the branch was forked from. */
  readonly base_canonical_hash: string;
  /** The hash of the branch at the moment of the opening. */
  readonly current_canonical_hash: string;
  /** The revision of the branch at the moment of the opening. */
  readonly revision: number;
  /** The moment the branch was created, as the server writes it. */
  readonly created_at: string;
  /** The moment the branch dies, as the server writes it. */
  readonly expires_at: string;
  /** The state of the branch, as the server writes it. */
  readonly state: string;
};

/**
 * The event that a commit publishes.
 *
 * Why it carries the revision and the hash: the revision says where the branch stands and the
 * hash proves the state, and neither is a value that the browser may calculate.
 */
export type BranchMutationCommittedEvent = BranchEventEnvelope & {
  /** The revision the branch is at now. */
  readonly revision: number;
  /** The hash of the branch now. */
  readonly canonical_hash: string;
  /** The identifier of the request that produced the commit. */
  readonly command_id: string;
  /** The kind of the command that was committed. */
  readonly kind: string;
};

/**
 * The event that an undo publishes.
 *
 * Why it carries the event that was undone: the log of the branch is the truth of what happened,
 * and the undo points at the event it took back.
 */
export type BranchUndoneEvent = BranchEventEnvelope & {
  /** The revision the branch is at now, which went BACK. */
  readonly revision: number;
  /** The hash of the branch now. */
  readonly canonical_hash: string;
  /** The identifier of the request that produced the undo. */
  readonly command_id: string;
  /** The kind of the command that was undone. */
  readonly kind: string;
  /** The identifier of the event of the log that the undo took back. */
  readonly undone_event_uid: string;
};

/**
 * The event that a reset publishes.
 *
 * Why the revision is zero: the reset puts the branch back at the published base, and the
 * revision of a branch that never moved is zero.
 */
export type BranchResetEvent = BranchEventEnvelope & {
  /** The revision of the branch now, which is zero after a reset. */
  readonly revision: number;
  /** The hash of the branch now, which is the hash of the base. */
  readonly canonical_hash: string;
  /** The hash of the published base of the branch. */
  readonly base_canonical_hash: string;
};

/**
 * The event that says the branch outlived its time to live.
 *
 * Why the state is the text `expired`: the state of the branch is the text of the server, and the
 * browser never writes a state of its own.
 */
export type BranchExpiredEvent = BranchEventEnvelope & {
  /** The moment the branch died, as the server writes it. */
  readonly expires_at: string;
  /** The state of the branch, the text `expired`. */
  readonly state: string;
};

/**
 * The event that says the client missed something and has to read the branch again.
 *
 * Why the identifier is echoed back: the client needs to know WHICH identifier the server could
 * not prove, and the reason says whether the identifier was behind the counter of the hub or
 * unknown to it.
 */
export type StreamResyncEvent = BranchEventEnvelope & {
  /** The identifier of the last event the client sent, echoed back. */
  readonly last_event_id: string;
  /** Why the resume could not be proven: the text `not_current` or the text `unknown`. */
  readonly reason: string;
};

/**
 * The event that says the stream is over.
 *
 * Why the reason is in the payload and not in the name: the end of the stream is one event and the
 * reason of the end is a fact about it.
 */
export type StreamClosedEvent = BranchEventEnvelope & {
  /** Why the stream ended, as the server writes it. */
  readonly reason: string;
};

/**
 * The event that keeps the connection alive.
 *
 * Why it is a named event and not a comment: a comment line is invisible to the JavaScript of the
 * source, and the client has to be able to COUNT the heartbeats to detect the silence.
 */
export type StreamHeartbeatEvent = BranchEventEnvelope & {
  /** The sequence of the last event of the lifecycle the server sent on that stream. */
  readonly last_seq: number;
};

/** The payload of an event of the branch stream, one shape for each of the eight names. */
export type BranchEventPayload =
  | BranchOpenedEvent
  | BranchMutationCommittedEvent
  | BranchUndoneEvent
  | BranchResetEvent
  | BranchExpiredEvent
  | StreamResyncEvent
  | StreamClosedEvent
  | StreamHeartbeatEvent;

/**
 * One event of the branch stream, as the reader of the text gives it back.
 *
 * Why the identifier is a text and not a number: the identifier travels in the header
 * `Last-Event-ID` and the browser sends that header by itself, so the text is what travels.
 */
export interface BranchStreamEvent {
  /** The name of the event, one of the eight. */
  readonly name: BranchEventName;
  /** The sequence of the event, the same number the `id:` line carries. */
  readonly seq: number;
  /** The text of the `id:` line, or null when the event carries no `id:` line. */
  readonly id: string | null;
  /** The payload of the event, as the server wrote it. */
  readonly payload: BranchEventPayload;
}

/** The answer of the reader of an event, when the reader refuses it. */
export interface BranchEventRefusal {
  /** The reader refused the event, and this is why. */
  readonly ok: false;
  /** The reason of the refusal, in words a reader can read. */
  readonly reason: string;
}

/** The answer of the reader of an event, when the reader accepts it. */
export interface BranchEventAccepted {
  /** The reader accepted the event. */
  readonly ok: true;
  /** The name of the event, one of the eight. */
  readonly name: BranchEventName;
  /** The sequence of the event. */
  readonly seq: number;
  /** The text of the `id:` line, or null when the event carries no `id:` line. */
  readonly id: string | null;
  /** The payload of the event, as the server wrote it. */
  readonly payload: BranchEventPayload;
}

/** The answer of the reader of an event: the event, or the reason of the refusal. */
export type BranchEventRead = BranchEventAccepted | BranchEventRefusal;

/** The answer of the reader of a payload: the payload, or the reason of the refusal. */
export type BranchPayloadRead =
  | { readonly ok: true; readonly payload: BranchEventEnvelope }
  | { readonly ok: false; readonly reason: string };

/**
 * Says whether a text is the name of an event of the branch stream.
 *
 * Why the question exists: the server names every event, and a name that the branch stream does
 * not use belongs to another vocabulary and has to be refused instead of read.
 */
export function isBranchEventName(value: string): value is BranchEventName {
  return (BRANCH_EVENT_TYPES as readonly string[]).includes(value);
}

/**
 * Writes the `Last-Event-ID` of a reconnection.
 *
 * Why the bare decimal integer: the browser sends the header by itself on a reconnection of the
 * source, and the server expects the exact text of the `id:` line, so the value carries no prefix
 * and no name (ADR-047).
 *
 * Why null for a number that is not a sequence: the sequence of a branch starts at one and grows
 * by one, and a value that is not a sequence is not a resume.
 */
export function formatLastEventId(seq: number): string | null {
  if (!Number.isInteger(seq) || seq < 1) {
    return null;
  }
  return String(seq);
}

/**
 * Reads the payload of an event out of the text of its data.
 *
 * Why the four common fields are checked and the fields of the event are not: the four are the
 * shape that EVERY event carries, and the fields that belong to one name are the truth of the
 * server about that name. The caller narrows them by the name of the event.
 */
export function readBranchPayload(text: string): BranchPayloadRead {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text) as unknown;
  } catch {
    return { ok: false, reason: "the data of the event is not a JSON document" };
  }
  return checkEnvelope(parsed);
}

/**
 * Reads one event of the branch stream out of a piece of text.
 *
 * Why the reader is pure: it reads no network and no clock, so a case can hold the shape of the
 * stream without a server.
 *
 * Why the `id:` line is checked against the sequence of the payload: the `id:` of an event IS its
 * sequence, and a stream whose `id:` line and whose payload disagree is a stream the client
 * cannot trust.
 */
export function readBranchEvent(text: string): BranchEventRead {
  const frame = firstFrameOf(text);
  if (frame === null) {
    return { ok: false, reason: "the text carries no complete event" };
  }

  const name = frame.get("event");
  if (name === undefined) {
    return { ok: false, reason: "the event carries no name" };
  }
  if (!isBranchEventName(name)) {
    return {
      ok: false,
      reason: `the event carries the name ${name}, which is not a name of the branch stream`,
    };
  }

  const data = frame.get("data");
  if (data === undefined) {
    return { ok: false, reason: `the event ${name} carries no data` };
  }

  const payload = readBranchPayload(data);
  if (!payload.ok) {
    return { ok: false, reason: payload.reason };
  }

  const id = frame.get("id") ?? null;
  if (id !== null && !isBareInteger(id)) {
    return {
      ok: false,
      reason: `the id line carries ${id}, which is not the bare decimal integer of the sequence`,
    };
  }
  if (id !== null && Number(id) !== payload.payload.seq) {
    return {
      ok: false,
      reason: `the id line carries ${id} and the payload carries the sequence ${payload.payload.seq}`,
    };
  }

  return {
    ok: true,
    name,
    seq: payload.payload.seq,
    id,
    payload: payload.payload as BranchEventPayload,
  };
}

/**
 * The three names of the stream, which belong to the connection and not to the branch.
 *
 * Why the list is apart from the eight names: the eight names are the vocabulary of the stream, and
 * these three are the ones that do NOT move the counter of the branch.
 */
const STREAM_EVENT_NAMES: readonly string[] = ["stream.resync", "stream.closed", "stream.heartbeat"];

/**
 * Says whether a name is one of the three names of the stream.
 *
 * Why the question exists: the writer has to write the `id:` line for the events of the lifecycle
 * and for NOTHING else, and the three names of the stream are the ones that never carry it.
 */
function isStreamEventName(name: BranchEventName): boolean {
  return STREAM_EVENT_NAMES.includes(name);
}

/**
 * Writes one event of the branch stream in the shape the server sends it.
 *
 * Why the writer exists: the shape of the stream is a contract, and a contract that nothing can
 * write is a contract that nothing can hold. The writer writes the SAME SHAPE as the server: the
 * same lines, the same fields and the same values, and it is what the tests of the reader read
 * back.
 *
 * Why the writer is NOT the server byte for byte: the server serializes the payload with
 * `canonical_json`, which sorts the keys of the payload in alphabetical order, and the front writes
 * the keys in the order of the insertion. The ORDER OF THE KEYS of the payload is NOT part of the
 * contract, because the reader reads the fields by name and never by position. The difference is
 * deliberate: the front writes the payload it holds and the server writes the payload it built.
 *
 * Why the three names of the stream carry no `id:` line: the counter of the branch counts the
 * events of the LIFECYCLE of the branch, and `stream.resync`, `stream.closed` and
 * `stream.heartbeat` are about the connection that concerns them: they do NOT move the counter and
 * the `Last-Event-ID` of the browser must never move because of one (ADR-047).
 */
export function writeBranchEvent(
  name: BranchEventName,
  payload: BranchEventPayload,
  sequence: number | null = null,
): string {
  const lines: string[] = [];
  if (sequence !== null && !isStreamEventName(name)) {
    lines.push(`id: ${sequence}`);
  }
  lines.push(`event: ${name}`);
  lines.push(`data: ${JSON.stringify(payload)}`);
  return `${lines.join("\n")}\n\n`;
}

/**
 * The options of the stream of the branch.
 *
 * Why the source can be built by the caller: the unit test of the stream uses a fake source and
 * never opens a socket.
 */
export interface BranchStreamOptions {
  /** The origin of the backend. */
  readonly baseUrl: string;
  /** The identifier of the branch, the one that travels in the path of the route. */
  readonly branchId: string;
  /** Whether the source carries the credentials. It does, unless the caller says otherwise. */
  readonly withCredentials?: boolean;
  /** The builder of the source. The default is the source of the browser. */
  readonly eventSourceFactory?: (url: string, init?: EventSourceInit) => EventSource;
  /** Called once per event of the stream, with the event the server sent. */
  readonly onEvent: (event: BranchStreamEvent) => void;
  /** Called when the stream opens. */
  readonly onOpen?: () => void;
  /** Called when the stream fails, with the reason in words. */
  readonly onError?: (message: string) => void;
}

/**
 * The handle of an open stream of the branch.
 *
 * Why the handle: the caller closes the stream when the visitor leaves the page, and a browser
 * that leaves a stream open keeps the connection of the backend alive.
 */
export interface BranchStreamHandle {
  /** Closes the stream. */
  readonly close: () => void;
}

/**
 * Opens the stream of the lifecycle of the branch.
 *
 * Why nothing calls this today: the browser does not open the stream of the branch yet (ADR-047,
 * decision seven). The front keeps polling by hand until the milestone of the browser, and this
 * function is the API that milestone will use.
 *
 * Why one listener per name: the server names every event, and a named event never reaches the
 * generic listener of the browser, so a client that only listened to the generic one would never
 * see an event at all.
 *
 * Why the source is closed on `stream.closed`: that event is the end of the stream, and a browser
 * that reconnected would ask for a resume that the hub cannot prove.
 */
export function openBranchStream(options: BranchStreamOptions): BranchStreamHandle {
  const build =
    options.eventSourceFactory ?? ((url: string, init?: EventSourceInit) => new EventSource(url, init));
  const url = apiUrl(`/v1/sandboxes/${encodeURIComponent(options.branchId)}/events`, options.baseUrl);
  const source = build(url, { withCredentials: options.withCredentials ?? true });

  let closed = false;
  const close = (): void => {
    if (closed) {
      return;
    }
    closed = true;
    source.close();
  };

  for (const name of BRANCH_EVENT_TYPES) {
    source.addEventListener(name, (event) => {
      const message = event as MessageEvent<string>;
      const payload = readBranchPayload(message.data);
      if (!payload.ok) {
        options.onError?.(payload.reason);
        return;
      }
      options.onEvent({
        name,
        seq: payload.payload.seq,
        id: message.lastEventId === "" ? null : message.lastEventId,
        payload: payload.payload as BranchEventPayload,
      });
      if (name === "stream.closed") {
        close();
      }
    });
  }

  source.onopen = () => {
    options.onOpen?.();
  };
  source.onerror = () => {
    options.onError?.("the stream of the branch failed");
  };

  return { close };
}

/**
 * Reads the first event of a piece of text.
 *
 * Why the blank line ends the frame: that is the shape of the server sent events, and a text that
 * carries no blank line carries no complete event.
 */
function firstFrameOf(text: string): Map<string, string> | null {
  const fields = new Map<string, string>();
  for (const raw of text.split("\n")) {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line === "") {
      return fields.size > 0 ? fields : null;
    }
    if (line.startsWith(":")) {
      // A comment line keeps the connection alive and carries nothing for the client.
      continue;
    }
    const separator = line.indexOf(":");
    if (separator === -1) {
      continue;
    }
    const field = line.slice(0, separator);
    const value = line.slice(separator + 1).replace(/^ /, "");
    const known = fields.get(field);
    fields.set(field, known === undefined ? value : `${known}\n${value}`);
  }
  return null;
}

/**
 * Checks the four fields that every payload of the branch stream carries.
 *
 * Why the refusal names the field: a client that is refused a payload has to say WHICH field is
 * missing, because a reason that names nothing is a reason nobody can act on.
 */
function checkEnvelope(value: unknown): BranchPayloadRead {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return { ok: false, reason: "the payload of the event is not an object" };
  }
  const candidate = value as Record<string, unknown>;
  if (typeof candidate["schema_version"] !== "string") {
    return { ok: false, reason: "the payload of the event carries no schema_version" };
  }
  if (typeof candidate["branch_id"] !== "string") {
    return { ok: false, reason: "the payload of the event carries no branch_id" };
  }
  if (typeof candidate["seq"] !== "number" || !Number.isInteger(candidate["seq"])) {
    return { ok: false, reason: "the payload of the event carries no seq" };
  }
  if (typeof candidate["at"] !== "string") {
    return { ok: false, reason: "the payload of the event carries no at" };
  }
  return { ok: true, payload: candidate as BranchEventEnvelope };
}

/**
 * Says whether a text is the bare decimal integer of a sequence.
 *
 * Why the text and not a number: the header `Last-Event-ID` is a text, and the browser sends
 * exactly the text the server wrote.
 */
function isBareInteger(value: string): boolean {
  return /^[0-9]+$/.test(value);
}

/** Every symbol this module exports, so that a reader sees the whole surface of the client at once. */
export const __all__ = [
  "BRANCH_EVENT_TYPES",
  "BranchEventName",
  "BranchEventEnvelope",
  "BranchOpenedEvent",
  "BranchMutationCommittedEvent",
  "BranchUndoneEvent",
  "BranchResetEvent",
  "BranchExpiredEvent",
  "StreamResyncEvent",
  "StreamClosedEvent",
  "StreamHeartbeatEvent",
  "BranchEventPayload",
  "BranchStreamEvent",
  "BranchEventRefusal",
  "BranchEventAccepted",
  "BranchEventRead",
  "BranchPayloadRead",
  "isBranchEventName",
  "formatLastEventId",
  "readBranchPayload",
  "readBranchEvent",
  "writeBranchEvent",
  "BranchStreamOptions",
  "BranchStreamHandle",
  "openBranchStream",
] as const;
