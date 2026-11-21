/**
 * The test of the panel of the cost.
 *
 * Why this test exists: this is the panel that shows money, and money is never a binary float. The
 * frontend does not compute an amount, does not multiply a price by a number of tokens and does not
 * format a money value: it renders the decimal text the server sent and renders nothing where the
 * server sent `null`. When the registry has no verified price, the panel says that the price is
 * unknown and shows no amount at all.
 *
 * Every case runs with no key and no network: the report is given to the panel directly.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CostReport } from "@/features/models/CostReport";
import type { CostReportBody } from "@/lib/api/live";

/** The report of a run that the server already closed. */
function report(overrides: Partial<CostReportBody> = {}): CostReportBody {
  return {
    run_id: "run_0123456789abcdef",
    status: "completed",
    model_calls: 2,
    tool_calls: 3,
    calls_by_model: { "gpt-4.1-mini": 2 },
    input_tokens: 1000,
    output_tokens: 500,
    elapsed_seconds: 4.5,
    observed_cost_usd: "0.012345",
    estimated_cost_usd: "0.011",
    price_known: true,
    money_cap_authoritative: false,
    cut_by: null,
    usage_without_reservation: [],
    note: "the server wrote this note",
    ...overrides,
  };
}

describe("the panel of the cost", () => {
  it("says that the price is unknown and shows no amount when the server knows no price", () => {
    render(
      <CostReport
        report={report({ price_known: false, observed_cost_usd: null, estimated_cost_usd: null })}
        running={false}
      />,
    );

    expect(screen.getByText(/price of the model is unknown/i)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\d+[.,]\d+/);
    expect(document.body.textContent).not.toMatch(/USD/i);
  });

  it("shows the decimal text of the server and never a recomputed amount", () => {
    render(<CostReport report={report()} running={false} />);

    expect(screen.getByText("0.012345")).toBeInTheDocument();
    expect(screen.getByText("0.011")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("0.0225");
    expect(document.body.textContent).not.toContain("22.5");
  });

  it("renders nothing where the server sent null", () => {
    render(<CostReport report={report({ estimated_cost_usd: null })} running={false} />);

    expect(screen.getByText("0.012345")).toBeInTheDocument();
    expect(screen.queryByText(/estimated cost/i)).toBeNull();
  });

  it("says that the cost is not known yet while the run is going", () => {
    render(<CostReport report={null} running={true} />);

    expect(screen.getByText(/not known yet/i)).toBeInTheDocument();
  });
});
