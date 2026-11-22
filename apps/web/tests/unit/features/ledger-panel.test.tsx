/**
 * The test of the panel of the ledger of the recorded demo.
 *
 * Why this test exists: the home page of the site promises the ledger rows the run read, and
 * ADR-045 turned that promise into an artifact of the site. The panel is the place where the
 * visitor reads that artifact, and it has to be honest about it in the same way the rest of the
 * recorded demo is honest: the amount of a movement is the decimal text the artifact carries, a
 * movement the run read carries the words that say so, and an artifact that could not be read
 * shows the reason and nothing else.
 *
 * The cases below are the ones ADR-045 asks of this set:
 *
 * 1. the panel shows the movements of the artifact with the amount and the currency of the artifact;
 * 2. it marks the movement the run read with the words "Read by the run" and leaves the other one
 *    unmarked;
 * 3. it opens the detail of the row the visitor opens and closes it;
 * 4. the detail shows the reads that name the row, and the rows of the read with the text of the
 *    artifact, rate included and without a currency;
 * 5. the detail says in words that the recording read no record of a row that no read names;
 * 6. the switcher shows the account of the artifact and says in words that the recording read the
 *    ledger of one account;
 * 7. the panel says in words how many rows the recording read;
 * 8. the panel shows the reason when the artifact is not available, and it shows nothing else.
 *
 * Every case runs with no key and no network: the artifact of the case is the artifact the
 * repository publishes, written here as a literal so that the case never depends on a file that
 * the export may move.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { LedgerPanel } from "@/features/ledger/LedgerPanel";
import type { LedgerArtifact } from "@/lib/api/schemas";

/**
 * The artifact of the ledger of the scenario S01, as `site/replay/s01/ledger.json` holds it.
 *
 * Why the artifact is a literal here: the case proves the rules of the panel, and a rule that
 * depends on a file the export may rewrite is a rule the case cannot prove twice.
 */
const ARTIFACT: LedgerArtifact = {
  schema_version: "1",
  scenario: "S01",
  snapshot_sha256: "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
  page_size: 50,
  accounts: [
    {
      id: "C-0412",
      kind: "customer",
      name: "Mariana Albuquerque Costa",
      rows: [
        {
          kind: "transaction",
          id: "TX-2048",
          at: "2026-10-15T09:12:00Z",
          amount: "100.00",
          currency: "EUR",
          status: "refunded",
        },
        {
          kind: "refund",
          id: "R-0731",
          at: "2026-10-20T14:05:00Z",
          amount: "549.31",
          currency: "BRL",
          status: "paid",
        },
      ],
      reads: [
        {
          evidence_id: "sql:1",
          seq: 19,
          tool: "query_ledger",
          sql: "SELECT * FROM (SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at) LIMIT 50",
          columns: ["kind", "applied_rate", "applied_at"],
          row_count: 2,
          truncated: false,
          records: ["TX-2048"],
          rows: [
            { kind: "charge", applied_rate: "5.6679", applied_at: "2026-10-15T09:12:04Z" },
            { kind: "refund", applied_rate: "5.4931", applied_at: "2026-10-20T14:30:00Z" },
          ],
        },
      ],
    },
  ],
};

/**
 * Finds the row of a movement in the table of the panel.
 *
 * Why the helper exists: the cases ask about ONE row of the table, and the row of a movement is
 * the row that carries its identifier as its row header.
 */
function rowOf(rowId: string): HTMLElement {
  const header = screen.getByRole("rowheader", { name: rowId });
  const row = header.closest("tr");
  if (row === null) {
    throw new Error(`the row of the movement ${rowId} was not found`);
  }
  return row as HTMLElement;
}

describe("the panel of the ledger of the recorded demo", () => {
  it("shows the movements of the artifact with the amount and the currency of the artifact", () => {
    // It proves that the panel shows the movements of the account of the artifact, and that the
    // money of the table is the decimal text of the artifact with the currency of the artifact.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    const table = screen.getByRole("table", { name: "The movements of the account C-0412" });
    expect(within(table).getByRole("rowheader", { name: "TX-2048" })).toBeInTheDocument();
    expect(within(table).getByRole("rowheader", { name: "R-0731" })).toBeInTheDocument();

    expect(within(rowOf("TX-2048")).getByText("EUR 100.00")).toBeInTheDocument();
    expect(within(rowOf("R-0731")).getByText("BRL 549.31")).toBeInTheDocument();
  });

  it("never shows a total of the column of the amounts", () => {
    // It proves that the browser never sums the column of the movements: no total row, no total in
    // the caption and no total in the detail, because a total is a number the browser calculated
    // and no artifact of the site carries one.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    expect(screen.queryByText(/total/i)).toBeNull();
    expect(screen.queryByText("649.31")).toBeNull();
  });

  it("marks the movement the run read with the words Read by the run and leaves the other one unmarked", () => {
    // It proves that the state of the reading is never only a colour: the movement the run read
    // carries the words, and the movement the run did not read carries no mark at all.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    expect(within(rowOf("TX-2048")).getByText("Read by the run")).toBeInTheDocument();
    expect(within(rowOf("R-0731")).queryByText("Read by the run")).toBeNull();
  });

  it("opens the detail of the row the visitor opens and closes it", async () => {
    // It proves that the visitor opens the detail of a movement with the button of the row and
    // closes it with the same button.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    const button = screen.getByRole("button", { name: "TX-2048" });
    expect(screen.queryByRole("heading", { name: "The movement TX-2048" })).toBeNull();

    await userEvent.setup().click(button);
    expect(screen.getByRole("heading", { name: "The movement TX-2048" })).toBeInTheDocument();

    await userEvent.setup().click(button);
    expect(screen.queryByRole("heading", { name: "The movement TX-2048" })).toBeNull();
  });

  it("shows the reads that name the row in the detail of the movement", async () => {
    // It proves that the detail shows the reads of the recording that name the movement, with the
    // citation, the sequence number of the event, the statement and the rows of the read.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    await userEvent.setup().click(screen.getByRole("button", { name: "TX-2048" }));

    const detail = screen.getByRole("region", { name: "The movement TX-2048" });
    // The citation of the read is named by the sentence of the read and by the caption of the
    // table of its rows, so the case looks for the text and not for one element.
    expect(within(detail).getAllByText(/sql:1/).length).toBeGreaterThan(0);
    expect(within(detail).getByText(/19/)).toBeInTheDocument();
    expect(within(detail).getByText(/query_ledger/)).toBeInTheDocument();
    expect(within(detail).getByText(/SELECT \* FROM/)).toBeInTheDocument();

    // The rows of the read are the rows the run read, and a rate is not money: it carries no
    // currency and it is written with the text of the artifact.
    const read = within(detail).getByRole("table", { name: "The rows the read sql:1 returned" });
    expect(within(read).getByText("5.6679")).toBeInTheDocument();
    expect(within(read).getByText("5.4931")).toBeInTheDocument();
    expect(within(read).queryByText(/5\.6679\s*(EUR|BRL|USD)/)).toBeNull();
  });

  it("says in words that the recording read no record of a movement that no read names", async () => {
    // It proves that the detail of a movement the run did not read says so in words, and that it
    // shows no read that does not name it.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    await userEvent.setup().click(screen.getByRole("button", { name: "R-0731" }));

    const detail = screen.getByRole("region", { name: "The movement R-0731" });
    expect(within(detail).getByText("The recording read no record of this movement.")).toBeInTheDocument();
    expect(within(detail).queryByText(/sql:1/)).toBeNull();
  });

  it("shows the account of the artifact and says in words that the recording read one account", () => {
    // It proves that the switcher shows the account of the artifact and that it says in words that
    // the recording read the ledger of one account, because a control that changes shape when the
    // recording reads many accounts is a control that breaks the visit.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    const group = screen.getByRole("group", { name: "The accounts of the recording" });
    const account = within(group).getByRole("button", { name: "C-0412, Mariana Albuquerque Costa" });
    expect(account).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("The recording read the ledger of one account.")).toBeInTheDocument();
  });

  it("says in words how many rows the recording read", () => {
    // It proves that the panel says how many rows the recording read, in words and not in a
    // number that the browser would have calculated out of the money of the ledger.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    expect(screen.getByText("The recording read 2 rows of the ledger.")).toBeInTheDocument();
  });

  it("switches the account when the visitor picks another one", async () => {
    // It proves that the switcher changes the movements on the screen, and that the table names
    // the account that is chosen. The state of the visit stays in the memory of the panel.
    const artifact: LedgerArtifact = {
      ...ARTIFACT,
      accounts: [
        ...ARTIFACT.accounts,
        {
          id: "M-17",
          kind: "merchant",
          name: "Mercado Livre",
          rows: [
            {
              kind: "transaction",
              id: "TX-3000",
              at: "2026-10-16T10:00:00Z",
              amount: "12.34",
              currency: "BRL",
              status: "paid",
            },
          ],
          reads: [],
        },
      ],
    };

    render(<LedgerPanel ledger={artifact} error={null} />);

    const merchant = screen.getByRole("button", { name: "M-17, Mercado Livre" });
    expect(merchant).toHaveAttribute("aria-pressed", "false");

    await userEvent.setup().click(merchant);

    expect(merchant).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("table", { name: "The movements of the account M-17" })).toBeInTheDocument();
    expect(screen.getByText("BRL 12.34")).toBeInTheDocument();

    // The sentence of the account of the recording is said when the artifact holds one account,
    // and it is not said when it holds many.
    expect(screen.queryByText("The recording read the ledger of one account.")).toBeNull();
  });

  it("shows the reason when the artifact is not available and shows nothing else", () => {
    // It proves that a panel without an artifact shows the reason and nothing else: no table, no
    // switcher and no detail, because a half drawn ledger is worse than no ledger.
    render(<LedgerPanel ledger={null} error="the file of the ledger could not be read" />);

    expect(screen.getByText("the file of the ledger could not be read")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByRole("group", { name: "The accounts of the recording" })).toBeNull();
    expect(screen.queryByRole("heading")).toBeNull();
  });

  it("draws the six fields of the movement in the detail, one by one", async () => {
    // It proves that the detail draws every field of the movement with the name the artifact gives
    // it, and that a field that the detail left out would be a field that the visitor never sees.
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    await userEvent.setup().click(screen.getByRole("button", { name: "TX-2048" }));

    const detail = screen.getByRole("region", { name: "The movement TX-2048" });
    const fields: Array<[string, string]> = [
      ["The kind of the movement", "transaction"],
      ["The identifier of the movement", "TX-2048"],
      ["The moment of the movement", "2026-10-15T09:12:00Z"],
      ["The amount the ledger carries", "EUR 100.00"],
      ["The currency of the movement", "EUR"],
      ["The state of the movement", "refunded"],
    ];
    for (const [name, value] of fields) {
      expect(within(detail).getByText(name)).toBeInTheDocument();
      expect(within(detail).getByText(value)).toBeInTheDocument();
    }
  });

  it("names the header of every column of a read in words", async () => {
    // It proves that the header of a column of a read says what the column holds, the way the
    // header of the duration says "the duration the capture measured" and not "duration".
    render(<LedgerPanel ledger={ARTIFACT} error={null} />);

    await userEvent.setup().click(screen.getByRole("button", { name: "TX-2048" }));

    const read = screen.getByRole("table", { name: "The rows the read sql:1 returned" });
    expect(within(read).getByRole("columnheader", { name: "The kind of the row the read returned" })).toBeInTheDocument();
    expect(within(read).getByRole("columnheader", { name: "The rate the read applied" })).toBeInTheDocument();
    expect(within(read).getByRole("columnheader", { name: "The moment the rate was applied" })).toBeInTheDocument();
    expect(within(read).queryByRole("columnheader", { name: "applied_rate" })).toBeNull();
  });

  it("says out loud that the integrity of the file of the ledger was not checked", () => {
    // It proves that the panel never shows an artifact as verified when it was not: a browser that
    // offered no Web Crypto leaves the integrity unknown, and the panel says so in words.
    render(<LedgerPanel ledger={ARTIFACT} error={null} integrity="unknown" />);

    expect(screen.getByText("The integrity of the file of the ledger was not checked.")).toBeInTheDocument();
  });

  it("says nothing about the integrity when the file of the ledger was really checked", () => {
    // It proves that the sentence is not noise: a file that was really checked needs no warning.
    render(<LedgerPanel ledger={ARTIFACT} error={null} integrity="checked" />);

    expect(screen.queryByText(/integrity/i)).toBeNull();
  });
});
