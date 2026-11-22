/**
 * The test of the stepper of the run.
 *
 * Why this test exists: the tree of the investigation answers which span opened which span and the timeline answers
 * what happened event by event, and neither of them answers the question a visitor asks first: how far along the run am
 * I, and which call is the current one. The stepper is the piece that answers it, and it has to answer it in words, with
 * a mark a reader with low vision can see, and without adding a single stop of the keyboard to the page.
 *
 * Why the steps of the case come from the published recording: the number of the steps and the names of the steps are
 * facts of the artifact of the scenario S01 and not facts written by hand, so the case reads the bundle the repository
 * publishes and projects it with the same projections the reader uses (ADR-050).
 *
 * Every case runs with no key and no network: the bundle of the case is the published bundle of the scenario S01, read
 * from the disk of the repository.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RunStepper } from "@/features/agent-trace/RunStepper";
import type { TraceEvent } from "@/lib/api/schemas";
import { reduceEvents } from "@/lib/replay/reducer";
import { buildRunSteps } from "@/lib/replay/selectors";

/**
 * Finds the folder of the published bundle of the scenario S01 on the disk.
 *
 * Why the search goes up from the working folder: the artifacts are published in `site/replay` at the root of the
 * repository and copied into `apps/web/public/replay` by the build, and the case must find them in either place.
 */
function findPublishedEvents(): string {
  const roots: string[] = [];
  let current = process.cwd();
  for (;;) {
    roots.push(current);
    const parent = dirname(current);
    if (parent === current) {
      break;
    }
    current = parent;
  }

  const candidates = [
    ...roots.map((root) => join(root, "public", "replay", "s01", "events.jsonl")),
    ...roots.map((root) => join(root, "site", "replay", "s01", "events.jsonl")),
  ];

  for (const file of candidates) {
    if (existsSync(file)) {
      return readFileSync(file, "utf8");
    }
  }
  throw new Error("the published bundle of the scenario S01 was not found on the disk of the repository");
}

/** The events of the published recording, in the order of the recording. */
const EVENTS: readonly TraceEvent[] = findPublishedEvents()
  .split("\n")
  .filter((line) => line.trim() !== "")
  .map((line) => JSON.parse(line) as TraceEvent);

/** The steps of the run of the recording of S01, as the reader projects them. */
const STEPS = buildRunSteps(reduceEvents(EVENTS).state.spans);

/** The step the recording stands at in the cases that need one: the second call of the recording. */
const CURRENT = STEPS[1] ?? null;

describe("the stepper of the run", () => {
  it("shows the four steps of the recording of S01 in the order of the recording", () => {
    // It proves that the stepper shows the calls of the recording, in the order the capture made them, with the names
    // the capture wrote.
    render(<RunStepper steps={STEPS} current={CURRENT} />);

    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(items).toHaveLength(4);
    expect(items.map((item) => item.textContent)).toEqual([
      "Step 1 of 4: query_ledger. Finished. Succeeded.",
      "Step 2 of 4: search_policies. The current step.",
      "Step 3 of 4: get_reference_fx. Not started yet.",
      "Step 4 of 4: calculate. Not started yet.",
    ]);
  });

  it("is a region with a heading of level four", () => {
    // It proves that the stepper is a panel of the section of the execution: a region a visitor can reach by name and a
    // heading of level four, so that the outline of the headings never skips a level.
    render(<RunStepper steps={STEPS} current={CURRENT} />);

    const region = screen.getByRole("region", { name: "The steps of the run" });
    expect(region).toBeInTheDocument();

    const heading = within(region).getByRole("heading", { level: 4, name: "The steps of the run" });
    expect(heading).toBeInTheDocument();
  });

  it("marks the current step with the attribute of the current item of a sequence", () => {
    // It proves that a reader of a screen reader knows which step the recording stands at, because the item of the list
    // carries `aria-current="step"`.
    render(<RunStepper steps={STEPS} current={CURRENT} />);

    const current = screen.getByRole("listitem", { current: "step" });
    expect(current).toHaveTextContent("Step 2 of 4: search_policies.");
    expect(current).toHaveTextContent("The current step.");
  });

  it("says in words that a step the recording is over is finished, with the status of the call", () => {
    // It proves that the state of a step is never only a colour: the step the recording is over says that it is
    // finished, and it says the status the capture wrote, with the words the table of the calls uses.
    render(<RunStepper steps={STEPS} current={CURRENT} />);

    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    const first = items[0];
    expect(first).toBeDefined();
    expect(first).toHaveTextContent("Finished.");
    expect(first).toHaveTextContent("Succeeded.");
    expect(first).not.toHaveAttribute("aria-current");
  });

  it("says in words that a step the recording has not reached has not started yet", () => {
    // It proves that a step the recording has not reached says so in words, and that it says no status at all: a call
    // that has not happened cannot have ended with one.
    render(<RunStepper steps={STEPS} current={CURRENT} />);

    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    const third = items[2];
    expect(third).toBeDefined();
    expect(third).toHaveTextContent("Not started yet.");
    expect(third?.textContent).not.toMatch(/Succeeded|Failed|Timed out/);
  });

  it("tells the current step from an ordinary step by something that is not a colour", () => {
    // It proves that the current step wears a mark a reader with low vision can see: a border on its left and a heavier
    // name, the mark the tree and the timeline already wear.
    render(<RunStepper steps={STEPS} current={CURRENT} />);

    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    const current = screen.getByRole("listitem", { current: "step" });
    const ordinary = items[2];
    expect(ordinary).toBeDefined();

    expect(current.className).toContain("border-l-2");
    expect(current.className).toContain("border-foreground");
    expect(ordinary?.className).toContain("border-transparent");

    const currentName = current.querySelector("span");
    const ordinaryName = ordinary?.querySelector("span");
    expect(currentName?.className).toContain("font-semibold");
    expect(ordinaryName?.className).toContain("font-medium");
  });

  it("holds no button, no link and no stop of the keyboard", () => {
    // It proves that the stepper is an indicator and never a control: it never seeks, it never opens the drawer of a
    // call, and it adds no stop of the keyboard to the page.
    const { container } = render(<RunStepper steps={STEPS} current={CURRENT} />);

    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
    expect(container.querySelectorAll("button, a, input, select, textarea")).toHaveLength(0);
    expect(container.querySelectorAll('[tabindex="0"]')).toHaveLength(0);
  });

  it("shows no amount of money", () => {
    // It proves that the stepper shows the number of the step, the name of the tool and the state of the step, and
    // nothing else: an amount of the recording is written by the panel of the amounts, in decimal text.
    render(<RunStepper steps={STEPS} current={CURRENT} />);

    const region = screen.getByRole("region", { name: "The steps of the run" });
    const text = region.textContent ?? "";

    expect(text).not.toMatch(/BRL|EUR|USD|R\$|\$/);
    expect(text).not.toMatch(/\d+[.,]\d{2}/);
  });

  it("shows no step when the recording made no call", () => {
    // It proves that the stepper never shows a step that the recording does not carry.
    render(<RunStepper steps={[]} current={null} />);

    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
    expect(screen.getByText("The recording made no call of a tool yet.")).toBeInTheDocument();
  });
});
