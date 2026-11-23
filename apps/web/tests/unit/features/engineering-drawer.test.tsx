/**
 * The test of the focus of the engineering drawer.
 *
 * Why this test exists: the drawer of the engineering tour is opened by a control that lives
 * outside of it, and the primitive of the dialog returns the focus to the element it knows, which
 * is not that control. The focus landed on the body of the page when the drawer closed, and a
 * visitor who opened a window with the keyboard and closed it with the Escape key had to find his
 * way back from scratch. The rule of the repository is that the focus returns to the control that
 * opened the drawer (ADR-046).
 *
 * Every case runs with no key and no network: the drawer is a component of the interface and
 * nothing else.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { EngineeringTour } from "@/features/architecture/EngineeringDrawer";

/**
 * The commit of the checkout that the links of the drawer open.
 *
 * Why the case carries a commit: the tour does not read the repository, so it names a commit of
 * forty hexadecimal characters and the drawer shows the links of that tree (ADR-046).
 */
const COMMIT = "0123456789abcdef0123456789abcdef01234567";

describe("the focus of the engineering drawer", () => {
  it("gives the focus back to the control that opened it when it closes", async () => {
    const user = userEvent.setup();
    render(<EngineeringTour commit={COMMIT} />);

    const trigger = screen.getByRole("button", {
      name: "Open the engineering drawer for the Query guard",
    });

    await user.click(trigger);
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(trigger).toHaveFocus();
    });
  });

  it("closes the drawer with the Escape key", async () => {
    const user = userEvent.setup();
    render(<EngineeringTour commit={COMMIT} />);

    await user.click(
      screen.getByRole("button", { name: "Open the engineering drawer for the Query guard" }),
    );
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("carries the name of the node it was opened with in its first sentence", async () => {
    const user = userEvent.setup();
    render(<EngineeringTour commit={COMMIT} />);

    await user.click(
      screen.getByRole("button", { name: "Open the engineering drawer for the Query guard" }),
    );

    const drawer = await screen.findByRole("dialog");

    expect(drawer).toHaveTextContent("This drawer is about the Query guard.");
  });

  it("never traps the keyboard behind the drawer that is closed", async () => {
    const user = userEvent.setup();
    render(<EngineeringTour commit={COMMIT} />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Open the engineering drawer for the Query guard" }),
    );
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
