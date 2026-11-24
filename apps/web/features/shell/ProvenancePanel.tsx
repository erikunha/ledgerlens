/**
 * The panel of the provenance of a recording.
 *
 * Why this file exists: a recording that says nothing about where it came from is a recording a
 * reader has to take on faith, and a recording that says more than it knows is worse. The panel
 * shows what the artifact publishes: the digest of the bundle, the mode and the kind of the
 * capture, the moment of the capture, the hashes, the files and the freshness of the snapshot.
 *
 * Why the panel never invents anything: a digest that was not read is shown as not available, and
 * the freshness is shown with the sentence that explains it, so the panel never calls a bundle
 * fresh or stale on a comparison it did not make (ADR-043).
 *
 * Why the panel shows the state of the integrity: the absence of the Web Crypto is not a refusal,
 * so a bundle that was accepted without a check has to say so. The panel never shows a bundle as
 * verified when it was not, and never shows it as unchecked when it was.
 *
 * Why the heading of the panel is at the third level: the panel is a section of the replay, and
 * that section sits under the title of the recording. The heading of the panel is the heading of
 * the section, and the heading of the files of the bundle is one level below it, so the outline of
 * the page mirrors the sections a visitor walks through.
 */

import type { ReactElement } from "react";

import { formatDigest, slotLabel, type ProvenanceSummary } from "@/lib/replay/provenance";

/**
 * The props of the panel of the provenance.
 *
 * Why the summary is the whole of the props: the summary is what the library of the provenance
 * read from the artifact, and the panel only shows it.
 */
export interface ProvenancePanelProps {
  /** What the artifact says about the recording. */
  readonly summary: ProvenanceSummary;
}

/** What the panel shows when the artifact carries nothing to show. */
const NOT_AVAILABLE = "Not available";

/** One row of the panel: a name and the value that was read. */
function Row(props: { readonly name: string; readonly value: ReactElement | string }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-xs font-medium text-text-subtle">{props.name}</dt>
      <dd className="text-sm text-foreground">{props.value}</dd>
    </div>
  );
}

/**
 * The panel of the provenance of a recording.
 *
 * Every value of the panel comes from the summary, which comes from the artifact. The panel adds
 * no digest, no hash and no verdict of its own.
 */
export function ProvenancePanel(props: ProvenancePanelProps): ReactElement {
  const summary = props.summary;
  const files = Object.entries(summary.files);

  return (
    <section
      aria-label="The provenance of the recording"
      className="rounded-lg border border-line bg-background"
    >
      <div className="border-b border-line px-4 py-3">
        <h3 className="text-base font-semibold">The provenance of the recording</h3>
        <p className="text-sm text-text-muted">
          Everything on this panel was read from the published artifact of the recording.
        </p>
      </div>

      <dl className="grid gap-4 px-4 py-4 sm:grid-cols-2">
        <Row name="Digest of the bundle" value={formatDigest(summary.bundleDigest)} />
        {summary.bundleDigest ? (
          <Row
            name="The digest as it was published"
            value={<span className="break-all font-mono text-xs">{summary.bundleDigest}</span>}
          />
        ) : null}
        <Row name="Mode of the recording" value={summary.modeLabel} />
        <Row name="Kind of the capture" value={summary.captureLabel} />
        <Row
          name="Moment of the capture"
          value={
            summary.recordedAt ? (
              <time dateTime={summary.recordedAt}>{summary.recordedAt}</time>
            ) : (
              NOT_AVAILABLE
            )
          }
        />
        <Row
          name="Hash of the snapshot the run read"
          value={
            summary.snapshotSha256 ? (
              <span className="break-all font-mono text-xs">{summary.snapshotSha256}</span>
            ) : (
              NOT_AVAILABLE
            )
          }
        />
        <Row
          name="Hash of the code that produced the run"
          value={
            summary.codeSha ? (
              <span className="break-all font-mono text-xs">{summary.codeSha}</span>
            ) : (
              NOT_AVAILABLE
            )
          }
        />
        <Row name="Profile of the model" value={summary.modelProfile ?? NOT_AVAILABLE} />
        <Row name="Version of the policy" value={summary.policyVersion ?? NOT_AVAILABLE} />
        <Row name="Freshness of the snapshot" value={summary.freshness} />
        <Row name="Integrity of the bundle" value={summary.integrity} />
      </dl>

      {Object.keys(summary.modelProfiles).length > 0 ? (
        <div className="border-t border-line px-4 py-3">
          <h4 className="text-xs font-medium text-text-subtle">The model of each task of the run</h4>
          <dl className="mt-2 grid gap-3 sm:grid-cols-2">
            {Object.entries(summary.modelProfiles).map(([slot, model]) => (
              <div key={slot} className="flex flex-col gap-1">
                <dt className="text-xs font-medium text-text-subtle">{slotLabel(slot)}</dt>
                <dd className="text-sm text-foreground">{model}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}

      <div className="border-t border-line px-4 py-3">
        <p className="text-sm text-text-muted">{summary.freshnessReason}</p>
        <p className="text-sm text-text-muted">{summary.integrityReason}</p>
      </div>

      {files.length > 0 ? (
        <div className="border-t border-line px-4 py-3">
          <h4 className="text-sm font-semibold">The files of the bundle</h4>
          <ul className="mt-2 flex flex-col gap-1">
            {files.map(([name, digest]) => (
              <li key={name} className="flex flex-col gap-0.5">
                <span className="text-xs text-text-subtle">{name}</span>
                <span className="break-all font-mono text-xs">{digest}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the panel at once. */
export const __all__ = ["ProvenancePanelProps", "ProvenancePanel"] as const;
