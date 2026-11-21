---
type: adr
status: accepted
date: 2026-11-14
---

# ADR-019: The sandbox facade follows the versioned OpenAPI contract and the session is a cookie

Status: accepted. Date: 2026-11-14.

## Context

The design package versions an HTTP contract for the sandbox, in `docs/v3/contracts/openapi.yaml`. It names the
paths, the security scheme and the shape of the answers:

- `POST /v1/sandboxes` takes a body with the scenario id and answers `201` with the resource `Sandbox`;
- `GET /v1/sandboxes/{sandbox_id}` answers `200` with the same resource;
- the session is an `apiKey` in a cookie named `ledgerlens_session`, described as an opaque signed HttpOnly demo
  session cookie, and it is not user identity;
- `POST /v1/sessions` issues the session and `DELETE /v1/sessions/current` ends it and purges its branches;
- the resource `Sandbox` has exactly five fields: `id`, `base_snapshot_id`, `snapshot_sha256`, `revision` and
  `expires_at`, and it accepts no other field.

The feature specification asks for the schema version on every sandbox answer (FR-042) and for a generic answer
that does not disclose that a branch of another visitor exists (FR-005).

## Decision

**The facade follows the versioned contract.** The path parameter is `sandbox_id`, the body of the sandbox answers
is exactly the five fields of the resource `Sandbox`, and the body of the fork takes exactly the scenario id.

**The session is the cookie of the contract.** `POST /v1/sessions` issues an opaque session identifier, sets the
cookie `ledgerlens_session` as HttpOnly and SameSite Lax, and answers with the resource `Session`. The sandbox
routes read the cookie and never a header, so the browser never has to handle the identifier, and the identifier
never travels in a place a third party can read. A request without a valid session answers `401`, and a branch
that belongs to another session answers `404` with a generic message that does not disclose that the branch
exists.

**The schema version travels in a header, not in the body.** The resource `Sandbox` accepts no other field, so
adding a version to the body would break the contract that the interface reads. The answer therefore carries the
version in the header `X-LedgerLens-Schema-Version`, which satisfies FR-042 without touching the contract.

**The identity of the base is the canonical hash and the identifier of the base is the published snapshot.** The
`base_snapshot_id` names the published snapshot the branch was forked from, as the source and the seed of the
dataset (`sample-42`), and the `snapshot_sha256` is the canonical hash of the account scoped projection the branch
reads. Two visitors of the same scenario report the same pair, and the hash is the one the branch can be compared
by after a mutation.

**The fork answers `201` when it creates a branch and `200` when the reuse rule returns the branch that already
exists.** The difference matters to a client: one answer is a creation and the other is not.

## Alternatives considered

- **The session identifier in a header.** It works and it is easy to test, but the contract says a cookie, and a
  header asks the browser to handle an identifier that the server can keep in a cookie it never exposes.
- **The schema version inside the body of the answer.** It would break the resource `Sandbox`, which accepts no
  other field, and the interface reads that resource.
- **The identifier of the base being the scenario.** It would name the case and not the snapshot, and the two are
  different things: the case is a curated question, the snapshot is the version of the ledger it reads.

## Consequences

- The facade of the sandbox is the one the interface expects, so the frontend that is paused can be written
  against the versioned contract without a translation layer.
- The version of the answers is available to a client that needs it, without changing the shape of the resource.
- A client that forks the same scenario twice can tell a creation from a reuse by the status code.
- The session is issued by the server and never carried by the browser in a readable place, which is one less
  place where a visitor identifier can leak.
