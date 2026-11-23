/**
 * The test of the four primitives of the design package.
 *
 * Why this test exists: the tabs, the dialog, the sheet and the skeleton are the building blocks of the interface of
 * the replay, and they carry the promises that the rest of the site relies on. The tabs carry the name of their group
 * and show one panel at a time. The dialog and the sheet are windows that a keyboard user can leave behind, so they
 * answer the Escape key and they carry a name. The skeleton announces the thing that is loading and stays silent when
 * the panel that is loading already carries the name.
 *
 * Every case runs with no key and no network: the primitives are components of the interface and nothing else.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Dialog } from "@/components/ui/Dialog";
import { Sheet } from "@/components/ui/Sheet";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs, type TabItem } from "@/components/ui/Tabs";

/** The tabs of the case, the four sections of the replay. */
const ITEMS: readonly TabItem[] = [
  { value: "execution", label: "Execution", content: <p>The tree of the investigation</p> },
  { value: "evidence", label: "Evidence", content: <p>The evidence of the answer</p> },
  { value: "decision", label: "Decision", content: <p>The claims of the answer</p> },
  { value: "provenance", label: "Provenance", content: <p>The provenance of the recording</p> },
];

/**
 * The tabs of the case, with the open tab in the state of the case.
 *
 * Why the state lives in a component: the tabs are controlled, because the open tab is part of the state of the
 * visit and a visitor can arrive at a tab through the URL.
 */
function ControlledTabs(): React.ReactElement {
  const [value, setValue] = useState("execution");
  return <Tabs items={ITEMS} value={value} onValueChange={setValue} label="The sections of the replay" />;
}

describe("the primitives of the design package", () => {
  it("gives the group of tabs its name and one tab per item", () => {
    // It proves that the row of tabs is announced with its name and that every section has its own tab.
    render(<ControlledTabs />);

    expect(screen.getByRole("tablist", { name: "The sections of the replay" })).toBeInTheDocument();
    for (const item of ITEMS) {
      expect(screen.getByRole("tab", { name: item.label })).toBeInTheDocument();
    }
  });

  it("shows the content of the tab that is open and hides the other panels", () => {
    // It proves that a panel that is not read does not stay in the page.
    render(<ControlledTabs />);

    expect(screen.getByText("The tree of the investigation")).toBeInTheDocument();
    expect(screen.queryByText("The evidence of the answer")).toBeNull();
  });

  it("shows the panel the visitor picked", async () => {
    // It proves that the tabs hand back the tab that was picked and that the content follows it.
    const user = userEvent.setup();
    render(<ControlledTabs />);

    await user.click(screen.getByRole("tab", { name: "Evidence" }));

    expect(screen.getByText("The evidence of the answer")).toBeInTheDocument();
    expect(screen.queryByText("The tree of the investigation")).toBeNull();
  });

  it("hands the value of the picked tab back to the caller", async () => {
    // It proves that the primitive does not keep the state of the visit inside itself.
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(
      <Tabs items={ITEMS} value="execution" onValueChange={onValueChange} label="The sections of the replay" />,
    );

    await user.click(screen.getByRole("tab", { name: "Provenance" }));

    expect(onValueChange).toHaveBeenCalledWith("provenance");
  });

  it("shows no window at all when the dialog is closed", () => {
    // It proves that a closed dialog is not in the page and not in the way of the visitor.
    render(
      <Dialog open={false} onOpenChange={() => undefined} title="The key of the visitor">
        <p>The key is stored for the time of the session.</p>
      </Dialog>,
    );

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByText("The key of the visitor")).toBeNull();
  });

  it("shows the dialog with its name and its content when it is open", () => {
    // It proves that the window is announced with the name it carries.
    render(
      <Dialog open onOpenChange={() => undefined} title="The key of the visitor">
        <p>The key is stored for the time of the session.</p>
      </Dialog>,
    );

    const dialog = screen.getByRole("dialog", { name: "The key of the visitor" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText("The key is stored for the time of the session.")).toBeInTheDocument();
  });

  it("opens the dialog from its trigger", async () => {
    // It proves that the trigger of the primitive is the way the visitor opens the window.
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    render(
      <Dialog
        open={false}
        onOpenChange={onOpenChange}
        title="The key of the visitor"
        trigger={<button type="button">Open the window</button>}
      >
        <p>The key is stored for the time of the session.</p>
      </Dialog>,
    );

    await user.click(screen.getByRole("button", { name: "Open the window" }));

    expect(onOpenChange).toHaveBeenCalledWith(true);
  });

  it("shows the sheet with its name and its content when it is open", () => {
    // It proves that the sheet is the same window as the dialog, with a name of its own.
    render(
      <Sheet open onOpenChange={() => undefined} title="The details of the call">
        <p>The arguments and the result the capture wrote.</p>
      </Sheet>,
    );

    const sheet = screen.getByRole("dialog", { name: "The details of the call" });
    expect(sheet).toBeInTheDocument();
    expect(screen.getByText("The arguments and the result the capture wrote.")).toBeInTheDocument();
  });

  it("anchors the sheet to the edge of the screen that the caller asked for", () => {
    // It proves that the side of the sheet is the one the caller chose and not the one of the last render.
    const { rerender } = render(
      <Sheet open onOpenChange={() => undefined} title="The details of the call" side="left">
        <p>The arguments and the result the capture wrote.</p>
      </Sheet>,
    );

    expect(screen.getByRole("dialog", { name: "The details of the call" }).className).toContain("left-0");

    rerender(
      <Sheet open onOpenChange={() => undefined} title="The details of the call" side="bottom">
        <p>The arguments and the result the capture wrote.</p>
      </Sheet>,
    );

    expect(screen.getByRole("dialog", { name: "The details of the call" }).className).toContain("bottom-0");
  });

  it("announces the skeleton that stands for one thing", () => {
    // It proves that a skeleton with a name says what is coming.
    render(<Skeleton label="The recorded run is loading" />);

    expect(screen.getByRole("status", { name: "The recorded run is loading" })).toBeInTheDocument();
  });

  it("keeps the skeleton of a whole panel silent", () => {
    // It proves that a skeleton without a name does not repeat the name that the panel already carries.
    const { container } = render(<Skeleton />);

    expect(screen.queryByRole("status")).toBeNull();
    expect(container.firstElementChild?.getAttribute("aria-hidden")).toBe("true");
  });

  it("takes the shape of the thing it stands for", () => {
    // It proves that the caller decides the shape of the placeholder.
    const { container } = render(<Skeleton className="h-4 w-32" />);

    expect(container.firstElementChild?.className).toContain("h-4");
    expect(container.firstElementChild?.className).toContain("w-32");
  });
});
