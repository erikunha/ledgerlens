---
type: adr
status: accepted
date: 2026-11-15
---

# ADR-036: The limitation of the zeroization of the key of a visitor

Status: accepted. Date: 2026-11-15.

## Context

The limitation of the zeroization is one sentence: the product never writes the key of the visitor to a file, a log or
a trace and drops it when the credential ends, but nobody can promise that no copy of the text of the key survives in
the memory of the interpreter or in a swap of the operating system. The product promises that the key does not LEAVE
the process, and it does not promise that the memory of the machine is ERASED (FR-021).

That limitation is already in the repository, and this ADR does not declare it a second time. It is declared in
[ADR-033](ADR-033-the-ephemeral-credential-vault.md), in the paragraph that says that the runtime cannot guarantee
the zeroization of the memory, and it is disclosed to the visitor by
[ADR-035](ADR-035-the-facade-of-the-live-mode.md), which puts the header `X-LedgerLens-Key-Erasure` on the answers of
the live mode. What is missing is the scope of the promise: which half of it is a promise, where it is kept, and what
the product is allowed to say out loud about it. An ADR that repeats a paragraph of another ADR without deciding
anything is not an ADR, so this one decides the scope and names the boundaries, and the trace boundary is the one that
no ADR named yet.

The scope matters because the two halves of the sentence are not of the same kind. The first half is a claim about
what the product does, and it can be kept and proved: the code of the repository writes the key of a visitor to no
file, to no log, to no trace, to no answer and to no error, and it drops it when the credential ends. The second half
is a claim about what the machine does, and no runtime of the language can keep it: the interpreter may copy the text,
the garbage collector may keep a copy alive, and the operating system may write the page of the memory to the disk in a
swap. A promise that cannot be kept is worse than a limitation that is stated, and a limitation that is stated in a
document nobody reads is a limitation that does not exist for the visitor.

Three constraints of the repository shape the decision. The domain layer never imports the API layer and never writes
SQL, so the promise is kept by the domain, by the facade and by the boundary of the trace, and each of them keeps it
in its own layer. Every module carries a docstring, an `__all__` and a test, and the whole suite runs offline with no
key, so every promise of the live mode is proved with a marker key and never with a provider. And the numbers of a
run are money and never come out of the model, which is the same discipline applied to the words of a promise: a
promise that the code does not keep is not a promise either.

## Decision

**The promise of the live mode has two clauses, and only one of them is a promise.** The first clause is the
containment: the product never writes the key of a visitor to a file, a log, a trace, a telemetry event, an answer or
an error, and it drops the key when the credential ends. The second clause is the limit: the product does not promise
that the memory of the machine is erased, and it does not promise that no copy of the text of the key survives in the
memory of the interpreter or in a swap of the operating system. The two clauses are never merged. A text that says
that the key is stored claims more than the product can keep, and a text that says that the key is erased claims
something no runtime can promise.

**The containment is kept at four named boundaries, and the trace boundary is the last one.** Each boundary is a place
where the key would leave the process, and each of them holds it:

- the adapter of the provider scrubs the credential of the run out of the error, in the message and in the chain of the
  error, before the error leaves the adapter (`ledgerlens/byok/adapter.py`);
- the vault scrubs the exact text of the secrets it holds out of a text and then applies the `redact` helper of the
  observability package, which is the one definition of what looks like a key in the repository
  (`ledgerlens/byok/vault.py`);
- the coordinator of a run scrubs the answer, the error, the payload of an event and the line of a log with the secret
  of the run and with the secrets the vault holds (`ledgerlens/api/live_run.py`);
- the boundary of the trace redacts the payload of the event as it is published: the sanitizer walks the payload and
  applies `redact` to every name and to every text, and it drops the forbidden names, which are the authentication
  keys of the well known headers (`ledgerlens/observability/trace_event.py`).

The boundary of the trace is the last one, and it is the one that holds when nobody scrubbed anything: the event is
redacted as it is written, so a payload that was assembled outside the coordinator, a payload that carries the key as
a field name and a payload that carries it inside a list reach the file of the trace without it. The two layers are
both needed, for the reason that ADR-033 gave: the helper only knows the shapes of the keys of the known providers,
and only the vault and the coordinator know the exact text of the key of this visitor.

**The wording of the two clauses is fixed in two constants of the API layer, and they never do the work of each
other.** The constant of the storage says what the product keeps, and the constant of the erasure says what the product
cannot promise. The header of the storage does not claim an erasure, and the header of the erasure does not claim a
storage. A test of the API asserts that the text of the storage does not carry the word of the erasure, because a
promise of the storage that claims an erasure is a promise the product cannot keep.

**The limitation travels in the answer, on the answers that hold or spend a credential.** The header of the erasure is
on the answer of the session, the answer of the credential, the answer that starts a run, the state of a run, the
events of a run, the cancellation of a run and the cost of a run. The four answers that hold no key and spend nothing,
which are the catalogue of the models, the price of a model, the forgetting of a key and the end of the session, carry
none of it: a limit about a key that is not there says nothing to the visitor. The header of the storage is on the two
answers that take a key or a session, the answer of the session and the answer of the credential.

**The zeroization that the code performs is a best effort, and the code calls it a best effort.** The secret of a
credential lives in a buffer, and the buffer is overwritten when the credential is dropped
(`ledgerlens/byok/vault.py`), and the secret of a run lives in a holder of its own, and the holder is emptied when the
run ends (`ledgerlens/api/live_run.py`). Neither of the two is a promise about the machine, and neither of them is
described as one in the code, in the docstring of the module or in the comment that says it.

**The repository does not claim the erasure, and this is not a matter of style.** No answer, no document and no
comment of the repository may say that the memory of the machine is erased, that the key is gone for good or that the
product keeps the secret in a safe place. The wording that is allowed is the wording of the two constants, and the
disclosure of the limit is the one of the header of the erasure. A deployment that disables the swap of the operating
system makes the erasure more likely, and it does not change what the product says: the promise of the product is the
one that the code can keep in any deployment.

## What the product says out loud to the visitor

The answer of the live mode carries two sentences, and they are the whole of the promise. The first one is the
containment:

> the key is not stored: it lives in the memory of the server and the credential is dropped when the session ends

The second one is the limit:

> the memory of the machine cannot be guaranteed to be erased: the server drops the key when the credential ends, but
> no runtime can promise that no copy of the text of the key survives in the memory of the interpreter or in a swap of
> the operating system

They travel in the headers `X-LedgerLens-Key-Storage` and `X-LedgerLens-Key-Erasure`, and the visitor reads them
before the first call of the provider, because the answer of the credential and the answer that starts a run carry
them. The product says that the key does not leave the process, and it says out loud that it does not promise that the
memory of the machine is erased. It never says the opposite.

## Alternatives considered

- **Disable the swap of the operating system, or lock the pages of the memory of the process, so that the erasure
  becomes closer to true.** The demo would ask the deployment for privileges that it may not have, and it would turn a
  product that runs anywhere into a product that has to be installed in a particular way. It would not touch the copies
  that the interpreter and the collector of the garbage make, so the header would still have to say what it says, and
  the product would pay a price for a promise it still could not keep.
- **Run the live mode of every visitor in a process of its own that dies with the session.** The machine may still hold
  the page of the memory in its swap, and the containment promise does not need it: the promise is kept by the four
  boundaries, and it does not depend on how the process ends.
- **Keep the key in a text and delete the text when the credential ends, instead of a buffer that can be
  overwritten.** A text prints itself, and the interpreter copies it into other strings that cannot be wiped. The
  buffer is what makes the wipe possible at all, and it is still only a best effort.
- **Leave the limitation in the documents of the repository and say nothing in the answer.** The visitor of the demo
  never reads the repository, so the limit would stay with the people who already know it, and the promise of the
  storage would claim more than the product can keep (FR-021).
- **Say only that the key is dropped when the credential ends, and not say that the memory may still hold a copy.**
  That is the promise the product cannot keep, and it is exactly the one that the header of the erasure refuses to
  make. A promise that cannot be kept is worse than a limitation that is stated.
- **Scrub the trace in the producer of the payload only, and leave the boundary of the trace without a redaction.**
  A payload that was assembled outside the coordinator reaches the sink, and the file of the trace is the last place
  where the key could land. The redaction belongs to the boundary, and it belongs there for the same reason the
  adapter scrubs the error of the provider.

## Consequences

- The promise of the live mode is two clauses. The first one is a promise the product keeps and the tests prove with a
  marker key; the second one is a limit that the product discloses out loud, and it is the same limit in every answer.
- The containment is kept at four named boundaries, the adapter, the vault, the coordinator of a run and the boundary of
  the trace. Each of them is a place where the key would leave the process, and each of them is covered by a test.
- The trace of a run carries no credential, whatever the shape of the payload: as the value of a field of a nested
  structure, as an item of a list, as the name of a field, or as the value of a field whose name is an authentication
  key. The redaction happens at the boundary, so it holds even for a payload that nobody scrubbed, and the published
  contract of the trace holds anyway: a payload that lost its secret is still a payload that the schema accepts.
- The seven answers that describe a run or a credential carry the limit, and the four answers that hold no key and
  spend nothing carry neither the limit nor the promise of the storage.
- The two sentences are the only wording of the promise. A document of the repository, a comment of the code or an
  answer of the API that says the memory of the machine is erased contradicts this ADR, and the contradiction is a
  defect, not a nuance of the wording.
- The limitation stays declared in one place, in [ADR-033](ADR-033-the-ephemeral-credential-vault.md), and it stays
  disclosed in the answer by [ADR-035](ADR-035-the-facade-of-the-live-mode.md). This ADR does not repeat either of
  them: it pins the scope of the promise, names the boundary of the trace and fixes the wording.
- The product never promises more than it keeps, in the code and in the answer. A deployment that wants a stronger
  guarantee has to bring it, and it has to say that it is the deployment that brings it.
