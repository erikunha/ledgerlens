"use client";

/**
 * The tabs of the design system.
 *
 * Why this file exists: the reader of a recording shows its panels side by side, and a panel that
 * hides the others behind a row of buttons is easier to read than four panels at once. The
 * primitive wraps `@radix-ui/react-tabs`, which the frontend already depends on, so the milestone
 * adds no dependency and the lock file of the repository does not move.
 *
 * Why the tabs are controlled: the tab that is open is part of the state of the visit, and the
 * visitor can arrive at a tab through the URL. The primitive therefore takes the open tab and
 * hands back the tab the visitor picked.
 */

import * as RadixTabs from "@radix-ui/react-tabs";
import type { ReactElement, ReactNode } from "react";

import { cn } from "@/lib/design/cn";

/**
 * One tab of the primitive.
 *
 * Why the content travels with the label: the primitive does not know what a panel holds, and the
 * caller keeps the panel and its content in one place.
 */
export interface TabItem {
  /** The value of the tab, the word that identifies it. */
  readonly value: string;
  /** The label the visitor reads. */
  readonly label: string;
  /** What the tab shows when it is open. */
  readonly content: ReactNode;
}

/**
 * The props of the tabs.
 *
 * Why the label of the whole group is required: a row of buttons without a name is a row of
 * buttons a screen reader announces without a context.
 */
export interface TabsProps {
  /** The tabs of the group. */
  readonly items: readonly TabItem[];
  /** The value of the tab that is open. */
  readonly value: string;
  /** The function that is called with the tab the visitor picked. */
  readonly onValueChange: (value: string) => void;
  /** The name of the group of tabs. */
  readonly label: string;
}

/**
 * The tabs of the design system.
 *
 * The primitive shows the content of the tab that is open, and the other tabs are unmounted, so a
 * panel that is not read does not stay in the page.
 */
export function Tabs(props: TabsProps): ReactElement {
  return (
    <RadixTabs.Root
      value={props.value}
      onValueChange={props.onValueChange}
      className="flex flex-col gap-3"
    >
      <RadixTabs.List
        aria-label={props.label}
        className="flex flex-wrap items-center gap-1 border-b border-line"
      >
        {props.items.map((item) => (
          <RadixTabs.Trigger
            key={item.value}
            value={item.value}
            className={cn(
              "rounded-t border-b-2 border-transparent px-3 py-2 text-sm font-medium text-text-muted",
              "hover:text-foreground data-[state=active]:border-foreground data-[state=active]:text-foreground",
            )}
          >
            {item.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {props.items.map((item) => (
        <RadixTabs.Content key={item.value} value={item.value} className="focus:outline-none">
          {item.content}
        </RadixTabs.Content>
      ))}
    </RadixTabs.Root>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the primitive at once. */
export const __all__ = ["TabItem", "TabsProps", "Tabs"] as const;
