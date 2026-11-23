/**
 * The test of the nodes of the tour of the architecture.
 *
 * Why this test exists: the tour of the architecture shows six subsystems and links each one to
 * the module it is written in and to the record that explains why it exists. A node that points at
 * a file that does not exist is a lie the site tells to a visitor who follows the link, and a
 * record whose title drifts from the title of its file is a link that opens a document that does
 * not say what the node promised (ADR-046).
 *
 * Why the test reads the disk and not a snapshot: the repository is the truth, and a test that
 * compares the nodes with a copy of the nodes proves nothing. The paths have to exist in the tree
 * and the titles have to be the titles of the files of the tree.
 *
 * Every case runs with no key and no network: the nodes are data of the repository and nothing else.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { ARCHITECTURE_NODES, type ArchitectureNode } from "@/features/architecture/nodes";

/**
 * The root of the repository.
 *
 * Why the root is found by walking up: the test lives in `apps/web/tests/unit/features/`, and a
 * path written by hand breaks the day the test moves. The walk stops at the folder that holds the
 * records of the decisions, which is the mark of the root.
 */
function repositoryRoot(): string {
  let current = dirname(fileURLToPath(import.meta.url));
  for (;;) {
    if (existsSync(join(current, "docs", "decisions"))) {
      return current;
    }
    const parent = dirname(current);
    if (parent === current) {
      throw new Error("the root of the repository was not found from the folder of this test");
    }
    current = parent;
  }
}

/** The root of the repository, once. */
const ROOT = repositoryRoot();

/**
 * The title of the heading of a file of the repository.
 *
 * Why the heading and not the whole file: a record of a decision begins with its number and its
 * title, and the node of the tour quotes that title word for word.
 */
function titleOfHeading(file: string): string {
  const content = readFileSync(file, { encoding: "utf8" });
  const heading = content.match(/^#\s+(.+)$/m);
  const title = heading?.[1];
  if (title === undefined) {
    throw new Error(`the file ${file} has no heading of the first level`);
  }
  return title.trim();
}

/**
 * The identifier of the node of the tour that has a given label.
 *
 * Why the lookup is by label: the label is what the visitor reads, and a node whose label changed
 * is a node whose link the visitor cannot find.
 */
function nodeWithLabel(label: string): ArchitectureNode {
  const node = ARCHITECTURE_NODES.find((candidate) => candidate.label === label);
  if (node === undefined) {
    throw new Error(`the tour has no node with the label ${label}`);
  }
  return node;
}

describe("the nodes of the tour of the architecture", () => {
  it("carries the six subsystems that the user story names", () => {
    expect(ARCHITECTURE_NODES.map((node) => node.label)).toEqual([
      "Query guard",
      "Scoped ledger copy",
      "Decimal calculator",
      "Deterministic simulator",
      "Verifier",
      "Trace recorder",
    ]);
  });

  it("keeps the order of the run, so that nobody reorders the nodes by accident", () => {
    expect(ARCHITECTURE_NODES.map((node) => node.id)).toEqual([
      "query-guard",
      "scoped-ledger-copy",
      "decimal-calculator",
      "deterministic-simulator",
      "verifier",
      "trace-recorder",
    ]);
  });

  it("gives every node an identifier that is not repeated", () => {
    const identifiers = ARCHITECTURE_NODES.map((node) => node.id);

    expect(new Set(identifiers).size).toBe(identifiers.length);
  });

  it("points every node at a module that exists in the repository", () => {
    for (const node of ARCHITECTURE_NODES) {
      const file = resolve(ROOT, node.module);

      expect(existsSync(file), `the module ${node.module} of the node ${node.label} does not exist`).toBe(
        true,
      );
    }
  });

  it("gives every node at least one record", () => {
    for (const node of ARCHITECTURE_NODES) {
      expect(node.records.length, `the node ${node.label} has no record`).toBeGreaterThan(0);
    }
  });

  it("points every record at a file that exists in the repository", () => {
    for (const node of ARCHITECTURE_NODES) {
      for (const record of node.records) {
        const file = resolve(ROOT, record.path);

        expect(
          existsSync(file),
          `the record ${record.number} of the node ${node.label} does not exist in ${record.path}`,
        ).toBe(true);
      }
    }
  });

  it("names every record with the number that begins the path of its file", () => {
    for (const node of ARCHITECTURE_NODES) {
      for (const record of node.records) {
        expect(record.path.startsWith(`docs/decisions/${record.number}-`)).toBe(true);
      }
    }
  });

  it("quotes the title of every record word for word as its file carries it", () => {
    for (const node of ARCHITECTURE_NODES) {
      for (const record of node.records) {
        const title = titleOfHeading(resolve(ROOT, record.path));

        expect(title).toBe(`ADR-${record.number.slice(4)}: ${record.title}`);
      }
    }
  });

  it("gives every node a summary of one plain sentence", () => {
    for (const node of ARCHITECTURE_NODES) {
      expect(node.summary.length).toBeGreaterThan(0);
      expect(node.summary.endsWith(".")).toBe(true);
    }
  });

  it("links the node of the guard to the record that describes the allowlist", () => {
    const guard = nodeWithLabel("Query guard");

    expect(guard.module).toBe("ledgerlens/tools/sql_guard.py");
    expect(guard.records.map((record) => record.number)).toContain("ADR-005");
  });

  it("links the node of the calculator and the node of the verifier to the record of the verification", () => {
    const calculator = nodeWithLabel("Decimal calculator");
    const verifier = nodeWithLabel("Verifier");

    expect(calculator.records.map((record) => record.number)).toContain("ADR-007");
    expect(verifier.records.map((record) => record.number)).toContain("ADR-007");
  });

  it("links the node of the trace to the record of the public trace", () => {
    const recorder = nodeWithLabel("Trace recorder");

    expect(recorder.records.map((record) => record.number)).toContain("ADR-013");
  });

  it("never writes a module as a URL, because the commit belongs to the build", () => {
    for (const node of ARCHITECTURE_NODES) {
      expect(node.module.startsWith("http")).toBe(false);
      expect(node.module.startsWith("/")).toBe(false);
    }
  });
});
