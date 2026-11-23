/**
 * The test of the hook that runs the case and reads the stream.
 *
 * Why this test exists: the hook is where the live mode of the browser becomes a run. Three rules
 * of it are worth a test of their own. The counters come from the `run.status` events of the
 * stream, because the page shows them as the server reports them. The source is closed on the
 * terminal event, because a browser that reconnects would receive the whole stream again, forever.
 * And the refusal of the server is a refusal, never a run: the `503` with the code
 * `LIVE_MODE_OFFLINE` becomes the status `refused` with the code and the message of the server.
 *
 * Every case runs with no key and no network: the client and the stream are fakes.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DEMO_CASES } from "@/features/live/cases";
import { useLiveRun } from "@/features/live/useLiveRun";
import { ApiError, type ApiClient } from "@/lib/api/client";
import type { LiveStreamOptions } from "@/lib/api/events";
import { DEFAULT_RUN_LIMITS, type LiveRunRequest, type ModelProfile } from "@/lib/api/live";
import type { TraceEvent } from "@/lib/api/schemas";

/** The profile the live run uses in the cases of this test. */
const PROFILE: ModelProfile = {
  profile_id: "openai-gpt-4.1-mini",
  provider: "openai",
  model_id: "gpt-4.1-mini",
  display_name: "GPT-4.1 mini",
  capabilities: ["chat", "tool_calling"],
  status: "tested",
  enabled_in_public_demo: true,
  pricing: { source: "provider", last_verified: null, input_per_1m_usd: null, output_per_1m_usd: null },
};

/** The client of the backend, with every route answered by a fake. */
function fakeClient(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    baseUrl: "http://localhost:8010",
    startSession: async () => ({ id: "session_1", expires_at: "", mode_capabilities: [] }),
    models: async () => ({ models: [] }),
    priceOfModel: async () => ({ model: PROFILE, price_known: false, price_note: "" }),
    acceptCredential: async () => ({
      handle: { handle: "cred_1", provider: "openai", created_at: "", expires_at: "" },
      disclosure: { billing: null, keyStorage: null, keyErasure: null },
    }),
    forgetCredential: async () => ({ forgotten: true, message: "" }),
    forkSandbox: async () => ({
      id: "sbx_1",
      base_snapshot_id: "snap_1",
      snapshot_sha256: "",
      revision: 3,
      expires_at: "",
    }),
    startLiveRun: async () => ({ run_id: "run_0123456789abcdef", status: "running", mode: "live_agent" }),
    stateOfRun: async () => ({
      run_id: "run_0123456789abcdef",
      status: "running",
      answer: "",
      error: null,
      best_effort: false,
      cancel_requested: false,
      provider: null,
      model_profile_id: null,
      model_id: null,
    }),
    costOfRun: async () => ({
      run_id: "run_0123456789abcdef",
      status: "completed",
      model_calls: 2,
      tool_calls: 3,
      calls_by_model: {},
      input_tokens: 1000,
      output_tokens: 500,
      elapsed_seconds: 4.5,
      observed_cost_usd: "0.012345",
      estimated_cost_usd: "0.011",
      price_known: true,
      money_cap_authoritative: false,
      cut_by: null,
      usage_without_reservation: [],
      note: "the server wrote this note",
    }),
    cancelRun: async () => ({
      run_id: "run_0123456789abcdef",
      status: "cancelled",
      best_effort: true,
      message: "",
    }),
    ...overrides,
  };
}

/** One event of the stream, with the shape the contract publishes. */
function traceEvent(seq: number, eventType: TraceEvent["event_type"], payload: Record<string, unknown>): TraceEvent {
  return {
    schema_version: "1",
    run_id: "run_0123456789abcdef",
    seq,
    at: "2026-11-21T17:00:00+00:00",
    event_type: eventType,
    payload,
    mode: "live_agent",
  };
}

/** The case the live mode runs in the cases of this test. */
const DEMO_CASE = DEMO_CASES[0];
if (!DEMO_CASE) {
  throw new Error("the demo has to carry at least one case");
}

describe("the hook of the live run", () => {
  it("takes the counters from the events of the stream", async () => {
    const client = fakeClient();
    let captured: LiveStreamOptions | undefined;
    const streamFactory = vi.fn((_options: LiveStreamOptions) => {
      captured = _options;
      return { close: vi.fn() };
    });

    const { result } = renderHook(() => useLiveRun(client, { streamFactory }));

    await act(async () => {
      await result.current.start({
        profile: PROFILE,
        credentialHandle: "cred_1",
        limits: DEFAULT_RUN_LIMITS,
        demoCase: DEMO_CASE,
      });
    });

    expect(result.current.status).toBe("running");
    expect(result.current.runId).toBe("run_0123456789abcdef");

    act(() => {
      captured?.onEvent(
        traceEvent(1, "run.status", {
          model_calls: 2,
          tool_calls: 3,
          input_tokens: 1000,
          output_tokens: 500,
          elapsed_seconds: 4.5,
        }),
      );
    });

    expect(result.current.counters).toEqual({
      modelCalls: 2,
      toolCalls: 3,
      inputTokens: 1000,
      outputTokens: 500,
      elapsedSeconds: 4.5,
    });
  });

  it("closes the source on the terminal event and asks for the cost", async () => {
    const client = fakeClient();
    let captured: LiveStreamOptions | undefined;
    const close = vi.fn();
    const streamFactory = vi.fn((_options: LiveStreamOptions) => {
      captured = _options;
      return { close };
    });

    const { result } = renderHook(() => useLiveRun(client, { streamFactory }));

    await act(async () => {
      await result.current.start({
        profile: PROFILE,
        credentialHandle: "cred_1",
        limits: DEFAULT_RUN_LIMITS,
        demoCase: DEMO_CASE,
      });
    });

    act(() => {
      captured?.onEvent(traceEvent(2, "run.completed", { answer: "the answer of the agent" }));
    });

    expect(close).toHaveBeenCalled();
    expect(result.current.status).toBe("ended");
    await waitFor(() => {
      expect(result.current.cost?.observed_cost_usd).toBe("0.012345");
    });
  });

  it("turns the refusal of the offline mode into a refusal and never into a run", async () => {
    const refusal = new ApiError(
      "the live mode is off because the product runs offline (LEDGERLENS_OFFLINE=1); the replay and the sandbox keep working exactly as before",
      {
        status: 503,
        code: "LIVE_MODE_OFFLINE",
        retryable: false,
        requestId: "req_1",
        body: {
          code: "LIVE_MODE_OFFLINE",
          message:
            "the live mode is off because the product runs offline (LEDGERLENS_OFFLINE=1); the replay and the sandbox keep working exactly as before",
          retryable: false,
          request_id: "req_1",
        },
      },
    );
    const client = fakeClient({
      startLiveRun: async () => {
        throw refusal;
      },
    });
    const streamFactory = vi.fn((_options: LiveStreamOptions) => ({ close: vi.fn() }));

    const { result } = renderHook(() => useLiveRun(client, { streamFactory }));

    await act(async () => {
      await result.current.start({
        profile: PROFILE,
        credentialHandle: "cred_1",
        limits: DEFAULT_RUN_LIMITS,
        demoCase: DEMO_CASE,
      });
    });

    expect(result.current.status).toBe("refused");
    expect(result.current.error?.code).toBe("LIVE_MODE_OFFLINE");
    expect(result.current.error?.message).toContain("LEDGERLENS_OFFLINE=1");
    expect(result.current.runId).toBeNull();
    expect(streamFactory).not.toHaveBeenCalled();
  });

  it("never sends a key, only the handle of the credential", async () => {
    const startLiveRun = vi.fn(async (_request: LiveRunRequest) => ({
      run_id: "run_0123456789abcdef",
      status: "running",
      mode: "live_agent" as const,
    }));
    const client = fakeClient({ startLiveRun });
    const streamFactory = vi.fn((_options: LiveStreamOptions) => ({ close: vi.fn() }));

    const { result } = renderHook(() => useLiveRun(client, { streamFactory }));

    await act(async () => {
      await result.current.start({
        profile: PROFILE,
        credentialHandle: "cred_1",
        limits: DEFAULT_RUN_LIMITS,
        demoCase: DEMO_CASE,
      });
    });

    const body = startLiveRun.mock.calls[0]?.[0];
    expect(body?.credential_handle).toBe("cred_1");
    expect(JSON.stringify(body)).not.toMatch(/api_key|sk-/);
  });
});
