"use client";

/**
 * The state of the branch of the visitor.
 *
 * Why this file exists: the branch of the visitor lives on the origin of the backend and the page
 * of the visitor holds only what it needs to draw it. The state of the branch lives in the memory
 * of the page and NOWHERE ELSE: not in the URL, not in the `localStorage`, not in the
 * `sessionStorage` and not in a cookie. A reload loses the state and keeps the branch, because
 * the fork of the scenario brings the branch back (ADR-044).
 *
 * The machine has four phases: `idle`, `opening`, `ready` and `refused`. A branch that is not
 * there is never half drawn: a refusal that means the branch is GONE empties the branch of the
 * state, and a refusal that is about an ACT keeps it.
 *
 * The session is asked for ONLY when the server refuses with `401 SESSION_REQUIRED`, and the call
 * is retried exactly once. The rule matters because every `POST /v1/sessions` issues a NEW
 * session: a front that asked for one on every visit would give the visitor a new session every
 * time and the branch of the previous visit would stay on the origin with nobody able to reach it.
 *
 * The money is never calculated here. The state carries the decimal TEXT of the server, the
 * revision is the integer of the server and the expiry is the ISO 8601 text of the server.
 */

import { useCallback, useMemo, useReducer, useRef } from "react";

import { ApiError } from "@/lib/api/client";
import type { SandboxClient } from "@/features/sandbox/api/sandboxClient";
import type {
  BranchDiffBody,
  BranchHistoryBody,
  MutationPreviewBody,
  MutationResultBody,
  SandboxCommand,
  SandboxErrorBody,
  SandboxForkAnswer,
} from "@/features/sandbox/types";

/**
 * The phases of the machine of the branch.
 *
 * Why `refused` is a phase of its own: a refusal is not a branch, and a panel that cannot tell the
 * two apart would show a branch that is not there.
 */
export type SandboxPhase = "idle" | "opening" | "ready" | "refused";

/**
 * The whole state of the branch.
 *
 * Why every field is there: the phase says what the panel shows, the identifier, the revision and
 * the expiry say which branch it is, the preview is the promise that a commit may be sent, the
 * diff and the history are what the visitor asked to read, and the refusal says why the last act
 * did not happen.
 */
export interface BranchState {
  /** Where the machine stands. */
  readonly phase: SandboxPhase;
  /** The identifier of the branch, or `null` when there is none. */
  readonly branchId: string | null;
  /** The revision the branch is at, as the server writes it. */
  readonly revision: number | null;
  /** The moment the branch dies, as the server writes it. */
  readonly expiresAt: string | null;
  /** The canonical hash of the branch, as the server writes it. */
  readonly canonicalHash: string | null;
  /** The state of the branch, as the header of the server carries it. */
  readonly branchState: string | null;
  /** Whether the branch was created by the fork or found by it, or `null` when there is none. */
  readonly created: boolean | null;
  /** The preview that waits for a commit, with the key that the commit carries. */
  readonly preview: {
    /** Whether the command would keep every rule of the domain. */
    readonly valid: boolean;
    /** The revision the preview was made at. */
    readonly revision: number;
    /** The key that names the request of the commit. */
    readonly idempotencyKey: string;
    /** The command that was previewed, sent again byte for byte by the commit. */
    readonly command: SandboxCommand;
    /** The answer of the server to the preview. */
    readonly answer: MutationPreviewBody;
  } | null;
  /** The difference between the published base and the branch. */
  readonly diff: BranchDiffBody | null;
  /** The log of the branch. */
  readonly history: BranchHistoryBody | null;
  /** The refusal of the server, with the code and the message of the server. */
  readonly refusal: SandboxErrorBody | null;
}

/**
 * The actions of the machine.
 *
 * Why they are the whole of the vocabulary: every change of the branch comes from one of them, and
 * the reducer is pure, so the same sequence of actions always ends in the same state.
 */
export type BranchAction =
  /** The fork is in flight. */
  | { readonly type: "fork" }
  /** The fork answered and the branch is there. */
  | {
      readonly type: "forked";
      readonly branchId: string;
      readonly revision: number;
      readonly expiresAt: string;
      readonly canonicalHash: string | null;
      readonly branchState: string | null;
      readonly created: boolean;
    }
  /** The preview arrived and waits for a commit. */
  | { readonly type: "previewed"; readonly preview: NonNullable<BranchState["preview"]> }
  /** A mutation was committed and the branch moved. */
  | { readonly type: "committed"; readonly revision: number }
  /** The last mutation was undone and the branch moved. */
  | { readonly type: "undone"; readonly revision: number }
  /** The branch was put back at the published base. */
  | { readonly type: "reset"; readonly revision: number }
  /** The difference of the branch was read. */
  | { readonly type: "diff"; readonly diff: BranchDiffBody }
  /** The log of the branch was read. */
  | { readonly type: "history"; readonly history: BranchHistoryBody }
  /** The last act was refused and the branch is still there. */
  | { readonly type: "refused"; readonly refusal: SandboxErrorBody }
  /** The branch is gone and the state keeps only the refusal. */
  | { readonly type: "lost"; readonly refusal: SandboxErrorBody }
  /** The session ended and the state is empty again. */
  | { readonly type: "sessionEnded" };

/** The state of a machine that has done nothing yet. */
const INITIAL_STATE: BranchState = {
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
};

/**
 * The reducer of the machine of the branch.
 *
 * The reducer is pure: it reads no clock, it draws no random number and it touches nothing
 * outside its arguments. The same sequence of actions always ends in the same state.
 *
 * Why the state may be absent: the reducer is also the initialization of the machine, so a caller
 * that holds no state yet gets the state of a machine that has done nothing.
 */
export function branchReducer(state: BranchState | undefined, action: BranchAction): BranchState {
  const current = state ?? INITIAL_STATE;

  switch (action.type) {
    case "fork":
      // The fork answers with the branch, so everything the state held before it is stale.
      return {
        ...INITIAL_STATE,
        phase: "opening",
      };

    case "forked":
      return {
        ...current,
        phase: "ready",
        branchId: action.branchId,
        revision: action.revision,
        expiresAt: action.expiresAt,
        canonicalHash: action.canonicalHash,
        branchState: action.branchState,
        created: action.created,
        preview: null,
        diff: null,
        history: null,
        refusal: null,
      };

    case "previewed":
      return {
        ...current,
        phase: current.branchId === null ? current.phase : "ready",
        preview: action.preview,
        refusal: null,
      };

    case "committed":
    case "undone":
      // The branch moved, so the preview that was made at the old revision is not a promise anymore.
      return {
        ...current,
        phase: current.branchId === null ? current.phase : "ready",
        revision: action.revision,
        preview: null,
        diff: null,
        history: null,
        refusal: null,
      };

    case "reset":
      return {
        ...current,
        phase: current.branchId === null ? current.phase : "ready",
        revision: action.revision,
        preview: null,
        diff: null,
        history: null,
        refusal: null,
      };

    case "diff":
      return { ...current, diff: action.diff, refusal: null };

    case "history":
      return { ...current, history: action.history, refusal: null };

    case "refused":
      // The refusal is about an act: the branch, its revision and its diff stay where they were.
      return {
        ...current,
        phase: current.branchId === null ? "refused" : current.phase,
        refusal: action.refusal,
      };

    case "lost":
      // The branch is gone: a branch that is not there is never half drawn.
      return {
        ...INITIAL_STATE,
        phase: "refused",
        refusal: action.refusal,
      };

    case "sessionEnded":
      return INITIAL_STATE;

    default:
      return current;
  }
}

/**
 * The options of the hook of the branch.
 *
 * Why the client is given by the caller: the unit test of the hook uses a stub and never opens a
 * socket.
 */
export interface UseBranchOptions {
  /** The client of the branch, the one module that reads the origin of the backend. */
  readonly client: SandboxClient;
  /**
   * The function that names a request of the branch.
   *
   * The default names it with the random identifier of the runtime. The name of a request is not a
   * secret: it travels in a header and it says that a second press of the commit is the SAME
   * request delivered twice.
   */
  readonly generateIdempotencyKey?: () => string;
}

/**
 * What the page gets from the hook of the branch.
 *
 * Why the reason of the commit is here and not in the state: a refusal of the LOCAL interface is
 * not a refusal of the server and it never wears its clothes. The state carries the refusal of the
 * server, and this carries the sentence of the interface.
 */
export interface UseBranchResult {
  /** The state of the machine. */
  readonly state: BranchState;
  /** Whether the commit may be sent right now. */
  readonly canCommit: boolean;
  /** The sentence that says why the commit may not be sent, or `null` when it may. */
  readonly commitReason: string | null;
  /** Opens the branch of a scenario, the fork of the branch. */
  readonly open: (scenarioId: string) => Promise<void>;
  /** Asks the server what the command WOULD do. */
  readonly preview: (command: SandboxCommand) => Promise<void>;
  /** Sends the command that was previewed, with the key of the preview. */
  readonly commit: () => Promise<void>;
  /** Undoes the last mutation of the branch. */
  readonly undo: () => Promise<void>;
  /** Puts the branch back at the published base. */
  readonly reset: () => Promise<void>;
  /** Reads the difference between the published base and the branch. */
  readonly readDiff: () => Promise<void>;
  /** Reads the log of the branch. */
  readonly readHistory: () => Promise<void>;
  /** Ends the session of the visitor and empties the state. */
  readonly endSession: () => Promise<void>;
}

/** The sentence the interface says when there is no branch to commit to. */
const REASON_NO_BRANCH = "open a scenario first";

/** The sentence the interface says when the command was never previewed. */
const REASON_NO_PREVIEW = "preview the command first";

/** The sentence the interface says when the command would break a rule of the domain. */
const REASON_INVALID = "the command would break a rule of the domain";

/** The sentence the interface says when the preview is older than the branch. */
const REASON_OUT_OF_DATE = "the preview is out of date, preview the command again";

/**
 * Says why the commit may not be sent, or `null` when it may.
 *
 * Why the preview has to be there and has to be current: the preview is the promise of the feature
 * and the commit is only offered after a preview that says the command is valid and that was made
 * at the revision the branch is at now.
 */
function reasonForCommit(state: BranchState): string | null {
  if (state.branchId === null || state.revision === null) {
    return REASON_NO_BRANCH;
  }
  const held = state.preview;
  if (held === null) {
    return REASON_NO_PREVIEW;
  }
  if (held.valid !== true) {
    return REASON_INVALID;
  }
  if (held.revision !== state.revision) {
    return REASON_OUT_OF_DATE;
  }
  return null;
}

/**
 * Says whether a refusal is about the session of the visitor.
 *
 * Why the status and the code are read: the status is what the server answered with and the code
 * is the name of the refusal, and a session that is gone is a session that is gone in the two.
 */
function isSessionRequired(caught: unknown): boolean {
  if (!(caught instanceof ApiError)) {
    return false;
  }
  return caught.status === 401 || caught.code === "SESSION_REQUIRED";
}

/**
 * Says whether a refusal means that the branch is GONE.
 *
 * Why the codes are named: a branch that is not there is never half drawn, and these two refusals
 * are the ways the server says that the branch is not there. The third way is the session that is
 * gone, and the session is read apart.
 */
function isLostBranch(refusal: SandboxErrorBody): boolean {
  return refusal.code === "NOT_FOUND" || refusal.code === "BRANCH_EXPIRED";
}

/**
 * Turns whatever was thrown into the body of a refusal.
 *
 * Why a refusal always has a code and a message: the panel renders them where the action was, and
 * an empty error panel would hide the reason of the failure.
 *
 * Why the wait of the server travels with the refusal: the server tells the visitor how long it
 * has to wait when it refuses a request over the rate limit, and the panel shows that number. The
 * number is the text of the header, never a number the browser computes (ADR-047).
 */
function readRefusal(caught: unknown): SandboxErrorBody {
  if (caught instanceof ApiError) {
    const body = caught.body ?? {
      code: caught.code,
      message: caught.message,
      retryable: caught.retryable,
      request_id: caught.requestId,
    };
    return { ...body, retryAfter: caught.retryAfter };
  }
  return {
    code: "UNEXPECTED_ERROR",
    message:
      caught instanceof Error
        ? caught.message
        : "the request failed for a reason the interface does not know",
    retryable: false,
    request_id: "",
    retryAfter: null,
  };
}

/** The branch that the answer of the fork carries. */
interface ForkedBranch {
  readonly branchId: string;
  readonly revision: number;
  readonly expiresAt: string;
  readonly canonicalHash: string | null;
  readonly branchState: string | null;
  readonly created: boolean;
}

/**
 * Reads the branch out of the answer of the fork.
 *
 * Why the answer is read as it is: the fork answers with the resource of the branch, with the two
 * headers of the branch and with the flag that says the branch was CREATED or FOUND, and the front
 * takes the three without calculating anything.
 */
function readForkedBranch(answer: SandboxForkAnswer): ForkedBranch {
  return {
    branchId: answer.id,
    revision: answer.revision,
    expiresAt: answer.expires_at,
    canonicalHash: answer.branchHash,
    branchState: answer.branchState,
    created: answer.created,
  };
}

/**
 * Names a request of the branch.
 *
 * Why the name is random: the name says that a second press of the commit is the SAME request
 * delivered twice, and it is not a secret, so it travels in a header of the call.
 */
function defaultIdempotencyKey(): string {
  const runtime = globalThis.crypto;
  if (runtime && typeof runtime.randomUUID === "function") {
    return runtime.randomUUID();
  }
  return `idem_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * The hook of the state of the branch.
 *
 * The client is given by the caller, so the unit test of the hook uses a stub and never opens a
 * socket. Every call of the hook goes through the session rule: the session is asked for only when
 * the server refuses with `401 SESSION_REQUIRED`, and the call is retried exactly once.
 */
export function useBranch(options: UseBranchOptions): UseBranchResult {
  const { client } = options;
  const generateKey = options.generateIdempotencyKey ?? defaultIdempotencyKey;

  const [state, dispatch] = useReducer(branchReducer, INITIAL_STATE);

  // The state is kept in a reference as well, so that a call that awaits the server reads the state
  // of the moment the call started and not the state of the render that built the call.
  const stateRef = useRef(state);
  stateRef.current = state;

  /**
   * Makes a call and asks for a session when the server says that there is none.
   *
   * Why the state is NOT cleared here: the order of the ADR is fixed. The call fails with 401,
   * the hook issues the session, the hook retries the call ONCE, and only a retry that fails with
   * 401 again clears the state. A state that is cleared before the retry would drop a branch
   * that the server still holds, and a preview could survive without its branch.
   */
  const withSession = useCallback(
    async <T,>(call: () => Promise<T>): Promise<T> => {
      try {
        return await call();
      } catch (caught) {
        if (!isSessionRequired(caught)) {
          throw caught;
        }
        await client.startSession();
        return await call();
      }
    },
    [client],
  );

  /** Puts the refusal of the server in the state, in the way the refusal demands. */
  const refuse = useCallback((caught: unknown): void => {
    if (isSessionRequired(caught)) {
      // The session is over: the branch, its revision, its expiry and its preview all go.
      dispatch({ type: "sessionEnded" });
      return;
    }
    const refusal = readRefusal(caught);
    if (isLostBranch(refusal)) {
      dispatch({ type: "lost", refusal });
      return;
    }
    dispatch({ type: "refused", refusal });
  }, []);

  /** Opens the branch of a scenario. */
  const open = useCallback(
    async (scenarioId: string): Promise<void> => {
      dispatch({ type: "fork" });
      try {
        const answer = await withSession(() => client.fork(scenarioId));
        const forked = readForkedBranch(answer);
        dispatch({
          type: "forked",
          branchId: forked.branchId,
          revision: forked.revision,
          expiresAt: forked.expiresAt,
          canonicalHash: forked.canonicalHash,
          branchState: forked.branchState,
          created: forked.created,
        });
      } catch (caught) {
        refuse(caught);
      }
    },
    [client, refuse, withSession],
  );

  /** Asks the server what the command WOULD do. */
  const preview = useCallback(
    async (command: SandboxCommand): Promise<void> => {
      const branchId = stateRef.current.branchId;
      if (branchId === null) {
        return;
      }
      // The key is named with the preview, so that the commit that follows it is the SAME request
      // and not another one.
      const idempotencyKey = generateKey();
      try {
        const answer = await withSession(() => client.preview(branchId, command));
        dispatch({
          type: "previewed",
          preview: {
            valid: answer.valid === true,
            revision: answer.revision,
            idempotencyKey,
            command,
            answer,
          },
        });
      } catch (caught) {
        refuse(caught);
      }
    },
    [client, generateKey, refuse, withSession],
  );

  /** Sends the command that was previewed, with the key of the preview. */
  const commit = useCallback(
    async (): Promise<void> => {
      const current = stateRef.current;
      const branchId = current.branchId;
      const held = current.preview;
      if (branchId === null || held === null || current.revision === null) {
        return;
      }
      if (held.valid !== true || held.revision !== current.revision) {
        // The front refuses the commit and says why in its own words: the reason is in
        // `commitReason`, and the server is never asked.
        return;
      }
      try {
        const result: MutationResultBody = await withSession(() =>
          client.commit(branchId, held.command, {
            revision: held.revision,
            idempotencyKey: held.idempotencyKey,
          }),
        );
        dispatch({ type: "committed", revision: result.revision });
      } catch (caught) {
        refuse(caught);
      }
    },
    [client, refuse, withSession],
  );

  /** Undoes the last mutation of the branch. */
  const undo = useCallback(
    async (): Promise<void> => {
      const current = stateRef.current;
      const branchId = current.branchId;
      const revision = current.revision;
      if (branchId === null || revision === null) {
        return;
      }
      try {
        const result: MutationResultBody = await withSession(() =>
          client.undo(branchId, { revision, idempotencyKey: generateKey() }),
        );
        dispatch({ type: "undone", revision: result.revision });
      } catch (caught) {
        refuse(caught);
      }
    },
    [client, generateKey, refuse, withSession],
  );

  /** Puts the branch back at the published base. */
  const reset = useCallback(
    async (): Promise<void> => {
      const branchId = stateRef.current.branchId;
      if (branchId === null) {
        return;
      }
      try {
        const answer = await withSession(() => client.reset(branchId));
        // The reset puts the branch back at the published base, and the revision of the answer is
        // the revision the server writes.
        dispatch({ type: "reset", revision: answer.revision });
      } catch (caught) {
        refuse(caught);
      }
    },
    [client, refuse, withSession],
  );

  /** Reads the difference between the published base and the branch. */
  const readDiff = useCallback(
    async (): Promise<void> => {
      const branchId = stateRef.current.branchId;
      if (branchId === null) {
        return;
      }
      try {
        const answer = await withSession(() => client.diff(branchId));
        dispatch({ type: "diff", diff: answer });
      } catch (caught) {
        refuse(caught);
      }
    },
    [client, refuse, withSession],
  );

  /** Reads the log of the branch. */
  const readHistory = useCallback(
    async (): Promise<void> => {
      const branchId = stateRef.current.branchId;
      if (branchId === null) {
        return;
      }
      try {
        const answer = await withSession(() => client.history(branchId));
        dispatch({ type: "history", history: answer });
      } catch (caught) {
        refuse(caught);
      }
    },
    [client, refuse, withSession],
  );

  /** Ends the session of the visitor and empties the state. */
  const endSession = useCallback(async (): Promise<void> => {
    try {
      await client.endSession();
    } catch {
      // The state goes whatever the server answers: a state that keeps a branch the visitor no
      // longer owns shows a branch that is not there.
    } finally {
      dispatch({ type: "sessionEnded" });
    }
  }, [client]);

  const commitReason = useMemo(() => reasonForCommit(state), [state]);

  return {
    state,
    canCommit: commitReason === null,
    commitReason,
    open,
    preview,
    commit,
    undo,
    reset,
    readDiff,
    readHistory,
    endSession,
  };
}

/** Every symbol this module exports, so that a reader sees the whole surface of the state at once. */
export const __all__ = [
  "SandboxPhase",
  "BranchState",
  "BranchAction",
  "branchReducer",
  "UseBranchOptions",
  "UseBranchResult",
  "useBranch",
] as const;
