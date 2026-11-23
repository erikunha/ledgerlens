/**
 * The panel of the ledger of the recorded demo.
 *
 * Why this file exists: the home page of the site promises the ledger rows the run read, and
 * ADR-045 turned that promise into an artifact of the site. ADR-049 turned the promise of the
 * rows into a promise the visitor can use: the movements of the account may be sorted and
 * filtered. The panel is the place where the visitor reads that artifact: the switcher of the
 * accounts, the controls of the order and of the filter, the table of the movements and the detail
 * of the movement that is open.
 *
 * Why the panel owns the state of the visitor: the account that is chosen, the row that is open,
 * the page that is on the screen, the sort and the filter live in the memory of the panel and in
 * nothing else. None of them goes in the URL, and none of them is written in the storage of the
 * browser: the query string of the route carries the tab and the speed and nothing else (ADR-043,
 * ADR-045, ADR-049).
 *
 * Why the panel shows the reason and nothing else when the artifact is not available: a half
 * drawn ledger is worse than no ledger, because a reader cannot tell which parts of it are true.
 *
 * Why the panel never reads the network: the artifact of the scenario is read by the library of
 * the artifacts, and the panel draws what it is given.
 */

"use client";

import { useState } from "react";
import type { ReactElement } from "react";

import { AccountSwitcher } from "@/features/ledger/AccountSwitcher";
import { LedgerRowDetail } from "@/features/ledger/LedgerRowDetail";
import { LedgerAccountContext, LedgerTable, LedgerViewContext } from "@/features/ledger/LedgerTable";
import type { LedgerArtifact } from "@/lib/api/schemas";
import type { BundleIntegrity } from "@/lib/api/replay";
import {
  LEDGER_UNAVAILABLE,
  filterLedgerRows,
  ledgerRowsHaveTheSameOrder,
  selectLedgerAccounts,
  selectLedgerReads,
  selectLedgerRows,
  sortLedgerRows,
} from "@/lib/replay/ledger";
import type { LedgerFilter, LedgerSort } from "@/lib/replay/ledger";

import "./ledger.css";

/** The identifier of the heading of the panel, so that the section names itself. */
const PANEL_HEADING_ID = "ledgerlens-ledger-panel-heading";

/**
 * The number of rows of a page, when the artifact declares no page.
 *
 * Why the number is here: the artifact of the site declares a page of fifty rows, and a panel
 * that divided by nothing would show no movement at all.
 */
const DEFAULT_PAGE_SIZE = 50;

/**
 * The filter of the movements, when the visitor asked for nothing.
 *
 * Why the filter starts empty: the default order of the movements is the order the artifact
 * declares, and the default filter keeps every movement.
 */
const NO_FILTER: LedgerFilter = { text: "", kind: null, status: null };

/**
 * The props of the panel of the ledger.
 *
 * Why the panel takes the artifact and the reason and nothing else: the panel reads the artifact
 * through the library of the ledger and it never reaches for the network by itself.
 */
export interface LedgerPanelProps {
  /** The artifact of the ledger of the scenario, when the site published one. */
  readonly ledger: LedgerArtifact | null;
  /** The reason the artifact could not be read, when it could not be read. */
  readonly error: string | null;
  /**
   * Whether the integrity of the file of the ledger was really checked.
   *
   * Why the panel carries it: the panel never shows an artifact as verified when it was not, and the
   * absence of the Web Crypto is a check that could not be made. The sentence that says so is drawn
   * by the panel and by nobody else, so that no other place can forget it.
   */
  readonly integrity?: BundleIntegrity | null;
}

/**
 * Writes the sentence that says how many rows the recording read.
 *
 * Why the number is a count of rows and not a sum of money: the browser never sums the column of
 * the amounts, and the count is the number of rows the reads of the recording declare.
 */
function rowsReadSentence(count: number): string {
  return count === 1
    ? "The recording read 1 row of the ledger."
    : `The recording read ${count} rows of the ledger.`;
}

/**
 * The panel of the ledger of the recorded demo.
 *
 * The panel draws the switcher of the accounts, the controls of the order and of the filter, the
 * table of the movements of the account that is chosen and the detail of the movement that is
 * open. It never reads the network and it never calculates a value of money.
 */
export function LedgerPanel({ ledger, error, integrity }: LedgerPanelProps): ReactElement {
  // The state of the visitor lives here and in nowhere else: the account that is chosen, the row
  // that is open, the page that is on the screen, the order and the filter.
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);
  const [openRowId, setOpenRowId] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState<LedgerSort | null>(null);
  const [filter, setFilter] = useState<LedgerFilter>(NO_FILTER);

  if (ledger === null) {
    return <p className="ll-ledger-unavailable">{error ?? LEDGER_UNAVAILABLE}</p>;
  }

  const accounts = selectLedgerAccounts(ledger);
  // The account that is chosen falls back to the first one of the artifact, so that an artifact
  // that changes never leaves the panel without an account.
  const account = accounts.find((candidate) => candidate.id === selectedAccountId) ?? accounts[0] ?? null;

  if (account === null) {
    return <p className="ll-ledger-unavailable">{error ?? LEDGER_UNAVAILABLE}</p>;
  }

  const artifactRows = selectLedgerRows(ledger, account.id);
  const reads = selectLedgerReads(ledger, account.id);
  const openRow = artifactRows.find((row) => row.id === openRowId) ?? null;
  const pageSize = ledger.page_size > 0 ? ledger.page_size : DEFAULT_PAGE_SIZE;

  // The rows the recording read are counted, because the panel has to say in words how many rows
  // the run read. It is a count of rows and never a sum of money.
  const rowsRead = reads.reduce((total, read) => total + read.row_count, 0);

  // The rows of the artifact come first, and the filter and the order of the visitor come
  // afterwards: the filter keeps the rows that carry what the visitor asked for, and the order
  // moves the rows that are left. Both rules live in the library of the ledger.
  const filteredRows = filterLedgerRows(artifactRows, filter);
  const rows = sort === null ? filteredRows : sortLedgerRows(filteredRows, sort);
  const sortedByTheVisitor = !ledgerRowsHaveTheSameOrder(filteredRows, rows);

  /** Chooses another account: the open row and the page of the previous account are left behind. */
  function selectAccount(accountId: string): void {
    setSelectedAccountId(accountId);
    setOpenRowId(null);
    setPage(0);
  }

  /** Changes the filter of the visitor: the page goes back to the first one. */
  function changeFilter(nextFilter: LedgerFilter): void {
    setFilter(nextFilter);
    setPage(0);
  }

  return (
    <section aria-labelledby={PANEL_HEADING_ID} className="ll-ledger-panel">
      <h4 id={PANEL_HEADING_ID} className="text-base font-semibold">
        The ledger of the account {account.id}
      </h4>

      <p className="ll-ledger-note">{rowsReadSentence(rowsRead)}</p>

      {integrity === "unknown" ? (
        <p className="ll-ledger-note">The integrity of the file of the ledger was not checked.</p>
      ) : null}

      <AccountSwitcher accounts={accounts} selectedAccountId={account.id} onSelectAccount={selectAccount} />

      <LedgerAccountContext.Provider value={{ accountId: account.id }}>
        <LedgerViewContext.Provider
          value={{
            artifactRows,
            sort,
            filter,
            onSortChange: setSort,
            onFilterChange: changeFilter,
            sortedByTheVisitor,
          }}
        >
          <LedgerTable
            rows={rows}
            reads={reads}
            openRowId={openRowId}
            onOpenRow={setOpenRowId}
            pageSize={pageSize}
            page={page}
            onPageChange={setPage}
          />
        </LedgerViewContext.Provider>
      </LedgerAccountContext.Provider>

      {openRow === null ? null : <LedgerRowDetail row={openRow} reads={reads} />}
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the panel at once. */
export const __all__ = ["LedgerPanelProps", "LedgerPanel"] as const;
