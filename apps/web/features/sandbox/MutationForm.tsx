"use client";

/**
 * The form of the mutation of the sandbox.
 *
 * Why this file exists: the visitor of the sandbox builds a typed command, asks the server what
 * it WOULD do and commits it only when the server says that the command is valid. The form
 * offers the five kinds of the catalog of the mutations of the domain, and never a kind of its
 * own, so the visitor never sends a command the server does not know.
 *
 * Why the form refuses to send a command with an empty required field: the server would refuse it
 * anyway, and a refusal of the local interface is not a refusal of the server and it never wears
 * its clothes. The form names the empty field, so the visitor knows what to fill.
 *
 * Why the form never calculates: the values before and after of the preview are the strings of the
 * server, and the form renders them as they were sent. The one number the form builds is the
 * count of seconds of the duplicate charge, because the contract of the command declares that
 * field as a number and a count of seconds is not money (ADR-044).
 *
 * Why the commit is offered only after a valid preview: the preview is the promise of the
 * feature. The control is never `disabled`: it carries `aria-disabled` and points at its reason
 * with `aria-describedby`, so that a visitor who pressed it and nothing happened gets an answer.
 */

import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactElement } from "react";

import { Button } from "@/components/ui/Button";
import {
  MUTATION_KINDS,
  type DeadlineCommand,
  type DuplicatePaymentCommand,
  type FxAdjustmentCommand,
  type FxOutageCommand,
  type SandboxCommand,
  type SandboxCommandKind,
  type UntrustedNoteCommand,
} from "@/features/sandbox/types";
import type { BranchState } from "@/features/sandbox/useBranch";
import { MONEY_UNAVAILABLE } from "@/lib/format/money";

/** The identifier of the reason of the local refusal of the form. */
const PROBLEM_ID = "sandbox-form-problem";

/** The identifier of the reason of the commit, so that the control points at it. */
const COMMIT_REASON_ID = "sandbox-commit-reason";

/** The sentence that says why the preview would do nothing when there is no branch. */
const NO_BRANCH_REASON = "There is no branch to preview, so open a scenario first.";

/** The sentence that says why the commit is not offered when the caller gave no reason. */
const NO_COMMIT_REASON = "The command cannot be committed right now.";

/**
 * The sentence that says why the commit is not offered when the command of the form is not the
 * command that was previewed.
 *
 * Why the form says it in its own words: a refusal of the local interface is not a refusal of the
 * server and it never wears its clothes.
 */
const CHANGED_REASON = "The command changed since the preview, so preview the command again.";

/**
 * The kind of a field of the form.
 *
 * Why the kinds are named: the checkbox of the outage of the tool carries a value that the other
 * fields do not, and the field of the count of seconds carries a number.
 */
type FieldKind = "text" | "number" | "checkbox";

/** One field of the form of one kind of the command. */
interface FieldSpec {
  /** The name of the field in the data of the command. */
  readonly name: string;
  /** The label the visitor reads. */
  readonly label: string;
  /** The kind of the field. */
  readonly kind: FieldKind;
  /** Whether the command cannot be sent without it. */
  readonly required: boolean;
  /** The sentence that tells the visitor what the server expects. */
  readonly hint: string;
}

/** The hint of the currency of the record, the same field in three kinds of the command. */
const CURRENCY_HINT = "The three letters of the currency of the record, when the visitor knows it.";

/**
 * The fields of each kind of the command.
 *
 * Why the fields live here and not in the server: the published schema of the command declares
 * the fields of each kind, and the form shows exactly them, so the visitor sees the body the
 * server is going to read.
 */
const FIELDS: Readonly<Record<SandboxCommandKind, readonly FieldSpec[]>> = {
  "refund.apply_fx_adjustment": [
    {
      name: "refund_id",
      label: "Identifier of the refund",
      kind: "text",
      required: true,
      hint: "The shape R followed by four digits.",
    },
    {
      name: "applied_rate",
      label: "Rate applied to the refund",
      kind: "text",
      required: true,
      hint: "A decimal text with at most eight decimals.",
    },
    {
      name: "effective_at",
      label: "Moment the adjustment takes effect",
      kind: "text",
      required: true,
      hint: "An ISO 8601 text with a time zone.",
    },
    {
      name: "currency",
      label: "Currency of the record",
      kind: "text",
      required: false,
      hint: CURRENCY_HINT,
    },
  ],
  "payment.simulate_duplicate": [
    {
      name: "transaction_id",
      label: "Identifier of the transaction",
      kind: "text",
      required: true,
      hint: "The shape TX followed by four digits.",
    },
    {
      name: "elapsed_seconds",
      label: "Seconds since the first charge",
      kind: "number",
      required: true,
      hint: "A whole number of seconds between 1 and 300.",
    },
    {
      name: "currency",
      label: "Currency of the record",
      kind: "text",
      required: false,
      hint: CURRENCY_HINT,
    },
  ],
  "chargeback.change_deadline": [
    {
      name: "chargeback_id",
      label: "Identifier of the chargeback",
      kind: "text",
      required: true,
      hint: "The shape CB followed by four digits.",
    },
    {
      name: "new_deadline",
      label: "New deadline",
      kind: "text",
      required: true,
      hint: "A day of the calendar, in the shape YYYY-MM-DD.",
    },
    {
      name: "currency",
      label: "Currency of the record",
      kind: "text",
      required: false,
      hint: CURRENCY_HINT,
    },
  ],
  "tool.fx_outage": [
    {
      name: "enabled",
      label: "The tool of the rate is enabled",
      kind: "checkbox",
      required: true,
      hint: "The tool goes down when the box is empty.",
    },
    {
      name: "error_code",
      label: "Error code of the tool",
      kind: "text",
      required: true,
      hint: "The code the tool answers with while it is down: UPSTREAM_UNAVAILABLE.",
    },
  ],
  "record.inject_untrusted_note": [
    {
      name: "record_id",
      label: "Identifier of the record",
      kind: "text",
      required: true,
      hint: "The identifier of the record the note is injected on.",
    },
    {
      name: "text",
      label: "Text of the note",
      kind: "text",
      required: true,
      hint: "The text of the note.",
    },
  ],
};

/**
 * The fields of a kind of the command, with the value they start with.
 *
 * Why the outage of the tool starts with the tool up: the checkbox is a fact about the tool, and
 * a tool that is up is the state the branch is in before the command is sent.
 */
function defaultDraft(kind: SandboxCommandKind): Draft {
  if (kind === "tool.fx_outage") {
    return { enabled: "true" };
  }
  return {};
}

/**
 * The props of the form of the mutation.
 *
 * Why the state comes as a prop: the form reads the preview that waits for a commit and it never
 * owns the state of the branch. The hook of the branch owns it.
 */
export interface MutationFormProps {
  /** The state of the branch, as the hook of the branch holds it. */
  readonly state: BranchState;
  /** Whether the commit may be sent right now, as the hook of the branch says it. */
  readonly canCommit: boolean;
  /** The sentence that says why the commit may not be sent, as the hook of the branch wrote it. */
  readonly commitReason: string | null;
  /** Called with the command the visitor built, when every required field is filled. */
  readonly onPreview: (command: SandboxCommand) => void;
  /** Called when the visitor asks to commit the command that was previewed. */
  readonly onCommit: () => void;
}

/** The empty field of the form, before the visitor types anything. */
type Draft = Readonly<Record<string, string>>;

/** The local refusal of the form, with the field that caused it. */
interface FieldProblem {
  /** The name of the field that is empty or that does not hold what the server expects. */
  readonly name: string;
  /** The sentence that says what is wrong, with the name of the field in it. */
  readonly message: string;
}

/**
 * The identifier of the field of the form.
 *
 * Why the name of the kind is not in it: only the fields of the chosen kind are on the screen, so
 * the name of the field alone is enough to name it.
 */
function fieldId(name: string): string {
  return `sandbox-field-${name}`;
}

/**
 * The codes the published schema declares for the outage of the tool.
 *
 * Why the list is the enum of the schema: the schema `scenario-mutation.schema.json` declares the
 * field `error_code` with the single code `UPSTREAM_UNAVAILABLE`, and the form refuses any other
 * code in its own words.
 */
const FX_OUTAGE_ERROR_CODES: readonly FxOutageCommand["data"]["error_code"][] = [
  "UPSTREAM_UNAVAILABLE",
];

/**
 * Says whether a code is one of the codes the schema declares.
 *
 * Why the guard exists: the type of the field is the enum of the schema, and the form has to
 * narrow a text the visitor typed to that enum before it builds a body with it.
 */
function isFxOutageErrorCode(value: string): value is FxOutageCommand["data"]["error_code"] {
  return (FX_OUTAGE_ERROR_CODES as readonly string[]).includes(value);
}

/**
 * The smallest and the biggest count of seconds the published schema declares.
 *
 * Why the numbers are named: the schema declares the field `elapsed_seconds` as an integer
 * between 1 and 300, and the form refuses a count outside the range before the server does.
 */
const MIN_ELAPSED_SECONDS = 1;
const MAX_ELAPSED_SECONDS = 300;

/**
 * Says which field of the command cannot be sent, or `null` when the command can be sent.
 *
 * Why the form refuses the empty field and not the server: the server would refuse it too, and a
 * refusal of the interface is not a refusal of the server. The form names the field, because a
 * visitor who does not know which field is missing sends the same command again.
 */
function findProblem(kind: SandboxCommandKind, draft: Draft): FieldProblem | null {
  for (const field of FIELDS[kind]) {
    if (field.kind === "checkbox") {
      // A checkbox always carries a value: the tool is up or it is down.
      continue;
    }
    const raw = (draft[field.name] ?? "").trim();
    if (field.required && raw === "") {
      return { name: field.name, message: `The field "${field.label}" is required.` };
    }
    if (field.name === "elapsed_seconds" && raw !== "") {
      // The count of seconds is the one number of the form, and the contract wants a whole one
      // inside the range that the schema declares.
      const seconds = Number(raw);
      if (
        !Number.isInteger(seconds) ||
        seconds < MIN_ELAPSED_SECONDS ||
        seconds > MAX_ELAPSED_SECONDS
      ) {
        return {
          name: field.name,
          message: `The field "${field.label}" must be a whole number of seconds between ${MIN_ELAPSED_SECONDS} and ${MAX_ELAPSED_SECONDS}.`,
        };
      }
    }
    if (field.name === "error_code" && raw !== "" && !isFxOutageErrorCode(raw)) {
      // The contract declares one code for the outage of the tool, and the form refuses the others
      // before the server does.
      return {
        name: field.name,
        message: `The field "${field.label}" must be ${FX_OUTAGE_ERROR_CODES.join(", ")}.`,
      };
    }
  }
  return null;
}

/**
 * Builds the body of the command of the chosen kind.
 *
 * Why the body is built here and not in the server: the visitor has to see the body it sends,
 * and the commit sends the very body that the preview sent. A field the visitor left empty and
 * that the contract declares as optional is left out of the body, because a body with an empty
 * field is a body the server refuses.
 */
function buildCommand(
  kind: SandboxCommandKind,
  draft: Draft,
  reason: string,
): SandboxCommand {
  const read = (name: string): string => (draft[name] ?? "").trim();
  const note = reason.trim();

  switch (kind) {
    case "refund.apply_fx_adjustment": {
      const data: FxAdjustmentCommand["data"] = {
        refund_id: read("refund_id"),
        applied_rate: read("applied_rate"),
        effective_at: read("effective_at"),
      };
      const currency = read("currency");
      if (currency !== "") {
        data.currency = currency;
      }
      return note === "" ? { kind, data } : { kind, data, reason: note };
    }
    case "payment.simulate_duplicate": {
      const seconds = Number(read("elapsed_seconds"));
      const data: DuplicatePaymentCommand["data"] = {
        transaction_id: read("transaction_id"),
        // The form refuses a count outside the range of the schema before it gets here, so the
        // number is one of the ones the schema declares.
        elapsed_seconds: seconds as DuplicatePaymentCommand["data"]["elapsed_seconds"],
      };
      const currency = read("currency");
      if (currency !== "") {
        data.currency = currency;
      }
      return note === "" ? { kind, data } : { kind, data, reason: note };
    }
    case "chargeback.change_deadline": {
      const data: DeadlineCommand["data"] = {
        chargeback_id: read("chargeback_id"),
        new_deadline: read("new_deadline"),
      };
      const currency = read("currency");
      if (currency !== "") {
        data.currency = currency;
      }
      return note === "" ? { kind, data } : { kind, data, reason: note };
    }
    case "tool.fx_outage": {
      const code = read("error_code");
      if (!isFxOutageErrorCode(code)) {
        // The form refuses the command before this point, so the branch is unreachable. The form
        // refuses to build a body with a code the contract does not declare.
        throw new Error(`the error code ${code} is not part of the contract of the sandbox`);
      }
      const data: FxOutageCommand["data"] = {
        enabled: read("enabled") === "true",
        error_code: code,
      };
      return note === "" ? { kind, data } : { kind, data, reason: note };
    }
    case "record.inject_untrusted_note": {
      const data: UntrustedNoteCommand["data"] = {
        record_id: read("record_id"),
        text: read("text"),
      };
      return note === "" ? { kind, data } : { kind, data, reason: note };
    }
    default: {
      // The catalog is closed, so this branch is unreachable. The form refuses to build a body it
      // does not understand instead of sending a command the server does not know.
      throw new Error(`the kind ${kind} is not part of the catalog of the sandbox`);
    }
  }
}

/**
 * Says whether two commands are the same command.
 *
 * Why the comparison is here and not in the hook: the promise of the preview is about ONE command,
 * and the form is the only place that knows which command the visitor is about to send. The
 * comparison reads the kind, the reason and the fields of the data, and it never calculates
 * anything.
 */
function sameCommand(left: SandboxCommand, right: SandboxCommand): boolean {
  if (left.kind !== right.kind) {
    return false;
  }
  if ((left.reason ?? "") !== (right.reason ?? "")) {
    return false;
  }
  const leftData = Object.entries(left.data as Record<string, unknown>).sort(([first], [second]) =>
    first.localeCompare(second),
  );
  const rightData = Object.entries(right.data as Record<string, unknown>).sort(
    ([first], [second]) => first.localeCompare(second),
  );
  if (leftData.length !== rightData.length) {
    return false;
  }
  return leftData.every(
    ([name, value], index) => name === rightData[index]?.[0] && value === rightData[index]?.[1],
  );
}

/**
 * The form of the mutation of the sandbox.
 *
 * The form builds the body of the command, asks for the preview and offers the commit only after
 * a valid preview. It gives its acts back as callbacks and it never calls the backend by itself.
 */
export function MutationForm({
  state,
  canCommit,
  commitReason,
  onPreview,
  onCommit,
}: MutationFormProps): ReactElement {
  const firstKind = MUTATION_KINDS[0] ?? "refund.apply_fx_adjustment";
  const [kind, setKind] = useState<SandboxCommandKind>(firstKind);
  const [draft, setDraft] = useState<Draft>(() => defaultDraft(firstKind));
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<FieldProblem | null>(null);

  const hasBranch = state.branchId !== null;
  const preview = state.preview;
  const previewIsCurrent =
    preview !== null && preview.valid === true && preview.revision === state.revision;

  /**
   * The command the visitor is about to send, or `null` when the form cannot build one.
   *
   * Why the form rebuilds the command: the commit is offered only when the command of the form is
   * the command that was previewed. A change of the kind or of the fields changes the command, and
   * the preview of the previous command promises nothing about the new one.
   */
  const currentCommand = useMemo(() => {
    if (findProblem(kind, draft) !== null) {
      return null;
    }
    return buildCommand(kind, draft, reason);
  }, [kind, draft, reason]);

  const previewMatches =
    preview !== null && currentCommand !== null && sameCommand(currentCommand, preview.command);
  const commitAllowed = canCommit && previewIsCurrent && previewMatches;
  const commitReasonText = commitAllowed
    ? null
    : preview !== null && previewIsCurrent && !previewMatches
      ? CHANGED_REASON
      : (commitReason ?? NO_COMMIT_REASON);

  // The field that refused the command takes the focus, so that a visitor who pressed the button
  // and nothing happened lands on the field they have to fill.
  useEffect(() => {
    if (problem === null) {
      return;
    }
    const element = document.getElementById(fieldId(problem.name));
    element?.focus();
  }, [problem]);

  /** Applies what the visitor typed to one field. */
  function handleField(name: string, value: string): void {
    setDraft((previous) => ({ ...previous, [name]: value }));
    if (problem !== null && problem.name === name) {
      setProblem(null);
    }
  }

  /** Changes the kind of the command, and forgets the fields of the kind before it. */
  function handleKind(next: SandboxCommandKind): void {
    setKind(next);
    setDraft(defaultDraft(next));
    setProblem(null);
  }

  /** Asks the server what the command WOULD do, and refuses it here when a field is empty. */
  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!hasBranch) {
      return;
    }
    const found = findProblem(kind, draft);
    if (found !== null) {
      setProblem(found);
      return;
    }
    setProblem(null);
    onPreview(buildCommand(kind, draft, reason));
  }

  return (
    <form className="ll-sandbox-form flex flex-col gap-3" onSubmit={handleSubmit} noValidate>
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium" htmlFor="sandbox-kind">
          Kind of the mutation
        </label>
        <select
          id="sandbox-kind"
          className="rounded border border-line-strong bg-background px-2 py-1 text-sm"
          value={kind}
          onChange={(event) => handleKind(event.target.value as SandboxCommandKind)}
        >
          {MUTATION_KINDS.map((candidate) => (
            <option key={candidate} value={candidate}>
              {candidate}
            </option>
          ))}
        </select>
      </div>

      {FIELDS[kind].map((field) => {
        const id = fieldId(field.name);
        const hintId = `${id}-hint`;
        const describedBy = problem !== null && problem.name === field.name ? `${hintId} ${PROBLEM_ID}` : hintId;
        return (
          <div key={field.name} className="flex flex-col gap-1">
            {field.kind === "checkbox" ? (
              <label className="flex items-center gap-2 text-sm font-medium" htmlFor={id}>
                <input
                  id={id}
                  type="checkbox"
                  className="h-4 w-4 rounded border border-line-strong"
                  checked={(draft[field.name] ?? "") === "true"}
                  aria-describedby={describedBy}
                  onChange={(event) => handleField(field.name, event.target.checked ? "true" : "")}
                />
                {field.label}
              </label>
            ) : (
              <>
                <label className="text-sm font-medium" htmlFor={id}>
                  {field.label}
                  {field.required ? "" : " (optional)"}
                </label>
                <input
                  id={id}
                  type={field.kind === "number" ? "number" : "text"}
                  inputMode={field.kind === "number" ? "numeric" : undefined}
                  step={field.kind === "number" ? 1 : undefined}
                  className="rounded border border-line-strong bg-background px-2 py-1 text-sm"
                  value={draft[field.name] ?? ""}
                  aria-invalid={problem !== null && problem.name === field.name ? true : undefined}
                  aria-describedby={describedBy}
                  onChange={(event) => handleField(field.name, event.target.value)}
                />
              </>
            )}
            <p id={hintId} className="text-xs text-text-subtle">
              {field.hint}
            </p>
          </div>
        );
      })}

      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium" htmlFor="sandbox-reason">
          Reason of the visitor (optional)
        </label>
        <textarea
          id="sandbox-reason"
          className="rounded border border-line-strong bg-background px-2 py-1 text-sm"
          rows={2}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </div>

      {problem === null ? null : (
        <p id={PROBLEM_ID} className="text-sm text-danger-dark">
          {problem.message}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          aria-disabled={hasBranch ? undefined : true}
          aria-describedby={hasBranch ? undefined : "sandbox-preview-reason"}
        >
          Preview the command
        </Button>
      </div>
      {hasBranch ? null : (
        <p id="sandbox-preview-reason" className="text-sm text-text-muted">
          {NO_BRANCH_REASON}
        </p>
      )}

      {preview === null ? null : (
        <div className="mt-2 rounded border border-line-strong bg-surface p-3">
          <p className="text-sm font-semibold">The preview of the command</p>
          <p className="text-sm">
            {preview.valid
              ? "The command keeps every rule of the domain."
              : "The command would break a rule of the domain."}
          </p>
          <dl className="mt-2 grid gap-2 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-text-subtle">Value before</dt>
              <dd className="text-sm">
                <span className="font-mono">
                  {preview.answer.before.value === "" ? MONEY_UNAVAILABLE : preview.answer.before.value}
                </span>
                {preview.answer.before.value === "" ? null : (
                  <>
                    {" "}
                    <span className="font-mono text-xs text-text-muted">
                      {preview.answer.before.currency}
                    </span>
                  </>
                )}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-text-subtle">Value after</dt>
              <dd className="text-sm">
                <span className="font-mono">
                  {preview.answer.after.value === "" ? MONEY_UNAVAILABLE : preview.answer.after.value}
                </span>
                {preview.answer.after.value === "" ? null : (
                  <>
                    {" "}
                    <span className="font-mono text-xs text-text-muted">
                      {preview.answer.after.currency}
                    </span>
                  </>
                )}
              </dd>
            </div>
          </dl>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button
              aria-disabled={commitAllowed ? undefined : true}
              aria-describedby={commitAllowed ? undefined : COMMIT_REASON_ID}
              onClick={onCommit}
            >
              Commit the command
            </Button>
          </div>
          {commitAllowed ? null : (
            <p id={COMMIT_REASON_ID} className="mt-2 text-sm text-text-muted">
              {commitReasonText}
            </p>
          )}
        </div>
      )}
    </form>
  );
}

/** Every symbol this module exports, so that a reader sees the whole surface of the form at once. */
export const __all__ = ["MutationFormProps", "MutationForm"] as const;
