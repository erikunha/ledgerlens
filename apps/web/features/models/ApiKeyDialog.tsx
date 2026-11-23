"use client";

/**
 * The dialog of the key of the visitor.
 *
 * Why this file exists: this is the only place of the browser where a provider key exists. The key
 * is typed in a password field, it is read once, at the moment of the submit, and it leaves the
 * dialog only through `onSubmit`. The field is emptied in the same tick, so the text of the key
 * never waits in the page while the server answers.
 *
 * The dialog carries the consent of T036: the send stays disabled until the visitor ticks the box,
 * because the contract of the credential route has no field for a consent and the gate has to live
 * in the interface.
 */

import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { ConsentNotice } from "@/features/consent/ConsentNotice";
import type { Provider } from "@/lib/api/live";

/**
 * The props of the dialog.
 *
 * Why the key arrives as a plain string: the value is read once, at the submit, and the transport
 * of the backend is the only place that sends it. The dialog keeps no copy of it anywhere else.
 */
export interface ApiKeyDialogProps {
  /** Whether the dialog is open. */
  open: boolean;
  /** The providers the visitor may choose from. */
  providers: Provider[];
  /** Whether the server is answering the credential right now. */
  busy?: boolean;
  /** The refusal of the server, shown where the action was. */
  error?: string | null;
  /** Called with the provider and the key, once, at the submit. */
  onSubmit: (input: { provider: string; apiKey: string }) => void;
  /** Called when the visitor closes the dialog. */
  onClose: () => void;
}

/**
 * The dialog of the key.
 *
 * The key is held in the state of the field and nowhere else. The state is emptied as soon as the
 * value is handed over, and again whenever the dialog opens, so a key never survives a dialog.
 */
export function ApiKeyDialog({ open, providers, busy = false, error = null, onSubmit, onClose }: ApiKeyDialogProps) {
  const [provider, setProvider] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [consent, setConsent] = useState(false);
  const [emptyKey, setEmptyKey] = useState<string | null>(null);

  const selectedProvider = provider ?? providers[0] ?? "";

  // The dialog opens empty: a key of a previous visit never comes back with the visitor.
  useEffect(() => {
    if (!open) {
      setApiKey("");
      setConsent(false);
      setEmptyKey(null);
    }
  }, [open]);

  if (!open) {
    return null;
  }

  /**
   * Hands the key over, once.
   *
   * Why the value is emptied here and not after the answer: the key has no reason to stay in the
   * page while the server answers, and the transport of the backend already carries it in the body
   * of one request.
   */
  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!consent) {
      return;
    }
    const value = apiKey.trim();
    if (value === "") {
      setEmptyKey("Type your key before sending it.");
      return;
    }
    setEmptyKey(null);
    onSubmit({ provider: selectedProvider, apiKey: value });
    setApiKey("");
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-900/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Your provider key"
        className="flex w-full max-w-lg flex-col gap-3 rounded-lg border border-line bg-background p-6 shadow-lg"
      >
        <h2 className="text-lg font-semibold">Your provider key</h2>
        <p className="text-sm text-text-muted">
          The key is read once, from the field below, and it never reaches a URL, a header or a log.
        </p>

        <ConsentNotice checked={consent} onCheckedChange={setConsent} />

        <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium" htmlFor="ledgerlens-api-key-provider">
              Provider
            </label>
            <select
              id="ledgerlens-api-key-provider"
              className="rounded border border-line-strong bg-background px-2 py-1 text-sm"
              value={selectedProvider}
              disabled={busy}
              onChange={(event) => setProvider(event.target.value)}
            >
              {providers.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {candidate}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium" htmlFor="ledgerlens-api-key-value">
              The key of your provider
            </label>
            <input
              id="ledgerlens-api-key-value"
              className="rounded border border-line-strong bg-background px-2 py-1 font-mono text-sm"
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={apiKey}
              disabled={busy}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </div>

          {emptyKey ? (
            <p role="alert" className="text-sm text-danger-dark">
              {emptyKey}
            </p>
          ) : null}
          {error ? (
            <p role="alert" className="text-sm text-danger-dark">
              {error}
            </p>
          ) : null}

          <div className="flex items-center gap-2">
            <Button type="submit" disabled={busy || !consent}>
              Send the key
            </Button>
            <Button variant="secondary" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
