/**
 * The panel of the ledger of the recorded demo.
 *
 * Why this file exists: the home page of the site promises the ledger rows the run read, and
 * ADR-045 turned that promise into an artifact of the site. The panel is the place where the
 * visitor reads that artifact: the switcher of the accounts, the table of the movements and the
 * detail of the movement that is open.
 *
 * Why the panel owns the state of the visitor: the account that is chosen and the row that is
 * open live in the memory of the panel and in nothing else. Neither of them goes in the URL, and
 * neither of them is written in the storage of the browser: the query string of the route carries
 * the tab and the speed and nothing else (ADR-043, ADR-045).
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
import { LedgerAccountContext, LedgerTable } from "@/features/ledger/LedgerTable";
import type { LedgerArtifact } from "@/lib/api/schemas";
import type { BundleIntegrity } from "@/lib/api/replay";
import {
  LEDGER_UNAVAILABLE,
  selectLedgerAccounts,
  selectLedgerReads,
  selectLedgerRows,
} from "@/lib/replay/ledger";

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
 * The panel draws the switcher of the accounts, the table of the movements of the account that is
 * chosen and the detail of the movement that is open. It never reads the network and it never
 * calculates a value of money.
 */
export function LedgerPanel({ ledger, error, integrity }: LedgerPanelProps): ReactElement {
  // The state of the visitor lives here and in nowhere else: the account that is chosen, the row
  // that is open and the page that is on the screen.
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);
  const [openRowId, setOpenRowId] = useState<string | null>(null);
  const [page, setPage] = useState(0);

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

  const rows = selectLedgerRows(ledger, account.id);
  const reads = selectLedgerReads(ledger, account.id);
  const openRow = rows.find((row) => row.id === openRowId) ?? null;
  const pageSize = ledger.page_size > 0 ? ledger.page_size : DEFAULT_PAGE_SIZE;

  // The rows the recording read are counted, because the panel has to say in words how many rows
  // the run read. It is a count of rows and never a sum of money.
  const rowsRead = reads.reduce((total, read) => total + read.row_count, 0);

  /** Chooses another account: the open row and the page of the previous account are left behind. */
  function selectAccount(accountId: string): void {
    setSelectedAccountId(accountId);
    setOpenRowId(null);
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
        <LedgerTable
          rows={rows}
          reads={reads}
          openRowId={openRowId}
          onOpenRow={setOpenRowId}
          pageSize={pageSize}
          page={page}
          onPageChange={setPage}
        />
      </LedgerAccountContext.Provider>

      {openRow === null ? null : <LedgerRowDetail row={openRow} reads={reads} />}
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the panel at once. */
export const __all__ = ["LedgerPanelProps", "LedgerPanel"] as const;
