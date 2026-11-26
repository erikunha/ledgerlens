# The baseline of the orchestration studio

The studio of the multi-agent orchestration is experimental and it is measured against the path that the repository
ships today. A reference that moves is not a reference, so this page freezes the behaviour of the shipped path at a
named commit and says what a reader of a comparison of the studio has to compare against.

The red line is [ADR-P007](../../docs/design/adrs/ADR-P007-no-multiagent-by-default.md): the runtime stays a single agent
with a deterministic verifier until a paired comparison measures a gain. This page is the arm that the studio has to
beat.

## The commit of the baseline

| What | Value |
| --- | --- |
| The commit the baseline was frozen at | `b407c10e83db65a551b4beeb104493d8e948a8d5` |
| The message of that commit | `feat(runtime): the turn ceiling, the vector protocol and the numbers` |
| The branch | `feature/v3` |

The commit is the one that the code of the shipped path had when this page was written. The test
`tests/orchestration/test_baseline_is_frozen.py` checks that the commit exists in the repository, so a page that names
a commit that was never pushed fails.

## The agent of the shipped path

The shipped runtime is one agent: `ledgerlens/agents/integrator.py`, built by `build_integrator`. It reads the
conversation, the plan of the investigation and the history of the session, and it returns an `InvestigationResult`.

| What | Where |
| --- | --- |
| The agent | `ledgerlens/agents/integrator.py`, `build_integrator` |
| The tools of the agent | `ledgerlens/agents/modern.py`, `build_investigation_tools` |
| The system prompt | `ledgerlens/agents/modern.py`, `DEFAULT_SYSTEM_PROMPT` |
| The result | `ledgerlens/schemas.py`, `InvestigationResult` |

The agent never decides a number and never moves data. Every amount of the result comes out of a tool, and the
verifier decides what the result claims.

## The six tools of the agent

The tools are the six that `build_investigation_tools` returns, in the order of the contract.

| The tool | What it does |
| --- | --- |
| `query_ledger` | writes the statement that reads the ledger, with the model of the slot `sql` |
| `get_ledger_record` | reads one record by its id, from the internal ledger service |
| `search_policies` | searches the corpus of the policies with the model of the slot `policy` |
| `get_reference_fx` | reads the reference rate of a pair and of a day from the public source |
| `calculate` | computes an amount with `Decimal`, and it is the only tool that computes money |
| `recall_cases` | reads the long-term memory of the cases that were already resolved |

The digest of the file that declares the six tools is
`e72ab023199d0a42c62858efb6388fd7ae8ec8f940cdb542cef45cd4e02bcd17`, and the test checks that each of the six names is
still declared by the source of the repository. A tool that is renamed or that disappears moves the baseline, and the
test says so.

## The verifier

The verifier is code and a local cross-encoder, and it is never a provider model.

| What | Where |
| --- | --- |
| The verification | `ledgerlens/verify/checks.py` |
| The claims and the amounts | `ledgerlens/verify/claims.py` |
| The escalation and the recommended action | `ledgerlens/verify/escalation.py` |
| The thresholds | `ledgerlens/verify/thresholds.json` |

The numbers are checked by code with `Decimal`, the coherence is checked by rules over the rows the queries returned,
and only the text claims with no amount go to the NLI model, which is the local cross-encoder
`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` with the thresholds of the file. The thresholds were calibrated with a
sweep over 70 cases and the calibration is written in the file with the rule that chose it.

## The snapshot of the comparison

Both arms of the comparison read the same snapshot, and the snapshot is named here.

| What | Value |
| --- | --- |
| The set of the comparison | the 31 cases of `data/eval/eval_cases.jsonl` |
| The digest of the set | `28f16cabcbb7391112ac6a7bbe6567ec877eeba3207dd1caa3c3933761362351` |
| The ledger of the set | the canonical sample ledger, `data/ledger.db` |
| The digest of the ledger | `aa342e39735acc7a0deb9e7795f41200566e776d3029edb13188a7fe6d1b9b92` |
| The scenarios of the ledger | `S01` to `S14` |
| The snapshot of a branch | the published snapshot of the scenario, named by `base_snapshot_id` |

The name of the snapshot of the comparison is the digest of the set and the digest of the ledger, and the test checks
that both are still the digests of the files of the disk. A comparison whose arms read different ledgers is not a
comparison, and the digest is what says that they did not.

## What the baseline does not say

- **It does not say that the studio is better.** It says what the studio has to beat, and the studio is off in the
  shipped configuration until a paired comparison measures a gain.
- **It does not freeze the thresholds of the verifier.** The thresholds move when the calibration moves, and the
  calibration is written in `ledgerlens/verify/thresholds.json` with its own sweep.
- **It does not name the model of the run.** The model of each slot is chosen by the task it does
  ([ADR-078](../../docs/decisions/ADR-078-the-model-of-each-slot-is-chosen-by-the-work-it-does.md)), and both arms of
  the comparison use the same decision, because a comparison over two models is a comparison over two questions.
