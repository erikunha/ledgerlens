---
type: adr
status: accepted
date: 2026-11-07
---

# ADR-001: Domain, payment investigation

Status: accepted. Date: 2026-11-07.

## Context

The project needs a domain where an agent has to choose different tools for each case. The agent needs SQL, policy search, an external API, memory and verification. The domain also needs numbers that cannot be wrong, to justify doing the arithmetic in code and not in the model.

## Decision

The domain is the investigation of payment complaints by an operations analyst at a fictional PSP (payment service provider). The agent is called LedgerLens. It understands the request, queries the transaction database, finds the right policy, compares with the reference exchange rate, calculates the difference with `Decimal`, verifies each claim and says what is missing when it cannot conclude.

An agent and not a chain, because the path changes with each case: a status request needs only SQL, a refund discrepancy in another currency needs SQL, policy, exchange rate and arithmetic, and an ambiguous request needs a question back.

## Alternatives considered

- **IncidentIQ (software incidents).** The project fits better with structured data, policies and exchange rates. There is no external API as natural as the exchange-rate quote.
- **Generic support assistant.** It has no exact arithmetic and no verifiable evidence, so verification would feel artificial.

## Consequences

- There are planted scenarios with known answers (a refund with exchange-rate markup, a duplicate charge, a chargeback near its deadline, a nonexistent ID). They allow deterministic tests and an evaluation with ground truth.
- The PSP name and the merchant data are invented. No real customer data enters the repository.
- The text the agent produces must cite evidence. This becomes a project rule: every claim cites the evidence it came from.
