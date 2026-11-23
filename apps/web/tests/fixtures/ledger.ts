/**
 * The deterministic fixture of the ledger of the tests.
 *
 * Why this file exists: ADR-049 proved that no account of the public data holds a thousand
 * movements, so the table of a thousand rows cannot be published and it is proved over a fixture
 * that only the tests use. The fixture is the ALGORITHM under test: the same sorting and the same
 * filtering that the visitor runs over the two movements of the recorded ledger.
 *
 * Why the generator is a pure function: it reads no clock, it calls no random source and it reads
 * no file, so the thousandth row of the fixture is the same row in every machine and in every run.
 * A test that depends on the machine is not a test.
 *
 * Why the rows carry the SIX fields of ADR-045 and nothing else: the shape of the row is the shape
 * of the branch ledger (`_ledger_items` of `ledgerlens/sandbox/branch.py`), and a fixture with
 * fields the artifact does not carry would prove a table that the artifact cannot render.
 *
 * Why the amounts are decimal TEXTS: the money of the ledger is a text, and the browser never
 * turns it into a number. The fixture builds the text of the amount by hand, digit by digit, and
 * it never writes a number of an amount.
 *
 * Why this file is never imported by a file of `apps/web/features/`: a component that reads a
 * fixture draws data that no artifact of the site carries, and the site publishes only what the
 * recordings read.
 */

import type { LedgerArtifact, LedgerRead, LedgerRow } from "@/lib/api/schemas";

/**
 * The kinds of movement the ledger of the branch writes.
 *
 * Why the list is closed: the fixture holds the kinds of the ledger and nothing else, so a row
 * with a kind outside the list would prove a shape that the artifact does not have.
 */
export const LEDGER_ROW_KINDS = ["transaction", "refund", "chargeback"] as const;

/**
 * The states a transaction of the ledger carries.
 *
 * Why the list is the one of the invariants of the sandbox: `TRANSACTION_STATUSES` of
 * `ledgerlens/sandbox/invariants.py` is the closed list of the states of a transaction.
 */
const TRANSACTION_STATUSES = [
  "authorized",
  "captured",
  "failed",
  "refunded",
  "partially_refunded",
  "disputed",
  "charged_back",
] as const;

/**
 * The states a refund of the ledger carries.
 *
 * Why the list is the one of the invariants of the sandbox: `REFUND_STATUSES` of
 * `ledgerlens/sandbox/invariants.py` is the closed list of the states of a refund.
 */
const REFUND_STATUSES = ["requested", "paid", "rejected"] as const;

/**
 * The stages a chargeback of the ledger carries.
 *
 * Why the list is the one of the projector of the simulator: the stages of a chargeback are the
 * ones the projector writes when it opens the case and when the case ends.
 */
const CHARGEBACK_STATUSES = [
  "opened",
  "evidence_requested",
  "evidence_submitted",
  "won",
  "lost",
] as const;

/**
 * Every state the fixture can write, the union of the three closed lists.
 *
 * Why the union is published: a case has to be able to say that every state of a row belongs to
 * the closed lists of the ledger, and the union is the whole of them.
 */
export const LEDGER_ROW_STATUSES = [
  ...TRANSACTION_STATUSES,
  ...REFUND_STATUSES,
  ...CHARGEBACK_STATUSES,
] as const;

/**
 * The currencies the fixture writes.
 *
 * Why the list is short and fixed: the currency of a movement is a text of the artifact, and the
 * fixture writes the currencies the ledger of the recording carries.
 */
export const LEDGER_ROW_CURRENCIES = ["EUR", "BRL", "USD"] as const;

/**
 * The moment the fixture starts at.
 *
 * Why the origin is written down: the moment of a row is the origin plus one second per row, and a
 * moment that came from the clock of the machine would make the fixture depend on the machine.
 */
const ORIGIN_YEAR = 2026;
const ORIGIN_MONTH = 1;
const ORIGIN_DAY = 1;

/**
 * The prefix of the identifier of a movement, per kind.
 *
 * Why the prefix is per kind: the identifier of a movement names its kind the way the ledger names
 * it, and the identifier of the fixture never collides with the identifier of another row.
 */
const ID_PREFIXES: Record<string, string> = {
  transaction: "TX",
  refund: "R",
  chargeback: "CB",
};

/**
 * The number of the digits of the identifier of a movement.
 *
 * Why the number is six: a thousand rows of the fixture need four digits, and six leave room for a
 * fixture bigger than the one the milestone uses.
 */
const ID_DIGITS = 6;

/**
 * Writes the moment of a movement, as an ISO 8601 text.
 *
 * Why the text is written by hand: the moment of the ledger is `2026-10-15T09:12:00Z`, with no
 * fraction of a second and with the letter `Z`, and the text of the artifact is written the same
 * way.
 */
function momentOf(index: number): string {
  const secondsOfDay = index % 86400;
  const hour = Math.floor(secondsOfDay / 3600);
  const minute = Math.floor((secondsOfDay % 3600) / 60);
  const second = secondsOfDay % 60;
  const day = ORIGIN_DAY + Math.floor(index / 86400);
  const dayText = String(day).padStart(2, "0");
  return `${ORIGIN_YEAR}-${String(ORIGIN_MONTH).padStart(2, "0")}-${dayText}T${String(hour).padStart(
    2,
    "0",
  )}:${String(minute).padStart(2, "0")}:${String(second).padStart(2, "0")}Z`;
}

/**
 * Writes the amount of a movement, as a decimal text.
 *
 * Why the text is built from the cents and never from a float: the amount of the ledger is a
 * decimal text, and a float of an amount of money is another amount. The rule walks the cents with
 * a stride that is not a divisor of the number of cents, so that the amounts of the fixture are
 * spread over the whole list and never repeat themselves in a short cycle.
 */
function amountOf(index: number): string {
  const cents = (1000 + index * 7919) % 1000000;
  const integer = Math.floor(cents / 100);
  const fraction = String(cents % 100).padStart(2, "0");
  return `${integer}.${fraction}`;
}

/**
 * The state of a movement, per kind.
 *
 * Why the state is chosen per kind: a transaction, a refund and a chargeback do not carry the same
 * states, and a fixture that gave a refund the state of a transaction would prove a shape that
 * the ledger does not have.
 */
function statusOf(kind: string, index: number): string {
  if (kind === "refund") {
    return REFUND_STATUSES[index % REFUND_STATUSES.length] ?? "paid";
  }
  if (kind === "chargeback") {
    return CHARGEBACK_STATUSES[index % CHARGEBACK_STATUSES.length] ?? "opened";
  }
  return TRANSACTION_STATUSES[index % TRANSACTION_STATUSES.length] ?? "captured";
}

/**
 * Builds the movements of the fixture.
 *
 * Why the rows come out in the order the artifact declares: the fixture declares them by the
 * moment, and a sort of the moment that keeps the order of the fixture gives that order back, so
 * the default order of the fixture and the default order of the artifact are the same thing.
 *
 * Why the function is pure: two calls with the same number of rows give the same rows, and the
 * thousandth row of the fixture is the same row in every machine and in every run.
 */
export function buildLedgerRows(count: number): LedgerRow[] {
  const total = Number.isFinite(count) && count > 0 ? Math.floor(count) : 0;
  const rows: LedgerRow[] = [];
  for (let index = 0; index < total; index += 1) {
    const kind = LEDGER_ROW_KINDS[index % LEDGER_ROW_KINDS.length] ?? "transaction";
    const prefix = ID_PREFIXES[kind] ?? "TX";
    // The currency walks the list with a stride that does not follow the kind, so that a kind is
    // not always paid in the same currency.
    const currency = LEDGER_ROW_CURRENCIES[(index + Math.floor(index / 3)) % LEDGER_ROW_CURRENCIES.length] ?? "EUR";
    rows.push({
      kind,
      id: `${prefix}-${String(index + 1).padStart(ID_DIGITS, "0")}`,
      at: momentOf(index),
      amount: amountOf(index),
      currency,
      status: statusOf(kind, index),
    });
  }
  return rows;
}

/**
 * Builds the artifact of the ledger of the fixture.
 *
 * Why the artifact exists: the panel of the ledger reads an artifact and never a list of rows, so
 * the case that renders a thousand rows has to give the panel an artifact of a thousand rows.
 *
 * Why the read names the first movement and nothing else: the mark of the table says that the run
 * read a movement, and the read of the fixture names one movement, the way the read of the
 * recording named one movement.
 */
export function buildLedgerArtifact(count: number): LedgerArtifact {
  const rows = buildLedgerRows(count);
  const firstRow = rows[0];
  const reads: LedgerRead[] =
    firstRow === undefined
      ? []
      : [
          {
            evidence_id: "sql:1",
            seq: 19,
            tool: "query_ledger",
            sql: `SELECT * FROM (SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = '${firstRow.id}' ORDER BY applied_at) LIMIT 50`,
            columns: ["kind", "applied_rate", "applied_at"],
            row_count: 1,
            truncated: false,
            records: [firstRow.id],
            rows: [{ kind: "charge", applied_rate: "5.6679", applied_at: firstRow.at }],
          },
        ];
  return {
    schema_version: "1",
    scenario: "S01",
    snapshot_sha256: "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
    page_size: 50,
    accounts: [
      {
        id: "C-0412",
        kind: "customer",
        name: "Mariana Albuquerque Costa",
        rows,
        reads,
      },
    ],
  };
}

/** Every symbol this module exports, so that a reader sees the whole surface of the fixture at once. */
export const __all__ = [
  "LEDGER_ROW_KINDS",
  "LEDGER_ROW_STATUSES",
  "LEDGER_ROW_CURRENCIES",
  "buildLedgerRows",
  "buildLedgerArtifact",
] as const;
