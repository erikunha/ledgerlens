/**
 * The test of the state of the branch of the visitor.
 *
 * Why this test exists: the state of the branch lives in the memory of the page and nowhere else,
 * and the rules that keep it honest are the rules of the ADR-044. Three of them are worth a test
 * of their own. The machine has four phases and a branch that is not there is never half drawn.
 * The session is asked for ONLY when the server refuses with `401 SESSION_REQUIRED`, and the call
 * is retried exactly once, because every `POST /v1/sessions` issues a new session and a visitor
 * that got one on every visit would lose the branch of the previous visit. And a mutation is
 * committed only after a valid preview, with the key of that preview, so that a second press of
 * the commit is the same request delivered twice.
 *
 * Every case runs with no key and no network: the client of the branch is a stub, and the stub
 * answers with the shapes of the facade.
 */

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { branchReducer, useBranch, type UseBranchResult } from "@/features/sandbox/useBranch";
import { ApiError } from "@/lib/api/client";

/** The identifier of the branch that the stub of the client answers with. */
const BRANCH_ID = "sb_0123456789abcdef01234567";

/** The moment the branch of the stub dies, as the server writes it. */
const EXPIRES_AT = "2026-11-22T12:00:00+00:00";

/** The resource of the branch, as the facade writes it. */
interface StubBranch {
  id: string;
  base_snapshot_id: string;
  snapshot_sha256: string;
  revision: number;
  expires_at: string;
}

/**
 * The answer of the fork, with the flag that says the branch was created or found.
 *
 * Why it is flat: the fork answers with the resource of the branch, with the two headers of the
 * branch and with the flag of the creation.
 */
interface StubForkAnswer extends StubBranch {
  branchHash: string | null;
  branchState: string | null;
  created: boolean;
}

/** The answer of the preview, with the eleven fields the facade writes. */
interface StubPreviewAnswer {
  valid: boolean;
  kind: string;
  revision: number;
  current_canonical_hash: string;
  projected_canonical_hash: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  records: unknown[];
  diff: unknown[];
  invariants: unknown[];
  verdict: string;
}

/** The answer of the commit and of the undo, with the shape the facade writes. */
interface StubCommitAnswer {
  command_id: string;
  kind: string;
  revision: number;
  canonical_hash: string;
  diff: unknown[];
  invariants: unknown[];
  verdict: string;
  replayed: boolean;
  stale: boolean;
  stale_against: string | null;
  undone: boolean;
  undone_event_uid: string | null;
}

/** The answer of the diff of the branch. */
interface StubDiffAnswer {
  revision: number;
  base_canonical_hash: string;
  canonical_hash: string;
  diff: unknown[];
  invariants: unknown[];
  verdict: string;
}

/** The answer of the history of the branch. */
interface StubHistoryAnswer {
  revision: number;
  canonical_hash: string;
  events: unknown[];
  answers: unknown[];
}

/** The client of the branch, as the stub of this test answers it. */
interface StubClient {
  startSession: () => Promise<unknown>;
  endSession: () => Promise<void>;
  fork: (scenarioId: string) => Promise<StubForkAnswer>;
  status: (branchId: string) => Promise<StubBranch>;
  preview: (branchId: string, command: unknown) => Promise<StubPreviewAnswer>;
  commit: (
    branchId: string,
    command: unknown,
    options: { revision: number; idempotencyKey: string },
  ) => Promise<StubCommitAnswer>;
  undo: (
    branchId: string,
    options: { revision: number; idempotencyKey: string },
  ) => Promise<StubCommitAnswer>;
  reset: (branchId: string) => Promise<StubBranch>;
  diff: (branchId: string) => Promise<StubDiffAnswer>;
  history: (branchId: string) => Promise<StubHistoryAnswer>;
}

/** The client that the hook expects, read from the options of the hook itself. */
type ClientOfTheHook = Parameters<typeof useBranch>[0]["client"];

/** The command that the form of the mutation builds, as the preview is asked for it. */
type CommandOfTheHook = Parameters<UseBranchResult["preview"]>[0];

/** The branch that the stub answers with, at the revision the case needs. */
function stubBranch(revision = 0): StubBranch {
  return {
    id: BRANCH_ID,
    base_snapshot_id: "snap_01",
    snapshot_sha256: "sha256_of_the_base",
    revision,
    expires_at: EXPIRES_AT,
  };
}

/** The answer of the fork that the stub answers with, at the revision the case needs. */
function stubFork(revision = 0, created = true): StubForkAnswer {
  return {
    ...stubBranch(revision),
    branchHash: "hash_base",
    branchState: "active",
    created,
  };
}

/** The preview that the stub answers with, at the revision the case needs. */
function stubPreview(revision = 0, valid = true): StubPreviewAnswer {
  return {
    valid,
    kind: "refund.apply_fx_adjustment",
    revision,
    current_canonical_hash: "hash_before",
    projected_canonical_hash: "hash_after",
    before: { amount: "100.00", currency: "USD" },
    after: { amount: "90.00", currency: "USD" },
    records: [],
    diff: [{ record: "tx_1", field: "amount", before: "100.00", after: "90.00" }],
    invariants: [],
    verdict: "within_expected_range",
  };
}

/** The result of a mutation, at the revision the case needs. */
function stubCommit(revision = 1): StubCommitAnswer {
  return {
    command_id: "cmd_01",
    kind: "refund.apply_fx_adjustment",
    revision,
    canonical_hash: "hash_after",
    diff: [],
    invariants: [],
    verdict: "within_expected_range",
    replayed: false,
    stale: false,
    stale_against: null,
    undone: false,
    undone_event_uid: null,
  };
}

/** The refusal of the server, as the transport of the repository raises it. */
function refusal(status: number, code: string, message: string): ApiError {
  return new ApiError(message, {
    status,
    code,
    retryable: false,
    requestId: "req_01",
    body: { code, message, retryable: false, request_id: "req_01" },
  });
}

/** The client of the branch, with every route answered by the stub. */
function fakeClient(overrides: Partial<StubClient> = {}): StubClient {
  return {
    startSession: vi.fn(async () => ({ id: "session_01", expires_at: EXPIRES_AT, mode_capabilities: [] })),
    endSession: vi.fn(async () => undefined),
    fork: vi.fn(async (_scenarioId: string) => stubFork()),
    status: vi.fn(async (_branchId: string) => stubBranch()),
    preview: vi.fn(async (_branchId: string, _command: unknown) => stubPreview()),
    commit: vi.fn(
      async (
        _branchId: string,
        _command: unknown,
        _options: { revision: number; idempotencyKey: string },
      ) => stubCommit(),
    ),
    undo: vi.fn(
      async (_branchId: string, _options: { revision: number; idempotencyKey: string }) => stubCommit(),
    ),
    reset: vi.fn(async (_branchId: string) => stubBranch(0)),
    diff: vi.fn(async (_branchId: string) => ({
      revision: 0,
      base_canonical_hash: "hash_base",
      canonical_hash: "hash_base",
      diff: [],
      invariants: [],
      verdict: "within_expected_range",
    })),
    history: vi.fn(async (_branchId: string) => ({
      revision: 0,
      canonical_hash: "hash_base",
      events: [],
      answers: [],
    })),
    ...overrides,
  };
}

/** The stub of the client, given to the hook as the client of the branch. */
function clientOf(stub: StubClient): ClientOfTheHook {
  return stub as unknown as ClientOfTheHook;
}

/** The command that the form of the mutation builds. */
const COMMAND = {
  kind: "refund.apply_fx_adjustment",
  data: { refund_id: "rf_01", amount: "10.00", currency: "USD" },
  reason: "the visitor asked for it",
} as unknown as CommandOfTheHook;

describe("the reducer of the branch", () => {
  it("goes from idle to opening and then to ready", () => {
    const opening = branchReducer(undefined, { type: "fork" });
    expect(opening.phase).toBe("opening");

    const ready = branchReducer(opening, {
      type: "forked",
      branchId: BRANCH_ID,
      revision: 0,
      expiresAt: EXPIRES_AT,
      canonicalHash: "hash_base",
      branchState: "open",
      created: true,
    });
    expect(ready.phase).toBe("ready");
    expect(ready.branchId).toBe(BRANCH_ID);
    expect(ready.revision).toBe(0);
    expect(ready.expiresAt).toBe(EXPIRES_AT);
    expect(ready.created).toBe(true);
  });

  it("moves the revision and clears the preview, the diff and the history when a mutation is committed", async () => {
    const stub = fakeClient();
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.preview(COMMAND);
    });
    await act(async () => {
      await result.current.readDiff();
    });
    await act(async () => {
      await result.current.readHistory();
    });

    expect(result.current.state.preview).not.toBeNull();
    expect(result.current.state.diff).not.toBeNull();
    expect(result.current.state.history).not.toBeNull();

    const committed = branchReducer(result.current.state, { type: "committed", revision: 3 });

    expect(committed.phase).toBe("ready");
    expect(committed.revision).toBe(3);
    expect(committed.preview).toBeNull();
    expect(committed.diff).toBeNull();
    expect(committed.history).toBeNull();
  });

  it("moves the revision to zero when the branch is reset", async () => {
    const stub = fakeClient();
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.preview(COMMAND);
    });
    await act(async () => {
      await result.current.commit();
    });

    expect(result.current.state.revision).toBe(1);

    const reset = branchReducer(result.current.state, { type: "reset", revision: 0 });

    expect(reset.phase).toBe("ready");
    expect(reset.revision).toBe(0);
    expect(reset.branchId).toBe(BRANCH_ID);
  });

  it("keeps the branch when the refusal is about an act", async () => {
    const stub = fakeClient();
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });

    const refused = branchReducer(result.current.state, {
      type: "refused",
      refusal: { code: "INVALID_AMOUNT", message: "the amount is not valid", retryable: false, request_id: "req_01" },
    });

    expect(refused.phase).toBe("ready");
    expect(refused.branchId).toBe(BRANCH_ID);
    expect(refused.revision).toBe(0);
    expect(refused.refusal?.code).toBe("INVALID_AMOUNT");
  });

  it("empties the branch when the refusal says that the branch is gone", async () => {
    const stub = fakeClient();
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });

    const lost = branchReducer(result.current.state, {
      type: "lost",
      refusal: { code: "BRANCH_EXPIRED", message: "the branch died", retryable: false, request_id: "req_01" },
    });

    expect(lost.phase).toBe("refused");
    expect(lost.branchId).toBeNull();
    expect(lost.revision).toBeNull();
    expect(lost.expiresAt).toBeNull();
    expect(lost.preview).toBeNull();
    expect(lost.refusal?.code).toBe("BRANCH_EXPIRED");
  });

  it("empties everything and goes back to idle when the session ends", async () => {
    const stub = fakeClient();
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.preview(COMMAND);
    });

    const ended = branchReducer(result.current.state, { type: "sessionEnded" });

    expect(ended.phase).toBe("idle");
    expect(ended.branchId).toBeNull();
    expect(ended.revision).toBeNull();
    expect(ended.expiresAt).toBeNull();
    expect(ended.preview).toBeNull();
    expect(ended.diff).toBeNull();
    expect(ended.history).toBeNull();
    expect(ended.refusal).toBeNull();
  });
});

describe("the hook of the branch", () => {
  it("opens the branch of a scenario and remembers that it was created", async () => {
    const stub = fakeClient();
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });

    expect(stub.fork).toHaveBeenCalledWith("S01");
    expect(result.current.state.phase).toBe("ready");
    expect(result.current.state.branchId).toBe(BRANCH_ID);
    expect(result.current.state.revision).toBe(0);
    expect(result.current.state.expiresAt).toBe(EXPIRES_AT);
    expect(result.current.state.created).toBe(true);
  });

  it("remembers that the branch was found and not created", async () => {
    // The reuse rule of the fork answers `200` when the branch already exists, and the visitor who
    // reloaded the page has to understand that the work of the branch is still there.
    const stub = fakeClient({ fork: vi.fn(async () => stubFork(2, false)) });
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });

    expect(result.current.state.phase).toBe("ready");
    expect(result.current.state.branchId).toBe(BRANCH_ID);
    expect(result.current.state.revision).toBe(2);
    expect(result.current.state.created).toBe(false);
  });

  it("asks for the session only when the server refuses with 401 SESSION_REQUIRED and retries the call once", async () => {
    const fork = vi
      .fn<(scenarioId: string) => Promise<StubForkAnswer>>()
      .mockRejectedValueOnce(refusal(401, "SESSION_REQUIRED", "the session is over"))
      .mockResolvedValueOnce(stubFork());
    const stub = fakeClient({ fork });
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });

    expect(stub.startSession).toHaveBeenCalledTimes(1);
    expect(fork).toHaveBeenCalledTimes(2);
    expect(result.current.state.phase).toBe("ready");
    expect(result.current.state.branchId).toBe(BRANCH_ID);
  });

  it("asks for the session exactly once and retries the call exactly once when the server refuses again", async () => {
    // The server refuses with 401 every time, so a hook that asked for a session on every refusal
    // would ask for one again and again. The ADR says one session and one retry, and the case
    // proves the two numbers.
    const fork = vi
      .fn<(scenarioId: string) => Promise<StubForkAnswer>>()
      .mockRejectedValue(refusal(401, "SESSION_REQUIRED", "the session is over"));
    const stub = fakeClient({ fork });
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });

    expect(stub.startSession).toHaveBeenCalledTimes(1);
    expect(fork).toHaveBeenCalledTimes(2);
  });

  it("keeps the branch when the server refuses once and then answers", async () => {
    // The order of the ADR is fixed: the call fails with 401, the hook issues the session, the
    // hook retries the call once, and only a retry that fails with 401 again clears the state.
    // The case proves that a branch that survives the refusal is still there after the retry.
    const preview = vi
      .fn<(branchId: string, command: unknown) => Promise<StubPreviewAnswer>>()
      .mockRejectedValueOnce(refusal(401, "SESSION_REQUIRED", "the session is over"))
      .mockResolvedValueOnce(stubPreview());
    const stub = fakeClient({ preview });
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.preview(COMMAND);
    });

    expect(stub.startSession).toHaveBeenCalledTimes(1);
    expect(preview).toHaveBeenCalledTimes(2);
    expect(result.current.state.phase).toBe("ready");
    expect(result.current.state.branchId).toBe(BRANCH_ID);
    expect(result.current.state.revision).toBe(0);
    expect(result.current.state.preview).not.toBeNull();
  });

  it("clears the state when the retry of the call fails with 401 again", async () => {
    // The server refuses twice: the branch is gone and the state keeps only the refusal of the
    // server, with the phase back to idle.
    const preview = vi
      .fn<(branchId: string, command: unknown) => Promise<StubPreviewAnswer>>()
      .mockRejectedValue(refusal(401, "SESSION_REQUIRED", "the session is over"));
    const stub = fakeClient({ preview });
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.preview(COMMAND);
    });

    expect(stub.startSession).toHaveBeenCalledTimes(1);
    expect(preview).toHaveBeenCalledTimes(2);
    expect(result.current.state.phase).toBe("idle");
    expect(result.current.state.branchId).toBeNull();
    expect(result.current.state.revision).toBeNull();
    expect(result.current.state.expiresAt).toBeNull();
    expect(result.current.state.preview).toBeNull();
  });

  it("never asks for a session when the refusal of the server is another one", async () => {
    const stub = fakeClient({
      fork: vi.fn(async () => {
        throw refusal(404, "UNKNOWN_SCENARIO", "the scenario does not exist");
      }),
    });
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S99");
    });

    expect(stub.startSession).not.toHaveBeenCalled();
    expect(stub.fork).toHaveBeenCalledTimes(1);
    expect(result.current.state.phase).toBe("refused");
    expect(result.current.state.refusal?.code).toBe("UNKNOWN_SCENARIO");
  });

  it("refuses a commit when there is no preview", async () => {
    const stub = fakeClient();
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.commit();
    });

    expect(stub.commit).not.toHaveBeenCalled();
    expect(result.current.canCommit).toBe(false);
    expect(result.current.commitReason).toBe("preview the command first");
  });

  it("refuses a commit when the preview says that the command is not valid", async () => {
    const stub = fakeClient({
      preview: vi.fn(async () => stubPreview(0, false)),
    });
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.preview(COMMAND);
    });
    await act(async () => {
      await result.current.commit();
    });

    expect(stub.commit).not.toHaveBeenCalled();
    expect(result.current.canCommit).toBe(false);
    expect(result.current.commitReason).toBe("the command would break a rule of the domain");
  });

  it("refuses a commit when the preview is out of date", async () => {
    const stub = fakeClient({
      fork: vi.fn(async () => stubFork(1)),
      preview: vi.fn(async () => stubPreview(0)),
    });
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.preview(COMMAND);
    });
    await act(async () => {
      await result.current.commit();
    });

    expect(stub.commit).not.toHaveBeenCalled();
    expect(result.current.canCommit).toBe(false);
    expect(result.current.commitReason).toBe("the preview is out of date, preview the command again");
  });

  it("sends the key of the preview with the commit", async () => {
    const stub = fakeClient();
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.preview(COMMAND);
    });

    const key = result.current.state.preview?.idempotencyKey;
    expect(key).toBeTruthy();

    await act(async () => {
      await result.current.commit();
    });

    const call = (stub.commit as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call?.[2]).toEqual({ revision: 0, idempotencyKey: key });
    expect(result.current.state.revision).toBe(1);
    expect(result.current.state.preview).toBeNull();
  });

  it("sends the body of the previewed command with the commit", async () => {
    const stub = fakeClient();
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.preview(COMMAND);
    });
    await act(async () => {
      await result.current.commit();
    });

    const call = (stub.commit as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call?.[1]).toBe(COMMAND);
  });

  it("keeps the branch when the server refuses an act", async () => {
    const stub = fakeClient({
      preview: vi.fn(async () => {
        throw refusal(422, "INVALID_AMOUNT", "the amount is not valid");
      }),
    });
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.preview(COMMAND);
    });

    expect(result.current.state.phase).toBe("ready");
    expect(result.current.state.branchId).toBe(BRANCH_ID);
    expect(result.current.state.revision).toBe(0);
    expect(result.current.state.refusal?.code).toBe("INVALID_AMOUNT");
  });

  it("empties the branch when the server says that the branch is gone", async () => {
    const stub = fakeClient({
      diff: vi.fn(async () => {
        throw refusal(410, "BRANCH_EXPIRED", "the branch died");
      }),
    });
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.readDiff();
    });

    expect(result.current.state.phase).toBe("refused");
    expect(result.current.state.branchId).toBeNull();
    expect(result.current.state.revision).toBeNull();
    expect(result.current.state.refusal?.code).toBe("BRANCH_EXPIRED");
  });

  it("clears the state when the session ends and the server answers", async () => {
    const stub = fakeClient();
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.preview(COMMAND);
    });
    await act(async () => {
      await result.current.endSession();
    });

    expect(stub.endSession).toHaveBeenCalledTimes(1);
    expect(result.current.state.phase).toBe("idle");
    expect(result.current.state.branchId).toBeNull();
    expect(result.current.state.revision).toBeNull();
    expect(result.current.state.expiresAt).toBeNull();
    expect(result.current.state.preview).toBeNull();
    expect(result.current.state.refusal).toBeNull();
  });

  it("clears the state when the session ends and the server refuses", async () => {
    const stub = fakeClient({
      endSession: vi.fn(async () => {
        throw refusal(401, "SESSION_REQUIRED", "the session is over");
      }),
    });
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.endSession();
    });

    expect(result.current.state.phase).toBe("idle");
    expect(result.current.state.branchId).toBeNull();
    expect(result.current.state.revision).toBeNull();
    expect(result.current.state.expiresAt).toBeNull();
    expect(result.current.state.preview).toBeNull();
    expect(result.current.state.refusal).toBeNull();
  });

  it("keeps the state in the memory of the page and nowhere else", async () => {
    const before = window.location.href;
    const stub = fakeClient();
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.preview(COMMAND);
    });

    expect(result.current.state.branchId).toBe(BRANCH_ID);
    expect(window.location.href).toBe(before);
    expect(window.location.search).toBe("");
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });

  it("keeps the money of the server as the text the server sent", async () => {
    const diff = {
      revision: 0,
      base_canonical_hash: "hash_base",
      canonical_hash: "hash_base",
      diff: [{ record: "tx_1", field: "amount", before: "100.00", after: "90.00" }],
      invariants: [],
      verdict: "within_expected_range",
    };
    const stub = fakeClient({ diff: vi.fn(async () => diff) });
    const { result } = renderHook(() => useBranch({ client: clientOf(stub) }));

    await act(async () => {
      await result.current.open("S01");
    });
    await act(async () => {
      await result.current.readDiff();
    });

    expect(result.current.state.diff).toEqual(diff);
    expect(JSON.stringify(result.current.state.diff)).toContain("100.00");
  });
});
