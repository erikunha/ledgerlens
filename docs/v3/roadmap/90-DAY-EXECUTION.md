# Execution Schedule - First Proof, Then Depth (illustrative 90-day sequence)

**Purpose:** publish a useful and verifiable experience while preserving the open-ended research vision. Dates and efforts depend on testing and constraints; milestones are gates, not promised completion dates.

## Days 1-15 - Freeze truth

- Run current `bash scripts/gate.sh` with Python 3.12/uv, record exact output and source SHA.
- Extract one current S01 genuine trace under a known mode, redact and create replay bundle. Do not fabricate model outputs.
- Verify `data/scenarios.json` oracle and economic labels for S01 - S12; document what does not generalize.
- Refactor only required seams to expose typed replay data without changing results.
- **Gate:** exact dataset+code+trace proof available and reproducible.

## Days 16-30 - Public visitor experience

- Next.js shell and design system; landing→S01 in one click.
- Payments portal, trace viewer, claim/verdict/evidence inspector; explicit replay mode.
- E2E keyboard/mobile; screen-reader smoke and clear failure states; deploy static fallback.
- **Gate:** external visitor can explain what happened, without credentials, in <3 minutes in a tested usability session. Publish first technical write-up once verified.

## Days 31-50 - Interactive simulator

- Per-visitor branch model, project event append, preview/apply/reset, hash consistency.
- S01 FX, S02 duplicates, S03 dispute deadlines with deterministic modified results.
- Before/after trace and evidence diff; no stale replay masquerading as new agent output.
- **Gate:** two concurrent visitors cannot observe each other's modifications; money invariants hold.

## Days 51-70 - Economic and quality experiments

- Publish A/B/C evaluation report from verifiable artifacts; expose failure slices and missed target.
- Implement economics assumptions and cost-per-correct using same cases; review burden chart.
- **Gate:** all charts have provenance and unit; no unsupported real savings claim. Publish second technical deep dive.

## Days 71-90 - Optional live and advanced proof

- Implement BYOK with ephemeral session, provider capability registry, strict cost limits, safe fallback.
- Test one provider end-to-end. Only then expand model choice and routing.
- Plan D-vs-C specialist experiment using frozen cases; implement only behind flag.
- **Gate:** secrets never present in traces/store/export; public demo remains usable without backend or key.

## After 90 days

Continue R8 - R23+ as research tracks, with contribution and learning value. Multi-agent, multimodal, durable and causal experiments can proceed alongside public use without turning the project into a commercial payments product. Publish genuine negative findings as valid research.

## Decision rules per sprint

- Which business/technical bottleneck is being relieved?
- What evidence will be visible to an outsider?
- What is learned if the experiment fails?
- Which alternative task has higher leverage?
- How easy is rollback?
- Which financial, security and privacy assumptions are new?

Every answer should be recorded in an ADR or decision journal, not left in an ephemeral chat.
