# Runbook: the durability of a run

This runbook is for the person who has to restart a run that died, read the state of a run, or roll the
journal of a run back. The journal of a run is the durable record of the steps of the run, and the restart of
a run reads it. The branch of a visitor is durable by itself (the idempotent commit, the pure projection), and
this runbook never touches it.

## The states of a run

A run is in one of these states, and the journal of the run says which:

| State | What it means | What the journal shows |
| --- | --- | --- |
| Running | The run is writing its steps | An intent with no result for the step that is running |
| Died | The run stopped between the intent of a step and its result | An intent with no result, and no more entries |
| Completed | The run wrote the result of every step | An intent and a result for every step |
| Needs a new run | A step of the run may not be run again | An intent with no result for a step that is not idempotent, or a step whose snapshot changed |

## The restart of a run

1. Read the journal of the run. The journal is the file `run_journal.jsonl` in the folder of the session that
   owns the run, beside the folder of the branch.
2. For every step with an intent and a result, reuse the output of the journal. The step does not run again.
3. For every step with an intent and no result:
   - If the step is idempotent (a read, or a write the store makes idempotent, like the commit of the branch),
     run it again with the same idempotency key. The effect does not happen twice.
   - If the step is not idempotent, do not run it again. The run needs a new run, and the reason is named.
4. If the snapshot of a step changed, the step needs a new run: a number that was read from another branch is
   not the number of this case.
5. The restart never rehydrates a credential of a visitor: a resume without a fresh authorization stops with
   that reason.

## The unknown status

A call of the provider whose answer never arrived is marked with the unknown status. The cost of the call is
unknown and never zero, and the run neither repeats the call nor claims a success it cannot prove.

What a person has to do with it: the call that is unknown may have spent the money of the visitor without the
repository knowing. Do not repeat the call by hand: a repeated call may spend the money twice for the same
answer. Read the journal of the run, name the call that is unknown, and decide with the person who owns the
run whether the case goes to a person.

## The rollback of the journal of a run

The journal of a run is append only, and the rollback of a run is never the deletion of the journal. To roll
the journal of a run back:

1. Stop the run. A run that is writing its journal is a run that is not rolled back.
2. Read the journal and name the step that has to be rolled back.
3. Start a new run with the steps that are still valid. The journal of the old run stays, because the journal
   is the evidence of what the run did, and the evidence is never deleted.

The branch of a visitor is never rolled back by the journal: the branch has its own undo, and the journal of
a run never writes to the branch.
