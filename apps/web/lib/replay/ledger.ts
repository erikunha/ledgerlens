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
 *
 * Why the sorting and the filtering live here and not in a component: they are rules of the ledger,
 * and a rule that lives in a component is a rule that the next component writes again (ADR-049). The
 * comparator compares the DECIMAL TEXT of the amounts and never a float, because a binary float of
 * a financial amount is a different amount, and the sort of the moments compares the text of the
 * ISO 8601, which is the order of the time.
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

/**
 * The field of a movement the visitor may sort the ledger by.
 *
 * Why the list is short: the sorts are the kind, the moment, the amount and the status, the four
 * fields of the row that carry an order. The identifier is the identity of the row and the tie
 * breaker of every sort, never a sort of its own.
 */
export type LedgerSortField = "at" | "amount" | "kind" | "status";

/**
 * The direction of a sort of the movements.
 *
 * Why the direction is a word and not a sign: the direction is shown to the visitor in words, and a
 * number that means "up" or "down" is a number the reader has to translate.
 */
export type LedgerSortDirection = "asc" | "desc";

/**
 * The order the visitor chose for the movements of the ledger.
 */
export interface LedgerSort {
  /** The field of the movement the order compares. */
  readonly field: LedgerSortField;
  /** The direction of the order. */
  readonly direction: LedgerSortDirection;
}

/**
 * The filter the visitor chose for the movements of the ledger.
 *
 * Why the filter holds three things and not one: the text searches the identifier, the kind, the
 * state and the currency of a movement, and the kind and the state narrow the rows down to the
 * ones that carry them. A filter with no text and no kind and no state keeps every row.
 */
export interface LedgerFilter {
  /** The text the identifier, the kind, the state or the currency carries, or empty. */
  readonly text: string;
  /** The kind of the movement kept, or null when every kind is kept. */
  readonly kind: string | null;
  /** The state of the movement kept, or null when every state is kept. */
  readonly status: string | null;
}

/**
 * The order of the movements that the artifact declares.
 *
 * Why the order of the artifact is a sort of the moment: the artifact declares the movements by the
 * moment, then by the kind, then by the identifier, and a sort of the moment that keeps the order
 * of the artifact for the movements that share a moment gives the order of the artifact back.
 */
export const LEDGER_DEFAULT_SORT: LedgerSort = { field: "at", direction: "asc" };

/**
 * The grammar of the decimal text of an amount of the ledger.
 *
 * Why the grammar is a regular expression and not a parser of floats: an amount that does not match
 * it is not an amount, and a comparator that guesses the value of a text is a comparator that
 * invents a number the artifact never carried.
 */
const DECIMAL_TEXT = /^-?\d+(\.\d+)?$/;

/**
 * The three parts of a decimal text of an amount.
 */
interface DecimalParts {
  /** Whether the amount is negative. */
  readonly negative: boolean;
  /** The integer part of the amount, with its digits and without its sign. */
  readonly integer: string;
  /** The fraction of the amount, with its digits and without the point. */
  readonly fraction: string;
}

/**
 * Removes the zeros that the integer part carries in front.
 *
 * Why the zeros are removed: the comparator compares the integer part by the number of its digits, and "099"
 * has three digits where "99" has two, so the two would not compare as the same amount. The zeros in front of
 * a decimal text carry no value, and removing them is a reading of the text and not a calculation of it.
 *
 * Why one zero always stays: the integer part of "0" and of "000" is the digit "0", and an empty part would
 * be a part that the comparator cannot compare.
 */
function withoutLeadingZeros(integer: string): string {
  const trimmed = integer.replace(/^0+(?=\d)/, "");
  return trimmed === "" ? "0" : trimmed;
}

/**
 * Splits a decimal text into its sign, its integer part and its fraction.
 *
 * Why the split is by hand: the parts are read as texts, and no part is ever turned into a number.
 * A text that does not match the grammar of a decimal amount gives null, and the comparator then
 * leaves the rows where the artifact put them.
 */
function partsOfDecimal(text: string): DecimalParts | null {
  if (!DECIMAL_TEXT.test(text)) {
    return null;
  }
  const negative = text.startsWith("-");
  const withoutSign = negative ? text.slice(1) : text;
  const point = withoutSign.indexOf(".");
  const integer = withoutLeadingZeros(point === -1 ? withoutSign : withoutSign.slice(0, point));
  const fraction = point === -1 ? "" : withoutSign.slice(point + 1);
  // The sign of a zero is not a sign: "-0" and "0" are the same amount, and a comparator that tells them
  // apart would put a zero on the wrong side of every other amount.
  const isZero = integer === "0" && /^0*$/.test(fraction);
  return { negative: negative && !isZero, integer, fraction };
}

/**
 * Compares two texts of the same grammar.
 *
 * Why the comparison is not a subtraction: the result of a subtraction is a number of the browser,
 * and the rule of the repository is that the browser never turns the text of the artifact into a
 * number.
 */
function compareText(left: string, right: string): number {
  if (left === right) {
    return 0;
  }
  return left < right ? -1 : 1;
}

/**
 * Compares the integer part of two decimal texts: by the number of digits and then by the digits.
 *
 * Why the number of digits comes first: the integer part of a decimal text is compared as a text,
 * and "100" is greater than "99" because it has more digits. A leading zero makes the text longer,
 * and a longer text is the greater one.
 */
function compareInteger(left: string, right: string): number {
  if (left.length !== right.length) {
    return left.length < right.length ? -1 : 1;
  }
  return compareText(left, right);
}

/**
 * Compares the fraction of two decimal texts, digit by digit.
 *
 * Why the shorter fraction is padded with zeros: "5.5" and "5.50" are the same amount, and the
 * fraction that ends first is as if it carried zeros.
 */
function compareFraction(left: string, right: string): number {
  const length = Math.max(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    const digitOfLeft = left.charAt(index) || "0";
    const digitOfRight = right.charAt(index) || "0";
    if (digitOfLeft !== digitOfRight) {
      return digitOfLeft < digitOfRight ? -1 : 1;
    }
  }
  return 0;
}

/**
 * Compares two decimal texts of amounts, as texts and never as floats.
 *
 * Why the comparator never calls `Number`, never calls `parseFloat` and never builds a `BigInt`:
 * a binary float of a financial amount is a different amount, and a text that does not match the
 * grammar of a decimal amount is never sorted by a guess: it keeps the place the artifact gave it.
 */
function compareDecimalText(left: string, right: string): number {
  const partsOfLeft = partsOfDecimal(left);
  const partsOfRight = partsOfDecimal(right);
  if (partsOfLeft === null || partsOfRight === null) {
    return 0;
  }
  if (partsOfLeft.negative !== partsOfRight.negative) {
    return partsOfLeft.negative ? -1 : 1;
  }
  const magnitude =
    compareInteger(partsOfLeft.integer, partsOfRight.integer) ||
    compareFraction(partsOfLeft.fraction, partsOfRight.fraction);
  return partsOfLeft.negative ? -magnitude : magnitude;
}

/**
 * Compares two movements by the field the visitor sorted by.
 *
 * Why the moment is compared as a text: the moment of a movement is an ISO 8601 text, and the
 * order of the text is the order of the time.
 */
function compareByField(left: LedgerRow, right: LedgerRow, field: LedgerSortField): number {
  if (field === "amount") {
    return compareDecimalText(left.amount, right.amount);
  }
  if (field === "kind") {
    return compareText(left.kind, right.kind);
  }
  if (field === "status") {
    return compareText(left.status, right.status);
  }
  return compareText(left.at, right.at);
}

/**
 * The movements of the ledger in the order the visitor chose.
 *
 * Why the sort is stable: two movements with the same value of the field keep the order the
 * artifact gave them, and the place of a movement in the artifact is a fact about the recording.
 * The index of the row is the tie breaker, so that the stability does not depend on the engine.
 *
 * Why the comparator compares the decimal TEXT of the amounts: a sort of money as a float is a sort
 * of money that is wrong, and the amount of the ledger is a text (ADR-043, ADR-049).
 */
export function sortLedgerRows(rows: readonly LedgerRow[], sort: LedgerSort): LedgerRow[] {
  const list = rows ?? [];
  const field = sort?.field ?? LEDGER_DEFAULT_SORT.field;
  const direction = sort?.direction === "desc" ? -1 : 1;
  return list
    .map((row, index) => ({ row, index }))
    .sort((left, right) => {
      const result = compareByField(left.row, right.row, field) * direction;
      return result !== 0 ? result : left.index - right.index;
    })
    .map((entry) => entry.row);
}

/**
 * The movements of the ledger that the filter of the visitor keeps.
 *
 * Why the text is searched in the identifier, the kind, the state and the currency: those are the
 * fields of the row that name it, and they are the fields a visitor reads before typing. The text
 * is read without its case and without its spaces at its edges, because a visitor types a word and
 * not a pattern.
 *
 * Why the kind and the state are compared exactly: a filter of the kind is a filter of the kind,
 * and a filter that matched a part of the word would keep movements the visitor did not ask for.
 */
export function filterLedgerRows(rows: readonly LedgerRow[], filter: LedgerFilter): LedgerRow[] {
  const list = rows ?? [];
  const text = (filter?.text ?? "").trim().toLowerCase();
  const kind = filter?.kind ?? null;
  const status = filter?.status ?? null;
  return list.filter((row) => {
    if (kind !== null && row.kind !== kind) {
      return false;
    }
    if (status !== null && row.status !== status) {
      return false;
    }
    if (text === "") {
      return true;
    }
    return (
      row.id.toLowerCase().includes(text) ||
      row.kind.toLowerCase().includes(text) ||
      row.status.toLowerCase().includes(text) ||
      row.currency.toLowerCase().includes(text)
    );
  });
}

/**
 * Says whether two lists of movements hold the same movements in the same order.
 *
 * Why the rule lives here: the panel has to know whether the sort of the visitor moved a movement,
 * and the answer is a rule of the ledger, so it is asked of the library and not written again in a
 * component.
 */
export function ledgerRowsHaveTheSameOrder(
  left: readonly LedgerRow[],
  right: readonly LedgerRow[],
): boolean {
  const first = left ?? [];
  const second = right ?? [];
  if (first.length !== second.length) {
    return false;
  }
  return first.every((row, index) => row.id === second[index]?.id);
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
  "LedgerSortField",
  "LedgerSortDirection",
  "LedgerSort",
  "LedgerFilter",
  "LEDGER_DEFAULT_SORT",
  "sortLedgerRows",
  "filterLedgerRows",
  "ledgerRowsHaveTheSameOrder",
] as const;
