/**
 * The test of the helper of the provenance of a bundle.
 *
 * Why this test exists: the provenance panel shows where the recording came from, and every word of that panel has to
 * come from the artifact. The browser never invents a digest, never shows a hash it did not read and never calls a
 * bundle fresh or stale on a comparison it did not make. The site publishes only the deterministic sandbox, so the
 * label of the mode of a published bundle never says live.
 *
 * Every case runs with no key and no network: the helper is a pure function of the values it is given, and the values
 * of the test are the ones of the published bundle of the repository.
 */

import { describe, expect, it } from "vitest";

import type { ReplayBundleManifest } from "@/lib/api/schemas";
import {
  captureLabel,
  formatDigest,
  modeLabel,
  snapshotFreshness,
  summarizeProvenance,
} from "@/lib/replay/provenance";

/** The manifest of the published bundle of the scenario S01, as `site/replay/s01/manifest.json` holds it. */
const MANIFEST: ReplayBundleManifest = {
  bundle_schema_version: "1",
  capture_kind: "scripted_fixture",
  code_sha: "9dc3af946b223496c7ed2e897b1e4152bbf9234f",
  created_at: "2026-11-14T11:00:14+00:00",
  events: 57,
  files: { "events.jsonl": "577939e532327f3af1a3897612f622d96edc27a620646437fb02c5fa5318de13" },
  mode: "deterministic_sandbox",
  model_profile: "scripted-fixture",
  note: "Deterministic execution of the scenario S01, account C-0412, with the scripted model and the recorded exchange rate. This is not a live execution and it calls no model.",
  policy_version: "policies-v1",
  recorded_at: "2026-11-14T11:00:14+00:00",
  run_id: "replay-s01",
  scenario: "S01",
  snapshot_sha256: "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
};

/** The provenance file of the published bundle, as `site/replay/s01/provenance.json` holds it. */
const PROVENANCE = {
  artifacts: {
    "events.jsonl": "577939e532327f3af1a3897612f622d96edc27a620646437fb02c5fa5318de13",
    "manifest.json": "bbbe1e54fcae712df66a3a6096838ab5b7f8c938e2e47b7ef6681e43cafa84ac",
  },
  bundle_digest: "bbbe1e54fcae712df66a3a6096838ab5b7f8c938e2e47b7ef6681e43cafa84ac",
  capture_kind: "scripted_fixture",
  code_sha: "9dc3af946b223496c7ed2e897b1e4152bbf9234f",
  created_at: "2026-11-14T11:00:14+00:00",
  dataset_sha256: "cab6cd1eeefd08ae58b138501c2c69431547fcbb7434f1a47720cc81aefe84ba",
  files: { "events.jsonl": "577939e532327f3af1a3897612f622d96edc27a620646437fb02c5fa5318de13" },
  mode: "deterministic_sandbox",
  model_profile: "scripted-fixture",
  note: "Deterministic execution of the scenario S01, account C-0412, with the scripted model and the recorded exchange rate. This is not a live execution and it calls no model.",
  policy_version: "policies-v1",
  recorded_at: "2026-11-14T11:00:14+00:00",
  snapshot_sha256: "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
};

describe("the helper of the provenance", () => {
  it("names the mode of a published bundle as a recorded replay", () => {
    // It proves that the site never presents a recorded run as a live one.
    expect(modeLabel("deterministic_sandbox")).toBe("Recorded Replay");
    expect(modeLabel("recorded_replay")).toBe("Recorded Replay");
  });

  it("names the mode of a live run as a live agent", () => {
    // It proves that the mapping knows the three modes of the contract, so that the route can refuse a live bundle.
    expect(modeLabel("live_agent")).toBe("Live agent");
  });

  it("names the kind of the capture of the recording", () => {
    // It proves that a bundle captured from a scripted fixture is never presented as a run of a real model.
    expect(captureLabel("scripted_fixture")).toBe("Scripted fixture");
    expect(captureLabel("real_model_recorded")).toBe("Real model recorded");
  });

  it("shortens the digest with the first and the last four characters", () => {
    // It proves that the digest on the screen is the one the artifact published and not a digest of its own. The
    // digest ends with "a84ac", so its last four characters are "84ac".
    expect(formatDigest("bbbe1e54fcae712df66a3a6096838ab5b7f8c938e2e47b7ef6681e43cafa84ac")).toBe("bbbe...84ac");
  });

  it("says that the digest is not available when the artifact carries none", () => {
    // It proves that the panel never shows a digest the browser did not read.
    expect(formatDigest(null)).toBe("Not available");
  });

  it("shows a digest of eight characters or fewer as it is, without the points", () => {
    // It proves that the helper never cuts a digest that is too short to be shortened.
    expect(formatDigest("abcd1234")).toBe("abcd1234");
    expect(formatDigest("abcd123")).toBe("abcd123");
  });

  it("says that the label is not available when the artifact carries no mode and no kind of capture", () => {
    // It proves that the panel never invents a mode and never invents a kind of capture.
    expect(modeLabel(null)).toBe("Not available");
    expect(captureLabel(null)).toBe("Not available");
  });

  it("calls the snapshot fresh only when a comparable hash was published and matches", () => {
    // It proves that the freshness rests on a comparison that was really made.
    expect(snapshotFreshness("a", "a")).toBe("fresh");
  });

  it("calls the snapshot stale only when a comparable hash was published and differs", () => {
    // It proves that a snapshot that does not match the published hash is called stale and not fresh.
    expect(snapshotFreshness("a", "b")).toBe("stale");
  });

  it("calls the freshness unknown when there is nothing to compare with", () => {
    // It proves that the panel never calls a bundle fresh or stale on a comparison it did not make.
    expect(snapshotFreshness("a", null)).toBe("unknown");
    expect(snapshotFreshness(null, null)).toBe("unknown");
  });

  it("reads the digest of the bundle out of the provenance file", () => {
    // It proves that the digest of the panel is the `bundle_digest` of the artifact and never one of the browser.
    const summary = summarizeProvenance({ manifest: MANIFEST, provenance: PROVENANCE });

    expect(summary.bundleDigest).toBe("bbbe1e54fcae712df66a3a6096838ab5b7f8c938e2e47b7ef6681e43cafa84ac");
    expect(summary.modeLabel).toBe("Recorded Replay");
    expect(summary.captureLabel).toBe("Scripted fixture");
    expect(summary.recordedAt).toBe("2026-11-14T11:00:14+00:00");
    expect(summary.codeSha).toBe("9dc3af946b223496c7ed2e897b1e4152bbf9234f");
    expect(summary.modelProfile).toBe("scripted-fixture");
    expect(summary.policyVersion).toBe("policies-v1");
    expect(summary.files["events.jsonl"]).toBe(
      "577939e532327f3af1a3897612f622d96edc27a620646437fb02c5fa5318de13",
    );
  });

  it("says that the freshness could not be checked when no comparable hash was published", () => {
    // It proves that the panel says out loud that the freshness could not be checked, because the hash of the dataset
    // and the hash of the snapshot are the hash of two different things.
    const summary = summarizeProvenance({ manifest: MANIFEST, provenance: PROVENANCE });

    expect(summary.freshness).toBe("unknown");
    expect(summary.freshnessReason).toMatch(/freshness could not be checked/i);
  });

  it("says why the freshness is what it is, in a sentence for the reader", () => {
    // It proves that the reason of the freshness is written for whoever reads the panel, and not as a code.
    const summary = summarizeProvenance({ manifest: MANIFEST, provenance: PROVENANCE });

    expect(summary.freshnessReason.length).toBeGreaterThan(0);
    expect(summary.freshnessReason).toContain(" ");
    expect(summary.freshnessReason.endsWith(".")).toBe(true);
  });

  it("calls the snapshot stale when the comparable hashes differ", () => {
    // It proves that the freshness rests on the comparison of two hashes of the same thing.
    const summary = summarizeProvenance({
      manifest: MANIFEST,
      provenance: PROVENANCE,
      publishedSnapshotSha256: "1111111111111111111111111111111111111111111111111111111111111111",
    });

    expect(summary.freshness).toBe("stale");
  });

  it("never shows a bundle of the site as a live one", () => {
    // It proves that the summary of a published bundle never carries the label of a live run.
    const summary = summarizeProvenance({ manifest: MANIFEST, provenance: PROVENANCE });

    expect(summary.modeLabel).not.toMatch(/live/i);
  });
});
