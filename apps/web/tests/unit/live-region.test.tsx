/**
 * The test of the polite live region of the design system.
 *
 * Why this test exists: the region is the only place of the site where the interface speaks to a visitor who does not
 * see the screen, and a region that talks too much is a region nobody can listen to. The primitive carries the markup
 * of a polite region and nothing else: it announces the sentence it is given, it writes no word of its own, and it
 * never touches the region again while the sentence does not change.
 *
 * Why the case counts the rewrites of the region: a reader of a screen reader hears the region every time the region
 * changes, so a region that is rewritten on every render of the page talks over the visitor. The rule of the milestone
 * is that the region speaks once per step, and this case is where that rule is proved (ADR-050).
 *
 * Every case runs with no key and no network: the primitive is a piece of markup.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LiveRegion } from "@/components/ui/LiveRegion";

/**
 * Waits for the browser of the case to deliver what the observer of the mutations saw.
 *
 * Why the wait is a turn of the event loop: the observer of the mutations is called in a task of its own, and a case
 * that asks for the count before that task runs would read a count of zero for a region that really changed.
 */
async function flushTheMutations(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

describe("the polite live region", () => {
  it("renders one polite region with the attributes of a polite region", () => {
    // It proves that the region is the region a reader of a screen reader listens to: it is polite, so it never
    // interrupts the visitor, it is atomic, so it is read as a whole, and it is out of the keyboard, because the
    // visitor reaches it with the focus and not with the tab.
    render(<LiveRegion>Step 2 of 4: search_policies.</LiveRegion>);

    const regions = document.querySelectorAll('[aria-live="polite"]');
    expect(regions).toHaveLength(1);

    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveAttribute("aria-atomic", "true");
    expect(region).toHaveAttribute("tabindex", "-1");

    // the region is never assertive, and it is never a log
    expect(document.querySelectorAll('[aria-live="assertive"]')).toHaveLength(0);
    expect(document.querySelectorAll('[role="alert"]')).toHaveLength(0);
    expect(document.querySelectorAll('[role="log"]')).toHaveLength(0);
  });

  it("renders the children as they are and writes no word of its own", () => {
    // It proves that the announcement is the sentence the caller wrote: the primitive knows nothing about the domain,
    // so it never adds a word of its own to what a visitor hears.
    render(<LiveRegion>Step 1 of 4: query_ledger.</LiveRegion>);

    const region = screen.getByRole("status");
    expect(region.textContent).toBe("Step 1 of 4: query_ledger.");
  });

  it("never renders a second region", () => {
    // It proves that the primitive renders ONE region and never a region inside a region: two polite regions on one
    // page are two announcements for one action.
    const { container } = render(
      <LiveRegion>
        <span>Step 1 of 4: query_ledger.</span>
      </LiveRegion>,
    );

    expect(container.querySelectorAll('[aria-live], [role="status"], [role="alert"], [role="log"]')).toHaveLength(1);
  });

  it("takes the focus when the page asks for it", () => {
    // It proves that the element the caller keeps is the paragraph of the region, so the reader can move the focus to
    // the region once, when the recording starts (FR-032).
    const nodes: HTMLParagraphElement[] = [];
    render(
      <LiveRegion ref={(node) => { if (node !== null) { nodes.push(node); } }}>
        Step 1 of 4: query_ledger.
      </LiveRegion>,
    );

    const region = nodes[0];
    expect(region).toBeDefined();

    region?.focus();
    expect(document.activeElement).toBe(screen.getByRole("status"));
  });

  it("says nothing while it is empty", () => {
    // It proves that an empty region stays silent: a region that holds a sentence when the page loads is announced
    // by some readers as soon as it appears, and the visitor hears the state of the recording before he asked for it.
    render(<LiveRegion>{""}</LiveRegion>);

    const region = screen.getByRole("status");
    expect(region.textContent).toBe("");
    expect(region).toHaveAttribute("aria-live", "polite");
  });

  it("does not touch the region again while the sentence does not change", async () => {
    // It proves the granularity of the announcement: the region is rewritten only when the sentence changes, so a
    // reader of a screen reader hears the region once per step and not once per render of the page.
    const { rerender } = render(<LiveRegion>Step 1 of 4: query_ledger.</LiveRegion>);

    const region = screen.getByRole("status");
    let rewrites = 0;
    const observer = new MutationObserver((records) => {
      rewrites += records.length;
    });
    observer.observe(region, { childList: true, characterData: true, subtree: true });

    rerender(<LiveRegion>Step 1 of 4: query_ledger.</LiveRegion>);
    await flushTheMutations();
    expect(rewrites).toBe(0);

    rerender(<LiveRegion>Step 2 of 4: search_policies.</LiveRegion>);
    await flushTheMutations();
    expect(rewrites).toBeGreaterThan(0);
    expect(region.textContent).toBe("Step 2 of 4: search_policies.");

    observer.disconnect();
  });
});
