/**
 * The summary of the provenance of a bundle.
 *
 * Why this file exists: the provenance panel shows where the recording came from, and every word of that panel has
 * to come from the artifact. The browser never invents a digest, never shows a hash it did not read and never calls a
 * bundle fresh or stale on a comparison it did not make. The digest shown is the one the artifact publishes, the
 * `bundle_digest` of the provenance file, which is the sha256 of the manifest.
 *
 * The panel also says whether the integrity of the bundle was really checked: the absence of the Web Crypto is not a
 * refusal, so a bundle that was accepted without a check says so, and the panel never shows a bundle as verified when
 * it was not (ADR-043).
 */

import type { BundleIntegrity } from "@/lib/api/replay";
import type { CaptureKind, ReplayBundleManifest, TraceMode } from "@/lib/api/schemas";

/** How the snapshot of the recording compares with the hash that was published next to it. */
export type SnapshotFreshness = "fresh" | "stale" | "unknown";

/** What the provenance panel shows about a bundle. */
export interface ProvenanceSummary {
  /** The digest of the bundle, as the artifact published it. */
  readonly bundleDigest: string | null;
  /** The label of the mode of the recording. */
  readonly modeLabel: string;
  /** The label of the kind of the capture. */
  readonly captureLabel: string;
  /** The moment of the capture, when the artifact carries one. */
  readonly recordedAt: string | null;
  /** The hash of the snapshot the run read, when the artifact carries one. */
  readonly snapshotSha256: string | null;
  /** The hash of the code commit that produced the run, when the artifact carries one. */
  readonly codeSha: string | null;
  /** The profile of the model the run used, when the artifact carries one. */
  readonly modelProfile: string | null;
  /**
   * The model that ran each task of the run, when the artifact carries one.
   *
   * Why the summary carries the map and not a sentence: the panel shows one line per task, and the
   * words of the tasks live in one place so that the reader sees the same name everywhere (ADR-078).
   */
  readonly modelProfiles: Readonly<Record<string, string>>;
  /** The version of the policy the run read, when the artifact carries one. */
  readonly policyVersion: string | null;
  /** The digest of each file of the bundle, by file name. */
  readonly files: Readonly<Record<string, string>>;
  /** How the snapshot compares with the published hash. */
  readonly freshness: SnapshotFreshness;
  /** The sentence that says why the freshness is what it is. */
  readonly freshnessReason: string;
  /**
   * Whether the integrity of the bundle was really checked.
   *
   * Why the summary carries it: the absence of the Web Crypto is not a refusal, so a bundle that
   * was accepted without a check has to say so. A panel that shows a bundle as verified when it was
   * not says something false about the artifact.
   */
  readonly integrity: BundleIntegrity;
  /** The sentence that says why the integrity is what it is. */
  readonly integrityReason: string;
}

/** What the summary is built from: the manifest, the provenance file and the hash that was published next to them. */
export interface ProvenanceInput {
  /** The manifest of the bundle, when the bundle could be read. */
  readonly manifest: ReplayBundleManifest | null;
  /** The provenance file of the bundle, when it could be read. */
  readonly provenance?: Readonly<Record<string, unknown>> | null;
  /** The hash of the snapshot that was published next to the bundle, when there is one. */
  readonly publishedSnapshotSha256?: string | null;
  /**
   * Whether the integrity of the bundle was really checked.
   *
   * Why the field is optional: a caller that does not know says nothing, and the summary then says
   * that the integrity was not checked, because a bundle that was not checked must never be shown
   * as a bundle that was verified.
   */
  readonly integrity?: BundleIntegrity;
}

/** The labels of the modes of the contract. */
const MODE_LABELS: Readonly<Record<string, string>> = {
  deterministic_sandbox: "Recorded Replay",
  recorded_replay: "Recorded Replay",
  // The recording of a real model is a recording and not a run in progress: the panel must not say that a live
  // run is on the screen, because the visitor is reading a recording that the repository published (ADR-075).
  live_agent: "Recorded with a real model",
};

/** The labels of the kinds of capture of the contract. */
const CAPTURE_LABELS: Readonly<Record<string, string>> = {
  scripted_fixture: "Scripted fixture",
  real_model_recorded: "Real model recorded",
};

/** What the panel shows when the artifact carries nothing to show. */
const NOT_AVAILABLE = "Not available";

/**
 * The words of each task of a run.
 *
 * Why the words live here: the names of the slots are the names of the code, and a reader of the site reads
 * the task and not the identifier of the slot (ADR-078).
 */
const SLOT_LABELS: Readonly<Record<string, string>> = {
  agent: "The answer with the tools",
  triage: "The plan of the investigation",
  sql: "The statement that reads the ledger",
  policy: "The rewrite of the search of the policies",
};

/**
 * The words of a task of a run.
 *
 * A slot that the repository does not know keeps its own name, because a name nobody translated is still a name
 * and hiding it would lose the information.
 */
export function slotLabel(slot: string): string {
  return SLOT_LABELS[slot] ?? slot;
}

/**
 * Renders the label of the mode of a recording.
 *
 * The site publishes two catalogs, the recordings of the scripted model and the recordings of a real model, and the
 * label of each one says what the recording is. The label of a recording of a real model never says that a live run
 * is on the screen, because what the visitor reads is a recording that the repository published (ADR-075).
 */
export function modeLabel(mode: TraceMode | null | undefined): string {
  if (typeof mode !== "string") {
    return NOT_AVAILABLE;
  }
  return MODE_LABELS[mode] ?? NOT_AVAILABLE;
}

/**
 * Renders the label of the kind of the capture.
 *
 * A bundle captured from a scripted fixture is never presented as a run of a real model.
 */
export function captureLabel(kind: CaptureKind | null | undefined): string {
  if (typeof kind !== "string") {
    return NOT_AVAILABLE;
  }
  return CAPTURE_LABELS[kind] ?? NOT_AVAILABLE;
}

/**
 * Shortens a digest for the reader, with the first and the last four characters.
 *
 * A digest that is too short to be shortened is shown as it is, and a recording without a digest gives
 * `Not available`.
 */
export function formatDigest(digest: string | null | undefined): string {
  const text = typeof digest === "string" ? digest.trim() : "";
  if (text === "") {
    return NOT_AVAILABLE;
  }
  if (text.length <= 8) {
    return text;
  }
  return `${text.slice(0, 4)}...${text.slice(-4)}`;
}

/**
 * Compares the hash of the bundle with a published hash.
 *
 * The bundle is fresh only when a comparable hash was published and matches, stale only when a comparable hash was
 * published and differs, and unknown when there is nothing to compare with.
 */
export function snapshotFreshness(
  bundleSha256: string | null | undefined,
  publishedSha256: string | null | undefined,
): SnapshotFreshness {
  const bundle = typeof bundleSha256 === "string" ? bundleSha256.trim() : "";
  const published = typeof publishedSha256 === "string" ? publishedSha256.trim() : "";
  if (bundle === "" || published === "") {
    return "unknown";
  }
  return bundle === published ? "fresh" : "stale";
}

/** Reads a non empty string out of a record, whatever it holds. */
function readString(source: Readonly<Record<string, unknown>> | null | undefined, key: string): string | null {
  if (!source) {
    return null;
  }
  const value = source[key];
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

/** Reads the digest of each file of the bundle out of a record, keeping only the entries that are digests. */
function readFileMap(source: Readonly<Record<string, unknown>> | null | undefined): Record<string, string> {
  if (!source) {
    return {};
  }
  const value = source.files;
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return {};
  }
  const files: Record<string, string> = {};
  for (const [name, digest] of Object.entries(value as Record<string, unknown>)) {
    if (typeof digest === "string") {
      files[name] = digest;
    }
  }
  return files;
}

/**
 * Reads the model of each task of the run out of a record.
 *
 * Why only the entries that carry a text: a map with a value that is not a name would say which model ran which
 * task and the reader could not check it, so the map is read strictly (ADR-078).
 */
function readModelProfiles(source: Readonly<Record<string, unknown>> | null | undefined): Record<string, string> {
  if (!source) {
    return {};
  }
  const value = source.model_profiles;
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return {};
  }
  const profiles: Record<string, string> = {};
  for (const [slot, model] of Object.entries(value as Record<string, unknown>)) {
    if (typeof model === "string" && model.trim() !== "") {
      profiles[slot] = model.trim();
    }
  }
  return profiles;
}

/** Reads a mode out of a record, and only when it is one of the modes of the contract. */
function readMode(source: Readonly<Record<string, unknown>> | null | undefined): TraceMode | null {
  const mode = readString(source, "mode");
  if (mode === "deterministic_sandbox" || mode === "recorded_replay" || mode === "live_agent") {
    return mode;
  }
  return null;
}

/** Reads a kind of capture out of a record, and only when it is one of the kinds of the contract. */
function readCaptureKind(source: Readonly<Record<string, unknown>> | null | undefined): CaptureKind | null {
  const kind = readString(source, "capture_kind");
  if (kind === "scripted_fixture" || kind === "real_model_recorded") {
    return kind;
  }
  return null;
}

/** The sentence that says why the freshness is what it is. */
function freshnessReasonFor(freshness: SnapshotFreshness): string {
  switch (freshness) {
    case "fresh":
      return "The hash of the snapshot the run read matches the hash that was published, so the snapshot is fresh.";
    case "stale":
      return "The hash of the snapshot the run read differs from the hash that was published, so the snapshot is stale.";
    default:
      return "The freshness could not be checked, because no comparable hash was published next to the bundle.";
  }
}

/**
 * The sentence that says why the integrity is what it is.
 *
 * Why the sentence is there: the panel has to say out loud that the integrity was not checked when
 * the browser offered no Web Crypto, and it has to say the opposite only when the digests of the
 * bundle really matched the digests that the artifact published.
 */
function integrityReasonFor(integrity: BundleIntegrity): string {
  switch (integrity) {
    case "checked":
      return "The digests of the bundle match the ones that the artifact published, so the integrity of the bundle was checked.";
    default:
      return "The integrity of the bundle was not checked, because the browser did not offer the Web Crypto, so the digest of the bundle was not verified.";
  }
}

/**
 * Summarizes the provenance of a bundle.
 *
 * The digest is the `bundle_digest` of the provenance file when the file carries one, and the digest of the manifest
 * itself otherwise. The freshness is compared only when a comparable hash was published: the artifacts of the
 * repository carry the hash of the dataset file and the hash of the snapshot the run read, and those two are the hash
 * of two different things, so the panel says that the freshness could not be checked instead of calling the bundle
 * fresh or stale on a comparison it did not make.
 */
export function summarizeProvenance(input: ProvenanceInput): ProvenanceSummary {
  const manifest = input.manifest;
  const provenance = input.provenance ?? null;

  const mode = manifest?.mode ?? readMode(provenance);
  const kind = manifest?.capture_kind ?? readCaptureKind(provenance);

  const bundleDigest =
    readString(provenance, "bundle_digest") ?? manifest?.files["manifest.json"] ?? null;

  const snapshotSha256 = manifest?.snapshot_sha256 ?? readString(provenance, "snapshot_sha256");
  const published = input.publishedSnapshotSha256 ?? null;
  const datasetSha256 = readString(provenance, "dataset_sha256");

  // The hash of the dataset and the hash of the snapshot are two different things. When the hash that was published is
  // the hash of the dataset, there is nothing to compare with and the freshness stays unknown.
  const notComparable =
    datasetSha256 !== null &&
    published !== null &&
    datasetSha256.trim() === published.trim() &&
    datasetSha256.trim() !== (snapshotSha256 ?? "").trim();

  const freshness = notComparable ? "unknown" : snapshotFreshness(snapshotSha256, published);
  const freshnessReason = notComparable
    ? "The freshness could not be checked, because the published hash is the hash of the dataset and not the hash of the snapshot the run read."
    : freshnessReasonFor(freshness);

  // A caller that does not know whether the integrity was checked gets the state that never claims
  // that the bundle was verified when it was not.
  const integrity = input.integrity ?? "unknown";
  const integrityReason = integrityReasonFor(integrity);

  return {
    bundleDigest,
    modeLabel: modeLabel(mode),
    captureLabel: captureLabel(kind),
    recordedAt:
      manifest?.recorded_at ??
      readString(provenance, "recorded_at") ??
      manifest?.created_at ??
      readString(provenance, "created_at") ??
      null,
    snapshotSha256,
    codeSha: manifest?.code_sha ?? readString(provenance, "code_sha"),
    modelProfile: manifest?.model_profile ?? readString(provenance, "model_profile"),
    modelProfiles: manifest?.model_profiles ?? readModelProfiles(provenance),
    policyVersion: manifest?.policy_version ?? readString(provenance, "policy_version"),
    files: manifest?.files ?? readFileMap(provenance),
    freshness,
    freshnessReason,
    integrity,
    integrityReason,
  };
}

/** Every symbol this module exports, so that a reader sees the whole surface of the summary at once. */
export const __all__ = [
  "SnapshotFreshness",
  "ProvenanceSummary",
  "ProvenanceInput",
  "modeLabel",
  "captureLabel",
  "formatDigest",
  "snapshotFreshness",
  "summarizeProvenance",
] as const;
