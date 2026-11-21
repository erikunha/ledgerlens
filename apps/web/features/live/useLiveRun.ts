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
 */
export type LiveRunStatus = "idle" | "starting" | "running" | "ended" | "failed" | "refused";

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
        setStatus(event.event_type === "run.failed" ? "failed" : "ended");
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
      await client.cancelRun(id);
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
  }, []);

  return {
    status,
    runId,
    events,
    counters,
    cost,
    error,
    start,
    cancel,
    reset,
  };
}
