/**
 * The page of the address that the site does not publish.
 *
 * Why this file exists: the route of a scenario answers with the page of 404 when the catalog of
 * the scenarios does not publish the identifier of the path, and the static host of the export
 * answers with the page of 404 when a visitor follows an address that the site never wrote. Without
 * this page the export holds the page of error of the framework, which is outside the shell of the
 * site and outside its words (ADR-043).
 *
 * Why the page is the failure state of the site and not a page of its own: the site has one look
 * of failure, and a visitor who follows an address that does not exist reads the same panel as a
 * visitor whose page broke.
 */

import Link from "next/link";
import type { ReactElement } from "react";

import { buttonClasses } from "@/components/ui/Button";

import { SiteFailure } from "./error";

/**
 * The page of the address that the site does not publish.
 *
 * The page says that the address is not one of the published ones and it leads the visitor to the
 * catalog of the scenarios, which is the way into the recorded demo.
 */
export default function SiteNotFound(): ReactElement {
  return (
    <div className="mx-auto flex w-full max-w-content flex-col gap-8 px-6 py-12">
      <SiteFailure
        title="This page is not published"
        reason="The site publishes the catalog of the scenarios and the recorded run of every scenario of the catalog. This address is not one of them."
        hint="The catalog of the scenarios is the way into the recorded demo, and it needs no key and no network."
      >
        <Link className={buttonClasses("ghost", "sm")} href="/replay">
          The catalog of the scenarios
        </Link>
      </SiteFailure>
    </div>
  );
}
