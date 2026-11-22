/**
 * The transport of the calls of the browser.
 *
 * Why this file exists: the browser of the demo talks to the backend on the origin of the
 * backend, with the credentials of the visitor (ADR-040). The transport is the one place where
 * that happens, so the two rules of the transport live here and nowhere else.
 *
 * The first rule: every call carries `credentials: "include"`, so the browser sends the cookie
 * of the session of the backend origin. The cookie is the identity of the visitor, and a call
 * without it is a call of nobody.
 *
 * The second rule: the transport never reads a provider key from anywhere but the argument of
 * `acceptCredential`. There is no key in the bundle of the browser, no key in the environment of
 * the browser and no key in a storage of the browser, so the only source of a key is the field
 * the visitor typed.
 */

import { apiBaseUrl, apiUrl, normalizeBaseUrl } from "@/lib/api/config";
import type {
  ApiErrorBody,
  CostReportBody,
  CredentialHandle,
  DisclosureHeaders,
  LiveRunAccepted,
  LiveRunRequest,
  LiveRunState,
  ModelCatalogueResponse,
  ModelPriceResponse,
  SandboxBody,
  SessionBody,
} from "@/lib/api/live";

/**
 * A refusal of the server, as an exception.
 *
 * Why an exception and not a result: every caller of the transport wants the refusal in the
 * place where the action was, and the words of the server travel with it, so the caller renders
 * the code and the message instead of guessing what happened.
 */
export class ApiError extends Error {
  /** The status the server answered with. Zero when the origin did not answer at all. */
  readonly status: number;

  /** The code of the refusal, for instance `LIVE_MODE_OFFLINE`. */
  readonly code: string;

  /** Whether the same request may work later. */
  readonly retryable: boolean;

  /** The identifier of the request, the one the logs of the server carry. */
  readonly requestId: string;

  /** The body of the refusal, when the server answered with the resource `Error`. */
  readonly body: ApiErrorBody | null;

  /**
   * The wait the server asked for, as the header `Retry-After` wrote it.
   *
   * Why the TEXT of the server and never a number the browser calculated: the front never computes
   * a wait with the clock of the browser, for the same reason it never computes the time that is
   * left of the expiry (FR-031). The value is the text of the header, exactly as it was sent.
   *
   * Why it is null and not zero: the difference between "the server said nothing" and "the server
   * said zero" is the difference between a refusal that carries no wait and a refusal that carries
   * a wait of no time at all.
   */
  readonly retryAfter: string | null;

  constructor(
    message: string,
    details: {
      status: number;
      code: string;
      retryable: boolean;
      requestId: string;
      body: ApiErrorBody | null;
      /**
       * The wait of the server, when the answer carried the header `Retry-After`.
       *
       * Why it is optional here and not in the field above: a refusal that is not a refusal of the
       * limits carries no wait, and the callers that do not read the header do not have to know
       * about it.
       */
      retryAfter?: string | null;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = details.status;
    this.code = details.code;
    this.retryable = details.retryable;
    this.requestId = details.requestId;
    this.body = details.body;
    this.retryAfter = details.retryAfter ?? null;
  }
}

/**
 * The options of the transport.
 *
 * Why the fetch and the origin can be given: the unit tests of the transport never open a
 * socket, and they need to say which origin they are talking to.
 */
export interface ApiClientOptions {
  /** The origin of the backend. The default is the origin of the configuration of the site. */
  baseUrl?: string;
  /** The fetch of the browser. The default is the fetch of the runtime. */
  fetchImpl?: typeof fetch;
}

/**
 * The calls the browser makes to the backend.
 *
 * Every method of this interface is a route of `ledgerlens/api/byok.py`, and every one of them
 * travels with the credentials of the session.
 */
export interface ApiClient {
  /** The origin the transport talks to, so the interface can say which origin it tried. */
  readonly baseUrl: string;

  /** Issues the session of the visitor and sets the cookie of the demo. */
  startSession(): Promise<SessionBody>;

  /** The catalogue of the models the visitor may pick. */
  models(): Promise<ModelCatalogueResponse>;

  /** The price of a model and where it comes from. */
  priceOfModel(profileId: string): Promise<ModelPriceResponse>;

  /** Accepts the key of the visitor and answers with the handle that stands for it. */
  acceptCredential(input: { provider: string; apiKey: string }): Promise<{
    handle: CredentialHandle;
    disclosure: DisclosureHeaders;
  }>;

  /** Drops the credential of a handle and says that the key is gone. */
  forgetCredential(handle: string): Promise<{ forgotten: boolean; message: string }>;

  /** Forks the published case into a private branch of the session. */
  forkSandbox(scenarioId: string): Promise<SandboxBody>;

  /** Starts a live run and answers with its identifier. */
  startLiveRun(request: LiveRunRequest): Promise<LiveRunAccepted>;

  /** The state of a run: its status, its answer and the reason it ended. */
  stateOfRun(runId: string): Promise<LiveRunState>;

  /** What the run consumed: the calls, the tokens, the elapsed time and the two costs. */
  costOfRun(runId: string): Promise<CostReportBody>;

  /** Cancels a run and says that the cancellation of a call in flight is a best effort. */
  cancelRun(runId: string): Promise<{
    run_id: string;
    status: string;
    best_effort: boolean;
    message: string;
  }>;
}

/** The answer of a call, with the headers the disclosures travel in. */
interface RawAnswer {
  status: number;
  body: unknown;
  headers: Headers;
}

/**
 * Reads the body of a refusal, when it is the resource `Error` of the contract.
 *
 * Why the reader is public: the envelope of the refusal has one reader in the repository and not
 * two, so the client of the sandbox of the visitor reads the envelope of a refusal with this very
 * reader and cannot disagree with the live mode about what a refusal is (ADR-044).
 *
 * Why it answers null for a body that is not the resource `Error`: a body that carries no code and
 * no message is not a refusal of the contract, and the caller decides what to do with it.
 */
export function readErrorBody(value: unknown): ApiErrorBody | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const candidate = value as Record<string, unknown>;
  if (typeof candidate["code"] !== "string" || typeof candidate["message"] !== "string") {
    return null;
  }
  return {
    code: candidate["code"],
    message: candidate["message"],
    retryable: candidate["retryable"] === true,
    request_id: typeof candidate["request_id"] === "string" ? candidate["request_id"] : "",
  };
}

/** The header that carries the wait the server asks for, in seconds. */
const RETRY_AFTER_HEADER = "Retry-After";

/**
 * Reads the wait of the server out of the headers of a refusal.
 *
 * Why only the status `429`: the header is the answer of the server to a request over the rate of
 * the requests, and the facade writes it in no other refusal. A wait that the server did not ask
 * for is a wait the browser invented, and the browser never invents one.
 *
 * Why the value is the text of the header: the front shows the number of seconds the server wrote
 * and it never computes a wait with the clock of the browser (FR-031).
 */
export function readRetryAfter(response: Response): string | null {
  if (response.status !== 429) {
    return null;
  }
  const wait = response.headers.get(RETRY_AFTER_HEADER);
  return wait === null || wait === "" ? null : wait;
}

/**
 * Creates the transport of the calls of the browser.
 *
 * Why the origin is normalized here: the caller may hand over a base with a trailing slash, and
 * the routes of the backend are published without one.
 */
export function createApiClient(options: ApiClientOptions = {}): ApiClient {
  const baseUrl = normalizeBaseUrl(options.baseUrl) ?? apiBaseUrl();
  const doFetch: typeof fetch =
    options.fetchImpl ?? ((input: RequestInfo | URL, init?: RequestInit) => globalThis.fetch(input, init));

  /** One call: it always carries the credentials of the session, and it never throws a raw error. */
  async function send(path: string, method: string, body?: unknown): Promise<RawAnswer> {
    const url = apiUrl(path, baseUrl);
    const init: RequestInit = {
      method,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
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
      const refusal = readErrorBody(parsed);
      throw new ApiError(refusal?.message ?? `the server answered ${response.status}`, {
        status: response.status,
        code: refusal?.code ?? "HTTP_ERROR",
        retryable: refusal?.retryable ?? false,
        requestId: refusal?.request_id ?? "",
        body: refusal,
        retryAfter: readRetryAfter(response),
      });
    }

    return { status: response.status, body: parsed, headers: response.headers };
  }

  /** The three disclosures of the server, read from the headers of the answer. */
  function disclosureOf(headers: Headers): DisclosureHeaders {
    return {
      billing: headers.get("X-LedgerLens-Billing-Disclosure"),
      keyStorage: headers.get("X-LedgerLens-Key-Storage"),
      keyErasure: headers.get("X-LedgerLens-Key-Erasure"),
    };
  }

  return {
    baseUrl,

    async startSession(): Promise<SessionBody> {
      const answer = await send("/v1/sessions", "POST");
      return answer.body as SessionBody;
    },

    async models(): Promise<ModelCatalogueResponse> {
      const answer = await send("/v1/models", "GET");
      return answer.body as ModelCatalogueResponse;
    },

    async priceOfModel(profileId: string): Promise<ModelPriceResponse> {
      const answer = await send(`/v1/models/${encodeURIComponent(profileId)}`, "GET");
      return answer.body as ModelPriceResponse;
    },

    async acceptCredential(input: { provider: string; apiKey: string }) {
      // The body carries the provider and the key and nothing else: the key of the visitor is
      // read here, from the argument of the caller, and from nowhere else.
      const answer = await send("/v1/credentials", "POST", {
        provider: input.provider,
        api_key: input.apiKey,
      });
      return {
        handle: answer.body as CredentialHandle,
        disclosure: disclosureOf(answer.headers),
      };
    },

    async forgetCredential(handle: string) {
      const answer = await send("/v1/credentials/forget", "POST", { handle });
      return answer.body as { forgotten: boolean; message: string };
    },

    async forkSandbox(scenarioId: string): Promise<SandboxBody> {
      const answer = await send("/v1/sandboxes", "POST", { scenario_id: scenarioId });
      return answer.body as SandboxBody;
    },

    async startLiveRun(request: LiveRunRequest): Promise<LiveRunAccepted> {
      const answer = await send("/v1/live-runs", "POST", request);
      return answer.body as LiveRunAccepted;
    },

    async stateOfRun(runId: string): Promise<LiveRunState> {
      const answer = await send(`/v1/live-runs/${encodeURIComponent(runId)}`, "GET");
      return answer.body as LiveRunState;
    },

    async costOfRun(runId: string): Promise<CostReportBody> {
      const answer = await send(`/v1/live-runs/${encodeURIComponent(runId)}/cost`, "GET");
      return answer.body as CostReportBody;
    },

    async cancelRun(runId: string) {
      const answer = await send(`/v1/live-runs/${encodeURIComponent(runId)}/cancel`, "POST");
      return answer.body as {
        run_id: string;
        status: string;
        best_effort: boolean;
        message: string;
      };
    },
  };
}

/**
 * The whole surface of the module, so a reader who opens the file sees it at once.
 *
 * Why the list is here: the transport of the repository is the place where the rules of the
 * credentials and of the refusals live, and a reader has to see the whole surface of it at once.
 */
export const __all__ = [
  "ApiError",
  "ApiClientOptions",
  "ApiClient",
  "readErrorBody",
  "readRetryAfter",
  "createApiClient",
] as const;
