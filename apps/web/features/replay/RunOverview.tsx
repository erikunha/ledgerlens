/**
 * The overview of a recorded run.
 *
 * Why this file exists: a reader has to know what the recording is before they read any of it.
 * The overview says the mode of the capture, the scenario, the run and the kind of the capture
 * in the words of the artifact itself, and it shows the note of the manifest word for word, so
 * that a recorded run is never presented as a live one (ADR-043).
 *
 * Every value here is read from the manifest or from the card of the scenario. The overview never
 * adds a fact of its own, and a value the artifact does not carry is shown as not available.
 */

import type { ReactElement } from "react";

import { Badge } from "@/components/ui/Badge";
import type { ReplayBundleManifest, ScenarioIndexEntry } from "@/lib/api/schemas";
import { formatObservedMoment } from "@/lib/format/duration";


/**
 * The props of the overview.
 *
 * Why the overview takes the card and the manifest: the card says what the scenario is and the
 * manifest says what the capture was, and the two together are everything the overview shows.
 */
export interface RunOverviewProps {
  /** The card of the scenario in the catalog of the site. */
  readonly scenario: ScenarioIndexEntry;
  /** The manifest of the bundle of the scenario. */
  readonly manifest: ReplayBundleManifest;
}

/** What the overview shows when the artifact carries nothing to show. */
const NOT_AVAILABLE = "Not available";

/**
 * The overview of a recorded run.
 *
 * The badges carry the raw words of the manifest, because the raw word is what the artifact says.
 * The note is shown word for word, because a note that was shortened is a note that was changed.
 */
export function RunOverview({ scenario, manifest }: RunOverviewProps): ReactElement {
  const concepts = scenario.concepts ?? [];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>mode: {manifest.mode}</Badge>
        <Badge>scenario: {manifest.scenario}</Badge>
        <Badge>run: {manifest.run_id}</Badge>
        {manifest.capture_kind ? <Badge>capture: {manifest.capture_kind}</Badge> : null}
      </div>

      <p className="text-sm text-text-subtle">{manifest.note}</p>

      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="flex flex-col gap-1">
          <dt className="text-xs font-medium text-text-subtle">Origin of the data</dt>
          <dd className="text-sm text-foreground">{scenario.data_origin ?? NOT_AVAILABLE}</dd>
        </div>
        <div className="flex flex-col gap-1">
          <dt className="text-xs font-medium text-text-subtle">Concepts of the scenario</dt>
          <dd className="text-sm text-foreground">
            {concepts.length > 0 ? concepts.join(", ") : NOT_AVAILABLE}
          </dd>
        </div>
        <div className="flex flex-col gap-1">
          <dt className="text-xs font-medium text-text-subtle">Status of the scenario</dt>
          <dd className="text-sm text-foreground">{scenario.status ?? NOT_AVAILABLE}</dd>
        </div>
        <div className="flex flex-col gap-1">
          <dt className="text-xs font-medium text-text-subtle">Moment of the capture</dt>
          <dd className="text-sm text-foreground">
            <time dateTime={manifest.recorded_at ?? manifest.created_at}>
              {formatObservedMoment(manifest.recorded_at ?? manifest.created_at)}
            </time>
          </dd>
        </div>
        <div className="flex flex-col gap-1">
          <dt className="text-xs font-medium text-text-subtle">Events of the recording</dt>
          <dd className="text-sm text-foreground">{manifest.events}</dd>
        </div>
        <div className="flex flex-col gap-1">
          <dt className="text-xs font-medium text-text-subtle">Profile of the model</dt>
          <dd className="text-sm text-foreground">{manifest.model_profile ?? NOT_AVAILABLE}</dd>
        </div>
      </dl>
    </div>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the overview at once. */
export const __all__ = ["RunOverviewProps", "RunOverview"] as const;
