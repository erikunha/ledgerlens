/**
 * The test of the reader and of the page of the Eval Lab.
 *
 * Why this test exists: the page of the Eval Lab shows the numbers of the verification and of the evaluation,
 * each one with the dataset it comes from and the restriction that applies to it, the confusion matrix of the
 * verifier with its denominator and the list of the cases that failed. A page that shows a number without its
 * dataset, or a confusion matrix without its denominator, is a page that lies about the numbers.
 *
 * Every case runs with no key and no network: the numbers of the case are the numbers the repository
 * publishes, read from the disk of the repository.
 */

import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import EvalLabPage from "@/app/(public)/eval-lab/page";
import { evalLabCandidates, readEvalLab } from "@/lib/eval-lab/catalog";

describe("the reader of the eval lab", () => {
  it("finds the numbers the repository publishes", () => {
    const lab = readEvalLab(process.cwd());

    expect(lab.verification.dataset_id).toBeTruthy();
    expect(lab.verification.denominator).toBeGreaterThan(0);
    expect(lab.evaluation.dataset_id).toBeTruthy();
    expect(lab.evaluation.denominator).toBeGreaterThan(0);
    expect(lab.confusion_matrix.denominator).toBeGreaterThan(0);
    expect(lab.failed_cases.length).toBeGreaterThan(0);
    expect(lab.notes.length).toBeGreaterThan(0);
  });

  it("looks in the copy of the build first and in the published source after", () => {
    const candidates = evalLabCandidates(process.cwd());

    expect(candidates[0]).toContain(join("public", "eval", "index.json"));
    expect(candidates[1]).toContain(join("site", "eval", "index.json"));
  });

  it("refuses a root with no numbers, and never becomes a page with no numbers", () => {
    const empty = mkdtempSync(join(tmpdir(), "eval-lab-"));

    expect(() => readEvalLab(empty)).toThrow(/not found/);
  });
});

describe("the page of the eval lab", () => {
  it("shows the numbers of the verification and of the evaluation with the dataset and the restriction", () => {
    const lab = readEvalLab(process.cwd());
    render(<EvalLabPage />);

    expect(screen.getByRole("heading", { level: 1, name: "Eval Lab" })).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`accuracy of the verifier over ${lab.verification.dataset_id}`)),
    ).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`correctness of the agent over ${lab.evaluation.dataset_id}`)),
    ).toBeInTheDocument();
    expect(screen.getAllByText(lab.verification.restriction + ".").length).toBeGreaterThan(0);
    expect(screen.getAllByText(lab.evaluation.restriction + ".").length).toBeGreaterThan(0);
  });

  it("shows the confusion matrix with its denominator and the note of the missing model", () => {
    const lab = readEvalLab(process.cwd());
    render(<EvalLabPage />);

    expect(
      screen.getByRole("heading", { name: "The confusion matrix of the verifier" }),
    ).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`denominator of ${lab.confusion_matrix.denominator}`))).toBeInTheDocument();
    expect(screen.getByText(/A missing model is not a pass/)).toBeInTheDocument();
  });

  it("lists the cases that failed, with the claim and the evidence of each one", () => {
    const lab = readEvalLab(process.cwd());
    render(<EvalLabPage />);

    expect(screen.getByRole("heading", { name: "The cases that failed" })).toBeInTheDocument();
    for (const failed of lab.failed_cases.slice(0, 5)) {
      expect(screen.getByText(new RegExp(failed.id))).toBeInTheDocument();
    }
  });
});
