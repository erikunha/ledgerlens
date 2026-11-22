/**
 * The client of the static artifacts of the recorded demo.
 *
 * Why this file exists: the recorded demo reads the published files of the site and nothing else,
 * so it needs no backend, no key and no network. This module is the ONE place that reads those
 * files: the catalog of the scenarios, the manifest of a bundle, the events of the recording and
 * the provenance file next to them. The folder of the components never reads the network, so the
 * rule that the demo works offline can be checked by reading this file alone.
 *
 * Why the loader never throws at the caller: it returns the bundle it read, or the reason it
 * refused it. The caller decides what to show, and the reason is a sentence a reader can act on.
 * A half drawn run is worse than no run, because a reader cannot tell which parts of it are true
 * (ADR-043).
 *
 * Why the integrity of the bundle is checked here: the manifest publishes the digest of each file
 * of the bundle, and a file whose digest does not match the digest that was declared is a bundle
 * the site refuses (FR-038). The digest is computed with the Web Crypto of the browser, and the
 * function that computes it can be injected, so a unit test never needs a browser. The ABSENCE of
 * the Web Crypto is not a refusal: the check is then unknown, and the panel says that the
 * integrity was not checked.
 *
 * Why a bundle that declares a live run is refused here: this site publishes only the
 * deterministic sandbox, and the label of the mode of a live run must never reach a visitor of the
 * replay. The refusal happens in the ONE place that reads the artifacts, so no other door can let
 * a live bundle through (ADR-043).
 */

import type { ReplayBundleManifest, ScenarioIndexEntry, TraceEvent } from "@/lib/api/schemas";
import { validateManifest, validateScenarioIndex, validateTraceEvent } from "@/lib/replay/validate";

/**
 * The root of the published artifacts of the site.
 *
 * Why the path is fixed: the artifacts are part of the static export, under `public/replay`, and
 * the site is served from the root of that export.
 */
export const ARTIFACT_ROOT = "/replay";

/**
 * The catalog of the scenarios, as the static export publishes it.
 *
 * Why the path is fixed: the catalog is the index of the export, next to the folders of the
 * bundles.
 */
const CATALOG_URL = `${ARTIFACT_ROOT}/index.json`;

/**
 * A recorded run that the site read and accepted.
 *
 * Why the provenance is a field and not a requirement: a bundle without a provenance file is
 * still a bundle, and a bundle whose provenance file is not a JSON document is still a bundle. The
 * panel shows what the artifact carries and nothing else.
 */
export interface LoadedReplay {
  /** The manifest of the bundle. */
  readonly manifest: ReplayBundleManifest;
  /** The events of the recording, in the order they were recorded. */
  readonly events: readonly TraceEvent[];
  /** The provenance file of the bundle, when it could be read. */
  readonly provenance: Readonly<Record<string, unknown>> | null;
  /**
   * Whether the integrity of the bundle was really checked.
   *
   * Why the field exists: the absence of the Web Crypto is not a refusal, so a bundle that was
   * accepted without a check has to say that it was accepted without a check, and the panel of the
   * provenance never shows a bundle as verified when it was not.
   *
   * Why the field is optional: a loader that was written before the field existed stays valid, and
   * a bundle that carries no field is a bundle whose integrity is unknown.
   */
  readonly integrity?: BundleIntegrity;
}

/**
 * Whether the integrity of the bundle could really be checked.
 *
 * Why the check can be unknown: the digest is computed with the Web Crypto of the browser, and a
 * browser that offers no Web Crypto computes no digest. The absence of the Web Crypto is not a
 * refusal, it is a check that could not be made, and the caller says so out loud (ADR-043).
 */
export type BundleIntegrity = "checked" | "unknown";

/**
 * The function that computes the sha256 of a sequence of bytes.
 *
 * Why it is a type of its own: the digest of the browser is not available in every environment,
 * and a unit test has to be able to say what the digest is without a browser.
 */
export type Sha256Hex = (bytes: ArrayBuffer) => Promise<string>;

/** The name of the file of the events of a bundle. */
const EVENTS_FILE = "events.jsonl";

/** The name of the file of the manifest of a bundle. */
const MANIFEST_FILE = "manifest.json";

/** Takes the fetch of the caller, or the fetch of the runtime. */
function resolveFetch(fetchImpl?: typeof fetch): typeof fetch {
  return fetchImpl ?? ((input: RequestInfo | URL, init?: RequestInit) => globalThis.fetch(input, init));
}

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
 * The sha256 of the bytes, computed with the Web Crypto of the browser.
 *
 * Why it returns null when there is no Web Crypto: the absence of the Web Crypto is not a
 * refusal, it only means that the integrity cannot be checked. The caller says so out loud.
 */
function browserSha256(): Sha256Hex | null {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) {
    return null;
  }
  return async (bytes: ArrayBuffer) => {
    const digest = await subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
  };
}

/** The bytes of a text, as the bytes of the file that carried it. */
function bytesOf(text: string): ArrayBuffer {
  return new TextEncoder().encode(text).buffer as ArrayBuffer;
}

/** Reads a digest out of a record, when the record holds a non empty string. */
function readDigest(source: unknown, key: string): string | null {
  if (typeof source !== "object" || source === null || Array.isArray(source)) {
    return null;
  }
  const value = (source as Record<string, unknown>)[key];
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

/** Reads a map of digests out of a record, when the record holds one. */
function readDigestMap(source: unknown): Record<string, string> {
  if (typeof source !== "object" || source === null || Array.isArray(source)) {
    return {};
  }
  const digests: Record<string, string> = {};
  for (const [name, value] of Object.entries(source as Record<string, unknown>)) {
    if (typeof value === "string" && value.trim() !== "") {
      digests[name] = value.trim();
    }
  }
  return digests;
}

/**
 * Reads the catalog of the scenarios from the published artifacts of the site.
 *
 * The loader never throws at the caller: it returns the catalog it read, or the reason it refused
 * it. A catalog that does not pass the contract is refused with the reasons of the validator, so
 * the reader knows which card is broken.
 */
export async function loadScenarioCatalog(
  fetchImpl?: typeof fetch,
): Promise<ScenarioIndexEntry[] | { error: string }> {
  const doFetch = resolveFetch(fetchImpl);

  let catalogText: string;
  try {
    const response = await doFetch(CATALOG_URL);
    if (!response.ok) {
      return {
        error: `the catalog of the scenarios could not be read: the site answered ${response.status}`,
      };
    }
    catalogText = await response.text();
  } catch {
    return { error: "the catalog of the scenarios could not be read: the site did not answer" };
  }

  let rawCatalog: unknown;
  try {
    rawCatalog = JSON.parse(catalogText);
  } catch {
    return { error: "the catalog of the scenarios is not a JSON document" };
  }

  const catalog = validateScenarioIndex(rawCatalog);
  if (!catalog.ok) {
    return {
      error: `the catalog of the scenarios did not pass the contract of the published artifacts: ${catalog.reasons.join("; ")}`,
    };
  }

  return catalog.value;
}

/**
 * Reads the bundle of a scenario from the published artifacts of the site.
 *
 * The loader never throws at the caller: it returns the bundle it read, or the reason it refused
 * it, and the caller decides what to show.
 *
 * Why the provenance file is read but never refused: a bundle without a provenance file is still
 * a bundle, and the panel shows what the artifact carries. A provenance file that is not a JSON
 * document is read as if it were not there, because a broken sidecar does not make the recording
 * unreadable.
 *
 * Why the integrity of the bundle is checked: the manifest publishes the digest of the file of the
 * events, and a file whose digest does not match the digest that was declared is refused with the
 * expected digest and the observed one (FR-038).
 *
 * Why a bundle that declares a live run is refused: this site publishes only the deterministic
 * sandbox, so a bundle that declares another mode is refused with the reason that the visitor can
 * act on, and the label of a live run never reaches the screen (ADR-043).
 */
export async function loadReplay(
  index: ScenarioIndexEntry,
  fetchImpl?: typeof fetch,
): Promise<LoadedReplay | { error: string }> {
  const doFetch = resolveFetch(fetchImpl);

  const directory = bundleDirectory(index);
  const manifestUrl = `${ARTIFACT_ROOT}/${directory}/${MANIFEST_FILE}`;
  const eventsUrl = `${ARTIFACT_ROOT}/${directory}/${EVENTS_FILE}`;
  const provenanceUrl = `${ARTIFACT_ROOT}/${directory}/provenance.json`;

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

  // A bundle that declares a live run is not a recording of this site. The site publishes only the
  // deterministic sandbox, so the bundle is refused here, in the ONE place that reads the
  // artifacts, and the label of a live run never reaches a visitor of the replay (ADR-043).
  if (manifest.value.mode === "live_agent") {
    return {
      error: `the bundle of the scenario ${index.id} declares the mode live_agent, and this site publishes only the deterministic sandbox`,
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

  const provenance = await readProvenance(provenanceUrl, doFetch);

  const integrity = await verifyBundleDigests({
    manifest: manifest.value,
    eventsBytes: bytesOf(eventsText),
    provenance,
  });
  const manifestReasons = await verifyManifestDigest(manifestText, provenance);
  if (!integrity.ok) {
    return {
      error: `the bundle of the scenario ${index.id} did not pass the integrity check: ${[...integrity.reasons, ...manifestReasons].join("; ")}`,
    };
  }
  if (manifestReasons.length > 0) {
    return {
      error: `the bundle of the scenario ${index.id} did not pass the integrity check: ${manifestReasons.join("; ")}`,
    };
  }

  return { manifest: manifest.value, events, provenance, integrity: integrity.integrity };
}

/**
 * Reads the provenance file of a bundle.
 *
 * Why nothing here is a refusal: the file is a sidecar, and a bundle without it is still a bundle.
 * The answer is null when the file is missing, when the site did not answer and when the file is
 * not a JSON document.
 */
async function readProvenance(
  url: string,
  doFetch: typeof fetch,
): Promise<Readonly<Record<string, unknown>> | null> {
  let text: string;
  try {
    const response = await doFetch(url);
    if (!response.ok) {
      return null;
    }
    text = await response.text();
  } catch {
    return null;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return null;
  }

  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return null;
  }
  return parsed as Readonly<Record<string, unknown>>;
}

/**
 * Checks the digest of the file of the events against the digest that was published for it.
 *
 * Why the digest function can be injected: a unit test has to be able to say what the digest of a
 * file is without a browser, and the browser computes it with the Web Crypto.
 *
 * Why a mismatch is a refusal and not a warning: the site refuses a bundle whose file digest does
 * not match the digest that its manifest declares, and it renders no partial result (FR-038).
 *
 * Why the absence of the Web Crypto is not a refusal: the check is then unknown, and an unknown
 * check is not a broken bundle. The answer is `{ ok: true, integrity: "unknown" }` with no reason
 * at all, and the caller says out loud that the integrity was not checked.
 */
export async function verifyBundleDigests(input: {
  readonly manifest: ReplayBundleManifest;
  readonly eventsBytes: ArrayBuffer;
  readonly provenance?: Readonly<Record<string, unknown>> | null;
  readonly sha256?: Sha256Hex;
}): Promise<
  | { readonly ok: true; readonly integrity: BundleIntegrity }
  | { readonly ok: false; readonly reasons: readonly string[] }
> {
  const sha256 = input.sha256 ?? browserSha256();
  if (!sha256) {
    return { ok: true, integrity: "unknown" };
  }

  let observed: string;
  try {
    observed = await sha256(input.eventsBytes);
  } catch {
    // A digest function that fails is not a broken bundle, so the check stays unknown.
    return { ok: true, integrity: "unknown" };
  }

  const expectations: { source: string; digest: string }[] = [];
  const fromManifest = input.manifest.files[EVENTS_FILE];
  if (typeof fromManifest === "string" && fromManifest.trim() !== "") {
    expectations.push({ source: "the manifest", digest: fromManifest.trim() });
  }
  const fromProvenanceFiles = readDigestMap(input.provenance?.["files"])[EVENTS_FILE];
  if (fromProvenanceFiles) {
    expectations.push({ source: "the provenance", digest: fromProvenanceFiles });
  }
  const fromProvenanceArtifacts = readDigestMap(input.provenance?.["artifacts"])[EVENTS_FILE];
  if (fromProvenanceArtifacts) {
    expectations.push({ source: "the provenance", digest: fromProvenanceArtifacts });
  }

  const reasons: string[] = [];
  for (const expectation of expectations) {
    if (expectation.digest !== observed) {
      reasons.push(
        `the digest of the file ${EVENTS_FILE} does not match the digest that ${expectation.source} published: expected ${expectation.digest}, observed ${observed}`,
      );
    }
  }

  if (reasons.length > 0) {
    return { ok: false, reasons };
  }
  return { ok: true, integrity: "checked" };
}

/**
 * Checks the digest of the manifest against the digest that the provenance published for it.
 *
 * Why the manifest is checked here and not in `verifyBundleDigests`: the digest of the manifest is
 * the `bundle_digest` of the provenance file, and the bytes of the manifest are the ones the
 * loader read, so the two belong together.
 *
 * Why nothing is a refusal when the provenance is not there: a bundle without a provenance file
 * publishes no digest of the manifest, so there is nothing to compare the manifest with.
 */
async function verifyManifestDigest(
  manifestText: string,
  provenance: Readonly<Record<string, unknown>> | null,
  sha256?: Sha256Hex,
): Promise<string[]> {
  const digest = sha256 ?? browserSha256();
  if (!digest || !provenance) {
    return [];
  }

  const expectations: string[] = [];
  const bundleDigest = readDigest(provenance, "bundle_digest");
  if (bundleDigest) {
    expectations.push(bundleDigest);
  }
  const artifactDigest = readDigestMap(provenance["artifacts"])[MANIFEST_FILE];
  if (artifactDigest) {
    expectations.push(artifactDigest);
  }
  if (expectations.length === 0) {
    return [];
  }

  let observed: string;
  try {
    observed = await digest(bytesOf(manifestText));
  } catch {
    return [];
  }

  const reasons: string[] = [];
  for (const expected of expectations) {
    if (expected !== observed) {
      reasons.push(
        `the digest of the file ${MANIFEST_FILE} does not match the digest that the provenance published: expected ${expected}, observed ${observed}`,
      );
    }
  }
  return reasons;
}

/** Every symbol this module exports, so that a reader sees the whole surface of the client at once. */
export const __all__ = [
  "ARTIFACT_ROOT",
  "BundleIntegrity",
  "LoadedReplay",
  "Sha256Hex",
  "loadScenarioCatalog",
  "loadReplay",
  "verifyBundleDigests",
] as const;
