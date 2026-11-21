/**
 * The loader of the static artifacts of the recorded demo.
 *
 * Why this file exists: the recorded demo reads the published files of the site and nothing else,
 * so it needs no backend, no key and no network. The loader is the only place that reads those
 * files, and it validates every one of them before the interface renders anything: an event that
 * is not a trace event, or a manifest that does not match the contract, is refused with a reason a
 * reader can act on, and the reader shows that reason instead of a half drawn run.
 *
 * Why the loader reads the events line by line: the file carries one JSON object per line, and a
 * line that is broken is a line that has to be refused on its own, with the number of the line.
 *
 * Why the manifest is read as it is published: the repository publishes the manifest with
 * `bundle_schema_version`, and the loader validates it exactly like that. A manifest that spells
 * the version in any other way is refused, because a recording the interface does not understand
 * is not a recording (ADR-042).
 */

import type { ReplayBundleManifest, ScenarioIndexEntry, TraceEvent } from "@/lib/api/schemas";
import { validateManifest, validateTraceEvent } from "@/lib/replay/validate";

/**
 * A recorded run that the site read and accepted.
 *
 * Why the manifest and the events are the whole of it: the manifest says in words what the bundle
 * is, and the events are the recording itself.
 */
export interface LoadedReplay {
  /** The manifest of the bundle. */
  manifest: ReplayBundleManifest;
  /** The events of the recording, in the order they were recorded. */
  events: TraceEvent[];
}

/**
 * The root of the published artifacts of the site.
 *
 * Why the path is fixed: the artifacts are part of the static export, under `public/replay`, and
 * the site is served from the root of that export.
 */
const ARTIFACT_ROOT = "/replay";

/**
 * The directory of the bundle of a scenario.
 *
 * Why the identifier is the fallback: the catalog of the site publishes the scenario as `S01`, and
 * the directory of its bundle is the same name in lower case.
 */
function bundleDirectory(scenario: ScenarioIndexEntry): string {
  const declared = scenario.bundle_path?.trim();
  if (declared) {
    return declared.replace(/^\/+/, "").replace(/\/+$/, "");
  }
  return scenario.id.toLowerCase();
}

/**
 * Reads the bundle of a scenario from the published artifacts of the site.
 *
 * The loader never throws at the caller: it returns the bundle it read, or the reason it refused
 * it, and the caller decides what to show.
 */
export async function loadReplay(
  index: ScenarioIndexEntry,
  fetchImpl?: typeof fetch,
): Promise<LoadedReplay | { error: string }> {
  const doFetch: typeof fetch =
    fetchImpl ?? ((input: RequestInfo | URL, init?: RequestInit) => globalThis.fetch(input, init));

  const directory = bundleDirectory(index);
  const manifestUrl = `${ARTIFACT_ROOT}/${directory}/manifest.json`;
  const eventsUrl = `${ARTIFACT_ROOT}/${directory}/events.jsonl`;

  let manifestText: string;
  try {
    const response = await doFetch(manifestUrl);
    if (!response.ok) {
      return {
        error: `the manifest of the scenario ${index.id} could not be read: the site answered ${response.status}`,
      };
    }
    manifestText = await response.text();
  } catch {
    return { error: `the manifest of the scenario ${index.id} could not be read: the site did not answer` };
  }

  let rawManifest: unknown;
  try {
    rawManifest = JSON.parse(manifestText);
  } catch {
    return { error: `the manifest of the scenario ${index.id} is not a JSON document` };
  }

  const manifest = validateManifest(rawManifest);
  if (!manifest.ok) {
    return {
      error: `the manifest of the scenario ${index.id} did not pass the contract of the bundle: ${manifest.reasons.join("; ")}`,
    };
  }

  let eventsText: string;
  try {
    const response = await doFetch(eventsUrl);
    if (!response.ok) {
      return {
        error: `the events of the scenario ${index.id} could not be read: the site answered ${response.status}`,
      };
    }
    eventsText = await response.text();
  } catch {
    return { error: `the events of the scenario ${index.id} could not be read: the site did not answer` };
  }

  const events: TraceEvent[] = [];
  const lines = eventsText.split("\n");
  for (const [position, line] of lines.entries()) {
    const trimmed = line.trim();
    if (trimmed === "") {
      continue;
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(trimmed);
    } catch {
      return {
        error: `the line ${position + 1} of the events of the scenario ${index.id} is not a JSON document`,
      };
    }

    const event = validateTraceEvent(parsed);
    if (!event.ok) {
      return {
        error: `the events of the scenario ${index.id} did not pass the contract of the bundle: ${event.reasons.join("; ")}`,
      };
    }
    events.push(event.value);
  }

  return { manifest: manifest.value, events };
}
