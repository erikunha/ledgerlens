---
type: adr
status: accepted
date: 2026-11-21
---

# ADR-038: The live run reads the ledger of the branch of the visitor

Status: accepted. Date: 2026-11-21.

## Context

The contract of the live run already asks for the branch of the visitor. The request schema requires `sandbox_id`,
`account_id` and `expected_revision` (`specs/003-r3-bring-your-own-key/contracts/live-run-request.schema.json`), and the
plan of the run carries them (`ledgerlens/api/byok.py`). The branch of the visitor is the only artifact that holds the
records of one visitor: the base is the account scoped copy that the resolver cuts and caches
(`ledgerlens/sandbox/snapshot.py`), and the branch is that base with the events of the visitor applied
(`ledgerlens/sandbox/projector.py`). The branch layer owns the two checks that matter: the ownership of the branch and
the proof of its own state (`ledgerlens/sandbox/branch.py`).

The live path does not read any of that. The case of the demo builds the agent with no ledger at all, so the tools of
the agent fall back to the configured ledger (`ledgerlens/tools/sql.py`, `ledgerlens/tools/ledger_api.py` and
`ledgerlens/verify/escalation.py`), which is the whole published ledger of the repository, with every account of it.
Nothing checks the account of the plan against the rows the model may read. A model that writes SQL may therefore read
the rows of another customer, and the run would answer about records the visitor does not own. ADR-037 says this out
loud and leaves it for the milestone that comes next.

There is a second reason to settle this now. The bridge of ADR-037 made every call of the agent go through the caller
of the run, so the budget, the trace and the report of the cost hold over the whole agent. What the agent does with
those calls is still undecided: a run that spends the money of the visitor to read the ledger of the repository is a
run whose answer is about somebody else.

Two candidate designs were examined.

**(a) The live run reads the branch through the branch layer.** The branch is the truth of the visitor, the ownership
check and the proof of the state already live there, and a live run that answers about a ledger other than the one on
the screen would contradict the sandbox in front of the same visitor. It costs a dependency of the live application,
one public method on the branch layer and one file per run.

**(b) The live run cuts its own scoped copy from the base**, the way the resolver does. It is cheap, and it is honest
about the account, but it is a second truth about the visitor: the visitor sees their own mutations in the sandbox and
the live run would answer about the base, and the `sandbox_id` and the `expected_revision` of the request would be
decoration.

Two obstacles stand in the way of (a), and the decision has to answer both.

The first is the shape of the state. The projection of a branch lives in an in-memory SQLite connection
(`ledgerlens/sandbox/projector.py`), while the tools of the agent take a path of a database file. The state has to be
materialized before the agent can read it.

The second is the session. The two facades sign their cookie with two different keys
(`ledgerlens/api/byok.py` and `ledgerlens/api/sandbox.py`), so the same cookie yields two different session
identifiers, and the ownership check of the branch would refuse every branch. ADR-035 says on purpose that the two
facades are two visitors, and the wiring of one issuer for the two of them is a decision of the deployment.

## Decision

**The live run reads the ledger of the visitor through the branch layer of the sandbox, and the branch is the only
truth of the visitor.** The live path does not cut a second scoped copy and it does not write to the branch.

**The state of the branch is materialized into a file of the run, and the file holds the rows of the account of the
branch and the counterparties of the transactions of that account.** The counterparty of a transaction of the visitor
is part of the story the run reads, and the name of that merchant is on the disk of the server for the length of the
run. The file holds no row of another account, so the isolation of the visitor holds. The materialization is a copy of
the projected connection and never a statement written by hand, and the base is only ever read.

**The branch is resolved before the first call of the provider.** A branch of another session, an expired branch, a
branch that cannot prove its own state, an account that is not the account of the branch and a revision that moved are
all refused with a readable answer, and no provider is called, so no money is spent.

**The case of the demo never falls back to the ledger of the configuration.** A run without a ledger of the visitor is
a refusal, because the fallback would hand the model the rows of every account of the repository.

**The ledger of the run travels in the plan, with its canonical hash and its revision, and the trace of the run says
which ledger was read.**

**A live application without a branch layer refuses every run that names a branch, with a readable reason.** It never
answers with the ledger of the configuration.

**The deployment wires one session issuer and one store for the two facades.** The wiring stays a decision of the
deployment (ADR-035), but the two facades have to accept the same issuer for it to be possible, and they already do.

**The layer boundary holds.** The branch layer owns the projection and the materialization, the facade owns the request
and the plan, and the case owns the agent. The new module of the sandbox does not import the API.

## The interface of the milestone

The two sides of the milestone are coded against each other through this interface, and this ADR fixes it before the
code, so that the two implementers never touch the same file.

In `ledgerlens/sandbox/ledger_view.py`, new:

```
@dataclass(frozen=True)
class LedgerView:
    """The ledger of ONE visitor, materialized in a file the tools of the agent can read."""

    path: Path
    account_id: str
    branch_id: str
    revision: int
    canonical_hash: str
```

and two refusals of the layer, beside the ones the layer already has:

```
class LedgerAccountMismatch(Exception):
    """The account of the request is not the account of the branch."""

    code = CODE_ACCOUNT_MISMATCH


class LedgerRevisionMoved(Exception):
    """The revision of the branch moved away from the revision the request expected."""

    code = CODE_REVISION_MOVED
```

The two refusals carry a code and a message, exactly like `BranchHashMismatch` carries `HASH_MISMATCH`, so a
refusal of the reader of the ledger is a refusal of the family of the sandbox. The codes are `ACCOUNT_MISMATCH` and
`REVISION_MOVED`, the codes the live facade already publishes for the same two cases.

On `BranchLayer`, one new public method:

```
def ledger_view(
    self,
    session_id: str,
    branch_id: str,
    *,
    account_id: str,
    expected_revision: int | None = None,
    target: Path | str,
) -> LedgerView:
    """The ledger of the visitor, materialized in the file of the target."""
```

The method does, in this order: the ownership check (a branch of another session raises `BranchNotFound`, the same
answer as a branch that does not exist), the expiry (`BranchExpired`), the account (`LedgerAccountMismatch`), the
revision (`LedgerRevisionMoved` when the expected revision is not the current one), the proof of the state
(`BranchHashMismatch`), the move of the idle deadline and only then the materialization in the target. The file is
written only when every check passed, so a refused branch leaves no file behind.

The move of the idle deadline comes after the proof of the state, so a branch that cannot prove its own state is never
touched. A live run is an activity of the visitor on the branch, exactly like a read of the status is, so the branch
of a visitor who is looking at it does not expire under the feet of the visitor. The file of the run is a copy of the
state, so the run itself is safe even when the cleanup job deletes the branch.

The plan of the run carries the view, so that the case and the trace can name the ledger that was read:

```
@dataclass(frozen=True)
class LiveRunPlan:
    ...
    ledger: LedgerView | None = None
```

## What this milestone does not have

- No call to a real provider. The tests use the fake adapter of the domain.
- No frontend, no page, no SSE bridge, no cost panel.
- The local NLI judge stays out of the budget: it is not a provider model (ADR-037).
- No second model in a run (FR-013).
- No mutation from the live path: the live run reads the ledger of the branch and never writes to it.
- No change of the contract of the request: the request already names the branch and its revision.
- No change of the offline path (FR-029).
- No memory of the visitor across runs.
- No move of `scoped_ledger` out of the API layer. `ledgerlens/sandbox/snapshot.py` imports it from
  `ledgerlens/api/accounts` today, and that debt is older than this milestone. The new module of the sandbox does not
  repeat it.

## What it costs

The live application gains a dependency (the branch layer), one public method on the branch layer, one new module in
the sandbox, one file per run in the runtime folder that the end of the run removes, and a rule of wiring for the
deployment.

## Alternatives considered

- **(a) The live run cuts its own scoped copy from the base.** Cheap and honest about the account, but it is a second
  truth about the visitor, and it leaves the branch and the revision of the request as decoration.
- **(b) The live run asks the sandbox facade over HTTP.** A network hop inside the server, and the facade answers JSON
  rows that the agent cannot query.
- **(c) The live run reads the projected state in memory.** The tools of the agent take a path, and the connection does
  not outlive the request.
- **(d) The live run keeps the ledger of the configuration and only names the account.** An account that nothing checks
  against the rows: the model may read the rows of every account.
- **(e) The live run keeps the ledger of the configuration but the tools refuse a SQL that names another account.** The
  refusal would live in the tool, and the tool is written by a model: the guarantee would be as strong as the prompt
  that asks for it.

## Consequences

The answer of a live run is about the ledger that the visitor sees. The tools of the agent cannot read the rows of
another account whatever SQL the model writes. The file of the run holds the rows of the account of the visitor and the
counterparties of the transactions of that account, so the name of a third party is on the disk of the server for the
length of the run, and the file goes away when the run ends. The trace names the ledger of the run, with the branch, the
revision and the canonical hash of the state that was read. The branch layer keeps the single implementation of the
ownership and of the proof of the state, so the two facades cannot disagree about what a branch holds. The deployment
has to wire one issuer for the two facades. A live application without a branch layer refuses the runs that name a
branch instead of silently reading the whole ledger of the repository.
