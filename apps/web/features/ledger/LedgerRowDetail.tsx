/**
 * The detail of the movement that is open.
 *
 * Why this file exists: the table of the ledger shows the movements of the account, and the
 * visitor has to be able to open one of them and read everything the recording knows about it:
 * the six fields of the movement, and the reads of the recording that name it.
 *
 * Why the detail says in words that the recording read no record of a movement that no read
 * names: a movement that the run did not read is a fact of the recording, and a reader that
 * cannot tell it apart from a movement the run never saw is reading a half truth.
 *
 * Why the detail says in words that the recording published no policy trigger for the movement:
 * the artifact of the ledger carries no policy, no policy identifier and no link between a policy
 * and a movement, so the trigger is NOT AVAILABLE. A field that does not exist is never invented,
 * and a field that the artifact does not carry is never guessed and never filled with a
 * placeholder that looks like a value (ADR-049). The rate is never shown next to the refund
 * either, because no read of the recording named the refund (ADR-045).
 *
 * Why a rate is written as it was read: the `applied_rate` of a read is a rate and not an amount,
 * so it carries no currency and it is never written with `formatMoney`. The rows of a read are
 * shown exactly as the artifact carries them, with the names of the columns the recording
 * declared.
 *
 * Why the detail never calculates a value: every text of it is a text of the artifact, and there
 * is no total of the movements in it, because no artifact carries one.
 */

import type { ReactElement } from "react";

import { Table, type TableColumn } from "@/components/ui/Table";
import { formatMoney } from "@/lib/format/money";
import { selectReadsForRecord } from "@/lib/replay/ledger";
import type { LedgerRead, LedgerReadRow, LedgerRow } from "@/lib/api/schemas";

/** The identifier of the heading of the detail, so that the section names itself. */
const HEADING_ID = "ledgerlens-ledger-detail-heading";

/** The sentence that says in words that the recording read no record of the movement. */
const NO_RECORD = "The recording read no record of this movement.";

/**
 * The sentence that says in words that the recording published no policy trigger for the movement.
 *
 * Why the sentence is here and not in a column of the fields: the artifact of the ledger carries
 * no policy, so a column of the policy trigger would be a column that is empty for every row, and
 * a column that is always empty is a column that lies about the shape of the data (ADR-049).
 */
const NO_POLICY_TRIGGER = "The recording published no policy trigger for this movement.";

/**
 * The props of the detail of a movement.
 *
 * Why the detail takes the reads and not the reads that name the row: the panel owns the artifact
 * and the detail asks the library of the ledger which reads name the row, so that the rule of the
 * naming lives in one place.
 */
export interface LedgerRowDetailProps {
  /** The movement that is open. */
  readonly row: LedgerRow;
  /** The reads of the recording, so that the panel can show the ones that name the row. */
  readonly reads: readonly LedgerRead[];
}

/**
 * Writes the header of a column of a read.
 *
 * Why the headers of the columns of a read are written in words: the header of a column says what
 * the column holds, the way the header of the duration says "the duration the capture measured"
 * and not "duration".
 */
function headerOf(column: string): string {
  if (column === "kind") {
    return "The kind of the row the read returned";
  }
  if (column === "applied_rate") {
    return "The rate the read applied";
  }
  if (column === "applied_at") {
    return "The moment the rate was applied";
  }
  return `The column ${column} of the read`;
}

/**
 * Reads the value of a column of a row of a read.
 *
 * Why the value is read as a text: a rate is a rate and not an amount, so it never wears a
 * currency, and the browser never turns the text of the artifact into a number.
 */
function valueOf(row: LedgerReadRow, column: string): string {
  const entry = Object.entries(row).find(([name]) => name === column);
  const value = entry?.[1];
  return typeof value === "string" ? value : "";
}

/**
 * One read of the recording, with the rows it returned.
 *
 * Why the rows of a read are a table of the design system: the rows are a set of values with
 * names, and a table with a caption names them the way a reader can hear them.
 */
function ReadDetail({ read }: { readonly read: LedgerRead }): ReactElement {
  const columns: Array<TableColumn<LedgerReadRow>> = read.columns.map((column) => ({
    key: column,
    header: headerOf(column),
    render: (row) => valueOf(row, column),
  }));

  return (
    <article className="ll-ledger-read">
      <p className="ll-ledger-note">
        The read {read.evidence_id}, the event {read.seq}, the tool {read.tool}.
      </p>
      <pre className="ll-ledger-statement">
        <code>{read.sql}</code>
      </pre>
      <Table
        caption={`The rows the read ${read.evidence_id} returned`}
        columns={columns}
        rows={[...read.rows]}
        emptyMessage="The read returned no row."
      />
    </article>
  );
}

/**
 * The detail of the movement that is open.
 *
 * The detail draws the six fields of the movement and the reads of the recording that name it. It
 * says in words that the recording published no policy trigger for the movement, because the
 * artifact carries none. It never calculates a value and it never shows a total.
 */
export function LedgerRowDetail({ row, reads }: LedgerRowDetailProps): ReactElement {
  const namedReads = selectReadsForRecord(reads, row.id);

  return (
    <section aria-labelledby={HEADING_ID} className="ll-ledger-detail">
      <h5 id={HEADING_ID} className="text-base font-semibold">
        The movement {row.id}
      </h5>

      <dl className="ll-ledger-fields">
        <div>
          <dt className="ll-ledger-field-name">The kind of the movement</dt>
          <dd className="ll-ledger-field-value">{row.kind}</dd>
        </div>
        <div>
          <dt className="ll-ledger-field-name">The identifier of the movement</dt>
          <dd className="ll-ledger-field-value">{row.id}</dd>
        </div>
        <div>
          <dt className="ll-ledger-field-name">The moment of the movement</dt>
          <dd className="ll-ledger-field-value">{row.at}</dd>
        </div>
        <div>
          <dt className="ll-ledger-field-name">The amount the ledger carries</dt>
          <dd className="ll-ledger-field-value ll-ledger-amount">{formatMoney(row.amount, row.currency)}</dd>
        </div>
        <div>
          <dt className="ll-ledger-field-name">The currency of the movement</dt>
          <dd className="ll-ledger-field-value">{row.currency}</dd>
        </div>
        <div>
          <dt className="ll-ledger-field-name">The state of the movement</dt>
          <dd className="ll-ledger-field-value">{row.status}</dd>
        </div>
      </dl>

      <p className="ll-ledger-note">{NO_POLICY_TRIGGER}</p>

      {namedReads.length === 0 ? (
        <p className="ll-ledger-note">{NO_RECORD}</p>
      ) : (
        <>
          <p className="ll-ledger-note">The reads of the recording that name this movement:</p>
          {namedReads.map((read) => (
            <ReadDetail key={read.evidence_id} read={read} />
          ))}
        </>
      )}
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the detail at once. */
export const __all__ = ["LedgerRowDetailProps", "LedgerRowDetail"] as const;
