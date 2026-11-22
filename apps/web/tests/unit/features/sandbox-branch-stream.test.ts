/**
 * The tests of the client of the stream of the branch of the visitor.
 *
 * Why this file exists: the lifecycle of a branch travels as a stream of named events, and that
 * stream has a vocabulary of its own. The client of the live mode is typed to the `TraceEvent` of a
 * run and closes its source on the terminal events of a run, so the client of the branch cannot be
 * that client (ADR-047). These cases hold the two things that the client promises: the EIGHT names
 * of the branch stream and NOTHING else, and the text of the server sent events, read and written
 * without a network.
 *
 * Why the reader and the writer are pure: the shape of the stream is a contract between the facade
 * and the browser, and a contract that can only be checked with a socket open is a contract that is
 * never checked. The reader takes a piece of text and gives back the name, the sequence and the
 * payload, and the writer gives back the text the server would write.
 *
 * Every case runs with no key and no network: the fetch of the case is a fake that answers with a
 * refusal the case chooses.
 */

import { describe, expect, it } from "vitest";

import { ApiError, createApiClient } from "@/lib/api/client";
import {
  BRANCH_EVENT_TYPES,
  formatLastEventId,
  isBranchEventName,
  readBranchEvent,
  writeBranchEvent,
  type BranchEventName,
  type BranchEventPayload,
} from "@/features/sandbox/api/branchStream";

/** The identifier of the branch, as the server writes it. */
const BRANCH_ID = "sb_0123456789abcdef01234567";

/** The moment of an event, as the server writes it. */
const AT = "2026-11-22T12:00:00+00:00";

/**
 * The payload of an event with the four fields that every event carries.
 *
 * Why the helper exists: every case needs the same envelope, and a case that wrote it by hand
 * would repeat the same four fields in every test.
 */
function envelopeOf(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema_version: "1",
    branch_id: BRANCH_ID,
    seq: 1,
    at: AT,
    ...overrides,
  };
}

/**
 * The text of an event, in the shape the server sends it.
 *
 * Why the helper builds the text and not the object: the reader of the stream reads TEXT, and a
 * case that gave it an object would prove nothing about the shape of the wire.
 */
function frameOf(name: string, payload: unknown, id: string | null = "1"): string {
  const lines: string[] = [];
  if (id !== null) {
    lines.push(`id: ${id}`);
  }
  lines.push(`event: ${name}`);
  lines.push(`data: ${JSON.stringify(payload)}`);
  return `${lines.join("\n")}\n\n`;
}

/**
 * The fake fetch: it answers with the refusal the case chooses.
 *
 * Why the answer carries the headers: the wait of the server travels in the header `Retry-After`
 * and not in the body of the refusal.
 */
function fakeFetchOf(status: number, body: unknown, headers: Record<string, string> = {}): typeof fetch {
  const headerMap = new Map(Object.entries(headers).map(([name, value]) => [name.toLowerCase(), value]));
  const impl = (async () => {
    return {
      ok: false,
      status,
      headers: {
        get: (name: string) => headerMap.get(name.toLowerCase()) ?? null,
      },
      text: async () => JSON.stringify(body),
    } as unknown as Response;
  }) as unknown as typeof fetch;
  return impl;
}

/**
 * The five names of the lifecycle of the branch, with the payload that each of them carries.
 *
 * Why the list is here: the writer writes the `id:` line for the five names of the lifecycle and
 * for NOTHING else, and a case that walks the five names needs a payload of each of them.
 */
const LIFECYCLE_EVENTS: ReadonlyArray<readonly [BranchEventName, BranchEventPayload]> = [
  [
    "branch.opened",
    {
      schema_version: "1",
      branch_id: BRANCH_ID,
      seq: 1,
      at: AT,
      scenario_id: "S01",
      base_snapshot_id: "sample-42",
      base_canonical_hash: "hash_of_the_base",
      current_canonical_hash: "hash_of_the_base",
      revision: 0,
      created_at: AT,
      expires_at: AT,
      state: "active",
    },
  ],
  [
    "branch.mutation.committed",
    {
      schema_version: "1",
      branch_id: BRANCH_ID,
      seq: 2,
      at: AT,
      revision: 1,
      canonical_hash: "hash_of_the_branch",
      command_id: "cmd_0001",
      kind: "refund.apply_fx_adjustment",
    },
  ],
  [
    "branch.undone",
    {
      schema_version: "1",
      branch_id: BRANCH_ID,
      seq: 3,
      at: AT,
      revision: 0,
      canonical_hash: "hash_of_the_base",
      command_id: "cmd_0002",
      kind: "refund.apply_fx_adjustment",
      undone_event_uid: "evt_0001",
    },
  ],
  [
    "branch.reset",
    {
      schema_version: "1",
      branch_id: BRANCH_ID,
      seq: 4,
      at: AT,
      revision: 0,
      canonical_hash: "hash_of_the_base",
      base_canonical_hash: "hash_of_the_base",
    },
  ],
  [
    "branch.expired",
    {
      schema_version: "1",
      branch_id: BRANCH_ID,
      seq: 5,
      at: AT,
      expires_at: AT,
      state: "expired",
    },
  ],
];

/**
 * The three names of the stream, with the payload that each of them carries.
 *
 * Why the list is here: the three names of the stream do NOT move the counter of the branch, so
 * the writer writes no `id:` line for them, whatever the sequence the caller holds.
 */
const STREAM_EVENTS: ReadonlyArray<readonly [BranchEventName, BranchEventPayload]> = [
  [
    "stream.resync",
    {
      schema_version: "1",
      branch_id: BRANCH_ID,
      seq: 5,
      at: AT,
      last_event_id: "9",
      reason: "not_current",
    },
  ],
  [
    "stream.closed",
    {
      schema_version: "1",
      branch_id: BRANCH_ID,
      seq: 5,
      at: AT,
      reason: "branch_expired",
    },
  ],
  [
    "stream.heartbeat",
    {
      schema_version: "1",
      branch_id: BRANCH_ID,
      seq: 5,
      at: AT,
      last_seq: 5,
    },
  ],
];

describe("the client of the stream of the branch", () => {
  it("reads the id, the event and the data of an event and gives back the name, the sequence and the payload", () => {
    const read = readBranchEvent(
      frameOf(
        "branch.mutation.committed",
        envelopeOf({
          seq: 3,
          revision: 1,
          canonical_hash: "hash_of_the_branch",
          command_id: "cmd_0001",
          kind: "refund.apply_fx_adjustment",
        }),
        "3",
      ),
    );

    expect(read.ok).toBe(true);
    if (!read.ok) {
      return;
    }
    expect(read.name).toBe("branch.mutation.committed");
    expect(read.seq).toBe(3);
    expect(read.id).toBe("3");
    expect(read.payload).toMatchObject({
      schema_version: "1",
      branch_id: BRANCH_ID,
      seq: 3,
      at: AT,
      revision: 1,
      canonical_hash: "hash_of_the_branch",
      command_id: "cmd_0001",
      kind: "refund.apply_fx_adjustment",
    });
  });

  it("refuses a payload that carries no schema_version, no branch_id, no seq or no at", () => {
    for (const field of ["schema_version", "branch_id", "seq", "at"]) {
      const payload = envelopeOf();
      delete payload[field];

      const read = readBranchEvent(frameOf("branch.opened", payload));

      expect(read.ok).toBe(false);
      if (read.ok) {
        return;
      }
      expect(read.reason).toContain(field);
      expect(read.reason.length).toBeGreaterThan(0);
    }
  });

  it("names the eight events of the branch stream and accepts no other name", () => {
    expect(BRANCH_EVENT_TYPES).toEqual([
      "branch.opened",
      "branch.mutation.committed",
      "branch.undone",
      "branch.reset",
      "branch.expired",
      "stream.resync",
      "stream.closed",
      "stream.heartbeat",
    ]);
    expect(BRANCH_EVENT_TYPES).toHaveLength(8);

    for (const name of BRANCH_EVENT_TYPES) {
      expect(isBranchEventName(name)).toBe(true);
    }
    expect(isBranchEventName("span.started")).toBe(false);
    expect(isBranchEventName("branch.created")).toBe(false);

    const read = readBranchEvent(frameOf("span.started", envelopeOf()));

    expect(read.ok).toBe(false);
    if (!read.ok) {
      expect(read.reason).toContain("span.started");
    }
  });

  it("writes the Last-Event-ID as the bare decimal integer, with no prefix", () => {
    expect(formatLastEventId(42)).toBe("42");
    expect(formatLastEventId(42)).not.toMatch(/[^0-9]/);
    expect(formatLastEventId(1)).toBe("1");
    // The sequence of a branch starts at one, so a number that is not one is not a sequence.
    expect(formatLastEventId(0)).toBeNull();
    expect(formatLastEventId(1.5)).toBeNull();
  });

  it("writes an event with the three lines and the blank line", () => {
    const payload = {
      schema_version: "1",
      branch_id: BRANCH_ID,
      seq: 1,
      at: AT,
      scenario_id: "S01",
      base_snapshot_id: "sample-42",
      base_canonical_hash: "hash_of_the_base",
      current_canonical_hash: "hash_of_the_base",
      revision: 0,
      created_at: AT,
      expires_at: AT,
      state: "active",
    } satisfies BranchEventPayload;

    const text = writeBranchEvent("branch.opened", payload, 1);

    expect(text).toBe(
      `id: 1\nevent: branch.opened\ndata: ${JSON.stringify(payload)}\n\n`,
    );
  });

  it("writes the heartbeat without an id line, because the heartbeat does not move the counter", () => {
    const payload = {
      schema_version: "1",
      branch_id: BRANCH_ID,
      seq: 4,
      at: AT,
      last_seq: 4,
    } satisfies BranchEventPayload;

    const text = writeBranchEvent("stream.heartbeat", payload, null);

    expect(text).toBe(`event: stream.heartbeat\ndata: ${JSON.stringify(payload)}\n\n`);
  });

  it("writes the id line for the five names of the lifecycle, because the lifecycle moves the counter", () => {
    expect(LIFECYCLE_EVENTS).toHaveLength(5);

    for (const [name, payload] of LIFECYCLE_EVENTS) {
      const text = writeBranchEvent(name, payload, payload.seq);
      const lines = text.split("\n");

      expect(lines[0]).toBe(`id: ${payload.seq}`);
      expect(lines[1]).toBe(`event: ${name}`);
      expect(lines[2]).toBe(`data: ${JSON.stringify(payload)}`);
      expect(lines[3]).toBe("");
    }
  });

  it("writes no id line for the three names of the stream, because they do not move the counter", () => {
    // The three names of the stream belong to the connection that concerns them and they are not
    // broadcast to the other tabs of the branch, so the server writes no `id:` line for them and
    // the writer writes none either, whatever the sequence the caller holds.
    expect(STREAM_EVENTS).toHaveLength(3);

    for (const [name, payload] of STREAM_EVENTS) {
      const text = writeBranchEvent(name, payload, 7);
      const lines = text.split("\n");

      expect(lines[0]).toBe(`event: ${name}`);
      expect(lines[1]).toBe(`data: ${JSON.stringify(payload)}`);
      expect(lines.some((line) => line.startsWith("id:"))).toBe(false);
    }
  });

  it("refuses an id line that disagrees with the sequence of the payload", () => {
    const read = readBranchEvent(
      frameOf("branch.mutation.committed", envelopeOf({ seq: 3 }), "4"),
    );

    expect(read.ok).toBe(false);
    if (read.ok) {
      return;
    }
    expect(read.reason).toContain("4");
    expect(read.reason).toContain("3");
  });

  it("refuses an id line that is not the bare decimal integer of the sequence", () => {
    const read = readBranchEvent(frameOf("branch.opened", envelopeOf(), "abc"));

    expect(read.ok).toBe(false);
    if (read.ok) {
      return;
    }
    expect(read.reason).toContain("abc");
  });

  it("reads the fields by name, whatever the order of the keys of the payload", () => {
    // The server sorts the keys of the payload and the front does not, so the order of the keys is
    // not part of the contract: the reader reads the fields by name and never by position.
    const text =
      `event: branch.opened\n` +
      `data: {"at":"${AT}","seq":2,"branch_id":"${BRANCH_ID}","schema_version":"1","revision":1}\n\n`;

    const read = readBranchEvent(text);

    expect(read.ok).toBe(true);
    if (!read.ok) {
      return;
    }
    expect(read.name).toBe("branch.opened");
    expect(read.seq).toBe(2);
    expect(read.id).toBeNull();
    expect(read.payload).toMatchObject({
      schema_version: "1",
      branch_id: BRANCH_ID,
      seq: 2,
      at: AT,
      revision: 1,
    });
  });

  it("reads the refusal of the server and carries the wait of a 429 in the ApiError", async () => {
    const client = createApiClient({
      baseUrl: "http://localhost:8010",
      fetchImpl: fakeFetchOf(
        429,
        {
          code: "RESOURCE_LIMIT_EXCEEDED",
          message: "the session made too many requests, wait for the window to open again",
          retryable: true,
          request_id: "req_01",
        },
        { "Retry-After": "42" },
      ),
    });

    const failure = client.forkSandbox("S01");

    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({
      status: 429,
      code: "RESOURCE_LIMIT_EXCEEDED",
      retryable: true,
      retryAfter: "42",
    });
  });

  it("carries no wait at all when the server answers a refusal without the header", async () => {
    const client = createApiClient({
      baseUrl: "http://localhost:8010",
      fetchImpl: fakeFetchOf(429, {
        code: "RESOURCE_LIMIT_EXCEEDED",
        message: "the session holds five live branches already",
        retryable: false,
        request_id: "req_02",
      }),
    });

    const failure = client.forkSandbox("S01");

    await expect(failure).rejects.toMatchObject({
      status: 429,
      retryable: false,
      retryAfter: null,
    });
  });
});
