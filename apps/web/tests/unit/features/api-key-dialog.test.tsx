/**
 * The test of the dialog of the key.
 *
 * Why this test exists: the dialog is the only place where a provider key exists in the browser,
 * and the rule of the repository is that the key leaves it exactly once, through `onSubmit`. The
 * dialog also carries the gate of the consent: the send stays disabled until the box is ticked.
 *
 * Every case runs with no key and no network: the dialog never talks to the backend by itself.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiKeyDialog } from "@/features/models/ApiKeyDialog";

describe("the dialog of the key", () => {
  it("shows the key in a password field", () => {
    render(<ApiKeyDialog open providers={["openai", "anthropic"]} onSubmit={() => {}} onClose={() => {}} />);

    const field = screen.getByLabelText(/the key of your provider/i);
    expect(field).toHaveAttribute("type", "password");
  });

  it("keeps the value inside the dialog and gives it only to onSubmit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ApiKeyDialog open providers={["openai"]} onSubmit={onSubmit} onClose={() => {}} />);

    const field = screen.getByLabelText(/the key of your provider/i);
    await user.type(field, "sk-secret-value");
    await user.click(screen.getByRole("checkbox"));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(document.body.textContent).not.toContain("sk-secret-value");

    await user.click(screen.getByRole("button", { name: /send the key/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith({ provider: "openai", apiKey: "sk-secret-value" });
  });

  it("empties the field once the value left the dialog", async () => {
    const user = userEvent.setup();
    render(<ApiKeyDialog open providers={["openai"]} onSubmit={() => {}} onClose={() => {}} />);

    const field = screen.getByLabelText(/the key of your provider/i);
    await user.type(field, "sk-secret-value");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /send the key/i }));

    expect(field).toHaveValue("");
  });

  it("keeps the send disabled until the box of the consent is ticked", async () => {
    const user = userEvent.setup();
    render(<ApiKeyDialog open providers={["openai"]} onSubmit={() => {}} onClose={() => {}} />);

    const send = screen.getByRole("button", { name: /send the key/i });
    expect(send).toBeDisabled();

    await user.click(screen.getByRole("checkbox"));

    expect(send).toBeEnabled();
  });

  it("shows the refusal of the server where the action was", () => {
    render(
      <ApiKeyDialog
        open
        providers={["openai"]}
        error="the live mode is off because the product runs offline (LEDGERLENS_OFFLINE=1)"
        onSubmit={() => {}}
        onClose={() => {}}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(/LEDGERLENS_OFFLINE=1/);
  });
});
