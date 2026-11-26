# Follow the Money inside Payment Operations

## Separate domains

A payment operation involves the consumer, merchant, PSP/acquirer, card/network rails, bank, risk/compliance and support. LedgerLens simulates these relationships for education. It **does not** access real accounts, debit funds, approve disputes or produce authorized customer-service decisions.

| Actor | Job to be done | Economic consequence of errors | Competing incentives | Feature that demonstrates engineering |
|---|---|---|---|---|
| Customer | Understand missing or lower refund | Time, trust, cash-flow inconvenience | Fast reassurance vs truthful uncertainty | Grounded case answer + source facts |
| Merchant ops | Reconcile payouts and fees | Delayed cash, accounting adjustments | Low handling cost vs correct reconciliation | Settlement arithmetic + evidence graph |
| Support analyst | Investigate many cases efficiently | Labor, unnecessary escalations | Speed vs confidence and policy compliance | Human review queue and workload lab |
| Risk/disputes | Meet response deadlines | Expiring options, loss exposure | Conservative escalation vs excess workload | Deadline case S03 with clocks |
| Finance controller | Trace adjustments and amounts | Reporting inconsistencies | Accuracy vs close speed | Exact decimal checks, event replay |
| Compliance | Preserve traceability | Governance/risk exposure | Scope minimization vs investigation access | Permission and trace provenance demos |
| AI platform owner | Run the system reliably | Provider spend, latency, uptime | Lower costs vs answer quality | Budget/quality model router and evals |
| Engineering leader | Assess trustworthy design | Incident cost, maintenance | Fast delivery vs correctness | Failure gallery, ADRs, CI provenance |

These are proposed stakeholder profiles, not interviewed customers. Underlying fees, financial figures and processing times in the demo remain simulated or sourced from the project's permitted fixtures.

## High-value case families

1. Cross-border refund differences: applied vs reference FX, policy terms, arithmetic provenance; avoid pretending reference FX equals network applied FX.
2. Duplicate transaction detection: same card/merchant/time is evidence, not categorical fraud proof; false-positive analysis.
3. Dispute/deadline handling: business-day and contractual cutoff behavior; no actual legal advice.
4. Merchant settlement: fees, refunds, holidays, currency and net payout reconstruction.
5. Refund policy ambiguity: retrieval coverage vs temporal policy versions.
6. Missing/corrupted identifiers: when asking for clarification is economically optimal.
7. Unsupported currency or unavailable external rate: proper abstention vs fabricated accuracy.
8. Prompt injection embedded in ledger/policy text: fail-safe data boundary.
9. Divergent support/review incentives: priority selection under fixed staffing.
10. Costly false escalations: compare risk-weighted decision quality, not only triage accuracy.
11. Evidence conflict across database/API/policy: reconcile sources with temporal validity.
12. Provider outage/timeouts and partial tool responses: degraded but truthful behavior.

## Economic measurement constraints

- `'amount at risk'` is a scenario attribute; it is **not** observed savings.
- `'money moved'`, `'revenue recovered'`, `'loss prevented'` must be **zero or N/A** in a public demo unless proven with an authorized external record. The fictional world may simulate these values, but must say so.
- Time savings require a human baseline measured with a stated protocol; latency differences alone prove only computational performance.
- Cost per correctly resolved case is a valid experiment measure when correctness is independently defined and datasets match.
- Estimate of expected financial loss requires probabilities, impact assumptions and uncertainty, all clearly labeled.
- Every economic number is tagged with provenance and units.

## Competitive positioning of this portfolio

Neither a payment helpdesk product nor a dispute automation business. The portfolio signal is **end-to-end Applied AI architecture for high-consequence workflows**: verifiable math, tools, retrieval, constraints, observability, human handoff, evaluation, UX and explicit economics. Link every demo walkthrough to exactly where its behavior is implemented in the repository.
