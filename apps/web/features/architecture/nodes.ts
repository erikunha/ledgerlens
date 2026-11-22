/**
 * The typed source of the six subsystems that the tour of the architecture shows.
 *
 * Why this file exists: the page of the architecture is the tour of the code of the repository, and
 * every word it shows about a subsystem has to live in the repository, because a page that invents
 * a description of a module is a page that describes a module that does not exist (ADR-046).
 *
 * Why this file is the ONE source of the content of the page: the picture of the diagram and the
 * accessible list that is its twin are both rendered from this array, so they cannot disagree about
 * a subsystem, and there is never a second file with the content of a node.
 *
 * Why the module is a path and not a URL: a URL needs the commit of the checkout, and the commit
 * belongs to the build and not to the source. The builders of the URL live in
 * `apps/web/lib/repository.ts`.
 *
 * Why this file imports nothing and reads nothing: the page of the architecture belongs to the
 * recorded demo, and the recorded demo calls nobody (ADR-042, ADR-043).
 */

/**
 * One record of a decision that explains why a subsystem exists.
 *
 * Why the record carries its own path: the link of the page opens the file of the record in the
 * repository, and a link built from a number alone would have to guess the name of the file.
 */
export interface ArchitectureRecord {
  /** The number of the record, as the file of the record begins with it. */
  readonly number: string;
  /** The title of the record, word for word as the file of the record carries it. */
  readonly title: string;
  /** The path of the file of the record, from the root of the repository. */
  readonly path: string;
}

/**
 * One subsystem of the system, and everything the page shows about it.
 *
 * Why the summary is one sentence: it is what the drawer of the engineering shows and the title of
 * the anchor of the picture, and a paragraph is neither.
 */
export interface ArchitectureNode {
  /** The identifier of the node. It never changes: it is the key of the list and the anchor of the node. */
  readonly id: string;
  /** The name of the subsystem, short, and the same word in the picture and in the list. */
  readonly label: string;
  /** The plain sentence that says what the subsystem does. */
  readonly summary: string;
  /** The path of the file of the module, from the root of the repository. Never a URL. */
  readonly module: string;
  /** The records that explain why the module exists. There is always at least one. */
  readonly records: readonly ArchitectureRecord[];
}

/**
 * The six subsystems of the system, in the order of the run.
 *
 * Why the order is the order of the run: the guard reads the ledger, the copy of the ledger decides
 * what the guard may read, the simulator builds the ledger, the calculator does the arithmetic on
 * what it read, the verifier checks what the answer said, and the recorder writes down what
 * happened. The picture draws the six in that order and the list lists them in that order.
 *
 * Why every path and every record was checked before this array was written: a node that points at
 * a file that does not exist is a lie the site tells, and the test of the nodes refuses it.
 */
export const ARCHITECTURE_NODES: readonly ArchitectureNode[] = [
  {
    id: "query-guard",
    label: "Query guard",
    summary:
      "The guard that only lets a query through when it is one single read of the tables of the ledger, so the model cannot write, cannot drop and cannot read the internal tables.",
    module: "ledgerlens/tools/sql_guard.py",
    records: [
      {
        number: "ADR-005",
        title: "Text-to-SQL with a guard and a read-only connection",
        path: "docs/decisions/ADR-005-guarded-text-to-sql.md",
      },
    ],
  },
  {
    id: "scoped-ledger-copy",
    label: "Scoped ledger copy",
    summary:
      "The copy of the ledger that holds only the rows of one account, so a query cannot return the rows of another customer.",
    module: "ledgerlens/api/accounts.py",
    records: [
      {
        number: "ADR-038",
        title: "The live run reads the ledger of the branch of the visitor",
        path: "docs/decisions/ADR-038-the-live-run-reads-the-ledger-of-the-branch-of-the-visitor.md",
      },
      {
        number: "ADR-045",
        title: "The ledger of the recorded demo is a published artifact of the site",
        path: "docs/decisions/ADR-045-the-ledger-of-the-recorded-demo.md",
      },
    ],
  },
  {
    id: "decimal-calculator",
    label: "Decimal calculator",
    summary:
      "The arithmetic of the money, done with decimal numbers and named operations, so that a rate never becomes a rounding error.",
    module: "ledgerlens/tools/calculator.py",
    records: [
      {
        number: "ADR-001",
        title: "Domain, payment investigation",
        path: "docs/decisions/ADR-001-payment-investigation-domain.md",
      },
      {
        number: "ADR-007",
        title: "Answer verification with an NLI model",
        path: "docs/decisions/ADR-007-nli-verification.md",
      },
    ],
  },
  {
    id: "deterministic-simulator",
    label: "Deterministic simulator",
    summary:
      "The builder of the ledger of the run, with a fixed seed and with the real public data where it exists, so the same command always writes the same rows.",
    module: "ledgerlens/sim/pipeline.py",
    records: [
      {
        number: "ADR-009",
        title: "Public data first, simulation only for the gaps",
        path: "docs/decisions/ADR-009-public-data-first-simulation-for-gaps.md",
      },
    ],
  },
  {
    id: "verifier",
    label: "Verifier",
    summary:
      "The step that gives every claim of the answer a verdict, so a sentence that the evidence does not back never reaches the visitor as true.",
    module: "ledgerlens/verify/checks.py",
    records: [
      {
        number: "ADR-007",
        title: "Answer verification with an NLI model",
        path: "docs/decisions/ADR-007-nli-verification.md",
      },
    ],
  },
  {
    id: "trace-recorder",
    label: "Trace recorder",
    summary:
      "The recorder of every run of the agent, which writes the public events that the recording of this site replays.",
    module: "ledgerlens/observability/trace.py",
    records: [
      {
        number: "ADR-013",
        title: "The public trace is a versioned contract",
        path: "docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md",
      },
    ],
  },
];

/** Every symbol this module exports, so that a reader sees the whole surface at once. */
export const __all__ = ["ArchitectureRecord", "ArchitectureNode", "ARCHITECTURE_NODES"] as const;
