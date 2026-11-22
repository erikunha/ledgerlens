"use client";

/**
 * The hook that runs the case and reads the stream.
 *
 * Why this file exists: the live mode of the browser is a run that the backend owns and a stream
 * that the backend writes. The hook is the one place where the two meet, and it carries the rules
 * that the rest of the interface depends on.
 *
 * The counters come from the events of the stream, because the page shows them as the server
 * reports them and never interpolates a number the server did not send. The source is closed on
 * the terminal event, because a browser that reconnects would receive the whole stream of the run
 * again, from the beginning, forever. And a refusal of the server is a refusal, never a run: the
 * `503` with the code `LIVE_MODE_OFFLINE` becomes the status `refused`, with the code and the
 * message of the server.
 *
 * The cancellation has its own state, because the truth of a cancellation is in the server and not
 * in the browser: the answer of the route of the cancellation carries the flag that says a call
 * was already at the provider and could not be guaranteed to stop, and the terminal event of the
 * trace carries the same flag. The hook keeps both, so the page can tell the visitor that the
 * cancellation was a best effort and what it means for the call that was in flight (FR-019).
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, type ApiClient } from "@/lib/api/client";
import { openRunStream, type LiveStreamHandle } from "@/lib/api/events";
import {
  TERMINAL_EVENT_TYPES,
  type ApiErrorBody,
  type CostReportBody,
  type ModelProfile,
  type RunLimits,
} from "@/lib/api/live";
import type { TraceEvent } from "@/lib/api/schemas";
import type { DemoCase } from "@/features/live/cases";

/**
 * The status of the live run, as the interface shows it.
 *
 * Why `refused` is a status of its own: a refusal is not a run, and a page that cannot tell the
 * two apart would show a failed run where nothing ever started.
 *
 * Why `cancelled` is a status of its own: a run that the visitor stopped is not a run that
 * finished and not a run that failed, and the page has to be able to tell the visitor that the run
 * was stopped on purpose (FR-019).
 */
export type LiveRunStatus =
  | "idle"
  | "starting"
  | "running"
  | "ended"
  | "failed"
  | "cancelled"
  | "refused";

/**
 * What the run consumed, as the server reported it.
 *
 * Why the numbers are not computed here: the event `run.status` carries them, and the page shows
 * them as they are.
 */
export interface RunCounters {
  /** How many calls of a model the run made. */
  modelCalls: number;
  /** How many calls of a tool the run made. */
  toolCalls: number;
  /** How many tokens the run read. */
  inputTokens: number;
  /** How many tokens the run wrote. */
  outputTokens: number;
  /** How many seconds the run took. */
  elapsedSeconds: number;
}

/**
 * What the hook gives to the page.
 *
 * Why the error is the body of the refusal: the page renders the code and the message of the
 * server, and it never invents a text of its own for a failure.
 */
export interface UseLiveRunResult {
  /** Where the run is. */
  status: LiveRunStatus;
  /** The identifier of the run, or `null` when there is none. */
  runId: string | null;
  /** The events the stream carried, in the order it carried them. */
  events: TraceEvent[];
  /** What the run consumed, or `null` while the server reported nothing. */
  counters: RunCounters | null;
  /** The report of the cost, or `null` while there is none. */
  cost: CostReportBody | null;
  /** The refusal of the server, or `null` when nothing was refused. */
  error: ApiErrorBody | null;
  /**
   * Whether the cancellation of the run was a best effort.
   *
   * Why the flag comes from the server and not from the browser: the server knows whether a call
   * was already at the provider when the visitor asked for the end of the run, and a call like
   * that cannot be guaranteed to stop (FR-019). The flag travels with the answer of the
   * cancellation and with the terminal event of the trace.
   */
  bestEffort: boolean;
  /** What the server said about the cancellation, or `null` when it said nothing. */
  cancelMessage: string | null;
  /** Starts the run of a case. */
  start(input: {
    profile: ModelProfile;
    credentialHandle: string;
    limits: RunLimits;
    demoCase: DemoCase;
  }): Promise<void>;
  /** Asks the server to stop the run. */
  cancel(): Promise<void>;
  /** Forgets the run and goes back to the state before it. */
  reset(): void;
}

/** The counters of a run that reported nothing yet. */
const EMPTY_COUNTERS: RunCounters = {
  modelCalls: 0,
  toolCalls: 0,
  inputTokens: 0,
  outputTokens: 0,
  elapsedSeconds: 0,
};

/**
 * Reads a number out of a payload.
 *
 * Why the fallback is the previous value: the page shows what the server reported, and a payload
 * that leaves a measure out does not erase the measure the server reported before.
 */
function readNumber(payload: Record<string, unknown>, name: string, fallback: number): number {
  const value = payload[name];
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

/**
 * Turns whatever was thrown into the body of a refusal.
 *
 * Why a refusal always has a code and a message: the page renders them where the action was, and
 * an empty error panel would hide the reason of the failure.
 */
function toErrorBody(caught: unknown): ApiErrorBody {
  if (caught instanceof ApiError) {
    return (
      caught.body ?? {
        code: caught.code,
        message: caught.message,
        retryable: caught.retryable,
        request_id: caught.requestId,
      }
    );
  }
  return {
    code: "UNEXPECTED_ERROR",
    message:
      caught instanceof Error
        ? caught.message
        : "the request failed for a reason the interface does not know",
    retryable: false,
    request_id: "",
  };
}

/**
 * The status of the page for the terminal event of the run.
 *
 * Why the three ends are three states: a run that finished, a run that failed and a run that the
 * visitor stopped are three different things for the visitor, and a page that shows them all as
 * "ended" cannot tell the visitor that the run was stopped on purpose (FR-019).
 */
function statusOfTheTerminalEvent(eventType: TraceEvent["event_type"]): LiveRunStatus {
  if (eventType === "run.failed") {
    return "failed";
  }
  if (eventType === "run.cancelled") {
    return "cancelled";
  }
  return "ended";
}

/**
 * The hook of the live run.
 *
 * The client is given by the caller, so the unit test of the hook uses a fake and never opens a
 * socket. The stream is built by the same caller, for the same reason.
 */
export function useLiveRun(
  client: ApiClient,
  options?: { streamFactory?: typeof openRunStream },
): UseLiveRunResult {
  const streamFactory = options?.streamFactory ?? openRunStream;

  const [status, setStatus] = useState<LiveRunStatus>("idle");
  const [runId, setRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [counters, setCounters] = useState<RunCounters | null>(null);
  const [cost, setCost] = useState<CostReportBody | null>(null);
  const [error, setError] = useState<ApiErrorBody | null>(null);
  // The flag of the best effort and the words of the server about the cancellation. The flag is
  // never taken back: the server sets it when a call was already at the provider, and it never
  // clears it (FR-019).
  const [bestEffort, setBestEffort] = useState(false);
  const [cancelMessage, setCancelMessage] = useState<string | null>(null);

  const streamRef = useRef<LiveStreamHandle | null>(null);
  const runIdRef = useRef<string | null>(null);

  // The stream of a page that goes away is closed, so the connection of the backend dies with it.
  useEffect(
    () => () => {
      streamRef.current?.close();
      streamRef.current = null;
    },
    [],
  );

  /** Asks the server for the money of a run that ended. */
  const loadCost = useCallback(
    async (id: string): Promise<void> => {
      try {
        const report = await client.costOfRun(id);
        setCost(report);
      } catch {
        // The route answers `409` while the run is still going. The counters of the stream stay,
        // and the money is asked for again when the run ends.
      }
    },
    [client],
  );

  /** Applies one event of the stream to the state of the page. */
  const handleEvent = useCallback(
    (event: TraceEvent): void => {
      setEvents((previous) => [...previous, event]);

      if (event.event_type === "run.status") {
        const payload = event.payload ?? {};
        setCounters((previous) => {
          const base = previous ?? EMPTY_COUNTERS;
          return {
            modelCalls: readNumber(payload, "model_calls", base.modelCalls),
            toolCalls: readNumber(payload, "tool_calls", base.toolCalls),
            inputTokens: readNumber(payload, "input_tokens", base.inputTokens),
            outputTokens: readNumber(payload, "output_tokens", base.outputTokens),
            elapsedSeconds: readNumber(payload, "elapsed_seconds", base.elapsedSeconds),
          };
        });
      }

      if (TERMINAL_EVENT_TYPES.includes(event.event_type)) {
        streamRef.current?.close();
        streamRef.current = null;
        setStatus(statusOfTheTerminalEvent(event.event_type));
        // The flag of the best effort travels with the terminal event of the trace, so the page
        // knows what happened even when the answer of the cancellation was lost (FR-019).
        if (event.payload["best_effort"] === true) {
          setBestEffort(true);
        }
        const id = runIdRef.current;
        if (id) {
          void loadCost(id);
        }
      }
    },
    [loadCost],
  );

  /**
   * Starts the run of a case.
   *
   * Why the sandbox is forked first: the live run reads a private branch of the published case, so
   * two visitors never read the same branch.
   */
  const start = useCallback(
    async (input: {
      profile: ModelProfile;
      credentialHandle: string;
      limits: RunLimits;
      demoCase: DemoCase;
    }): Promise<void> => {
      setStatus("starting");
      setError(null);
      setCost(null);
      setCounters(null);
      setEvents([]);
      setRunId(null);
      setBestEffort(false);
      setCancelMessage(null);
      runIdRef.current = null;

      try {
        const sandbox = await client.forkSandbox(input.demoCase.scenarioId);
        const accepted = await client.startLiveRun({
          mode: "live_agent",
          scenario_id: input.demoCase.scenarioId,
          sandbox_id: sandbox.id,
          expected_revision: sandbox.revision,
          account_id: input.demoCase.accountId,
          question: input.demoCase.question,
          variant: input.demoCase.variant,
          model_profile_id: input.profile.profile_id,
          credential_handle: input.credentialHandle,
          limits: input.limits,
        });

        runIdRef.current = accepted.run_id;
        setRunId(accepted.run_id);
        setStatus("running");

        streamRef.current = streamFactory({
          baseUrl: client.baseUrl,
          runId: accepted.run_id,
          onEvent: handleEvent,
        });
      } catch (caught) {
        setError(toErrorBody(caught));
        setStatus("refused");
      }
    },
    [client, handleEvent, streamFactory],
  );

  /** Asks the server to stop the run. */
  const cancel = useCallback(async (): Promise<void> => {
    const id = runIdRef.current;
    if (!id) {
      return;
    }
    try {
      const answer = await client.cancelRun(id);
      // The answer of the cancellation is where the truth of the cancellation lives: the flag says
      // that a call was already at the provider and could not be guaranteed to stop, and the
      // message is the sentence of the server about what happened (FR-019).
      if (answer.best_effort === true) {
        setBestEffort(true);
      }
      setCancelMessage(answer.message === "" ? null : answer.message);
    } catch (caught) {
      setError(toErrorBody(caught));
    }
  }, [client]);

  /** Forgets the run and goes back to the state before it. */
  const reset = useCallback((): void => {
    streamRef.current?.close();
    streamRef.current = null;
    runIdRef.current = null;
    setStatus("idle");
    setRunId(null);
    setEvents([]);
    setCounters(null);
    setCost(null);
    setError(null);
    setBestEffort(false);
    setCancelMessage(null);
  }, []);

  return {
    status,
    runId,
    events,
    counters,
    cost,
    error,
    bestEffort,
    cancelMessage,
    start,
    cancel,
    reset,
  };
}
