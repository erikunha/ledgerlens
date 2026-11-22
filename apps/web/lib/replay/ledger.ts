/**
 * The selectors of the ledger of the recorded demo.
 *
 * Why this file exists: the artifact of the ledger is a published document, and the interface reads
 * it through these selectors instead of reaching into its fields. A selector that reads a field and
 * gives it back is a place where a rule can live: the order of the rows is the order of the
 * artifact, the order of the reads is the order of the recording, and a movement is read by the run
 * exactly when a read names it.
 *
 * Why nothing here calculates: the browser never sums the column of the amounts, never rounds an
 * amount and never turns the decimal text of the ledger into a number. A total of the interface is a
 * number the browser calculated, and no artifact of the site carries one (ADR-045).
 *
 * Why nothing here reads the network: the artifact is read by `apps/web/lib/api/replay.ts`, which is
 * the ONE place of the frontend that reads the published files, and the fence of the network keeps
 * holding because of it.
 */

import type { LedgerAccount, LedgerArtifact, LedgerRead, LedgerRow } from "@/lib/api/schemas";

/**
 * The sentence the panel shows when the site published no file of the ledger.
 *
 * Why the sentence is here and not in the component: a reason that a component writes is a reason
 * that another component has to write again, and the two sentences drift apart.
 */
export const LEDGER_UNAVAILABLE = "The site published no ledger of the recording.";

/**
 * The accounts the artifact publishes, in the order the artifact declares them.
 *
 * Why the list is never empty by accident: an artifact that publishes no account publishes no
 * movement, and the caller decides what to show when the list is empty.
 */
export function selectLedgerAccounts(ledger: LedgerArtifact): LedgerAccount[] {
  return ledger.accounts ?? [];
}

/**
 * The movements of an account, in the order the artifact declares them.
 *
 * Why the order is kept: the order of the ledger is the order of the movements in time, and a table
 * that reorders the rows says something the artifact does not say.
 */
export function selectLedgerRows(ledger: LedgerArtifact, accountId: string): LedgerRow[] {
  const account = (ledger.accounts ?? []).find((candidate) => candidate.id === accountId);
  return account?.rows ?? [];
}

/**
 * The reads of the recording that named the movements of an account, in the order of the recording.
 *
 * Why the reads live with the account: a read belongs to the account whose movements it names, and
 * the detail of a movement shows the reads of that account and nothing else.
 */
export function selectLedgerReads(ledger: LedgerArtifact, accountId: string): LedgerRead[] {
  const account = (ledger.accounts ?? []).find((candidate) => candidate.id === accountId);
  return account?.reads ?? [];
}

/**
 * The reads that named a movement.
 *
 * Why the identifier is compared and not guessed: a read names a movement exactly when the
 * identifier of the movement is one of the records the statement of the read named. A read that
 * named nothing names no movement.
 */
export function selectReadsForRecord(reads: readonly LedgerRead[], recordId: string): LedgerRead[] {
  return (reads ?? []).filter((read) => (read.records ?? []).includes(recordId));
}

/**
 * Says whether the run read a movement.
 *
 * Why the mark of the table is exact: the movement the run read carries the words that say so, and
 * a movement the run did not read carries no mark, because a mark that is on every row says nothing.
 */
export function ledgerRowIsRead(reads: readonly LedgerRead[], rowId: string): boolean {
  return selectReadsForRecord(reads, rowId).length > 0;
}

/**
 * One page of the movements.
 *
 * Why the page is clamped: a page beyond the last one is empty and never a wrapped page, so that the
 * visitor never sees the first rows again under a number that says otherwise. A page size that is
 * not a positive number gives no row at all, because a page of zero rows is not a page.
 */
export function paginateLedgerRows(
  rows: readonly LedgerRow[],
  page: number,
  pageSize: number,
): LedgerRow[] {
  const size = Number.isFinite(pageSize) && pageSize > 0 ? Math.floor(pageSize) : 0;
  if (size === 0) {
    return [];
  }
  const index = Number.isFinite(page) ? Math.floor(page) : 0;
  if (index < 0) {
    return [];
  }
  const start = index * size;
  return (rows ?? []).slice(start, start + size);
}

/** Every symbol this module exports, so that a reader sees the whole surface of the selectors at once. */
export const __all__ = [
  "LEDGER_UNAVAILABLE",
  "selectLedgerAccounts",
  "selectLedgerRows",
  "selectLedgerReads",
  "selectReadsForRecord",
  "ledgerRowIsRead",
  "paginateLedgerRows",
] as const;
