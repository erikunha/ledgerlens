/**
 * The reader of the published Eval Lab of the repository.
 *
 * Why this file exists: the route of the Eval Lab is a server component of a static export, so it has to read
 * the numbers while the export is built. The repository publishes the numbers in one place only,
 * `site/eval/index.json`, and the build copies it into `apps/web/public/eval`, where the site serves it.
 *
 * Why the reader looks in two places: the copy is the file the site serves, so it is the first place to look,
 * and the published source is the fallback. A reader that only knows the copy depends on the order of the
 * steps of the build, and a unit test that runs before the copy exists would see no numbers at all.
 *
 * Why the failure is loud: a file that cannot be read stops the build with a reason a reader can act on. It
 * never becomes a page with no numbers, because a page with no numbers is a page that says nothing.
 */

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

/** The number of the verification or of the evaluation, with the dataset it comes from and its restriction. */
export interface LabNumber {
  readonly dataset_id: string;
  readonly role: string;
  readonly restriction: string;
  readonly denominator: number;
}

/** The number of the verification, with the accuracy and the counts. */
export interface LabVerification extends LabNumber {
  readonly accuracy: string;
  readonly correct: number;
  readonly cases: number;
}

/** The number of the evaluation of the agent, with the mean of the correctness and the repeats. */
export interface LabEvaluation extends LabNumber {
  readonly correctness_mean: string;
  readonly repeats: number;
}

/** One row of the confusion matrix of the verifier: the counts of one label of the reader over the verifier. */
export interface LabConfusionMatrix {
  readonly rows: string;
  readonly columns: string;
  readonly labels: readonly string[];
  readonly counts: Readonly<Record<string, Readonly<Record<string, number>>>>;
  readonly denominator: number;
}

/** One case that failed, with the claim and the evidence of the case. */
export interface LabFailedCase {
  readonly kind: string;
  readonly id: string;
  readonly set_name: string;
  readonly scenario?: string;
  readonly claim: string;
  readonly evidence: string;
  readonly expected: string;
  readonly got: string;
  readonly outcome: string;
}

/** The Eval Lab of the repository, as the export of the repository publishes it. */
export interface EvalLab {
  readonly verification: LabVerification;
  readonly confusion_matrix: LabConfusionMatrix;
  readonly evaluation: LabEvaluation;
  readonly failed_cases: readonly LabFailedCase[];
  readonly notes: readonly string[];
}

/**
 * The places where the Eval Lab can be, in the order they are looked for.
 *
 * Why the first place is the copy: the site serves that file, so the export has to be built from the very
 * file that the visitor will read. Why the second place is the published source: the repository publishes the
 * numbers in `site/eval`, and the copy is made from it.
 */
export function evalLabCandidates(root: string = process.cwd()): string[] {
  return [
    path.join(root, "public", "eval", "index.json"),
    path.join(root, "..", "..", "site", "eval", "index.json"),
  ];
}

/**
 * The Eval Lab of the repository, read from the disk.
 *
 * The reader refuses a file that is not there and a file whose shape is not the shape of the export, because
 * a page of numbers a reader cannot trust is a page that stops the build, and never a page with no numbers.
 */
export function readEvalLab(root: string = process.cwd()): EvalLab {
  for (const candidate of evalLabCandidates(root)) {
    if (!existsSync(candidate)) {
      continue;
    }
    const data = JSON.parse(readFileSync(candidate, "utf8")) as Partial<EvalLab>;
    if (!data.verification || !data.evaluation || !data.confusion_matrix || !Array.isArray(data.failed_cases)) {
      throw new Error(`the eval lab at ${candidate} does not hold the numbers of the export`);
    }
    return data as EvalLab;
  }
  throw new Error("the published eval lab was not found on the disk of the repository");
}
