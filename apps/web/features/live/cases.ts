/**
 * The cases of the demo.
 *
 * Why this file exists: the live mode of the browser runs a case of the published dataset, and
 * the case has to be the same one for every visitor, otherwise two runs of the demo would not be
 * comparable. The list below is the single source of that case: the scenario it comes from, the
 * account it is about, the question it asks and the variant of the architecture it exercises.
 *
 * Why the variant C: the architectures A, B and C exist in the registry of the backend, A is the
 * chain that uses no tool and B and C drive the tools of the agent, so B and C need a model that
 * calls tools natively. C is the architecture that has the tools and the verification, which is the
 * one the recorded case of the site used.
 */

import type { RunVariant } from "@/lib/api/live";

/**
 * One case of the demo.
 *
 * Why the names are in camel case: the case is a value of the interface, not a body of a request,
 * and the page assembles the body of the request out of it.
 */
export interface DemoCase {
  /** The identifier of the scenario, in the shape `S` followed by two digits. */
  scenarioId: string;
  /** The identifier of the account the case is about. */
  accountId: string;
  /** The question the case asks. */
  question: string;
  /** The variant of the architecture the case runs in. */
  variant: RunVariant;
}

/**
 * The cases the live mode of the demo offers.
 *
 * Why there is exactly one: the demo has to be reproducible, and one case is enough to show the
 * whole trace of an investigation.
 */
export const DEMO_CASES: readonly DemoCase[] = [
  {
    scenarioId: "S01",
    accountId: "C-0412",
    question: "Why was the BRL refund for TX-2048 lower than the EUR payment?",
    variant: "C",
  },
];
