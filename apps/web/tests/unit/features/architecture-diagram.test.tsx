/**
 * The test of the picture of the architecture and of the accessible list that is its twin.
 *
 * Why this test exists: ADR-046 promises that the picture and the list carry the same six
 * subsystems in the same order, that every node of the picture links to its module and to at least
 * one record, that the picture never animates, that the list is always in the page and that the
 * outline of the headings never skips a level. A promise that no test proves is a promise that
 * breaks without anybody noticing.
 *
 * Why the picture is tested and not only the page: the picture is the part that a visitor with a
 * keyboard and a visitor with a screen reader meet first, and a picture that is wrong is wrong on
 * every page that shows it.
 *
 * Every case runs with no key and no network: the picture and the list are components of the
 * interface and nothing else.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ArchitectureDiagram, ArchitectureNodeList } from "@/features/architecture/ArchitectureDiagram";
import { ArchitectureNodeCard } from "@/features/architecture/ArchitectureNodeCard";
import { ARCHITECTURE_NODES, type ArchitectureNode } from "@/features/architecture/nodes";
import { recordUrlOf, sourceUrlOf } from "@/lib/repository";

/** A commit of forty characters, the shape that the library of the repository accepts. */
const COMMIT = "0123456789abcdef0123456789abcdef01234567";

/**
 * The node of the array at a position.
 *
 * Why the helper fails loudly: a test that found no node would carry an empty expectation and
 * would pass for the wrong reason.
 */
function nodeAt(index: number): ArchitectureNode {
  const node = ARCHITECTURE_NODES[index];
  if (node === undefined) {
    throw new Error(`the node ${index} is not in the array of the nodes`);
  }
  return node;
}

/** The picture of the architecture inside a rendered page.
 *
 * Why the helper fails loudly: a test that finds no picture would carry an empty list of labels
 * and would pass for the wrong reason.
 */
function pictureOf(container: HTMLElement): Element {
  const picture = container.querySelector("svg[data-architecture-picture]");
  if (picture === null) {
    throw new Error("the picture of the architecture is not in the page");
  }
  return picture;
}

/** The labels the picture draws, in the order it draws them. */
function pictureLabels(picture: Element): readonly (string | null)[] {
  return Array.from(picture.querySelectorAll('a[data-architecture-link="module"]')).map(
    (anchor) => anchor.textContent,
  );
}

/** The headings of the list, in the order the list shows them. */
function listHeadings(container: HTMLElement): readonly (string | null)[] {
  return Array.from(container.querySelectorAll("h3")).map((heading) => heading.textContent);
}

describe("the picture of the architecture", () => {
  it("carries the same six labels as the list, in the same order", () => {
    const { container } = render(<ArchitectureDiagram commit={COMMIT} />);

    const labels = ARCHITECTURE_NODES.map((node) => node.label);

    expect(labels).toHaveLength(6);
    expect(pictureLabels(pictureOf(container))).toEqual(labels);
    expect(listHeadings(container)).toEqual(labels);
  });

  it("draws two anchors for every node, one for the module and one for the record", () => {
    const { container } = render(<ArchitectureDiagram commit={COMMIT} />);

    const picture = pictureOf(container);

    expect(picture.querySelectorAll("a")).toHaveLength(ARCHITECTURE_NODES.length * 2);

    for (const node of ARCHITECTURE_NODES) {
      const group = picture.querySelector(`g[data-architecture-node="${node.id}"]`);
      const moduleLink = group?.querySelector('a[data-architecture-link="module"]');
      const recordLink = group?.querySelector('a[data-architecture-link="record"]');
      const record = node.records[0];

      expect(moduleLink?.getAttribute("href")).toBe(sourceUrlOf(node.module, COMMIT));
      expect(recordLink?.getAttribute("href")).toBe(
        record === undefined ? null : recordUrlOf(record.path, COMMIT),
      );
    }
  });

  it("never animates, so the preference for reduced motion has nothing to switch off", () => {
    const { container } = render(<ArchitectureDiagram commit={COMMIT} />);

    const picture = pictureOf(container);

    expect(picture.querySelector("animate")).toBeNull();
    expect(picture.querySelector("animateTransform")).toBeNull();
    expect(picture.querySelector("set")).toBeNull();

    for (const element of Array.from(picture.querySelectorAll("*"))) {
      expect(element.getAttribute("class") ?? "").not.toMatch(/transition|animate/i);
      expect(element.getAttribute("style") ?? "").not.toMatch(/transition|animate/i);
    }
  });

  it("shows the name of the node as visible text and not only as a label of the anchor", () => {
    const { container } = render(<ArchitectureDiagram commit={COMMIT} />);

    const picture = pictureOf(container);

    for (const node of ARCHITECTURE_NODES) {
      const moduleLink = picture.querySelector(
        `g[data-architecture-node="${node.id}"] a[data-architecture-link="module"]`,
      );

      expect(moduleLink?.textContent).toBe(node.label);
      expect(moduleLink?.getAttribute("aria-label")).toBeNull();
    }
  });

  it("names the anchor of every node with the visible name of the subsystem", () => {
    render(<ArchitectureDiagram commit={COMMIT} />);

    for (const node of ARCHITECTURE_NODES) {
      const links = screen.getAllByRole("link", { name: node.label });

      expect(links).toHaveLength(1);
    }
  });

  it("carries the sentence of the node in the title of its anchor", () => {
    const { container } = render(<ArchitectureDiagram commit={COMMIT} />);

    const picture = pictureOf(container);

    for (const node of ARCHITECTURE_NODES) {
      const moduleLink = picture.querySelector(
        `g[data-architecture-node="${node.id}"] a[data-architecture-link="module"]`,
      );

      expect(moduleLink?.getAttribute("title")).toBe(node.summary);
    }
  });

  it("tells the chosen node apart by a mark that is not a colour", () => {
    const chosen = nodeAt(2);
    const { container } = render(<ArchitectureDiagram commit={COMMIT} selectedNodeId={chosen.id} />);

    const picture = pictureOf(container);
    const group = picture.querySelector(`g[data-architecture-node="${chosen.id}"]`);
    const moduleLink = group?.querySelector('a[data-architecture-link="module"]');
    const otherGroup = picture.querySelector(`g[data-architecture-node="${nodeAt(0).id}"]`);

    expect(moduleLink?.getAttribute("aria-current")).toBe("true");
    expect(
      otherGroup?.querySelector('a[data-architecture-link="module"]')?.getAttribute("aria-current"),
    ).toBeNull();
    expect(picture.textContent).toContain("The chosen node");

    const chosenBorder = Number(group?.querySelector("rect")?.getAttribute("stroke-width"));
    const otherBorder = Number(otherGroup?.querySelector("rect")?.getAttribute("stroke-width"));

    expect(chosenBorder).toBeGreaterThan(otherBorder);
  });

  it("never forces a scroll sideways, because the width of the picture is a percentage", () => {
    const { container } = render(<ArchitectureDiagram commit={COMMIT} />);

    const picture = pictureOf(container);

    expect(picture.getAttribute("width")).toBe("100%");
    expect(picture.getAttribute("viewBox")).not.toBeNull();
    expect(picture.getAttribute("class") ?? "").not.toMatch(/\d+px/);
  });
});

describe("the accessible list of the architecture", () => {
  it("is always in the page and no control hides it", () => {
    const { container } = render(<ArchitectureDiagram commit={COMMIT} />);

    const list = container.querySelector("section[data-architecture-list]");

    expect(list).not.toBeNull();
    expect(list?.hasAttribute("hidden")).toBe(false);
    expect(container.querySelectorAll("[data-architecture-card]")).toHaveLength(ARCHITECTURE_NODES.length);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("carries the heading, the sentence and the links of every node", () => {
    const { container } = render(<ArchitectureNodeList commit={COMMIT} />);

    for (const node of ARCHITECTURE_NODES) {
      const card = container.querySelector(`[data-architecture-card="${node.id}"]`);

      expect(card?.querySelector("h3")?.textContent).toBe(node.label);
      expect(card?.textContent).toContain(node.summary);
      expect(card?.querySelector(`a[href="${sourceUrlOf(node.module, COMMIT)}"]`)).not.toBeNull();
    }
  });

  it("never skips a level of the outline of the headings", () => {
    const { container } = render(<ArchitectureDiagram commit={COMMIT} />);

    const levels = Array.from(container.querySelectorAll("h1, h2, h3, h4, h5, h6")).map((heading) =>
      heading.tagName.toLowerCase(),
    );

    expect(container.querySelector("h1")).toBeNull();
    expect(levels).toEqual(ARCHITECTURE_NODES.map(() => "h3"));
  });
});

describe("the card of one node", () => {
  it("shows the name of the node as the heading of the level the caller chose", () => {
    const node = nodeAt(0);
    const { container } = render(<ArchitectureNodeCard commit={COMMIT} node={node} titleLevel="h2" />);

    expect(container.querySelector("h2")?.textContent).toBe(node.label);
    expect(container.querySelector("h3")).toBeNull();
  });

  it("links to the module of the node and to its records", () => {
    const node = nodeAt(1);
    const { container } = render(<ArchitectureNodeCard commit={COMMIT} node={node} />);

    const links = Array.from(container.querySelectorAll("a"));

    expect(links.map((link) => link.getAttribute("href"))).toContain(sourceUrlOf(node.module, COMMIT));
    for (const record of node.records) {
      expect(links.map((link) => link.getAttribute("href"))).toContain(recordUrlOf(record.path, COMMIT));
    }
  });
});
