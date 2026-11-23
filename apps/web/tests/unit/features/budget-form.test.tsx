/**
 * The test of the form of the budget.
 *
 * Why this test exists: the caps of the run are what bounds the calls of the live mode, and the
 * published contract refuses a cap that is out of its range. The form has to refuse it too, and
 * it has to say why, instead of sending a value the server will reject.
 *
 * Every case runs with no key and no network: the form never talks to the backend by itself.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BudgetForm } from "@/features/models/BudgetForm";
import { DEFAULT_RUN_LIMITS } from "@/lib/api/live";

describe("the form of the budget", () => {
  it("shows the four caps with their default values", () => {
    render(<BudgetForm limits={DEFAULT_RUN_LIMITS} onChange={() => {}} />);

    expect(screen.getByLabelText(/calls of the model/i)).toHaveValue(DEFAULT_RUN_LIMITS.max_model_calls);
    expect(screen.getByLabelText(/calls of the tools/i)).toHaveValue(DEFAULT_RUN_LIMITS.max_tool_calls);
    expect(screen.getByLabelText(/seconds of the run/i)).toHaveValue(DEFAULT_RUN_LIMITS.max_wall_seconds);
    expect(screen.getByLabelText(/tokens of the answer/i)).toHaveValue(DEFAULT_RUN_LIMITS.max_output_tokens);
  });

  it("refuses a value that is out of the range of the contract", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<BudgetForm limits={DEFAULT_RUN_LIMITS} onChange={onChange} />);

    const field = screen.getByLabelText(/calls of the model/i);
    await user.clear(field);
    await user.type(field, "99");

    expect(screen.getByRole("alert")).toHaveTextContent(/between 1 and 20/i);
    expect(onChange).not.toHaveBeenCalledWith(expect.objectContaining({ max_model_calls: 99 }));
  });

  it("gives the new caps when the value is inside the range", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<BudgetForm limits={DEFAULT_RUN_LIMITS} onChange={onChange} />);

    const field = screen.getByLabelText(/calls of the tools/i);
    await user.clear(field);
    await user.type(field, "7");

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ max_tool_calls: 7 }));
  });
});
