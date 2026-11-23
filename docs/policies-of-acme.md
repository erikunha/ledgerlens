# The rules of the world and the rules of Acme: what the corpus of the policies really is

The eight policies of `data/policies/` are the contract of a fictional company, and this document says, rule by
rule, which of them are a rule of the world, which are a house rule of Acme and which are an invention of this
project, with the source and the date of every rule of the world.

## What this document is for

The corpus of `data/policies/` is what the agent quotes to a merchant and what the verifier judges every answer
against. It reads like a handbook of payments as they are, because it names the card network, the central bank
and the law, and because some of its rules happen to be true. It is not a handbook of payments as they are. It
is the operating contract of Acme Payments, a company that does not exist, created only for this project.

That decision is [ADR-061](decisions/ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md).
It splits every rule of the corpus into one of three classes:

| Class | What it means | What the reader may do with it |
|---|---|---|
| A rule of the world | A rule of a card network, a central bank, a law or a published schedule | Quote it to a merchant, with the source and the date it was read |
| A house rule of Acme | A commercial choice of a fictional company | Quote it as what Acme does. Never as what the world requires |
| An invention of this project | A simplification made for the sake of a demo | Quote it as what the system does. Never as a rule of anybody |

The class in the second column of every table below is the class of the rule as the corpus states it. A rule of
the world with no source is a guess, and a guess here is worse than a gap, because this document exists to end the
gaps. Every rule of the world carries the URL of the source and the date it was read, and every house rule says
that it has no source.

This document does not change the corpus. It describes the corpus as it stands and marks what is wrong with it.
The correction of the eight files is the work of the specs, and it happens elsewhere. This document is the
context and not the contract: when a merchant asks what the network really does, this is where the answer is.
The decisions that frame the matter are
[ADR-001](decisions/ADR-001-payment-investigation-domain.md), which named the domain and the fictional company,
and [ADR-009](decisions/ADR-009-public-data-first-simulation-for-gaps.md), which separated the real data from the
simulated one. What was never decided, until ADR-061, was what a policy of a demo is.

The facts come from the audit of the truth of the policies and of the money, read on 2026-11-22 and written on
2026-11-23. Where the audit marked something as unverified or as an inference, this document says so in the same
words, and those items are listed under what is still unverified.

## The eight policies, rule by rule

The order of the sections is the order of the files in `data/policies/`. The first column gives the rule and the
line of the file it comes from. The rows that are a gap carry the number of the gap, and the second column says what
is wrong with the rule as it stands.

### 1. [Chargeback handling](../data/policies/chargeback-handling.md)

| The rule | What it is | The source |
|---|---|---|
| `:13`, `:17` What a chargeback is, the stages of a dispute, and that the network decides. | A rule of the world in its shape. The names of the stages are internal to Acme. | Primary: [Mastercard Chargeback Guide](https://brand.mastercard.com/content/dam/mccom/en-us/documents/rules/chargeback-guide.pdf) and [Mastercard Chargebacks Made Simple Guide](https://www.mastercard.us/content/dam/public/mastercardcom/na/global-site/documents/chargebacks-made-simple-guide.pdf), read 2026-11-22 |
| **Gap 2.** `:21` The reason codes FRD, NRC, NAD, DUP and OTH, and the evidence each one asks for. | A house rule of Acme. What is wrong: the codes are internal to the company and no network uses them. | None: this is a house rule of Acme. The codes of the networks are under what the networks really say |
| **Gap 1.** `:25` The response deadline, and that a late response loses the dispute. | An invention of this project. What is wrong: a window of ten to fourteen days is not a rule of any network, and ten rows of the ledger carry it. | None: the window is an invention of this project. The window of the network is under what the networks really say |
| **Gap 9.** `:29` The business days, and the calendar of the merchant's settlement currency. | A house rule of Acme. What is wrong: the policy names the settlement currency and the code uses the currency of the dispute record (`ledgerlens/verify/escalation.py:30`). | The calendars come from the `holidays` library, per [ADR-009](decisions/ADR-009-public-data-first-simulation-for-gaps.md) |
| `:33` to `:49` The evidence list of each reason code, and what a strong defense is. | A house rule of Acme. The audit named no source for the evidence lists. | None: this is a house rule of Acme |
| `:53`, `:65`, `:69` Who sends the evidence, no refund while a dispute is open, and the thresholds of escalation. | A house rule of Acme: the thresholds are service levels and no rule of the world fixes them. | None: this is a house rule of Acme |
| **Gap 13.** `:57` The outcome of the dispute: the network decides for or against the merchant, and Acme cannot change the outcome. | A rule of the world in its shape: the card network decides the outcome of a dispute, the rule that `:13` and `:17` already state with a source. What is wrong: the corpus states the rule of the network as the contract of Acme, in a paragraph that carries no source and no date, and the sentence that Acme cannot change the outcome is a house rule of the company. | Primary: [Mastercard Chargeback Guide](https://brand.mastercard.com/content/dam/mccom/en-us/documents/rules/chargeback-guide.pdf) and [Mastercard Chargebacks Made Simple Guide](https://www.mastercard.us/content/dam/public/mastercardcom/na/global-site/documents/chargebacks-made-simple-guide.pdf), read 2026-11-22 |
| `:61` The fee of each dispute opened, charged even if the merchant wins. | A rule of the world: the dispute received fee is not returned on a win. The amount is the figure of this repository. | Primary: [Stripe, How disputes work](https://docs.stripe.com/disputes/how-disputes-work) and [Stripe, Respond to disputes](https://docs.stripe.com/disputes/responding), read 2026-11-22 |

### 2. [Cross-currency refunds](../data/policies/cross-currency-refunds.md)

| The rule | What it is | The source |
|---|---|---|
| `:13`, `:17`, `:21` What a cross-currency refund is, what it records, and that it uses the rate of the refund date. | A house rule of Acme: the definition, the records and the choice of the date. | None: this is a house rule of Acme |
| `:25` The charge conversion at the reference rate of the capture date, with no markup. | A rule of the world: the rate of the day is the rate of the ECB. The audit found the rule exact on 1704 of 1704 charge conversions. | Primary: the [live Frankfurter call of 2026-10-05](https://api.frankfurter.dev/v1/2026-10-05?from=EUR&to=BRL), read 2026-11-22, byte for byte the body the repository records |
| **Gap 6.** `:29` The merchant markup of up to 3.0 percent, and the applied rate is the reference times one minus the markup. | A house rule of Acme with a wording defect: the file says "over" in the sentence that subtracts the markup. The direction of the spread of an acquirer is a rule of the world, and the spread lowers the rate. | The audit attributes the direction to Stripe, "Currency conversions", and to the Mastercard rulebook on currency conversion, and its source list carries no URL and no date for the two. See what is still unverified |
| `:33`, `:37`, `:41` The standard plan, how to read the difference, and the worked example of EUR 200.00. | A house rule of Acme. The arithmetic is right: the calculator of the repository returns the figures of the file. | None: this is a house rule of Acme |
| `:45` Rates to four decimals, amounts to the smallest unit of the currency, always half to even. | A house rule of Acme, a choice of the platform: the market rounds a tie up, and the promise of four decimals is false for the euro against sterling, where the tool returns 0.85898 and the ledger applied 0.8590. | Primary: [Stripe Pricing Policy, clause 1.3](https://stripe.com/legal/pricing-policy), read 2026-11-22, for what the market does |
| `:49`, `:53`, `:57`, `:61` The payout currency, the currency with no published rate, the explanation to the customer, and the records kept. | A house rule of Acme, except for the fact it rests on: the Argentine peso is not on the list of the ECB, which the audit verified against the recorded answer of the service, a not found with the status 404. | Primary: the live Frankfurter service, read 2026-11-22, and the recorded response of the repository |

### 3. [Duplicate charges](../data/policies/duplicate-charges.md)

| The rule | What it is | The source |
|---|---|---|
| `:13`, `:17` The detection rule: same merchant, card, amount and currency, and the second capture within five minutes of the first. | A house rule of Acme, a simplification of the networks, which detect a duplicate from the merchant, the amount, the terminal, the date and the time. It fires once on the shipped ledger, on a pair a scenario planted. | Primary: [Mastercard Chargeback Guide](https://brand.mastercard.com/content/dam/mccom/en-us/documents/rules/chargeback-guide.pdf), read 2026-11-22, for the definition of the network |
| `:21`, `:23` What is not a duplicate, and what to do when the interval is longer than five minutes. | A house rule of Acme. The boundary is discussed by the file and exercised by nothing. | None: this is a house rule of Acme |
| `:29` The later charge is refunded in full within five business days, whatever the refund window. | A house rule of Acme. No law read in the audit fixes a window for a duplicate, and five business days are stricter than the statutory floor of fourteen days. | Primary: [Directive 2011/83/EU](https://eur-lex.europa.eu/eli/dir/2011/83/oj/eng), Article 13, read 2026-11-22, for the floor |
| `:33` to `:57` Who refunds, the four checks, that only captures count, the duplicate with a conversion, what the customer is told, the escalation and the records. | A house rule of Acme. | None: this is a house rule of Acme |

### 4. [Escalation and human review](../data/policies/escalation-and-review.md)

| The rule | What it is | The source |
|---|---|---|
| `:17` When to escalate: a contradicted claim, missing data, a deadline two days away or less, or an amount above 5,000. | A house rule of Acme: these are service levels and no rule of the world fixes them. | None: this is a house rule of Acme |
| `:21`, `:25`, `:57` A contradicted claim, missing data, and no guessing. | A house rule of Acme. What is missing from it: a contradiction with a policy may mean that the policy is wrong. | None: this is a house rule of Acme |
| `:29` to `:61` The urgency of a deadline, the amount above 5,000, the text of a data field read as data, the response times, the handoff, the flag and the record of the review. | A house rule of Acme, a design of the product. | None: this is a house rule of Acme |

### 5. [Fees and pricing](../data/policies/fees-and-pricing.md)

| The rule | What it is | The source |
|---|---|---|
| `:13`, `:17` The processing fee: 2.9 percent of the gross volume captured in the period, before refunds. | A house rule of Acme: the percentage is a commercial price, and the simulator invents every fee of the repository. | None: this is a house rule of Acme |
| `:21` The fee of each dispute opened: 15.00 in the settlement currency, charged whether the merchant wins or loses. | A rule of the world: the dispute received fee is charged even on a win. The amount is the figure of this repository, and the market has two fees where the corpus has one. | Primary: [Stripe, How disputes work](https://docs.stripe.com/disputes/how-disputes-work), [Stripe, Respond to disputes](https://docs.stripe.com/disputes/responding) and [Stripe, June 2025 pricing updates for disputes](https://support.stripe.com/questions/june-2025-pricing-updates-for-disputes), read 2026-11-22 |
| `:25` The total of the fees, shown apart in the settlement. | A house rule of Acme. The arithmetic is right: the audit recomputed the fee of all 286 settlements and found no mismatch. | None: this is a house rule of Acme |
| **Gap 7.** `:29` The rounding: half to even, so 14.5 cents become 14 and 43.5 cents become 44. | A house rule of Acme, a choice of the platform. What is wrong: the file states the mode as a rule and does not say that it is a choice, and no row of the ledger reaches a tie. | Primary: [Stripe Pricing Policy, clause 1.3](https://stripe.com/legal/pricing-policy), read 2026-11-22, for what the market does |
| `:33` The worked example: 10,000.00 of gross, two chargebacks, 320.00 of fees and a net of 9,280.00. | A house rule of Acme. The arithmetic is right: the calculator of the repository returns both figures. | None: this is a house rule of Acme |
| `:37` The processing fee is not returned when a payment is refunded. | A rule of the world: a refund does not give back the processing fee. | Primary: [Stripe Pricing Policy](https://stripe.com/legal/pricing-policy), clause 1.3, and [Stripe, How disputes work](https://docs.stripe.com/disputes/how-disputes-work), read 2026-11-22 |
| `:41` to `:61` The markup is not a fee of Acme, the currency of the fees, the disclosure, the changes, the explanation of the payout, and the escalation of a disputed fee. | A house rule of Acme. | None: this is a house rule of Acme |

### 6. [Reference exchange rates](../data/policies/fx-reference-rates.md)

| The rule | What it is | The source |
|---|---|---|
| `:13`, `:17` The official source: the daily rate of the ECB through the Frankfurter service, ECB only, and the previous business day on a weekend or a holiday. | A rule of the world. The audit called the live service on 2026-11-22 and got the body the repository records, byte for byte. | Primary: [European Central Bank, Disclaimer and copyright](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html) and the [live Frankfurter call](https://api.frankfurter.dev/v1/2026-10-05?from=EUR&to=BRL), read 2026-11-22 |
| `:21`, `:25` The weekends and the holidays, and the refusal to blend the sources. | A house rule of Acme: the single source is a choice of the platform. The reason was measured in ADR-009, where a version without a pinned source returned 5.7379 against 5.5849, a difference of 2.7 percent. | Primary: the live Frankfurter service, read 2026-11-22. The blended figure is from [ADR-009](decisions/ADR-009-public-data-first-simulation-for-gaps.md), 2026-11-07 |
| `:29` The second source for the real: the closing PTAX rate of the Banco Central do Brasil, as a cross-check. | A house rule of Acme in the choice of the default source. The existence of the PTAX is a rule of the world, but the difference the file describes was not measured by the audit. | [ADR-009](decisions/ADR-009-public-data-first-simulation-for-gaps.md), 2026-11-07 |
| `:33` Four decimals for rates, exact decimals and never floating point, and a cross rate computed through the euro. | An invention of this project. The cross rate through the euro is computed by the platform, and the promise of four decimals is false for the euro against sterling, where the ECB quotes five. | Primary: the live Frankfurter service and the recorded series, read 2026-11-22 |
| `:37`, `:41` The available currencies, about thirty on the list of the ECB, and no rate for a currency outside it. | A rule of the world. The Argentine peso case was verified against the recorded answer of the service, a not found with the status 404. The handling of the case is a house rule of Acme. | Primary: the live Frankfurter service, read 2026-11-22 |
| `:45` The service is down: the rate could not be looked up and the number is never filled in. | A house rule of Acme. | None: this is a house rule of Acme |
| **Gap 5.** `:49`, `:53` The implied markup, the ceiling of 3.0 percent above which the case is escalated, and the band of five hundredths of a percentage point that rounding alone can cause. | A house rule of Acme: no rule of the world fixes the ceiling. What is wrong: the rule at `:49` is applied without the band that `:53` defines, so sixteen refunds of merchants at exactly 3.0 percent are escalated, the largest implied markup being 3.025830258302583025830258300. | None: the ceiling is a house rule of Acme. The quantization that breaks it comes from the quote of the ECB, read 2026-11-22 |
| `:57` The rate evidence: every rate cited carries the source, the pair, the requested date, the date used and the value. | A house rule of Acme. | None: this is a house rule of Acme |

### 7. [Refund policy](../data/policies/refund-policy.md)

| The rule | What it is | The source |
|---|---|---|
| **Gap 10.** `:13` The overview, which says that Acme Payments is a fictional company created only for this project. | A house rule of Acme, and the only sentence of the eight files that says so. What is wrong: the fiction is stated in one policy of eight and in no chunk of the index. | None: this is a house rule of Acme |
| `:17` The refund window: thirty calendar days after the capture, unless the merchant sets a different one. | A house rule of Acme, a commercial window, that may not be narrower than the right of withdrawal, which is a rule of the world. | Primary: [Directive 2011/83/EU](https://eur-lex.europa.eu/eli/dir/2011/83/oj/eng), Article 9, read 2026-11-22 |
| `:21` to `:33` The window per merchant, who can request a refund, the full and the partial refund, and the three statuses. | A house rule of Acme. | None: this is a house rule of Acme |
| **Gap 8.** `:37` The time to pay: the refund is paid on the same business day or on the next one. | A house rule of Acme, stricter than the law. What is wrong: the file states the time to pay and never the statutory floor of fourteen days, although `:49` already states the rule of the same means of payment of Article 13. | Primary: [Directive 2011/83/EU](https://eur-lex.europa.eu/eli/dir/2011/83/oj/eng), Article 13(1), read 2026-11-22 |
| `:41` to `:53` The reasons for a rejection, the refund that waits for the outcome of a dispute, and the confirmed duplicate. | A house rule of Acme. | None: this is a house rule of Acme |
| `:49` Where the money goes: the same method as the original payment, and a boleto refunded by bank transfer. | A rule of the world in the same means of payment. The rule of the boleto is a house rule of Acme. | Primary: [Directive 2011/83/EU](https://eur-lex.europa.eu/eli/dir/2011/83/oj/eng), Article 13, read 2026-11-22 |
| `:57` to `:65` The text of a request is data and never an instruction, the records kept, and what the answer to the customer states. | A house rule of Acme, a design of the product. | None: this is a house rule of Acme |

### 8. [Settlement schedule](../data/policies/settlement-schedule.md)

| The rule | What it is | The source |
|---|---|---|
| `:13`, `:17`, `:21` The period of one week from Monday to Sunday per merchant, and the four values of a settlement. | A house rule of Acme: the period and the currency of the payout are the choice of a company. | None: this is a house rule of Acme |
| `:25` The net amount is the gross minus the refunds minus the fees, and the sum must add up exactly. | A rule of the world in its arithmetic, and the best proved rule of the corpus: the audit recomputed all 286 settlements and found no mismatch, and the schema holds the identity as a constraint. | None: the audit names no external source for the identity. The proof is the recomputation over the shipped data |
| `:29` The payout is paid two business days after the end of the period. | A house rule of Acme: the audit found no source of the world for the two business days. | None: this is a house rule of Acme |
| `:33` The calendar of each settlement currency: TARGET, B3, the federal holidays of the United States, weekends only for the others. | A rule of the world: these are real calendars, and the audit checked the date of the example of the policy day by day. | The calendars come from the `holidays` library, per [ADR-009](decisions/ADR-009-public-data-first-simulation-for-gaps.md), read 2026-11-22 |
| `:37` The worked example: a period ending on Sunday, October 11, 2026, paid on the 14th in reais and on the 13th in euros. | A house rule of Acme, an illustration the audit checked with the code of the repository: the payout dates are exactly the ones of the file. | The calendars come from the `holidays` library, per [ADR-009](decisions/ADR-009-public-data-first-simulation-for-gaps.md), read 2026-11-22 |
| `:41`, `:45` The settlement currency of the merchant, and the statuses `scheduled` and `paid`. | A house rule of Acme. | None: this is a house rule of Acme |
| **Gap 3.** `:49` The negative balance: no payout on a negative net, and the balance deducted from the next settlement. | A house rule of Acme, and the sharpest disagreement of the audit: two settlements with a negative net, ST-0104 at -1801.20 EUR and ST-0159 at -9.92 EUR, are both paid, and the next settlement does not carry the balance. The practice of the world is to transfer the negative balance to the next settlement batch. | Primary: [Adyen, Balance transfers](https://docs.adyen.com/reporting/balance-transfers/) and [Adyen, Next payout](https://docs.adyen.com/account/balances/next-payout/), read 2026-11-22 |
| `:53` to `:61` A late payout, the reconciliation of a settlement, and what the answer to the merchant shows. | A house rule of Acme. | None: this is a house rule of Acme |

## The thirteen gaps

The audit found twelve places where the corpus says something the world does not say, or something the data of this
repository contradicts, and the review of the milestone found a thirteenth. They are the skeleton of this document, and
each one is marked in the tables above.

| # | The place | What is wrong | What the rule really is | The source |
|---|---|---|---|---|
| 1 | `data/policies/chargeback-handling.md:25` | A window of ten to fourteen days is called the deadline of the card network, and no source of Visa or Mastercard read in the audit gives an acquirer a window that short. | An invention of this project. The window of the network is thirty calendar days for Visa categories 12 and 13, and the Mastercard frames run to forty five days. | Secondary: [Verdikx](https://verdikx.com/resources/chargeback-reason-codes/visa) and [disputed.ai](https://disputed.ai/resources/guides/chargeback-response-deadlines), read 2026-11-22. Primary: [Mastercard Chargeback Guide](https://brand.mastercard.com/content/dam/mccom/en-us/documents/rules/chargeback-guide.pdf), read 2026-11-22 |
| 2 | `data/policies/chargeback-handling.md:21` | The codes FRD, NRC, NAD, DUP and OTH are internal to the company and no network uses them. | A house rule of Acme. A merchant cannot be told which code its case carries in the language of the network. | Primary: [Visa Dispute Management Guide](https://usa.visa.com/content/dam/VCOM/global/support-legal/documents/merchants-dispute-management-guidelines.pdf) and [Visa, Updates and Clarifications](https://usa.visa.com/content/dam/VCOM/global/support-legal/documents/updates-and-clarifications-to-dispute-rule-language.pdf), read 2026-11-22, with the full list of the Visa codes from [Verdikx](https://verdikx.com/resources/chargeback-reason-codes/visa), secondary. Primary: [Mastercard Chargeback Guide](https://brand.mastercard.com/content/dam/mccom/en-us/documents/rules/chargeback-guide.pdf), read 2026-11-22 |
| 3 | `data/policies/settlement-schedule.md:49` | A negative net gets no payout and the balance is carried to the next settlement, and the simulator pays two such settlements: ST-0104 at -1801.20 EUR and ST-0159 at -9.92 EUR. | A house rule of Acme that contradicts the data of this repository. The practice of the world is to transfer the negative balance to the next settlement batch. | Primary: [Adyen, Balance transfers](https://docs.adyen.com/reporting/balance-transfers/) and [Adyen, Next payout](https://docs.adyen.com/account/balances/next-payout/), read 2026-11-22 |
| 4 | `ledgerlens/tools/calculator.py:210` | The guard refuses an applied rate above the reference and tells the model it never happens, and nine rows of the ledger are above the reference inside the rounding band of four decimals. | An invention of this project, a guard on a premise that is false. The cause is the quote of the ECB, which carries five decimals for sterling on some days, against a four decimal quantization. | Primary: the live Frankfurter service, read 2026-11-22, and the recorded series of the repository |
| 5 | `data/policies/fx-reference-rates.md:49` | Above three percent the case is escalated, while the band of five hundredths of a percentage point that `:53` defines is never applied. Sixteen refunds of the merchants at exactly 3.0 percent are escalated, the largest implied markup being 3.025830258302583025830258300. | A house rule of Acme: no rule of the world fixes the ceiling. The ceiling must be read with the band the same file defines. | None: the ceiling is a house rule of Acme. The quantization that breaks it comes from the quote of the ECB, read 2026-11-22 |
| 6 | `data/policies/cross-currency-refunds.md:29` | The file says "up to 3.0% over the reference rate" and then subtracts the markup in the same sentence. | A house rule of Acme with a wording defect. The direction of the spread of an acquirer is a rule of the world, and the spread lowers the rate the customer receives. | The audit attributes the direction to Stripe, "Currency conversions", and to the Mastercard rulebook on currency conversion, and its source list carries no URL and no date for the two. See what is still unverified |
| 7 | `data/policies/fees-and-pricing.md:29` | A tie rule of half to even is stated as a rule of the world, and no row of the ledger exercises the tie: none of the 286 settlements reaches an exact half cent. | A house rule of Acme, a choice of the platform. The practice the audit could read rounds a tie up. | Primary: [Stripe Pricing Policy, clause 1.3](https://stripe.com/legal/pricing-policy), read 2026-11-22 |
| 8 | `data/policies/refund-policy.md:37` | The time to pay a refund is stated and the statutory floor of fourteen days never is, while `:49` already states the rule of the same means of payment of Article 13. | The time to pay is a house rule of Acme, stricter than the law. The floor is a rule of the world and the corpus omits it. | Primary: [Directive 2011/83/EU](https://eur-lex.europa.eu/eli/dir/2011/83/oj/eng), Articles 9 and 13, read 2026-11-22 |
| 9 | `data/policies/chargeback-handling.md:29` and `ledgerlens/verify/escalation.py:30` | The policy names the calendar of the merchant's settlement currency and the code uses the calendar of the currency of the dispute record, and the code says so in its own docstring. | A house rule of Acme either way. The two disagree, so the agent is right by the code and wrong by the policy. | The calendars come from the `holidays` library, per [ADR-009](decisions/ADR-009-public-data-first-simulation-for-gaps.md) |
| 10 | `ledgerlens/retrieval.py:96` | The fiction is stated in one policy of eight (`data/policies/refund-policy.md:13`) and in no chunk of the index, so a served excerpt reads as the rule of a real company. | A house rule of Acme that is not marked anywhere the reader looks. | None: this is a house rule of Acme |
| 11 | `ledgerlens/verify/claims.py:54` | A claim may cite only what is inside this repository, so an answer that is right about the real world can only be contradicted or not enough evidence. | An invention of this project: the vocabulary of the verifier has no way to cite a rule that is not in the corpus. | None: this is a choice of this project |
| 12 | `NOTICE` and `data/sources.lock.json` | The ECB sets three conditions for the reuse of its material and the NOTICE states two, the lock records the string "ECB reuse with source acknowledged" which is not the notice of the ECB, and the cross rates of the committed recordings are computed through the euro without a word about it. | The three conditions are a rule of the world, and the string of the lock is an invention of this project. | Primary: [European Central Bank, Disclaimer and copyright](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html), read 2026-11-22 |
| 13 | `data/policies/chargeback-handling.md:57` | The outcome of the dispute is attributed to the card network, and Acme is said to be unable to change it, in a paragraph that carries no source and no date, so a claim about the world is stated as the contract of the company. | A rule of the world in its shape, the decision of the network that `:13` and `:17` already state with a source. The sentence that Acme cannot change the outcome is a house rule of Acme. | Primary: [Mastercard Chargeback Guide](https://brand.mastercard.com/content/dam/mccom/en-us/documents/rules/chargeback-guide.pdf) and [Mastercard Chargebacks Made Simple Guide](https://www.mastercard.us/content/dam/public/mastercardcom/na/global-site/documents/chargebacks-made-simple-guide.pdf), read 2026-11-22 |

## What the networks and the law really say

This section is the one an analyst reads when a merchant asks what the network really does. It is the context and
not the contract: the contract is the file of Acme that the agent enforces, and the world is this section.

**The window of the network for a chargeback.** The Visa response window for the acquirer is thirty calendar days
for the categories 12 and 13, from the rules of Visa as reported by two secondary sources, Verdikx and
disputed.ai, read 2026-11-22: the Visa document the audit read states that every step of the dispute has a strict
deadline and that the acquirer decides the timeline, without printing the number. The Mastercard frames run to
forty five calendar days, and the issuer has one hundred and twenty calendar days from the Central Site Business
Date to file (Mastercard Chargeback Guide, primary, read 2026-11-22). The window of ten to fourteen days of the
corpus is not a rule of anybody.

**The codes the networks use.** Visa: 10.4, 12.6.1, 13.1, 13.3, 13.5 and 13.7 (Visa Dispute Management Guide and
Visa, Updates and Clarifications, primary, read 2026-11-22, with the complete list from Verdikx, secondary, read
2026-11-22). Mastercard: 4833, 4834, 4835, 4837, 4853 and 4841 (Mastercard Chargeback Guide, primary, read
2026-11-22). A duplicate transaction is 4834 for Mastercard and 12.6.1 for Visa. The five codes of Acme are the
company's own.

**The floor of the refund and the right of withdrawal.** Article 9(1) of Directive 2011/83/EU gives the consumer
fourteen days to withdraw. Article 13(1) says the trader reimburses without undue delay and in any event not
later than fourteen days from the day he is informed of the decision to withdraw, using the same means of payment
as the consumer used for the initial transaction (read 2026-11-22). The fourteen days are a floor and a house
rule may not cross it: the same business day or next of the refund policy and the five business days of the
duplicate policy are stricter, and both are commercial terms of Acme. The floor itself is a rule of the world,
and the corpus omits it.

**The rule of the reference rate.** The reference rate is the daily rate of the European Central Bank, taken
through the Frankfurter service in the version that uses only that source, and a date that is not a business day
returns the rate of the last business day. The audit called the live service on 2026-11-22 and got back the body
the repository records, byte for byte. The ECB sets three conditions on the reuse of its material: the
information must appear accurately and the ECB must be cited as the source, and any modification must be stated
explicitly (Disclaimer and copyright of the ECB, read 2026-11-22). The project modifies the series, because it
computes the cross rates through the euro, and the NOTICE does not say so yet.

**The schedule of the settlement.** The calendar of the payout depends on the currency of the settlement: the
TARGET calendar for the euro, the calendar of B3 for the Brazilian real, the federal holidays of the United
States for the dollar, and weekends only for the others. The audit checked the example day by day with the code
of the repository: a period that ends on Sunday, October 11, 2026 is paid on October 14 in reais, because
Monday the 12th is the holiday of Our Lady of Aparecida, and on October 13 in euros. When the net of a period is
negative, the practice of the world is to transfer the negative balance to the next settlement batch
(`NEGATIVE_AMOUNT_COMPENSATION`), and a negative next payout does not by itself cancel a funded payout (Adyen,
Balance transfers and Next payout, read 2026-11-22). The two business days of the payout of the corpus are a
house rule of Acme, and the audit found no source of the world for them.

## What the corpus of Acme is

The corpus of `data/policies/` is the operations handbook of Acme Payments, a fictional payment service provider
created only for this project, and it is the contract of that company. The agent quotes it to merchants and the
verifier judges every answer against it, so it is simulated data with teeth: the fiction has to be honest about
being a fiction, and it is not, in seven files of eight, until the corrections of the specs are done. Only
`data/policies/refund-policy.md:13` says the company is fictional, and no chunk of the index carries the marker.
The contract is the file the agent enforces, and the world is this document. A rule of the corpus is never a claim
about a card network, a central bank or a law, and where it happens to be true, it is true of Acme and not of the
world. The data of the repository is a different matter: the amounts come from the public dataset of the UCI, the
reference rates from the ECB, the calendars from real calendars, and the simulator invents the disputes, the
fees and the settlements, as [ADR-009](decisions/ADR-009-public-data-first-simulation-for-gaps.md) decided.

## What is still unverified

The audit names what it did not check, and this document does not fill the gaps by guessing.

- **The provision of the United Kingdom was not located.** The audit read section 58 of the Consumer Rights Act
  2015 and it is the section on the powers of the court, so the UK citation is marked unverified. The inference
  that the United Kingdom applies the same fourteen day shape is an inference of the audit and not a verified
  fact.
- **The refund rule of the card regulation was not verified.** The audit did not verify the refund provision of
  Regulation (EU) 2015/751, which governs the card side of this business. It is not cited in any finding of the
  audit, and it is not cited here.
- **The Brazilian right of regret of seven days was not verified.** The audit did not verify it at all, and it
  is not cited in any finding. It would be shorter than the fourteen days of the Union, and it is relevant to the
  merchants of the corpus that trade in Brazil.
- **The two documents of the direction of the spread carry no reference.** The audit attributes the direction of
  the spread of an acquirer to Stripe, "Currency conversions", and to the Mastercard rulebook on currency
  conversion, and its list of sources gives neither a URL nor a date for them. The attribution is published here
  as it stands, without a reference.
- **The label of a sentence that contradicts a policy excerpt is an inference.** The audit did not run the NLI
  model. The label is a reading of the code path of the verifier and of its thresholds.
- **The full text of the two network guides was not read.** The audit read the extracts that the search returned
  for the Visa Dispute Management Guide and for the Mastercard Chargeback Guide. The thirty day Visa response
  window comes from secondary sources and is marked as such.
- **The difference between the PTAX rate and the ECB rate was not measured.** The corpus says the two can differ
  by tenths of a percentage point, and the audit did not measure it, so no figure is stated here.
- **The threshold of excessive disputes of the networks was not looked for**, so no figure is stated for it.
- **The licences of the BIN list and of Nager.Date were not audited** beyond what the NOTICE says about them,
  and the terms of the Nager.Date service were not read.
- **The test suite was not run.** Every statement of the audit about what passes is a statement about what the
  code says.
- **The history of the policies was not checked**, so nobody knows when each rule was written or whether any of
  them was ever checked against a source.

## The sources

Each source was read on the date given. A primary source is the document of the body that makes the rule. A
secondary source reports the rule and is marked as such.

**Card networks**

- [Visa Dispute Management Guide for Merchants](https://usa.visa.com/content/dam/VCOM/global/support-legal/documents/merchants-dispute-management-guidelines.pdf),
  read 2026-11-22. Primary. The conditions 13.1, 13.5 and 13.7, and the strict deadline of every step.
- [Visa, Updates and Clarifications to Dispute Rule Language](https://usa.visa.com/content/dam/VCOM/global/support-legal/documents/updates-and-clarifications-to-dispute-rule-language.pdf),
  read 2026-11-22. Primary. The time limits of the dispute, and the thirty and fifteen day waits.
- [Mastercard Chargeback Guide](https://brand.mastercard.com/content/dam/mccom/en-us/documents/rules/chargeback-guide.pdf),
  read 2026-11-22. Primary. The codes 4834, 4837, 4853 and 4841, the frames, and the duplicate transaction.
- [Mastercard Chargebacks Made Simple Guide](https://www.mastercard.us/content/dam/public/mastercardcom/na/global-site/documents/chargebacks-made-simple-guide.pdf),
  read 2026-11-22. Primary. The four categories of chargeback and the pre-arbitration step.
- [Verdikx, "Visa Chargeback Reason Codes"](https://verdikx.com/resources/chargeback-reason-codes/visa),
  read 2026-11-22. Secondary. The list of the Visa codes and the thirty day response window.
- [disputed.ai, "Chargeback Response Deadlines by Network and Reason"](https://disputed.ai/resources/guides/chargeback-response-deadlines),
  read 2026-11-22. Secondary. The same thirty day window, as a cross check.

**Law and regulator**

- [Directive 2011/83/EU of the European Parliament and of the Council](https://eur-lex.europa.eu/eli/dir/2011/83/oj/eng),
  read 2026-11-22. Primary. Article 9 and Article 13, the fourteen days and the same means of payment.

**Central bank and reference rates**

- [European Central Bank, Disclaimer and copyright](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html),
  read 2026-11-22. Primary. The three conditions of the free use of the material of the site.
- [Frankfurter, live rate for EUR to BRL on 2026-10-05](https://api.frankfurter.dev/v1/2026-10-05?from=EUR&to=BRL),
  read 2026-11-22. Primary. It returned the body that the repository records, byte for byte.

**Acquirer and provider practice**

- [Adyen, Balance transfers](https://docs.adyen.com/reporting/balance-transfers/), read 2026-11-22. Primary. The
  `NEGATIVE_AMOUNT_COMPENSATION` rule and the transfer of a negative balance to the next batch.
- [Adyen, Next payout](https://docs.adyen.com/account/balances/next-payout/), read 2026-11-22. Primary. What a
  negative next payout balance does and does not prevent.
- [Stripe Pricing Policy, clause 1.3](https://stripe.com/legal/pricing-policy), read 2026-11-22. Primary. "Stripe
  rounds each Stripe fee to the nearest unit (e.g., cents). For example, if the fee is 0.025, Stripe will round
  up to 0.03."
- [Stripe, How disputes work](https://docs.stripe.com/disputes/how-disputes-work), read 2026-11-22. Primary. "For
  businesses outside Mexico, the dispute received fee is non-refundable."
- [Stripe, Respond to disputes](https://docs.stripe.com/disputes/responding), read 2026-11-22. Primary. The
  dispute countered fee is returned on a win and the dispute received fee never is.
- [Stripe, June 2025 pricing updates for disputes](https://support.stripe.com/questions/june-2025-pricing-updates-for-disputes),
  read 2026-11-22. Primary. The United States figures of 15 USD for each of the two fees.

**The data owner**

- [UCI Machine Learning Repository, Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii),
  read 2026-11-22. Primary. The licence CC BY 4.0 and the citation that the NOTICE reproduces.

**Inside this repository**

- [ADR-001, the domain of the payment investigation](decisions/ADR-001-payment-investigation-domain.md),
  2026-11-07. The fictional company and the rule that every claim cites its evidence.
- [ADR-009, public data first and simulation only for the gaps](decisions/ADR-009-public-data-first-simulation-for-gaps.md),
  2026-11-07. The single source of the reference rates, the calendars of the `holidays` library, and the
  difference of 2.7 percent between the blended rate and the rate of the ECB.
- [ADR-061, the corpus of the policies is the contract of a fictional company](decisions/ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md),
  2026-11-23. The decision this document serves.
