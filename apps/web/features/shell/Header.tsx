"use client";

/**
 * The header of the shell.
 *
 * Why this file exists: every page of the site needs the same answer to the same question, which
 * question is on the screen, and the header is where that answer sits. It carries the name of the
 * site, the indicator of the mode and the navigation of the rooms, so a header never competes with
 * the content of the page for the attention of the reader.
 *
 * Why the raw mode of the artifact is not here: the raw mode belongs to the panel of the run,
 * which is where the artifact is read (ADR-043). The header carries the label, and the label of a
 * recorded bundle never says live.
 *
 * Why the header is a client component: the navigation has to say which room the visitor is in,
 * and only the browser knows the address of the page. The header reads that address and marks the
 * room, so a visitor who lands on a room and a reader of a screen reader both know where they are.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactElement } from "react";

import { buttonClasses } from "@/components/ui/Button";
import type { TraceMode } from "@/lib/api/schemas";

import { ModeIndicator } from "./ModeIndicator";

/**
 * The rooms of the site, with the path of each one.
 *
 * Why the list lives here and not in the pages: the rooms are the same on every page of the site,
 * and a list written by a page is a list that a page can forget. The tour of the architecture was
 * unreachable for a long time because no header ever named it, and a header that names the rooms
 * is what keeps every room reachable from every page.
 */
const ROOMS = [
  { href: "/replay", label: "Recorded demo" },
  { href: "/sandbox", label: "Sandbox" },
  { href: "/live", label: "Live mode" },
  { href: "/engineering", label: "Architecture" },
] as const;

/**
 * The props of the header.
 *
 * Why the mode is optional: a page that shows no recording has no mode to announce.
 */
export interface HeaderProps {
  /** The mode of what the page shows. */
  readonly mode?: TraceMode | null;
}

/**
 * The header of the shell.
 *
 * The header is the landmark of the banner of the page, so a screen reader can jump to it and
 * back to the content.
 *
 * Why the banner carries a name: a reader who jumps between the landmarks of a page hears the
 * name of the banner as "banner" when it has none, and a name that says which site it is tells the
 * reader that the jump reached the right page.
 *
 * Why the navigation is a landmark with a name: the rooms of the site are the way out of every
 * page, and a reader of a screen reader has to be able to jump to them and to know that the jump
 * reached the rooms.
 *
 * Why the room the visitor is in is marked with an attribute and not with a colour: the mark of
 * the room has to survive the forced colours mode of the system and low vision.
 */
export function Header(props: HeaderProps): ReactElement {
  const pathname = usePathname() ?? "";

  return (
    <header aria-label="LedgerLens" className="border-b border-line bg-surface">
      <div className="mx-auto flex w-full max-w-content flex-wrap items-center justify-between gap-3 px-6 py-4">
        <Link href="/" className="text-base font-semibold text-foreground">
          LedgerLens
        </Link>
        <ModeIndicator mode={props.mode ?? null} />
      </div>

      <nav aria-label="The rooms of the demo" className="mx-auto w-full max-w-content px-6 pb-4">
        <ul className="flex flex-wrap items-center gap-2">
          {ROOMS.map((room) => {
            // The room of a scenario is the room of the recorded demo, so the mark follows the path
            // and not only the exact address of the room.
            const isTheRoomOfTheVisitor = pathname.startsWith(room.href);

            return (
              <li key={room.href}>
                <Link
                  aria-current={isTheRoomOfTheVisitor ? "page" : undefined}
                  className={buttonClasses(isTheRoomOfTheVisitor ? "primary" : "ghost", "sm")}
                  href={room.href}
                >
                  {room.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </header>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the header at once. */
export const __all__ = ["HeaderProps", "Header"] as const;
