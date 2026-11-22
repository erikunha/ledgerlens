/**
 * The table of the movements of the ledger of the recorded demo.
 *
 * Why this file exists: the ledger of the recorded demo is a table of movements, and the table is
 * the place where the visitor reads the rows the recording read. The table is drawn with the
 * table of the design system, so the first column is a row header, the caption is the accessible
 * name of the table and the arrow keys walk the cells.
 *
 * Why the table shows the order the visitor asked for and says so in words: the order the artifact
 * declares is the truth of the recording, and a visitor who cannot tell a reorder from the truth
 * is reading a lie. The table therefore always names in words the order that is on the screen,
 * and it says that the order is the order the visitor chose whenever the order on the screen is
 * not the order of the artifact (ADR-049).
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
 * Why the account and the state of the visit travel through a context and not through a prop: the
 * props of this table are pinned by ADR-045 and they carry no account and no visit, and the
 * caption of the table has to name the account whose movements it shows. The same reason holds for
 * the sort and the filter of the visitor: they are the state of the visit, they live in the memory
 * of the panel, and the panel hands them to the table through a context. A table that is used
 * outside the panel falls back to a caption that names the account of the recording.
 */

"use client";

import { createContext, useContext } from "react";
import type { ReactElement } from "react";

import { Table, type TableColumn } from "@/components/ui/Table";
import { formatMoney } from "@/lib/format/money";
import { ledgerRowIsRead, paginateLedgerRows } from "@/lib/replay/ledger";
import type { LedgerFilter, LedgerSort, LedgerSortDirection, LedgerSortField } from "@/lib/replay/ledger";
import type { LedgerRead, LedgerRow } from "@/lib/api/schemas";

/** The identifier of the reason of the control of the previous page. */
const PREVIOUS_REASON_ID = "ledgerlens-ledger-previous-reason";

/** The identifier of the reason of the control of the next page. */
const NEXT_REASON_ID = "ledgerlens-ledger-next-reason";

/** The identifier of the reason of the control that clears the filter. */
const CLEAR_REASON_ID = "ledgerlens-ledger-clear-reason";

/** The identifier of the label of the group of the order of the movements. */
const SORT_LABEL_ID = "ledgerlens-ledger-sort-label";

/** The identifier of the label of the group of the filter of the movements. */
const FILTER_LABEL_ID = "ledgerlens-ledger-filter-label";

/** The identifier of the field of the text of the filter. */
const FILTER_TEXT_ID = "ledgerlens-ledger-filter-text";

/** The identifier of the field of the kind of the filter. */
const FILTER_KIND_ID = "ledgerlens-ledger-filter-kind";

/** The identifier of the field of the state of the filter. */
const FILTER_STATUS_ID = "ledgerlens-ledger-filter-status";

/** The sentence that says why the control of the previous page would do nothing. */
const FIRST_PAGE = "This is the first page of the movements of the account.";

/** The sentence that says why the control of the next page would do nothing. */
const LAST_PAGE = "This is the last page of the movements of the account.";

/** The sentence that says why the control that clears the filter would do nothing. */
const NOTHING_TO_CLEAR = "The filter is empty, so there is nothing to clear.";

/**
 * The sentence that names the order on the screen when the order is the order of the artifact.
 */
const ARTIFACT_ORDER = "The order on the screen is the order the artifact declares.";

/**
 * The fields the visitor may sort the movements by.
 *
 * Why the list is the four fields that carry an order: the identifier is the identity of the
 * movement and the tie breaker of every sort, never a sort of its own.
 */
const SORT_FIELDS: readonly LedgerSortField[] = ["kind", "at", "amount", "status"];

/**
 * The name of the control of each sort, in the words of the interface.
 */
const SORT_LABELS: Record<LedgerSortField, string> = {
  kind: "Sort by the kind",
  at: "Sort by the moment",
  amount: "Sort by the amount",
  status: "Sort by the state",
};

/**
 * The name of each field in the sentence that names the order on the screen.
 */
const FIELD_NAMES: Record<LedgerSortField, string> = {
  kind: "the kind",
  at: "the moment",
  amount: "the amount",
  status: "the state",
};

/**
 * The name of each direction in the sentence that names the order on the screen.
 */
const DIRECTION_NAMES: Record<LedgerSortDirection, string> = {
  asc: "ascending",
  desc: "descending",
};

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
 * The state of the visit that the table of the movements draws.
 *
 * Why the state travels through a context: the props of this table are pinned by ADR-045 and they
 * carry no visit, and the sort and the filter of the visitor are the state of the visit, so they
 * live in the memory of the panel and reach the table through here.
 */
export interface LedgerViewContextValue {
  /** The movements of the account in the order the artifact declares, before the sort and the filter. */
  readonly artifactRows: readonly LedgerRow[];
  /** The sort the visitor chose, or null when the order of the artifact is on the screen. */
  readonly sort: LedgerSort | null;
  /** The filter the visitor chose. */
  readonly filter: LedgerFilter;
  /** Called when the visitor chooses another order. */
  readonly onSortChange: (sort: LedgerSort | null) => void;
  /** Called when the visitor changes the filter. */
  readonly onFilterChange: (filter: LedgerFilter) => void;
  /** Whether the sort of the visitor moved a movement. */
  readonly sortedByTheVisitor: boolean;
}

/**
 * The context that carries the state of the visit to the table of the movements.
 *
 * Why the default is an empty visit: a table that is used outside the panel shows the movements it
 * is given in the order it is given them, and its controls do nothing.
 */
export const LedgerViewContext = createContext<LedgerViewContextValue>({
  artifactRows: [],
  sort: null,
  filter: { text: "", kind: null, status: null },
  onSortChange: () => undefined,
  onFilterChange: () => undefined,
  sortedByTheVisitor: false,
});

/**
 * The props of the table of the movements.
 *
 * Why the table takes the reads of the recording: the table has to mark the movements a read
 * names, and only the reads know which ones they are.
 */
export interface LedgerTableProps {
  /** The movements of the account, in the order that is on the screen. */
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
 * Keeps the first occurrence of every value of a list.
 *
 * Why the helper exists: the filter offers the kinds and the states that the account of the
 * recording holds, and the order of the options is the order the artifact declares them in.
 */
function distinctOf(values: readonly string[]): string[] {
  const seen = new Set<string>();
  const distinct: string[] = [];
  for (const value of values) {
    if (!seen.has(value)) {
      seen.add(value);
      distinct.push(value);
    }
  }
  return distinct;
}

/**
 * Writes the sentence that names the order on the screen.
 *
 * Why the sentence names the order in words: a sort that the visitor cannot see is a lie, and the
 * order on the screen is either the order the artifact declares or the order the visitor chose.
 */
function orderSentence(view: LedgerViewContextValue): string {
  if (!view.sortedByTheVisitor || view.sort === null) {
    return ARTIFACT_ORDER;
  }
  const field = FIELD_NAMES[view.sort.field];
  const direction = DIRECTION_NAMES[view.sort.direction];
  return `The order on the screen is the order the visitor chose: by ${field}, ${direction}, and not the order the artifact declares.`;
}

/**
 * Writes the sentence that says how many movements the table shows.
 *
 * Why the sentence counts rows and never sums money: a total of the interface is a number the
 * browser calculated, and no artifact of the site carries one. A row that disappears because of a
 * filter is a row the visitor has to be told about.
 */
function rowsSentence(shown: number, total: number): string {
  if (total === 0) {
    return "The account holds no movement.";
  }
  if (shown === total) {
    return `The table shows the ${total} movements of the account.`;
  }
  return `The table shows ${shown} of the ${total} movements of the account.`;
}

/**
 * The table of the movements of the account.
 *
 * The table draws one page of the movements, it marks the movements the run read with the words
 * that say so, it carries the place the visitor stands at on the row itself, it never sums the
 * column of the amounts, and it draws the controls of the order and of the filter with the
 * sentences that say which order is on the screen.
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
  const view = useContext(LedgerViewContext);

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

  const kinds = distinctOf(view.artifactRows.map((row) => row.kind));
  const statuses = distinctOf(view.artifactRows.map((row) => row.status));
  const hasFilter =
    view.filter.text.trim() !== "" || view.filter.kind !== null || view.filter.status !== null;

  /** Chooses a field to sort by, and reverses the order when the field is the one already chosen. */
  function chooseField(field: LedgerSortField): void {
    if (view.sort !== null && view.sort.field === field) {
      view.onSortChange({ field, direction: view.sort.direction === "asc" ? "desc" : "asc" });
      return;
    }
    view.onSortChange({ field, direction: "asc" });
  }

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
      <div className="ll-ledger-controls">
        <div role="group" aria-labelledby={SORT_LABEL_ID} className="ll-ledger-control-group">
          <p id={SORT_LABEL_ID} className="ll-ledger-control-label">
            The order of the movements
          </p>
          <div className="ll-ledger-control-buttons">
            <button
              type="button"
              className="ll-ledger-control"
              aria-pressed={view.sort === null}
              onClick={() => view.onSortChange(null)}
            >
              The order of the artifact
            </button>
            {SORT_FIELDS.map((field) => (
              <button
                key={field}
                type="button"
                className="ll-ledger-control"
                aria-pressed={view.sort !== null && view.sort.field === field}
                onClick={() => chooseField(field)}
              >
                {SORT_LABELS[field]}
              </button>
            ))}
          </div>
        </div>

        <div role="group" aria-labelledby={FILTER_LABEL_ID} className="ll-ledger-control-group">
          <p id={FILTER_LABEL_ID} className="ll-ledger-control-label">
            The filter of the movements
          </p>
          <div className="ll-ledger-filter">
            <label className="ll-ledger-filter-label" htmlFor={FILTER_TEXT_ID}>
              The text the identifier, the kind, the state or the currency carries
            </label>
            <input
              id={FILTER_TEXT_ID}
              className="ll-ledger-filter-input"
              type="search"
              value={view.filter.text}
              onChange={(event) => view.onFilterChange({ ...view.filter, text: event.target.value })}
            />
          </div>
          <div className="ll-ledger-filter">
            <label className="ll-ledger-filter-label" htmlFor={FILTER_KIND_ID}>
              The kind of the movement kept
            </label>
            <select
              id={FILTER_KIND_ID}
              className="ll-ledger-filter-input"
              value={view.filter.kind ?? ""}
              onChange={(event) =>
                view.onFilterChange({ ...view.filter, kind: event.target.value === "" ? null : event.target.value })
              }
            >
              <option value="">Every kind</option>
              {kinds.map((kind) => (
                <option key={kind} value={kind}>
                  {kind}
                </option>
              ))}
            </select>
          </div>
          <div className="ll-ledger-filter">
            <label className="ll-ledger-filter-label" htmlFor={FILTER_STATUS_ID}>
              The state of the movement kept
            </label>
            <select
              id={FILTER_STATUS_ID}
              className="ll-ledger-filter-input"
              value={view.filter.status ?? ""}
              onChange={(event) =>
                view.onFilterChange({ ...view.filter, status: event.target.value === "" ? null : event.target.value })
              }
            >
              <option value="">Every state</option>
              {statuses.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            className="ll-ledger-control"
            aria-disabled={hasFilter ? undefined : true}
            aria-describedby={hasFilter ? undefined : CLEAR_REASON_ID}
            onClick={() => view.onFilterChange({ text: "", kind: null, status: null })}
          >
            Clear the filter
          </button>
          {hasFilter ? null : (
            <p id={CLEAR_REASON_ID} className="ll-ledger-note">
              {NOTHING_TO_CLEAR}
            </p>
          )}
        </div>
      </div>

      <p className="ll-ledger-note">{orderSentence(view)}</p>
      <p className="ll-ledger-note">{rowsSentence(rows.length, view.artifactRows.length)}</p>

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
  "LedgerViewContextValue",
  "LedgerViewContext",
  "LedgerTableProps",
  "LedgerTable",
] as const;
