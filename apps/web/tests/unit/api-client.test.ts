/**
 * The tests of the transport of the browser.
 *
 * Why this file exists: two rules of the transport are not negotiable. Every call carries the
 * credentials of the session, because the session cookie is the identity of the visitor, and
 * the transport never reads a provider key from anywhere but the argument of `acceptCredential`,
 * because a key that lives in the bundle or in the environment of the browser is a key that
 * every visitor of the site shares.
 *
 * Every case runs with no key and no network: the fetch of the test is a fake that records what
 * the client asked for and answers with a body the test chooses.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createApiClient } from "@/lib/api/client";
import type { LiveRunRequest } from "@/lib/api/live";

interface Answer {
  status: number;
  body: unknown;
  headers?: Record<string, string>;
}

interface RecordedCall {
  url: string;
  init: RequestInit;
}

/**
 * A response of the fake fetch.
 *
 * It carries only what the transport reads: the status, the headers and the body. The transport
 * never touches anything else of the answer of the server.
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

/** The request of a live run, with every field the published contract asks for. */
const aLiveRun: LiveRunRequest = {
  mode: "live_agent",
  scenario_id: "S01",
  sandbox_id: "branch_1",
  expected_revision: 0,
  account_id: "C-0001",
  question: "Why was the refund lower than the payment?",
  variant: "A",
  model_profile_id: "profile_1",
  credential_handle: "cred_1",
  limits: {
    max_model_calls: 8,
    max_tool_calls: 12,
    max_wall_seconds: 60,
    max_output_tokens: 2048,
  },
};

describe("the transport", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("carries the credentials of the session in every call", async () => {
    const { impl, calls } = fakeFetch(() => ({ status: 200, body: {} }));
    const client = createApiClient({ baseUrl: "http://localhost:8010", fetchImpl: impl });

    await client.startSession();
    await client.models();
    await client.priceOfModel("profile_1");
    await client.acceptCredential({ provider: "openai", apiKey: "sk-test" });
    await client.forgetCredential("cred_1");
    await client.forkSandbox("S01");
    await client.startLiveRun(aLiveRun);
    await client.stateOfRun("run_0123456789abcdef");
    await client.costOfRun("run_0123456789abcdef");
    await client.cancelRun("run_0123456789abcdef");

    expect(calls).toHaveLength(10);
    for (const call of calls) {
      expect(call.init.credentials).toBe("include");
    }
  });

  it("calls the routes of the backend", async () => {
    const { impl, calls } = fakeFetch(() => ({ status: 200, body: {} }));
    const client = createApiClient({ baseUrl: "http://localhost:8010", fetchImpl: impl });

    await client.startSession();
    await client.models();
    await client.priceOfModel("profile_1");
    await client.acceptCredential({ provider: "openai", apiKey: "sk-test" });
    await client.forgetCredential("cred_1");
    await client.forkSandbox("S01");
    await client.startLiveRun(aLiveRun);
    await client.stateOfRun("run_0123456789abcdef");
    await client.costOfRun("run_0123456789abcdef");
    await client.cancelRun("run_0123456789abcdef");

    expect(calls.map((call) => call.url)).toEqual([
      "http://localhost:8010/v1/sessions",
      "http://localhost:8010/v1/models",
      "http://localhost:8010/v1/models/profile_1",
      "http://localhost:8010/v1/credentials",
      "http://localhost:8010/v1/credentials/forget",
      "http://localhost:8010/v1/sandboxes",
      "http://localhost:8010/v1/live-runs",
      "http://localhost:8010/v1/live-runs/run_0123456789abcdef",
      "http://localhost:8010/v1/live-runs/run_0123456789abcdef/cost",
      "http://localhost:8010/v1/live-runs/run_0123456789abcdef/cancel",
    ]);
  });

  it("turns the refusal of the server into an ApiError", async () => {
    const { impl } = fakeFetch(() => ({
      status: 503,
      body: {
        code: "LIVE_MODE_OFFLINE",
        message: "the live mode is off because the product runs offline",
        retryable: false,
        request_id: "req_0123456789abcdef",
      },
    }));
    const client = createApiClient({ baseUrl: "http://localhost:8010", fetchImpl: impl });

    const failure = client.startLiveRun(aLiveRun);

    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({
      status: 503,
      code: "LIVE_MODE_OFFLINE",
      message: "the live mode is off because the product runs offline",
      retryable: false,
      requestId: "req_0123456789abcdef",
    });
  });

  it("turns an origin that does not answer into an ApiError", async () => {
    const impl = (async () => {
      throw new TypeError("failed to fetch");
    }) as unknown as typeof fetch;
    const client = createApiClient({ baseUrl: "http://localhost:8010", fetchImpl: impl });

    await expect(client.models()).rejects.toBeInstanceOf(ApiError);
    await expect(client.models()).rejects.toMatchObject({
      code: "NETWORK_ERROR",
    });
  });

  it("sends the provider and the key of the visitor and nothing else", async () => {
    const { impl, calls } = fakeFetch(() => ({
      status: 201,
      body: {
        handle: "cred_0123456789abcdef",
        provider: "openai",
        created_at: "2026-11-21T10:00:00+00:00",
        expires_at: "2026-11-21T18:00:00+00:00",
      },
    }));
    const client = createApiClient({ baseUrl: "http://localhost:8010", fetchImpl: impl });

    const answer = await client.acceptCredential({ provider: "openai", apiKey: "sk-test-key" });

    const body = JSON.parse(String(calls[0]?.init.body ?? "{}")) as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual(["api_key", "provider"]);
    expect(body["provider"]).toBe("openai");
    expect(body["api_key"]).toBe("sk-test-key");
    expect(answer.handle.handle).toBe("cred_0123456789abcdef");
  });

  it("reads the disclosure of the server from the headers of the answer", async () => {
    const { impl } = fakeFetch(() => ({
      status: 201,
      body: {
        handle: "cred_0123456789abcdef",
        provider: "openai",
        created_at: "2026-11-21T10:00:00+00:00",
        expires_at: "2026-11-21T18:00:00+00:00",
      },
      headers: {
        "X-LedgerLens-Billing-Disclosure": "your provider may charge you",
        "X-LedgerLens-Key-Storage": "the key is not stored",
        "X-LedgerLens-Key-Erasure": "the memory of the machine cannot be erased",
      },
    }));
    const client = createApiClient({ baseUrl: "http://localhost:8010", fetchImpl: impl });

    const answer = await client.acceptCredential({ provider: "openai", apiKey: "sk-test-key" });

    expect(answer.disclosure.billing).toBe("your provider may charge you");
    expect(answer.disclosure.keyStorage).toBe("the key is not stored");
    expect(answer.disclosure.keyErasure).toBe("the memory of the machine cannot be erased");
  });

  it("never reads a key from the environment", async () => {
    vi.stubEnv("OPENAI_API_KEY", "sk-from-the-environment");
    vi.stubEnv("LEDGERLENS_API_KEY", "sk-from-the-environment");
    vi.stubEnv("NEXT_PUBLIC_LEDGERLENS_API_KEY", "sk-from-the-environment");

    const { impl, calls } = fakeFetch(() => ({ status: 200, body: {} }));
    const client = createApiClient({ baseUrl: "http://localhost:8010", fetchImpl: impl });

    await client.startSession();
    await client.models();
    await client.acceptCredential({ provider: "openai", apiKey: "sk-test-key" });
    await client.forgetCredential("cred_1");
    await client.startLiveRun(aLiveRun);

    expect(calls.length).toBeGreaterThan(0);
    for (const call of calls) {
      expect(call.url).not.toContain("sk-from-the-environment");
      expect(String(call.init.body ?? "")).not.toContain("sk-from-the-environment");
    }
  });
});
