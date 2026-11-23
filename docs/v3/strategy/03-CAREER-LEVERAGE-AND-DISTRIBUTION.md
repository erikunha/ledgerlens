# Portfolio Distribution, Proof of Work, and Career Leverage

## Two feedback loops

**Engineering loop:** trace → observed error → reproduction → benchmark case → fix → new result → public case study.

**Distribution loop:** first-visit 60-second tour → no-key demo → evidence inspection → technical deep dive → GitHub → conversations with peers, hiring managers and potential collaborators. The second loop must never influence scientific evaluation labels.

## Observable funnel (privacy-preserving)

Measure aggregated: landing views, demo start, first case completed, trace opened, sandbox mutation performed, model arena inspected, source link opened, external referral (optional), anonymized feedback count. Use aggregate daily/weekly counts with opt-in analytics where required, do not collect secrets or free-text payment questions in web analytics, and offer a no-tracking mode. Distinguish actual interactions from bot traffic. No employer salary or hiring prediction from clicks.

## Six distinct proof artifacts

1. **90-second keyless demo:** shareable direct link to a replay, scenario facts and trace. One clear 'what can I verify?' hook.
2. **Senior engineering case study:** architectural constraints, alternatives considered, data flow, failure paths, tests, rollback and threat model.
3. **Agent evaluation report:** exact model/version/snapshot, paired cases, confidence intervals, cost, latency, error distribution; show negative results.
4. **Security teardown:** SQL guard, tool injection tests, tenant isolation, BYOK lifecycle and reproducible adversarial cases.
5. **ML depth note:** NLI limitations, calibration, selective prediction, drift and evaluation error analysis.
6. **Public repo with testable claims:** commands, seed, frozen fixtures, source licenses, CI and honest limitations.

## Proposed LinkedIn publication series (content only after a working claim)

- **Episode 1:** Why I didn't build 'just another agent' - verified financial investigation end-to-end.
- **Episode 2:** A hallucination looked plausible; here's the evidence that contradicted it.
- **Episode 3:** What three agent architectures cost per correct investigation, with reproducible run bundles.
- **Episode 4:** Injecting a bad FX rate and observing what survives.
- **Episode 5:** One agent versus many: measured quality, tokens, p95 latency, reviewer load and failure modes.
- **Episode 6:** The economic bottleneck moved from model latency to analyst review.
- **Episode 7:** How I built an interactive research lab with Next.js, Python, event-sourced data and BYOK without persistent secrets.
- **Episode 8:** The failures I couldn't fix, with the dataset slice and a public issue.

Do not assert a result before execution. Each post links to live demo, code path, dataset and methodology; provide short video subtitles and a text transcript; accessible diagrams.

## Decision journal for career ROI

For each 2-4 week development bet, record build hours, planned visitor action, technical skill demonstrated, distribution channel, explicit hypothesis, observable outcome, possible disconfirmation, and what we learn if it fails. Career returns may be delayed and noisy, so record direct external feedback (interviews, meaningful review, referrals) separately from proxy metrics (stars, likes, views).

## Audience modes

- 60 seconds: recruiter/curious visitor: one obvious scenario, result, code link.
- 3 minutes: engineering manager: inspect trace, reason for escalation, tests.
- 15-30 minutes: senior engineer: mutate scenario, benchmark, inspect reasoning boundaries.
- 60+ minutes: researcher: reproduce evals, compare architectures and critique assumptions.

Do not gate the first three behind auth, payment or BYOK.
