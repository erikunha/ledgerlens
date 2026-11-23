/**
 * The test of the heading level of the card of the design system.
 *
 * Why this test exists: the card promises that the level of the heading of its title is the
 * choice of the caller, so that the outline of the headings of a page never skips a level. The
 * promise was not kept: the title of the card was always an `h3`, and a page that puts a card
 * right under its own `h1` skipped a level. The scan of the axe found it on the landing page, and
 * the rule of the repository is that the outline of the headings never skips a level, so the
 * primitive has to keep the promise it makes.
 *
 * Every case runs with no key and no network: the card is a component of the interface and
 * nothing else.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Card, CardSection, CardTitle } from "@/components/ui/Card";

/**
 * A card under the title of a page.
 *
 * Why the page is written in the case: the outline of the headings is a property of the document
 * and not of a single component, so the assertion has to see the whole document.
 */
function PageWithACard({ level }: { readonly level?: "h2" | "h3" | "h4" | "h5" }): React.ReactElement {
  return (
    <div>
      <h1>The page</h1>
      <CardSection title="The card" description="The description of the card" titleLevel={level}>
        <p>The body of the card.</p>
      </CardSection>
    </div>
  );
}

/** The levels of the headings of the document, in the order they appear. */
function headingLevels(container: HTMLElement): readonly string[] {
  return Array.from(container.querySelectorAll("h1, h2, h3, h4, h5, h6")).map(
    (heading) => heading.tagName.toLowerCase(),
  );
}

describe("the heading level of the card", () => {
  it("keeps the level of the title as the caller chose it", () => {
    const { container } = render(
      <PageWithACard level="h2" />,
    );

    expect(headingLevels(container)).toEqual(["h1", "h2"]);
  });

  it("writes a card under the title of a page as an h2, so the outline never skips a level", () => {
    const { container } = render(<PageWithACard level="h2" />);

    const levels = headingLevels(container);

    expect(levels).not.toContain("h3");
    expect(levels[1]).toBe("h2");
  });

  it("defaults to an h3 when the caller says nothing", () => {
    const { container } = render(
      <div>
        <h1>The page</h1>
        <h2>The section</h2>
        <CardSection title="The card">
          <p>The body of the card.</p>
        </CardSection>
      </div>,
    );

    expect(headingLevels(container)).toEqual(["h1", "h2", "h3"]);
  });

  it("accepts every level the primitive allows", () => {
    for (const level of ["h2", "h3", "h4", "h5"] as const) {
      const { container, unmount } = render(<PageWithACard level={level} />);

      expect(headingLevels(container)).toEqual(["h1", level]);
      unmount();
    }
  });

  it("shows the title of the card as the heading of that level", () => {
    render(<PageWithACard level="h2" />);

    const heading = screen.getByRole("heading", { level: 2, name: "The card" });

    expect(heading).toBeInTheDocument();
  });

  it("keeps the title of a bare card at the level the caller chose", () => {
    const { container } = render(
      <Card>
        <CardTitle level="h4">The bare title</CardTitle>
      </Card>,
    );

    expect(headingLevels(container)).toEqual(["h4"]);
  });
});
