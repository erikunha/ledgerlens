# SPEC LL-R3-02 - BYOK credential lifecycle, model runtime and cost policy

**Status:** P1, blocked by sandbox/session security and trace redaction gates.

## Invariants

- Keys are not recorded to disk/database/analytics/traces; stored only in bounded backend memory with TTL; scoping to anonymous session is mandatory.
- Any model run is explicitly opt-in, shows provider billing disclosure and applies hard caps and timeouts.
- Public demo works without this feature. There is no owner-funded free inference.
- No arbitrary provider URL or unknown model name in public configuration; only registry-approved adapters.

## Lifecycle

`unregistered → received → handle_active → run_reserved → run_in_progress → revoked/expired`. Credential object held by `CredentialVault` in process memory, keyed by opaque random handle mapped to server session, provider, created/expires times; never return or serialize actual secret. Source must be HTTPS endpoint, `Cache-Control: no-store`, body logging disabled.

Use constructor injection to create per-run `BaseChatModel` (LangChain) with provider-specific secret and options. Do not mutate `os.environ` or current global Settings. On cancellation/revocation, stop subsequent calls; best-effort cancellation of already in-flight provider call. Expiry time and inability to guarantee zeroization must be disclosed.

## Model catalog

`ModelProfile`: exact provider ID, tested capabilities, allowed models, optional dependency version, pricing provenance and last verified date, status. First public release enables only models successfully tested for native tool calling and output parsing, behind server allowlist. API fetch is not itself proof of feature support; run smoke tests. The example model-profile in `contracts/examples` is intentionally experimental/disabled until verified.

## Run budget

At least: `max_model_calls`, `max_tool_calls`, `max_wall_seconds`, `max_output_tokens` plus input/token limit when provider reports it. Track `observed_cost` and `estimated_cost` separately. If costs unknown, never say a USD cap is authoritative; technical caps still apply. Count retries and submodels (SQL generator, triage, final judge). Model switch mid-run forbidden: new run ID needed.

## Threat/eval tests

- Marker key in forced SDK exception never appears in logs, SSE, trace JSON, error UI or telemetry.
- Session B cannot consume A's credential handle.
- A revoked handle cannot start new run; in-flight cancellation is best-effort and state labeled.
- Simultaneous A(OpenAI)/B(other) cannot cross-contaminate keys via process env, client singleton or callbacks.
- Changing URL to `http://169.254.169.254` or `localhost` is rejected in public mode.
- Model missing `tool_calling` cannot start architecture B/C.
- Provider timeout does not cause unlimited retries or hanging browser; terminal trace captures partial state.
- No key provided: Replay and Sandbox deterministic remain fully usable.

## UX and acceptance

Consent modal clearly says "Your provider may charge you; LedgerLens does not store your key. Key is handled transiently by this demo server." Shows supported models, tested status and budgets. "Forget key" always available. `POST /credentials` returns only handle+TTL; `POST /runs` never accepts a raw key. No real financial operations ever executed.
