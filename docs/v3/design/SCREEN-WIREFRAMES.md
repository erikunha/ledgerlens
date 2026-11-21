# Screen wireframes - structural examples, not generated screenshots

## 1. Landing (desktop)

```text
┌───────────────────────────────────────────────────────────────────────┐
│ LedgerLens                   Demo  Scenario Lab  Evals  Engineering  GitHub│
├───────────────────────────────────────────────────────────────────────┤
│  FINANCIAL AGENTS SHOULD SHOW THEIR WORK                              │
│  Evidence-first payment investigation with inspectable agent traces. │
│  [Try demo - no key]  [Explore engineering]                           │
│                                                                       │
│  Ledger  →  Policy / FX  →  Decimal  →  Verified answer               │
│  Recorded replay · Simulated data · Open source                       │
├───────────────────────────────────────────────────────────────────────┤
│  Three experiences     Evidence not guesses     Benchmark with caveats│
└───────────────────────────────────────────────────────────────────────┘
```

## 2. Guided case (desktop)

```text
┌───────────────────┬──────────────────────────────┬─────────────────────┐
│ Scenarios         │ Payment Ledger                │ Agent Narrative     │
│ > FX refund       │ TX-2048 566.79 BRL           │ Step 2 / 5         │
│   Duplicate       │ R-0731 549.31 BRL            │ SQL → FX → Policy   │
│   Dispute          │ [Record details]            │ [Play/Pause/Step]   │
│   Injection        │                              │ Answer evidence ... │
├───────────────────┴──────────────────────────────┴─────────────────────┤
│ Mode: RECORDED REPLAY | Actual captured: <date> | [Show raw trace]      │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. Scenario editor (desktop)

```text
┌──────────────────┬──────────────────────────┬────────────────────────┐
│ Branch timeline  │ Change refund FX rate    │ Before / After         │
│ Base seed 42     │ Refund: R-0731           │ Source hash ...        │
│ Mutation #1      │ Rate: [5.49...]          │ New refund ...         │
│ [Reset]          │ [Preview] [Apply]        │ Invariants ✓           │
│                  │                          │ Replay stale ⚠         │
└──────────────────┴──────────────────────────┴────────────────────────┘
│ [Run deterministic checks] [Use live model - BYOK]                    │
└────────────────────────────────────────────────────────────────────────┘
```

## 4. Agent Inspector (desktop)

```text
┌──────────────────────────┬────────────────────────┬──────────────────────┐
│ Execution tree           │ Evidence panel         │ Decision             │
│ └ investigate 3.2s       │ sql:1 TX-2048          │ CL1 Supported (rule) │
│   ├ triage               │ policy:4 refund rates  │ CL2 Not enough ...   │
│   ├ agent                │ fx:2 recorded rate      │ Human review? No     │
│   │ ├ query_ledger       │ calc:1 delta           │ Answer text ...      │
│   │ ├ get_reference_fx   │ [Source / JSON]         │ [Export]             │
│   └ verification         │                        │                      │
└──────────────────────────┴────────────────────────┴──────────────────────┘
```

## Mobile behavior

Stack the content and provide context tabs `Ledger | Steps | Evidence | Answer` rather than scaling down three columns. Keep current mode and next action visible. Every panel uses semantic headings and supports keyboard navigation. Screenshots/video should show the actual app once implemented, not these planning diagrams.
