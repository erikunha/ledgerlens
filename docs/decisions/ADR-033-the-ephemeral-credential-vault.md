---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-033: The ephemeral credential vault of the live mode

Status: accepted. Date: 2026-11-14.

## Context

The third story of the R3 specification asks for a key that never reaches a file, a log, a trace or an answer to the
client (FR-003, FR-004). The visitor pastes a key of a provider into the live mode, the demo runs a real case with it,
and the promise is that the key lives in the memory of the server process of the session and disappears when the
session ends (FR-002, FR-022). A leaked key is the worst failure this feature can have, and it is the reason the
feature comes last.

The design note `LL-R3-02` puts the lifecycle in one line: `unregistered -> received -> handle_active -> run_reserved
-> run_in_progress -> revoked/expired`. It says that the credential object is held by a `CredentialVault` in the
memory of the process, keyed by an opaque random handle that is mapped to the server session, to the provider and to
the moments of the creation and of the expiry, and that the secret is never returned nor serialized. The note also
names the threats that the decision has to answer: a marker key inside a forced exception of a provider must not
appear in the logs, in the stream, in the trace, in the interface or in the telemetry, and the session B must not be
able to consume the handle of the session A.

Three constraints of the repository shape the decision. The domain layer never imports the API layer and never writes
SQL, so the vault is a domain object with no persistence of any kind. Every module of the repository carries a
docstring, an `__all__` and a test, and the clock is injected, because the expiry is decided by the server and a test
that waits for an hour proves nothing. And the whole suite runs offline with no key, so the vault is proved with marker
keys and never touches a provider.

Two questions were open. The first is where the secret lives between the moment the visitor pastes it and the moment
the run ends. The second is what the vault can promise about that secret once the credential is gone, because a
runtime that copies a string cannot promise that every copy of it is erased.

## Decision

**The secret lives in the memory of the process and nowhere else.** The vault keeps it in a buffer of the process and
writes it to no file, no database, no log, no trace, no telemetry event, no environment variable and no URL
(FR-003). It is not stored in the folder of the runtime of the configuration, and it is not kept in the environment of
the process, so two visitors of the same deployment cannot see each other's key through a shared setting. The
credential that the client holds is the handle and nothing else, and the raw key is never returned in any response
(FR-004).

**The handle is opaque, random and never derived from the secret.** The handle is a random token of the process, and
it is not a digest, a cipher or a signature of the key. A handle that is derived from the secret would tell something
about it, and a handle that a visitor could guess would let another visitor try to use it. The handle carries the
provider, the moment of the creation and the moment of the expiry, and it never carries the secret, not in a field and
not in its representation (FR-005).

The provider of the handle is one of the providers that the registry publishes, and the vault refuses a name that is
not in that list. The published contract of the handle enumerates the providers of the live mode, and a vault that
accepted any text would break that contract on the day a visitor pastes a name that nobody publishes. The list lives
in the registry, so the vault and the registry never disagree about what a provider is (FR-004).

The internals of the vault never show the key either. The secret of an entry lives in a buffer whose representation is
a marker, so a debug print, a `dataclasses.asdict` of the internals or a traceback with the locals of the vault cannot
leak it (FR-003, FR-018).

**The handle is bound to the session that owns it.** The vault refuses a handle presented by another session, and the
answer of that refusal is the answer of a handle that never existed, so a visitor cannot learn that the handle of
another session exists (FR-006, SC-002). The refusal of a handle of another session and the refusal of a handle that
does not exist are the same error with the same message. The tombstone of a credential that is gone is bound to the
session in the same way, so the end of a credential is never announced to a session that does not own it.

**The vault is bounded and expiring.** The vault holds a bounded number of credentials, and the oldest one is dropped
when the vault is full, and the vault says so in its log (FR-002). Every credential has a time to live counted from
its creation, an expired credential is dropped on the access and by the sweep, and the sweep runs on every access and
in a sweeper thread that the domain offers, so a vault that nobody touches still forgets (FR-022, SC-011). The
credential of a session dies with the session: the vault offers the drop of every credential of a session and the drop
on the restart of the process, because the memory of the process is the only place the key ever lived. The facade of
the live mode, which is the task of the next milestone, is what starts the sweeper thread and what calls the drop of
the session.

**A failure drops the credential.** The number of failures of a credential is bounded, and the credential is dropped
when the bound is reached (FR-023). A key that fails again and again is a key that does not work, and a visitor that
keeps it alive only spends more of it.

**The vault scrubs its own secret out of a text, and the adapter scrubs the key of the run out of the error of the
provider.** A provider exception can carry the key, and the key has to be gone from the log, from the trace, from the
error message and from the telemetry (FR-018). Two places do that work today. The adapter holds the key it injected
into the client of the provider, so the adapter scrubs that key out of the error, in the message and in the chain of
the error, before the error leaves the adapter. The vault replaces the exact text of the secrets it holds and then
applies the `redact` helper of the observability package, which is the one definition of what looks like a key in the
repository and which covers the keys the vault never held. The two layers are both needed: the helper only knows the
shapes of the keys of the known providers, and only the vault knows the exact text of the key of this visitor.

The promise of the scrub has a scope, and the scope is said out loud. It holds while the credential is alive and at
the boundary of the adapter, which is where the key still is. It is not a promise about a text that a credential which
is already dead produced: the vault does not keep the secret of a credential that is gone, on purpose, and a text that
such a credential produced cannot be scrubbed by a vault that no longer holds the key. The tombstone of a credential
that is gone carries the reason of its end and never its secret.

**The runtime cannot guarantee the zeroization of the memory, and this is disclosed.** The vault keeps the secret in a
buffer so that it can overwrite that buffer when the credential is dropped, and that is the best effort a runtime
offers. It is not a promise. The interpreter of the language may copy the text, the garbage collector may keep a copy
alive, and the operating system may write the page of the memory to the disk in a swap. The repository therefore
discloses the limitation (FR-021): the key is never written by the product to a file, a log or a trace, and the
product drops it when the credential ends, but nobody can promise that no copy of the secret survives in the memory of
the machine. The disclosure is in this ADR, and the interface of the live mode, which is the task of the next
milestone, is what will carry it to the visitor.

**The rule lives in one module and one test.** `ledgerlens/byok/vault.py` holds the whole rule and nothing else, and
`tests/byok/test_vault.py` proves it with a marker key: the tree of the repository and the folder of the runtime that
the configuration names are inspected for the marker, whatever that folder is, the environment of the process is
compared before and after, the records of the log are inspected, and the refusals are inspected for the marker.

## Alternatives considered

- **Keep the key in an encrypted file, in a database or in a secret manager of the deployment.** The demo would keep
  working after a restart, and the key would leave the process of the demo for the process of the secret manager. The
  promise of the specification is that the key lives in the memory of the session and nowhere else (FR-002), and an
  encrypted copy on the disk is still a copy on the disk. The cost of the decision is that a restart sends the visitor
  back to the key field, and that is a small cost next to a leaked key.
- **Derive the handle from the secret, with a keyed digest.** The handle would be stable and the vault would not need
  a table of handles. The handle would then be a function of the key, and a handle that leaks tells something about the
  key to whoever holds it, and a short keyspace makes a guess possible. A random handle says nothing at all.
- **Use the session identifier as the handle.** The visitor would see something they already know, and the handle
  would be guessable by any other visitor of the demo. The handle has to be unguessable, because it is the only
  thing that stands between the key of a visitor and a visitor who guesses it.
- **Keep the credential for the whole life of the session and let the run decide when it ends.** The key would live
  longer than the run that needs it, and a key that is alive is a key that can leak (FR-002, SC-011). The time to
  live is short, and it is renewed by nothing.
- **Let the provider client hold the key and skip the vault.** The key would live in the client, and the client would
  have to be reachable by handle, which is the vault with a worse boundary and no bound.
- **Write the key into the environment of the process for the duration of the run.** The key would reach every log of
  the process, every trace of the library and every child process. The specification forbids it (FR-007), and the
  client of the provider is built per run with the key in its constructor instead.
- **Promise that the memory is erased.** No runtime of the language can promise it, and a promise that cannot be kept
  is worse than a limitation that is stated. The buffer is overwritten on a best effort, and the limitation is
  disclosed (FR-021).
- **Let the vault remember the secret of a dropped credential so that a late exception can still be scrubbed.** A
  secret that outlives its credential is exactly what the specification forbids, and the pattern based redaction
  covers the shapes of the keys that a provider is likely to leak. The key of a run is scrubbed at the boundary of the
  adapter, where the key is still alive, and that is where the promise of the scrub stops.

## Consequences

- The key of a visitor lives in the memory of the process of the demo and nowhere else. The process that receives it
  is the process that uses it, and the key is gone when the process ends.
- The handle is the only thing that travels. The client receives the handle, the provider and the expiry, and the
  handle of another session is refused with the same answer as a handle that does not exist.
- The vault is bounded in the number of credentials, in the time to live of each one and in the number of failures it
  survives. The oldest credential is dropped when the vault is full, and the vault says so.
- A credential that is expired, revoked or dropped after too many failures keeps a tombstone that carries no secret,
  so the refusal can name the reason. The tombstone is bound to the session that owned the credential, and the map of
  the tombstones is bounded like the map of the credentials.
- The scrub of the vault is the tool of the facade of the live mode, and the facade is the task of the next
  milestone: nothing in the product calls the scrub of the vault today. The boundary that applies a scrub today is the
  adapter, and a provider exception that carries the key leaves the adapter without the key, in the message and in the
  traceback (FR-018, SC-001).
- The limitation of the zeroization is disclosed here, and the interface of the live mode will disclose it to the
  visitor when the facade of the next milestone is built. The product never writes the key anywhere and drops it
  when the credential ends, and the machine may still hold a copy of it for a while.
- The domain layer grows one module and one test, and the live mode has no persistence at all: the module imports
  nothing of the API layer and writes no SQL.
