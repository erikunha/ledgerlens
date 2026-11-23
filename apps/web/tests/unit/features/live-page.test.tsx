/**
 * The test of the page of the live mode.
 *
 * Why this test exists: the live page is armed by the visitor and by nothing else, and the backend
 * may refuse the live mode while the product runs offline. The test pins the three rules of the
 * page: the consent box of the dialog gates the send, the page never starts a run on its own, and
 * the refusal `LIVE_MODE_OFFLINE` disables the live controls for the rest of the session (ADR-040,
 * question 7). A refusal with any other code leaves the controls usable, because the visitor may
 * type another key, and an origin that does not answer leaves them usable too, because the visitor
 * may start the backend and try again.
 *
 * Every case runs with no key and no network: the backend is a fake that answers the routes the
 * page calls, and the assertions are about what the visitor sees.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import LivePage from "@/app/(public)/live/page";

/**
 * The message the backend sends with the refusal of the live mode while the product runs offline.
 *
 * Why the real words of the server: the page has to show them, and a test with other words would
 * pass with a page that shows nothing.
 */
const OFFLINE_MESSAGE =
  "the live mode is off because the product runs offline (LEDGERLENS_OFFLINE=1); the replay and the sandbox keep working exactly as before";

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

/** Builds an answer of the fake backend, with the shape the transport of the browser expects. */
function answer(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === null ? "" : JSON.stringify(body)),
    headers: new Headers(),
  } as unknown as Response;
}

/**
 * The fake backend of the page: it answers the routes the page calls and records every call.
 *
 * Why the credential route is a parameter: the refusal of the credential is what the test is about,
 * and every other answer is the happy one.
 */
function fakeBackend(credential: () => Response) {
  const calls: string[] = [];
  const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    calls.push(url);
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
      return credential();
    }
    return answer(404, {
      code: "NOT_FOUND",
      message: "the route is not published",
      retryable: false,
      request_id: "request-0",
    });
  });
  return { calls, fetch: fetchImpl as unknown as typeof fetch };
}

/** The answer of a credential the backend accepted. */
function acceptedCredential(): Response {
  return answer(200, {
    handle: "handle-1",
    provider: "openai",
    created_at: "2026-11-21T00:00:00+00:00",
    expires_at: "2026-11-21T01:00:00+00:00",
  });
}

/**
 * Sends the key of the visitor through the dialog of the page.
 *
 * Why the three acts: the dialog is closed until the visitor asks for it, the send waits for the
 * tick of the consent, and the key is typed before the send.
 */
async function sendTheKey(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.click(await screen.findByRole("button", { name: /use your own key/i }));
  await user.type(screen.getByLabelText(/the key of your provider/i), "sk-test-key");
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: /send the key/i }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the page of the live mode", () => {
  it("keeps the send of the key disabled until the box of the consent is ticked", async () => {
    const user = userEvent.setup();
    const backend = fakeBackend(acceptedCredential);
    vi.stubGlobal("fetch", backend.fetch);

    render(<LivePage />);

    await user.click(await screen.findByRole("button", { name: /use your own key/i }));

    const send = screen.getByRole("button", { name: /send the key/i });
    expect(send).toBeDisabled();

    await user.click(screen.getByRole("checkbox"));

    expect(send).toBeEnabled();
  });

  it("never starts a run on its own", async () => {
    const backend = fakeBackend(acceptedCredential);
    vi.stubGlobal("fetch", backend.fetch);

    render(<LivePage />);

    expect(await screen.findByText("A small model")).toBeInTheDocument();
    expect(backend.calls.some((url) => url.includes("/v1/live-runs"))).toBe(false);
    expect(backend.calls.some((url) => url.includes("/v1/sandboxes"))).toBe(false);
    expect(screen.getByRole("button", { name: /run the case/i })).toBeDisabled();
  });

  it("disables the live controls for the rest of the session after the refusal LIVE_MODE_OFFLINE", async () => {
    const user = userEvent.setup();
    const backend = fakeBackend(() =>
      answer(503, {
        code: "LIVE_MODE_OFFLINE",
        message: OFFLINE_MESSAGE,
        retryable: false,
        request_id: "request-1",
      }),
    );
    vi.stubGlobal("fetch", backend.fetch);

    render(<LivePage />);

    await sendTheKey(user);

    expect(
      await screen.findByRole("heading", { name: /the live mode is off: LIVE_MODE_OFFLINE/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(OFFLINE_MESSAGE)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /use your own key/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /send the key/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /run the case/i })).toBeDisabled();
    // The caps are part of the live controls: a run the backend will never accept cannot be tuned.
    expect(screen.getByLabelText(/maximum calls of the model/i)).toBeDisabled();
    expect(screen.getByLabelText(/maximum calls of the tools/i)).toBeDisabled();
    expect(screen.getByLabelText(/maximum seconds of the run/i)).toBeDisabled();
    expect(screen.getByLabelText(/maximum tokens of the answer/i)).toBeDisabled();
    // The visitor is never trapped in the dialog: there is a way out of it.
    const close = screen.getByRole("button", { name: /close the dialog/i });
    expect(close).toBeInTheDocument();
    await user.click(close);
    expect(screen.queryByRole("button", { name: /send the key/i })).not.toBeInTheDocument();
  });

  it("keeps the controls usable after a refusal with another code", async () => {
    const user = userEvent.setup();
    const backend = fakeBackend(() =>
      answer(422, {
        code: "CREDENTIAL_REFUSED",
        message: "the key was refused by the server",
        retryable: false,
        request_id: "request-2",
      }),
    );
    vi.stubGlobal("fetch", backend.fetch);

    render(<LivePage />);

    await sendTheKey(user);

    expect((await screen.findAllByText(/CREDENTIAL_REFUSED/)).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /use your own key/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /send the key/i })).toBeEnabled();
  });

  it("keeps the controls usable when the origin does not answer, and says which origin it tried", async () => {
    const user = userEvent.setup();
    const backend = fakeBackend(() => {
      throw new TypeError("failed to fetch");
    });
    vi.stubGlobal("fetch", backend.fetch);

    render(<LivePage />);

    await sendTheKey(user);

    expect((await screen.findAllByText(/the origin .* did not answer the request/)).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /use your own key/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /send the key/i })).toBeEnabled();
  });
});
