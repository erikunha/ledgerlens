# The versioned memory

The memory of the repository holds what a verified case concluded, and the versioned memory adds the four
things the case memory of today does not have: a version, a trust tier, an owner and an approval state. This
page names the tiers, the states of a record, the reason of a quarantine and the rule that a recalled text is
data.

## The trust tiers

Every record carries a tier, and the tier travels with the record, because the reader of a recall has to see
how the fact entered the memory.

| Tier | What it says |
| --- | --- |
| `observed` | One verified case observed the fact. This is the tier of every record when it enters the memory, and it is the tier of the records of the case memory of today. |
| `corroborated` | Two cases observed the same fact. The record is one, with the two sources, deduplicated by the hash of the fact. |
| `approved` | A promotion approved the record, with a recorded approval that names the approver, the date and whether the reviewer was simulated. |

## The states of a record

A record is `active` or `quarantined`. The quarantine is a state and not a deletion: the record that was meant
to steer the agent stays in the store with its reason, so the attempt is readable, and a person may release it.
The release is a version of the record like any other, with the name of the person that released it.

A quarantined record is absent from every retrieval, including the query it matches best. A quarantine that
only catches the best match is a filter that the attack reads, and the quarantine of the repository is not
that filter.

## The reason of a quarantine

The detection is deterministic: the patterns that name an attempt to steer the agent are code of the
repository, in `ledgerlens/memory/quarantine.py`. A text that asks the agent to ignore the policies, that
tells the agent which tool to call, that names the system prompt, that asks to skip the verification or that
claims the authority to approve a payment action is an attempt, and the reason of the quarantine names which
one it is. A reason that nobody can read is not a reason, so a quarantine with no reason is refused.

## A recalled text is data

The recalled text arrives as the output of a tool, and the code of the repository decides which tools exist
and what they may do. A record whose text claims tool authority changes neither the tools of the agent nor its
system prompt, and the test of the repository proves it. The boundary between the memory and the policy is not
negotiable by a text that a case wrote.

## The rule of the verified source

Only what was verified gets in. A proposal without a verified source is refused, and the case memory of
[`ledgerlens/memory/long_term.py`](../ledgerlens/memory/long_term.py) keeps refusing an investigation whose
verdict is not `supported`. The rule of the versioned memory is the rule of the case memory read from the
other side.

## The snapshot of a run

A run reads a frozen snapshot of the memory, and the digest of the snapshot travels with the run and with the
published bundle, so a replay of an old case reads the memory of its generation and the reader of the bundle
can check it. The verifier of [`ledgerlens/replay/verdict.py`](../ledgerlens/replay/verdict.py) refuses a
bundle whose digest does not match the snapshot it names.

## Where the memory lives

The records, their versions and their approvals live in the folder of the memory of the session, beside the
file of the case memory, because the memory of a session lives in the folder of that session (ADR-030). The
deletion of the memory of a session takes the records of its owner and nothing else, and the folder of the
session is gone with the expiry of the session.

## Links

- [the case memory](../ledgerlens/memory/long_term.py)
- [the versioned store](../ledgerlens/memory/versioned_store.py)
- [the quarantine](../ledgerlens/memory/quarantine.py)
- [the snapshot](../ledgerlens/memory/snapshot.py)
- [ADR-030, the case memory scoped to the session](decisions/ADR-030-case-memory-scoped-to-the-session.md)
- [ADR-089, the studio stays off in the shipped configuration](decisions/ADR-089-the-studio-stays-off-in-the-shipped-configuration-and-the-comparison-was-registered-before-it-ran.md)
