"use client";

/**
 * The consent of the visitor, of task T036.
 *
 * Why this file exists: the visitor sends a key of their own, so the page has to say the three
 * things that matter before the send is enabled. The provider of the visitor may charge the
 * visitor, the key is not stored and dies with the session, and the memory of the machine cannot
 * be guaranteed to be erased. The third sentence is the limit of the promise of the repository, said
 * out loud.
 *
 * After the credential is accepted the page shows the words of the server, read from the headers of
 * the answer. The frontend never invents a disclosure: a header the browser may not read is a
 * header the server did not send, and it is shown as nothing at all.
 *
 * The box belongs to the dialog, where the visitor ticks it and the send waits for the tick. After
 * the credential is accepted the visitor has nothing to tick, so the page shows the three sentences
 * and the words of the server with `ConsentSummary`, which carries no control at all.
 */

import type { DisclosureHeaders } from "@/lib/api/live";

/**
 * The three sentences the visitor reads before the key is sent.
 *
 * Why they are a constant and not a text of the page: the same three sentences have to appear
 * everywhere the consent appears, and a test has to be able to check that the page shows exactly
 * what the contract of T036 asks for.
 */
export const CONSENT_SENTENCES: readonly string[] = [
  "Your provider may charge you for the calls of this run. LedgerLens does not pay for them, and the caps of the run bound the calls, not the bill of your provider.",
  "Your key is not stored: it lives in the memory of the server of the demo, it is dropped when the session ends, and it is never written to a file, a log, a trace or a URL.",
  "The memory of the machine cannot be guaranteed to be erased: the server drops the key when the credential ends, but no runtime can promise that no copy of the text of the key survives in the memory of the interpreter or in a swap of the operating system.",
];

/**
 * The props of the consent.
 *
 * Why the box is controlled: the page and the dialog share the answer, and the send of the key
 * stays disabled until the answer is yes.
 */
export interface ConsentNoticeProps {
  /** Whether the visitor ticked the box. */
  checked: boolean;
  /** Called with the new answer of the box. */
  onCheckedChange: (checked: boolean) => void;
  /** The words of the server, when the answer of the credential route arrived. */
  disclosure?: DisclosureHeaders | null;
}

/**
 * The consent of the visitor.
 *
 * The three sentences, the box, and the words of the server when they arrive. Nothing else: the
 * component never says that a key is safe, it only says what the server said and what the contract
 * of the demo promises.
 */
export function ConsentNotice({ checked, onCheckedChange, disclosure }: ConsentNoticeProps) {
  return (
    <section
      className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4"
      aria-label="What happens to your key"
    >
      <h2 className="text-base font-semibold">Before you send your key</h2>
      <ul className="list-disc pl-5 text-sm text-text-muted">
        {CONSENT_SENTENCES.map((sentence) => (
          <li key={sentence}>{sentence}</li>
        ))}
      </ul>
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-1 h-4 w-4"
          checked={checked}
          onChange={(event) => onCheckedChange(event.target.checked)}
        />
        <span>I read the three sentences above and I accept them.</span>
      </label>
      <DisclosurePanel disclosure={disclosure} />
    </section>
  );
}

/**
 * The consent that was already given, with no box.
 *
 * Why a second component and not the same one without a checkbox: the signature of the consent is
 * fixed by ADR-040, and the box belongs to the dialog, where the visitor ticks it. After the
 * credential is accepted the visitor has nothing left to tick, so the page shows the three
 * sentences and the words of the server, and nothing that pretends to be a choice.
 */
export function ConsentSummary({ disclosure }: { disclosure?: DisclosureHeaders | null }) {
  return (
    <section
      className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4"
      aria-label="The consent of the visitor"
    >
      <h2 className="text-base font-semibold">What happens to your key</h2>
      <ul className="list-disc pl-5 text-sm text-text-muted">
        {CONSENT_SENTENCES.map((sentence) => (
          <li key={sentence}>{sentence}</li>
        ))}
      </ul>
      <DisclosurePanel disclosure={disclosure} />
    </section>
  );
}

/**
 * The words of the server about the billing, the storage and the erasure of the key.
 *
 * Why a row disappears when the header is absent: the server did not say it, so the page does not
 * say it either. A refusal to answer is not an invitation to guess.
 */
function DisclosurePanel({ disclosure }: { disclosure: DisclosureHeaders | null | undefined }) {
  if (!disclosure) {
    return null;
  }

  const rows = [
    { label: "The server says about the billing:", value: disclosure.billing },
    { label: "The server says about the storage of the key:", value: disclosure.keyStorage },
    { label: "The server says about the erasure of the key:", value: disclosure.keyErasure },
  ].filter((row): row is { label: string; value: string } => typeof row.value === "string" && row.value !== "");

  if (rows.length === 0) {
    return null;
  }

  return (
    <div className="rounded border border-line bg-background p-3">
      <h3 className="text-sm font-semibold">What the server said about your key</h3>
      <ul className="list-disc pl-5 text-sm text-text-muted">
        {rows.map((row) => (
          <li key={row.label}>
            {row.label} {row.value}
          </li>
        ))}
      </ul>
    </div>
  );
}
