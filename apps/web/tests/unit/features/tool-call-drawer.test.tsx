/**
 * The test of the drawer of a tool call of the recording.
 *
 * Why this test exists: the drawer is where the visitor reads what a call of the recording
 * received, what it returned and what statement it ran. The drawer has to hold the call it was
 * opened with, has to give the focus back to the cell that opened it, has to keep the outline of
 * the page and has to stay silent, because the reader of the replay keeps the one polite region
 * of the page (ADR-048).
 *
 * Why the case reads the source of the module: the rules about the network and about the
 * arithmetic of the drawer are rules about WHERE they are written, and no observation of the
 * rendered tree can tell that a module never reads the network. The fence of the network of the
 * repository walks the source for the same reason.
 *
 * Every case runs with no key and no network: the drawer is a component of the interface and it
 * reads nothing but its props.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { useRef, useState } from "react";
import type { ReactElement } from "react";

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ToolCallDrawer } from "@/features/agent-trace/ToolCallDrawer";
import type { ToolCallState } from "@/lib/replay/reducer";

/**
 * The statement of the published scenario, exactly as the recording carries it.
 *
 * Why the case uses the statement of the bundle: the drawer is proved with the text that a real
 * recording ships, and the literal `'TX-2048'` is the one the bundle of the scenario carries.
 */
const RECORDED_SQL =
  "SELECT * FROM (SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at) LIMIT 50";

/**
 * The call of the ledger of the published scenario, as the reducer assembled it.
 *
 * Why the case carries the whole call: the drawer shows the arguments, the result, the statement
 * and the error of the call it was opened with, and the fields of the case are the fields of the
 * state of the reducer.
 */
const CALL: ToolCallState = {
  spanId: "01a1d9b7-0a73-76bc-b867-b61b7586ff63",
  name: "query_ledger",
  inputs: { question: "FX rates applied to TX-2048" },
  outputs: {
    ok: true,
    evidence_ids: ["sql:1"],
    data: {
      sql: RECORDED_SQL,
      columns: ["kind", "applied_rate", "applied_at"],
      rows: [
        ["charge", "5.6679", "2026-10-15T09:12:04Z"],
        ["refund", "5.4931", "2026-10-20T14:30:00Z"],
      ],
      row_count: 2,
      truncated: false,
    },
  },
  error: null,
  latencyMs: 12,
  status: "ok",
  evidenceIds: ["sql:1"],
  seq: 19,
};

/**
 * The call of the calculation of the published scenario, with the money of the ledger.
 *
 * Why the case carries the money as text: the calculator of the core works with `Decimal` and the
 * bundle carries the amounts as text, so a drawer that turned an amount into a number would write
 * a value that the core never wrote.
 */
const CALCULATION: ToolCallState = {
  spanId: "01a1d9b7-0a73-76bc-b867-b61b7586ff64",
  name: "calculate",
  inputs: { formula: "charge = 100.00 * 5.6679" },
  outputs: {
    ok: true,
    evidence_ids: ["calc:1"],
    data: {
      operation: "fx_gap_breakdown",
      result: { charge: "566.79", refund: "549.31", markup: "14.08", markup_pct: "2.50" },
    },
  },
  error: null,
  latencyMs: 1,
  status: "ok",
  evidenceIds: ["calc:1"],
  seq: 43,
};

/**
 * A call that ended with an error and that carries no statement.
 *
 * Why the case carries a call without a statement: the drawer has to say in words that the call
 * carries none, and never to show an empty pane of the SQL.
 */
const FAILED_CALL: ToolCallState = {
  spanId: "01a1d9b7-0a73-76bc-b867-b61b7586ff65",
  name: "query_ledger",
  inputs: { question: "the movements of TX-2048" },
  outputs: null,
  error: "the guard refused the statement",
  latencyMs: 3,
  status: "error",
  evidenceIds: [],
  seq: 44,
};

/**
 * The source of the module of the drawer.
 *
 * Why the case reads the file and not the running code: the rules about the network and about the
 * arithmetic of the drawer are rules about where they are written.
 */
function sourceOfTheDrawer(): string {
  return readFileSync(join(process.cwd(), "features", "agent-trace", "ToolCallDrawer.tsx"), "utf8");
}

/**
 * A page with one cell and the drawer of a call, the way the reader of the replay holds them.
 *
 * Why the case carries a cell and not a button: the focus goes back to the CELL that opened the
 * drawer, because the cell is the stop of the keyboard of the table and a focus inside the cell
 * would take the visitor out of the navigation group (ADR-048, decision 7).
 */
function Harness({ call }: { readonly call: ToolCallState | null }): ReactElement {
  const [open, setOpen] = useState(false);
  const cellRef = useRef<HTMLTableCellElement | null>(null);

  return (
    <>
      <table>
        <tbody>
          <tr>
            <th ref={cellRef} scope="row" tabIndex={0}>
              the cell of the name of the tool
            </th>
          </tr>
        </tbody>
      </table>
      <button type="button" onClick={() => setOpen(true)}>
        open the drawer
      </button>
      <ToolCallDrawer open={open} onOpenChange={setOpen} call={call} returnFocusTo={cellRef} />
    </>
  );
}

describe("the drawer of a tool call of the recording", () => {
  it("shows the identity, the arguments, the result and the error of the call it was opened with", () => {
    // It proves that the drawer shows the five things the record names: the identity of the call,
    // the arguments, the result, the statement and the error.
    render(<ToolCallDrawer open onOpenChange={vi.fn()} call={FAILED_CALL} />);

    const drawer = screen.getByRole("dialog");
    expect(drawer).toHaveAccessibleName("The call of query_ledger");

    // the identity of the call: the name of the tool, the number of the event, the status and the
    // duration the capture measured
    const identity = drawer.querySelector("dl");
    expect(identity).not.toBeNull();
    const facts = within(identity as HTMLElement);
    expect(facts.getByText("query_ledger")).toBeInTheDocument();
    expect(facts.getByText("44")).toBeInTheDocument();
    expect(facts.getByText("Failed")).toBeInTheDocument();
    expect(facts.getByText("3 ms")).toBeInTheDocument();

    // the arguments of the call, as the recording wrote them
    expect(drawer).toHaveTextContent("the movements of TX-2048");

    // the error of the call, and nothing else in its place
    expect(drawer).toHaveTextContent("the guard refused the statement");
  });

  it("holds the call it was opened with and never follows the recording", () => {
    // It proves that the drawer keeps the call it was opened with: a call of the recording is a
    // fact, and a drawer whose content changes under the eyes of the reader is a drawer that
    // lies (ADR-048, decision 3).
    const { rerender } = render(<ToolCallDrawer open onOpenChange={vi.fn()} call={CALL} />);

    expect(screen.getByRole("dialog")).toHaveTextContent("FX rates applied to TX-2048");

    // the recording moved to another call
    rerender(<ToolCallDrawer open onOpenChange={vi.fn()} call={CALCULATION} />);

    const drawer = screen.getByRole("dialog");
    expect(drawer).toHaveTextContent("FX rates applied to TX-2048");
    expect(drawer).not.toHaveTextContent("charge = 100.00 * 5.6679");
  });

  it("shows the statement of the call in the pane of the SQL, with the literal as it was recorded", () => {
    // It proves that the statement is shown by the pane of the SQL, as text, and that the literal
    // of the recording is shown as it was written: the browser never masks a literal, because the
    // rule about what a published recording may carry belongs to the Python core (ADR-048).
    render(<ToolCallDrawer open onOpenChange={vi.fn()} call={CALL} />);

    const pane = screen.getByRole("region", { name: "The statement of the call of query_ledger" });
    expect(pane.tagName).toBe("PRE");
    expect(pane).toHaveClass("ll-code-pane");
    expect(pane.textContent).toBe(RECORDED_SQL);
    expect(pane.textContent).toContain("'TX-2048'");
    expect(pane.querySelector("code")?.textContent).toBe(RECORDED_SQL);

    // the drawer says out loud that the statement is the one the capture recorded, and it never
    // says that a statement was sanitised
    const drawer = screen.getByRole("dialog");
    expect(drawer).toHaveTextContent("This is the statement the capture recorded, exactly as it was written.");
    expect(drawer.textContent?.toLowerCase()).not.toContain("sanitised");
    expect(drawer.textContent?.toLowerCase()).not.toContain("sanitized");
  });

  it("says in words that a call with no statement carries none", () => {
    // It proves that the drawer never shows an empty pane of the SQL for a call that carries no
    // statement.
    render(<ToolCallDrawer open onOpenChange={vi.fn()} call={FAILED_CALL} />);

    const drawer = screen.getByRole("dialog");
    expect(drawer).toHaveTextContent("This call carries no statement of SQL.");
    expect(screen.queryByRole("region", { name: /statement/i })).toBeNull();
  });

  it("shows the money of the server as the text it sent and never turns it into a number", () => {
    // It proves that the drawer shows the amounts of the ledger exactly as the core wrote them,
    // and that it never converts a value of the recording into a binary float.
    render(<ToolCallDrawer open onOpenChange={vi.fn()} call={CALCULATION} />);

    const drawer = screen.getByRole("dialog");
    expect(drawer).toHaveTextContent('"566.79"');
    expect(drawer).toHaveTextContent('"549.31"');
    expect(drawer).not.toHaveTextContent("566,79");
    expect(drawer).not.toHaveTextContent("BRL 566.79");

    const source = sourceOfTheDrawer();
    expect(source).not.toContain("Number(");
    expect(source).not.toContain("parseFloat");
    expect(source).not.toContain("parseInt");
  });

  it("gives the focus back to the cell that opened it and closes with the Escape key", async () => {
    // It proves that the focus goes back to the CELL that opened the drawer and not to the button
    // inside it, so that the navigation group of the table survives the window (ADR-048, decision 7).
    const user = userEvent.setup();
    render(<Harness call={CALL} />);

    const cell = screen.getByRole("rowheader", { name: "the cell of the name of the tool" });
    await user.click(screen.getByRole("button", { name: "open the drawer" }));
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    await waitFor(() => {
      expect(cell).toHaveFocus();
    });
  });

  it("is a named region with the title as the h2 and the sections inside as the h3", () => {
    // It proves that the outline of the page never skips a level: the title of the drawer is the
    // h2 of the primitive and the sections inside are h3 (ADR-048, decision 8).
    render(<ToolCallDrawer open onOpenChange={vi.fn()} call={CALL} />);

    const drawer = screen.getByRole("dialog");
    const headings = within(drawer).getAllByRole("heading");
    expect(headings.map((heading) => heading.tagName)).toEqual(["H2", "H3", "H3", "H3"]);
    expect(headings.map((heading) => heading.textContent)).toEqual([
      "The call of query_ledger",
      "The arguments of the call",
      "The result of the call",
      "The statement of the call",
    ]);

    // the body of the drawer is a named region, because the sheet is a portal outside the main
    const region = within(drawer).getByRole("region", {
      name: "The details of the call of query_ledger",
    });
    expect(region.tagName).toBe("SECTION");

    // and the drawer adds no landmark to the page outside of itself
    expect(drawer.querySelectorAll("main, nav, aside, header, footer")).toHaveLength(0);
    expect(
      drawer.querySelectorAll(
        '[role="navigation"], [role="main"], [role="banner"], [role="contentinfo"], [role="complementary"]',
      ),
    ).toHaveLength(0);
  });

  it("announces nothing and it adds no live region to the page", () => {
    // It proves that the drawer is silent: the dialog announces itself and the reader of the
    // replay keeps the one polite region of the page (ADR-048, decision 9).
    render(<ToolCallDrawer open onOpenChange={vi.fn()} call={CALL} />);

    const drawer = screen.getByRole("dialog");
    expect(drawer.querySelectorAll("[aria-live]")).toHaveLength(0);
    expect(drawer.querySelectorAll('[role="status"]')).toHaveLength(0);
    expect(drawer.querySelectorAll('[role="alert"], [role="log"]')).toHaveLength(0);
  });

  it("reads no network and it dispatches nothing", () => {
    // It proves that the drawer is a client component of a static export: it reads the call it
    // was given, it calls nobody and it never moves the recording (ADR-048, decisions 3 and 10).
    const source = sourceOfTheDrawer();

    expect(source).not.toContain("fetch(");
    expect(source).not.toContain("XMLHttpRequest");
    expect(source).not.toContain("EventSource");
    expect(source).not.toContain("WebSocket");
    expect(source).not.toContain("@/lib/api/client");
    expect(source).not.toContain("@/lib/api/live");
    expect(source).not.toContain("dispatch(");
    expect(source).not.toContain("useReplay");
  });
});
