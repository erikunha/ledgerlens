/**
 * The test of the form of the mutation of the sandbox.
 *
 * Why this test exists: the form builds the body of the five kinds of the catalog of the
 * mutations, and the body it builds is the body the server receives. The form refuses to send a
 * command with an empty required field and it names the empty field, because a visitor who does
 * not know which field is missing sends the same command again. The form never calculates: the
 * values before and after of the preview are the strings of the server. And the commit is offered
 * only after a valid preview, because the preview is the promise of the feature (ADR-044).
 *
 * Every case runs with no key and no network: the form gives its acts back as callbacks and never
 * calls the backend by itself.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MutationForm } from "@/features/sandbox/MutationForm";
import type {
  DuplicatePaymentCommand,
  FxOutageCommand,
  SandboxCommand,
} from "@/features/sandbox/types";
import type { BranchState } from "@/features/sandbox/useBranch";

/** The reason of the visitor, the note that travels with the command. */
const REASON = "the visitor asked for it";

/**
 * The state of a branch that is ready, with the overrides a case needs.
 *
 * Why the helper exists: every case needs the same state, and a case that builds it by hand
 * would repeat the same eleven fields in every test.
 */
function stateOf(overrides: Partial<BranchState> = {}): BranchState {
  return {
    phase: "ready",
    branchId: "sb_0123456789abcdef01234567",
    revision: 3,
    expiresAt: "2026-11-22T12:00:00+00:00",
    canonicalHash: "hash_of_the_base",
    branchState: "active",
    created: true,
    preview: null,
    diff: null,
    history: null,
    refusal: null,
    ...overrides,
  };
}

/** The preview of a command that the domain accepts, with the values the server sent. */
function previewOf(overrides: Partial<NonNullable<BranchState["preview"]>> = {}): NonNullable<
  BranchState["preview"]
> {
  return {
    valid: true,
    revision: 3,
    idempotencyKey: "idem_01",
    command: {
      kind: "refund.apply_fx_adjustment",
      data: { refund_id: "R0001", applied_rate: "1.0850", effective_at: "2026-11-20T10:00:00+00:00" },
    } as SandboxCommand,
    answer: {
      valid: true,
      kind: "refund.apply_fx_adjustment",
      revision: 3,
      current_canonical_hash: "hash_before",
      projected_canonical_hash: "hash_after",
      before: { value: "100.00", currency: "USD" },
      after: { value: "90.00", currency: "USD" },
      records: [],
      diff: [],
      invariants: [],
      verdict: {
        label: "within_expected_range",
        measure: "ratio_of_the_refund",
        value: "0.90",
        low: "0.80",
        high: "1.20",
        detail: "the refund stays inside the expected range",
      },
    },
    ...overrides,
  };
}

/**
 * Fills one field of the form.
 *
 * Why the helper clears the field first: the field starts empty, and a test that typed over an
 * empty field would depend on the order of the keystrokes.
 */
async function fill(user: ReturnType<typeof userEvent.setup>, label: RegExp, value: string): Promise<void> {
  const field = screen.getByLabelText(label);
  await user.clear(field);
  await user.type(field, value);
}

/**
 * Fills the form with the command that the preview of the case holds.
 *
 * Why the helper exists: the commit is offered only when the command of the form is the command
 * that was previewed, and a case that proves it has to put the same command in the form.
 */
async function fillThePreviewedCommand(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await fill(user, /identifier of the refund/i, "R0001");
  await fill(user, /rate applied to the refund/i, "1.0850");
  await fill(user, /moment the adjustment takes effect/i, "2026-11-20T10:00:00+00:00");
}

/**
 * The type of the field of the error code, as the published schema declares it.
 *
 * Why the guard is here: the schema declares the field `error_code` with the enum
 * `["UPSTREAM_UNAVAILABLE"]`, and the type of the front has to be that enum. The `@ts-expect-error`
 * directive fails the type check of the repository when the type is wider than the schema.
 */
const ALLOWED_ERROR_CODE: FxOutageCommand["data"]["error_code"] = "UPSTREAM_UNAVAILABLE";

// @ts-expect-error the published schema declares only the code UPSTREAM_UNAVAILABLE
const REFUSED_ERROR_CODE: FxOutageCommand["data"]["error_code"] = "FX_TIMEOUT";

/**
 * The type of the count of seconds, as the published schema declares it.
 *
 * Why the guard is here: the schema declares the field `elapsed_seconds` as an integer between 1
 * and 300, and the type of the front has to say that range.
 */
const ALLOWED_ELAPSED_SECONDS: DuplicatePaymentCommand["data"]["elapsed_seconds"] = 300;

// @ts-expect-error the published schema declares a count of seconds between 1 and 300
const REFUSED_ELAPSED_SECONDS: DuplicatePaymentCommand["data"]["elapsed_seconds"] = 301;

describe("the form of the mutation", () => {
  it("carries the codes and the counts of seconds that the published schema declares", () => {
    // The constants of the case are a type guard: the type of the field of the error code is the
    // enum of the schema and the type of the count of seconds is the range of the schema, and the
    // `@ts-expect-error` directives above fail the type check of the repository when the types
    // are wider than the contract.
    expect(ALLOWED_ERROR_CODE).toBe("UPSTREAM_UNAVAILABLE");
    expect(REFUSED_ERROR_CODE).toBe("FX_TIMEOUT");
    expect(ALLOWED_ELAPSED_SECONDS).toBe(300);
    expect(REFUSED_ELAPSED_SECONDS).toBe(301);
  });

  it("builds the body of the adjustment of the rate of a refund", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(
      <MutationForm
        state={stateOf()}
        canCommit={false}
        commitReason="preview the command first"
        onPreview={onPreview}
        onCommit={() => {}}
      />,
    );

    await user.selectOptions(screen.getByLabelText(/kind of the mutation/i), "refund.apply_fx_adjustment");
    await fill(user, /identifier of the refund/i, "R0001");
    await fill(user, /rate applied to the refund/i, "1.0850");
    await fill(user, /moment the adjustment takes effect/i, "2026-11-20T10:00:00+00:00");
    await fill(user, /currency of the record/i, "USD");
    await fill(user, /reason of the visitor/i, REASON);
    await user.click(screen.getByRole("button", { name: /preview the command/i }));

    expect(onPreview).toHaveBeenCalledWith({
      kind: "refund.apply_fx_adjustment",
      data: {
        refund_id: "R0001",
        applied_rate: "1.0850",
        effective_at: "2026-11-20T10:00:00+00:00",
        currency: "USD",
      },
      reason: REASON,
    });
  });

  it("builds the body of the second charge of a payment", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(
      <MutationForm
        state={stateOf()}
        canCommit={false}
        commitReason="preview the command first"
        onPreview={onPreview}
        onCommit={() => {}}
      />,
    );

    await user.selectOptions(screen.getByLabelText(/kind of the mutation/i), "payment.simulate_duplicate");
    await fill(user, /identifier of the transaction/i, "TX0001");
    await fill(user, /seconds since the first charge/i, "90");
    await fill(user, /currency of the record/i, "USD");
    await user.click(screen.getByRole("button", { name: /preview the command/i }));

    expect(onPreview).toHaveBeenCalledWith({
      kind: "payment.simulate_duplicate",
      data: { transaction_id: "TX0001", elapsed_seconds: 90, currency: "USD" },
    });
  });

  it("builds the body of the new deadline of a chargeback", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(
      <MutationForm
        state={stateOf()}
        canCommit={false}
        commitReason="preview the command first"
        onPreview={onPreview}
        onCommit={() => {}}
      />,
    );

    await user.selectOptions(screen.getByLabelText(/kind of the mutation/i), "chargeback.change_deadline");
    await fill(user, /identifier of the chargeback/i, "CB0001");
    await fill(user, /new deadline/i, "2026-12-01");
    await fill(user, /currency of the record/i, "EUR");
    await user.click(screen.getByRole("button", { name: /preview the command/i }));

    expect(onPreview).toHaveBeenCalledWith({
      kind: "chargeback.change_deadline",
      data: { chargeback_id: "CB0001", new_deadline: "2026-12-01", currency: "EUR" },
    });
  });

  it("builds the body of the outage of the tool of the rate", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(
      <MutationForm
        state={stateOf()}
        canCommit={false}
        commitReason="preview the command first"
        onPreview={onPreview}
        onCommit={() => {}}
      />,
    );

    await user.selectOptions(screen.getByLabelText(/kind of the mutation/i), "tool.fx_outage");
    await fill(user, /error code of the tool/i, "UPSTREAM_UNAVAILABLE");
    await user.click(screen.getByRole("button", { name: /preview the command/i }));

    expect(onPreview).toHaveBeenCalledWith({
      kind: "tool.fx_outage",
      data: { enabled: true, error_code: "UPSTREAM_UNAVAILABLE" },
    });
  });

  it("refuses an error code that the published schema does not declare", async () => {
    // The schema declares the field `error_code` with the enum `["UPSTREAM_UNAVAILABLE"]`, and the
    // form refuses any other code in its own words, before the server does.
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(
      <MutationForm
        state={stateOf()}
        canCommit={false}
        commitReason="preview the command first"
        onPreview={onPreview}
        onCommit={() => {}}
      />,
    );

    await user.selectOptions(screen.getByLabelText(/kind of the mutation/i), "tool.fx_outage");
    await fill(user, /error code of the tool/i, "FX_TIMEOUT");
    await user.click(screen.getByRole("button", { name: /preview the command/i }));

    expect(onPreview).not.toHaveBeenCalled();
    expect(
      screen.getByText(/The field "Error code of the tool" must be UPSTREAM_UNAVAILABLE\./),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/error code of the tool/i)).toHaveAttribute("aria-invalid", "true");
  });

  it("refuses a count of seconds that the published schema does not declare", async () => {
    // The schema declares the field `elapsed_seconds` as an integer between 1 and 300, and the
    // form refuses a count outside the range before the server does.
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(
      <MutationForm
        state={stateOf()}
        canCommit={false}
        commitReason="preview the command first"
        onPreview={onPreview}
        onCommit={() => {}}
      />,
    );

    await user.selectOptions(screen.getByLabelText(/kind of the mutation/i), "payment.simulate_duplicate");
    await fill(user, /identifier of the transaction/i, "TX0001");
    await fill(user, /seconds since the first charge/i, "301");
    await user.click(screen.getByRole("button", { name: /preview the command/i }));

    expect(onPreview).not.toHaveBeenCalled();
    expect(
      screen.getByText(/must be a whole number of seconds between 1 and 300\./),
    ).toBeInTheDocument();
  });

  it("builds the body of the untrusted note on a record", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(
      <MutationForm
        state={stateOf()}
        canCommit={false}
        commitReason="preview the command first"
        onPreview={onPreview}
        onCommit={() => {}}
      />,
    );

    await user.selectOptions(screen.getByLabelText(/kind of the mutation/i), "record.inject_untrusted_note");
    await fill(user, /identifier of the record/i, "R0001");
    await fill(user, /text of the note/i, "the note of the visitor");
    await user.click(screen.getByRole("button", { name: /preview the command/i }));

    expect(onPreview).toHaveBeenCalledWith({
      kind: "record.inject_untrusted_note",
      data: { record_id: "R0001", text: "the note of the visitor" },
    });
  });

  it("refuses to send a command with an empty required field and it names the empty field", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(
      <MutationForm
        state={stateOf()}
        canCommit={false}
        commitReason="preview the command first"
        onPreview={onPreview}
        onCommit={() => {}}
      />,
    );

    await user.selectOptions(screen.getByLabelText(/kind of the mutation/i), "refund.apply_fx_adjustment");
    await fill(user, /identifier of the refund/i, "R0001");
    await user.click(screen.getByRole("button", { name: /preview the command/i }));

    expect(onPreview).not.toHaveBeenCalled();
    expect(
      screen.getByText(/The field "Rate applied to the refund" is required\./),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/rate applied to the refund/i)).toHaveAttribute("aria-invalid", "true");
  });

  it("shows the preview with the values before and after as the strings of the server", () => {
    render(
      <MutationForm
        state={stateOf({ preview: previewOf() })}
        canCommit
        commitReason={null}
        onPreview={() => {}}
        onCommit={() => {}}
      />,
    );

    expect(screen.getByText("100.00")).toBeInTheDocument();
    expect(screen.getByText("90.00")).toBeInTheDocument();
    expect(screen.getAllByText("USD")).toHaveLength(2);
  });

  it("shows a value of the server that has no trailing zero exactly as it was sent", () => {
    // The money of the sandbox is the text the server wrote: a text that arrives as `900.5` is
    // shown as `900.5` and never as `900.50`.
    const preview = previewOf();
    preview.answer.before = { value: "900.5", currency: "USD" };
    preview.answer.after = { value: "1200", currency: "USD" };

    render(
      <MutationForm
        state={stateOf({ preview })}
        canCommit
        commitReason={null}
        onPreview={() => {}}
        onCommit={() => {}}
      />,
    );

    expect(screen.getByText("900.5")).toBeInTheDocument();
    expect(screen.getByText("1200")).toBeInTheDocument();
    expect(screen.queryByText("900.50")).not.toBeInTheDocument();
    expect(screen.queryByText("1200.00")).not.toBeInTheDocument();
  });

  it("offers the commit only after a valid preview", async () => {
    const user = userEvent.setup();
    const onCommit = vi.fn();
    render(
      <MutationForm
        state={stateOf({ preview: previewOf() })}
        canCommit
        commitReason={null}
        onPreview={() => {}}
        onCommit={onCommit}
      />,
    );

    await fillThePreviewedCommand(user);

    const commit = screen.getByRole("button", { name: /commit the command/i });
    expect(commit).not.toHaveAttribute("aria-disabled", "true");

    await user.click(commit);

    expect(onCommit).toHaveBeenCalledTimes(1);
  });

  it("does not offer the commit after a change of the kind of the command", async () => {
    // The preview is the promise of the feature, and the promise is about ONE command: a change of
    // the kind is a change of the command, and the commit of the previous command is not what the
    // visitor asked for.
    const user = userEvent.setup();
    render(
      <MutationForm
        state={stateOf({ preview: previewOf() })}
        canCommit
        commitReason={null}
        onPreview={() => {}}
        onCommit={() => {}}
      />,
    );

    await fillThePreviewedCommand(user);

    const commit = screen.getByRole("button", { name: /commit the command/i });
    expect(commit).not.toHaveAttribute("aria-disabled", "true");

    await user.selectOptions(screen.getByLabelText(/kind of the mutation/i), "payment.simulate_duplicate");

    expect(commit).toHaveAttribute("aria-disabled", "true");
    expect(commit).not.toBeDisabled();
    const reason = screen.getByText(/preview the command again/i);
    expect(commit.getAttribute("aria-describedby")).toBe(reason.getAttribute("id"));
  });

  it("does not offer the commit after a change of the fields of the command", async () => {
    // A field the visitor changes is a change of the command, and the preview of the previous
    // command does not promise anything about the new one.
    const user = userEvent.setup();
    render(
      <MutationForm
        state={stateOf({ preview: previewOf() })}
        canCommit
        commitReason={null}
        onPreview={() => {}}
        onCommit={() => {}}
      />,
    );

    await fillThePreviewedCommand(user);

    const commit = screen.getByRole("button", { name: /commit the command/i });
    expect(commit).not.toHaveAttribute("aria-disabled", "true");

    await fill(user, /rate applied to the refund/i, "1.0900");

    expect(commit).toHaveAttribute("aria-disabled", "true");
    expect(commit).not.toBeDisabled();
    const reason = screen.getByText(/preview the command again/i);
    expect(commit.getAttribute("aria-describedby")).toBe(reason.getAttribute("id"));
  });

  it("never offers the commit when there is no valid preview and it says why", () => {
    render(
      <MutationForm
        state={stateOf({ preview: previewOf({ valid: false }) })}
        canCommit={false}
        commitReason="the command would break a rule of the domain"
        onPreview={() => {}}
        onCommit={() => {}}
      />,
    );

    const commit = screen.getByRole("button", { name: /commit the command/i });
    expect(commit).not.toBeDisabled();
    expect(commit).toHaveAttribute("aria-disabled", "true");

    const reason = screen.getByText("the command would break a rule of the domain");
    expect(commit.getAttribute("aria-describedby")).toBe(reason.getAttribute("id"));
  });

  it("never disables the preview that would do nothing and it says why", () => {
    render(
      <MutationForm
        state={stateOf({ branchId: null })}
        canCommit={false}
        commitReason="open a scenario first"
        onPreview={() => {}}
        onCommit={() => {}}
      />,
    );

    const preview = screen.getByRole("button", { name: /preview the command/i });
    expect(preview).not.toBeDisabled();
    expect(preview).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText(/there is no branch to preview/i)).toBeInTheDocument();
  });
});
