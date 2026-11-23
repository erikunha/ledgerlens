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
import type { LedgerArtifact, ReplayBundleManifest, ScenarioIndexEntry, TraceEvent } from "@/lib/api/schemas";

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
/**
 * The published events of the recording, with the latency of the read of the ledger fixed.
 *
 * Why the case fixes the latency: the duration that the recording carries changes with every recapture of the
 * scenario, and a case that repeats a number of the recording breaks every time the scenario is recorded again.
 * The case fixes the number and proves the spelling of the duration, which is what the column promises.
 */
const EVENTS_WITH_A_KNOWN_LATENCY: readonly TraceEvent[] = EVENTS.map((event) => {
  const payload = event.payload ?? {};
  if (payload.run_type !== "tool" || payload.name !== "query_ledger") {
    return event;
  }
  return { ...event, payload: { ...payload, latency_ms: 120 } };
});

const EVENTS_WITH_A_SLOW_CALL: readonly TraceEvent[] = EVENTS.map((event) => {
  const payload = event.payload ?? {};
  if (payload.run_type !== "tool" || payload.name !== "calculate") {
    return event;
  }
  return { ...event, payload: { ...payload, latency_ms: 1200 } };
});

/**
 * The commit of the checkout that the links of the engineering drawer open.
 *
 * Why the case carries a commit: the reader opens the engineering drawer, and the links of the
 * drawer open the tree of that commit. The case does not read the repository, so it names a commit
 * of forty hexadecimal characters and the drawer shows the links of that tree (ADR-046).
 */
const COMMIT = "0123456789abcdef0123456789abcdef01234567";

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

/**
 * The artifact of the ledger of the scenario S01, as `site/replay/s01/ledger.json` holds it.
 *
 * Why the artifact is a literal here: the case proves that the reader opens the panel of the
 * ledger, and the bytes of the artifact are not the subject of this case.
 */
const LEDGER: LedgerArtifact = {
  schema_version: "1",
  scenario: "S01",
  snapshot_sha256: "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
  page_size: 50,
  accounts: [
    {
      id: "C-0412",
      kind: "customer",
      name: "Mariana Albuquerque Costa",
      rows: [
        {
          kind: "transaction",
          id: "TX-2048",
          at: "2026-10-15T09:12:00Z",
          amount: "100.00",
          currency: "EUR",
          status: "refunded",
        },
        {
          kind: "refund",
          id: "R-0731",
          at: "2026-10-20T14:05:00Z",
          amount: "549.31",
          currency: "BRL",
          status: "paid",
        },
      ],
      reads: [
        {
          evidence_id: "sql:1",
          seq: 19,
          tool: "query_ledger",
          sql: "SELECT * FROM (SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at) LIMIT 50",
          columns: ["kind", "applied_rate", "applied_at"],
          row_count: 2,
          truncated: false,
          records: ["TX-2048"],
          rows: [
            { kind: "charge", applied_rate: "5.6679", applied_at: "2026-10-15T09:12:04Z" },
            { kind: "refund", applied_rate: "5.4931", applied_at: "2026-10-20T14:30:00Z" },
          ],
        },
      ],
    },
  ],
};

/**
 * The bundle that the loader of the case answers with.
 *
 * Why the bundle carries the artifact of the ledger: the site publishes the rows the run read
 * beside the recording, and the tab of the ledger shows them (ADR-045).
 */
const LOADED: LoadedReplay = {
  manifest: MANIFEST,
  events: EVENTS,
  provenance: PROVENANCE,
  ledger: LEDGER,
};

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
      <ReplayViewer commit={COMMIT} scenario={SCENARIO} />
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

/**
 * Moves the recording to its end, so that the table of the calls shows every call of the capture.
 *
 * Why the helper exists: the table of the calls shows the calls that already happened, and a case that opens the
 * drawer about a call needs that call to be on the screen.
 */
async function moveTheRecordingToTheEnd(): Promise<void> {
  const slider = screen.getByRole("slider", { name: "Position of the recording" });
  const last = slider.getAttribute("max");
  fireEvent.change(slider, { target: { value: last ?? String(EVENTS.length - 1) } });
  await waitFor(() => {
    expect(screen.getByText(new RegExp(`Event ${EVENTS.length} of ${EVENTS.length}\\.`))).toBeInTheDocument();
  });
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
      expect(within(calls).getByRole("rowheader", { name: /query_ledger/ })).toBeInTheDocument();
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

  it("shows the stepper of the run with the four steps of the recording", async () => {
    // It proves that the stepper is in the tab of the execution and that it shows the calls of the recording, in the
    // order the capture made them. The recording stands at its first event, so no step of it is the current one yet.
    renderViewer(LOADED);

    await findLoadedRun();
    const panel = await findPanel("The steps of the run", "Execution");
    expect(panel).not.toBeNull();

    const items = within(panel as HTMLElement).getAllByRole("listitem");
    expect(items).toHaveLength(4);
    expect(items.map((item) => item.textContent)).toEqual([
      "Step 1 of 4: query_ledger. Not started yet.",
      "Step 2 of 4: search_policies. Not started yet.",
      "Step 3 of 4: get_reference_fx. Not started yet.",
      "Step 4 of 4: calculate. Not started yet.",
    ]);
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

  it("has five sections of the replay and the ledger sits between the execution and the evidence", async () => {
    // It proves the order of the sections: the reader sees what the run did, then the rows it
    // read, then what it gathered, then what it concluded and then the proof of the recording.
    renderViewer(LOADED);

    await findLoadedRun();
    const tabs = screen.getByRole("tablist", { name: "The sections of the replay" });
    expect(
      within(tabs)
        .getAllByRole("tab")
        .map((tab) => tab.textContent),
    ).toEqual(["Execution", "Ledger", "Evidence", "Decision", "Provenance"]);
  });

  it("opens the panel of the ledger from the tab of the ledger", async () => {
    // It proves that the fifth tab opens the panel of the ledger, with the movements of the
    // account and the amount the artifact carries.
    renderViewer(LOADED);

    await findLoadedRun();
    const trigger = screen.getByRole("tab", { name: "Ledger" });
    await userEvent.setup().click(trigger);

    const table = await screen.findByRole("table", { name: "The movements of the account C-0412" });
    expect(within(table).getByRole("rowheader", { name: "TX-2048" })).toBeInTheDocument();
    expect(within(table).getByText("EUR 100.00")).toBeInTheDocument();
  });

  it("keeps the state of the visit in the tab and the speed and nothing else", async () => {
    // It proves that the address of the visit carries the tab and the speed and nothing else: the
    // account that is chosen and the row that is open live in the memory of the panel.
    renderViewer(LOADED);

    await findLoadedRun();
    await userEvent.setup().click(screen.getByRole("tab", { name: "Ledger" }));

    expect(window.location.pathname).toBe("/");
    expect(window.location.search).toBe("?tab=ledger&speed=1");
    expect(window.location.href).not.toContain("TX-2048");
    expect(window.location.href).not.toContain("C-0412");
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
    renderViewer({ manifest: MANIFEST, events: EVENTS_WITH_A_KNOWN_LATENCY, provenance: PROVENANCE });

    await findLoadedRun();
    const slider = screen.getByRole("slider", { name: "Position of the recording" });
    const last = slider.getAttribute("max");
    fireEvent.change(slider, { target: { value: last ?? String(EVENTS_WITH_A_KNOWN_LATENCY.length - 1) } });

    const calls = await screen.findByRole("table", { name: "The calls of the tools of the recorded run" });
    await waitFor(() => {
      expect(within(calls).getByRole("rowheader", { name: /query_ledger/ })).toBeInTheDocument();
    });

    // the header of the column says what the column holds, the way the timeline says it
    expect(
      within(calls).getByRole("columnheader", { name: "Duration the capture measured" }),
    ).toBeInTheDocument();

    const row = within(calls).getByRole("rowheader", { name: /query_ledger/ }).closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("120 ms")).toBeInTheDocument();
    expect(within(row as HTMLElement).queryByText("120")).toBeNull();
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
      expect(within(calls).getByRole("rowheader", { name: /calculate/ })).toBeInTheDocument();
    });

    const row = within(calls).getByRole("rowheader", { name: /calculate/ }).closest("tr");
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

  it("opens the drawer of a call about the row, with a real button that announces the window", async () => {
    // It proves that the trigger of the drawer of a call is a real button in the row header cell of the table of the
    // calls, that it announces the window it opens and that it is not a stop of the keyboard: the cells of the table
    // are the navigation group of the table and the cell is the stop (ADR-048, decision 2).
    renderViewer(LOADED);

    await findLoadedRun();
    await moveTheRecordingToTheEnd();

    const calls = screen.getByRole("table", { name: "The calls of the tools of the recorded run" });
    const trigger = await within(calls).findByRole("button", { name: "query_ledger Event 19" });

    expect(trigger).toHaveAttribute("aria-haspopup", "dialog");
    expect(trigger).toHaveAttribute("tabindex", "-1");

    // the button sits in the row header cell, the cell that holds the name of the tool
    const cell = trigger.closest("th");
    expect(cell).not.toBeNull();
    expect(cell).toHaveAttribute("scope", "row");
  });

  it("opens the drawer of a call with the Enter key on the cell of the name of the tool", async () => {
    // It proves that the Enter key on the cell of the name of the tool opens the drawer about the call of that row,
    // the way the Enter key on the cell of the event number moves the recording in the timeline.
    const user = userEvent.setup();
    renderViewer(LOADED);

    await findLoadedRun();
    await moveTheRecordingToTheEnd();

    const calls = screen.getByRole("table", { name: "The calls of the tools of the recorded run" });
    const cell = within(calls).getByRole("rowheader", { name: /query_ledger/ });
    cell.focus();

    await user.keyboard("{Enter}");

    const drawer = await screen.findByRole("dialog");
    expect(drawer).toHaveAccessibleName("The call of query_ledger");
    expect(drawer).toHaveTextContent("FX rates applied to TX-2048");
  });

  it("closes the drawer of a call with the Escape key and gives the focus back to the cell that opened it", async () => {
    // It proves that the focus comes back to the CELL that opened the drawer and not to the button inside it, so that
    // the navigation group of the table survives the window (ADR-048, decision 7).
    const user = userEvent.setup();
    renderViewer(LOADED);

    await findLoadedRun();
    await moveTheRecordingToTheEnd();

    const calls = screen.getByRole("table", { name: "The calls of the tools of the recorded run" });
    const cell = within(calls).getByRole("rowheader", { name: /query_ledger/ });
    cell.focus();

    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    await waitFor(() => {
      expect(cell).toHaveFocus();
    });
  });

  it("holds the call it was opened with when the recording moves to another call", async () => {
    // It proves that the drawer of a call holds the call it was opened with: a call of the recording is a fact, and a
    // drawer whose content changes under the eyes of the reader is a drawer that lies (ADR-048, decision 3).
    const user = userEvent.setup();
    renderViewer(LOADED);

    await findLoadedRun();
    const slider = screen.getByRole("slider", { name: "Position of the recording" });

    // the recording stands on the event that closed the call of the ledger
    const moment = EVENTS.findIndex((event) => event.seq === 19);
    fireEvent.change(slider, { target: { value: String(moment) } });

    const calls = screen.getByRole("table", { name: "The calls of the tools of the recorded run" });
    await waitFor(() => {
      expect(within(calls).getByRole("rowheader", { name: /query_ledger/ })).toBeInTheDocument();
    });

    const cell = within(calls).getByRole("rowheader", { name: /query_ledger/ });
    cell.focus();
    await user.keyboard("{Enter}");

    const drawer = await screen.findByRole("dialog");
    expect(drawer).toHaveAccessibleName("The call of query_ledger");

    // the recording moves on and the table of the calls grows. The page around the drawer is
    // hidden while the drawer is open, so the case reads the step of the recording by its text.
    fireEvent.change(slider, { target: { value: String(EVENTS.length - 1) } });
    await waitFor(() => {
      expect(screen.getByText(new RegExp(`Event ${EVENTS.length} of ${EVENTS.length}\\.`))).toBeInTheDocument();
    });

    // the drawer still shows the call it was opened with
    expect(screen.getByRole("dialog")).toHaveAccessibleName("The call of query_ledger");
    expect(screen.getByRole("dialog")).toHaveTextContent("FX rates applied to TX-2048");
    expect(screen.getByRole("dialog")).not.toHaveTextContent("calculate");
  });

  it("still opens the drawer of the engineering tour", async () => {
    // It proves that the drawer of a call of the recording did not take the place of the drawer of the engineering
    // tour: the two are two windows and the visitor reaches both (ADR-046, ADR-048).
    renderViewer(LOADED);

    await findLoadedRun();
    await userEvent.setup().click(screen.getByRole("button", { name: "Open the engineering drawer" }));

    const drawer = await screen.findByRole("dialog");
    expect(drawer).toHaveTextContent("This drawer is not tied to one call of the recording.");
  });
});
