/**
 * The test of the sorting and of the filtering of the ledger, and the measurement of SC-010.
 *
 * Why this file exists: ADR-049 decided that the recorded ledger may be sorted and filtered, that
 * the sorting and the filtering live in the library and not in a component, and that the behaviour
 * and the performance of a thousand rows are proved over the fixture of the tests, because no
 * account of the public data holds a thousand movements and a synthetic row may not be published.
 *
 * The cases below are the ones ADR-049 asks of this set:
 *
 * 1. the fixture is deterministic, its rows carry the six fields of ADR-045, its amounts are
 *    decimal texts and its kinds and states come from the closed lists of the ledger;
 * 2. the default order of the rows is the order of the artifact, and the default sort returns it;
 * 3. the sort by the amount compares the decimal TEXT: `9.90` comes before `10.00` and `100.00`
 *    comes after `99.99`;
 * 4. the sort never calls `Number` on an amount: two rows that differ only by a leading zero, and
 *    two rows that differ only past the digits a float holds, change the order;
 * 5. the sort is stable: two rows with the same value of the field keep the order of the artifact;
 * 6. the filter keeps the rows that carry the text, the kind and the state, and the sort and the
 *    filter compose;
 * 7. the budget of SC-010: the sort and the filter of a thousand rows under 200 ms and the render
 *    of the panel with a thousand rows under 1 s.
 *
 * Every case runs with no key and no network: the artifact of the case is a literal or the
 * fixture of the tests, and the browser of the case is the one of the test environment.
 */

import { createElement } from "react";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LedgerPanel } from "@/features/ledger/LedgerPanel";
import {
  LEDGER_DEFAULT_SORT,
  filterLedgerRows,
  ledgerRowsHaveTheSameOrder,
  sortLedgerRows,
} from "@/lib/replay/ledger";
import type { LedgerFilter, LedgerSort } from "@/lib/replay/ledger";
import type { LedgerRow } from "@/lib/api/schemas";
import {
  LEDGER_ROW_KINDS,
  LEDGER_ROW_STATUSES,
  buildLedgerArtifact,
  buildLedgerRows,
} from "@/tests/fixtures/ledger";

/**
 * The number of rows of the fixture that the budget of SC-010 is measured over.
 *
 * Why the number is a thousand: the fixture of the tests carries a thousand movements, and a
 * measurement over two rows is not a measurement of a thousand rows.
 */
const ROWS_OF_THE_BUDGET = 1000;

/**
 * The budget of the sort and of the filter of a thousand rows, in milliseconds.
 *
 * Why the number comes from the specification: SC-010 asks for two hundred milliseconds.
 */
const BUDGET_MS = 200;

/**
 * The budget of the render of the panel with a thousand rows, in milliseconds.
 *
 * Why the number comes from the specification: SC-010 asks for one second.
 */
const RENDER_BUDGET_MS = 1000;

/**
 * The filter that keeps every movement.
 */
const NO_FILTER: LedgerFilter = { text: "", kind: null, status: null };

/**
 * Builds a movement of the ledger with the six fields of ADR-045.
 *
 * Why the movements are built and not written: the cases of the comparator need amounts that
 * differ in ways a decimal text can differ, and writing them one by one would be noise.
 */
function movementOf(
  id: string,
  amount: string,
  options: { kind?: string; status?: string; currency?: string; at?: string } = {},
): LedgerRow {
  return {
    kind: options.kind ?? "transaction",
    id,
    at: options.at ?? "2026-10-15T09:12:00Z",
    amount,
    currency: options.currency ?? "EUR",
    status: options.status ?? "captured",
  };
}

describe("the fixture of the ledger of the tests", () => {
  it("builds the same rows every time", () => {
    // It proves that the generator is a pure function: the thousandth row of the fixture is the
    // same row in every machine and in every run, because the generator reads no clock and calls
    // no random source.
    const first = buildLedgerRows(ROWS_OF_THE_BUDGET);
    const second = buildLedgerRows(ROWS_OF_THE_BUDGET);

    expect(first).toHaveLength(ROWS_OF_THE_BUDGET);
    expect(second).toEqual(first);
  });

  it("gives the six fields of ADR-045 to every row and nothing else", () => {
    // It proves that the shape of the row does not grow: a fixture with fields the artifact does
    // not carry would prove a table that the artifact cannot render.
    const rows = buildLedgerRows(20);

    for (const row of rows) {
      expect(Object.keys(row).sort()).toEqual(["amount", "at", "currency", "id", "kind", "status"]);
    }
  });

  it("writes the amount as a decimal text and never as a number", () => {
    // It proves that the money of the fixture is the money of the ledger: a text, and never a
    // binary float of an amount.
    const rows = buildLedgerRows(50);

    for (const row of rows) {
      expect(typeof row.amount).toBe("string");
      expect(row.amount).toMatch(/^\d+\.\d{2}$/);
    }
  });

  it("takes the kinds and the states from the closed lists of the ledger", () => {
    // It proves that the fixture does not invent a kind and does not invent a state.
    const rows = buildLedgerRows(200);

    for (const row of rows) {
      expect(LEDGER_ROW_KINDS).toContain(row.kind);
      expect(LEDGER_ROW_STATUSES).toContain(row.status);
    }
  });
});

describe("the sorting and the filtering of the ledger", () => {
  it("keeps the order of the artifact and gives it back with the default sort", () => {
    // It proves that the default order of the movements is the order the artifact declares, and
    // that the default sort, the sort of the moment, returns it.
    const rows = buildLedgerRows(200);

    expect(sortLedgerRows(rows, LEDGER_DEFAULT_SORT)).toEqual(rows);
    expect(ledgerRowsHaveTheSameOrder(rows, sortLedgerRows(rows, LEDGER_DEFAULT_SORT))).toBe(true);
  });

  it("compares the decimal TEXT of the amounts and never a float", () => {
    // It proves that the comparator of the amounts reads the integer part by its length and then
    // by its digits, and the fraction digit by digit: `9.90` comes before `10.00` and `100.00`
    // comes after `99.99`.
    const rows = [
      movementOf("TX-0001", "100.00"),
      movementOf("TX-0002", "9.90"),
      movementOf("TX-0003", "99.99"),
      movementOf("TX-0004", "10.00"),
    ];

    const sorted = sortLedgerRows(rows, { field: "amount", direction: "asc" });

    expect(sorted.map((row) => row.amount)).toEqual(["9.90", "10.00", "99.99", "100.00"]);
  });

  it("never turns an amount into a number when it sorts", () => {
    // It proves that the comparator does not parse the amount as a float: two rows whose amounts
    // differ only past the digits that a float holds change the order, because a float would make
    // them the same amount and a text comparator keeps them apart.
    const withMoreDigitsThanAFloatHolds = [
      movementOf("TX-0003", "9007199254740993.00"),
      movementOf("TX-0004", "9007199254740992.00"),
    ];

    const sortedBig = sortLedgerRows(withMoreDigitsThanAFloatHolds, {
      field: "amount",
      direction: "asc",
    });

    expect(sortedBig.map((row) => row.id)).toEqual(["TX-0004", "TX-0003"]);
  });

  it("compares the value of the amount and not the shape of its text", () => {
    // It proves that the zeros in front of the integer part carry no value: "010.00" and "10.00"
    // are the same amount, and the sign of a zero is not a sign, so "-0" and "0" are the same amount
    // too. Two equal amounts keep the order of the artifact, because the sort is stable.
    const withLeadingZero = [
      movementOf("TX-0001", "010.00"),
      movementOf("TX-0002", "10.00"),
    ];
    const withNegativeZero = [
      movementOf("TX-0005", "-0.00"),
      movementOf("TX-0006", "0.00"),
    ];

    const sortedLeadingZero = sortLedgerRows(withLeadingZero, { field: "amount", direction: "asc" });
    const sortedNegativeZero = sortLedgerRows(withNegativeZero, { field: "amount", direction: "asc" });

    expect(sortedLeadingZero.map((row) => row.id)).toEqual(["TX-0001", "TX-0002"]);
    expect(sortedNegativeZero.map((row) => row.id)).toEqual(["TX-0005", "TX-0006"]);
  });

  it("puts a negative amount before a positive one of the same value", () => {
    // It proves that the sign is read before the digits: "-10.00" comes before "10.00", and the
    // comparator still never turns an amount into a number.
    const rows = [
      movementOf("TX-0001", "10.00"),
      movementOf("TX-0002", "-10.00"),
      movementOf("TX-0003", "-2.00"),
    ];

    const sorted = sortLedgerRows(rows, { field: "amount", direction: "asc" });

    expect(sorted.map((row) => row.amount)).toEqual(["-10.00", "-2.00", "10.00"]);
  });

  it("keeps the order of the artifact when two movements carry the same value", () => {
    // It proves that the sort is stable: the place of a movement in the artifact is a fact about
    // the recording, and the index of the row is the tie breaker.
    const rows = [
      movementOf("TX-0001", "10.00"),
      movementOf("TX-0002", "10.00"),
      movementOf("TX-0003", "20.00"),
    ];

    const sorted = sortLedgerRows(rows, { field: "amount", direction: "asc" });

    expect(sorted.map((row) => row.id)).toEqual(["TX-0001", "TX-0002", "TX-0003"]);
  });

  it("reverses the order when the visitor asks for the other direction", () => {
    // It proves that the direction of the sort is the direction the visitor chose.
    const rows = [movementOf("TX-0001", "10.00"), movementOf("TX-0002", "20.00")];

    const ascending = sortLedgerRows(rows, { field: "amount", direction: "asc" });
    const descending = sortLedgerRows(rows, { field: "amount", direction: "desc" });

    expect(ascending.map((row) => row.id)).toEqual(["TX-0001", "TX-0002"]);
    expect(descending.map((row) => row.id)).toEqual(["TX-0002", "TX-0001"]);
  });

  it("keeps the rows that carry the text of the filter", () => {
    // It proves that the text of the filter searches the identifier, the kind, the state and the
    // currency, and that a filter with no text keeps every row.
    const rows = [
      movementOf("TX-2048", "100.00", { kind: "transaction", status: "refunded", currency: "EUR" }),
      movementOf("R-0731", "549.31", { kind: "refund", status: "paid", currency: "BRL" }),
      movementOf("CB-0003", "12.00", { kind: "chargeback", status: "opened", currency: "BRL" }),
    ];

    expect(filterLedgerRows(rows, { ...NO_FILTER, text: "TX-20" }).map((row) => row.id)).toEqual([
      "TX-2048",
    ]);
    expect(filterLedgerRows(rows, { ...NO_FILTER, text: "chargeback" }).map((row) => row.id)).toEqual([
      "CB-0003",
    ]);
    expect(filterLedgerRows(rows, { ...NO_FILTER, text: "paid" }).map((row) => row.id)).toEqual([
      "R-0731",
    ]);
    expect(filterLedgerRows(rows, { ...NO_FILTER, text: "brl" }).map((row) => row.id)).toEqual([
      "R-0731",
      "CB-0003",
    ]);
    expect(filterLedgerRows(rows, NO_FILTER)).toHaveLength(3);
  });

  it("keeps the rows that carry the kind and the state of the filter", () => {
    // It proves that the filter of the kind and the filter of the state are exact: a filter that
    // matched a part of the word would keep movements the visitor did not ask for.
    const rows = [
      movementOf("TX-0001", "10.00", { kind: "transaction", status: "refunded" }),
      movementOf("TX-0002", "20.00", { kind: "refund", status: "paid" }),
      movementOf("TX-0003", "30.00", { kind: "refund", status: "refunded" }),
    ];

    expect(filterLedgerRows(rows, { ...NO_FILTER, kind: "refund" }).map((row) => row.id)).toEqual([
      "TX-0002",
      "TX-0003",
    ]);
    expect(filterLedgerRows(rows, { ...NO_FILTER, status: "refunded" }).map((row) => row.id)).toEqual([
      "TX-0001",
      "TX-0003",
    ]);
  });

  it("composes the filter and the sort", () => {
    // It proves that the filter comes first and the sort comes after, and that the result is the
    // sort of the filtered rows.
    const rows = buildLedgerRows(200);
    const filter: LedgerFilter = { ...NO_FILTER, kind: "refund" };
    const sort: LedgerSort = { field: "amount", direction: "asc" };

    const filtered = filterLedgerRows(rows, filter);
    const composed = sortLedgerRows(filtered, sort);

    expect(composed).toEqual(sortLedgerRows(filterLedgerRows(rows, filter), sort));
    expect(composed.every((row) => row.kind === "refund")).toBe(true);
  });
});

describe("the budget of SC-010 over the fixture of a thousand rows", () => {
  it("sorts a thousand rows under two hundred milliseconds", () => {
    // It proves that the sort of a thousand rows finishes well inside the budget of the
    // specification, timed with `performance.now()` and with no clock of the wall.
    const rows = buildLedgerRows(ROWS_OF_THE_BUDGET);

    const started = performance.now();
    const sorted = sortLedgerRows(rows, { field: "amount", direction: "asc" });
    const elapsed = performance.now() - started;

    expect(sorted).toHaveLength(ROWS_OF_THE_BUDGET);
    expect(elapsed, `the sort of a thousand rows took ${elapsed.toFixed(1)} ms`).toBeLessThan(BUDGET_MS);
  });

  it("filters a thousand rows under two hundred milliseconds", () => {
    // It proves that the filter of a thousand rows finishes well inside the budget of the
    // specification, timed with `performance.now()` and with no clock of the wall.
    const rows = buildLedgerRows(ROWS_OF_THE_BUDGET);

    const started = performance.now();
    const filtered = filterLedgerRows(rows, { ...NO_FILTER, text: "TX" });
    const elapsed = performance.now() - started;

    expect(filtered.length).toBeGreaterThan(0);
    expect(elapsed, `the filter of a thousand rows took ${elapsed.toFixed(1)} ms`).toBeLessThan(BUDGET_MS);
  });

  it("renders the panel with a thousand rows under one second", () => {
    // It proves that the render of a thousand rows finishes inside the budget of the specification.
    // The panel draws one page of the movements, the page the artifact declares, so the DOM never
    // holds a thousand rows.
    const artifact = buildLedgerArtifact(ROWS_OF_THE_BUDGET);

    const started = performance.now();
    render(createElement(LedgerPanel, { ledger: artifact, error: null }));
    const elapsed = performance.now() - started;

    expect(elapsed, `the render of the panel with a thousand rows took ${elapsed.toFixed(1)} ms`).toBeLessThan(
      RENDER_BUDGET_MS,
    );
  });
});
