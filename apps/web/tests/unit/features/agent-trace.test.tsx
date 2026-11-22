/**
 * The test of the trace of a recorded run: the timeline of the recording and the tree of the
 * investigation.
 *
 * Why this test exists: the trace is where a reader sees where the recording stands, and both of
 * its panels carry a state that must never be only a colour. The row the visitor stands at wears
 * a mark a reader with low vision can see, and the mark survives the forced colours mode of the
 * system, where a tint of the background does not. The tree indents every level of the
 * investigation with the steps of the spacing scale of the design system, and it writes no pixel
 * of the indent in the markup, so the indent moves with the scale.
 *
 * Why the case carries a stylesheet of its own: the unit tests run in jsdom, which knows no
 * stylesheet of the site, so the case gives the utilities of the design system the values of the
 * tokens of the site. The case then asks the browser of the case what the weight and the border of
 * a row are, and it asks about the style of the row and never about the name of the class that
 * draws it.
 */

import { render, screen, within } from "@testing-library/react";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { TraceTimeline } from "@/features/agent-trace/TraceTimeline";
import { TraceTree } from "@/features/agent-trace/TraceTree";
import { colors, spacing } from "@/lib/design/tokens";
import type { TimelineRow, TraceTreeNode } from "@/lib/replay/selectors";

/**
 * The stylesheet of the case: the utilities of the design system, with the values of the tokens.
 *
 * Why the values come from the tokens: the case has to measure the site as the site draws it, so
 * the spacing steps and the colours it measures are the ones the design system declares.
 */
const STYLESHEET = `
${Object.entries(spacing)
  .map(([key, value]) => `.pl-${key} { padding-left: ${value}; } .px-${key} { padding-left: ${value}; }`)
  .join("\n")}
.font-thin { font-weight: 100; }
.font-light { font-weight: 300; }
.font-normal { font-weight: 400; }
.font-medium { font-weight: 500; }
.font-semibold { font-weight: 600; }
.font-bold { font-weight: 700; }
.font-extrabold { font-weight: 800; }
.font-black { font-weight: 900; }
.border-l-2 { border-left-width: 2px; border-left-style: solid; }
.border-l-4 { border-left-width: 4px; border-left-style: solid; }
.border-foreground { border-left-color: ${colors.text}; }
.border-transparent { border-left-color: transparent; }
`;

/**
 * The weights of the type of the design system, from the lightest to the heaviest.
 *
 * Why the case keeps the order: the case says that the name of the row the visitor stands at is
 * heavier than the name of an ordinary row, and it compares two weights by their place in the
 * order of the weights, never by turning them into numbers.
 */
const WEIGHTS: readonly string[] = [
  "100",
  "200",
  "300",
  "400",
  "500",
  "600",
  "700",
  "800",
  "900",
];

/** The rows of the case: three events of a recording, one of them slow. */
const ROWS: readonly TimelineRow[] = [
  {
    seq: 1,
    eventType: "span.started",
    label: "investigate",
    at: "2026-11-14T11:00:14.051+00:00",
    latencyMs: null,
    error: null,
    isTool: false,
  },
  {
    seq: 2,
    eventType: "span.ended",
    label: "query_ledger",
    at: "2026-11-14T11:00:14.063+00:00",
    latencyMs: 12,
    error: null,
    isTool: true,
  },
  {
    seq: 3,
    eventType: "span.ended",
    label: "calculate",
    at: "2026-11-14T11:00:14.075+00:00",
    latencyMs: 1200,
    error: null,
    isTool: true,
  },
];

/** The nodes of the case: a span that opened a span that opened a span. */
const NODES: readonly TraceTreeNode[] = [
  {
    spanId: "root",
    parentSpanId: null,
    name: "investigate",
    runType: "chain",
    depth: 0,
    startedSeq: 1,
    endedSeq: 9,
    children: [
      {
        spanId: "child",
        parentSpanId: "root",
        name: "query_ledger",
        runType: "tool",
        depth: 1,
        startedSeq: 2,
        endedSeq: 3,
        children: [
          {
            spanId: "grandchild",
            parentSpanId: "child",
            name: "calculate",
            runType: "tool",
            depth: 2,
            startedSeq: 4,
            endedSeq: 5,
            children: [],
          },
        ],
      },
    ],
  },
];

/**
 * The steps of the indent of a row of the tree, from the row to its button.
 *
 * Why the case adds up the steps and not the pixels: the indent of a row is a sum of the steps of
 * the spacing scale, so the case asks the browser of the case for the step of every level and
 * never for a number of pixels, which is a value of the design system and not a value of the
 * case.
 */
function indentSteps(button: HTMLElement): string[] {
  const steps: string[] = [];
  let element = button.parentElement;
  while (element !== null && element.getAttribute("role") !== "none") {
    steps.push(window.getComputedStyle(element).paddingLeft);
    element = element.parentElement;
  }
  return steps;
}

beforeAll(() => {
  const style = document.createElement("style");
  style.textContent = STYLESHEET;
  document.head.appendChild(style);
});

afterAll(() => {
  document.head.querySelectorAll("style").forEach((node) => node.remove());
});

describe("the timeline of the recording", () => {
  it("tells the row the visitor stands at from an ordinary row by something that is not a colour", () => {
    // It proves that the row the visitor stands at wears a mark a reader with low vision can see:
    // a heavier name and a border on its left. The name is the mark that survives the forced
    // colours mode of the system, where a tint of the background does not.
    render(<TraceTimeline rows={ROWS} position={1} onSeek={() => undefined} />);

    const current = screen.getByRole("button", { name: "2" });
    const ordinary = screen.getByRole("button", { name: "1" });

    const currentStyle = window.getComputedStyle(current);
    const ordinaryStyle = window.getComputedStyle(ordinary);

    // the weight of the name: the mark of the tree of the investigation, and no colour at all
    expect(WEIGHTS.indexOf(currentStyle.fontWeight)).toBeGreaterThan(
      WEIGHTS.indexOf(ordinaryStyle.fontWeight),
    );

    // the border on the left: the mark the tree of the investigation carries as well
    expect(currentStyle.borderLeftStyle).toBe("solid");
    expect(currentStyle.borderLeftColor).not.toBe(ordinaryStyle.borderLeftColor);
    expect(ordinaryStyle.borderLeftColor).toMatch(/transparent|rgba\(0, 0, 0, 0\)/);
  });

  it("keeps the row the visitor stands at the current row of the table", () => {
    // It proves that the row that wears the mark is the row the reader hears as the current one.
    render(<TraceTimeline rows={ROWS} position={1} onSeek={() => undefined} />);

    const current = screen.getByRole("row", { current: true });
    expect(within(current).getByRole("button", { name: "2" })).toBeInTheDocument();
  });
});

describe("the tree of the investigation", () => {
  it("indents every level of the tree with the steps of the scale of the design system", () => {
    // It proves that the indent of a row is a sum of the steps of the spacing scale: every step
    // of the indent is one the design system declares, and a deeper row carries more steps than a
    // shallower one.
    render(<TraceTree nodes={NODES} selectedSpanId="root" onSelect={() => undefined} />);

    const root = screen.getByRole("treeitem", { name: /investigate/ });
    const child = screen.getByRole("treeitem", { name: /query_ledger/ });
    const grandchild = screen.getByRole("treeitem", { name: /calculate/ });

    const rootSteps = indentSteps(root);
    const childSteps = indentSteps(child);
    const grandchildSteps = indentSteps(grandchild);

    for (const step of [...rootSteps, ...childSteps, ...grandchildSteps]) {
      expect(Object.values(spacing)).toContain(step);
    }

    expect(childSteps.length).toBeGreaterThan(rootSteps.length);
    expect(grandchildSteps.length).toBeGreaterThan(childSteps.length);
  });

  it("writes no pixel of the indent in the markup", () => {
    // It proves that the indent is not written by hand: the tree carries no style of its own, so
    // the indent cannot drift away from the scale of the design system.
    const { container } = render(
      <TraceTree nodes={NODES} selectedSpanId="root" onSelect={() => undefined} />,
    );

    expect(container.querySelectorAll("[style]")).toHaveLength(0);
  });

  it("tells the chosen span from an ordinary span by something that is not a colour", () => {
    // It proves that the chosen span wears a heavier name, the mark that survives the forced
    // colours mode of the system.
    render(<TraceTree nodes={NODES} selectedSpanId="root" onSelect={() => undefined} />);

    const chosen = screen.getByRole("treeitem", { name: /investigate/ });
    const ordinary = screen.getByRole("treeitem", { name: /query_ledger/ });

    const chosenName = chosen.querySelector("span");
    const ordinaryName = ordinary.querySelector("span");
    expect(chosenName).not.toBeNull();
    expect(ordinaryName).not.toBeNull();

    expect(WEIGHTS.indexOf(window.getComputedStyle(chosenName as Element).fontWeight)).toBeGreaterThan(
      WEIGHTS.indexOf(window.getComputedStyle(ordinaryName as Element).fontWeight),
    );
  });
});
