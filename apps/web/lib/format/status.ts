/**
 * The mapping of the words of the domain to the words of the reader.
 *
 * Why this file exists: the recording speaks in the words of the domain, `idle`, `not_enough_evidence`, `ok`, and the
 * reader needs a label and a tone. The mapping lives in one place so that the same word always gets the same label,
 * and so that no component of the interface invents a tone on its own.
 *
 * A word the mapping does not know is shown as it was read, with the neutral tone. A tone never replaces a label: the
 * label always carries the meaning and the tone only carries the colour.
 */

/** The colour a label is painted with, without ever carrying the meaning on its own. */
export type StatusTone = "neutral" | "success" | "danger" | "warning" | "accent";

/** What the interface shows about a status: the words of the reader and the tone they are painted with. */
export interface StatusLabel {
  /** The label the reader sees. */
  readonly label: string;
  /** The tone the label is painted with. */
  readonly tone: StatusTone;
}

/** What the interface shows when the recording carries no status at all. */
const STATUS_UNAVAILABLE: StatusLabel = { label: "Not available", tone: "neutral" };

/** The words of the run, as the domain writes them. */
const RUN_STATUSES: Readonly<Record<string, StatusLabel>> = {
  idle: { label: "Idle", tone: "neutral" },
  running: { label: "Running", tone: "accent" },
  completed: { label: "Completed", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "warning" },
};

/** The words of the verdicts of the verifier, as the domain writes them. */
const VERDICTS: Readonly<Record<string, StatusLabel>> = {
  supported: { label: "Supported", tone: "success" },
  contradicted: { label: "Contradicted", tone: "danger" },
  not_enough_evidence: { label: "Not enough evidence", tone: "warning" },
  not_verified: { label: "Not verified", tone: "neutral" },
};

/** The words of the status of a tool call, as the capture writes them. */
const TOOL_STATUSES: Readonly<Record<string, StatusLabel>> = {
  ok: { label: "Succeeded", tone: "success" },
  success: { label: "Succeeded", tone: "success" },
  error: { label: "Failed", tone: "danger" },
  failed: { label: "Failed", tone: "danger" },
  timeout: { label: "Timed out", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "warning" },
  running: { label: "Running", tone: "accent" },
  pending: { label: "Pending", tone: "neutral" },
};

/**
 * Looks a word up in a mapping.
 *
 * A word that the mapping does not know is returned as it was read, with the neutral tone, because a tone that was
 * guessed is worse than no tone at all.
 */
function lookup(mapping: Readonly<Record<string, StatusLabel>>, word: string | null | undefined): StatusLabel {
  if (typeof word !== "string") {
    return STATUS_UNAVAILABLE;
  }
  const trimmed = word.trim();
  if (trimmed === "") {
    return STATUS_UNAVAILABLE;
  }
  const known = mapping[trimmed.toLowerCase()];
  if (known) {
    return known;
  }
  return { label: trimmed, tone: "neutral" };
}

/**
 * Renders the status of the run, for instance `running` or `failed`.
 *
 * The status of the run comes from the events of the recording, and the function only translates the word.
 */
export function formatRunStatus(status: string | null | undefined): StatusLabel {
  return lookup(RUN_STATUSES, status);
}

/**
 * Renders the verdict of the verifier about a claim.
 *
 * The verdict `not_verified` is the case where the verifier itself was unavailable, which is not a verdict about the
 * claim, and it gets the neutral tone.
 */
export function formatVerdict(label: string | null | undefined): StatusLabel {
  return lookup(VERDICTS, label);
}

/**
 * Renders the status of a tool call, as the capture recorded it.
 *
 * The capture is free to record any word, so a word the mapping does not know is shown as it was read.
 */
export function formatToolStatus(status: string | null | undefined): StatusLabel {
  return lookup(TOOL_STATUSES, status);
}

/** Every symbol this module exports, so that a reader sees the whole surface of the mapping at once. */
export const __all__ = [
  "StatusTone",
  "StatusLabel",
  "formatRunStatus",
  "formatVerdict",
  "formatToolStatus",
] as const;
