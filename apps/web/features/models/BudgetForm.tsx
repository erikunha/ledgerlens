"use client";

/**
 * The form of the budget of the run.
 *
 * Why this file exists: the caps of the run are what bounds the calls of the live mode, and the
 * published contract of the request refuses a cap that is out of its range. The form refuses it
 * too, and it says why, instead of sending a value the server will reject.
 *
 * Why the caps are the only numbers of the form: the cap of money is a text of the server or
 * nothing at all, and the interface never computes an amount of money (FR-011).
 */

import { useEffect, useRef, useState } from "react";

import type { RunLimits } from "@/lib/api/live";

/**
 * The props of the form.
 *
 * Why the limits are controlled: the page owns the caps of the run, and the form only proposes a
 * new set of them.
 */
export interface BudgetFormProps {
  /** The caps of the run right now. */
  limits: RunLimits;
  /** Called with the new caps, when the new caps are inside the range of the contract. */
  onChange: (limits: RunLimits) => void;
  /** Whether the form is read only. */
  disabled?: boolean;
}

/** The name of one cap of the request, the four the contract requires. */
type CapName = "max_model_calls" | "max_tool_calls" | "max_wall_seconds" | "max_output_tokens";

/** One cap of the form: its label and the range the contract allows. */
interface CapField {
  /** The name of the cap in the request. */
  name: CapName;
  /** The label the visitor reads. */
  label: string;
  /** The smallest value the contract allows. */
  min: number;
  /** The largest value the contract allows. */
  max: number;
}

/**
 * The four caps of the run and their ranges.
 *
 * Why the ranges are here and not in the server: the contract of the request is published in
 * `specs/003-r3-bring-your-own-key/contracts/live-run-request.schema.json`, and the form refuses
 * a value the contract refuses, so the visitor learns it before the run and not after it.
 */
const CAP_FIELDS: readonly CapField[] = [
  { name: "max_model_calls", label: "Maximum calls of the model", min: 1, max: 20 },
  { name: "max_tool_calls", label: "Maximum calls of the tools", min: 1, max: 40 },
  { name: "max_wall_seconds", label: "Maximum seconds of the run", min: 5, max: 180 },
  { name: "max_output_tokens", label: "Maximum tokens of the answer", min: 128, max: 16000 },
];

/** The four caps as they are typed, so that an empty field is an empty field and not a zero. */
type Draft = Record<CapName, string>;

/** Reads the four caps of the request as the text of the fields. */
function draftOf(limits: RunLimits): Draft {
  return {
    max_model_calls: String(limits.max_model_calls),
    max_tool_calls: String(limits.max_tool_calls),
    max_wall_seconds: String(limits.max_wall_seconds),
    max_output_tokens: String(limits.max_output_tokens),
  };
}

/**
 * The form of the budget.
 *
 * The form keeps the text the visitor typed, and it only hands the caps over when every cap is
 * inside the range of the contract. An out of range value stays on the screen with the reason it
 * was refused, and the run keeps the caps it had.
 */
export function BudgetForm({ limits, onChange, disabled = false }: BudgetFormProps) {
  const [draft, setDraft] = useState<Draft>(() => draftOf(limits));
  const [error, setError] = useState<string | null>(null);
  const emitted = useRef<RunLimits | null>(null);

  // The form follows the caps it is given, so that a reset of the page is seen here too. The caps
  // the form itself proposed are left alone, or the field would jump back under the visitor.
  useEffect(() => {
    if (emitted.current === limits) {
      return;
    }
    setDraft(draftOf(limits));
    setError(null);
  }, [limits]);

  /** Applies what the visitor typed to one cap, and refuses it when it is out of range. */
  function handleChange(field: CapField, raw: string): void {
    setDraft((previous) => ({ ...previous, [field.name]: raw }));

    const value = Number(raw);
    if (raw.trim() === "" || !Number.isInteger(value) || value < field.min || value > field.max) {
      setError(
        `The cap "${field.label}" must be a whole number between ${field.min} and ${field.max}, as the contract of the run asks.`,
      );
      return;
    }

    setError(null);
    const next: RunLimits = { ...limits, [field.name]: value };
    emitted.current = next;
    onChange(next);
  }

  return (
    <fieldset className="flex flex-col gap-3" disabled={disabled}>
      <legend className="text-sm font-semibold">Caps of the run</legend>

      <div className="grid gap-3 sm:grid-cols-2">
        {CAP_FIELDS.map((field) => (
          <div key={field.name} className="flex flex-col gap-1">
            <label className="text-sm font-medium" htmlFor={`ledgerlens-${field.name}`}>
              {field.label}
            </label>
            <input
              id={`ledgerlens-${field.name}`}
              className="rounded border border-line-strong bg-background px-2 py-1 text-sm"
              type="number"
              inputMode="numeric"
              min={field.min}
              max={field.max}
              step={1}
              value={draft[field.name]}
              disabled={disabled}
              onChange={(event) => handleChange(field, event.target.value)}
            />
            <p className="text-xs text-text-subtle">
              Between {field.min} and {field.max}.
            </p>
          </div>
        ))}
      </div>

      {error ? (
        <p role="alert" className="text-sm text-danger-dark">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
