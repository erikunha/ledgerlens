/**
 * The test of the copy of the published artifacts into the tree of the frontend.
 *
 * Why this test exists: the site of the demo serves the artifacts the repository publishes, and the
 * only way it can do that is if the copy is right. The copy has three duties: it writes the files
 * of the source, it fails loudly when the source is not there, and it takes away the files of the
 * destination that the source does not have. A build that serves a stale scenario is worse than a
 * build that fails, so the failure is part of the promise and is tested here.
 *
 * Why the test works in a temporary folder: the artifacts the repository publishes must never be
 * touched by a test, so the test builds a source and a destination of its own under the temporary
 * folder of the operating system and runs the copy on them.
 */

import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

/**
 * Finds the script under test: the copy the build of the frontend runs.
 *
 * Why the search goes up from the working folder: the test does not care where it is run from, and
 * the script always lives in the `scripts` folder of the package of the frontend.
 */
function findScript(): string {
  let current = process.cwd();
  for (;;) {
    const candidate = join(current, "scripts", "sync-replay-artifacts.mjs");
    if (existsSync(candidate)) {
      return candidate;
    }
    const parent = dirname(current);
    if (parent === current) {
      throw new Error("the script of the copy was not found above the working folder");
    }
    current = parent;
  }
}

/** The script under test: the copy the build of the frontend runs. */
const SCRIPT = findScript();

/**
 * Finds the manifest of the package of the frontend.
 *
 * Why the search goes up from the working folder: the test does not care where it is run from, and the manifest
 * always lives beside the `scripts` folder of the package.
 */
function findManifest(): string {
  let current = process.cwd();
  for (;;) {
    const candidate = join(current, "package.json");
    if (existsSync(candidate)) {
      return candidate;
    }
    const parent = dirname(current);
    if (parent === current) {
      throw new Error("the manifest of the package was not found above the working folder");
    }
    current = parent;
  }
}

/** The manifest of the package of the frontend. */
const MANIFEST = findManifest();

/** The folders the test created, so that every case can clean up after itself. */
const temporaryFolders: string[] = [];

/**
 * Creates a folder for one case of the test.
 *
 * Why a folder of its own for every case: the cases must not see the files of each other, and the
 * artifacts of the repository must never be written to.
 */
function temporaryFolder(): string {
  const folder = mkdtempSync(join(tmpdir(), "ledgerlens-replay-"));
  temporaryFolders.push(folder);
  return folder;
}

/**
 * Writes a file of the test, creating the folders above it.
 *
 * Why the helper writes bytes and not text: the promise of the copy is byte for byte, so the test
 * compares bytes.
 */
function writeFileOfTest(root: string, relativePath: string, content: string): void {
  const target = join(root, relativePath);
  mkdirSync(join(target, ".."), { recursive: true });
  writeFileSync(target, content);
}

/**
 * Runs the copy and says what it answered.
 *
 * Why the status and the two streams come back together: the copy has to fail loudly, and a
 * failure that says nothing is not a loud failure.
 */
function runCopy(args: string[]): { status: number; stdout: string; stderr: string } {
  const result = spawnSync(process.execPath, [SCRIPT, ...args], { encoding: "utf8" });
  return {
    status: result.status ?? -1,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
  };
}

afterEach(() => {
  while (temporaryFolders.length > 0) {
    const folder = temporaryFolders.pop();
    if (folder) {
      rmSync(folder, { recursive: true, force: true });
    }
  }
});

describe("the copy of the published artifacts", () => {
  it("writes the files of the source into the destination", () => {
    const root = temporaryFolder();
    const source = join(root, "site", "replay");
    const destination = join(root, "apps", "web", "public", "replay");
    writeFileOfTest(source, "index.json", '[{"id":"S01"}]');
    writeFileOfTest(source, "s01/manifest.json", '{"bundle_schema_version":"1"}');

    const result = runCopy(["--source", source, "--destination", destination]);

    expect(result.status).toBe(0);
    expect(readFileSync(join(destination, "index.json"), "utf8")).toBe('[{"id":"S01"}]');
    expect(readFileSync(join(destination, "s01", "manifest.json"), "utf8")).toBe(
      '{"bundle_schema_version":"1"}',
    );
    expect(result.stdout).toContain("index.json");
    expect(result.stdout).toContain("s01/manifest.json");
  });

  it("fails loudly when the source is not there", () => {
    const root = temporaryFolder();
    const source = join(root, "site", "replay");
    const destination = join(root, "apps", "web", "public", "replay");

    const result = runCopy(["--source", source, "--destination", destination]);

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(source);
    expect(existsSync(destination)).toBe(false);
  });

  it("fails loudly when the source holds no file", () => {
    const root = temporaryFolder();
    const source = join(root, "site", "replay");
    const destination = join(root, "apps", "web", "public", "replay");
    mkdirSync(source, { recursive: true });

    const result = runCopy(["--source", source, "--destination", destination]);

    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain(source);
  });

  it("takes away the file of the destination that the source does not have", () => {
    const root = temporaryFolder();
    const source = join(root, "site", "replay");
    const destination = join(root, "apps", "web", "public", "replay");
    writeFileOfTest(source, "index.json", "[]");
    writeFileOfTest(destination, "s99/events.jsonl", "{}\n");
    writeFileOfTest(destination, "s99/manifest.json", "{}");

    const result = runCopy(["--source", source, "--destination", destination]);

    expect(result.status).toBe(0);
    expect(existsSync(join(destination, "s99", "events.jsonl"))).toBe(false);
    expect(existsSync(join(destination, "s99", "manifest.json"))).toBe(false);
    expect(existsSync(join(destination, "index.json"))).toBe(true);
  });

  it("runs the copy before the unit tests of the package", () => {
    // It proves the order of the steps: the unit tests read the catalog that the site serves, so the copy has to be
    // made before they run. Without this hook the continuous integration runs the tests on a checkout that has no
    // copy at all, the route of a scenario finds no scenario, and the suite fails with a page of 404 that has nothing
    // to do with the 404.
    const manifest = JSON.parse(readFileSync(MANIFEST, "utf8")) as {
      scripts?: Record<string, string>;
    };

    expect(manifest.scripts?.["pretest"]).toBe("node scripts/sync-replay-artifacts.mjs");
    expect(manifest.scripts?.["prebuild"]).toBe("node scripts/sync-replay-artifacts.mjs");
  });

  it("copies the two catalogs of the site when the caller names no source and no destination", () => {
    // It proves that the copy of the build takes the recordings of the scripted model AND the recordings of a real
    // model, each one into the folder of its own catalog: the site publishes two catalogs and each one has to be in
    // the export, or the page of that catalog is a page of nothing (ADR-075).
    const result = runCopy([]);

    expect(result.status).toBe(0);
    expect(result.stdout).toContain(join("site", "replay"));
    expect(result.stdout).toContain(join("public", "replay"));
    expect(result.stdout).toContain(join("site", "replay-real"));
    expect(result.stdout).toContain(join("public", "replay-real"));
  });
});
