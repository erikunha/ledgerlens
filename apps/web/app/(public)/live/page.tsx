"use client";

/**
 * The live mode of the demo, the page of task T034.
 *
 * Why this file exists: the live half of the demo asks the backend of the demo for a run, with the
 * key of the visitor, and it has to be honest about what it is doing. The page never starts a run
 * on its own: the visitor types a key, ticks the consent and presses the run. Every refusal of the
 * server is rendered where the action was, with the code and the message of the server, and a
 * refusal is never dressed up as a run.
 *
 * The page opens a session and reads the catalog of the models when it opens, and it touches no route
 * that holds or spends a credential: the routes that hold or spend a credential are the routes that
 * refuse, and a probe of them would create a credential. What the opening requests tell the visitor is
 * whether the server is there at all, and the refusal of the server is rendered where the action was.
 *
 * The one refusal that closes the live mode is `LIVE_MODE_OFFLINE`: while the product runs offline
 * the backend takes no credential and starts no run, so the controls of the live mode stay disabled
 * for the rest of the session (ADR-040, question 7). Every other refusal leaves the controls
 * usable, because the visitor may type another key or start the backend and try again.
 *
 * The page says what stopping a run does and does not promise, before the visitor presses the
 * button: the calls that have not started never start, and a call that is already at the provider
 * is a best effort, because it cannot be guaranteed to stop (FR-019). The truth of the
 * cancellation comes from the server: the answer of the cancellation and the terminal event of the
 * trace carry the flag of the best effort, the hook keeps it, and the page says what really
 * happened when the visitor stopped the run.
 */

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

/**
 * The words of the disclosure of the AI agent, read from the domain of the product.
 *
 * Why the file of the domain and not a sentence written here: Article 50 of the EU AI Act has applied
 * since 2 August 2026, and the surface that answers a person has to say that the answer comes from an
 * AI agent and that a person reviews the cases that need a review. The demo application says it with
 * the same words, and the two surfaces cannot drift apart because there is only one place where the
 * sentence is written: `ledgerlens/prompts/ai_disclosure.json`.
 */
import aiDisclosure from "../../../../../ledgerlens/prompts/ai_disclosure.json";

import { Badge } from "@/components/ui/Badge";
import { Button, buttonClasses } from "@/components/ui/Button";
import { CardSection } from "@/components/ui/Card";
import { ConsentSummary } from "@/features/consent/ConsentNotice";
import { CostPanel } from "@/features/evals/CostPanel";
import { DEMO_CASES } from "@/features/live/cases";
import { RunTimeline } from "@/features/live/RunTimeline";
import { useLiveRun } from "@/features/live/useLiveRun";
import { ApiKeyDialog } from "@/features/models/ApiKeyDialog";
import { BudgetForm } from "@/features/models/BudgetForm";
import { ModelSelector } from "@/features/models/ModelSelector";
import { ApiError, createApiClient } from "@/lib/api/client";
import {
  DEFAULT_RUN_LIMITS,
  type DisclosureHeaders,
  type ModelProfile,
  type Provider,
  type RunLimits,
} from "@/lib/api/live";

/**
 * The code the backend answers with while the product runs offline.
 *
 * Why this code and no other one: it is the only refusal that says that the live mode is off for
 * good in this session. A refusal with any other code (a key the server did not accept, for
 * instance) is about the act of the visitor, and the visitor may act again.
 */
const LIVE_MODE_OFFLINE = "LIVE_MODE_OFFLINE";

/**
 * The identifier of the sentence that says what stopping a run does and does not promise.
 *
 * Why the sentence has an identifier: the control that stops the run points at it with
 * `aria-describedby`, so a reader of a screen reader hears the contract of the cancellation
 * before pressing the button (FR-019).
 */
const CANCEL_REASON_ID = "ledgerlens-live-cancel-reason";

/**
 * Turns whatever the backend refused with into words a visitor can read.
 *
 * Why the code comes first: the code is what the runbook of the deployment talks about, and the
 * message of the server is the sentence the visitor reads.
 */
function describeFailure(caught: unknown, origin: string): string {
  if (caught instanceof ApiError) {
    return `${caught.code}: ${caught.message}`;
  }
  return `the origin ${origin} did not answer the request`;
}

/**
 * The page of the live mode.
 *
 * The page is a client component because the live mode is an interaction: the catalog of the
 * models, the key of the visitor and the stream of the run all happen in the browser.
 */
export default function LivePage() {
  const client = useMemo(() => createApiClient(), []);
  const run = useLiveRun(client);

  const [models, setModels] = useState<ModelProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [priceNote, setPriceNote] = useState<string | null>(null);
  const [priceKnown, setPriceKnown] = useState<boolean | null>(null);
  const [limits, setLimits] = useState<RunLimits>(DEFAULT_RUN_LIMITS);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [credentialHandle, setCredentialHandle] = useState<string | null>(null);
  const [disclosure, setDisclosure] = useState<DisclosureHeaders | null>(null);
  const [credentialError, setCredentialError] = useState<string | null>(null);
  const [credentialBusy, setCredentialBusy] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [liveRefusal, setLiveRefusal] = useState<{ code: string; message: string } | null>(null);

  // The session of the visitor is opened once, and the catalog of the models comes with it.
  useEffect(() => {
    let alive = true;

    async function load(): Promise<void> {
      try {
        await client.startSession();
        const catalog = await client.models();
        if (!alive) {
          return;
        }
        setModels(catalog.models);
        setCatalogError(null);
      } catch (caught) {
        if (!alive) {
          return;
        }
        setCatalogError(describeFailure(caught, client.baseUrl));
      }
    }

    void load();
    return () => {
      alive = false;
    };
  }, [client]);

  // The price of the chosen profile is read before the first call, so the visitor knows where the
  // price comes from before the run and not after it.
  useEffect(() => {
    if (!selectedProfileId) {
      setPriceNote(null);
      setPriceKnown(null);
      return;
    }

    let alive = true;
    void client
      .priceOfModel(selectedProfileId)
      .then((price) => {
        if (!alive) {
          return;
        }
        setPriceNote(price.price_note);
        setPriceKnown(price.price_known);
      })
      .catch(() => {
        if (!alive) {
          return;
        }
        setPriceNote(null);
        setPriceKnown(null);
      });

    return () => {
      alive = false;
    };
  }, [client, selectedProfileId]);

  /** Accepts the key of the visitor and keeps the handle, which is all the page ever keeps. */
  const handleCredential = useCallback(
    async (input: { provider: string; apiKey: string }): Promise<void> => {
      setCredentialBusy(true);
      setCredentialError(null);
      try {
        const accepted = await client.acceptCredential(input);
        setCredentialHandle(accepted.handle.handle);
        setDisclosure(accepted.disclosure);
        setDialogOpen(false);
      } catch (caught) {
        setCredentialError(describeFailure(caught, client.baseUrl));
        // Only the offline refusal closes the live mode for the rest of the session. Any other
        // refusal is about the key of this attempt, and the visitor may type another one.
        if (caught instanceof ApiError && caught.code === LIVE_MODE_OFFLINE) {
          setLiveRefusal({ code: caught.code, message: caught.message });
        }
      } finally {
        setCredentialBusy(false);
      }
    },
    [client],
  );

  /** Starts the run of the case of the demo. */
  const handleRun = useCallback((): void => {
    const profile = models.find((candidate) => candidate.profile_id === selectedProfileId);
    const demoCase = DEMO_CASES[0];
    if (!profile || !demoCase || !credentialHandle) {
      return;
    }
    void run.start({ profile, credentialHandle, limits, demoCase });
  }, [credentialHandle, limits, models, run, selectedProfileId]);

  const providers = useMemo<Provider[]>(() => {
    const found = Array.from(new Set(models.map((model) => model.provider)));
    return found.length > 0 ? found : ["openai"];
  }, [models]);

  const isRunning = run.status === "starting" || run.status === "running";
  const isRefused = run.status === "refused";
  // The truth of the cancellation comes from the server: the flag of the best effort says that a
  // call was already at the provider when the visitor asked for the end of the run, and the status
  // of the run says that the run ended because it was cancelled (FR-019).
  const wasCancelled = run.status === "cancelled" || run.bestEffort;

  // The offline refusal is the only one that disables the controls of the live mode for the rest
  // of the session: the backend will take no credential and start no run while the product runs
  // offline, so a control that stayed usable would only offer the visitor a refusal.
  const liveControlsDisabled = liveRefusal !== null;
  const demoCase = DEMO_CASES[0];

  return (
    <div className="mx-auto flex w-full max-w-content flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>mode: live_agent</Badge>
          <Badge>origin: {client.baseUrl}</Badge>
        </div>
        <h1 className="text-3xl font-semibold">Live mode</h1>
        <p className="max-w-2xl text-text-muted">{aiDisclosure.sentence}</p>
        <p className="max-w-2xl text-text-muted">
          You type the key of your provider and the run happens on the backend of the demo. The key is
          read once, from the field you typed, and it never reaches a URL, a header or a log. The
          caps of the run bound the calls of the run, not the bill of your provider.
        </p>
        <p className="text-sm text-text-subtle">
          The recorded demo needs no key and no network:{" "}
          <Link className={buttonClasses("ghost", "sm")} href="/replay">
            Open the recorded demo
          </Link>
        </p>
      </header>

      {catalogError ? (
        <div role="alert" className="rounded-lg border border-danger/40 bg-danger-light p-4">
          <h2 className="text-base font-semibold text-danger-dark">The catalog is not available</h2>
          <p className="text-sm text-danger-dark">{catalogError}</p>
        </div>
      ) : null}

      {liveRefusal ? (
        <div className="relative z-[60] flex flex-col gap-2">
          <div role="alert" className="rounded-lg border border-danger/40 bg-danger-light p-4">
            <h2 className="text-base font-semibold text-danger-dark">
              The live mode is off: {liveRefusal.code}
            </h2>
            <p className="text-sm text-danger-dark">{liveRefusal.message}</p>
            <p className="mt-2 text-sm text-text-muted">
              The live controls stay disabled for the rest of this session, because the backend
              refuses the live mode while the product runs offline. The recorded demo keeps working
              exactly as before, and it needs no key.
            </p>
          </div>
          {dialogOpen ? (
            <div>
              <Button variant="secondary" onClick={() => setDialogOpen(false)}>
                Close the dialog
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}

      {isRefused && run.error ? (
        <div role="alert" className="rounded-lg border border-danger/40 bg-danger-light p-4">
          <h2 className="text-base font-semibold text-danger-dark">
            The backend refused: {run.error.code}
          </h2>
          <p className="text-sm text-danger-dark">{run.error.message}</p>
          <p className="mt-2 text-sm text-text-muted">
            The recorded demo keeps working exactly as before, and it needs no key.
          </p>
        </div>
      ) : null}

      <CardSection
        title="The model of the run"
        description="Only the models the catalog of the server enables for the public demo are offered."
        titleLevel="h2"
      >
        <ModelSelector
          profiles={models}
          selectedProfileId={selectedProfileId}
          onSelect={setSelectedProfileId}
          priceNote={priceNote}
          priceKnown={priceKnown}
        />
      </CardSection>

      <CardSection
        title="The caps of the run"
        description="The caps bound the calls of the run."
        titleLevel="h2"
      >
        <BudgetForm limits={limits} onChange={setLimits} disabled={isRunning || liveControlsDisabled} />
      </CardSection>

      <CardSection
        title="Your key"
        description="The key is read once and it dies with the session."
        titleLevel="h2"
      >
        <div className="flex flex-col gap-3">
          {credentialHandle ? (
            <p className="text-sm text-text-muted">
              The server accepted the key of your provider and holds it in its vault. The page keeps
              the handle and nothing else.
            </p>
          ) : (
            <div>
              <Button onClick={() => setDialogOpen(true)} disabled={isRefused || liveControlsDisabled}>
                Use your own key
              </Button>
            </div>
          )}

          {credentialError && !liveRefusal ? (
            <p role="alert" className="text-sm text-danger-dark">
              {credentialError}
            </p>
          ) : null}

          {credentialHandle ? <ConsentSummary disclosure={disclosure} /> : null}
        </div>
      </CardSection>

      <CardSection
        title="The case"
        description="The case of the demo is the same for every visitor."
        titleLevel="h2"
      >
        <div className="flex flex-col gap-3">
          {demoCase ? (
            <p className="text-sm text-text-muted">
              Scenario {demoCase.scenarioId}, account {demoCase.accountId}, variant{" "}
              {demoCase.variant}. The question is: {demoCase.question}
            </p>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={handleRun}
              disabled={
                isRefused ||
                liveControlsDisabled ||
                isRunning ||
                !selectedProfileId ||
                !credentialHandle ||
                !demoCase
              }
            >
              Run the case
            </Button>
            {isRunning ? (
              <Button
                variant="secondary"
                aria-describedby={CANCEL_REASON_ID}
                onClick={() => void run.cancel()}
              >
                Stop the run
              </Button>
            ) : null}
          </div>
          <p id={CANCEL_REASON_ID} className="text-sm text-text-subtle">
            Stopping a run ends it: the calls that have not started never start. A call that is
            already at the provider is a best effort, and it may not stop. The run ends with the
            status cancelled, and the trace keeps the events that already happened.
          </p>
          {wasCancelled ? (
            <div role="alert" className="rounded-lg border border-warning/40 bg-warning-light p-4">
              <h3 className="text-base font-semibold text-warning-dark">
                {run.bestEffort ? "The cancellation was a best effort" : "The run was cancelled"}
              </h3>
              <p className="text-sm text-warning-dark">
                {run.bestEffort
                  ? "A call of the provider was already in flight when you stopped the run, and it could not be guaranteed to stop: it may finish anyway, and the tokens it reports are counted in the cost of the run. The calls that had not started never started."
                  : "The calls that had not started never started."}
              </p>
              <p className="mt-2 text-sm text-text-muted">
                The run ends with the status cancelled, and the trace keeps the events that already
                happened.
              </p>
              {run.cancelMessage ? (
                <p className="mt-2 text-sm text-text-subtle">{run.cancelMessage}</p>
              ) : null}
            </div>
          ) : null}
          <p className="text-sm text-text-subtle">
            The page never starts a run on its own, and a refusal of the server is shown with its
            code and its message.
          </p>
        </div>
      </CardSection>

      {run.runId ? (
        <div className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold">The run</h2>
          <p className="font-mono text-xs text-text-subtle">{run.runId}</p>

          <RunTimeline counters={run.counters} events={run.events} />
          <CostPanel report={run.cost} running={isRunning} />
        </div>
      ) : null}

      <ApiKeyDialog
        open={dialogOpen}
        providers={providers}
        // The busy of the dialog is the one lever that disables its send, so the offline refusal
        // uses it: the send of a key is impossible while the backend refuses the live mode.
        busy={credentialBusy || liveControlsDisabled}
        error={credentialError}
        onSubmit={(input) => void handleCredential(input)}
        onClose={() => setDialogOpen(false)}
      />
    </div>
  );
}
