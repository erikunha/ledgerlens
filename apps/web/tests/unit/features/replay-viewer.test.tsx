/**
 * The test of the reader of the recorded run.
 *
 * Why this test exists: the recorded demo is the half of the demo that works with no key and no network, so the reader
 * has to be honest about what it shows. It shows the mode of the manifest it read and the note of the capture, word
 * for word, and it never presents a recorded run as a live one. It shows the panels of the milestone, the tree, the
 * timeline, the provenance, the evidence and the verdicts. And when the artifact is broken it shows the reason instead
 * of a half drawn run, because a reader cannot tell which parts of a half drawn run are true.
 *
 * The reader no longer fetches by itself: it reads the state of the provider of the replay, and the provider is the
 * one that loads the bundle. The test therefore builds the provider with a loader of its own, and the loader answers
 * with the artifacts the repository publishes.
 *
 * Every case runs with no key and no network: the bundle of the case is the published bundle of the scenario S01, read
 * from the disk of the repository, and the fetch of the runtime is a fake that answers with the same artifacts.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReplayProvider } from "@/features/replay/ReplayProvider";
import { ReplayViewer } from "@/features/replay/ReplayViewer";
import { loadReplay, type LoadedReplay } from "@/lib/api/replay";
import type { ReplayBundleManifest, ScenarioIndexEntry, TraceEvent } from "@/lib/api/schemas";

/**
 * Finds the folder of the published bundle of the scenario S01 on the disk.
 *
 * Why the search goes up from the working folder: the artifacts are published in `site/replay` at the root of the
 * repository and copied into `apps/web/public/replay` by the build, and the test must find them in either place. The
 * artifacts of the repository are the source of truth, so the case serves the real bytes of the real files.
 */
function findPublishedBundle(): { manifest: string; events: string; provenance: string } {
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
    ...roots.map((root) => join(root, "public", "replay", "s01")),
    ...roots.map((root) => join(root, "site", "replay", "s01")),
  ];

  for (const folder of candidates) {
    if (!existsSync(join(folder, "events.jsonl"))) {
      continue;
    }
    return {
      manifest: readFileSync(join(folder, "manifest.json"), "utf8"),
      events: readFileSync(join(folder, "events.jsonl"), "utf8"),
      provenance: readFileSync(join(folder, "provenance.json"), "utf8"),
    };
  }
  throw new Error("the published bundle of the scenario S01 was not found on the disk of the repository");
}

/** The published bundle of the scenario S01, read from the disk of the repository. */
const PUBLISHED = findPublishedBundle();

/** The manifest of the published bundle, as `site/replay/s01/manifest.json` holds it. */
const MANIFEST = JSON.parse(PUBLISHED.manifest) as ReplayBundleManifest;

/** The provenance file of the published bundle, as `site/replay/s01/provenance.json` holds it. */
const PROVENANCE = JSON.parse(PUBLISHED.provenance) as Record<string, unknown>;

/** The events of the published recording, in the order of the recording. */
const EVENTS: readonly TraceEvent[] = PUBLISHED.events
  .split("\n")
  .filter((line) => line.trim() !== "")
  .map((line) => JSON.parse(line) as TraceEvent);

/**
 * The published events of the recording, with the call of the calculation slowed down.
 *
 * Why the case slows a call down: a duration of one second or more is written in seconds, so the
 * case needs a call that takes more than a second to prove that the column of the latency writes
 * the duration the way the timeline writes it and never as the bare number of the recording.
 */
const EVENTS_WITH_A_SLOW_CALL: readonly TraceEvent[] = EVENTS.map((event) => {
  const payload = event.payload ?? {};
  if (payload.run_type !== "tool" || payload.name !== "calculate") {
    return event;
  }
  return { ...event, payload: { ...payload, latency_ms: 1200 } };
});

/** The card of the scenario in the published catalog, as `site/replay/index.json` holds it. */
const SCENARIO: ScenarioIndexEntry = {
  id: "S01",
  name: "fx_markup_refund",
  question: "Why was the BRL refund for TX-2048 lower than the EUR payment?",
  concepts: [
    "read_only_ledger_query",
    "policy_retrieval",
    "exchange_rate_reference",
    "decimal_calculation",
  ],
  data_origin: "UCI Online Retail II",
  status: "Recorded",
  capture_kind: "scripted_fixture",
  bundle_path: "s01",
};

/** The bundle that the loader of the case answers with. */
const LOADED: LoadedReplay = { manifest: MANIFEST, events: EVENTS, provenance: PROVENANCE };

/**
 * The loader of the case: it answers with the bundle or with the reason of the refusal.
 *
 * Why the fetch of the runtime is stubbed as well: the reader reads the state of the provider, and the provider reads
 * the bundle through the loader of the case. The fetch is stubbed with the same artifacts, so that a reader that
 * reaches for the network on its own finds the same published bundle and never a network of its own.
 */
function loaderOf(answer: LoadedReplay | { error: string }) {
  return vi.fn(async () => answer);
}

/** Stubs the fetch of the runtime with the published artifacts of the repository. */
function stubFetch(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.endsWith("manifest.json")
        ? PUBLISHED.manifest
        : url.endsWith("events.jsonl")
          ? PUBLISHED.events
          : url.endsWith("provenance.json")
            ? PUBLISHED.provenance
            : "";
      return { ok: true, status: 200, text: async () => body } as unknown as Response;
    }),
  );
}

/**
 * Renders the reader inside the provider of the replay.
 *
 * Why the provider is here: the reader stopped fetching by itself, so the state of the bundle lives in the provider
 * and the reader only draws it.
 */
function renderViewer(answer: LoadedReplay | { error: string }): void {
  stubFetch();
  render(
    <ReplayProvider scenario={SCENARIO} loader={loaderOf(answer)}>
      <ReplayViewer scenario={SCENARIO} />
    </ReplayProvider>,
  );
}

/**
 * Finds a panel of the replay, and opens its section when the panel is not in the page yet.
 *
 * Why the section is opened: the panels of the replay live in the sections of the replay, and a section that is not
 * the open one is not in the page. The helper proves that the panel exists and that the visitor can reach it.
 */
async function findPanel(name: string, section?: string): Promise<HTMLElement | null> {
  const panel = screen.queryByRole("region", { name });
  if (panel !== null) {
    return panel;
  }
  const trigger = section === undefined ? null : screen.queryByRole("tab", { name: section });
  if (trigger === null) {
    return null;
  }
  await userEvent.setup().click(trigger);
  return screen.queryByRole("region", { name });
}

/**
 * Waits for the recorded run to be drawn, and gives the region of the run.
 *
 * Why the case waits for the slider and not for the region: the loading state carries the very same
 * name as the run itself, so a case that waits for the region can wake up while the run has drawn
 * nothing yet. The slider only exists once the bundle has been read.
 */
async function findLoadedRun(): Promise<HTMLElement> {
  await screen.findByRole("slider", { name: "Position of the recording" });
  return screen.getByRole("region", { name: "The recorded run" });
}

afterEach(() => {
  vi.unstubAllGlobals();
  // The address of the case and the preferences of the view are put back where they were, so that a
  // case that writes them never reaches the case that runs after it.
  window.history.replaceState(null, "", "/");
  window.localStorage.clear();
});

describe("the reader of the recorded run", () => {
  it("shows the recorded run with the mode of the manifest and the note of the capture", async () => {
    // It proves that the reader shows what the manifest says, in the region the visitor reads.
    renderViewer(LOADED);

    const recordedRun = await findLoadedRun();
    expect(within(recordedRun).getAllByText("mode: deterministic_sandbox")).toHaveLength(1);
    expect(within(recordedRun).getByText("scenario: S01")).toBeInTheDocument();
    expect(within(recordedRun).getByText("run: replay-s01")).toBeInTheDocument();
    expect(within(recordedRun).getByText("capture: scripted_fixture")).toBeInTheDocument();
    expect(screen.getByText(MANIFEST.note)).toBeInTheDocument();
  });

  it("never presents the recorded run as a live one", async () => {
    // It proves that the mode the visitor reads is the sandbox and never a live one. The note of the capture is left
    // out of the check, because it says out loud that the recording is not a live execution.
    renderViewer(LOADED);

    const recordedRun = await findLoadedRun();
    const rest = (document.body.textContent ?? "")
      .replace(recordedRun.textContent ?? "", "")
      .replace(MANIFEST.note, "");
    expect(rest).not.toMatch(/live/i);
  });

  it("shows the position of the recording and the calls of the tools of the capture", async () => {
    // It proves that the reader shows the slider of the position and the table of the calls, with the names the
    // capture gave them.
    renderViewer(LOADED);

    const slider = await screen.findByRole("slider", { name: "Position of the recording" });
    expect(slider).toBeInTheDocument();

    const calls = screen.getByRole("table", { name: "The calls of the tools of the recorded run" });
    expect(calls).toBeInTheDocument();

    // The calls of the capture are on the screen when the visitor reaches the end of the recording.
    const last = slider.getAttribute("max");
    fireEvent.change(slider, { target: { value: last ?? String(EVENTS.length - 1) } });

    await waitFor(() => {
      expect(within(calls).getByRole("rowheader", { name: "query_ledger" })).toBeInTheDocument();
    });
  });

  it("shows that the recording has no call of a tool yet at the beginning", async () => {
    // It proves that the reader tells the visitor where it is in the recording.
    renderViewer(LOADED);

    const recordedRun = await findLoadedRun();
    expect(within(recordedRun).getByText("The recording has no call of a tool yet.")).toBeInTheDocument();
    expect(within(recordedRun).getByText(/Event \d+ of 57\./)).toBeInTheDocument();
    expect(within(recordedRun).getByText(/The status of the run is:/)).toBeInTheDocument();
  });

  it("shows the whole recording when the visitor moves to its end", async () => {
    // It proves that the reader follows the position of the slider and shows the count of the events of the bundle.
    renderViewer(LOADED);

    const slider = await screen.findByRole("slider", { name: "Position of the recording" });
    const last = slider.getAttribute("max");

    fireEvent.change(slider, { target: { value: last ?? String(EVENTS.length - 1) } });

    await waitFor(() => {
      expect(screen.getByText(/Event 57 of 57\./)).toBeInTheDocument();
    });
    expect(screen.getByText(/The status of the run is:/)).toBeInTheDocument();
  });

  it("shows the tree of the investigation", async () => {
    // It proves that the panel of the tree of the investigation is on the screen.
    renderViewer(LOADED);

    await findLoadedRun();
    expect(await findPanel("The tree of the investigation", "Execution")).not.toBeNull();
  });

  it("shows the timeline of the recording", async () => {
    // It proves that the panel of the timeline is on the screen.
    renderViewer(LOADED);

    await findLoadedRun();
    expect(await findPanel("The timeline of the recording", "Execution")).not.toBeNull();
  });

  it("shows the provenance of the recording", async () => {
    // It proves that the panel of the provenance is on the screen.
    renderViewer(LOADED);

    await findLoadedRun();
    expect(await findPanel("The provenance of the recording", "Provenance")).not.toBeNull();
  });

  it("shows the evidence of the answer", async () => {
    // It proves that the panel of the evidence is on the screen.
    renderViewer(LOADED);

    await findLoadedRun();
    expect(await findPanel("The evidence of the answer", "Evidence")).not.toBeNull();
  });

  it("shows the claims of the answer", async () => {
    // It proves that the panel of the verdicts of the verifier is on the screen.
    renderViewer(LOADED);

    await findLoadedRun();
    expect(await findPanel("The claims of the answer", "Decision")).not.toBeNull();
  });

  it("shows a percentage of the breakdown without the currency of the run", async () => {
    // It proves that a percentage is not money: the result of the calculation carries `markup_pct` next to money values,
    // and the panel shows the percentage with the symbol of the percentage and with no currency at all. The currency of
    // the run belongs to the money values only.
    renderViewer(LOADED);

    await findLoadedRun();
    const slider = screen.getByRole("slider", { name: "Position of the recording" });
    const last = slider.getAttribute("max");
    fireEvent.change(slider, { target: { value: last ?? String(EVENTS.length - 1) } });

    const panel = await findPanel("The amounts of the answer", "Decision");
    expect(panel).not.toBeNull();

    // The percentage is written with the symbol of the percentage, and the money values keep the currency of the run.
    expect(within(panel as HTMLElement).getByText("2.50%")).toBeInTheDocument();
    expect(within(panel as HTMLElement).getByText("BRL 566.79")).toBeInTheDocument();
    expect(within(panel as HTMLElement).getByText("BRL 549.31")).toBeInTheDocument();

    // The percentage never wears the currency of the run.
    expect(within(panel as HTMLElement).queryByText("BRL 2.50")).toBeNull();
    expect(within(panel as HTMLElement).queryByText(/2\.50\s*BRL/)).toBeNull();
  });

  it("shows the controls of the playback and the sections of the replay", async () => {
    // It proves that the visitor can play, pause, step and restart the recording, and that the sections of the replay
    // carry their name.
    renderViewer(LOADED);

    await findLoadedRun();
    expect(screen.getByRole("button", { name: "Play the recording" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pause the recording" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous event" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next event" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Restart the recording" })).toBeInTheDocument();

    const tabs = screen.getByRole("tablist", { name: "The sections of the replay" });
    expect(within(tabs).getByRole("tab", { name: "Execution" })).toBeInTheDocument();
    expect(within(tabs).getByRole("tab", { name: "Evidence" })).toBeInTheDocument();
    expect(within(tabs).getByRole("tab", { name: "Decision" })).toBeInTheDocument();
    expect(within(tabs).getByRole("tab", { name: "Provenance" })).toBeInTheDocument();
  });

  it("keeps the fragment of the address when the visitor changes a preference", async () => {
    // It proves that a deep link survives the writes of the preferences: the fragment points at the panel of a
    // section, and the fragment is a part of the address the visitor brought, not a preference of the view. The
    // fragment is never written into the query string either: it stays the fragment of the address.
    window.history.replaceState(null, "", "/replay/scenario/S01?tab=evidence#ledgerlens-section-evidence");

    renderViewer(LOADED);
    await findLoadedRun();

    const speed = screen.getByRole("combobox", { name: "Speed of the playback" });
    await userEvent.setup().selectOptions(speed, "2");

    expect(window.location.pathname).toBe("/replay/scenario/S01");
    expect(window.location.search).toBe("?tab=evidence&speed=2");
    expect(window.location.hash).toBe("#ledgerlens-section-evidence");
  });

  it("shows the reason of a refused artifact instead of a partial render", async () => {
    // It proves that a refused artifact shows the reason and nothing else: no tree, no timeline, no evidence and no
    // answer, because a reader cannot tell which parts of a half drawn run are true.
    renderViewer({ error: "the bundle of the scenario S01 did not pass the integrity check" });

    expect(await screen.findByText(/did not pass the integrity check/)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "The tree of the investigation" })).toBeNull();
    expect(screen.queryByRole("region", { name: "The timeline of the recording" })).toBeNull();
    expect(screen.queryByRole("region", { name: "The evidence of the answer" })).toBeNull();
    expect(screen.queryByRole("region", { name: "The claims of the answer" })).toBeNull();
    expect(screen.queryByRole("region", { name: "The provenance of the recording" })).toBeNull();
    expect(screen.queryByText(MANIFEST.note)).toBeNull();
    expect(screen.queryByRole("table", { name: "The calls of the tools of the recorded run" })).toBeNull();
  });

  it("shows the empty state for a bundle that carries no event", async () => {
    // It proves that a bundle with no event shows the empty state and not a run with nothing in it.
    renderViewer({ manifest: MANIFEST, events: [], provenance: PROVENANCE });

    await waitFor(() => {
      expect(screen.getAllByText(/S01/).length).toBeGreaterThan(0);
    });
    expect(screen.queryByRole("region", { name: "The tree of the investigation" })).toBeNull();
    expect(screen.queryByRole("region", { name: "The timeline of the recording" })).toBeNull();
    expect(screen.queryByRole("region", { name: "The evidence of the answer" })).toBeNull();
    expect(screen.queryByRole("region", { name: "The claims of the answer" })).toBeNull();
  });

  it("shows the duration of a call of a tool the way the timeline writes it", async () => {
    // It proves that the latency of a call is written with the formatter of the durations and
    // never as the bare number of the recording, so that one timing of the recording has one
    // spelling on the screen.
    renderViewer(LOADED);

    await findLoadedRun();
    const slider = screen.getByRole("slider", { name: "Position of the recording" });
    const last = slider.getAttribute("max");
    fireEvent.change(slider, { target: { value: last ?? String(EVENTS.length - 1) } });

    const calls = await screen.findByRole("table", { name: "The calls of the tools of the recorded run" });
    await waitFor(() => {
      expect(within(calls).getByRole("rowheader", { name: "query_ledger" })).toBeInTheDocument();
    });

    // the header of the column says what the column holds, the way the timeline says it
    expect(
      within(calls).getByRole("columnheader", { name: "Duration the capture measured" }),
    ).toBeInTheDocument();

    const row = within(calls).getByRole("rowheader", { name: "query_ledger" }).closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("12 ms")).toBeInTheDocument();
    expect(within(row as HTMLElement).queryByText("12")).toBeNull();
  });

  it("writes a call of a tool that takes more than a second in seconds", async () => {
    // It proves that the column of the latency writes a duration of more than a second the way the
    // timeline writes it, and never as the bare number of the recording.
    renderViewer({ manifest: MANIFEST, events: EVENTS_WITH_A_SLOW_CALL, provenance: PROVENANCE });

    await findLoadedRun();
    const slider = screen.getByRole("slider", { name: "Position of the recording" });
    const last = slider.getAttribute("max");
    fireEvent.change(slider, { target: { value: last ?? String(EVENTS_WITH_A_SLOW_CALL.length - 1) } });

    const calls = await screen.findByRole("table", { name: "The calls of the tools of the recorded run" });
    await waitFor(() => {
      expect(within(calls).getByRole("rowheader", { name: "calculate" })).toBeInTheDocument();
    });

    const row = within(calls).getByRole("rowheader", { name: "calculate" }).closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("1.2 s")).toBeInTheDocument();
    expect(within(row as HTMLElement).queryByText("1200")).toBeNull();
  });

  it("reads the bundle of the scenario with the loader of the library", async () => {
    // It proves that the loader that reads the published artifacts lives in the library of the interface and not in
    // the folder of the components, and that it still refuses a bundle that does not pass the contract.
    const impl = (async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.endsWith("manifest.json")
        ? JSON.stringify({ bundle_schema_version: "1" })
        : url.endsWith("events.jsonl")
          ? ""
          : "";
      return { ok: true, status: 200, text: async () => body } as unknown as Response;
    }) as unknown as typeof fetch;

    const loaded = await loadReplay(SCENARIO, impl);

    expect("error" in loaded).toBe(true);
    if ("error" in loaded) {
      expect(loaded.error).toContain("did not pass the contract");
    }
  });
});
