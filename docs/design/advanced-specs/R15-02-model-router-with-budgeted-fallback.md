# LL-V3-R15-02 - Model router with budgeted fallback

**Status:** design proposed; not yet implemented. **Strategic lens:** Value Capture and Opportunity Cost. **Audience:** AI platform engineer. **Dependencies:** R3 provider registry, R4 eval, R9 economics.

## User outcome

Understand when cheaper models are sufficient and when escalation improves verified utility.

## Ownership and compatibility

Use existing `ledgerlens/config.py` provider factory through versioned gateway, not parallel model logic in frontend; route on pre-verified intent/risk and allowed vendor capability.

## Typed interfaces and persisted state

`RoutingDecision {case_id,case_type,risk_tier,allowed_provider_models,chosen_model,reason,budget,price_snapshot,confidence_kind}`; output as immutable trace metadata.

## Algorithm and execution contract

Obtain case class, list compatible tested models, select cheapest eligible from registered profile or pinned user choice, execute bounded, perform verifier, optionally fallback if supported by pre-consented strategy and remaining budget; record route and costs.

## Security, invalid states and recovery

Never auto-increase spend or switch data provider outside consent. Never accept free-form server URL from anonymous visitor. Prices missing -> cost unknown, not zero.

## Acceptance scenarios (Given / When / Then)

- Unsupported function-calling model disabled.
- Failure with no retry budget -> stops with explicit reason.
- Human-selected model not silently replaced.
- Stale pricing metadata -> cost estimate labeled stale.
- Same case cohort used for route comparison.

## Metrics, evidence and regression gates

Accuracy by intent, cost per correct, p95, fallback rate, model mix and failure modes.

## Definition of done and rollback

Provider mock conformance, one live provider smoke with explicit opt-in, benchmark artifacts, rollback to single selected model.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
