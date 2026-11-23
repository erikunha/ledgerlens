"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";

import { cn } from "@/lib/design/cn";

/**
 * The table of the design system: a dense data table that a keyboard user can read and sort.
 *
 * Why it is built by hand and not taken from a library: the design package asks for three
 * things that a general purpose grid does not give for free, and that the interface has to get
 * right on the first try.
 *
 * The first is the row header. The first column of every row is a `th` with `scope="row"`, so
 * a screen reader announces the row by its identity and not by a sequence of cells.
 *
 * The second is the accessible name. The table carries a caption, visible or hidden, and that
 * caption is what names it. A table without a name is announced only as "table".
 *
 * The third is the keyboard. The cells form a single navigation group: the arrow keys move
 * between the cells, Home and End go to the ends of the row, and the sort buttons are real
 * buttons, so they are reachable with Tab and they fire with Enter and Space.
 *
 * The sorting is controlled by the caller. The table never reorders the data on its own, so the
 * order the visitor sees is always the order the published artifact declares.
 *
 * Why a row can carry an attribute: the place the visitor stands at is a property of the row and
 * not of the cell that happens to hold the name of the thing. A table that marks the row the
 * reader is at with `aria-current` gives a reader of a screen reader that place, and the caller
 * of the table is the one that knows which row it is.
 */

export type SortDirection = "ascending" | "descending";

export interface TableColumn<T> {
  /** The key of the column. It identifies the column in the sort state. */
  key: string;
  /** The header of the column. */
  header: ReactNode;
  /** Renders the cell of the column. */
  render: (row: T, index: number) => ReactNode;
  /** The value the sort compares. A column without it cannot be sorted. */
  sortValue?: (row: T) => string | number;
  /** True when the column holds the identity of the row. Only the first column should say so. */
  rowHeader?: boolean;
  /** The alignment of the column. */
  align?: "left" | "right";
}

/**
 * The attributes the table gives to one row of its body.
 *
 * Why the list is short: the table draws the data and the keyboard of the table, and the only
 * thing a caller has to say about a row is whether the row marks the place the reader stands at.
 */
export interface TableRowAttributes {
  /** The value of `aria-current` of the row, when the row marks the place the visitor stands at. */
  "aria-current"?: "true" | "false";
}

export interface TableProps<T> {
  /** The caption of the table. It is its accessible name. */
  caption: string;
  /** Hides the caption visually when it is still needed by a screen reader. */
  hideCaption?: boolean;
  /** The columns of the table. */
  columns: Array<TableColumn<T>>;
  /** The rows of the table. */
  rows: Array<T>;
  /**
   * The attributes of the row of the data.
   *
   * Why it is a function and not a value: the caller is the one that knows which row marks a
   * place, and the table never decides that for anybody. A table that is used without it is a
   * table whose rows carry no attribute, exactly as before.
   */
  rowAttributes?: (row: T, index: number) => TableRowAttributes;
  /** The key of the sorted column, when the table is sorted. */
  sortKey?: string;
  /** The direction of the sort, when the table is sorted. */
  sortDirection?: SortDirection;
  /** Called when the visitor asks for another order. */
  onSortChange?: (key: string, direction: SortDirection) => void;
  /** The message shown when there is no row. */
  emptyMessage?: string;
  /** Extra class names of the table element. */
  className?: string;
}

export function Table<T>({
  caption,
  hideCaption = false,
  columns,
  rows,
  rowAttributes,
  sortKey,
  sortDirection,
  onSortChange,
  emptyMessage = "No rows.",
  className,
}: TableProps<T>) {
  const bodyRef = useRef<HTMLTableSectionElement | null>(null);
  // The focused cell is the anchor of the keyboard navigation: every cell is reachable from it.
  const [activeCell, setActiveCell] = useState<{ row: number; column: number } | null>(null);

  const focusCell = useCallback((row: number, column: number) => {
    setActiveCell({ row, column });
    // the focus happens after the state, because the cell has to be rendered with its tab index first
    window.requestAnimationFrame(() => {
      const target = bodyRef.current?.querySelector<HTMLElement>(
        `[data-cell="${row}:${column}"]`,
      );
      target?.focus();
    });
  }, []);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTableSectionElement>) => {
      if (rows.length === 0 || columns.length === 0) {
        return;
      }
      const current = activeCell ?? { row: 0, column: 0 };
      const { row, column } = current;
      let next: { row: number; column: number } | null = null;

      switch (event.key) {
        case "ArrowRight":
          next = { row, column: Math.min(column + 1, columns.length - 1) };
          break;
        case "ArrowLeft":
          next = { row, column: Math.max(column - 1, 0) };
          break;
        case "ArrowDown":
          next = { row: Math.min(row + 1, rows.length - 1), column };
          break;
        case "ArrowUp":
          next = { row: Math.max(row - 1, 0), column };
          break;
        case "Home":
          next = { row, column: 0 };
          break;
        case "End":
          next = { row, column: columns.length - 1 };
          break;
        default:
          return;
      }

      event.preventDefault();
      focusCell(next.row, next.column);
    },
    [activeCell, columns.length, focusCell, rows.length],
  );

  const sortableColumns = useMemo(
    () => new Set(columns.filter((column) => Boolean(column.sortValue)).map((column) => column.key)),
    [columns],
  );

  const handleSort = useCallback(
    (key: string) => {
      if (!onSortChange) {
        return;
      }
      // clicking the sorted column again reverses the order, which is what a visitor expects
      const direction: SortDirection = sortKey === key && sortDirection === "ascending" ? "descending" : "ascending";
      onSortChange(key, direction);
    },
    [onSortChange, sortDirection, sortKey],
  );

  return (
    <div className="w-full overflow-x-auto">
      <table className={cn("w-full border-collapse text-sm", className)}>
        <caption className={cn(hideCaption ? "ll-visually-hidden" : "px-4 py-2 text-left text-sm text-text-muted")}>
          {caption}
        </caption>
        <thead>
          <tr className="border-b border-line">
            {columns.map((column) => {
              const canSort = sortableColumns.has(column.key) && Boolean(onSortChange);
              const isSorted = sortKey === column.key;
              const ariaSort = isSorted ? sortDirection : undefined;

              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={ariaSort}
                  className={cn(
                    "px-3 py-2 text-xs font-semibold tracking-wide text-text-muted uppercase",
                    column.align === "right" ? "text-right" : "text-left",
                  )}
                >
                  {canSort ? (
                    <button
                      type="button"
                      onClick={() => handleSort(column.key)}
                      className="inline-flex items-center gap-1 rounded text-left hover:text-foreground"
                    >
                      {column.header}
                      <span aria-hidden="true" className="text-[10px]">
                        {isSorted ? (sortDirection === "ascending" ? "▲" : "▼") : "↕"}
                      </span>
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody ref={bodyRef} onKeyDown={handleKeyDown}>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-3 py-4 text-text-muted">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row, rowIndex) => (
              // the caller says what the row says about itself, and a table used without the prop
              // gives its rows no attribute at all
              <tr
                key={rowIndex}
                {...rowAttributes?.(row, rowIndex)}
                className="border-b border-line last:border-b-0 hover:bg-surface"
              >
                {columns.map((column, columnIndex) => {
                  const isRowHeader = column.rowHeader ?? columnIndex === 0;
                  const cellContent = column.render(row, rowIndex);
                  const isActive = (activeCell ?? { row: 0, column: 0 }).row === rowIndex
                    && (activeCell ?? { row: 0, column: 0 }).column === columnIndex;

                  if (isRowHeader) {
                    return (
                      <th
                        key={column.key}
                        scope="row"
                        data-cell={`${rowIndex}:${columnIndex}`}
                        tabIndex={isActive ? 0 : -1}
                        onFocus={() => setActiveCell({ row: rowIndex, column: columnIndex })}
                        className={cn(
                          "px-3 py-2 text-left font-medium text-foreground",
                          column.align === "right" && "text-right",
                        )}
                      >
                        {cellContent}
                      </th>
                    );
                  }

                  return (
                    <td
                      key={column.key}
                      data-cell={`${rowIndex}:${columnIndex}`}
                      tabIndex={isActive ? 0 : -1}
                      onFocus={() => setActiveCell({ row: rowIndex, column: columnIndex })}
                      className={cn(
                        "px-3 py-2 text-text-muted",
                        column.align === "right" && "text-right",
                      )}
                    >
                      {cellContent}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
