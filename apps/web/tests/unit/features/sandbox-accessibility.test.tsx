/**
 * The regression guard of the accessibility of the sandbox of the visitor.
 *
 * Why this file exists: the accessibility of the front of the sandbox is part of the contract of the milestone and not
 * a polish of the end of it (ADR-044). Every rule of that block has to be able to fail, and this file is where the
 * rules live as cases:
 *
 * 1. the outline of the headings never skips a level, from the `h1` of the route to the `h4` of the verdict;
 * 2. the controls are never `disabled`, and the blocked ones carry `aria-disabled` and a reason they point at;
 * 3. the `aria-current` sits on the ROW of the history and on no cell of it;
 * 4. the change is announced in a polite region and the refusal of the server in an alert, and the two never overlap;
 * 5. the diff is a table with a caption and a header for every column;
 * 6. the state is never only a colour.
 *
 * Every case runs with no key and no network: the fetch of the runtime is a fake that answers with the published
 * catalog and with the answers of the backend.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import SandboxPage from "@/app/(public)/sandbox/page";

/** One card of the published catalog of the scenarios, as `site/replay/index.json` holds it. */
const CATALOG = [
  {
    id: "S01",
    name: "fx_markup_refund",
    question: "Why was the BRL refund for TX-2048 lower than the EUR payment?",
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

/** The difference between the published base and the branch, as the server answers it. */
const DIFF = {
  revision: 1,
  base_canonical_hash: "hash_of_the_base",
  canonical_hash: "hash_of_the_branch",
  diff: [
    {
      record: "refunds",
      record_id: "R0001",
      field: "amount",
      before: "100.00",
      after: "105.50",
      value_kind: "monetary",
      currency: "EUR",
    },
  ],
  invariants: [
    {
      identifier: "refund_amount_positive",
      description: "the amount of the refund is positive",
      passed: true,
      reason: "",
    },
  ],
  verdict: {
    label: "within_expected_range",
    measure: "fx_markup",
    value: "0.055",
    low: "0.01",
    high: "0.08",
    detail: "the rate is inside the range that the policy allows",
  },
};

/**
 * The log of the branch, as the server answers it.
 *
 * Why the last event is undone: the branch stands at the LAST event that is not undone, and a case that marked the
 * last event of the log would pass with a page that marks the wrong row.
 */
const HISTORY = {
  revision: 1,
  canonical_hash: "hash_of_the_branch",
  events: [
    {
      event_uid: "evt_1",
      event_type: "branch.forked",
      aggregate_id: BRANCH_ID,
      occurred_at: "2026-11-22T10:00:00+00:00",
      payload: {},
      undone: false,
    },
    {
      event_uid: "evt_2",
      event_type: "refund.applied",
      aggregate_id: "R0001",
      occurred_at: "2026-11-22T10:05:00+00:00",
      payload: {},
      undone: true,
    },
  ],
  answers: [],
};

/** The refusal of the server, as the resource `Error` of the contract carries it. */
const REFUSAL = {
  code: "REVISION_CONFLICT",
  message: "the branch is at revision 2 and the request expected 1",
  retryable: false,
  request_id: "req_01a2b3c4d5e6f7a8b",
};

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
 * Stubs the network of the case.
 *
 * Why the fork can be refused: the refusal of the server is announced by an alert and not by the polite region, and a
 * case that never refuses anything cannot prove that the two regions never overlap.
 */
function stubNetwork(options: { readonly refuseTheFork?: boolean } = {}): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();

      if (url.endsWith("/replay/index.json")) {
        return answer(200, CATALOG);
      }
      if (method === "POST" && url.endsWith("/v1/sandboxes")) {
        if (options.refuseTheFork === true) {
          return answer(409, REFUSAL);
        }
        return answer(201, BRANCH, BRANCH_HEADERS);
      }
      if (url.endsWith("/diff")) {
        return answer(200, DIFF);
      }
      if (url.endsWith("/history")) {
        return answer(200, HISTORY);
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
function renderPage(options: { readonly refuseTheFork?: boolean } = {}): void {
  stubNetwork(options);
  render(<SandboxPage />);
}

/** Opens the branch of the first scenario of the catalog. */
async function openTheBranch(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.click(await screen.findByRole("button", { name: /open the branch of S01/i }));
  await screen.findByText(BRANCH_ID);
}

/**
 * Proves that every control of the page is honest.
 *
 * Why the helper exists: the rule is about EVERY control of the page, and a case that checks two of them proves
 * nothing about the other six.
 */
function expectHonestControls(): void {
  for (const control of screen.getAllByRole("button")) {
    expect(control).not.toBeDisabled();
    expect(control).not.toHaveAttribute("disabled");

    if (control.getAttribute("aria-disabled") !== "true") {
      continue;
    }

    // a blocked control points at its reason, and the reason is a sentence a reader can hear
    const describedBy = control.getAttribute("aria-describedby");
    expect(describedBy).not.toBeNull();
    const reason = document.getElementById((describedBy ?? "").split(" ")[0] ?? "");
    expect(reason).not.toBeNull();
    expect((reason?.textContent?.trim() ?? "").length).toBeGreaterThan(0);
  }
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the outline of the headings of the sandbox", () => {
  it("never skips a level", async () => {
    // It proves that the outline mirrors the sections of the page: the route has its h1, the panel of the branch
    // has its h2, the three sections of the page have their h3 and the verdict of the case has its h4.
    const user = userEvent.setup();
    renderPage();

    await openTheBranch(user);
    await user.click(screen.getByRole("button", { name: /read the difference/i }));
    await screen.findByRole("table", { name: /the difference between the published base and the branch/i });
    await user.click(screen.getByRole("button", { name: /read the history/i }));
    await screen.findByRole("table", { name: /the log of the branch/i });

    const headings = Array.from(
      document.querySelectorAll("h1, h2, h3, h4, h5, h6"),
    ) as HTMLHeadingElement[];

    expect(headings.length).toBeGreaterThan(0);
    expect(headings.some((heading) => heading.tagName === "H1")).toBe(true);
    expect(headings.some((heading) => heading.tagName === "H4")).toBe(true);

    // the outline is a contract and not only a rule about the skips: the panel of the branch is the second
    // level, the three sections of the page are the third level and the verdict of the case is the fourth.
    expect(screen.getByRole("heading", { level: 2, name: "The branch of the visitor" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "The mutation" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "The difference" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "The history" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 4, name: "The verdict of the case" })).toBeInTheDocument();

    let previous = 0;
    for (const heading of headings) {
      const level = Number(heading.tagName.slice(1));
      if (previous !== 0) {
        expect(level - previous).toBeLessThanOrEqual(1);
      }
      previous = level;
    }
  });
});

describe("the controls of the sandbox", () => {
  it("are never disabled, and the blocked ones say why", async () => {
    // It proves that a control that would do nothing stays in the keyboard, carries `aria-disabled` and points
    // at a reason a reader can hear.
    renderPage();

    await screen.findByRole("button", { name: /open the branch of S01/i });
    expectHonestControls();
  });

  it("are never disabled once the branch is open either", async () => {
    // It proves the same rule for the page with a branch: the rule is about every control, not only about the
    // controls of a page that has nothing yet.
    const user = userEvent.setup();
    renderPage();

    await openTheBranch(user);
    expectHonestControls();
  });
});

describe("the place the branch stands at", () => {
  it("sits on the row of the history and on no cell of it", async () => {
    // It proves that the `aria-current` marks the LINE where the branch stands, which is the last event that
    // is not undone, and that no cell of the row carries the mark.
    const user = userEvent.setup();
    renderPage();

    await openTheBranch(user);
    await user.click(screen.getByRole("button", { name: /read the history/i }));
    await screen.findByRole("table", { name: /the log of the branch/i });

    const current = screen.getAllByRole("row", { current: true });
    expect(current).toHaveLength(1);
    expect(current[0]?.tagName).toBe("TR");
    expect(current[0]).toHaveTextContent("evt_1");
    expect(current[0]).not.toHaveTextContent("evt_2");

    expect(document.querySelectorAll("td[aria-current], th[aria-current]")).toHaveLength(0);
  });
});

describe("the announcements of the page", () => {
  it("announces the change in a polite region", async () => {
    // It proves that the change of the branch is announced politely, with one sentence at a time, and that the
    // region is never assertive.
    const user = userEvent.setup();
    renderPage();

    await openTheBranch(user);

    const statuses = screen.getAllByRole("status");
    expect(statuses).toHaveLength(1);

    const status = statuses[0] as HTMLElement;
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveAttribute("aria-atomic", "true");
    expect(status).not.toHaveAttribute("aria-live", "assertive");
    expect(status.textContent ?? "").toMatch(/revision 0/i);

    // the region carries the sentence of the LAST change and one sentence at a time
    await user.click(screen.getByRole("button", { name: /read the difference/i }));
    await screen.findByRole("table", { name: /the difference between the published base and the branch/i });

    expect(status.textContent ?? "").toMatch(/the difference has been read/i);
    expect(status.textContent ?? "").not.toMatch(/revision 0/i);
  });

  it("announces the refusal of the server in an alert and not in the polite region", async () => {
    // It proves that a refusal is heard at once, that it carries the code and the message of the server, and
    // that the two regions never overlap: the polite region says nothing about the refusal.
    const user = userEvent.setup();
    renderPage({ refuseTheFork: true });

    await user.click(await screen.findByRole("button", { name: /open the branch of S01/i }));

    const alerts = await screen.findAllByRole("alert");
    expect(alerts).toHaveLength(1);
    expect(alerts[0]).toHaveTextContent("REVISION_CONFLICT");
    expect(alerts[0]).toHaveTextContent("the branch is at revision 2 and the request expected 1");

    const status = screen.getByRole("status");
    expect(status).not.toHaveTextContent("REVISION_CONFLICT");
    expect(status).not.toHaveTextContent("the branch is at revision 2 and the request expected 1");
  });
});

describe("the difference of the branch", () => {
  it("is a table with a caption and a header for every column", async () => {
    // It proves that the difference is a table a screen reader can read: the caption names it, every column has
    // a header and every row has the header of its field.
    const user = userEvent.setup();
    renderPage();

    await openTheBranch(user);
    await user.click(screen.getByRole("button", { name: /read the difference/i }));

    const table = await screen.findByRole("table", {
      name: /the difference between the published base and the branch/i,
    });

    expect(table.querySelector("caption")?.textContent).toBe(
      "The difference between the published base and the branch",
    );

    const columns = within(table).getAllByRole("columnheader");
    expect(columns).toHaveLength(5);
    for (const column of columns) {
      expect(column).toHaveAttribute("scope", "col");
    }

    const rows = within(table).getAllByRole("rowheader");
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      expect(row).toHaveAttribute("scope", "row");
    }
  });
});

describe("the state is never only a colour", () => {
  it("writes the phase of the branch and the origin of it in words", async () => {
    // It proves that what the visitor has to know is written down: the revision of the branch is a sentence and
    // the origin of the branch says in words that it was created and not only that it wears a colour.
    const user = userEvent.setup();
    renderPage();

    await openTheBranch(user);

    const status = screen.getByRole("status");
    expect(status.textContent ?? "").toMatch(/the branch is at revision 0/i);
    expect(screen.getByText(/this branch was created for this visit/i)).toBeInTheDocument();
    expect(screen.getByText("mode: visitor_sandbox")).toBeInTheDocument();
  });

  it("writes the state of every event of the history in words", async () => {
    // It proves that the mark of an undone event is a word and not a tint of the background.
    const user = userEvent.setup();
    renderPage();

    await openTheBranch(user);
    await user.click(screen.getByRole("button", { name: /read the history/i }));
    await screen.findByRole("table", { name: /the log of the branch/i });

    expect(screen.getByText("Not undone")).toBeInTheDocument();
    expect(screen.getByText("Undone")).toBeInTheDocument();
  });
});
