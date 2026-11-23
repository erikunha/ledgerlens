---
type: adr
status: accepted
date: 2026-11-23
---

# ADR-063: The path of the machine of the owner is not a decision and is not published

Status: accepted. Date: 2026-11-23.

## Context

The repository has two rules that pull in opposite directions, and until now nothing said which one wins.

The first rule is that an accepted record is never edited: a change of an accepted decision is a new record
(`AGENTS.md:20`). The reason is that a record is the history of a decision, and a history that is rewritten is a
history that lies.

The second rule is that the tree of the repository holds no path of the machine of the owner. The test
`tests/test_public_clean.py` refuses a tracked file that names the home of a person, in the shape that
Linux uses and in the shape that macOS uses, because a path of the machine of the owner tells a reader where the
private folders of the owner live, and the local notes and the local planning folders of the owner have to stay out
of git.

The two rules met in [ADR-041](ADR-041-the-interactive-diagrams-are-rendered-outside-the-repository.md), an accepted
record that shows the interface of the tool that renders the diagrams: two commands of `node`, with the path of the
tool and the path of the folder of the artefacts written out. Both paths were the paths of the machine of the owner.

The rule of the paths did not catch them, because the regex of the test knew the two shapes of a path of Linux and
not the form that macOS uses, where the home of the user is written with a tilde. So the tree carried two machine
paths for a year and the guard said nothing.

## Decision

**A path of the machine of the owner is not a decision, it is not publishable, and it may be replaced by a neutral
form inside an accepted record, with a new record that says what changed and why.**

### 1. What the rule of the accepted record protects and what it does not

The rule of the accepted record protects the decision, its context, its alternatives and its consequences. It does
not protect the environment in which the decision was taken, because the environment of the owner is not a decision of
the repository and it does not belong to the reader of the repository.

A record that names the path of the machine of the owner publishes something that the repository does not own and
that the owner cannot change for anybody else, and it does it in a place where a reader looks for the history of a
decision. The rule of the paths wins over the rule of the record in this narrow case, and the change is published in a
new record so that a reader who remembers the old text knows that the decision did not move.

### 2. The neutral form

A path of the machine of the owner is written as a description of what it is, between angle brackets:

```
<the tool of the owner, outside the repository>
<the folder of the artefacts, outside the repository>
```

The description has to say what the path is for, because a command with a placeholder that says nothing is a command
that nobody can run.

### 3. The guard learns the form of macOS

The regex of `tests/test_public_clean.py` refuses a path that starts with `~/` as well. The form is the one that
macOS uses for the home of the user, and it is the form in which the paths of this repository were written.

The branch that the change adds does not touch the workflow of the continuous integration, which keeps the cache of
the vector model in a dot folder of the home of the user, because a dot folder is not the home of the user.

### 4. What this record changed

The two commands of ADR-041 now carry the neutral form. The decision of ADR-041, that the interactive diagrams are
rendered outside the repository by a tool of the owner with two commands and a source of the schema in the tree, did
not move.

## Alternatives considered

- **To leave ADR-041 as it is and to leave the regex as it was.** Refused. The tree would carry the paths of the
  machine of the owner in a record, and the guard would keep saying that it is clean.
- **To make the guard spare the accepted records.** Refused. The guard would stop at the folder where the paths are
  most likely to be written, and it would do it for a reason that has nothing to do with the nature of the record.
- **To rewrite ADR-041 in full, as if the decision had been taken with the neutral form.** Refused. The record would
  pretend that the owner had never written the path, and the history of the decision is not the thing to clean up.
- **To move the two commands of ADR-041 to a document that is not a record.** Refused. The commands are the interface
  of the decision, and a record that names an interface without showing it is a record that sends the reader looking.

## Consequences

- **The tree carries no path of the machine of the owner.** The guard of `tests/test_public_clean.py` now catches the
  form of macOS, and the two paths of ADR-041 are gone.
- **A record may be touched without its decision moving.** The only case is this one, and it leaves a record of the
  change, which is what a reader needs to trust the record that stayed.
- **The same leak can be found in the other records.** The test runs over the whole tree, so any other path of the
  machine of the owner is caught by the gate. A path that is found in a record is replaced by the neutral form of the
  section 2 and the change is recorded in a new record, with the same rule.
