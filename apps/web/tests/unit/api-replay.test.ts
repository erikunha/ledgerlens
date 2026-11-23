/**
 * The test of the client of the static artifacts of the recorded demo.
 *
 * Why this test exists: the recorded demo works with no key, no account and no network, and the one place that reads
 * the published files has to read them exactly as the repository publishes them. A catalog that does not pass the
 * contract, a manifest that spells the version in another way and an event that is not a trace event are refused with a
 * reason a reader can act on. And the integrity of the bundle is checked against the digests that the manifest and the
 * provenance file publish, so a bundle whose file was tampered with is refused with the digest it expected and the
 * digest it observed (FR-038).
 *
 * Every case runs with no key and no network: the fetch of the case is a fake that answers with the artifacts the
 * repository publishes, read from the disk of the repository. The digest is computed with the Web Crypto of the
 * runtime, and the function that computes it can be injected, so the test never needs a browser.
 */

import { createHash, webcrypto } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { ARTIFACT_ROOT, loadReplay, loadScenarioCatalog, verifyBundleDigests } from "@/lib/api/replay";
import type { ReplayBundleManifest, ScenarioIndexEntry } from "@/lib/api/schemas";

/**
 * Finds the folder of the published bundle of the scenario S01 on the disk.
 *
 * Why the search goes up from the working folder: the artifacts are published in `site/replay` at the root of the
 * repository and copied into `apps/web/public/replay` by the build, and the test must find them in either place. The
 * artifacts of the repository are the source of truth, so the test serves the real bytes of the real files and never a
 * bundle that the test invented.
 */
function findPublishedBundle(): {
  folder: string;
  manifest: string;
  events: string;
  provenance: string;
  ledger: string;
} {
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
      folder,
      manifest: readFileSync(join(folder, "manifest.json"), "utf8"),
      events: readFileSync(join(folder, "events.jsonl"), "utf8"),
      provenance: readFileSync(join(folder, "provenance.json"), "utf8"),
      ledger: existsSync(join(folder, "ledger.json"))
        ? readFileSync(join(folder, "ledger.json"), "utf8")
        : "",
    };
  }
  throw new Error("the published bundle of the scenario S01 was not found on the disk of the repository");
}

/** Finds the published catalog of the scenarios on the disk. */
function findPublishedCatalog(): string {
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
    ...roots.map((root) => join(root, "public", "replay", "index.json")),
    ...roots.map((root) => join(root, "site", "replay", "index.json")),
  ];

  for (const catalog of candidates) {
    if (existsSync(catalog)) {
      return readFileSync(catalog, "utf8");
    }
  }
  throw new Error("the published catalog of the scenarios was not found on the disk of the repository");
}

/** The published bundle of the scenario S01, read from the disk of the repository. */
const PUBLISHED = findPublishedBundle();

/** The published catalog of the scenarios, read from the disk of the repository. */
const PUBLISHED_CATALOG = findPublishedCatalog();

/** The card of the scenario in the published catalog, as `site/replay/index.json` holds it. */
const PUBLISHED_CARD: ScenarioIndexEntry = {
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

/** The digest of the file of the events, as the manifest of the published bundle declares it. */
const EVENTS_DIGEST = (JSON.parse(PUBLISHED.manifest) as ReplayBundleManifest).files["events.jsonl"] as string;

/**
 * The fetch of the case: it answers with the artifacts the repository publishes.
 *
 * Why the answers are a parameter: the case that proves a refusal needs an artifact that does not pass the contract,
 * and every other answer is the published one. The list of the URLs that were asked for comes back with it, so that
 * the case can prove that the artifacts are read from the origin of the site.
 */
function fakeFetch(answers: {
  catalog?: string;
  manifest?: string;
  events?: string;
  provenance?: string;
  ledger?: string;
  ledgerMissing?: boolean;
}): { impl: typeof fetch; urls: string[] } {
  const urls: string[] = [];
  const impl = (async (input: RequestInfo | URL) => {
    const url = String(input);
    urls.push(url);
    if (answers.ledgerMissing === true && url.endsWith("ledger.json")) {
      return { ok: false, status: 404, text: async () => "" } as unknown as Response;
    }
    const body = url.endsWith("index.json")
      ? (answers.catalog ?? PUBLISHED_CATALOG)
      : url.endsWith("manifest.json")
        ? (answers.manifest ?? PUBLISHED.manifest)
        : url.endsWith("events.jsonl")
          ? (answers.events ?? PUBLISHED.events)
          : url.endsWith("provenance.json")
            ? (answers.provenance ?? PUBLISHED.provenance)
            : url.endsWith("ledger.json")
              ? (answers.ledger ?? PUBLISHED.ledger)
              : "";
    return { ok: true, status: 200, text: async () => body } as unknown as Response;
  }) as unknown as typeof fetch;
  return { impl, urls };
}

/** The sha256 of a text, computed the way the browser computes it. */
function sha256Of(text: string): string {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the client of the static artifacts", () => {
  it("reads the artifacts from the root of the published artifacts of the site", () => {
    // It proves that the recorded demo reads the files of the export and never calls the backend of the demo.
    expect(ARTIFACT_ROOT).toBe("/replay");
  });

  it("reads the published catalog of the scenarios", async () => {
    // It proves that the catalog of the site is read as the list of cards that the repository publishes.
    const { impl, urls } = fakeFetch({});

    const catalog = await loadScenarioCatalog(impl);

    expect(urls).toContain("/replay/index.json");
    if (!Array.isArray(catalog)) {
      throw new Error(`the loader refused the published catalog: ${catalog.error}`);
    }
    expect(catalog).toHaveLength(5);
    expect(catalog.map((card) => card.id)).toEqual(["S01", "S02", "S03", "S04", "S08"]);
    expect(catalog[0]?.question).toBe("Why was the BRL refund for TX-2048 lower than the EUR payment?");
  });

  it("refuses a catalog that does not pass the contract", async () => {
    // It proves that a catalog the contract does not accept is refused with a reason and not shown as a half read list.
    const { impl } = fakeFetch({ catalog: JSON.stringify({ scenarios: [PUBLISHED_CARD], schema_version: "1" }) });

    const catalog = await loadScenarioCatalog(impl);

    expect("error" in catalog).toBe(true);
    if ("error" in catalog) {
      expect(catalog.error.length).toBeGreaterThan(0);
    }
  });

  it("reads the manifest, the events and the provenance of the published bundle", async () => {
    // It proves that the bundle of the scenario is read from the folder that the catalog published, and that the real
    // artifact passes the integrity check against the digests that the manifest and the provenance publish.
    const { impl, urls } = fakeFetch({});

    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect(urls).toContain("/replay/s01/manifest.json");
    expect(urls).toContain("/replay/s01/events.jsonl");
    expect(urls).toContain("/replay/s01/provenance.json");
    if ("error" in loaded) {
      throw new Error(`the loader refused the published bundle: ${loaded.error}`);
    }
    expect(loaded.manifest.mode).toBe("deterministic_sandbox");
    expect(loaded.manifest.bundle_schema_version).toBe("1");
    expect(loaded.events.length).toBeGreaterThan(0);
    // The digest of the bundle is the digest of the manifest that the bundle publishes, and the case computes it
    // from the bytes of the file on the disk: a case that repeats the digest of the recording breaks every time
    // the scenario is recorded again, and the check it wants is the one between the two published files.
    expect(loaded.provenance?.["bundle_digest"]).toBe(
      createHash("sha256").update(PUBLISHED.manifest).digest("hex"),
    );
  });

  it("refuses a manifest that spells the version of the contract in another way", async () => {
    // It proves that a recording the interface does not understand is not a recording.
    const otherSpelling: Record<string, unknown> = { ...JSON.parse(PUBLISHED.manifest), schema_version: "1" };
    delete otherSpelling["bundle_schema_version"];
    const { impl } = fakeFetch({ manifest: JSON.stringify(otherSpelling) });

    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect("error" in loaded).toBe(true);
    if ("error" in loaded) {
      expect(loaded.error).toContain("bundle_schema_version");
    }
  });

  it("refuses an event that is not a trace event", async () => {
    // It proves that an event whose sequence number is below one is refused before anything is rendered.
    const broken = PUBLISHED.events.replace('"seq": 1,', '"seq": 0,');
    expect(broken).not.toBe(PUBLISHED.events);
    const { impl } = fakeFetch({ events: broken });

    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect("error" in loaded).toBe(true);
    if ("error" in loaded) {
      expect(loaded.error).toContain("did not pass the contract");
    }
  });

  it("refuses a bundle that declares a live run", async () => {
    // It proves that this site publishes only the deterministic sandbox: a bundle whose manifest declares the mode
    // `live_agent` is refused with the reason that names the mode, and the label of a live run never reaches a
    // visitor of the replay (ADR-043).
    //
    // Why the provenance of the case is written for the manifest of the case: the refusal has to come from the mode
    // and from nothing else, so the digests of the case have to agree with the files the case publishes.
    const liveManifest: Record<string, unknown> = { ...JSON.parse(PUBLISHED.manifest), mode: "live_agent" };
    const liveManifestText = JSON.stringify(liveManifest);
    const liveDigest = sha256Of(liveManifestText);
    const publishedProvenance = JSON.parse(PUBLISHED.provenance) as Record<string, unknown>;
    const liveProvenance = {
      ...publishedProvenance,
      bundle_digest: liveDigest,
      artifacts: {
        ...(publishedProvenance["artifacts"] as Record<string, string>),
        "manifest.json": liveDigest,
      },
    };
    const { impl } = fakeFetch({ manifest: liveManifestText, provenance: JSON.stringify(liveProvenance) });

    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect("error" in loaded).toBe(true);
    if (!("error" in loaded)) {
      throw new Error("the loader accepted a bundle that declares a live run");
    }
    expect(loaded.error).toContain("live_agent");
    expect(loaded.error).toContain("deterministic sandbox");
  });

  it("never throws at the caller when the site does not answer", async () => {
    // It proves that the loader always hands back a bundle or a reason, so that the caller never has to catch.
    const impl = (async () => {
      throw new TypeError("failed to fetch");
    }) as unknown as typeof fetch;

    const catalog = await loadScenarioCatalog(impl);

    expect("error" in catalog).toBe(true);
  });

  it("never throws at the caller when the site does not answer the bundle", async () => {
    // It proves the same rule for the bundle and not only for the catalog: the loader of the bundle hands back the
    // reason it refused it, and it never throws at the caller. A loader that threw would leave the reader with an
    // exception instead of a sentence a visitor can act on (ADR-043).
    const impl = (async () => {
      throw new TypeError("failed to fetch");
    }) as unknown as typeof fetch;

    // the case awaits the loader, so a loader that throws fails the case right here
    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect("error" in loaded).toBe(true);
    if (!("error" in loaded)) {
      throw new Error("the loader accepted a bundle it never read");
    }
    expect(loaded.error).toContain("did not answer");
    expect(loaded.error).toContain(PUBLISHED_CARD.id);
  });

  it("refuses a bundle whose digest does not match, with the digest it expected and the one it observed", async () => {
    // It proves that the integrity check names both digests, so that a reader can act on the refusal, and that a file
    // that was tampered with never reaches the interface (FR-038).
    vi.stubGlobal("crypto", webcrypto);
    const tampered = PUBLISHED.events.replace('"566.79"', '"566.98"');
    expect(tampered).not.toBe(PUBLISHED.events);
    const observed = sha256Of(tampered);
    expect(observed).not.toBe(EVENTS_DIGEST);
    const { impl } = fakeFetch({ events: tampered });

    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect("error" in loaded).toBe(true);
    if (!("error" in loaded)) {
      throw new Error("the loader accepted a bundle whose digest does not match");
    }
    expect(loaded.error).toContain(EVENTS_DIGEST);
    expect(loaded.error).toContain(observed);
  });

  it("accepts a bundle whose digest matches", async () => {
    // It proves that the integrity check passes the bundle that the repository published.
    const sha256 = vi.fn(async () => EVENTS_DIGEST);

    const result = await verifyBundleDigests({
      manifest: JSON.parse(PUBLISHED.manifest) as ReplayBundleManifest,
      eventsBytes: new TextEncoder().encode(PUBLISHED.events).buffer as ArrayBuffer,
      provenance: JSON.parse(PUBLISHED.provenance) as Record<string, unknown>,
      sha256,
    });

    expect(result.ok).toBe(true);
    expect(sha256).toHaveBeenCalled();
  });

  it("refuses a bundle whose digest does not match when the digest function is injected", async () => {
    // It proves that the check rests on the digest function that the caller injects, and not on a browser.
    const observed = "b".repeat(64);
    const sha256 = vi.fn(async () => observed);

    const result = await verifyBundleDigests({
      manifest: JSON.parse(PUBLISHED.manifest) as ReplayBundleManifest,
      eventsBytes: new TextEncoder().encode(PUBLISHED.events).buffer as ArrayBuffer,
      provenance: JSON.parse(PUBLISHED.provenance) as Record<string, unknown>,
      sha256,
    });

    expect(result.ok).toBe(false);
    if (result.ok) {
      throw new Error("the integrity check accepted a bundle whose digest does not match");
    }
    expect(result.reasons.join(" ")).toContain(EVENTS_DIGEST);
    expect(result.reasons.join(" ")).toContain(observed);
  });

  it("does not refuse a bundle when the Web Crypto is absent", async () => {
    // It proves that the absence of the Web Crypto is not a refusal: the check is then unknown, the loader does not
    // refuse because of it and the panel says that the integrity was not checked.
    vi.stubGlobal("crypto", undefined);

    const result = await verifyBundleDigests({
      manifest: JSON.parse(PUBLISHED.manifest) as ReplayBundleManifest,
      eventsBytes: new TextEncoder().encode(PUBLISHED.events).buffer as ArrayBuffer,
      provenance: JSON.parse(PUBLISHED.provenance) as Record<string, unknown>,
    });

    expect(result.ok).toBe(true);

    const { impl } = fakeFetch({});
    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect("error" in loaded).toBe(false);
  });

  it("reads the file of the ledger beside the bundle", async () => {
    // It proves that the artifact of the ledger is read from the folder of the bundle, next to the manifest, the
    // events and the provenance, and that the ONE place that reads the published artifacts is the one that reads it.
    vi.stubGlobal("crypto", webcrypto);
    const { impl, urls } = fakeFetch({});

    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect(urls).toContain("/replay/s01/ledger.json");
    if ("error" in loaded) {
      throw new Error(`the loader refused the published bundle: ${loaded.error}`);
    }
    expect(loaded.ledger).not.toBeNull();
    expect(loaded.ledger?.accounts).toHaveLength(1);
    expect(loaded.ledger?.accounts[0]?.id).toBe("C-0412");
    expect(loaded.ledger?.accounts[0]?.rows).toHaveLength(2);
    expect(loaded.ledgerError).toBeNull();
    expect(loaded.ledgerIntegrity).toBe("checked");
  });

  it("does not refuse a bundle that publishes no file of the ledger", async () => {
    // It proves that the file of the ledger is a SIDECAR: a bundle without it is still a bundle, and the recording is
    // still a recording. The state carries the reason, so that the interface says in words what the site did not
    // publish, instead of showing nothing and saying nothing (ADR-045).
    vi.stubGlobal("crypto", webcrypto);
    const { impl } = fakeFetch({ ledgerMissing: true });

    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect("error" in loaded).toBe(false);
    if ("error" in loaded) {
      throw new Error(`the loader refused a bundle without a file of the ledger: ${loaded.error}`);
    }
    expect(loaded.ledger).toBeNull();
    expect(loaded.ledgerError).toContain("no ledger");
  });

  it("does not refuse a bundle whose file of the ledger is not a JSON document", async () => {
    // It proves that a broken sidecar does not make the recording unreadable, and that the reason says what happened.
    vi.stubGlobal("crypto", webcrypto);
    const { impl } = fakeFetch({ ledger: "{ this is not a document" });

    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect("error" in loaded).toBe(false);
    if ("error" in loaded) {
      throw new Error(`the loader refused a bundle with a broken sidecar: ${loaded.error}`);
    }
    expect(loaded.ledger).toBeNull();
    expect(loaded.ledgerError).toContain("not a JSON document");
  });

  it("does not show a file of the ledger whose digest does not match the digest that was published", async () => {
    // It proves that the file of the ledger is checked against the digest that the provenance publishes, and that a
    // file that was tampered with is hidden with the reason. The BUNDLE is not refused: the ledger is a sidecar and a
    // recording stays a recording.
    vi.stubGlobal("crypto", webcrypto);
    const tampered = PUBLISHED.ledger.replace('"100.00"', '"100.01"');
    expect(tampered).not.toBe(PUBLISHED.ledger);
    const { impl } = fakeFetch({ ledger: tampered });

    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect("error" in loaded).toBe(false);
    if ("error" in loaded) {
      throw new Error(`the loader refused a bundle because of its sidecar: ${loaded.error}`);
    }
    expect(loaded.ledger).toBeNull();
    expect(loaded.ledgerError).toContain("ledger.json");
    expect(loaded.ledgerError).toContain(sha256Of(tampered));
  });

  it("says out loud that the integrity of the file of the ledger was not checked without the Web Crypto", async () => {
    // It proves that the absence of the Web Crypto is not a refusal and not a silent pass: the integrity of the file
    // of the ledger is then unknown, and the interface never shows an artifact as verified when it was not.
    vi.stubGlobal("crypto", undefined);
    const { impl } = fakeFetch({});

    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect("error" in loaded).toBe(false);
    if ("error" in loaded) {
      throw new Error(`the loader refused the published bundle: ${loaded.error}`);
    }
    expect(loaded.ledger).not.toBeNull();
    expect(loaded.ledgerIntegrity).toBe("unknown");
  });

  it("never says that the integrity of the file of the ledger was checked when nothing was compared", async () => {
    // It proves that the field says the truth: a site that published no digest of the file of the ledger published
    // nothing to compare, and a field that says "checked" when no digest was compared is a field that lies about the
    // only thing it exists to say.
    vi.stubGlobal("crypto", webcrypto);
    const publishedProvenance = JSON.parse(PUBLISHED.provenance) as Record<string, unknown>;
    const artifacts = { ...(publishedProvenance["artifacts"] as Record<string, string>) };
    delete artifacts["ledger.json"];
    const { impl } = fakeFetch({ provenance: JSON.stringify({ ...publishedProvenance, artifacts }) });

    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect("error" in loaded).toBe(false);
    if ("error" in loaded) {
      throw new Error(`the loader refused the published bundle: ${loaded.error}`);
    }
    expect(loaded.ledger).not.toBeNull();
    expect(loaded.ledgerIntegrity).toBe("unknown");
  });

  it("says that the integrity of the file of the ledger was checked only when a digest was compared", async () => {
    // It proves the other side of the same truth: a file whose digest was compared with the digest that the
    // provenance published is a file whose integrity really was checked.
    vi.stubGlobal("crypto", webcrypto);
    const { impl } = fakeFetch({});

    const loaded = await loadReplay(PUBLISHED_CARD, impl);

    expect("error" in loaded).toBe(false);
    if ("error" in loaded) {
      throw new Error(`the loader refused the published bundle: ${loaded.error}`);
    }
    expect(loaded.ledgerIntegrity).toBe("checked");
  });
});
