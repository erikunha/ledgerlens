/**
 * The test of the selectors of the ledger of the recorded demo.
 *
 * Why this test exists: the artifact of the ledger is published by the site, and the interface
 * reads it through these selectors and never through a computation of its own. The selectors have
 * to keep the order of the artifact and the order of the recording, because a ledger whose rows
 * move around is a ledger that says something the artifact does not say.
 *
 * The cases below are the ones ADR-045 asks of this set:
 *
 * 1. the accounts come from the artifact and there is one of them;
 * 2. the rows of the chosen account keep the order of the artifact;
 * 3. the reads of the chosen account keep the order of the recording;
 * 4. a read names a movement exactly when the identifier of the movement is one of the records of
 *    the read;
 * 5. the pagination returns one page of at most `page_size` rows and never a page that is out of
 *    range.
 *
 * Every case runs with no key and no network: the artifact of the case is a literal, so that the
 * case never depends on a file that the export may rewrite.
 */

import { describe, expect, it } from "vitest";

import type { LedgerArtifact, LedgerRead } from "@/lib/api/schemas";
import {
  LEDGER_UNAVAILABLE,
  ledgerRowIsRead,
  paginateLedgerRows,
  selectLedgerAccounts,
  selectLedgerReads,
  selectLedgerRows,
  selectReadsForRecord,
} from "@/lib/replay/ledger";

/**
 * The artifact of the ledger of the scenario S01, as `site/replay/s01/ledger.json` holds it.
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
 * A read that names a second movement, so that the cases can prove that the order of the reads is
 * the order of the recording and not the order of the identifiers.
 */
const SECOND_READ: LedgerRead = {
  evidence_id: "sql:2",
  seq: 24,
  tool: "query_ledger",
  sql: "SELECT kind FROM fx_applied WHERE transaction_id = 'TX-2049'",
  columns: ["kind"],
  row_count: 1,
  truncated: false,
  records: ["R-0731"],
  rows: [{ kind: "refund" }],
};

describe("the selectors of the ledger of the recorded demo", () => {
  it("reads the accounts from the artifact and there is one of them", () => {
    // It proves that the switcher of the accounts reads the list of the artifact and nothing else,
    // and that a recording that read one account publishes one account.
    const accounts = selectLedgerAccounts(ARTIFACT);

    expect(accounts).toHaveLength(1);
    expect(accounts[0]?.id).toBe("C-0412");
    expect(accounts[0]?.kind).toBe("customer");
  });

  it("keeps the order of the artifact in the rows of the chosen account", () => {
    // It proves that the table shows the movements in the order the artifact declares, and that the
    // money of a movement is the decimal text of the artifact and never a number of the browser.
    const rows = selectLedgerRows(ARTIFACT, "C-0412");

    expect(rows.map((row) => row.id)).toEqual(["TX-2048", "R-0731"]);
    expect(rows[0]?.amount).toBe("100.00");
    expect(rows[1]?.amount).toBe("549.31");
  });

  it("returns no rows for an account the artifact does not publish", () => {
    // It proves that an account that the artifact does not publish gives no row and no read, and
    // that the panel never shows the movements of another account by accident.
    expect(selectLedgerRows(ARTIFACT, "C-9999")).toEqual([]);
    expect(selectLedgerReads(ARTIFACT, "C-9999")).toEqual([]);
  });

  it("keeps the order of the recording in the reads of the chosen account", () => {
    // It proves that the reads keep the order the recording made them in, and not the order of
    // their citations.
    const account = ARTIFACT.accounts[0];
    const reads = selectLedgerReads(
      { ...ARTIFACT, accounts: [{ ...(account as LedgerArtifact["accounts"][number]), reads: [SECOND_READ, ...(account?.reads ?? [])] }] },
      "C-0412",
    );

    expect(reads.map((read) => read.evidence_id)).toEqual(["sql:2", "sql:1"]);
  });

  it("names a movement exactly when the identifier of the movement is one of the records of the read", () => {
    // It proves that the mark of the table is exact: the movement the run read carries the words
    // that say so, and the movement the run did not read carries no mark at all.
    const reads = selectLedgerReads(ARTIFACT, "C-0412");

    expect(ledgerRowIsRead(reads, "TX-2048")).toBe(true);
    expect(ledgerRowIsRead(reads, "R-0731")).toBe(false);
  });

  it("returns only the reads that name a movement", () => {
    // It proves that the detail of a movement shows the reads that name it and nothing else.
    const reads = selectLedgerReads(ARTIFACT, "C-0412");

    expect(selectReadsForRecord(reads, "TX-2048").map((read) => read.evidence_id)).toEqual(["sql:1"]);
    expect(selectReadsForRecord(reads, "R-0731")).toEqual([]);
  });

  it("returns one page of at most page_size rows", () => {
    // It proves that the DOM of the table never holds more than a page of rows, because a DOM of a
    // thousand rows is a DOM that a reader with a keyboard has to walk through row by row.
    const rows = selectLedgerRows(ARTIFACT, "C-0412");

    expect(paginateLedgerRows(rows, 0, 1)).toHaveLength(1);
    expect(paginateLedgerRows(rows, 1, 1)).toHaveLength(1);
    expect(paginateLedgerRows(rows, 0, 50)).toHaveLength(2);
  });

  it("never returns a page that is out of range", () => {
    // It proves that a page beyond the last one is empty and never a wrapped page, so that the
    // visitor never sees the first rows again under a number that says otherwise.
    const rows = selectLedgerRows(ARTIFACT, "C-0412");

    expect(paginateLedgerRows(rows, 5, 1)).toEqual([]);
    expect(paginateLedgerRows(rows, -1, 1)).toEqual([]);
  });

  it("says in words that the ledger is not available", () => {
    // It proves that the panel has a sentence to show when the site published no file of the
    // ledger, and that the sentence is a sentence and not a code.
    expect(LEDGER_UNAVAILABLE).toMatch(/ledger/i);
    expect(LEDGER_UNAVAILABLE.length).toBeGreaterThan(0);
  });
});
