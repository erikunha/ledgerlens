/**
 * The component of the guided tour.
 *
 * Why this file exists: the cold start of a visitor who knows nothing about the repository is a
 * path of steps over the reader of a recording. The component draws the steps of the guide over
 * the reader, and it never draws the reader itself: the guide names regions of the reader and the
 * reader owns the layout, so the tour asks the reader to show a region and the reader decides how
 * the region is shown. A tour that owned the layout would be a second reader, and two readers of
 * the same recording would disagree one day.
 *
 * Why the steps are drawn from the guide and never written here: the guide is data, and the test
 * of the guide reads it without a browser. A step written in the component would be a step no test
 * could check, and the promises of the cold start are exactly the promises the test checks.
 *
 * Why the tour adds no verdict of its own: the sentences of the steps explain what the reader
 * shows, and the decision of the case is the decision the recording carries. The tour says how to
 * read the case and never what the case decides.
 */

"use client";

import Link from "next/link";
import type { ReactElement } from "react";

import { Button } from "@/components/ui/Button";
import type { GuideRegion, ReplayGuide } from "@/lib/replay/guide";

/**
 * The identifier of the anchor of a region of the reader.
 *
 * Why the tab regions keep the identifiers of the panels: the panels of the sections of the replay
 * already carry an identifier, and a deep link of the site points at them. The tour names the same
 * identifier, so a region of the guide and a panel of the reader are the same place and not two
 * places that could drift apart.
 */
export function regionAnchorId(region: GuideRegion): string {
  switch (region) {
    case "execution":
    case "ledger":
    case "evidence":
    case "decision":
    case "provenance":
      return `ledgerlens-section-${region}`;
    default:
      return `ledgerlens-region-${region}`;
  }
}

/** The props of the guided tour. */
export interface GuidedTourProps {
  /** The guide of the scenario, as the data of the cold start holds it. */
  readonly guide: ReplayGuide;
  /**
   * Shows a region of the reader.
   *
   * Why the tour asks and never shows: the reader owns the layout, so the reader is the one that
   * opens the tab of a region or moves the focus to it. The tour only says which region the step
   * is about.
   */
  readonly onShowRegion: (region: GuideRegion) => void;
}

/**
 * The guided tour of a recording.
 *
 * The tour draws the steps of the guide in the order the visitor walks them, with a control that
 * asks the reader to show the region of the step, and it ends in the fork, so the visitor who
 * finished the path can mutate the case in the sandbox.
 */
export function GuidedTour({ guide, onShowRegion }: GuidedTourProps): ReactElement {
  return (
    <section
      aria-label="The guided path"
      className="flex flex-col gap-3 rounded-lg border border-line bg-background p-4"
    >
      <div className="flex flex-col gap-1">
        <h2 className="text-base font-semibold">The guided path</h2>
        <p className="text-sm text-text-muted">
          New here? These steps walk the recording of {guide.scenario} from the first event to the
          decision of the case. The path asks no key and no network.
        </p>
      </div>
      <ol className="flex flex-col gap-3">
        {guide.steps.map((step, index) => (
          <li key={step.id} className="flex flex-col gap-1">
            <p className="text-sm text-foreground" id={`ledgerlens-guide-step-${step.id}`}>
              <span className="font-medium">{index + 1}.</span> {step.sentence}
            </p>
            <div>
              {/*
                The name of the control is short, and the sentence of the step is the description of the
                control: an accessible name that carried the whole sentence would collide with the names of
                the page, and a name that is a sentence is a name that is hard to hear.
              */}
              <Button
                variant="ghost"
                size="sm"
                className="min-h-12"
                aria-describedby={`ledgerlens-guide-step-${step.id}`}
                onClick={() => onShowRegion(step.region)}
              >
                Show me
              </Button>
            </div>
          </li>
        ))}
      </ol>
      <p className="text-sm text-text-subtle">
        <Link className="inline-flex min-h-12 items-center underline underline-offset-2" href="/sandbox">
          Mutate this case in the sandbox
        </Link>
      </p>
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the tour at once. */
export const __all__ = ["GuidedTourProps", "GuidedTour", "regionAnchorId"] as const;
