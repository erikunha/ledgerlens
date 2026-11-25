# The comparison of the studio against the single agent

> Real run of the two arms over the same set of cases, over the same ledger, with the same model and with the deterministic judge of the repository. One run per case: the numbers are a trend and not a statistical significance. The answer of the studio is composed and not written by a model: it renders the evidence the verifier supported, and a case the studio did not resolve counts in the denominator like any other. The dollars of a model whose price nobody verified are unknown, and unknown is never zero.

The set of the comparison is 31 cases (`eval_cases.jsonl`, digest `28f16cabcbb7391112ac6a7bbe6567ec877eeba3207dd1caa3c3933761362351`), the denominator of every measure is the 31 cases of the set, and the ledger of the two arms is `994667ee48fb14a1f59858b2861716e291e9bd235c0817bf9c34904a9e10e91a`. The model of the two arms is `gpt-4.1-mini`, the commit of the run is `b407c10e83db65a551b4beeb104493d8e948a8d5` and the manifest of the experiment is `data/runtime/orchestration/comparison.json` (digest `4ccaa3300e4905bc6ca1773c5becb9d059a5410b7f534037d6fe0ec506be8148`), registered before the run.

The judge of the two arms is the deterministic judge of the repository, with the stub of the NLI and the fixtures of the exchange: the absolute numbers of this page are not the numbers of the published online report, and the two arms are the ones that are comparable with each other.

## The arm `single_agent`

The path that the repository ships: one agent of ledgerlens/agents/integrator.py with its six tools and the deterministic verifier of ledgerlens/verify/.

- The correct cases: 22 of 31.
- The cost per correct case: 0.004823 dollars.
- The p95 of the latency: 10082 ms over 31 cases.
- The calls of the tools: 47 over 31 cases.

## The arm `orchestration_studio`

The experimental variant: a plan of steps dispatched to specialists under the budget of the run, with the same tools, the same verifier and the same model of the single agent.

- The correct cases: 22 of 31.
- The cost per correct case: 0.000909 dollars.
- The p95 of the latency: 6593 ms over 31 cases.
- The calls of the tools: 36 over 31 cases.

## The difference of the arms

The studio resolved 0 more case(s) than the single agent: 3 case(s) only the studio resolved and 3 case(s) only the single agent resolved. The interval of the difference of the correctness is [-0.0278, 0.0278] (the paired difference of the correctness, with the standard error of the discordant cases and the normal approximation of 95 percent).

## The rule and the decision

The rule of the manifest: The studio is a gain only when it resolves strictly more cases than the single agent over the same 31 cases, with a difference of at least 2 cases, and its cost per resolved case is not higher than the cost per resolved case of the single agent. A difference of 0 or 1 case is a trend and not a gain. A studio that costs more and answers the same is not a gain. When the money of an arm is unknown, the comparison of the money is not established and the flag stays off. The flag stays off in every other case, and the result is published either way.

The decision: **the flag stays off**. the difference of 0 case(s) is a trend and not a gain: the rule asks for a difference of at least 2 cases.

## The uncertainty

One run per case over 31 cases makes the difference of the arms a trend and not a statistical significance. The page of the result publishes the interval of the difference of the correctness, and an interval that covers zero keeps the flag off. The threshold of 2 cases is a decision of the repository and not a significance, and the page says so.

The number of this page was measured over the set it names and is not a generalization: it says what the two arms did over these cases, with this model and with this snapshot, and nothing else.

