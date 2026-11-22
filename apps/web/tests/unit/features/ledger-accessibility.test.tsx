/**
 * The regression guard of the accessibility of the ledger of the recorded demo.
 *
 * Why this file exists: the rules of the browser of ADR-045 are part of the contract of the
 * milestone and not a polish of the end of it. Every rule of that list has to be able to fail,
 * and this file is where the rules live as cases:
 *
 * 1. the table has a caption, which is its accessible name, and a header for every column;
 * 2. the `aria-current` sits on the ROW that is open and on no cell of it;
 * 3. the state is never only a colour: the open row carries the words "Open" and the movement the
 *    run read carries the words "Read by the run";
 * 4. the controls of the pagination are never `disabled`, and the ones that would do nothing
 *    carry `aria-disabled` and a reason they point at;
 * 5. the outline of the headings never skips a level, from the `h1` of the route to the `h5` of the
 *    detail of a movement;
 * 6. the state of the visitor never reaches the URL, nor the storage of the browser.
 *
 * Every case runs with no key and no network: the artifact of the case is a literal, and the
 * browser of the case is the one of the test environment.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { LedgerPanel } from "@/features/ledger/LedgerPanel";
import type { LedgerArtifact, LedgerRow } from "@/lib/api/schemas";

/**
 * Builds a movement of the ledger, with the fields the artifact carries.
 *
 * Why the movements are built and not written: the case of the pagination needs more movements
 * than a page holds, and writing them one by one would be noise.
 */
function movementOf(index: number): LedgerRow {
  return {
    kind: "transaction",
    id: `TX-${String(index).padStart(4, "0")}`,
    at: "2026-10-15T09:12:00Z",
    amount: "100.00",
    currency: "EUR",
    status: "refunded",
  };
}

/**
 * The artifact of one account with many movements, as the pagination needs a second page.
 *
 * Why the page of the case holds two movements and not fifty: the artifact of the site declares a
 * page of fifty rows, and the case declares the page it wants to prove.
 */
const ARTIFACT: LedgerArtifact = {
  schema_version: "1",
  scenario: "S01",
  snapshot_sha256: "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
  page_size: 2,
  accounts: [
    {
      id: "C-0412",
      kind: "customer",
      name: "Mariana Albuquerque Costa",
      rows: [movementOf(1), movementOf(2), movementOf(3)],
      reads: [
        {
          evidence_id: "sql:1",
          seq: 19,
          tool: "query_ledger",
          sql: "SELECT * FROM (SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-0001' ORDER BY applied_at) LIMIT 50",
          columns: ["kind", "applied_rate", "applied_at"],
          row_count: 2,
          truncated: false,
          records: ["TX-0001"],
          rows: [
            { kind: "charge", applied_rate: "5.6679", applied_at: "2026-10-15T09:12:04Z" },
            { kind: "refund", applied_rate: "5.4931", applied_at: "2026-10-20T14:30:00Z" },
          ],
        },
      ],
    },
  ],
};

afterEach(() => {
  // The address of the case is put back where it was, so that a case that reads it never reaches
  // the case that runs after it.
  window.history.replaceState(null, "", "/");
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe("the accessibility of the ledger of the recorded demo", () => {
  it("gives the table a caption and a header for every column", () => {
    // It proves that the table is named by its caption and that every column says what it holds.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    const table = screen.getByRole("table", { name: "The movements of the account C-0412" });
    const headers = within(table).getAllByRole("columnheader");

    expect(headers.map((header) => header.textContent)).toEqual([
      "The identifier of the movement",
      "The kind of the movement",
      "The moment of the movement",
      "The amount the ledger carries",
      "The state of the movement",
      "The reading of the run",
      "The state of the visit",
    ]);
  });

  it("puts the aria-current on the row that is open and on no cell of it", async () => {
    // It proves that the place the visitor stands at is a property of the row, and not of the cell
    // that happens to hold the name of the movement.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    await userEvent.setup().click(screen.getByRole("button", { name: "TX-0001" }));

    const row = screen.getByRole("rowheader", { name: "TX-0001" }).closest("tr");
    expect(row).not.toBeNull();
    expect(row).toHaveAttribute("aria-current", "true");

    // No cell of the row carries the attribute.
    for (const cell of within(row as HTMLElement).getAllByRole("cell")) {
      expect(cell).not.toHaveAttribute("aria-current");
    }
    expect(within(row as HTMLElement).getByRole("rowheader")).not.toHaveAttribute("aria-current");
  });

  it("never carries a state in a colour alone", async () => {
    // It proves that the words of the state are on the screen: the open row says that it is open
    // and the movement the run read says that the run read it.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    await userEvent.setup().click(screen.getByRole("button", { name: "TX-0001" }));

    const row = screen.getByRole("rowheader", { name: "TX-0001" }).closest("tr") as HTMLElement;
    expect(within(row).getByText("Open")).toBeInTheDocument();
    expect(within(row).getByText("Read by the run")).toBeInTheDocument();

    // The account that is chosen carries the state of the pressed button.
    const account = screen.getByRole("button", { name: "C-0412, Mariana Albuquerque Costa" });
    expect(account).toHaveAttribute("aria-pressed", "true");
  });

  it("never disables a control of the pagination and gives a reason to the ones that do nothing", () => {
    // It proves that the control that would do nothing says so with aria-disabled and a sentence a
    // reader can hear, and that no control of the panel carries the attribute disabled: a focus
    // that is dropped on the body of the document sends the next Tab back to the top of the page.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    const previous = screen.getByRole("button", { name: "Previous page" });
    const next = screen.getByRole("button", { name: "Next page" });

    expect(previous).not.toHaveAttribute("disabled");
    expect(next).not.toHaveAttribute("disabled");

    expect(previous).toHaveAttribute("aria-disabled", "true");
    const reason = document.getElementById(previous.getAttribute("aria-describedby") ?? "");
    expect(reason).not.toBeNull();
    expect(reason?.textContent).not.toBe("");

    // The control of the next page works, so it carries no reason.
    expect(next).not.toHaveAttribute("aria-disabled");
  });

  it("keeps the page of the movements inside the page the artifact declares", async () => {
    // It proves that the table never holds more rows than the page of the artifact, and that the
    // visitor moves between the pages with the control of the pagination.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    const table = screen.getByRole("table", { name: "The movements of the account C-0412" });
    expect(within(table).getAllByRole("rowheader")).toHaveLength(2);
    expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();

    await userEvent.setup().click(screen.getByRole("button", { name: "Next page" }));

    const second = screen.getByRole("table", { name: "The movements of the account C-0412" });
    expect(within(second).getAllByRole("rowheader")).toHaveLength(1);
    expect(within(second).getByRole("rowheader", { name: "TX-0003" })).toBeInTheDocument();
    expect(screen.getByText("Page 2 of 2")).toBeInTheDocument();
  });

  it("never skips a level in the outline of the headings", async () => {
    // It proves the shape of the outline: the route carries the h1 and the h2 of the scenario, the
    // tab carries the h3, the panel of the ledger carries the h4 and the detail of a movement
    // carries the h5.
    const { container } = render(
      <div>
        <h1>The recorded run of the scenario</h1>
        <h2>The scenario S01</h2>
        <h3>The ledger of the recording</h3>
        <LedgerPanel ledger={ARTIFACT} error={null} />
      </div>,
    );

    await userEvent.setup().click(screen.getByRole("button", { name: "TX-0001" }));

    const headings = Array.from(container.querySelectorAll("h1, h2, h3, h4, h5, h6"));
    expect(headings.map((heading) => heading.tagName)).toEqual(["H1", "H2", "H3", "H4", "H5"]);
  });

  it("never lets the state of the visitor reach the URL or the storage of the browser", async () => {
    // It proves that the account that is chosen and the row that is open live in the memory of the
    // panel and in nothing else.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    await userEvent.setup().click(screen.getByRole("button", { name: "TX-0001" }));

    expect(window.location.search).toBe("");
    expect(window.location.href).not.toContain("TX-0001");
    expect(window.location.href).not.toContain("C-0412");
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });
});
