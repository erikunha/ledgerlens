"use client";

/**
 * The view of the difference of the branch.
 *
 * Why this file exists: the visitor of the sandbox has to see what the mutations of the branch
 * changed, and the view shows exactly what the server sent. The values before and after are
 * rendered as they were written, a decimal text is never rewritten, the currency of a monetary
 * value is shown next to it, the verdict is the label of the server and the rule of the domain
 * that does not hold says its own reason.
 *
 * Why the difference is a table with a header: the identity of a record is not a column of its
 * own, it is a value of the first column, and the header of the row is the field of the row, so
 * a screen reader reads the field and the record together. The caption is the accessible name of
 * the table, a `th` with `scope="col"` names every column and a `th` with `scope="row"` names
 * every row (ADR-044).
 *
 * Why the verdict carries an `h4`: the section of the difference is an `h3` of the page, and the
 * verdict of the case is one step below it.
 */

import type { ReactElement } from "react";

import { Table } from "@/components/ui/Table";
import type { TableColumn } from "@/components/ui/Table";
import type { BranchDiffBody, BranchDiffEntry } from "@/features/sandbox/types";
import { MONEY_UNAVAILABLE } from "@/lib/format/money";

/**
 * Renders one value of the difference, with the currency of the value when there is one.
 *
 * Why the value is a text: the money of the sandbox is a decimal text of the server, and the
 * formatter of the recorded demo groups the digits of the integer part. The rule of the sandbox
 * is stricter: the value of the difference is the value the server wrote, so the text is shown
 * as it is and the currency is written next to it.
 */
function valueCell(value: string, currency: string | null, monetary: boolean): ReactElement {
  const text = value === "" ? MONEY_UNAVAILABLE : value;
  return (
    <>
      <span className="font-mono">{text}</span>
      {monetary && currency !== null && currency !== "" ? (
        <>
          {" "}
          <span className="font-mono text-xs text-text-muted">{currency}</span>
        </>
      ) : null}
    </>
  );
}

/**
 * Says whether a value of the server is absent.
 *
 * Why an empty text is an absent value: the server writes a missing amount as an empty text, and
 * a blank cell would hide that the value is not there. The interface says that the value is not
 * available instead.
 */
function isAbsent(value: string | null): boolean {
  return value === null || value === "";
}

/**
 * Renders the range of the measure of the verdict, with the texts of the server.
 *
 * Why the range is a sentence and not two blanks: an empty bound is an absent bound, and a range
 * whose two bounds are absent says that the range is not available.
 */
function rangeText(low: string | null, high: string | null): string {
  if (isAbsent(low) && isAbsent(high)) {
    return MONEY_UNAVAILABLE;
  }
  return `${low === null || low === "" ? MONEY_UNAVAILABLE : low} to ${high === null || high === "" ? MONEY_UNAVAILABLE : high}`;
}

/**
 * The columns of the table of the difference.
 *
 * Why the record is the first column and not the header of the row: the header of the row is
 * the field, and the record is a value of the first column, so that a screen reader reads the
 * field and the record together.
 */
const DIFF_COLUMNS: Array<TableColumn<BranchDiffEntry>> = [
  {
    key: "record",
    header: "Record",
    rowHeader: false,
    render: (entry) => (
      <>
        <span>{entry.record}</span>
        {entry.record_id === "" ? null : (
          <>
            {" "}
            <span className="font-mono text-xs text-text-muted">{entry.record_id}</span>
          </>
        )}
      </>
    ),
  },
  {
    key: "field",
    header: "Field",
    rowHeader: true,
    render: (entry) => entry.field,
  },
  {
    key: "before",
    header: "Value before",
    render: (entry) => valueCell(entry.before, entry.currency, entry.value_kind === "monetary"),
  },
  {
    key: "after",
    header: "Value after",
    render: (entry) => valueCell(entry.after, entry.currency, entry.value_kind === "monetary"),
  },
  {
    key: "kind",
    header: "Kind of the value",
    render: (entry) => entry.value_kind,
  },
];

/**
 * The props of the view of the difference.
 *
 * Why the whole answer comes as a prop: the difference, the rules of the domain and the verdict
 * are the three parts of one answer of the server, and the view never mixes them with a fact of
 * its own.
 */
export interface DiffViewProps {
  /** The answer of the diff of the branch, when the visitor asked for it. */
  readonly diff: BranchDiffBody | null;
}

/**
 * The view of the difference between the published base and the branch.
 *
 * The view draws the answer of the server and it never calculates a value.
 */
export function DiffView({ diff }: DiffViewProps): ReactElement {
  if (diff === null) {
    return (
      <p className="ll-sandbox-empty text-sm text-text-muted">
        The difference has not been read yet.
      </p>
    );
  }

  return (
    <div className="ll-sandbox-diff flex flex-col gap-4">
      <Table
        caption="The difference between the published base and the branch"
        columns={DIFF_COLUMNS}
        rows={diff.diff}
        emptyMessage="The branch did not change since the published base."
      />

      <section aria-labelledby="sandbox-verdict-heading">
        <h4 id="sandbox-verdict-heading" className="text-sm font-semibold uppercase tracking-wide text-text-muted">
          The verdict of the case
        </h4>
        <dl className="mt-2 grid gap-2 sm:grid-cols-2">
          <div>
            <dt className="text-xs text-text-subtle">Verdict</dt>
            <dd className="text-sm">
              <span className="inline-block rounded border border-line-strong px-1 font-semibold">
                {diff.verdict.label}
              </span>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-text-subtle">Measure</dt>
            <dd className="text-sm">{diff.verdict.measure}</dd>
          </div>
          <div>
            <dt className="text-xs text-text-subtle">Value</dt>
            <dd className="font-mono text-sm">
              {isAbsent(diff.verdict.value) ? MONEY_UNAVAILABLE : diff.verdict.value}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-text-subtle">Range</dt>
            <dd className="font-mono text-sm">{rangeText(diff.verdict.low, diff.verdict.high)}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs text-text-subtle">Detail</dt>
            <dd className="text-sm">{diff.verdict.detail}</dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="sandbox-invariants-label">
        <h4 id="sandbox-invariants-label" className="text-sm font-semibold uppercase tracking-wide text-text-muted">
          The rules of the domain
        </h4>
        <ul className="mt-2 flex flex-col gap-3">
          {diff.invariants.map((invariant) => (
            <li key={invariant.identifier} className="rounded border border-line p-2">
              <p className="text-sm font-semibold">{invariant.identifier}</p>
              <p className="text-sm text-text-muted">{invariant.description}</p>
              <p className="text-sm">
                {invariant.passed ? "The rule holds." : "The rule does not hold."}
              </p>
              {invariant.passed ? null : (
                <p className="text-sm text-danger-dark">{invariant.reason}</p>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the view at once. */
export const __all__ = ["DiffViewProps", "DiffView"] as const;
