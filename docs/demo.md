# Demo recording

- Date of the run: 2026-11-11.
- Mode: online (`LEDGERLENS_OFFLINE=0`). Model `gpt-4.1-mini` (`LEDGERLENS_MODEL`), live exchange rates from Frankfurter, real NLI in the verifier.
- File: [`ledgerlens_demo.mp4`](img/ledgerlens_demo.mp4), 28 s, 3024x1890, 30 fps, H.264, no audio. sha256 `9a891e787bc7b35baf10ac33a84c654e3be47d415f04ae812a0cd7292773a574`.

## What the video shows

1. LedgerLens Pay open, signed in as Mariana Albuquerque Costa (customer C-0412, simulated data), with the Help panel on the right.
2. The suggested question "Why was the BRL refund for TX-2048 lower than the EUR payment?" filled into the Help box, then sent.
3. The agent trace growing live while the agent works: `chain · triage`, `chain · agent`, each `llm · gpt-4.1-mini` call with its latency and token count, and each tool call (`tool · query_ledger`, `tool · search_policies`, `tool · get_reference_fx`, `tool · calculate`) with the SQL it generated.
4. The one-line summary: "Checked 7 sources in 17.4 s, 30109 tokens: 2 claims supported, 2 contradicted, 2 without evidence; goes to human review".
5. The answer, with the citations of the sources it used: `[sql:2]`, `[fx:2026-10-20:EUR-BRL]`, `[calc:2]` and the policy ids.
6. On the statement, the lines the assistant read, marked "read by assistant".

## The numbers on screen

The refund of TX-2048 was processed on 2026-10-20. The ECB market reference rate for EUR to BRL on that date was 5.6339, so the refunded 100.00 EUR would convert to 563.39 BRL, while the payout was 549.31 BRL. The answer names the policy behind the gap: a cross-currency refund converts at the rate of the refund date, so the gap between the market reference and the payout is the applied markup and the rate difference.

## How it was recorded

The Mac screen was recorded with OpenScreen 2.2.2, capturing the "LedgerLens Pay" window (browser window, 1512x945 points on a Retina display, so 3024x1890 pixels). The clicks are real: a Playwright script opened the portal, waited for the page, clicked the suggested question, waited for the box to be filled and clicked "Send". The question box is a form with a submit button, so the agent receives typed text and not a preset answer.

The raw recording is not in this repository. The file here is the master cut to its first 28 seconds and re-encoded, so it fits in git without losing resolution:

```bash
ffmpeg -ss 0 -t 28 -i master.mp4 -vf scale=3024:1890 -r 30 -c:v libx264 -crf 21 -preset slow -pix_fmt yuv420p -an ledgerlens_demo.mp4
```

## The output is probabilistic

The same question on another run can take a different path, call a different set of tools and land on a different set of verdicts. What does not change is the discipline: every claim in the answer gets a verdict, the numbers are checked against the cited evidence by code instead of by the model, and a case that cannot be settled goes to human review.

## No secrets

No key, no authentication header and no real personal data appear in the video. The customer name comes from the simulated sample the project generates.
