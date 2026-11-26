# Public demonstration narrative and career outcome

## Positioning

Treat LedgerLens as proof of **AI systems engineering and product engineering**, not a generic LangChain tutorial. Its distinctive capabilities: constrained SQL tool use, deterministic arithmetic, adversarial examples, NLI claim-level evidence, event-sourced simulator, repeatable experiments and a professional interactive UI.

## Landing story (English copy)

**Headline:** "Financial agents should show their work."  
**Subheadline:** "Investigate simulated payment disputes with an AI agent that uses scoped tools, cites evidence, checks each claim and explains when human review is necessary. Try an actual recorded run - no API key required."  
**Primary:** "Try a case". **Secondary:** "Explore the architecture".  
**Disclosure:** "Demo environment. All money is simulated. Recorded playback is labeled; live calls use your provider key."

## 90-second demo flow

| Time | Action | Skill communicated |
|---|---|---|
| 0-10s | Open Landing and choose refund discrepancy | Clarity, UX and domain framing |
| 10-25s | Show EUR/BRL payment and refund in ledger | Reliable modeling, data provenance |
| 25-45s | Replay triage → SQL → policy → rate → Decimal | Agent tool orchestration |
| 45-60s | Click claim and view exact supporting source and verdict | Evaluation, groundedness, verification |
| 60-75s | Modify synthetic FX in Scenario Lab and show data delta | Event sourcing, safe experimental design |
| 75-90s | Compare A/B/C baseline and show an actual failed case | Scientific honesty and engineering trade-offs |

Publish a second technical video (3-5 minutes) with SQL guard, prompt injection S09, BYOK and evaluation. Do not use fake animations implying the recording is live. The narrated video script should say when a step is recorded, deterministic or provider-backed.

## LinkedIn post structure

Hook: "I built a payment investigation agent - then tested whether its claims were actually supported." One clear diagram and real screenshot. Describe agent's six tools and verification, benchmark methods, example failure and why demo can be tested. Keep claims tied to tests. CTA: repository + public replay link. Avoid claiming bank integration or commercial production volume.

## GitHub README above fold

1. One-line problem and demo image/GIF from real implemented UI.
2. Buttons/links: **Live demo**, **90-second walkthrough**, **Architecture**, **Evals**, **Run locally**.
3. Result table with tested variant / dataset / sample size / date.
4. Mermaid data/agent flow and security design.
5. Quickstart using `uv` and actual verified web command.
6. Limitations (scripted offline, calibration, no real payments) and attribution.

## Recruiter proof map

| Claim on resume/LinkedIn | Proof asset |
|---|---|
| Built an agent with tool-use, RAG and deterministic finance checks | Tool inspector / GitHub source |
| Designed safe text-to-SQL and isolation boundaries | SQL guard test corpus + security ADR |
| Implemented claim-level verification with NLI | Claims vs evidence view + calibration report |
| Evaluated alternative agent architectures | A/B/C repeatable benchmark + failure cases |
| Built a modern frontend for data-intensive systems | Ledger and Trace inspector + a11y tests |
| Designed reliable data simulations | Versioned event log, projector canonical hash, scenario editor |
| Implemented observability and failure handling | Trace events, SSE, outage/error states |

## Metrics of portfolio success (not business metrics)

- A reviewer can understand purpose within ten seconds without scrolling.
- The replay works without signup/API key and on mobile.
- The GitHub repository links to actual code and reproducible benchmarks.
- At least two scenario failure modes are accessible in three clicks.
- At least one tester follows a trace to a code module and understands what was verified.
- User testing asks: "Could you tell whether that output was live or replayed?" All participants should correctly differentiate.

## Content distribution

Create 3 linked assets rather than a long generic post: 1) one-minute hero video, 2) technical deep dive showing SQL guard/verifier, 3) benchmark/failure analysis. Write in English for global recruiting audience; optionally provide PT-BR summary. Keep the code open source and explain cost/availability of live BYOK.
