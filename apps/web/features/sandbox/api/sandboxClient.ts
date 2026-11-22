/**
 * The client of the branch of the visitor.
 *
 * Why this file exists: the sandbox of the visitor is a third route of the site, and it is the only
 * half of the demo that talks to the origin of the backend besides the live mode. The calls of the
 * branch travel with the credentials of the visitor, exactly like the calls of the live mode, and
 * they live here so that the rule of the credentials has one place (ADR-040, ADR-044).
 *
 * The rules of this file are these. Every call carries `credentials: "include"`, so the browser
 * sends the cookie of the session of the origin of the backend. The client never calculates a
 * value: it carries the text of the server as it is, and the money of an answer stays the decimal
 * text the domain wrote. A refusal of the server arrives as an `ApiError` that holds the code, the
 * message, the status, the flag of the retry and the identifier of the request of the envelope,
 * because the interface shows the reason of the server and never a guess. An origin that does not
 * answer arrives as an `ApiError` with the status zero and the code `NETWORK_ERROR`, because the
 * interface says in words which origin it tried and never falls back.
 *
 * The ten calls of the client are the ten paths of the facade of `ledgerlens/api/sandbox.py` that
 * the milestone calls: the session, the end of the session, the fork, the status, the preview, the
 * commit, the undo, the reset, the diff and the history. The ledger of the branch is not called in
 * this milestone.
 */

import { ApiError, readErrorBody } from "@/lib/api/client";
import { apiBaseUrl, apiUrl, normalizeBaseUrl } from "@/lib/api/config";
import type { SessionBody } from "@/lib/api/live";
import type {
  BranchDiffBody,
  BranchHistoryBody,
  MutationPreviewBody,
  MutationResultBody,
  SandboxCommand,
  SandboxErrorBody,
  SandboxForkAnswer,
  SandboxResource,
  SandboxStatusAnswer,
} from "@/features/sandbox/types";

/** The header that carries the current canonical hash of the branch. */
const BRANCH_HASH_HEADER = "X-LedgerLens-Branch-Hash";

/** The header that carries the state of the branch. */
const BRANCH_STATE_HEADER = "X-LedgerLens-Branch-State";

/**
 * The options of the client of the branch.
 *
 * Why the origin and the fetch can be given: the unit tests of the client never open a socket, and
 * they need to say which origin they are talking to.
 */
export interface SandboxClientOptions {
  /** The origin of the backend. The default is the origin of the configuration of the site. */
  baseUrl?: string;
  /** The fetch of the browser. The default is the fetch of the runtime. */
  fetchImpl?: typeof fetch;
}

/**
 * The calls the browser makes to the branch of the visitor.
 *
 * Every method of this interface is a path of `ledgerlens/api/sandbox.py`, and every one of them
 * travels with the credentials of the session.
 */
export interface SandboxClient {
  /** The origin the client talks to, so the interface can say which origin it tried. */
  readonly baseUrl: string;

  /** Issues the session of the visitor and sets the cookie of the session. */
  startSession(): Promise<SessionBody>;

  /** Ends the session of the visitor and deletes the branches that belong to it. */
  endSession(): Promise<void>;

  /** Forks the published case into a private branch of the session. */
  fork(scenarioId: string): Promise<SandboxForkAnswer>;

  /** The state of the branch: the revision, the hashes and the expiry. */
  status(branchId: string): Promise<SandboxStatusAnswer>;

  /** What a typed mutation would do to the branch, computed without writing anything. */
  preview(branchId: string, command: SandboxCommand): Promise<MutationPreviewBody>;

  /** Writes the mutation in the branch, with the key of the request and the revision it expects. */
  commit(
    branchId: string,
    command: SandboxCommand,
    options: { revision: number; idempotencyKey: string },
  ): Promise<MutationResultBody>;

  /** Takes back the last mutation of the branch, with the key of the request and the revision. */
  undo(
    branchId: string,
    options: { revision: number; idempotencyKey: string },
  ): Promise<MutationResultBody>;

  /** Puts the branch back at the published base. */
  reset(branchId: string): Promise<SandboxStatusAnswer>;

  /** The difference between the published base of the branch and the state it holds now. */
  diff(branchId: string): Promise<BranchDiffBody>;

  /** The log of the branch and the answers the branch remembers. */
  history(branchId: string): Promise<BranchHistoryBody>;
}

/** The answer of a call, with the headers of the branch. */
interface RawAnswer {
  status: number;
  body: unknown;
  headers: Headers;
}

/**
 * Creates the client of the branch.
 *
 * Why the origin is normalized here: the caller may hand over a base with a trailing slash, and
 * the routes of the backend are published without one.
 */
export function createSandboxClient(options: SandboxClientOptions = {}): SandboxClient {
  const baseUrl = normalizeBaseUrl(options.baseUrl) ?? apiBaseUrl();
  const doFetch: typeof fetch =
    options.fetchImpl ?? ((input: RequestInfo | URL, init?: RequestInit) => globalThis.fetch(input, init));

  /** One call: it always carries the credentials of the session, and it never throws a raw error. */
  async function send(
    path: string,
    method: string,
    body?: unknown,
    extraHeaders?: Record<string, string>,
  ): Promise<RawAnswer> {
    const url = apiUrl(path, baseUrl);
    const init: RequestInit = {
      method,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(extraHeaders ?? {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    };

    let response: Response;
    try {
      response = await doFetch(url, init);
    } catch {
      throw new ApiError(`the origin ${baseUrl} did not answer the request to ${method} ${path}`, {
        status: 0,
        code: "NETWORK_ERROR",
        retryable: true,
        requestId: "",
        body: null,
      });
    }

    const text = await response.text();
    let parsed: unknown = null;
    if (text !== "") {
      try {
        parsed = JSON.parse(text) as unknown;
      } catch {
        parsed = null;
      }
    }

    if (!response.ok) {
      // The envelope of the refusal is read with the reader of the repository, so the sandbox and
      // the live mode cannot disagree about what a refusal is.
      const refusal: SandboxErrorBody | null = readErrorBody(parsed);
      throw new ApiError(refusal?.message ?? `the server answered ${response.status}`, {
        status: response.status,
        code: refusal?.code ?? "HTTP_ERROR",
        retryable: refusal?.retryable ?? false,
        requestId: refusal?.request_id ?? "",
        body: refusal,
      });
    }

    return { status: response.status, body: parsed, headers: response.headers };
  }

  /**
   * The two headers of the branch, read from the answer of the server.
   *
   * Why the state is a text and not a closed list: the client carries the text of the server as it
   * is, and the domain writes `active` and `expired` today.
   */
  function branchOf(answer: RawAnswer): { branchHash: string | null; branchState: string | null } {
    return {
      branchHash: answer.headers.get(BRANCH_HASH_HEADER),
      branchState: answer.headers.get(BRANCH_STATE_HEADER),
    };
  }

  /** The path of a branch, with the identifier of the branch escaped. */
  function branchPath(branchId: string): string {
    return `/v1/sandboxes/${encodeURIComponent(branchId)}`;
  }

  return {
    baseUrl,

    async startSession(): Promise<SessionBody> {
      const answer = await send("/v1/sessions", "POST");
      return answer.body as SessionBody;
    },

    async endSession(): Promise<void> {
      await send("/v1/sessions/current", "DELETE");
    },

    async fork(scenarioId: string): Promise<SandboxForkAnswer> {
      const answer = await send("/v1/sandboxes", "POST", { scenario_id: scenarioId });
      // The fork answers 201 when it creates the branch and 200 when the reuse rule returns the
      // branch that already exists, and the difference tells the visitor that the work of the
      // branch survived a reload of the page.
      return {
        ...(answer.body as SandboxResource),
        ...branchOf(answer),
        created: answer.status === 201,
      };
    },

    async status(branchId: string): Promise<SandboxStatusAnswer> {
      const answer = await send(branchPath(branchId), "GET");
      return { ...(answer.body as SandboxResource), ...branchOf(answer) };
    },

    async preview(branchId: string, command: SandboxCommand): Promise<MutationPreviewBody> {
      const answer = await send(`${branchPath(branchId)}/mutations/preview`, "POST", command);
      return answer.body as MutationPreviewBody;
    },

    async commit(
      branchId: string,
      command: SandboxCommand,
      commitOptions: { revision: number; idempotencyKey: string },
    ): Promise<MutationResultBody> {
      const answer = await send(
        `${branchPath(branchId)}/mutations`,
        "POST",
        command,
        {
          // The key names the request: a second press of the commit is the same request delivered
          // twice, and the server answers it with the answer it stored.
          "Idempotency-Key": commitOptions.idempotencyKey,
          // The revision the visitor believes the branch is at. The server reads it as a number.
          "If-Match": String(commitOptions.revision),
        },
      );
      return answer.body as MutationResultBody;
    },

    async undo(
      branchId: string,
      undoOptions: { revision: number; idempotencyKey: string },
    ): Promise<MutationResultBody> {
      const answer = await send(
        `${branchPath(branchId)}/undo`,
        "POST",
        undefined,
        {
          "Idempotency-Key": undoOptions.idempotencyKey,
          "If-Match": String(undoOptions.revision),
        },
      );
      return answer.body as MutationResultBody;
    },

    async reset(branchId: string): Promise<SandboxStatusAnswer> {
      const answer = await send(`${branchPath(branchId)}/reset`, "POST");
      return { ...(answer.body as SandboxResource), ...branchOf(answer) };
    },

    async diff(branchId: string): Promise<BranchDiffBody> {
      const answer = await send(`${branchPath(branchId)}/diff`, "GET");
      return answer.body as BranchDiffBody;
    },

    async history(branchId: string): Promise<BranchHistoryBody> {
      const answer = await send(`${branchPath(branchId)}/history`, "GET");
      return answer.body as BranchHistoryBody;
    },
  };
}

/**
 * The whole surface of the module, so a reader who opens the file sees it at once.
 */
export const __all__ = ["SandboxClientOptions", "SandboxClient", "createSandboxClient"] as const;
