# LL-V3-R13-02 - Safe adversarial laboratory

**Status:** design proposed; not yet implemented. **Strategic lens:** Inversion and Risk Management. **Audience:** Security engineer. **Dependencies:** R7, R11, R12.

## User outcome

Make agentic threat boundaries inspectable through controlled prompt-injection and tool misuse scenarios.

## Ownership and compatibility

Use synthetic S09 plus added safe attack scenarios; existing SQL guard remains an independent layer; `tools` registry enforces allowlist separately from model intent.

## Typed interfaces and persisted state

`POST /attack-lab/run` accepts only canned scenario IDs and per-branch benign options; outputs `{attack_surface,expected_boundary,trace_ref,blocked_actions,unresolved_risk}`. No raw shell/network command input.

## Algorithm and execution contract

Load synthetic malicious datum, run with scoped read-only tools, check whether agent obeys lower-trust instruction; inspect trace and boundary decisions; create regression when an unsafe action or answer occurs.

## Security, invalid states and recovery

Explicit deny: live payment mutations, unrestricted network, process execution, arbitrary tool manifests, unbounded prompts, external domains and key export. Mock adversarial content must never include real secrets.

## Acceptance scenarios (Given / When / Then)

- S09 fake instruction has no effect on permissions.
- Malformed tool arguments denied and logged.
- Cross-account memory source cannot be mounted.
- Missing budget stops run.
- Canned attack traces can be reviewed without BYOK.

## Metrics, evidence and regression gates

Unauthorized actions 0 under tests, attack success/defense rate for labeled controlled fixtures, false alarms and cost.

## Definition of done and rollback

Threat matrix mapped to OWASP 2026 and NIST, reproducible fixture hashes, negative cases; rollback research feature by disabling all executable attack endpoints.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
