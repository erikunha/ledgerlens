/**
 * The panel of the cost of a run, for every view that inspects a run.
 *
 * Why this file exists: the money of a run is shown by one panel only, the one of the models
 * (`features/models/CostReport.tsx`), and that panel renders the decimal texts of the server and
 * never an amount of its own. This file is the panel of the cost of a run that a run inspector
 * drops into its run view, so the cost of a live run and the cost of a run of the lab of the
 * evaluations are presented the same way, by the same component.
 *
 * Why the panel adds no money of its own: a second place that formats an amount is a second place
 * that can show a float, and the money of a run is never a binary float (FR-010, FR-011). The panel
 * reuses the report of the models and computes nothing.
 *
 * Why the panel is a region with a name: a run inspector shows several panels side by side, and a
 * reader of a screen reader has to be able to reach the one that carries the money.
 */

import type { ReactElement } from "react";

import { CostReport } from "@/features/models/CostReport";
import type { CostReportBody } from "@/lib/api/live";

/**
 * The props of the panel of the cost.
 *
 * Why the report can be null: the route of the cost answers `409` while the run is going, so the
 * panel says that the cost is not known yet instead of showing an empty report.
 */
export interface CostPanelProps {
  /** The report of the server, or `null` while there is none. */
  readonly report: CostReportBody | null;
  /** Whether the run is still going. */
  readonly running: boolean;
}

/**
 * The panel of the cost of a run.
 *
 * The panel presents the report of the server and nothing else: the observed cost and the
 * estimated cost are the texts the server sent, and the price of a model that was never verified
 * shows no amount at all.
 */
export function CostPanel({ report, running }: CostPanelProps): ReactElement {
  return (
    <section aria-label="The cost of the run" className="flex flex-col gap-2">
      <CostReport report={report} running={running} />
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the panel at once. */
export const __all__ = ["CostPanelProps", "CostPanel"] as const;
