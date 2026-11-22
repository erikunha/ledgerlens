/**
 * The test of the mapping of the words of the domain to the words of the reader.
 *
 * Why this test exists: the recording speaks in the words of the domain, `idle`, `not_enough_evidence`, `ok`, and the
 * reader needs a label and a tone. The mapping lives in one place, so that the same word always gets the same label.
 * A word the mapping knows gets the word of the reader and the tone that goes with it, and a word the mapping does not
 * know is shown as it was read, with the neutral tone. A tone never replaces a label.
 *
 * Every case runs with no key and no network: the mapping is a pure function of the word it is given.
 */

import { describe, expect, it } from "vitest";

import { formatRunStatus, formatToolStatus, formatVerdict } from "@/lib/format/status";

describe("the mapping of the statuses", () => {
  it("maps the statuses of the run to the words of the reader and to their tone", () => {
    // It proves that each status of the run carries the word of the reader and the tone that goes with it.
    expect(formatRunStatus("idle")).toEqual({ label: "Idle", tone: "neutral" });
    expect(formatRunStatus("running")).toEqual({ label: "Running", tone: "accent" });
    expect(formatRunStatus("completed")).toEqual({ label: "Completed", tone: "success" });
    expect(formatRunStatus("failed")).toEqual({ label: "Failed", tone: "danger" });
    expect(formatRunStatus("cancelled")).toEqual({ label: "Cancelled", tone: "warning" });
  });

  it("shows a word the mapping does not know as it was read, with the neutral tone", () => {
    // It proves that the interface never guesses a tone, and that a newer bundle does not break an older page. The word
    // is not capitalised, because it was not read from the mapping.
    expect(formatRunStatus("something new")).toEqual({ label: "something new", tone: "neutral" });
  });

  it("says that the status is not available when the recording carries none", () => {
    // It proves that a missing status is rendered as unavailable and never as a status that was invented.
    expect(formatRunStatus(null)).toEqual({ label: "Not available", tone: "neutral" });
  });

  it("maps the verdicts of the verifier to the words of the reader and to their tone", () => {
    // It proves that the verdicts of the domain keep their meaning and get the tone that goes with it.
    expect(formatVerdict("supported")).toEqual({ label: "Supported", tone: "success" });
    expect(formatVerdict("contradicted")).toEqual({ label: "Contradicted", tone: "danger" });
    expect(formatVerdict("not_enough_evidence")).toEqual({ label: "Not enough evidence", tone: "warning" });
    expect(formatVerdict("not_verified")).toEqual({ label: "Not verified", tone: "neutral" });
  });

  it("shows a verdict the mapping does not know as it was read, with the neutral tone", () => {
    // It proves that a verdict of a later export is shown as it is and never as a verdict that was guessed.
    expect(formatVerdict("something new")).toEqual({ label: "something new", tone: "neutral" });
  });

  it("maps the status of a tool call to the words of the reader and to their tone", () => {
    // It proves that the status the capture recorded keeps its meaning and gets the tone that goes with it.
    expect(formatToolStatus("ok")).toEqual({ label: "Succeeded", tone: "success" });
    expect(formatToolStatus("error")).toEqual({ label: "Failed", tone: "danger" });
  });

  it("shows a status of a tool call the mapping does not know as it was read, with the neutral tone", () => {
    // It proves that the capture is free to record any word and that the interface never guesses a tone for it.
    expect(formatToolStatus("something new")).toEqual({ label: "something new", tone: "neutral" });
  });

  it("says that the status of a tool call is not available when the recording carries none", () => {
    // It proves that a missing status is rendered as unavailable and never as a status that was invented.
    expect(formatToolStatus(null)).toEqual({ label: "Not available", tone: "neutral" });
  });

  it("never replaces the label with the tone", () => {
    // It proves that the label always carries the meaning and that the tone only carries the colour. Every mapped word
    // has a label of its own, and no label is empty.
    for (const status of ["idle", "running", "completed", "failed", "cancelled"]) {
      expect(formatRunStatus(status).label.length).toBeGreaterThan(0);
    }
    for (const verdict of ["supported", "contradicted", "not_enough_evidence", "not_verified"]) {
      expect(formatVerdict(verdict).label.length).toBeGreaterThan(0);
    }
    for (const status of ["ok", "error"]) {
      expect(formatToolStatus(status).label.length).toBeGreaterThan(0);
    }
    expect(formatRunStatus("idle").label).not.toBe(formatRunStatus("idle").tone);
    expect(formatVerdict("supported").label).not.toBe(formatVerdict("supported").tone);
    expect(formatToolStatus("ok").label).not.toBe(formatToolStatus("ok").tone);
  });
});
