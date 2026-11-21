"use client";

/**
 * The panel of the cost of a run.
 *
 * Why this file exists: this is the only place of the interface where money is shown, and money is
 * never a binary float. The panel renders the decimal texts the server sent and renders nothing
 * where the server sent `null`. It never multiplies a price by a number of tokens, it never
 * formats an amount and it never invents one.
 *
 * When the registry has no verified price, the panel says that the price is unknown and shows no
 * amount at all (FR-011).
 */

import type { CostReportBody } from "@/lib/api/live";

/**
 * The props of the panel.
 *
 * Why the panel knows whether the run is going: the cost route answers `409` while the run is
 * going, so the panel says that the cost is not known yet instead of showing an empty report.
 */
export interface CostReportProps {
  /** The report of the server, or `null` while there is none. */
  report: CostReportBody | null;
  /** Whether the run is still going. */
  running: boolean;
}

/**
 * The panel of the cost.
 *
 * The amounts are the texts of the server, one row each, and a row without an amount does not
 * exist: the server sent `null` and the panel shows nothing there.
 */
export function CostReport({ report, running }: CostReportProps) {
  if (!report) {
    return (
      <div className="rounded-lg border border-line bg-background p-4">
        <h3 className="text-base font-semibold">Cost of the run</h3>
        <p className="text-sm text-text-muted">
          {running
            ? "The cost of the run is not known yet: the server sends it when the run ends."
            : "The server sent no report of the cost of this run."}
        </p>
      </div>
    );
  }

  const observed = report.observed_cost_usd;
  const estimated = report.estimated_cost_usd;
  const showsMoney = report.price_known && (observed !== null || estimated !== null);

  return (
    <div className="rounded-lg border border-line bg-background p-4">
      <h3 className="text-base font-semibold">Cost of the run</h3>
      <p className="text-sm text-text-muted">The run ended with the status: {report.status}</p>

      {showsMoney ? (
        <dl className="mt-2 flex flex-col gap-1 text-sm">
          {observed !== null ? (
            <div className="flex items-baseline gap-2">
              <dt className="text-text-muted">Observed cost</dt>
              <dd className="font-mono">
                <span className="text-text-subtle">USD</span> <span>{observed}</span>
              </dd>
            </div>
          ) : null}
          {estimated !== null ? (
            <div className="flex items-baseline gap-2">
              <dt className="text-text-muted">Estimated cost</dt>
              <dd className="font-mono">
                <span className="text-text-subtle">USD</span> <span>{estimated}</span>
              </dd>
            </div>
          ) : null}
        </dl>
      ) : (
        <p className="mt-2 text-sm text-text-muted">
          {report.price_known
            ? "The server sent no amount of money for this run."
            : "The price of the model is unknown, so no amount of money is shown."}
        </p>
      )}

      {report.cut_by ? (
        <p className="mt-2 text-sm text-text-muted">The run was cut by: {report.cut_by}</p>
      ) : null}
      {report.money_cap_authoritative ? (
        <p className="mt-2 text-sm text-text-muted">The cap of money is the one the server applied.</p>
      ) : null}
      {report.usage_without_reservation.length > 0 ? (
        <p className="mt-2 text-sm text-text-muted">
          The usage that was not reserved: {report.usage_without_reservation.join(", ")}
        </p>
      ) : null}
      <p className="mt-2 text-sm text-text-subtle">{report.note}</p>
    </div>
  );
}
