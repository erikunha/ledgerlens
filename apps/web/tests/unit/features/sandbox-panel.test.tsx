/**
 * The test of the panel of the branch of the visitor.
 *
 * Why this test exists: the panel is what tells the visitor which branch is on the screen, and
 * every rule of it comes from ADR-044. The panel never calculates anything: the identifier, the
 * revision and the expiry are the texts of the server. The branch that was CREATED and the branch
 * that was FOUND are told apart in words and not only with a colour, because a visitor who
 * reloaded the page has to understand that the work of the branch is still there. A refusal is
 * shown with the code and the message of the server, and a control that would do nothing says so
 * instead of disappearing under the focus of the visitor.
 *
 * Every case runs with no key and no network: the panel reads the state of the branch and never
 * the network.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BranchPanel } from "@/features/sandbox/BranchPanel";
import type { BranchState } from "@/features/sandbox/useBranch";

/** The identifier of the branch, as the server writes it. */
const BRANCH_ID = "sb_0123456789abcdef01234567";

/** The moment the branch dies, as the server writes it. */
const EXPIRES_AT = "2026-11-22T12:00:00+00:00";

/**
 * The state of a branch that is ready, with the overrides a case needs.
 *
 * Why the helper exists: every case needs the same state, and a case that builds it by hand
 * would repeat the same eleven fields in every test.
 */
function stateOf(overrides: Partial<BranchState> = {}): BranchState {
  return {
    phase: "ready",
    branchId: BRANCH_ID,
    revision: 3,
    expiresAt: EXPIRES_AT,
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

/**
 * Reads the value of one term of the panel.
 *
 * Why the helper reads the sibling of the term: the panel shows the values of the branch in a
 * list of terms, and asking for the value by its label keeps the test away from the markup.
 */
function valueOf(label: string): string | null {
  const term = screen.getByText(label);
  return term.nextElementSibling?.textContent ?? null;
}

describe("the panel of the branch", () => {
  it("shows the identifier, the revision and the expiry of the branch", () => {
    render(<BranchPanel state={stateOf()} onReset={() => {}} onEndSession={() => {}} />);

    expect(valueOf("Identifier of the branch")).toBe(BRANCH_ID);
    expect(valueOf("Revision")).toBe("3");
    expect(valueOf("Expires at")).toBe(EXPIRES_AT);
  });

  it("shows the label of the simulation", () => {
    render(<BranchPanel state={stateOf()} onReset={() => {}} onEndSession={() => {}} />);

    expect(screen.getByText("Simulation")).toBeInTheDocument();
  });

  it("says in words that the branch was created", () => {
    render(<BranchPanel state={stateOf({ created: true })} onReset={() => {}} onEndSession={() => {}} />);

    expect(screen.getByText(/branch was created/i)).toBeInTheDocument();
    expect(screen.queryByText(/branch was found/i)).not.toBeInTheDocument();
  });

  it("says in words that the branch was found and not created", () => {
    render(<BranchPanel state={stateOf({ created: false })} onReset={() => {}} onEndSession={() => {}} />);

    expect(screen.getByText(/branch was found/i)).toBeInTheDocument();
    expect(screen.queryByText(/branch was created/i)).not.toBeInTheDocument();
  });

  it("offers the reset of the branch and calls it back", async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    render(<BranchPanel state={stateOf()} onReset={onReset} onEndSession={() => {}} />);

    const reset = screen.getByRole("button", { name: /put the branch back at the base/i });
    expect(reset).not.toHaveAttribute("aria-disabled", "true");

    await user.click(reset);

    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it("offers the end of the session and calls it back", async () => {
    const user = userEvent.setup();
    const onEndSession = vi.fn();
    render(<BranchPanel state={stateOf()} onReset={() => {}} onEndSession={onEndSession} />);

    await user.click(screen.getByRole("button", { name: /end the session/i }));

    expect(onEndSession).toHaveBeenCalledTimes(1);
  });

  it("never disables a control: the reset that would do nothing says why", async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    render(
      <BranchPanel state={stateOf({ branchId: null })} onReset={onReset} onEndSession={() => {}} />,
    );

    const reset = screen.getByRole("button", { name: /put the branch back at the base/i });
    expect(reset).not.toBeDisabled();
    expect(reset).toHaveAttribute("aria-disabled", "true");

    const reason = screen.getByText(/there is no branch to put back/i);
    expect(reset.getAttribute("aria-describedby")).toBe(reason.getAttribute("id"));

    await user.click(reset);

    expect(onReset).not.toHaveBeenCalled();
  });

  it("shows the reason of a refusal with the code and the message of the server", () => {
    render(
      <BranchPanel
        state={stateOf({
          refusal: {
            code: "REVISION_CONFLICT",
            message: "the branch is at revision 3 and the request expected 2",
            retryable: false,
            request_id: "req_01",
          },
        })}
        onReset={() => {}}
        onEndSession={() => {}}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("REVISION_CONFLICT");
    expect(alert).toHaveTextContent("the branch is at revision 3 and the request expected 2");
  });

  it("is a heading of level two and its sections are of level three", () => {
    render(<BranchPanel state={stateOf()} onReset={() => {}} onEndSession={() => {}} />);

    expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3 }).length).toBeGreaterThan(0);
  });

  it("shows the canonical hash of the server exactly as it was sent", () => {
    // The hash is the text of the server, and the panel never rewrites it: a panel that cut the
    // hash would show a hash that is not the hash of the branch.
    const hash = "1f0c3a5b7d9e1123456789abcdef0123456789abcdef0123456789abcdef01";
    render(
      <BranchPanel
        state={stateOf({ canonicalHash: hash })}
        onReset={() => {}}
        onEndSession={() => {}}
      />,
    );

    expect(valueOf("Canonical hash")).toBe(hash);
    expect(screen.getByText(hash)).toBeInTheDocument();
  });

  it("never disables a control in any phase, and the blocked ones say why", () => {
    // The rule of the panel is about every phase of the machine, not only about the phase where
    // the branch is ready: a control that would do nothing stays in the keyboard, carries
    // `aria-disabled` and points at a reason a reader can hear.
    const phases: BranchState["phase"][] = ["idle", "opening", "ready", "refused"];

    for (const phase of phases) {
      const { unmount } = render(
        <BranchPanel
          state={stateOf({
            phase,
            branchId: phase === "ready" ? BRANCH_ID : null,
            revision: phase === "ready" ? 3 : null,
            expiresAt: phase === "ready" ? EXPIRES_AT : null,
            canonicalHash: phase === "ready" ? "hash_of_the_base" : null,
            branchState: phase === "ready" ? "active" : null,
            created: phase === "ready" ? true : null,
          })}
          onReset={() => {}}
          onEndSession={() => {}}
        />,
      );

      // No control of the panel ever carries the attribute `disabled`, in any phase.
      expect(document.querySelectorAll("[disabled]")).toHaveLength(0);

      const controls = Array.from(document.querySelectorAll("button, input, select, textarea"));
      expect(controls.length).toBeGreaterThan(0);

      const blocked = controls.filter(
        (control) => control.getAttribute("aria-disabled") === "true",
      );
      if (phase === "ready") {
        expect(blocked).toHaveLength(0);
      } else {
        // The phases without a branch block the reset, and the reset says why.
        expect(blocked.length).toBeGreaterThan(0);
      }

      for (const control of blocked) {
        const describedBy = control.getAttribute("aria-describedby");
        expect(describedBy).not.toBeNull();
        const reason = document.getElementById(describedBy ?? "");
        expect(reason).not.toBeNull();
        expect((reason?.textContent ?? "").trim().length).toBeGreaterThan(0);
      }

      unmount();
    }
  });

  it("marks the control that would do nothing with aria-disabled and points at its reason", () => {
    // The phase of the refusal has no branch, so the reset would do nothing, and the panel says
    // so in words instead of hiding the control.
    render(
      <BranchPanel
        state={stateOf({
          phase: "refused",
          branchId: null,
          revision: null,
          expiresAt: null,
          canonicalHash: null,
          branchState: null,
          created: null,
          refusal: {
            code: "BRANCH_EXPIRED",
            message: "the branch died",
            retryable: false,
            request_id: "req_01",
          },
        })}
        onReset={() => {}}
        onEndSession={() => {}}
      />,
    );

    expect(document.querySelectorAll("[disabled]")).toHaveLength(0);

    const reset = screen.getByRole("button", { name: /put the branch back at the base/i });
    expect(reset).not.toBeDisabled();
    expect(reset).toHaveAttribute("aria-disabled", "true");

    const reason = screen.getByText(/there is no branch to put back/i);
    expect(reset.getAttribute("aria-describedby")).toBe(reason.getAttribute("id"));
    expect((reason.textContent ?? "").trim().length).toBeGreaterThan(0);
  });
});
