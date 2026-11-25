/**
 * The guide of the cold start, as data.
 *
 * Why this file exists: the guided path takes a visitor who knows nothing about the repository to
 * one resolved case, and the path is a list of steps. The list is data and not code that draws the
 * page, because a list that is data can be checked without a browser: the test of the guide reads
 * the steps and refuses a step that names no region of the reader, a last step that carries no
 * limitation, a guide that does not name the capture it walks and a step that states a verdict the
 * bundle does not carry. A guide written as code could promise anything and no test could read it.
 *
 * Why a step names a region and not a selector: the guide explains the reader, and the reader owns
 * the layout. A guide that named selectors would break every time the layout moved, and a guide
 * that owns the layout is a second reader. The region is the contract between the two, and the
 * component of the tour resolves the region to the place of the reader that carries it.
 *
 * Why the guide names the capture it walks: the steps say what the recording shows, and the
 * recording is one specific capture of one specific scenario. The digest of the bundle is the name
 * of the capture, and the test of the guide refuses a guide whose capture is not the capture the
 * catalog publishes, because a guide that walks a recording that is no longer there explains
 * nothing.
 *
 * Why the decision step states the action: the decision of the case is a decision of the code and
 * not of the model (ADR-074), and the guide says so. The step carries the action it states, so the
 * test can refuse a guide that states a verdict the bundle does not carry.
 */

/** The regions of the reader the guide may name. */
export const GUIDE_REGIONS = [
  "overview",
  "controls",
  "position",
  "announcement",
  "execution",
  "ledger",
  "evidence",
  "decision",
  "provenance",
] as const;

/** One region of the reader, as the guide names it. */
export type GuideRegion = (typeof GUIDE_REGIONS)[number];

/** The kind of a step of the guide. */
export type GuideStepKind = "orientation" | "playback" | "reading" | "decision" | "limitation";

/** One step of the guided path. */
export interface GuideStep {
  /** The identifier of the step, stable, so a test and a link can name it. */
  readonly id: string;
  /** The region of the reader the step explains. */
  readonly region: GuideRegion;
  /** The kind of the step. */
  readonly kind: GuideStepKind;
  /** The sentence that says what the reader is looking at and why it matters. */
  readonly sentence: string;
  /**
   * The action the step states, when the step is the decision of the case.
   *
   * Why the action is a field and not a part of the sentence: the test of the guide compares the
   * action with the recommended action of the recording, and a comparison over a sentence would be
   * a comparison over the wording and not over the decision.
   */
  readonly statesAction?: string;
}

/** The fork the last step of the guide links to, so the visitor can mutate the case. */
export interface GuideFork {
  /** The scenario the fork opens. */
  readonly scenario: string;
  /** The digest of the ledger of the recording the fork starts from. */
  readonly baseHash: string;
}

/** The guided path of a scenario. */
export interface ReplayGuide {
  /** The scenario the guide walks. */
  readonly scenario: string;
  /** The capture the guide walks: the digest of the bundle of the recording. */
  readonly capture: string;
  /** The steps of the path, in the order the visitor walks them. */
  readonly steps: readonly GuideStep[];
  /** The fork the last step links to. */
  readonly fork: GuideFork;
}

/**
 * The guided path of the scenario S01, the fx markup refund.
 *
 * Why the steps are these: the path takes the visitor from what the page is, to the controls that
 * move the recording, to the sections that hold the work of the agent, to the decision of the case
 * and to what the case cannot decide. The order is the order of the questions a first-time visitor
 * asks.
 */
const S01_GUIDE: ReplayGuide = {
  scenario: "S01",
  capture: "024711fb1b0061137093627c2ad77879fb43802717fdc7101bff28b5977b4e63",
  steps: [
    {
      id: "what-this-is",
      region: "overview",
      kind: "orientation",
      sentence:
        "This is the recording of one real investigation of a payment complaint, played back event " +
        "by event. Nothing here is live: the run was captured once, and the page reads the capture " +
        "from a file, with no key and no network.",
    },
    {
      id: "the-controls",
      region: "controls",
      kind: "playback",
      sentence:
        "The controls move the recording: play, pause, one step at a time, and back. The recording " +
        "never asks a provider for anything, so every visitor sees the same run.",
    },
    {
      id: "the-position",
      region: "position",
      kind: "playback",
      sentence:
        "The slider is the position of the recording. Seek back and the trace is rebuilt up to that " +
        "point: the same events, in the same order, with the same numbers.",
    },
    {
      id: "the-work",
      region: "execution",
      kind: "reading",
      sentence:
        "The execution section shows the work of the agent: the question it put to the ledger, the " +
        "search of the policies, the reference rate it read and the calculation it made. Every " +
        "amount came out of a tool, never out of the model.",
    },
    {
      id: "the-rows",
      region: "ledger",
      kind: "reading",
      sentence:
        "The ledger section shows the rows of the account the run read: the payment of 100.00 EUR " +
        "and the refund of 451.88 BRL behind the complaint.",
    },
    {
      id: "the-evidence",
      region: "evidence",
      kind: "reading",
      sentence:
        "The evidence section shows the answer and the pieces of evidence behind it. Every claim " +
        "cites the piece it came from, and a citation opens the exact line behind it.",
    },
    {
      id: "the-decision",
      region: "decision",
      kind: "decision",
      sentence:
        "The case ends in a decision of the code, not of the model: the refund was lower than the " +
        "payment because of the markup of the acquirer over the reference rate, and the case is " +
        "explained to the customer.",
      statesAction: "explain_to_customer",
    },
    {
      id: "the-limit",
      region: "provenance",
      kind: "limitation",
      sentence:
        "What the case cannot decide: the recording shows one run over one ledger, and it proves " +
        "that this answer was built from these rows. It does not prove the agent answers every " +
        "complaint this well, and the provenance section says exactly which capture this is.",
    },
  ],
  fork: {
    scenario: "S01",
    baseHash: "92960fce6c40388f3b3813ceb2c6517e484ecf1c95d04d2ec0e77678e86a5699",
  },
};

const GUIDES: Readonly<Record<string, ReplayGuide>> = {
  S01: S01_GUIDE,
};

/**
 * Reads the guide of a scenario, or null when the scenario has no guided path.
 *
 * Why the reader returns null and never invents a guide: a scenario with no guide is a scenario
 * the cold start does not walk, and a guide invented for it would explain a recording nobody
 * checked.
 */
export function guideFor(scenario: string): ReplayGuide | null {
  return GUIDES[scenario] ?? null;
}

/** Every symbol this module exports, so that a reader sees the whole surface of the guide at once. */
export const __all__ = [
  "GUIDE_REGIONS",
  "GuideRegion",
  "GuideStep",
  "GuideStepKind",
  "GuideFork",
  "ReplayGuide",
  "guideFor",
] as const;
