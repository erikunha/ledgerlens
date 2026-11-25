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
 *
 * Why the catalog of a real model is a room of its own: the site publishes two catalogs, the
 * recordings of the scripted model and the recordings of a real model, and each one has its own
 * route and its own pages (ADR-075). A visitor that is on one of them has to be able to reach the
 * other one from any page, and the header is the place where every room is named.
 */
const ROOMS = [
  { href: "/replay", label: "Recorded demo" },
  { href: "/replay-real", label: "Real model" },
  { href: "/sandbox", label: "Sandbox" },
  { href: "/live", label: "Live mode" },
  { href: "/engineering", label: "Architecture" },
] as const;

/**
 * Says whether a path is inside a room.
 *
 * Why the comparison is by segment and not by prefix: the room of the scripted model is `/replay`
 * and the room of a real model is `/replay-real`. A comparison that only looked at the beginning
 * of the path would say that a page of the catalog of a real model is inside the room of the
 * scripted model, and the header would announce the wrong room as the room of the visitor
 * (ADR-075).
 */
function isInsideTheRoom(pathname: string, room: string): boolean {
  return pathname === room || pathname.startsWith(`${room}/`);
}

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
            // and not only the exact address of the room. The comparison is by segment, so the
            // catalog of a real model is never announced as the room of the scripted model.
            const isTheRoomOfTheVisitor = isInsideTheRoom(pathname, room.href);

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
