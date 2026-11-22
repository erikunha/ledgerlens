/**
 * The test of the states of the reader of a recorded run: the refusal of a bundle and the bundle
 * that carries no event.
 *
 * Why this test exists: the two states are drawn inside the section of the reader, and the reader
 * prescribes that the heading of a section of the reader is an `h3`. A state that carries another
 * level breaks the outline of the page, and a reader who walks the headings of the page hears the
 * states of the reader as something else than the sections they belong to.
 *
 * Every case runs with no key and no network: the two states are components of the interface and
 * nothing else.
 */

import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { ReplayEmptyState } from "@/features/replay/ReplayEmptyState";
import { ReplayErrorState } from "@/features/replay/ReplayErrorState";

/** The level of every heading of the page, by the name of its tag. */
const LEVEL_OF_TAG: Record<string, number> = {
  H1: 1,
  H2: 2,
  H3: 3,
  H4: 4,
  H5: 5,
  H6: 6,
};

/**
 * The levels of the headings of the page, in the order the reader meets them.
 *
 * Why the case reads the tag and not the attribute: the outline of a page is the order of its
 * headings, and the tag is what says the level of a heading.
 */
function outlineLevels(container: HTMLElement): number[] {
  return Array.from(container.querySelectorAll("h1, h2, h3, h4, h5, h6")).map(
    (heading) => LEVEL_OF_TAG[heading.tagName] ?? 0,
  );
}

/**
 * Says whether the outline of the page skips a level.
 *
 * Why the case looks at the steps and not at the levels: an outline that jumps from a level to a
 * level below it is the outline a reader with a screen reader cannot follow, and the jump is the
 * thing the case looks for.
 */
function skipsALevel(levels: readonly number[]): boolean {
  for (let index = 1; index < levels.length; index += 1) {
    const previous = levels[index - 1];
    const current = levels[index];
    if (previous === undefined || current === undefined) {
      continue;
    }
    if (current > previous + 1) {
      return true;
    }
  }
  return false;
}

/**
 * Renders a state of the reader inside the page of a scenario.
 *
 * Why the page is here: the level of the heading of a state is a fact about the page it is drawn
 * in, and the page of a scenario is the `h1` of the route and the `h2` of the scenario.
 */
function renderState(state: ReactNode): HTMLElement {
  const { container } = render(
    <>
      <h1>Recorded demo</h1>
      <h2>S01 - Why was the BRL refund for TX-2048 lower than the EUR payment?</h2>
      <section aria-label="The recorded run">{state}</section>
    </>,
  );
  return container;
}

describe("the failure state of the reader", () => {
  it("gives the refusal the heading of a section of the reader", () => {
    // It proves that the refusal is announced with the heading of a section of the reader and not
    // with the heading of the page.
    render(
      <ReplayErrorState reason="the bundle of the scenario S01 did not pass the integrity check" />,
    );

    expect(
      screen.getByRole("heading", { level: 3, name: "The recorded run was refused" }),
    ).toBeInTheDocument();
  });

  it("never skips a level of the outline of the page", () => {
    // It proves that the outline of the page walks from the route to the refusal one level at a
    // time.
    const container = renderState(
      <ReplayErrorState reason="the bundle of the scenario S01 did not pass the integrity check" />,
    );

    const levels = outlineLevels(container);
    expect(levels).toEqual([1, 2, 3]);
    expect(skipsALevel(levels)).toBe(false);
  });
});

describe("the empty state of the reader", () => {
  it("gives the empty recording the heading of a section of the reader", () => {
    // It proves that a recording with no event is announced with the heading of a section of the
    // reader and not with the heading of the page.
    render(<ReplayEmptyState scenarioId="S01" />);

    expect(
      screen.getByRole("heading", {
        level: 3,
        name: "The recording of the scenario has no event",
      }),
    ).toBeInTheDocument();
  });

  it("never skips a level of the outline of the page", () => {
    // It proves that the outline of the page walks from the route to the empty recording one level
    // at a time.
    const container = renderState(<ReplayEmptyState scenarioId="S01" />);

    const levels = outlineLevels(container);
    expect(levels).toEqual([1, 2, 3]);
    expect(skipsALevel(levels)).toBe(false);
  });
});
