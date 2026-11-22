/**
 * The tests of the panel of the branch with the refusals of the limits.
 *
 * Why this file exists: the facade refuses the two limits with `429 RESOURCE_LIMIT_EXCEEDED`, and
 * the flag `retryable` is the only difference between them (ADR-047). The rate of the requests is
 * retryable and carries the wait of the server in the header `Retry-After`; the cap of the branches
 * of the session is not retryable and carries no wait. The panel shows the wait of the server and
 * it never calculates one, and it stops offering the action when the server says that the same
 * request will not work later.
 *
 * Why the panel never counts: the server names the count and the cap in the message of the
 * refusal, and the panel shows that message as it is. The panel never counts the branches of the
 * session and never computes a wait with the clock of the browser.
 *
 * Every case runs with no key and no network: the panel reads the state of the branch and never
 * the network.
 */

import { act, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BranchPanel, type BranchPanelState } from "@/features/sandbox/BranchPanel";
import { useBranch } from "@/features/sandbox/useBranch";
import { ApiError } from "@/lib/api/client";

/** The identifier of the branch, as the server writes it. */
const BRANCH_ID = "sb_0123456789abcdef01234567";

/** The moment the branch dies, as the server writes it. */
const EXPIRES_AT = "2026-11-22T12:00:00+00:00";

/**
 * The state of a branch that is ready, with the overrides a case needs.
 *
 * Why the helper exists: every case needs the same state, and a case that built it by hand would
 * repeat the same fields in every test.
 */
function stateOf(overrides: Partial<BranchPanelState> = {}): BranchPanelState {
  return {
    phase: "ready",
    branchId: BRANCH_ID,
    revision: 3,
    expiresAt: EXPIRES_AT,
    canonicalHash: "hash_of_the_base",
    branchState: "active",
    created: true,
    preview: null,
    diff: null,
    history: null,
    refusal: null,
    ...overrides,
  };
}

/** The refusal of the rate of the requests, with the wait that the server wrote. */
function rateRefusal(): BranchPanelState["refusal"] {
  return {
    code: "RESOURCE_LIMIT_EXCEEDED",
    message: "the session made too many requests in one minute",
    retryable: true,
    request_id: "req_01",
    retryAfter: "42",
  };
}

/** The refusal of the cap of the branches of the session, which carries no wait. */
function branchCapRefusal(): BranchPanelState["refusal"] {
  return {
    code: "RESOURCE_LIMIT_EXCEEDED",
    message: "the session holds five live branches already",
    retryable: false,
    request_id: "req_02",
  };
}

/**
 * The client that the hook expects, read from the options of the hook itself.
 *
 * Why the type is read from the hook: the hook owns the shape of the client it takes, and a case
 * that wrote the shape by hand would break the day the shape moves.
 */
type ClientOfTheHook = Parameters<typeof useBranch>[0]["client"];

/**
 * The refusal of the rate of the requests, as the transport of the repository raises it.
 *
 * Why the wait is the text of the server: the server writes the wait in the header `Retry-After`
 * and the browser never calculates one (ADR-047).
 */
function rateRefusalOfTheServer(): ApiError {
  return new ApiError("the session made too many requests in one minute", {
    status: 429,
    code: "RESOURCE_LIMIT_EXCEEDED",
    retryable: true,
    requestId: "req_03",
    body: {
      code: "RESOURCE_LIMIT_EXCEEDED",
      message: "the session made too many requests in one minute",
      retryable: true,
      request_id: "req_03",
    },
    retryAfter: "37",
  });
}

/**
 * The client of the branch, and every call of it refuses with the refusal of the rate.
 *
 * Why the client refuses and does not answer: the case is about the refusal of the rate and about
 * the wait that the server wrote in the header of that refusal.
 */
function clientThatRefuses(): ClientOfTheHook {
  return {
    fork: vi.fn(async () => {
      throw rateRefusalOfTheServer();
    }),
    startSession: vi.fn(async () => ({ id: "session_01", expires_at: EXPIRES_AT, mode_capabilities: [] })),
  } as unknown as ClientOfTheHook;
}

describe("the panel of the branch with the refusals of the limits", () => {
  it("shows the wait the server wrote, and it shows the number of the server", () => {
    render(
      <BranchPanel
        state={stateOf({ refusal: rateRefusal() })}
        onReset={() => {}}
        onEndSession={() => {}}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("42");
    expect(alert).toHaveTextContent(/wait/i);
  });

  it("shows no wait at all when the server refused without a wait", () => {
    render(
      <BranchPanel
        state={stateOf({ refusal: branchCapRefusal() })}
        onReset={() => {}}
        onEndSession={() => {}}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("RESOURCE_LIMIT_EXCEEDED");
    expect(alert).not.toHaveTextContent(/wait/i);
    expect(alert).not.toHaveTextContent(/\d+\s*second/);
  });

  it("does not offer the action again when the refusal is not retryable", async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    render(
      <BranchPanel
        state={stateOf({ refusal: branchCapRefusal() })}
        onReset={onReset}
        onEndSession={() => {}}
      />,
    );

    const reset = screen.getByRole("button", { name: /put the branch back at the base/i });
    expect(reset).not.toBeDisabled();
    expect(reset).toHaveAttribute("aria-disabled", "true");

    const reason = screen.getByText(/will not work later/i);
    expect(reset.getAttribute("aria-describedby")).toBe(reason.getAttribute("id"));

    await user.click(reset);

    expect(onReset).not.toHaveBeenCalled();
  });

  it("offers the action again when the refusal is retryable", async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    render(
      <BranchPanel
        state={stateOf({ refusal: rateRefusal() })}
        onReset={onReset}
        onEndSession={() => {}}
      />,
    );

    const reset = screen.getByRole("button", { name: /put the branch back at the base/i });
    expect(reset).not.toHaveAttribute("aria-disabled", "true");

    await user.click(reset);

    expect(onReset).toHaveBeenCalledTimes(1);
  });
});

describe("the hook of the branch with the refusal of the rate", () => {
  it("carries the wait the server wrote into the state of the hook", async () => {
    // The hook copies the wait of the refusal into the state it holds, and a hook that dropped it
    // would leave the panel with no wait at all, so the case pins the copy here.
    const { result } = renderHook(() => useBranch({ client: clientThatRefuses() }));

    await act(async () => {
      await result.current.open("S01");
    });

    expect(result.current.state.refusal?.code).toBe("RESOURCE_LIMIT_EXCEEDED");
    expect(result.current.state.refusal?.retryAfter).toBe("37");
  });

  it("shows in the panel the number of seconds the server wrote, and never a number of the browser", async () => {
    const { result } = renderHook(() => useBranch({ client: clientThatRefuses() }));

    await act(async () => {
      await result.current.open("S01");
    });

    render(
      <BranchPanel
        state={result.current.state}
        onReset={() => {}}
        onEndSession={() => {}}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("The server asks to wait 37 seconds before this request is tried again.");
    expect(alert).not.toHaveTextContent(/\b60\b/);
  });
});
