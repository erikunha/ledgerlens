/**
 * The test of the pane of the SQL of a tool call.
 *
 * Why this test exists: the drawer of a call shows the statement that the agent asked the ledger,
 * and that statement comes from a recording. It is text that a browser never ran and that the
 * backend does not sanitise today, so the pane has to show it exactly as it was recorded, as text,
 * in a region that the keyboard can reach, with a name and without announcing anything (ADR-048).
 *
 * Why the case reads the source of the module and the stylesheet: the rules that the pane never
 * writes the statement into the markup of the page, never turns an amount into a number and never
 * reads the network are rules about WHERE they are written, and no observation of the rendered
 * tree can tell that a module never reads the network. The fence of the network of the repository
 * walks the source for the same reason.
 *
 * Every case runs with no key and no network: the pane is a component of the interface and
 * nothing else.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SqlCodePane } from "@/features/agent-trace/SqlCodePane";

/**
 * The statement of the published scenario, exactly as the recording carries it.
 *
 * Why the case uses the statement of the bundle: the pane is proved with the text that a real
 * recording ships, and the literal `'TX-2048'` is the one the bundle of the scenario carries.
 */
const RECORDED_SQL =
  "SELECT * FROM (SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at) LIMIT 50";

/**
 * A statement whose literal looks like markup.
 *
 * Why the case builds it: the statement of a recording is text that came from a model, and a
 * literal that carries a tag has to show the tag and never become an element.
 */
const MARKUP_SQL =
  "SELECT * FROM payments WHERE note = '<script>alert(\"x\")</script>' AND city = '&amp;' LIMIT 1";

/**
 * A statement that carries an amount of the ledger.
 *
 * Why the amount is a text: the calculator of the core works with `Decimal` and the bundle carries
 * the amounts as text, so a pane that turned the amount into a number would write a value that the
 * core never wrote.
 */
const AMOUNT_SQL = "SELECT amount FROM payments WHERE amount = '566.79' LIMIT 1";

/**
 * The source of the module of the pane.
 *
 * Why the case reads the file and not the running code: the rules about the markup of the
 * statement, about the arithmetic and about the network are rules about where they are written.
 */
function sourceOfThePane(): string {
  return readFileSync(join(process.cwd(), "features", "agent-trace", "SqlCodePane.tsx"), "utf8");
}

/**
 * The stylesheet of the site.
 *
 * Why the case reads the file: the class of the pane is the rule that gives the pane its sideways
 * scroll, and the rule lives in the stylesheet of the site, not in the markup of the pane.
 */
function stylesheetOfTheSite(): string {
  return readFileSync(join(process.cwd(), "app", "globals.css"), "utf8");
}

/**
 * The body of a rule of the stylesheet, the text between its braces.
 *
 * Why the function returns the body and not the whole file: a case asserts about one property of
 * one rule, and a rule that carries the property is enough to hold it.
 */
function bodyOfTheRule(source: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const found = new RegExp(`${escaped}\\s*\\{([^}]*)\\}`).exec(source);
  return found?.[1] ?? "";
}

describe("the pane of the SQL of a tool call", () => {
  it("shows the statement as text, in the pane of the design system", () => {
    // It proves that the statement is written as a text node inside the pane of the design
    // system, and that the pane holds the statement and nothing else.
    render(<SqlCodePane sql={RECORDED_SQL} />);

    const pane = screen.getByRole("region", { name: "The SQL of the call" });

    expect(pane.tagName).toBe("PRE");
    expect(pane).toHaveClass("ll-code-pane");
    expect(pane.textContent).toBe(RECORDED_SQL);

    // the statement lives in a `code` inside the pane, and the pane holds nothing else
    const code = pane.querySelector("code");
    expect(code).not.toBeNull();
    expect(code?.textContent).toBe(RECORDED_SQL);
    expect(pane.children).toHaveLength(1);
  });

  it("is a stop of the keyboard, because a region that scrolls has to be reachable", () => {
    // It proves that the pane is a stop of the keyboard: a region that scrolls sideways and that
    // the keyboard cannot reach is a region that a keyboard visitor cannot read.
    render(<SqlCodePane sql={RECORDED_SQL} />);

    const pane = screen.getByRole("region", { name: "The SQL of the call" });

    expect(pane).toHaveAttribute("tabindex", "0");

    pane.focus();
    expect(pane).toHaveFocus();
  });

  it("is a named region, and it takes the name that the caller gives it", () => {
    // It proves that the pane carries a name, because the name of a region is what a reader of a
    // screen reader announces, and that the caller can name it after the call it shows.
    const { rerender } = render(<SqlCodePane sql={RECORDED_SQL} />);

    expect(screen.getByRole("region", { name: "The SQL of the call" })).toBeInTheDocument();

    rerender(<SqlCodePane sql={RECORDED_SQL} label="The statement of the call of query_ledger" />);

    expect(
      screen.getByRole("region", { name: "The statement of the call of query_ledger" }),
    ).toBeInTheDocument();
  });

  it("announces nothing, and it adds no heading and no other landmark to the page", () => {
    // It proves that the pane is silent: the dialog announces itself and the reader of the replay
    // keeps the one polite region of the page. It proves that the pane adds no heading, because
    // the heading of the statement is the `h3` of the drawer and the outline never skips a level.
    render(<SqlCodePane sql={RECORDED_SQL} />);

    const pane = screen.getByRole("region", { name: "The SQL of the call" });

    expect(pane).not.toHaveAttribute("aria-live");
    expect(pane.querySelectorAll("[aria-live]")).toHaveLength(0);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(pane.getAttribute("role")).toBe("region");

    expect(pane.querySelectorAll("h1, h2, h3, h4, h5, h6")).toHaveLength(0);
    // the region of the pane is the only role of the pane, and it adds no landmark of its own
    expect(pane.querySelectorAll("[role]")).toHaveLength(0);
  });

  it("shows a literal that looks like markup as text and never as an element", () => {
    // It proves that a literal that carries a tag is a literal that shows the tag: React escapes
    // a text node, so the statement never becomes markup of the page.
    render(<SqlCodePane sql={MARKUP_SQL} />);

    const pane = screen.getByRole("region", { name: "The SQL of the call" });

    expect(pane.textContent).toBe(MARKUP_SQL);
    expect(pane.textContent).toContain("<script>");
    expect(document.querySelector("script")).toBeNull();
    expect(pane.querySelectorAll("script")).toHaveLength(0);

    // the pane holds the `code` of the statement and nothing that the statement brought with it
    expect(pane.children).toHaveLength(1);
    expect(pane.firstElementChild?.tagName).toBe("CODE");
  });

  it("never writes the statement into the markup of the page", () => {
    // It proves that the pane has no way to write the statement as markup of the page, and that it
    // has no highlighter and no parser of SQL: a highlighter either reads the text with a grammar
    // of SQL or writes the statement into the markup of the page.
    const source = sourceOfThePane();

    expect(source).not.toContain("dangerouslySetInnerHTML");
    expect(source).not.toContain("innerHTML");
  });

  it("keeps the scroll of the statement inside the pane and the page from scrolling sideways", () => {
    // It proves that the class of the pane is the rule that gives the pane its sideways scroll and
    // that the scroll never chains to the page, and that the pane never stretches the drawer.
    const stylesheet = stylesheetOfTheSite();

    const pane = bodyOfTheRule(stylesheet, ".ll-code-pane");
    expect(pane).toContain("overflow-x: auto");
    expect(pane).toContain("overscroll-behavior-x: contain");
    expect(pane).toContain("min-width: 0");

    // the page itself never scrolls sideways, only the pane of the code does
    const page = bodyOfTheRule(stylesheet, "body");
    expect(page).toContain("overflow-x: hidden");

    // and the pane of the component is the element that carries that class
    render(<SqlCodePane sql={RECORDED_SQL} />);
    const rendered = screen.getByRole("region", { name: "The SQL of the call" });
    expect(rendered).toHaveClass("ll-code-pane");
  });

  it("shows the amount of the server as the text it sent, and never turns it into a number", () => {
    // It proves that the pane shows the amount of the ledger exactly as the core wrote it, and that
    // the pane never converts a value of the recording into a binary float.
    render(<SqlCodePane sql={AMOUNT_SQL} />);

    const pane = screen.getByRole("region", { name: "The SQL of the call" });

    expect(pane.textContent).toBe(AMOUNT_SQL);
    expect(pane.textContent).toContain("'566.79'");
    expect(pane.textContent).not.toContain("566,79");

    const source = sourceOfThePane();
    expect(source).not.toContain("Number(");
    expect(source).not.toContain("parseFloat");
    expect(source).not.toContain("parseInt");
  });

  it("reads its props only, and it calls nobody", () => {
    // It proves that the pane never reads the network: the site is a static export and the pane
    // holds the statement that the reader of the replay already holds.
    const source = sourceOfThePane();

    expect(source).not.toContain("fetch(");
    expect(source).not.toContain("XMLHttpRequest");
    expect(source).not.toContain("EventSource");
    expect(source).not.toContain("WebSocket");
    expect(source).not.toContain("@/lib/api/client");
    expect(source).not.toContain("@/lib/api/live");
  });
});
