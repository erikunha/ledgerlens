# ADR-P009: Restrict public LedgerLens to fictional payment data and non-transactional operations

**Status:** proposed. **Context:** a demo should not collect real financial statements, card data or enable actual refunds. Visitors may bring a provider key for simulated cases, but this is not permission to submit customer PII.

**Decision:** no uploads P0, no real payment APIs/keys, no real banking operations, fake data with provenance and notices. Session prompts/transient keys not shared, persisted or sent to analytics by default. Human-review recommendation is simulated; cannot trigger financial write.

**Alternatives:** connect Stripe sandbox (could imply fintech deployment and invite complexity); allow arbitrary financial uploads (privacy/safety burden). **Trade-offs:** less impressive external integration, much safer and clearer demonstration. **Rollback:** not applicable: safety invariant.
