# LL-V3-R1-02 - Cold-start guided replay

**Status:** design proposed; not yet implemented. **Strategic lens:** Distribution and Proof of Work. **Audience:** Recruiter and engineering lead. **Dependencies:** Original R0 and Replay Bundle schema.

## User outcome

A new visitor can understand one resolved case in <3 minutes with no API key or login, then optionally inspect engineering depth.

## Ownership and compatibility

Next.js routing/controls; static replay JSON produced from Python TraceEvent normalization; immutable manifest; no backend requirement on initial path. Preserve the current `app/streamlit_app.py` as fallback reference.

## Typed interfaces and persisted state

`GET /replays/:id` returns immutable versioned bundle including `mode: recorded_replay`, input question, steps, evidence refs, verifier output, source SHA, dataset hash; fetch is safe and cacheable. UI stores only playback position.

## Algorithm and execution contract

1. Load known scenario S01. 2. Render honest 8-12 meaningful execution events with actual event ordering; no artificial pauses that imply model is computing. 3. Permit seek, inspect SQL, click cited evidence. 4. End with verified conclusion plus limitations. 5. Lead to a sandbox fork; replay remains unchanged.

## Security, invalid states and recovery

Static replay contains no secrets/personally identifying values; no key, model call, auto auth or state mutation. If source artifact missing, show error and local demo path; do not fabricate frames.

## Acceptance scenarios (Given / When / Then)

- Given no session and no backend, when opening S01, then replay works and no provider network request occurs.
- Given pause/seek, when jumping backwards, then same event order is reconstructed.
- Given source evidence link, when clicked, then exact referenced line or redacted source is displayed.
- Given keyboard-only visitor, when navigating controls, then focus and labels remain usable.

## Metrics, evidence and regression gates

Measure first-play completion, time to verifier result, source-code click, mobile performance and accessibility; annotate analytics with consent.

## Definition of done and rollback

Add Playwright a11y/mobile tests, static manifest validation, screenshot and source links. Rollback to static HTML page if React runtime fails; source artifact remains immutable.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
