# Career Narrative, Public Demo Strategy and Source Proof

## Positioning hypothesis

'Built and evaluated an evidence-grounded AI investigation workbench - a full-stack environment with typed tools, scoped SQL access, event-sourced simulation, trace inspection, human review, model/provider routing and cost/quality analysis.' Only use verbs proven by shipped code, not aspirational roadmap items.

## Technical value signals

| Audience | Signal | Proof | Business interpretation |
|---|---|---|---|
| Frontend/platform leader | UX and stateful flow of a complex agent | keyboard-tested Next.js UI + SSE contracts | Trustworthy user experience |
| AI platform engineer | Routing, budgets, execution recovery | typed run manifests and fault tests | Operational control |
| Applied AI engineer | Tool selection + grounded claims + evals | paired A/B/C experiments, honest dataset | Correctness, not anecdotes |
| Staff/full-stack | Clear ownership, data scope, consistency | ADRs, domain model and migration | Long-lived maintainability |
| Security engineer | SQL guard, BYOK, prompt injection defenses | attack fixtures and controls | Reduced exposure |
| Financial operations manager | Measured economics with assumptions | Cost-per-correct and review queue | Decision support, not fake recovered revenue |
| Founder | Distribution and learning loop | keyless demo, deep links, external user feedback | Product judgment |

## Distribution experiments

A. One-page product demo with 'Start S01' in first viewport. B. Story-driven technical essay showing a bug and fix. C. Short annotated screencast (captions) showing claim and evidence. D. Agent-eval report with methodological candor. E. Open-source reproducibility template + issue prompts. F. Technical peer review with 5 external engineers using a 5-task evaluation criteria. Measure completion and useful feedback, not mere likes.

## Public case-study generator rules

Can export sanitized report containing: question, scenario id, simulation mode, code version SHA, dataset hash, plan, called tools, numerical verification, supported/unsupported claims, observed errors, model info, tokens and pricing snapshot, tests and known limits. Never include BYOK, per-visitor IP, personal details or private trace contents. Every field carries provenance; absent fields say unknown.

## Post-release review

Record which technical questions and hiring conversations recur; add those as demo experiments, tests or clearer docs. A new LinkedIn post is warranted when a new claim can be **verified** or a failure can teach something, not for every feature commit. Keep a monthly decision log (bet, spend, evidence, next action).
