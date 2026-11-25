/**
 * The test of the detail of a read of the ledger.
 *
 * Why this test exists: the site publishes two catalogs and each one shows the reads the recording made. A read made
 * with a statement shows the statement; a read made with the tool that returns one record has no statement at all,
 * because the tool never wrote one. An empty block of code would read as a broken site, and the panel has to say
 * what the read is (ADR-075).
 *
 * Every case runs with no key and no network: the reads are given to the component directly.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LedgerRowDetail } from "@/features/ledger/LedgerRowDetail";
import type { LedgerRead, LedgerRow } from "@/lib/api/schemas";

/** The movement that is open, the one the detail shows. */
const ROW: LedgerRow = {
  amount: "100.00",
  at: "2026-10-15T09:12:00Z",
  currency: "EUR",
  id: "TX-2048",
  kind: "transaction",
  status: "refunded",
};

/** A read made with a statement, the shape the sandbox catalog publishes. */
const READ_WITH_STATEMENT: LedgerRead = {
  columns: ["kind", "applied_rate"],
  evidence_id: "sql:1",
  records: ["TX-2048"],
  row_count: 1,
  rows: [{ kind: "charge", applied_rate: "5.6679" }],
  seq: 19,
  sql: "SELECT kind, applied_rate FROM fx_applied WHERE transaction_id = 'TX-2048'",
  tool: "query_ledger",
  truncated: false,
};

/** A read made with the tool that returns one record, the shape the real catalog publishes. */
const READ_OF_A_RECORD: LedgerRead = {
  columns: ["collection", "id"],
  evidence_id: "api:1",
  records: ["TX-2048"],
  row_count: 1,
  rows: [{ collection: "transaction", id: "TX-2048" }],
  seq: 17,
  sql: "",
  tool: "get_ledger_record",
  truncated: false,
};

describe("the detail of a read of the ledger", () => {
  it("shows the statement of a read that has one", () => {
    // It proves that the reader sees the statement that fetched the rows.
    render(<LedgerRowDetail row={ROW} reads={[READ_WITH_STATEMENT]} />);

    expect(screen.getByText(/SELECT kind, applied_rate/)).toBeTruthy();
  });

  it("shows no empty block of code for a read that had no statement", () => {
    // It proves that the panel does not show an empty block of code, which would read as a broken site.
    const { container } = render(<LedgerRowDetail row={ROW} reads={[READ_OF_A_RECORD]} />);

    expect(container.querySelector(".ll-ledger-statement")).toBeNull();
  });

  it("names the tool that made the read and the rows it returned", () => {
    // It proves that the reader knows which tool read the ledger and what it returned.
    render(<LedgerRowDetail row={ROW} reads={[READ_OF_A_RECORD]} />);

    expect(screen.getByText(/the tool get_ledger_record/i)).toBeTruthy();
    // The identifier of the movement is on the panel and in the row of the read, so the panel shows it twice.
    expect(screen.getAllByText("TX-2048").length).toBeGreaterThan(0);
  });
});
