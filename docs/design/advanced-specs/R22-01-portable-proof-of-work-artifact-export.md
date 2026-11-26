# LL-V3-R22-01 - Portable proof-of-work artifact export

**Status:** design proposed; not yet implemented. **Strategic lens:** Distribution Advantage and Bargaining Power. **Audience:** Recruiter, senior engineer and open-source contributor. **Dependencies:** R1 demo, R4 eval, R8 evidence, R9 economics, R21 tooling.

## User outcome

Allow any reviewer to validate a technical claim from a short public URL and the exact code+trace evidence, without trusting a LinkedIn assertion.

## Ownership and compatibility

Server or static build tool composes sanitized evidence from immutable experiment run; preserve Git SHA and method. Never export ephemeral BYOK or visitor private input.

## Typed interfaces and persisted state

`portfolio-proof` schema v3; route `GET /proof/{id}`, optional accessible image/video, JSON report and code deep links. Public artifact IDs are unguessable but access scope must still be enforced for private cases.

## Algorithm and execution contract

Select a completed case and experiment manifest, redact, verify hashes and source references, calculate metrics with provenance, produce Markdown/static page/card. If required evidence missing, mark draft and disallow public verified badge.

## Security, invalid states and recovery

No ability to forge employer proof; no proprietary customer data, provider key, private chats, IP or path secrets. External links are normalized to source commit paths.

## Acceptance scenarios (Given / When / Then)

- Missing experiment hash -> export marked incomplete, not published as verified.
- Secret-like string in trace -> redaction test blocks export.
- Benchmark numbers sourced from actual report.
- Accessibility includes text transcript for media.

## Metrics, evidence and regression gates

Visitor completion, source verification click, independently reproduced demos, genuine external review. Do not equate impressions with career outcomes.

## Definition of done and rollback

Publish reproducible artifact and exact recipe, automated link check, README claim audit and rollback; user controls sharing.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
