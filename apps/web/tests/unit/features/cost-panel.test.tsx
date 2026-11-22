/**
 * The test of the panel of the cost of a run.
 *
 * Why this test exists: the panel of the cost is the panel that a run inspector drops into its run
 * view, and it presents the money of the run. The panel reuses the report of the models and
 * computes nothing: it shows the decimal text the server sent, it shows no amount at all when the
 * server knows no price, and it never writes a money amount of its own (FR-010, FR-011).
 *
 * Every case runs with no key and no network: the report is given to the panel directly.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CostPanel } from "@/features/evals/CostPanel";
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

describe("the panel of the cost of a run", () => {
  it("is a region a reader can reach by its name", () => {
    render(<CostPanel report={report()} running={false} />);

    expect(screen.getByRole("region", { name: /the cost of the run/i })).toBeInTheDocument();
  });

  it("shows the decimal text of the server and never a recomputed amount", () => {
    render(<CostPanel report={report()} running={false} />);

    expect(screen.getByText("0.012345")).toBeInTheDocument();
    expect(screen.getByText("0.011")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("0.0225");
    expect(document.body.textContent).not.toContain("22.5");
  });

  it("says that the price is unknown and shows no amount when the server knows no price", () => {
    render(
      <CostPanel report={report({ price_known: false, observed_cost_usd: null, estimated_cost_usd: null })} running={false} />,
    );

    expect(screen.getByText(/price of the model is unknown/i)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\d+[.,]\d+/);
    expect(document.body.textContent).not.toMatch(/USD/i);
  });

  it("says that the cost is not known yet while the run is going", () => {
    render(<CostPanel report={null} running={true} />);

    expect(screen.getByText(/not known yet/i)).toBeInTheDocument();
  });
});
