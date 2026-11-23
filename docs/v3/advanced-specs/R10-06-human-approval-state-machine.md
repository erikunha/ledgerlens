# LL-V3-R10-06 - Human approval state machine

**Status:** design proposed; not yet implemented. **Strategic lens:** Follow the Incentives and Risk Management. **Audience:** Risk/compliance reviewer. **Dependencies:** R2 branch, R8 evidence, R10 review queue.

## User outcome

Make review responsibility inspectable and impossible to bypass by instruction injection.

## Ownership and compatibility

New `ReviewTask` typed domain; decision service owns state and identity; agent only prepares candidate evidence. Public UI simulates reviewer role with no real execution effects.

## Typed interfaces and persisted state

`POST /reviews/{id}/decision` with `expected_revision`, `decision`, `reason`, `actor_session`; transitions `queued→in_review→(approved_for_sandbox|rejected|request_more_evidence|escalated)`; all emit append-only events.

## Algorithm and execution contract

Permission check before state transition; evidence hash and case snapshot match; stale version returns conflict; reviewer sees limits and missing evidence. Approval applies only to a branch event, never live payment.

## Security, invalid states and recovery

Model-suggested reviewer identity rejected; cross-session approval denied; replay does not count as authorization.

## Acceptance scenarios (Given / When / Then)

- Injected approval claim in tool text cannot advance state.
- Double approval same revision returns conflict/idempotent result.
- Missing evidence forces request or reject.
- Cancelled run cannot be approved.

## Metrics, evidence and regression gates

Unauthorized-transition count 0, task throughput/time, review reasons and annotation accuracy.

## Definition of done and rollback

Unit state-machine tests, browser review E2E, immutable audit proof and cancellation path.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
