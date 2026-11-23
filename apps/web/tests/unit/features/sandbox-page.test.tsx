/**
 * The test of the route of the sandbox of the visitor.
 *
 * Why this test exists: the route is the door of the third room of the demo. It shows the scenarios of the published
 * catalog, it opens the branch of the scenario the visitor picked, and it keeps the state of the branch in the memory
 * of the page. The address of the browser carries NOTHING: no identifier of the scenario, no identifier of the branch
 * and no revision, because a branch of a visitor never travels in a link and never stays in a storage of the browser
 * (ADR-044).
 *
 * Why the case stubs the fetch of the runtime: the route reads the published catalog through the one loader of the
 * artifacts and the branch through the one client of the branch, and neither of them may open a socket in a test.
 *
 * Every case runs with no key and no network.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import SandboxPage from "@/app/(public)/sandbox/page";

/** One card of the published catalog of the scenarios, as `site/replay/index.json` holds it. */
const CATALOG = [
  {
    id: "S01",
    name: "fx_markup_refund",
    question: "Why was the BRL refund for TX-2048 lower than the EUR payment?",
    concepts: ["read_only_ledger_query", "policy_retrieval"],
    data_origin: "UCI Online Retail II",
    status: "Recorded",
  },
];

/** The identifier of the branch, as the server writes it. */
const BRANCH_ID = "sb_0123456789abcdef01234567";

/** The branch, as the answer of the fork carries it. */
const BRANCH = {
  id: BRANCH_ID,
  base_snapshot_id: "snap_01",
  snapshot_sha256: "0".repeat(64),
  revision: 0,
  expires_at: "2026-11-22T12:00:00+00:00",
};

/** The two headers of the branch, as the answer of the fork carries them. */
const BRANCH_HEADERS = {
  "X-LedgerLens-Branch-Hash": "hash_of_the_branch",
  "X-LedgerLens-Branch-State": "active",
};

/**
 * One call the fake network answered.
 *
 * Why the calls are kept: a case has to prove WHAT the page asked for, and a case that only proves what the page shows
 * would pass with a page that asked for the wrong scenario.
 */
interface RecordedCall {
  /** The address of the call. */
  readonly url: string;
  /** The method of the call. */
  readonly method: string;
  /** The body of the call, when it had one. */
  readonly body: unknown;
}

/** Every call the fake network answered. */
const CALLS: RecordedCall[] = [];

/**
 * Builds an answer of the fake network.
 *
 * Why the headers are a little object and not the ones of the runtime: the case runs in jsdom, and the reader of the
 * branch only ever asks the headers for the hash and for the state of the branch.
 */
function answer(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (name: string): string | null => {
        const found = Object.keys(headers).find((key) => key.toLowerCase() === name.toLowerCase());
        return found === undefined ? null : (headers[found] ?? null);
      },
    },
    text: async (): Promise<string> => (body === null ? "" : JSON.stringify(body)),
  } as unknown as Response;
}

/**
 * Stubs the network of the case with the published catalog and with the answers of the backend.
 *
 * Why the catalog and the backend answer the same fake: the route reads the catalog of the site and the branch of the
 * origin of the backend, and the case proves that the route asks for the catalog of the site and for the branch of the
 * scenario the visitor picked, without opening a socket.
 */
function stubNetwork(): void {
  CALLS.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      let body: unknown = null;
      if (typeof init?.body === "string") {
        try {
          body = JSON.parse(init.body) as unknown;
        } catch {
          body = init.body;
        }
      }
      CALLS.push({ url, method, body });

      if (url.endsWith("/replay/index.json")) {
        return answer(200, CATALOG);
      }
      if (method === "POST" && url.endsWith("/v1/sandboxes")) {
        return answer(201, BRANCH, BRANCH_HEADERS);
      }
      return answer(404, {
        code: "NOT_FOUND",
        message: "the fake network does not know this route",
        retryable: false,
        request_id: "req_fake",
      });
    }),
  );
}

/** Renders the route of the sandbox with the network of the case. */
function renderPage(): void {
  stubNetwork();
  render(<SandboxPage />);
}

afterEach(() => {
  vi.unstubAllGlobals();
  CALLS.length = 0;
});

describe("the route of the sandbox", () => {
  it("reads the published catalog of the scenarios at run time", async () => {
    // It proves that the list of the cases comes from the catalog of the site and not from a list the
    // route invented: the loader of the artifacts is the ONE place that reads the published files.
    renderPage();

    await screen.findByRole("button", { name: /open the branch of S01/i });

    expect(CALLS.some((call) => call.url.endsWith("/replay/index.json"))).toBe(true);
  });

  it("shows the scenarios of the published catalog", async () => {
    // It proves that the visitor sees the cases the site published, each one with its question.
    renderPage();

    await screen.findByRole("button", { name: /open the branch of S01/i });

    expect(screen.getByText(/why was the BRL refund for TX-2048 lower than the EUR payment/i)).toBeInTheDocument();
  });

  it("opens the branch of the scenario the visitor picked", async () => {
    // It proves that the fork names the scenario that the visitor chose and not another one, and that the
    // branch the server answers is the one the panel draws.
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /open the branch of S01/i }));

    await screen.findByText(BRANCH_ID);

    const fork = CALLS.find((call) => call.method === "POST" && call.url.endsWith("/v1/sandboxes"));
    expect(fork).toBeDefined();
    expect(fork?.body).toEqual({ scenario_id: "S01" });
  });

  it("keeps the address of the browser free of the branch", async () => {
    // It proves that the URL of the route carries NOTHING: no identifier of the scenario, no identifier of the
    // branch and no revision. A branch of a visitor never travels in a link.
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /open the branch of S01/i }));
    await screen.findByText(BRANCH_ID);

    expect(window.location.search).toBe("");
    expect(window.location.pathname).not.toContain("S01");
    expect(window.location.href).not.toContain(BRANCH_ID);

    for (const link of Array.from(document.querySelectorAll("a"))) {
      const href = link.getAttribute("href") ?? "";
      expect(href).not.toContain("S01");
      expect(href).not.toContain(BRANCH_ID);
      expect(href.includes("?")).toBe(false);
    }
  });

  it("keeps the state of the branch out of the storage of the browser", async () => {
    // It proves that the state of the branch lives in the memory of the page and nowhere else: not in the
    // localStorage, not in the sessionStorage and not in a cookie.
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /open the branch of S01/i }));
    await screen.findByText(BRANCH_ID);

    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });

  it("links back to the recorded demo and to the live mode", async () => {
    // It proves that the pages of the site link to each other in their bodies, the way the live mode already
    // links to the recorded demo.
    renderPage();

    const recorded = await screen.findByRole("link", { name: /open the recorded demo/i });
    const live = screen.getByRole("link", { name: /open the live mode/i });

    expect(recorded).toHaveAttribute("href", "/replay");
    expect(live).toHaveAttribute("href", "/live");
  });

  it("shows the concepts that the scenario demonstrates", async () => {
    // It proves that the card shows the concepts of the scenario, because the concepts are part of
    // what the catalog publishes and a card that throws them away is a card that hides what the
    // scenario demonstrates.
    renderPage();

    await screen.findByRole("button", { name: /open the branch of S01/i });

    expect(screen.getByText("read_only_ledger_query")).toBeInTheDocument();
    expect(screen.getByText("policy_retrieval")).toBeInTheDocument();
  });

  it("shows a skeleton while the catalog is being read", async () => {
    // It proves that the page says that it is loading while it loads, because a page that shows a
    // title over nothing reads as a broken page.
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>(() => {
            // the reading of the catalog never finishes
          }),
      ),
    );

    render(<SandboxPage />);

    const skeleton = await screen.findByRole("status", {
      name: "The catalog of the scenarios is being read",
    });
    expect(skeleton).toBeInTheDocument();
  });
});
