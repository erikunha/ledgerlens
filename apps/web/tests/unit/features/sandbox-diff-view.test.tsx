/**
 * The test of the view of the difference of the branch.
 *
 * Why this test exists: the view of the difference is the only place where the interface shows
 * what a mutation did, and it must not invent anything. The values before and after are the
 * strings of the server, a decimal text is never rewritten, the currency of a monetary value is
 * shown next to it, the verdict is the label of the server and the rule that does not hold says
 * its own reason (ADR-044).
 *
 * Every case runs with no key and no network: the view reads the answer of the server and never
 * the network.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DiffView } from "@/features/sandbox/DiffView";
import type { BranchDiffBody } from "@/features/sandbox/types";

/**
 * The answer of the diff of a branch, with the overrides a case needs.
 *
 * Why the helper exists: every case needs the same answer, and a case that builds it by hand
 * would repeat the same six fields in every test.
 */
function diffOf(overrides: Partial<BranchDiffBody> = {}): BranchDiffBody {
  return {
    revision: 3,
    base_canonical_hash: "hash_of_the_base",
    canonical_hash: "hash_of_the_branch",
    diff: [
      {
        record: "refunds",
        record_id: "R0001",
        field: "refund_amount",
        before: "1000.00",
        after: "900.00",
        value_kind: "monetary",
        currency: "USD",
      },
      {
        record: "refunds",
        record_id: "R0001",
        field: "payout_amount",
        before: "900.5",
        after: "1200",
        value_kind: "monetary",
        currency: "USD",
      },
      {
        record: "refunds",
        record_id: "R0001",
        field: "status",
        before: "settled",
        after: "adjusted",
        value_kind: "non_monetary",
        currency: null,
      },
    ],
    invariants: [
      {
        identifier: "refund_not_above_paid",
        description: "the refund never goes above the amount that was paid",
        passed: true,
        reason: "",
      },
      {
        identifier: "refund_within_window",
        description: "the refund happens inside the window of the policy",
        passed: false,
        reason: "the refund of 900.00 happened after the window of thirty days",
      },
    ],
    verdict: {
      label: "within_expected_range",
      measure: "ratio_of_the_refund",
      value: "0.90",
      low: "0.80",
      high: "1.20",
      detail: "the refund stays inside the expected range",
    },
    ...overrides,
  };
}

describe("the view of the difference", () => {
  it("renders the values before and after exactly as they were sent", () => {
    render(<DiffView diff={diffOf()} />);

    expect(screen.getByText("1000.00")).toBeInTheDocument();
    expect(screen.getByText("900.00")).toBeInTheDocument();
    expect(screen.getByText("settled")).toBeInTheDocument();
    expect(screen.getByText("adjusted")).toBeInTheDocument();
  });

  it("never rewrites a decimal text", () => {
    render(<DiffView diff={diffOf()} />);

    expect(screen.queryByText("1,000.00")).not.toBeInTheDocument();
    expect(screen.queryByText("900")).not.toBeInTheDocument();
  });

  it("shows the currency code next to a monetary value", () => {
    render(<DiffView diff={diffOf()} />);

    const cell = screen.getByText("1000.00").closest("td");
    expect(cell).not.toBeNull();
    expect(cell?.textContent).toContain("USD");
  });

  it("shows the verdict with the label of the server", () => {
    render(<DiffView diff={diffOf()} />);

    expect(screen.getByText("within_expected_range")).toBeInTheDocument();
  });

  it("shows the invariants with the reason of the one that does not hold", () => {
    render(<DiffView diff={diffOf()} />);

    expect(
      screen.getByText("the refund of 900.00 happened after the window of thirty days"),
    ).toBeInTheDocument();
    expect(screen.getByText(/the rule holds/i)).toBeInTheDocument();
    expect(screen.getByText(/the rule does not hold/i)).toBeInTheDocument();
  });

  it("is a table with a caption and a header for every column", () => {
    render(<DiffView diff={diffOf()} />);

    const table = screen.getByRole("table", {
      name: "The difference between the published base and the branch",
    });
    expect(within(table).getAllByRole("columnheader")).toHaveLength(5);
  });

  it("gives every row a header that is the field of the row", () => {
    render(<DiffView diff={diffOf()} />);

    const table = screen.getByRole("table", {
      name: "The difference between the published base and the branch",
    });
    const rowHeaders = within(table).getAllByRole("rowheader");
    expect(rowHeaders.map((header) => header.textContent)).toEqual([
      "refund_amount",
      "payout_amount",
      "status",
    ]);
  });

  it("carries the identity of the record in the first column", () => {
    render(<DiffView diff={diffOf()} />);

    const table = screen.getByRole("table", {
      name: "The difference between the published base and the branch",
    });
    const firstCell = within(table).getAllByRole("cell")[0];
    expect(firstCell).toHaveTextContent("refunds");
    expect(firstCell).toHaveTextContent("R0001");
  });

  it("renders a decimal text of the server that has no trailing zero exactly as it was sent", () => {
    // The money of the sandbox is the text the server wrote: a text that arrives as `900.5` is
    // shown as `900.5` and never as `900.50`, and a text that arrives as `1200` is shown as
    // `1200` and never as `1200.00`.
    render(<DiffView diff={diffOf()} />);

    expect(screen.getByText("900.5")).toBeInTheDocument();
    expect(screen.getByText("1200")).toBeInTheDocument();
    expect(screen.queryByText("900.50")).not.toBeInTheDocument();
    expect(screen.queryByText("1200.00")).not.toBeInTheDocument();
  });

  it("shows a value that the server sent empty as not available and never as a blank", () => {
    // An empty text is an absent value: the cell says that the amount is not available, because a
    // unit written on a missing value would be an invention. The case covers the entries of the
    // difference and the values of the verdict.
    const base = diffOf();
    const diff = diffOf({
      verdict: { ...base.verdict, value: "", low: "", high: "" },
    });
    diff.diff[1] = { ...diff.diff[1]!, before: "", after: "" };

    render(<DiffView diff={diff} />);

    const table = screen.getByRole("table", {
      name: "The difference between the published base and the branch",
    });
    const rows = within(table).getAllByRole("row");
    const row = rows[2];
    expect(row).toBeDefined();
    expect(within(row as HTMLElement).getAllByText("Not available")).toHaveLength(2);
    for (const cell of within(row as HTMLElement).getAllByRole("cell")) {
      expect((cell.textContent ?? "").trim()).not.toBe("");
    }

    const value = screen.getByText("Value").nextElementSibling;
    expect(value?.textContent).toBe("Not available");

    const range = screen.getByText("Range").nextElementSibling;
    expect(range?.textContent).toBe("Not available");
  });

  it("carries the verdict of the case in a heading of level four", () => {
    render(<DiffView diff={diffOf()} />);

    expect(screen.getByRole("heading", { level: 4, name: /the verdict of the case/i })).toBeInTheDocument();
  });

  it("carries the rules of the domain in a heading, and the outline of the headings never skips a level", () => {
    // The rules of the domain are a part of the difference that a screen reader navigates by
    // heading, so they carry a heading of the level of the verdict, and the outline of the
    // headings of the view goes from one level to the next one without a jump.
    render(<DiffView diff={diffOf()} />);

    const rules = screen.getByRole("heading", { name: /the rules of the domain/i });
    expect(rules.tagName).toBe("H4");

    const headings = Array.from(
      document.querySelectorAll("h1, h2, h3, h4, h5, h6"),
    ) as HTMLHeadingElement[];
    expect(headings.length).toBeGreaterThan(1);

    let previous = 0;
    for (const heading of headings) {
      const level = Number(heading.tagName.slice(1));
      if (previous !== 0) {
        expect(level - previous).toBeLessThanOrEqual(1);
      }
      previous = level;
    }
  });
});
