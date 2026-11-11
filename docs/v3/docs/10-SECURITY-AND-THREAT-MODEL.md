# Public demo threat model and security control plan

## Scope and trust boundaries

Assets: visitor BYOK secrets, immutable dataset, account-scoped simulated ledger, sandbox branches, traces, provider spend, public repo reputation, CPU/memory resources. Actors: anonymous visitor, adversarial anonymous visitor, compromised third-party provider/asset, repo dependency contributor. Trust boundaries: browser → first-party API → sandbox/domain tools → provider, and browser → public static replay.

**Core property:** there are no connections or credentials to live financial systems; the only write domain is isolated synthetic scenario events. This is stronger than merely requiring human approval for real refunds.

## Threats and mitigations

| Threat | Impact | Control | Verification |
|---|---|---|---|
| Visitor accesses another branch/account | Data leakage | opaque IDs + session-bound authorization on *every* read and SSE subscribe; scoped ledger | adversarial two-session E2E |
| Visitor modifies shared sample | data corruption, false demos | immutable base snapshot, per-session COW, no API path to global file | hash unchanged after mutation suite |
| SQL prompt injection | sensitive/meta table leakage or writes | AST allowlist, read-only SQLite URI, limited rows and wall time, no extensions | property/fuzz, forbidden corpus |
| Indirect prompt injection in ledger note | instruction hijack | untrusted labeling + tool policy, no write-capable tools, verifier, scenario tests | S09 and adversarial set |
| Credential exfiltration | visitor loss | HTTPS, scoped in-memory key, no third-party logs, redaction, CSP, limited allowed providers | fake key marker scan end-to-end |
| Budget abuse | cost explosion / host exhaustion | BYOK, calls/tokens/time/concurrency quotas, IP/session rate limits | load tests + billing mock |
| SSRF via model endpoint or tool URL | internal resource access | provider allowlist, no arbitrary URL, egress filtering | reject internal URLs |
| Reused stale trace | misleading false proof | binding to `snapshot_sha256`, branch revision and capture provenance | update invalidates replay |
| UI injection from LLM response | XSS | render text safely; sanitize Markdown/links and JSON; CSP | malicious output browser tests |
| Path traversal in filename/export | local filesystem compromise | fixed root, opaque identifiers, path validation, no uploads P0 | traversal tests |
| Secrets in telemetry | credential disclosure | structured logging, content scrubbing, sample off | grep trace artifacts and logs |
| Session fixation / CSRF | unauthorized branch mutation | signed HttpOnly cookies, Origin/CSRF validation on modifying requests | forged request tests |
| Replay tampering | incorrect educational results | SHA256, publication review, versioned manifest | integrity hash and schema validation |
| Dependencies / supply chain | compromise | pinned lockfiles, secret scan, vulnerability checks, provenance | CI gating and license audit |

## Controls by layer

**Browser** - HttpOnly Secure cookie, CSRF protection for state mutations, CSP no `unsafe-inline` scripts in new UI, safe component rendering, no localStorage keys. Session data downloads explicitly sanitized. Referrer policy, HSTS on deployment and third-party analytics disabled by default.

**API** - opaque random IDs, per-request owner authorization, strict Pydantic input sizes, request origin, rate limits, limited CORS, limited upload size (uploads disabled P0), error envelope, idempotency, single-run concurrency, deletion TTL.

**Execution** - no `subprocess` from prompts, no arbitrary SQL execution, bounded callbacks and output payloads, never `eval`/dynamic imports, limit recursion, cancellation and timeout, network egress allowlist. Any tool raising must create a sanitized error event.

**Data** - fake seeded names and accounts; no real personal financial data; immutable published base; isolated branches; explicit origins (`public-derived`/`synthetic`/`scenario`); least privilege for execution environment.

**Model providers** - opt-in, allowlisted, no arbitrary base URL, no server owner secrets available to clients, usage caps, errors redacted, no cross-user memory.

**Human factors** - disclaimers prominent: demo only, simulated financial events, not financial advice; an AI recommendation is not a payment action.

## Prompt injection is not solved by prompts

S09 contains malicious text inside a refund record. The test is that the content remains data and cannot modify account scope, bypass SQL tool restriction or cause payment changes. Keyword filters/extra instructions are secondary; authorization at each tool boundary is primary. OWASP's agentic threat model covers goal hijack, tool misuse, supply chain attacks, memory poisoning and cascading failures. Security claims must be scoped to tested attacks.

## Data policy

The initial public app accepts **no uploads of personal statements**, scanned ID, cards or secret invoices. BYOK data sent to providers consists only of the fictional simulated ledger and the visitor's own question; disclose it. User chat inputs may contain arbitrary text; keep only in ephemeral process state for the lifetime of the session unless explicitly exported by the visitor. No commercial analytics payload may contain prompt bodies or keys.

Retention defaults proposed: session 60 minutes idle, absolute 4 hours; run traces only within session; public curated replay versioned indefinitely; revoked keys unusable immediately for new calls. Values must be configurable, documented and tested. Python cannot guarantee secret memory zeroization upon revocation.

## Security release gate

Must demonstrate with tests: zero cross-branch leak, zero forbidden financial writes, no unscoped SQL, no shared cached mutable state, no secrets in public artifacts, no arbitrary endpoints, rate-limit protection, session destruction, low-privilege runtime account, and high-severity dependency findings triaged before release. Provide a concise public `SECURITY.md` with disclosure contact only if actual contact is known and accepted.
