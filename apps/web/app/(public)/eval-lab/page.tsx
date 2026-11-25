/**
 * The Eval Lab of the repository: the numbers of the verification and of the evaluation, with their limits.
 *
 * Why this file exists: the repository publishes the numbers of the verification and of the evaluation, and a
 * visitor who opens the site has to find them with the dataset each one comes from and the restriction that
 * applies to it. A number without the dataset it was measured over is a number a reader cannot check, and a
 * number without the restriction that applies to it is a number that reads as a generalization when it is
 * not one.
 *
 * Why the page is a server component: the site is a static export, and the numbers of the Eval Lab are a file
 * of the repository, so the page reads them from the disk while the export is built. The page asks no
 * backend, it needs no key and no network, and it runs the same way for every visitor.
 *
 * Why the page shows the cases that failed: an aggregate hides the cases that failed, and a release that
 * publishes only the aggregate publishes a tendency and calls it a significance. The list of the cases that
 * failed names the claim and the evidence of each one, and the drill of each case opens with the keyboard as
 * well as with the pointer.
 */

import { Badge } from "@/components/ui/Badge";
import { readEvalLab } from "@/lib/eval-lab/catalog";

export const metadata = {
  title: "Eval Lab",
  description:
    "The numbers of the verification and of the evaluation of the repository, each one with the dataset it comes from and the restriction that applies to it.",
};

/**
 * The page of the Eval Lab.
 *
 * The page reads the numbers from the disk while the export is built, and every number names the dataset it
 * comes from and the restriction that applies to it.
 */
export default function EvalLabPage() {
  const lab = readEvalLab(process.cwd());

  return (
    <div className="mx-auto flex w-full max-w-content flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold">Eval Lab</h1>
        <p className="max-w-2xl text-text-muted">
          The numbers of the verification and of the evaluation of the repository, each one with the dataset it
          comes from and the restriction that applies to it. The cases that failed are listed with the claim
          and the evidence of each one.
        </p>
      </header>

      <section aria-labelledby="eval-lab-verification" className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold" id="eval-lab-verification">
          The verification
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{lab.verification.dataset_id}</Badge>
          <Badge tone={lab.verification.role === "held_out" ? "accent" : "neutral"}>{lab.verification.role}</Badge>
        </div>
        <p className="text-sm text-text-muted">
          The accuracy of the verifier over {lab.verification.dataset_id} is {lab.verification.accuracy} (
          {lab.verification.correct} of {lab.verification.cases} cases, denominator {lab.verification.denominator}).
        </p>
        <p className="text-sm text-text-subtle">{lab.verification.restriction}.</p>
      </section>

      <section aria-labelledby="eval-lab-confusion" className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold" id="eval-lab-confusion">
          The confusion matrix of the verifier
        </h2>
        <p className="text-sm text-text-subtle">
          The rows are the labels of the reader and the columns are the labels of the verifier, over a
          denominator of {lab.confusion_matrix.denominator} cases. A missing model is not a pass: a case whose
          verification is unavailable is a case without a verdict.
        </p>
        <table className="border-collapse text-sm">
          <caption className="sr-only">
            The confusion matrix of the verifier over {lab.confusion_matrix.denominator} cases
          </caption>
          <thead>
            <tr>
              <th className="border border-border p-2 text-left">reader \ verifier</th>
              {lab.confusion_matrix.labels.map((label) => (
                <th className="border border-border p-2 text-left" key={label}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {lab.confusion_matrix.labels.map((row) => (
              <tr key={row}>
                <th className="border border-border p-2 text-left">{row}</th>
                {lab.confusion_matrix.labels.map((column) => (
                  <td className="border border-border p-2" key={column}>
                    {lab.confusion_matrix.counts[row]?.[column] ?? 0}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section aria-labelledby="eval-lab-evaluation" className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold" id="eval-lab-evaluation">
          The evaluation of the agent
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{lab.evaluation.dataset_id}</Badge>
          <Badge tone={lab.evaluation.role === "held_out" ? "accent" : "neutral"}>{lab.evaluation.role}</Badge>
        </div>
        <p className="text-sm text-text-muted">
          The mean of the correctness of the agent over {lab.evaluation.dataset_id} is{" "}
          {lab.evaluation.correctness_mean} (denominator {lab.evaluation.denominator} cases,{" "}
          {lab.evaluation.repeats} runs of each case). The correctness of the agent and the accuracy of the
          verifier are two different measurements over two different sets.
        </p>
        <p className="text-sm text-text-subtle">{lab.evaluation.restriction}.</p>
      </section>

      <section aria-labelledby="eval-lab-failed" className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold" id="eval-lab-failed">
          The cases that failed
        </h2>
        <p className="text-sm text-text-subtle">
          {lab.failed_cases.length} cases failed, with the claim and the evidence of each one. Open a case to
          read it.
        </p>
        <ul className="flex flex-col gap-2">
          {lab.failed_cases.map((failed) => (
            <li key={`${failed.kind}-${failed.id}`}>
              <details className="rounded-lg border border-border p-4">
                <summary className="cursor-pointer">
                  <span className="font-semibold">
                    {failed.id} ({failed.kind}, {failed.set_name})
                  </span>{" "}
                  <span className="text-sm text-text-muted">{failed.outcome}</span>
                </summary>
                <dl className="mt-2 flex flex-col gap-1 text-sm">
                  <div>
                    <dt className="text-text-subtle">The claim</dt>
                    <dd>{failed.claim}</dd>
                  </div>
                  {failed.evidence ? (
                    <div>
                      <dt className="text-text-subtle">The evidence</dt>
                      <dd>{failed.evidence}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt className="text-text-subtle">The expected verdict</dt>
                    <dd>{failed.expected}</dd>
                  </div>
                  <div>
                    <dt className="text-text-subtle">The verdict that came out</dt>
                    <dd>{failed.got}</dd>
                  </div>
                </dl>
              </details>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="eval-lab-notes" className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold" id="eval-lab-notes">
          The notes of the numbers
        </h2>
        <ul className="flex list-disc flex-col gap-1 pl-6 text-sm text-text-muted">
          {lab.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
