/**
 * The pane of the SQL of a tool call.
 *
 * Why this file exists: the drawer of a call shows the statement that the agent asked the ledger,
 * and a statement is read as code. The pane is the `pre` of the design system that carries the
 * class `ll-code-pane`, the only area of the page that scrolls sideways, so a long statement never
 * makes the page scroll sideways (ADR-048, decision 4).
 *
 * Why the statement is a text node and never markup: the statement comes from a recording, and
 * React escapes a text node. A literal that carries a tag shows the tag and never becomes an
 * element of the page.
 *
 * Why the pane does not sanitise the literals of the statement: the backend does not sanitise them
 * today, and the rule about what a published recording may carry belongs to the Python core, in
 * `ledgerlens/tools/sql.py` and in the recorder that carries every statement of every span
 * (ADR-048, decision 5). A pane that masked a literal would show a statement that no ledger ever
 * received, and a literal such as `'TX-2048'` is therefore shown as `'TX-2048'`. The next reader
 * must not "fix" that, and must not move the rule of the core into the browser.
 *
 * Why there is no highlighter and no parser of SQL: a highlighter either reads the statement with
 * a grammar of SQL, which is a parser of text that came from a recording, or writes the statement
 * into the markup of the page with tags of its own. The first adds a dependency to a static
 * export, the second is the shape of an injection (ADR-048, decision 4).
 *
 * Why the pane announces nothing: the dialog of the drawer announces itself and the reader of the
 * replay keeps the one polite region of the page, so a region that announces a statement that does
 * not change is noise (ADR-048, decision 9).
 *
 * Why the pane reads its props only: the site is a static export with no server, and the statement
 * comes from the state of the reader, which already holds it (ADR-048, decision 10).
 */

import type { ReactElement } from "react";

/**
 * The props of the pane of the SQL.
 *
 * Why the statement is a string and not a tree of nodes: the pane shows what the recording carries
 * and nothing else, so the caller hands it the text and the pane hands it to the browser as a text
 * node.
 */
export interface SqlCodePaneProps {
  /** The statement, exactly as the recording carries it. */
  readonly sql: string;
  /** The name of the region of the pane. */
  readonly label?: string;
}

/**
 * The name of the region when the caller gives none.
 *
 * Why the default names the statement: the pane is a region and the name of a region is what a
 * reader of a screen reader announces, so the default has to say what the region holds.
 */
const DEFAULT_LABEL = "The SQL of the call";

/**
 * The pane of the SQL of a tool call.
 *
 * The pane is a named region that the keyboard can reach, because a region that scrolls sideways
 * and that cannot be reached is a region that a keyboard visitor cannot read. It holds the
 * statement as a text node, in a `code`, and it changes nothing: no literal is masked, no
 * character is dropped and no value is turned into a number.
 */
export function SqlCodePane({ sql, label = DEFAULT_LABEL }: SqlCodePaneProps): ReactElement {
  return (
    <pre
      // the class of the design system is what gives the pane its sideways scroll, and the pane
      // never lets that scroll reach the page
      className="ll-code-pane min-w-0 rounded border border-line bg-surface-muted p-3 font-mono text-xs text-foreground"
      // the pane is a stop of the keyboard of the drawer, because it scrolls
      tabIndex={0}
      role="region"
      aria-label={label}
    >
      {/* the statement is a text node: React escapes it, so a literal never becomes markup */}
      <code>{sql}</code>
    </pre>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the pane at once. */
export const __all__ = ["SqlCodePaneProps", "SqlCodePane"] as const;
