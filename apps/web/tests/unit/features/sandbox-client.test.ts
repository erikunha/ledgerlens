/**
 * The tests of the client of the branch of the visitor.
 *
 * Why this file exists: the client of the branch is the ONE place where the browser of the sandbox
 * talks to the origin of the backend, and every rule of that talk is a rule of this file.
 *
 * The rules are these. Every call carries the credentials of the session, because the cookie of the
 * session is the identity of the visitor and a call without it is a call of nobody. A refusal of the
 * server arrives as an `ApiError` with the code, the message, the status, the flag of the retry and
 * the identifier of the request of the envelope, because the interface shows the reason of the
 * server and never a guess. An origin that does not answer arrives as an `ApiError` with the status
 * zero and the code `NETWORK_ERROR`, because the interface says in words which origin it tried. And
 * the client never calculates a value, so the money of an answer stays the decimal text the server
 * wrote.
 *
 * Every case runs with no key and no network: the fetch of the test is a fake that records what the
 * client asked for and answers with a body transcribed from the facade of `ledgerlens/api/sandbox.py`
 * and from the domain of the branch.
 */

import { describe, expect, it } from "vitest";

import { createSandboxClient, type SandboxClient } from "@/features/sandbox/api/sandboxClient";
import type { SandboxCommand } from "@/features/sandbox/types";
import { ApiError } from "@/lib/api/client";

/** The origin the tests talk to. */
const ORIGIN = "http://localhost:8010";

/** The identifier of the branch, the one the server writes: the prefix `sb_` and twenty four hex characters. */
const BRANCH_ID = "sb_0123456789abcdef01234567";

/** The hash of the published base of the branch. */
const HASH_OF_THE_BASE = "1f0c3a5b7d9e1123456789abcdef0123456789abcdef0123456789abcdef01";

/** The hash of the state the branch holds after the commit of the case. */
const HASH_OF_THE_BRANCH = "2a1d4b6c8e0f2234567890abcdef0123456789abcdef0123456789abcdef02";

/** The answer of the facade for the resource `Sandbox` of the contract, field for field. */
const sandboxResource = {
  id: BRANCH_ID,
  base_snapshot_id: "public-ledger-2026-01",
  snapshot_sha256: HASH_OF_THE_BASE,
  revision: 0,
  expires_at: "2026-11-22T12:00:00+00:00",
};

/** The answer of the facade for the resource `Session`, field for field. */
const sessionBody = {
  id: "session_0123456789abcdef01234567",
  expires_at: "2026-11-22T12:00:00+00:00",
  mode_capabilities: ["visitor_sandbox"],
};

/**
 * The envelope of a refusal, as the facade writes it.
 *
 * Why it is a helper: the three refusals that the state depends on are the same shape with three
 * codes, and a case that writes the envelope by hand repeats the same four fields.
 */
function refusalBody(code: string, message: string): Record<string, unknown> {
  return {
    code,
    message,
    retryable: false,
    request_id: "req_1a2b3c4d5e6f7a8b",
  };
}

/** One entry of the difference, as the projector of the domain writes it. */
const diffEntry = {
  record: "refunds",
  record_id: "R-0001",
  field: "payout_amount",
  before: "100.00",
  after: "105.00",
  value_kind: "monetary",
  currency: "USD",
};

/** One rule of the domain and the outcome of the rule over the state of the branch. */
const invariant = {
  identifier: "refund_not_above_captured",
  description: "no refund asks for more than the transaction captured",
  passed: true,
  reason: "",
};

/** The verdict of the case, as the projector of the domain writes it. */
const verdict = {
  label: "within_expected_range",
  measure: "refund_ratio",
  value: "1.05",
  low: "0.90",
  high: "1.10",
  detail: "",
};

/** The eleven fields of the answer of the preview. */
const previewBody = {
  valid: true,
  kind: "refund.apply_fx_adjustment",
  revision: 0,
  current_canonical_hash: HASH_OF_THE_BASE,
  projected_canonical_hash: HASH_OF_THE_BRANCH,
  before: { value: "100.00", currency: "USD" },
  after: { value: "105.00", currency: "USD" },
  records: [diffEntry],
  diff: [diffEntry],
  invariants: [invariant],
  verdict,
};

/** The answer of the commit: the twelve fields of the result of a mutation. */
const resultBody = {
  command_id: "cmd_0123456789abcdef01234567",
  kind: "refund.apply_fx_adjustment",
  revision: 1,
  canonical_hash: HASH_OF_THE_BRANCH,
  diff: [diffEntry],
  invariants: [invariant],
  verdict,
  replayed: false,
  stale: false,
  stale_against: null,
  undone: false,
  undone_event_uid: null,
};

/** The answer of the diff of the branch. */
const diffBody = {
  revision: 1,
  base_canonical_hash: HASH_OF_THE_BASE,
  canonical_hash: HASH_OF_THE_BRANCH,
  diff: [diffEntry],
  invariants: [invariant],
  verdict,
};

/** The answer of the history of the branch: the log of the branch and the answers it remembers. */
const historyBody = {
  revision: 1,
  canonical_hash: HASH_OF_THE_BRANCH,
  events: [
    {
      event_uid: "evt_0123456789abcdef01234567",
      event_type: "refund.fx_adjusted",
      aggregate_id: "R-0001",
      occurred_at: "2026-11-22T10:00:00+00:00",
      payload: { applied_rate: "1.05" },
      undone: false,
    },
  ],
  answers: [
    {
      branch_id: BRANCH_ID,
      idempotency_key: "cmd-0001",
      payload_digest: "9f2b6c1d8e4a7b0c3d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4",
      revision: 1,
      canonical_hash: HASH_OF_THE_BRANCH,
      response_diff: [diffEntry],
      response_verdict: verdict,
      response_invariants: [invariant],
      generation: 0,
      stale: false,
      stale_against: null,
      undone: false,
      undone_event_uid: null,
    },
  ],
};

/** The command of the case, the one the visitor previews and then commits. */
const command: SandboxCommand = {
  kind: "refund.apply_fx_adjustment",
  data: {
    refund_id: "R-0001",
    applied_rate: "1.05",
    effective_at: "2026-11-20T10:00:00+00:00",
  },
  reason: "the rate the partner applied was wrong",
};

/**
 * The ten calls of the client, so that a case can walk them one by one.
 *
 * Why the list lives here: the rule that one call is one fetch holds for every route of the
 * client, and a case that walked them one by one would repeat the same ten lines.
 */
const CALLS_OF_THE_CLIENT: ReadonlyArray<(client: SandboxClient) => Promise<unknown>> = [
  (client) => client.startSession(),
  (client) => client.endSession(),
  (client) => client.fork("S01"),
  (client) => client.status(BRANCH_ID),
  (client) => client.preview(BRANCH_ID, command),
  (client) => client.commit(BRANCH_ID, command, { revision: 0, idempotencyKey: "cmd-0001" }),
  (client) => client.undo(BRANCH_ID, { revision: 1, idempotencyKey: "undo-0001" }),
  (client) => client.reset(BRANCH_ID),
  (client) => client.diff(BRANCH_ID),
  (client) => client.history(BRANCH_ID),
];

/** The headers that every answer of a branch carries. */
const branchHeaders = {
  "X-LedgerLens-Schema-Version": "1",
  "X-LedgerLens-Branch-Hash": HASH_OF_THE_BRANCH,
  "X-LedgerLens-Branch-State": "active",
};

/** The answer that the fake fetch gives back. */
interface Answer {
  status: number;
  body: unknown;
  headers?: Record<string, string>;
}

/** One call that the fake fetch recorded. */
interface RecordedCall {
  url: string;
  init: RequestInit;
}

/**
 * A response of the fake fetch.
 *
 * It carries only what the client reads: the status, the headers and the body. The client never
 * touches anything else of the answer of the server.
 */
function fakeResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  const text = body === undefined ? "" : JSON.stringify(body);
  const headerMap = new Map(Object.entries(headers).map(([name, value]) => [name.toLowerCase(), value]));
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (name: string) => headerMap.get(name.toLowerCase()) ?? null,
    },
    text: async () => text,
    json: async () => JSON.parse(text),
  } as unknown as Response;
}

/** The fake fetch: it records every call and answers with what the case decides. */
function fakeFetch(answer: (url: string, init: RequestInit) => Answer) {
  const calls: RecordedCall[] = [];
  const impl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const requestInit = init ?? {};
    calls.push({ url: String(input), init: requestInit });
    const chosen = answer(String(input), requestInit);
    return fakeResponse(chosen.status, chosen.body, chosen.headers);
  }) as unknown as typeof fetch;
  return { impl, calls };
}

/** The client of the branch, over the fake fetch of the case. */
function clientOf(answer: (url: string, init: RequestInit) => Answer) {
  const fake = fakeFetch(answer);
  const client = createSandboxClient({ baseUrl: ORIGIN, fetchImpl: fake.impl });
  return { client, calls: fake.calls };
}

describe("the client of the branch", () => {
  it("carries the credentials of the session in every call", async () => {
    const { client, calls } = clientOf(() => ({ status: 200, body: sandboxResource }));

    await client.startSession();
    await client.endSession();
    await client.fork("S01");
    await client.status(BRANCH_ID);
    await client.preview(BRANCH_ID, command);
    await client.commit(BRANCH_ID, command, { revision: 0, idempotencyKey: "cmd-0001" });
    await client.undo(BRANCH_ID, { revision: 1, idempotencyKey: "undo-0001" });
    await client.reset(BRANCH_ID);
    await client.diff(BRANCH_ID);
    await client.history(BRANCH_ID);

    expect(calls).toHaveLength(10);
    for (const call of calls) {
      expect(call.init.credentials).toBe("include");
    }
  });

  it("calls the ten routes of the branch", async () => {
    const { client, calls } = clientOf(() => ({ status: 200, body: sandboxResource }));

    await client.startSession();
    await client.endSession();
    await client.fork("S01");
    await client.status(BRANCH_ID);
    await client.preview(BRANCH_ID, command);
    await client.commit(BRANCH_ID, command, { revision: 0, idempotencyKey: "cmd-0001" });
    await client.undo(BRANCH_ID, { revision: 1, idempotencyKey: "undo-0001" });
    await client.reset(BRANCH_ID);
    await client.diff(BRANCH_ID);
    await client.history(BRANCH_ID);

    expect(calls.map((call) => `${call.init.method} ${call.url}`)).toEqual([
      `POST ${ORIGIN}/v1/sessions`,
      `DELETE ${ORIGIN}/v1/sessions/current`,
      `POST ${ORIGIN}/v1/sandboxes`,
      `GET ${ORIGIN}/v1/sandboxes/${BRANCH_ID}`,
      `POST ${ORIGIN}/v1/sandboxes/${BRANCH_ID}/mutations/preview`,
      `POST ${ORIGIN}/v1/sandboxes/${BRANCH_ID}/mutations`,
      `POST ${ORIGIN}/v1/sandboxes/${BRANCH_ID}/undo`,
      `POST ${ORIGIN}/v1/sandboxes/${BRANCH_ID}/reset`,
      `GET ${ORIGIN}/v1/sandboxes/${BRANCH_ID}/diff`,
      `GET ${ORIGIN}/v1/sandboxes/${BRANCH_ID}/history`,
    ]);
  });

  it("makes exactly one fetch for one call, whatever the server answers", async () => {
    // The ADR says the client never retries a call and never asks for a session, and the case
    // proves it for every route and for every answer: one call is one fetch, with the answer of
    // the server whatever it is.
    const answers = [
      { status: 200, body: sandboxResource },
      { status: 401, body: refusalBody("SESSION_REQUIRED", "the session is over") },
      { status: 500, body: { detail: "something went wrong" } },
    ];

    for (const answer of answers) {
      for (const call of CALLS_OF_THE_CLIENT) {
        const { client, calls } = clientOf(() => answer);

        await call(client).catch(() => undefined);

        expect(calls).toHaveLength(1);
      }
    }
  });

  it("never asks for a session, not even when the server refuses with 401", async () => {
    const { client, calls } = clientOf(() => ({
      status: 401,
      body: refusalBody("SESSION_REQUIRED", "the session is over"),
    }));

    await expect(client.status(BRANCH_ID)).rejects.toBeInstanceOf(ApiError);

    expect(calls).toHaveLength(1);
    expect(calls[0]?.url).not.toContain("/v1/sessions");
  });

  it("turns the refusal 401 SESSION_REQUIRED into an ApiError with the envelope of the server", async () => {
    const { client } = clientOf(() => ({
      status: 401,
      body: refusalBody("SESSION_REQUIRED", "the session is over"),
    }));

    const failure = client.status(BRANCH_ID);

    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({
      status: 401,
      code: "SESSION_REQUIRED",
      message: "the session is over",
      retryable: false,
      requestId: "req_1a2b3c4d5e6f7a8b",
    });
  });

  it("turns the refusal 404 NOT_FOUND into an ApiError with the envelope of the server", async () => {
    const { client } = clientOf(() => ({
      status: 404,
      body: refusalBody("NOT_FOUND", "no sandbox is available for this session"),
    }));

    const failure = client.status(BRANCH_ID);

    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({
      status: 404,
      code: "NOT_FOUND",
      message: "no sandbox is available for this session",
      retryable: false,
      requestId: "req_1a2b3c4d5e6f7a8b",
    });
  });

  it("turns the refusal 410 BRANCH_EXPIRED into an ApiError with the envelope of the server", async () => {
    const { client } = clientOf(() => ({
      status: 410,
      body: refusalBody("BRANCH_EXPIRED", "the branch died"),
    }));

    const failure = client.status(BRANCH_ID);

    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({
      status: 410,
      code: "BRANCH_EXPIRED",
      message: "the branch died",
      retryable: false,
      requestId: "req_1a2b3c4d5e6f7a8b",
    });
  });

  it("answers 201 when the fork creates the branch", async () => {
    const { client } = clientOf(() => ({ status: 201, body: sandboxResource, headers: branchHeaders }));

    const answer = await client.fork("S01");

    expect(answer.created).toBe(true);
    expect(answer.id).toBe(BRANCH_ID);
    expect(answer.revision).toBe(0);
  });

  it("answers 200 when the fork finds the branch that already exists", async () => {
    const { client } = clientOf(() => ({ status: 200, body: sandboxResource, headers: branchHeaders }));

    const answer = await client.fork("S01");

    expect(answer.created).toBe(false);
    expect(answer.id).toBe(BRANCH_ID);
  });

  it("answers the two headers of the branch", async () => {
    const { client } = clientOf(() => ({ status: 200, body: sandboxResource, headers: branchHeaders }));

    const answer = await client.fork("S01");

    expect(answer.branchHash).toBe(HASH_OF_THE_BRANCH);
    expect(answer.branchState).toBe("active");
  });

  it("answers the resource Sandbox of the status of the branch", async () => {
    const { client } = clientOf(() => ({ status: 200, body: sandboxResource, headers: branchHeaders }));

    const answer = await client.status(BRANCH_ID);

    expect(answer.id).toBe(BRANCH_ID);
    expect(answer.base_snapshot_id).toBe("public-ledger-2026-01");
    expect(answer.snapshot_sha256).toBe(HASH_OF_THE_BASE);
    expect(answer.revision).toBe(0);
    expect(answer.expires_at).toBe("2026-11-22T12:00:00+00:00");
    expect(answer.branchHash).toBe(HASH_OF_THE_BRANCH);
  });

  it("answers the eleven fields of the preview", async () => {
    const { client } = clientOf(() => ({ status: 200, body: previewBody }));

    const answer = await client.preview(BRANCH_ID, command);

    expect(answer.valid).toBe(true);
    expect(answer.kind).toBe("refund.apply_fx_adjustment");
    expect(answer.revision).toBe(0);
    expect(answer.current_canonical_hash).toBe(HASH_OF_THE_BASE);
    expect(answer.projected_canonical_hash).toBe(HASH_OF_THE_BRANCH);
    expect(answer.before).toEqual({ value: "100.00", currency: "USD" });
    expect(answer.after).toEqual({ value: "105.00", currency: "USD" });
    expect(answer.records).toEqual([diffEntry]);
    expect(answer.diff).toEqual([diffEntry]);
    expect(answer.invariants).toEqual([invariant]);
    expect(answer.verdict).toEqual(verdict);
  });

  it("answers the flag valid at false when an invariant does not hold", async () => {
    const failed = { ...invariant, passed: false, reason: "the refund R-0001 is above the captured amount" };
    const { client } = clientOf(() => ({
      status: 200,
      body: { ...previewBody, valid: false, invariants: [failed] },
    }));

    const answer = await client.preview(BRANCH_ID, command);

    expect(answer.valid).toBe(false);
    expect(answer.invariants[0]?.passed).toBe(false);
    expect(answer.invariants[0]?.reason).toBe("the refund R-0001 is above the captured amount");
  });

  it("sends the two headers of the commit", async () => {
    const { client, calls } = clientOf(() => ({ status: 200, body: resultBody }));

    await client.commit(BRANCH_ID, command, { revision: 3, idempotencyKey: "cmd-0001" });

    const headers = calls[0]?.init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBe("cmd-0001");
    expect(headers["If-Match"]).toBe("3");
  });

  it("sends the body of the previewed command to the commit", async () => {
    const { client, calls } = clientOf(() => ({ status: 200, body: resultBody }));

    await client.commit(BRANCH_ID, command, { revision: 0, idempotencyKey: "cmd-0001" });

    const body = JSON.parse(String(calls[0]?.init.body ?? "{}")) as Record<string, unknown>;
    expect(body).toEqual({
      kind: "refund.apply_fx_adjustment",
      data: {
        refund_id: "R-0001",
        applied_rate: "1.05",
        effective_at: "2026-11-20T10:00:00+00:00",
      },
      reason: "the rate the partner applied was wrong",
    });
  });

  it("answers the result of the commit", async () => {
    const { client } = clientOf(() => ({ status: 200, body: resultBody }));

    const answer = await client.commit(BRANCH_ID, command, { revision: 0, idempotencyKey: "cmd-0001" });

    expect(answer.command_id).toBe("cmd_0123456789abcdef01234567");
    expect(answer.kind).toBe("refund.apply_fx_adjustment");
    expect(answer.revision).toBe(1);
    expect(answer.canonical_hash).toBe(HASH_OF_THE_BRANCH);
    expect(answer.diff).toEqual([diffEntry]);
    expect(answer.invariants).toEqual([invariant]);
    expect(answer.verdict).toEqual(verdict);
    expect(answer.replayed).toBe(false);
    expect(answer.stale).toBe(false);
    expect(answer.stale_against).toBeNull();
    expect(answer.undone).toBe(false);
    expect(answer.undone_event_uid).toBeNull();
  });

  it("sends an empty body and the two headers to the undo", async () => {
    const { client, calls } = clientOf(() => ({ status: 200, body: resultBody }));

    await client.undo(BRANCH_ID, { revision: 1, idempotencyKey: "undo-0001" });

    const call = calls[0];
    expect(String(call?.init.body ?? "")).toBe("");
    const headers = call?.init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBe("undo-0001");
    expect(headers["If-Match"]).toBe("1");
  });

  it("answers the resource Sandbox of the reset of the branch", async () => {
    const { client } = clientOf(() => ({ status: 200, body: sandboxResource, headers: branchHeaders }));

    const answer = await client.reset(BRANCH_ID);

    expect(answer.id).toBe(BRANCH_ID);
    expect(answer.revision).toBe(0);
    expect(answer.branchHash).toBe(HASH_OF_THE_BRANCH);
  });

  it("answers the shape of the diff of the branch", async () => {
    const { client } = clientOf(() => ({ status: 200, body: diffBody }));

    const answer = await client.diff(BRANCH_ID);

    expect(answer.revision).toBe(1);
    expect(answer.base_canonical_hash).toBe(HASH_OF_THE_BASE);
    expect(answer.canonical_hash).toBe(HASH_OF_THE_BRANCH);
    expect(answer.diff).toEqual([diffEntry]);
    expect(answer.invariants).toEqual([invariant]);
    expect(answer.verdict).toEqual(verdict);
  });

  it("answers the shape of the history of the branch", async () => {
    const { client } = clientOf(() => ({ status: 200, body: historyBody }));

    const answer = await client.history(BRANCH_ID);

    expect(answer.revision).toBe(1);
    expect(answer.canonical_hash).toBe(HASH_OF_THE_BRANCH);
    expect(answer.events).toHaveLength(1);
    expect(answer.events[0]?.event_type).toBe("refund.fx_adjusted");
    expect(answer.events[0]?.undone).toBe(false);
    expect(answer.answers).toHaveLength(1);
    expect(answer.answers[0]?.idempotency_key).toBe("cmd-0001");
    expect(answer.answers[0]?.undone).toBe(false);
  });

  it("pins the exact keys of every answer of the server", () => {
    // The answers of the server are written by hand in this file, and a hand written answer can
    // lose a key or gain one without anybody noticing. The case pins the keys of every answer:
    // the session has three, the resource of the branch has five, the preview has eleven, the
    // commit and the undo have twelve, the diff has six and the history has four.
    expect(Object.keys(sessionBody).sort()).toEqual(["expires_at", "id", "mode_capabilities"]);
    expect(Object.keys(sandboxResource).sort()).toEqual([
      "base_snapshot_id",
      "expires_at",
      "id",
      "revision",
      "snapshot_sha256",
    ]);
    expect(Object.keys(previewBody).sort()).toEqual([
      "after",
      "before",
      "current_canonical_hash",
      "diff",
      "invariants",
      "kind",
      "projected_canonical_hash",
      "records",
      "revision",
      "valid",
      "verdict",
    ]);
    expect(Object.keys(resultBody).sort()).toEqual([
      "canonical_hash",
      "command_id",
      "diff",
      "invariants",
      "kind",
      "replayed",
      "revision",
      "stale",
      "stale_against",
      "undone",
      "undone_event_uid",
      "verdict",
    ]);
    expect(Object.keys(diffBody).sort()).toEqual([
      "base_canonical_hash",
      "canonical_hash",
      "diff",
      "invariants",
      "revision",
      "verdict",
    ]);
    expect(Object.keys(historyBody).sort()).toEqual([
      "answers",
      "canonical_hash",
      "events",
      "revision",
    ]);
  });

  it("answers with the keys of the server and with the two headers of the branch", async () => {
    // The case proves that the client carries every field of the server and adds only the two
    // headers of the branch and the flag of the creation, and that no field of an answer is
    // absent: a field the server stops sending has to show up here as a missing key.
    const { client } = clientOf((url) => {
      if (url.endsWith("/v1/sessions")) {
        return { status: 201, body: sessionBody };
      }
      if (url.endsWith("/mutations/preview")) {
        return { status: 200, body: previewBody };
      }
      if (url.endsWith("/mutations") || url.endsWith("/undo")) {
        return { status: 200, body: resultBody };
      }
      if (url.endsWith("/diff")) {
        return { status: 200, body: diffBody };
      }
      if (url.endsWith("/history")) {
        return { status: 200, body: historyBody };
      }
      return { status: 200, body: sandboxResource, headers: branchHeaders };
    });

    const session = await client.startSession();
    const status = await client.status(BRANCH_ID);
    const fork = await client.fork("S01");
    const reset = await client.reset(BRANCH_ID);
    const preview = await client.preview(BRANCH_ID, command);
    const commit = await client.commit(BRANCH_ID, command, { revision: 0, idempotencyKey: "cmd-0001" });
    const undo = await client.undo(BRANCH_ID, { revision: 1, idempotencyKey: "undo-0001" });
    const diff = await client.diff(BRANCH_ID);
    const history = await client.history(BRANCH_ID);

    expect(Object.keys(session).sort()).toEqual(["expires_at", "id", "mode_capabilities"]);
    expect(Object.keys(status).sort()).toEqual([
      "base_snapshot_id",
      "branchHash",
      "branchState",
      "expires_at",
      "id",
      "revision",
      "snapshot_sha256",
    ]);
    expect(Object.keys(fork).sort()).toEqual([
      "base_snapshot_id",
      "branchHash",
      "branchState",
      "created",
      "expires_at",
      "id",
      "revision",
      "snapshot_sha256",
    ]);
    expect(Object.keys(reset).sort()).toEqual(Object.keys(status).sort());
    expect(Object.keys(preview).sort()).toEqual(Object.keys(previewBody).sort());
    expect(Object.keys(commit).sort()).toEqual(Object.keys(resultBody).sort());
    expect(Object.keys(undo).sort()).toEqual(Object.keys(resultBody).sort());
    expect(Object.keys(diff).sort()).toEqual(Object.keys(diffBody).sort());
    expect(Object.keys(history).sort()).toEqual(Object.keys(historyBody).sort());

    for (const answer of [session, status, fork, reset, preview, commit, undo, diff, history]) {
      for (const value of Object.values(answer as unknown as Record<string, unknown>)) {
        expect(value).not.toBeUndefined();
      }
    }
  });

  it("carries the decimal text of the server and never a number", async () => {
    const { client } = clientOf(() => ({ status: 200, body: diffBody }));

    const answer = await client.diff(BRANCH_ID);

    const entry = answer.diff[0];
    expect(typeof entry?.before).toBe("string");
    expect(typeof entry?.after).toBe("string");
    expect(entry?.before).toBe("100.00");
    expect(entry?.after).toBe("105.00");
    expect(entry?.currency).toBe("USD");
  });

  it("turns the refusal of the server into an ApiError", async () => {
    const { client } = clientOf(() => ({
      status: 409,
      body: {
        code: "REVISION_CONFLICT",
        message: "the branch is at revision 2 and the request expected 1",
        retryable: false,
        request_id: "req_1a2b3c4d5e6f7a8b",
      },
    }));

    const failure = client.commit(BRANCH_ID, command, { revision: 1, idempotencyKey: "cmd-0001" });

    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({
      status: 409,
      code: "REVISION_CONFLICT",
      message: "the branch is at revision 2 and the request expected 1",
      retryable: false,
      requestId: "req_1a2b3c4d5e6f7a8b",
    });
  });

  it("turns a body that is not the resource Error into an ApiError with the code HTTP_ERROR", async () => {
    const { client } = clientOf(() => ({ status: 500, body: { detail: "something went wrong" } }));

    const failure = client.status(BRANCH_ID);

    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({
      status: 500,
      code: "HTTP_ERROR",
      retryable: false,
    });
  });

  it("turns an origin that does not answer into an ApiError with the status 0", async () => {
    const impl = (async () => {
      throw new TypeError("failed to fetch");
    }) as unknown as typeof fetch;
    const client = createSandboxClient({ baseUrl: ORIGIN, fetchImpl: impl });

    const failure = client.status(BRANCH_ID);

    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({
      status: 0,
      code: "NETWORK_ERROR",
    });
    await expect(failure).rejects.toThrow(ORIGIN);
  });

  it("ends the session without a body and answers with nothing", async () => {
    const { client, calls } = clientOf(() => ({ status: 204, body: undefined }));

    const answer = await client.endSession();

    expect(answer).toBeUndefined();
    expect(String(calls[0]?.init.body ?? "")).toBe("");
    expect(calls[0]?.init.method).toBe("DELETE");
  });
});
