/**
 * The table of the movements of the ledger of the recorded demo.
 *
 * Why this file exists: the ledger of the recorded demo is a table of movements, and the table is
 * the place where the visitor reads the rows the recording read. The table is drawn with the
 * table of the design system, so the first column is a row header, the caption is the accessible
 * name of the table and the arrow keys walk the cells.
 *
 * Why the table never reorders the rows: the order the visitor sees is the order the artifact
 * declares, and the artifact is the truth of the recording.
 *
 * Why the money of the table is the decimal text of the artifact: the amount is written with
 * `formatMoney` with the currency of the artifact, and the browser never calls `Number`, never
 * multiplies, never rounds and never converts a currency. There is no total row and no total in
 * the caption, because a total is a number the browser calculated and no artifact carries one.
 *
 * Why the pagination never disables a control: a control that would do nothing carries
 * `aria-disabled` and a sentence a reader can hear, pointed at with `aria-describedby`. A focus
 * that is dropped on the body of the document sends the next Tab back to the top of the page
 * (ADR-043).
 *
 * Why the account travels through a context and not through a prop: the props of this table are
 * pinned by ADR-045 and they carry no account, and the caption of the table has to name the
 * account whose movements it shows. A table that is used outside the panel falls back to a caption
 * that names the account of the recording.
 */

"use client";

import { createContext, useContext } from "react";
import type { ReactElement } from "react";

import { Table, type TableColumn } from "@/components/ui/Table";
import { formatMoney } from "@/lib/format/money";
import { ledgerRowIsRead, paginateLedgerRows } from "@/lib/replay/ledger";
import type { LedgerRead, LedgerRow } from "@/lib/api/schemas";

/** The identifier of the reason of the control of the previous page. */
const PREVIOUS_REASON_ID = "ledgerlens-ledger-previous-reason";

/** The identifier of the reason of the control of the next page. */
const NEXT_REASON_ID = "ledgerlens-ledger-next-reason";

/** The sentence that says why the control of the previous page would do nothing. */
const FIRST_PAGE = "This is the first page of the movements of the account.";

/** The sentence that says why the control of the next page would do nothing. */
const LAST_PAGE = "This is the last page of the movements of the account.";

/**
 * The account whose movements the table shows.
 *
 * Why the context carries it: the caption of the table names the account, and the props of the
 * table are pinned by ADR-045.
 */
export interface LedgerAccountContextValue {
  /** The identifier of the account whose movements are on the screen. */
  readonly accountId: string | null;
}

/** The context that carries the account of the table of the movements. */
export const LedgerAccountContext = createContext<LedgerAccountContextValue>({ accountId: null });

/**
 * The props of the table of the movements.
 *
 * Why the table takes the reads of the recording: the table has to mark the movements a read
 * names, and only the reads know which ones they are.
 */
export interface LedgerTableProps {
  /** The movements of the account, in the order of the artifact. */
  readonly rows: readonly LedgerRow[];
  /** The reads of the recording, so that the table can mark the rows the run read. */
  readonly reads: readonly LedgerRead[];
  /** The identifier of the row that is open, when a row is open. */
  readonly openRowId: string | null;
  /** Called when the visitor opens a row, or closes it with null. */
  readonly onOpenRow: (rowId: string | null) => void;
  /** The number of rows of a page, the number the artifact declares. */
  readonly pageSize: number;
  /** The page that is on the screen, counting from zero. */
  readonly page: number;
  /** Called when the visitor asks for another page. */
  readonly onPageChange: (page: number) => void;
}

/**
 * The table of the movements of the account.
 *
 * The table draws one page of the movements, it marks the movements the run read with the words
 * that say so, it carries the place the visitor stands at on the row itself, and it never sums the
 * column of the amounts.
 */
export function LedgerTable({
  rows,
  reads,
  openRowId,
  onOpenRow,
  pageSize,
  page,
  onPageChange,
}: LedgerTableProps): ReactElement {
  const { accountId } = useContext(LedgerAccountContext);

  const safePageSize = pageSize > 0 ? pageSize : 1;
  const pageCount = Math.max(1, Math.ceil(rows.length / safePageSize));
  const currentPage = Math.min(Math.max(page, 0), pageCount - 1);
  const pageRows = paginateLedgerRows(rows, currentPage, safePageSize);
  const isFirstPage = currentPage <= 0;
  const isLastPage = currentPage >= pageCount - 1;

  const caption =
    accountId === null
      ? "The movements of the account of the recording"
      : `The movements of the account ${accountId}`;

  const columns: Array<TableColumn<LedgerRow>> = [
    {
      key: "id",
      header: "The identifier of the movement",
      rowHeader: true,
      render: (row) => {
        const isOpen = row.id === openRowId;
        return (
          <button
            type="button"
            aria-expanded={isOpen}
            className="ll-ledger-open"
            onClick={() => onOpenRow(isOpen ? null : row.id)}
          >
            {row.id}
          </button>
        );
      },
    },
    {
      key: "kind",
      header: "The kind of the movement",
      render: (row) => row.kind,
    },
    {
      key: "at",
      header: "The moment of the movement",
      render: (row) => row.at,
    },
    {
      key: "amount",
      header: "The amount the ledger carries",
      align: "right",
      // The money is the decimal text of the artifact with the currency of the artifact: the
      // formatter groups the digits of the integer part and changes no digit.
      render: (row) => <span className="ll-ledger-amount">{formatMoney(row.amount, row.currency)}</span>,
    },
    {
      key: "status",
      header: "The state of the movement",
      render: (row) => row.status,
    },
    {
      key: "read",
      header: "The reading of the run",
      render: (row) =>
        ledgerRowIsRead(reads, row.id) ? <span className="ll-ledger-mark">Read by the run</span> : null,
    },
    {
      key: "open",
      header: "The state of the visit",
      render: (row) => (row.id === openRowId ? <span className="ll-ledger-mark">Open</span> : null),
    },
  ];

  return (
    <div className="ll-ledger-table">
      <Table
        caption={caption}
        columns={columns}
        rows={[...pageRows]}
        emptyMessage="The account holds no movement."
        // The place the visitor stands at is a property of the row, and the caller is the one that
        // knows which row it is.
        rowAttributes={(row) => (row.id === openRowId ? { "aria-current": "true" } : {})}
      />

      <div className="ll-ledger-pagination">
        <button
          type="button"
          className="ll-ledger-page"
          aria-disabled={isFirstPage ? true : undefined}
          aria-describedby={isFirstPage ? PREVIOUS_REASON_ID : undefined}
          onClick={() => onPageChange(Math.max(currentPage - 1, 0))}
        >
          Previous page
        </button>
        <p className="ll-ledger-page-state">
          Page {currentPage + 1} of {pageCount}
        </p>
        <button
          type="button"
          className="ll-ledger-page"
          aria-disabled={isLastPage ? true : undefined}
          aria-describedby={isLastPage ? NEXT_REASON_ID : undefined}
          onClick={() => onPageChange(Math.min(currentPage + 1, pageCount - 1))}
        >
          Next page
        </button>
      </div>

      {isFirstPage ? (
        <p id={PREVIOUS_REASON_ID} className="ll-ledger-note">
          {FIRST_PAGE}
        </p>
      ) : null}
      {isLastPage ? (
        <p id={NEXT_REASON_ID} className="ll-ledger-note">
          {LAST_PAGE}
        </p>
      ) : null}
    </div>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the table at once. */
export const __all__ = [
  "LedgerAccountContextValue",
  "LedgerAccountContext",
  "LedgerTableProps",
  "LedgerTable",
] as const;
