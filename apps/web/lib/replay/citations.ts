/**
 * The resolver of the citations of the answer.
 *
 * Why this file exists: the answer of the run cites the pieces of evidence it was built from, and
 * the visitor who clicks a citation reads the exact line behind it. The citation names one piece of
 * evidence, so the resolution is an exact match and never a search: a resolver that guessed the
 * nearest piece would show a line the answer did not cite, and a line the answer did not cite is a
 * line that proves nothing.
 *
 * Why the refusal is stated: a citation whose source is absent is a fact about the recording, and
 * the reader says it in words. A refusal that named nothing would leave the visitor to guess
 * whether the citation was misread or the source is missing.
 *
 * Why the money stays text: the rows of the ledger carry the amounts as the decimal text of the
 * ledger, and the reader never parses them into a float. A float is a rounded number, and the
 * rounded number of a row is not the number the run read.
 */

import type { LedgerArtifact, LedgerReadRow } from "@/lib/api/schemas";
import type { EvidenceSummary } from "@/lib/replay/selectors";

/** The resolution of a citation of the answer. */
export interface CitationResolution {
  /** The citation, as the answer wrote it. */
  readonly citation: string;
  /** The evidence the citation names, or null when the recording carries no such evidence. */
  readonly evidence: EvidenceSummary | null;
  /** The reason of the refusal, when the citation names no evidence of the recording. */
  readonly refusal: string | null;
}

/**
 * Resolves a citation to the piece of evidence it names.
 *
 * Why the match is exact: the citation is the identifier of the evidence, and an identifier is the
 * name of one piece and not a description of it. A citation that names nothing the recording
 * carries is refused with the reason, and it never resolves to the piece that happens to be near.
 */
export function resolveCitation(
  citation: string,
  evidence: readonly EvidenceSummary[],
): CitationResolution {
  const named = citation.trim();
  const found = evidence.find((item) => item.evidenceId === named) ?? null;
  if (found === null) {
    return {
      citation: named,
      evidence: null,
      refusal: `the answer cites ${named}, and the recording carries no evidence with that identifier`,
    };
  }
  return { citation: named, evidence: found, refusal: null };
}

/**
 * Reads the citations of a text of the answer, in the order they appear.
 *
 * Why the reader splits the brackets: the answer cites with brackets, and one bracket may hold more
 * than one citation, as in `[sql:1, calc:1]`. The citations come out in the order the answer wrote
 * them, because the order of the citations is the order of the reading.
 */
export function citationsOf(text: string): string[] {
  const citations: string[] = [];
  for (const match of text.matchAll(/\[([^\]]+)\]/g)) {
    const inside = match[1] ?? "";
    for (const part of inside.split(",")) {
      const named = part.trim();
      if (named.length > 0) {
        citations.push(named);
      }
    }
  }
  return citations;
}

/**
 * Reads the rows of the ledger behind a citation of a read.
 *
 * Why the rows come from the artifact of the ledger: the artifact is the file the site publishes
 * with the rows the run read, and the citation of a read names the read of the artifact. The rows
 * come back exactly as the artifact carries them, with the amounts as the decimal text of the
 * ledger, so the reader that shows the line behind a citation shows the number the run read and
 * never a rounded one.
 */
export function citedRows(citation: string, ledger: LedgerArtifact | null): readonly LedgerReadRow[] {
  if (ledger === null) {
    return [];
  }
  const named = citation.trim();
  for (const account of ledger.accounts) {
    for (const read of account.reads) {
      if (read.evidence_id === named) {
        return read.rows;
      }
    }
  }
  return [];
}

/** Every symbol this module exports, so that a reader sees the whole surface of the resolver at once. */
export const __all__ = ["CitationResolution", "resolveCitation", "citationsOf", "citedRows"] as const;
