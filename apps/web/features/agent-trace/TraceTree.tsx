/**
 * The tree of the investigation of a recorded run.
 *
 * Why this file exists: a recorded run is a nest of spans, and a reader who sees only a flat list
 * of them cannot tell which step opened which one. The tree shows the nesting as the recording
 * nested it, with the kind of every span and the moment it was opened, and it is walked with the
 * arrow keys, with the Home key and with the End key, so that a reader with a keyboard reaches
 * every span of the run (FR-012, ADR-043).
 *
 * Why the tree carries the semantics of a tree: a list of buttons tells a reader with a screen
 * reader that there are thirty one buttons, and it tells nothing about which span opened which
 * one. The role of the tree, the level of every row and the expanded state of the rows that have
 * children say it (FR-031).
 *
 * Why the name of a row is its own text: a name that hides the words of the row from the reader
 * breaks the rule that says the visible text of a control belongs to its name, and the reader
 * loses the name, the kind and the number of the event (WCAG 2.5.3).
 *
 * Why the tree is never collapsed: the recording is read as it was captured and the spans it
 * opened are always shown, so a node with children is always expanded. There is nothing to open
 * and nothing to close, and the right arrow key goes to the first span under the node and the
 * left arrow key goes to its parent.
 *
 * Why the chosen span is marked by more than a colour: a tint of the background alone is a mark
 * that a reader with low vision cannot see, and a tint that a hovered row also wears tells the
 * reader nothing. The chosen span carries a border on its left and a heavier name, and the two
 * marks survive the forced colours mode of the system, where a background tint does not.
 *
 * Why the indent of a row is a sum of the steps of the scale: the depth of a node has to grow the
 * indent, and the spacing scale of the design system is the only source of the sizes of the site.
 * Every level of the nest of the row adds one step of the scale, so the indent of a row moves with
 * the scale and no pixel of it is written in the markup.
 */

"use client";

import { useRef, useState } from "react";
import type { KeyboardEvent, ReactElement, ReactNode } from "react";

import type { TraceTreeNode } from "@/lib/replay/selectors";

/**
 * The props of the tree.
 *
 * Why the selection is a callback: the tree holds no state of its own. The reader decides what
 * selecting a span means, and the tree only says which span was selected.
 */
export interface TraceTreeProps {
  /** The spans of the recording, with the spans they opened nested under them. */
  readonly nodes: readonly TraceTreeNode[];
  /** The span the visitor selected, when one is selected. */
  readonly selectedSpanId: string | null;
  /** Called with the identifier of the span the visitor selected. */
  readonly onSelect: (spanId: string) => void;
}

/**
 * Flattens the tree into the rows the reader walks.
 *
 * Why the rows are flat: the reader walks the tree row by row with the arrow keys, and a walk
 * over a nest of lists needs a single list of rows to move through.
 */
function flatten(nodes: readonly TraceTreeNode[], rows: TraceTreeNode[] = []): TraceTreeNode[] {
  for (const node of nodes) {
    rows.push(node);
    flatten(node.children, rows);
  }
  return rows;
}

/**
 * Finds the row of the parent of a row of the tree.
 *
 * Why the parent is found by the depth and not by the identifier of the parent span: the tree of
 * the interface is flattened into rows, and the depth of a row says how deep it sits, so the
 * nearest row above it that sits one level less is its parent.
 *
 * Why a root has no parent: a root of the tree is a span whose parent is not in the recording,
 * and the left arrow key of a root has nowhere to go.
 */
function parentRow(rows: readonly TraceTreeNode[], index: number): number | null {
  const row = rows[index];
  if (row === undefined || row.depth === 0) {
    return null;
  }
  for (let above = index - 1; above >= 0; above -= 1) {
    const candidate = rows[above];
    if (candidate !== undefined && candidate.depth === row.depth - 1) {
      return above;
    }
  }
  return null;
}

/**
 * Finds the row of the first child of a row of the tree.
 *
 * Why the child is found by the depth: the rows of the tree are flattened in the order of the
 * recording, and the row that follows a row and sits one level deeper is its first child.
 *
 * Why a leaf has no child: a span that opened no span has nothing under it.
 */
function firstChildRow(rows: readonly TraceTreeNode[], index: number): number | null {
  const row = rows[index];
  const below = rows[index + 1];
  if (row === undefined || below === undefined || below.depth !== row.depth + 1) {
    return null;
  }
  return index + 1;
}

/**
 * The props of the indent of a row of the tree.
 */
interface TreeIndentProps {
  /** The depth of the node the row holds, the distance of the node from the root of its tree. */
  readonly depth: number;
  /** The row to indent. */
  readonly children: ReactNode;
}

/**
 * The indent of a row of the tree.
 *
 * Why the indent is a nest of wrappers: the depth of a node has to grow the indent, and the
 * spacing scale of the design system is the only source of the sizes of the site. Every level of
 * the nest adds one step of the scale, so the indent of a row is the sum of the steps of its
 * depth, the indent moves with the scale, and no pixel of it is written in the markup.
 */
function TreeIndent({ depth, children }: TreeIndentProps): ReactElement {
  if (depth <= 0) {
    return <>{children}</>;
  }
  return (
    <div className="pl-4">
      <TreeIndent depth={depth - 1}>{children}</TreeIndent>
    </div>
  );
}

/**
 * The tree of the investigation of a recorded run.
 *
 * Every span is a row of the tree, so a visitor reaches it with the keyboard and opens it with
 * the Enter and the Space keys. The up and the down arrow keys move the focus from one span to
 * the next one, the right arrow key goes to the first span under the one that holds the focus,
 * the left arrow key goes to its parent, the Home key goes to the first span and the End key
 * goes to the last one.
 *
 * The tree is one navigation group: only the row that holds the focus is in the tab order, and
 * the other rows are reached with the arrow keys, the way a tree is walked.
 */
export function TraceTree({ nodes, selectedSpanId, onSelect }: TraceTreeProps): ReactElement {
  const rows = flatten(nodes);
  const listRef = useRef<HTMLUListElement | null>(null);
  const [activeSpanId, setActiveSpanId] = useState<string | null>(null);

  // the row that is in the tab order: the one that holds the focus, or the first one of the tree
  const activeIndex =
    activeSpanId === null
      ? 0
      : Math.max(
          rows.findIndex((row) => row.spanId === activeSpanId),
          0,
        );

  const focusRow = (index: number): void => {
    const row = rows[index];
    if (!row) {
      return;
    }
    setActiveSpanId(row.spanId);
    const buttons = listRef.current?.querySelectorAll<HTMLButtonElement>("button[data-span]");
    const target = buttons?.[index];
    target?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLUListElement>): void => {
    if (rows.length === 0) {
      return;
    }

    const current = Array.from(
      listRef.current?.querySelectorAll<HTMLButtonElement>("button[data-span]") ?? [],
    );
    const active = current.indexOf(document.activeElement as HTMLButtonElement);
    const from = active === -1 ? 0 : active;

    let next: number | null = null;
    switch (event.key) {
      case "ArrowDown":
        next = Math.min(from + 1, rows.length - 1);
        break;
      case "ArrowUp":
        next = Math.max(from - 1, 0);
        break;
      case "ArrowRight":
        // the tree of the interface is never collapsed, so there is nothing to open: the right
        // arrow key goes to the first span under the one that holds the focus
        next = firstChildRow(rows, from) ?? from;
        break;
      case "ArrowLeft":
        // the tree of the interface is never collapsed, so there is nothing to close: the left
        // arrow key goes to the parent of the span that holds the focus
        next = parentRow(rows, from) ?? from;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = rows.length - 1;
        break;
      default:
        return;
    }

    event.preventDefault();
    focusRow(next);
  };

  return (
    <section
      aria-label="The tree of the investigation"
      className="rounded-lg border border-line bg-background"
    >
      <div className="flex flex-col gap-1 border-b border-line px-4 py-3">
        <h4 className="text-base font-semibold">The tree of the investigation</h4>
        <p className="text-sm text-text-muted">
          The spans of the recording, with the nesting the capture recorded. The up and the down
          arrow keys walk the tree, the right arrow key goes to the first span under the one that
          holds the focus, the left arrow key goes to its parent, and the Home and the End keys go
          to its ends.
        </p>
      </div>

      {rows.length === 0 ? (
        <p className="px-4 py-3 text-sm text-text-muted">The recording opened no span yet.</p>
      ) : (
        <ul
          ref={listRef}
          role="tree"
          className="flex flex-col gap-1 px-2 py-3"
          onKeyDown={handleKeyDown}
        >
          {rows.map((node, index) => {
            const isSelected = node.spanId === selectedSpanId;
            return (
              <li key={node.spanId} role="none">
                <TreeIndent depth={node.depth}>
                  <button
                    type="button"
                    role="treeitem"
                    data-span={node.spanId}
                    aria-level={node.depth + 1}
                    aria-expanded={node.children.length > 0 ? true : undefined}
                    aria-selected={isSelected ? "true" : undefined}
                    aria-current={isSelected ? "true" : undefined}
                    tabIndex={index === activeIndex ? 0 : -1}
                    onClick={() => {
                      setActiveSpanId(node.spanId);
                      onSelect(node.spanId);
                    }}
                    className={
                      isSelected
                        ? "flex w-full items-center gap-2 rounded border-l-2 border-foreground bg-surface-muted px-2 py-1 text-left text-sm"
                        : "flex w-full items-center gap-2 rounded border-l-2 border-transparent px-2 py-1 text-left text-sm hover:bg-surface"
                    }
                  >
                    {/* the weight of the name is the mark that says which span is the chosen one: a
                        weight survives the forced colours mode, where a tint of the background does
                        not, so the state is never carried by the colour alone */}
                    <span
                      className={
                        isSelected
                          ? "font-semibold text-foreground"
                          : "font-medium text-foreground"
                      }
                    >
                      {node.name ?? node.spanId}
                    </span>
                    {node.runType ? (
                      <span className="text-xs text-text-subtle">{node.runType}</span>
                    ) : null}
                    {node.startedSeq !== null ? (
                      <span className="text-xs text-text-subtle">event {node.startedSeq}</span>
                    ) : null}
                  </button>
                </TreeIndent>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the tree at once. */
export const __all__ = ["TraceTreeProps", "TraceTree"] as const;
