# ADR-P002: Replay ≠ deterministic simulation ≠ live LLM

**Status:** proposed. **Context:** anonymous recruiters need a zero-friction demonstration; real LLM calls are paid, slow and may be unavailable. A replay that pretends to be live is misleading.

**Decision:** three visually distinct modes. A replay contains real previously recorded trace/result and provenance; a deterministic sandbox displays derived state/calculations only; a live mode runs a current model under BYOK and budgets. The UI always labels the mode and source snapshot.

**Alternatives:** free owner-paid inference (cost/abuse); always scripted chat labeled AI (misleading); only a video (low interactivity). **Consequence:** the replay recorder and artifact format are P0. **Rollback:** static replay works without live backend.
