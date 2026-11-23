/**
 * The test of the cancellation of a run on the page of the live mode.
 *
 * Why this test exists: the cancellation of a run is a best effort, and the visitor has to read
 * that before pressing the button and not after the run ended. The contract of the product is
 * exact: the calls that have not started never start, a call that is already at the provider cannot
 * be guaranteed to stop, the server flags the cancellation as a best effort and the trace of the
 * run keeps the events that already happened (FR-019, SC-010).
 *
 * Why the flag is read from the server and not from the browser: the server knows whether a call
 * was already at the provider, and it says so in the answer of the cancellation and in the
 * terminal event of the trace. The hook keeps the flag and the page shows it (ADR-035).
 *
 * Every case runs with no key and no network: the backend is a fake and the source of the stream
 * is a fake, because jsdom has no `EventSource`.
 */

import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import LivePage from "@/app/(public)/live/page";

/** One model of the catalogue of the server, in the shape the contract publishes. */
const MODEL = {
  profile_id: "openai-small",
  provider: "openai",
  model_id: "gpt-4o-mini",
  display_name: "A small model",
  capabilities: ["chat"],
  status: "tested",
  enabled_in_public_demo: true,
  pricing: {
    source: "provider",
    last_verified: null,
    input_per_1m_usd: null,
    output_per_1m_usd: null,
  },
};

/** The identifier of the run of the cases of this test. */
const RUN_ID = "run_0123456789abcdef";

/**
 * The source of the stream of the events of the run, as a fake.
 *
 * Why the fake is here: the browser of a visitor opens the source, and jsdom has no
 * `EventSource`. The fake keeps the listeners and lets the test send the events of the server, the
 * way the backend frames them.
 */
class FakeEventSource {
  /** The source of the last run, so that the test can send the events of the server. */
  static last: FakeEventSource | null = null;

  /** The url the source was opened with. */
  readonly url: string;

  /** The listeners of the source, by the name of the event. */
  private readonly listeners = new Map<string, Set<(event: MessageEvent<string>) => void>>();

  /** Whether the source was closed. */
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.last = this;
  }

  /** Registers the listener of one name of event. */
  addEventListener(name: string, listener: (event: MessageEvent<string>) => void): void {
    const known = this.listeners.get(name) ?? new Set<(event: MessageEvent<string>) => void>();
    known.add(listener);
    this.listeners.set(name, known);
  }

  /** Closes the source, the way the browser does when the run ends. */
  close(): void {
    this.closed = true;
  }

  /** Sends one event of the server, with the framing the backend writes. */
  send(eventType: string, payload: Record<string, unknown>): void {
    const data = JSON.stringify({
      schema_version: "1",
      run_id: RUN_ID,
      seq: 1,
      at: "2026-11-21T17:00:00+00:00",
      event_type: eventType,
      payload,
      mode: "live_agent",
    });
    for (const listener of this.listeners.get(eventType) ?? []) {
      listener({ data } as MessageEvent<string>);
    }
  }
}

/** Builds an answer of the fake backend, with the shape the transport of the browser expects. */
function answer(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === null ? "" : JSON.stringify(body)),
    headers: new Headers(),
  } as unknown as Response;
}

/** The backend of the demo, with every route the page calls answered by a fake. */
function fakeBackend(): { fetch: typeof fetch } {
  const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/v1/sessions")) {
      return answer(200, { id: "session-1", expires_at: "", mode_capabilities: [] });
    }
    if (url.includes("/v1/models/openai-small")) {
      return answer(200, { model: MODEL, price_known: false, price_note: "the price is unknown" });
    }
    if (url.includes("/v1/models")) {
      return answer(200, { models: [MODEL] });
    }
    if (url.includes("/v1/credentials")) {
      return answer(200, {
        handle: "handle-1",
        provider: "openai",
        created_at: "2026-11-21T00:00:00+00:00",
        expires_at: "2026-11-21T01:00:00+00:00",
      });
    }
    if (url.includes("/v1/sandboxes")) {
      return answer(200, {
        id: "sbx-1",
        base_snapshot_id: "snap-1",
        snapshot_sha256: "hash",
        revision: 0,
        expires_at: "",
      });
    }
    if (url.includes("/v1/live-runs") && url.includes("/cancel")) {
      return answer(200, {
        run_id: RUN_ID,
        status: "cancelling",
        best_effort: true,
        message: "the run was cancelled",
      });
    }
    if (url.includes("/v1/live-runs") && url.includes("/cost")) {
      return answer(200, {
        run_id: RUN_ID,
        status: "cancelled",
        model_calls: 1,
        tool_calls: 0,
        calls_by_model: { "gpt-4o-mini": 1 },
        input_tokens: 120,
        output_tokens: 30,
        elapsed_seconds: 1.5,
        observed_cost_usd: "0.012345",
        estimated_cost_usd: "0.011",
        price_known: true,
        money_cap_authoritative: false,
        cut_by: null,
        usage_without_reservation: [],
        note: "the server wrote this note",
      });
    }
    if (url.includes("/v1/live-runs")) {
      return answer(201, { run_id: RUN_ID, status: "running", mode: "live_agent" });
    }
    return answer(404, {
      code: "NOT_FOUND",
      message: "the route is not published",
      retryable: false,
      request_id: "request-0",
    });
  });
  return { fetch: fetchImpl as unknown as typeof fetch };
}

/**
 * Arms the page: the visitor types the key, ticks the consent, picks the model and starts the run.
 *
 * Why the four acts: the dialog is closed until the visitor asks for it, the send waits for the
 * tick of the consent, the run needs a model, and the run needs a key.
 */
async function armTheRun(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.click(await screen.findByRole("button", { name: /use your own key/i }));
  await user.type(screen.getByLabelText(/the key of your provider/i), "sk-test-key");
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: /send the key/i }));

  await screen.findByText(/the server accepted the key of your provider/i);

  await user.click(screen.getByRole("radio", { name: /a small model/i }));
  await user.click(screen.getByRole("button", { name: /run the case/i }));

  await waitFor(() => {
    expect(FakeEventSource.last).not.toBeNull();
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  FakeEventSource.last = null;
});

describe("the cancellation of a run on the page of the live mode", () => {
  it("says that stopping a run is a best effort before the visitor stops it", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", fakeBackend().fetch);
    vi.stubGlobal("EventSource", FakeEventSource);

    render(<LivePage />);

    const reason = await screen.findByText(/stopping a run ends it/i);
    expect(reason).toBeInTheDocument();
    expect(reason.textContent).toMatch(/a call that is already at the provider is a best effort/i);
    expect(reason.textContent).toMatch(/the trace keeps the events that already happened/i);

    await armTheRun(user);

    // The control that stops the run points at the reason, so a reader of a screen reader hears it.
    expect(screen.getByRole("button", { name: /stop the run/i })).toHaveAttribute(
      "aria-describedby",
      expect.stringContaining("ledgerlens"),
    );
  });

  it("says that the cancellation was a best effort when the server flags it", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", fakeBackend().fetch);
    vi.stubGlobal("EventSource", FakeEventSource);

    render(<LivePage />);
    await armTheRun(user);

    // The visitor stops the run, and the server answers that the cancellation is a best effort.
    await user.click(screen.getByRole("button", { name: /stop the run/i }));

    // The notice is an alert, so a reader of a screen reader hears it when it appears.
    const notice = await screen.findByRole("alert");
    expect(within(notice).getByText(/the cancellation was a best effort/i)).toBeInTheDocument();
    // The sentence says what the call that was in flight may do, and what happens to the trace.
    expect(
      within(notice).getByText(/a call of the provider was already in flight when you stopped the run/i),
    ).toBeInTheDocument();
    expect(
      within(notice).getByText(/it may finish anyway, and the tokens it reports are counted in the cost/i),
    ).toBeInTheDocument();
    expect(
      within(notice).getByText(/the trace keeps the events that already happened/i),
    ).toBeInTheDocument();
  });

  it("says that the run was cancelled when the trace ends it without the flag of the best effort", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", fakeBackend().fetch);
    vi.stubGlobal("EventSource", FakeEventSource);

    render(<LivePage />);
    await armTheRun(user);

    await act(async () => {
      FakeEventSource.last?.send("run.cancelled", { status: "cancelled", best_effort: false });
    });

    expect(await screen.findByText(/the run was cancelled/i)).toBeInTheDocument();
    expect(screen.getByText(/the calls that had not started never started/i)).toBeInTheDocument();
    expect(screen.queryByText(/the cancellation was a best effort/i)).not.toBeInTheDocument();
  });
});
