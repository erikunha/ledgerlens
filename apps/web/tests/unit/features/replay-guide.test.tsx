/**
 * The test of the guide of the cold start: the guide is data, and the data is honest.
 *
 * Why this test exists: the guide of the cold start is the path that takes a visitor who knows
 * nothing about the repository to one resolved case. The guide is data and not code that draws
 * the page, so the promises of the guide can be checked without a browser: every step names a
 * region of the reader, the last step carries the limitation of the case, the guide names the
 * capture it walks, and no step states a verdict that the bundle does not carry.
 *
 * Every case runs with no key and no network: the guide is a module of data, the catalog is the
 * file the site serves and the events of the recording are the file the site publishes.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReplayProvider } from "@/features/replay/ReplayProvider";
import { ReplayViewer } from "@/features/replay/ReplayViewer";
import type { LoadedReplay } from "@/lib/api/replay";
import type { ReplayBundleManifest, ScenarioIndexEntry, TraceEvent } from "@/lib/api/schemas";
import { readPublishedCatalog } from "@/lib/replay/catalog";
import { reduceToIndex } from "@/lib/replay/reducer";
import { GUIDE_REGIONS, guideFor } from "@/lib/replay/guide";
import { regionAnchorId } from "@/features/replay/GuidedTour";

/** The root of the site, so the test reads the files the site serves. */
const ROOT = process.cwd();

/** The guide of the scenario the cold start walks. */
const GUIDE = guideFor("S01");
if (GUIDE === null) {
  throw new Error("the guide of the scenario S01 is not there");
}

/**
 * Reads the events of the published recording of the scenario the guide walks.
 *
 * Why the test reads the file of the site: the guide walks the recording the site publishes, and
 * the promise of a step is checked against the events of that recording and never against a copy
 * of the test.
 */
function readPublishedEvents(scenario: string): Array<Record<string, unknown>> {
  const file = path.join(ROOT, "public", "replay", scenario.toLowerCase(), "events.jsonl");
  return readFileSync(file, "utf8")
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as Record<string, unknown>);
}

/**
 * Reads the recommended action of the recording, out of the span of the escalation.
 *
 * Why the span of the escalation: the decision of the case is a decision of the code, and the
 * span of the escalation is where the code wrote it.
 */
function recommendedActionOf(events: Array<Record<string, unknown>>): string | null {
  for (const event of events) {
    const payload = event.payload as Record<string, unknown> | undefined;
    if (payload?.name !== "escalation") {
      continue;
    }
    const outputs = payload.outputs as Record<string, unknown> | undefined;
    const action = outputs?.recommended_action;
    if (typeof action === "string") {
      return action;
    }
  }
  return null;
}

describe("the guide of the cold start", () => {
  it("walks the scenario S01", () => {
    expect(GUIDE.scenario).toBe("S01");
    expect(GUIDE.steps.length).toBeGreaterThan(0);
  });

  it("names, in every step, a region of the reader", () => {
    for (const step of GUIDE.steps) {
      expect(
        GUIDE_REGIONS,
        `the step ${step.id} names the region ${step.region}, which is not a region of the reader`,
      ).toContain(step.region);
    }
  });

  it("carries the limitation of the case in the last step", () => {
    const last = GUIDE.steps[GUIDE.steps.length - 1];
    expect(last?.kind).toBe("limitation");
    expect(last?.sentence.length).toBeGreaterThan(0);
  });

  it("names the capture it walks, and the catalog declares the same capture", () => {
    const card = readPublishedCatalog(ROOT, "sandbox").find((entry) => entry.id === GUIDE.scenario);
    expect(card, `the catalog publishes no card of the scenario ${GUIDE.scenario}`).toBeDefined();
    expect(GUIDE.capture).toBe(card?.bundle_digest);
  });

  it("states, in the decision step, the action the bundle carries and no other", () => {
    const decision = GUIDE.steps.find((step) => step.kind === "decision");
    expect(decision, "the guide has no step of the kind decision").toBeDefined();
    const events = readPublishedEvents(GUIDE.scenario);
    const action = recommendedActionOf(events);
    expect(action, "the recording carries no recommended action").not.toBeNull();
    expect(decision?.statesAction).toBe(action);
  });
});

/** The card of the scenario in the published catalog, as the site serves it. */
const SCENARIO: ScenarioIndexEntry = {
  id: "S01",
  name: "fx_markup_refund",
  question: "Why was the BRL refund for TX-2048 lower than the EUR payment?",
  data_origin: "UCI Online Retail II",
  status: "Recorded",
  capture_kind: "scripted_fixture",
  bundle_path: "s01",
};

/** The commit of the checkout that the links of the engineering drawer open. */
const COMMIT = "0123456789abcdef0123456789abcdef01234567";

/**
 * The bundle that the loader of the case answers with, read from the published artifacts.
 *
 * Why the case serves the real bytes: the component of the guide is drawn over the reader of the
 * real recording, and a reader built from a fixture of the test would prove the guide against a
 * reader that is not the one the site serves.
 */
function loadPublishedReplay(): LoadedReplay {
  const folder = path.join(ROOT, "public", "replay", "s01");
  const events = readFileSync(path.join(folder, "events.jsonl"), "utf8")
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as TraceEvent);
  return {
    manifest: JSON.parse(readFileSync(path.join(folder, "manifest.json"), "utf8")) as ReplayBundleManifest,
    events,
    provenance: JSON.parse(readFileSync(path.join(folder, "provenance.json"), "utf8")) as Record<
      string,
      unknown
    >,
  };
}

/**
 * Renders the reader of the recording with the guide of the cold start over it.
 *
 * Why the guide goes through the reader: the guide names regions of the reader and the reader owns
 * the layout, so the component of the guide is drawn by the reader and never beside a copy of it.
 */
function renderReaderWithTheGuide(): void {
  const loaded = loadPublishedReplay();
  const loader = vi.fn(async () => loaded);
  const guide = guideFor("S01");
  if (guide === null) {
    throw new Error("the guide of the scenario S01 is not there");
  }
  render(
    <ReplayProvider scenario={SCENARIO} loader={loader}>
      <ReplayViewer commit={COMMIT} scenario={SCENARIO} guide={guide} />
    </ReplayProvider>,
  );
}

describe("the component of the guide over the reader", () => {
  it("draws no step whose region does not exist in the reader", async () => {
    renderReaderWithTheGuide();
    await screen.findByRole("slider", { name: "Position of the recording" });

    const user = userEvent.setup();
    const controls = screen.getAllByRole("button", { name: "Show me" });
    expect(controls.length).toBe(GUIDE.steps.length);
    for (const [index, step] of GUIDE.steps.entries()) {
      const control = controls[index];
      expect(control, `the guide drew no control for the step ${step.id}`).toBeDefined();
      await user.click(control as HTMLElement);
      const anchor = document.getElementById(regionAnchorId(step.region));
      expect(
        anchor,
        `the step ${step.id} names the region ${step.region} and the reader has no such region`,
      ).not.toBeNull();
    }
  });

  it("links the fork of the last step to the scenario and to the base hash the recording declares", async () => {
    const card = readPublishedCatalog(ROOT, "sandbox").find((entry) => entry.id === GUIDE.fork.scenario);
    expect(card, `the catalog publishes no card of the scenario ${GUIDE.fork.scenario}`).toBeDefined();
    expect(
      GUIDE.fork.baseHash,
      "the fork of the guide names a base hash that is not the one the recording declares",
    ).toBe(card?.ledger_sha256);

    renderReaderWithTheGuide();
    await screen.findByRole("slider", { name: "Position of the recording" });
    const fork = screen.getByRole("link", { name: /mutate this case/i });
    expect(fork.getAttribute("href")).toContain("/sandbox");
  });
});

describe("the seeks of the reader", () => {
  it("rebuilds the same state on two seeks to the same position, and never shows an event out of order", () => {
    const events = loadPublishedReplay().events;
    const middle = Math.floor(events.length / 2);

    const first = reduceToIndex(events, middle);
    // The visitor seeks to the end and back to the middle: the state is the state of the first seek.
    reduceToIndex(events, events.length - 1);
    const second = reduceToIndex(events, middle);

    expect(second.state).toEqual(first.state);
    // The events the reader shows are the events of the bundle, in the order of the bundle, and the
    // count never grows past the position.
    expect(second.state.events).toEqual(events.slice(0, middle + 1));
    expect(second.state.events.length).toBe(middle + 1);
  });
});
