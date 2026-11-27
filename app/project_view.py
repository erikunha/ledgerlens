"""Explain how LedgerLens works and let visitors inspect the published evidence."""

import streamlit as st

from app.artifact_views import ROOT, SITE, _artifact_errors, _read, render_engineering, render_evaluation, render_proof

REPOSITORY = "https://github.com/erikunha/ledgerlens/blob/main"
EVALUATION_INDEX = SITE / "eval" / "index.json"
CANDIDATE_REVIEW = "data/eval/reports/policy-resolution-comparison.json"
OPENAI_VERIFIER = "data/eval/report_openai_verifier.json"
POLICY_REVIEW = "data/eval/policy_journey_review.json"


def _render_scores() -> None:
    st.header("Published scores")
    with _artifact_errors():
        report = _read(EVALUATION_INDEX)
        tuning = report["evaluation"]
        held_out = report["verification"]
        runs = _read(ROOT / CANDIDATE_REVIEW)["runs"]
        policy = runs["repeat"]
        candidate = _read(ROOT / OPENAI_VERIFIER)

        agent, verifier, policy_runs = st.columns(3)
        agent.metric("Agent correctness · tuning set", f"{float(tuning['correctness_mean']):.2%}")
        agent.caption(
            f"{tuning['denominator']} cases · {tuning['repeats']} repeats. Mean over the development set. "
            f"[Agent evaluation report]({REPOSITORY}/data/eval/report_online.json)"
        )
        verifier.metric("OpenAI verifier accuracy · held-out set", f"{candidate['correct']} / {candidate['total']}")
        verifier.caption(
            f"Baseline: {held_out['correct']}/{held_out['denominator']}. Two blind model readers supplied the labels. "
            f"[OpenAI verifier results]({REPOSITORY}/{OPENAI_VERIFIER}) · "
            f"[Held-out verifier report]({REPOSITORY}/data/eval/report_heldout.json)"
        )
        policy_runs.metric(
            "Policy questions resolved · development rerun", f"{policy['resolved_cases']} / {policy['total_cases']}"
        )
        policy_runs.caption(
            f"First candidate run: {runs['candidate']['resolved_cases']}/17. "
            f"Baseline rerun: {runs['control']['resolved_cases']}/17. Same 17 questions. "
            "A case counts as resolved when the answer is definitive, "
            f"supported and gives an appropriate action. [Candidate results]({REPOSITORY}/{CANDIDATE_REVIEW}) · "
            f"[Baseline review]({REPOSITORY}/{POLICY_REVIEW})"
        )
    st.caption("The two development scores describe their test sets. Production accuracy is unknown.")


def _render_architecture() -> None:
    st.header("From public data to an investigation")
    st.markdown(
        """
The bundled sample starts with public UCI Online Retail II orders and cancellations. It uses reference exchange
rates from the ECB. Investigations can also request Brazil's PTAX reference rate for BRL pairs.
A seeded simulator adds payment behavior the source data
does not cover, including disputes, payouts, fees and exchange-rate margins. The simulator writes an append-only
event stream. A projector turns those events into the SQLite tables the account browser and agent read.

When you send a question, triage identifies the intent and the records involved. A LangGraph workflow uses that
context to plan tool calls. The tools can query the account's read-only ledger, look up records by ID and retrieve
policy passages. Other tools fetch reference rates, recall relevant cases and calculate amounts with `Decimal`.
Each tool result can supply an evidence ID for the final answer.

Deterministic checks validate claims against evidence, including money and dates. Claims can be supported,
contradicted or marked as having insufficient evidence. The workflow can flag uncertain results for human review.
Learned verification evaluates whether text evidence supports a claim. That component is unavailable in the
visitor demo, which runs deterministic checks.
"""
    )
    st.markdown(
        f"[Data sources]({REPOSITORY}/NOTICE) · [Architecture]({REPOSITORY}/docs/architecture.md) · "
        f"[Tool catalog]({REPOSITORY}/docs/tools.md) · [Evaluation methods]({REPOSITORY}/docs/evaluation.md)"
    )

    st.header("Scripted, recorded and live")
    st.markdown(
        """
- **Scripted demo** runs supported questions against the bundled sample with scripted model responses and recorded
  rate data. You can browse all nine tables in the sample database without a key.
- **Recordings** play back previously captured scripted and real-model runs. Proofs contain evidence IDs,
  deterministic verdicts and the recording's receipt.
- **OpenAI** runs a new investigation with the key you supply. This requires a published snapshot matching the
  selected account and case. The key lives in a session-bound, in-memory vault. The run uses the configured limits,
  and OpenAI may charge for calls. The paid model still investigates demo data.

Use the [case simulator](?view=visitor-sandbox) to change a published case on a private branch and preview the result.
"""
    )


def render_project() -> None:
    """Present the architecture and scores alongside the existing evidence browsers."""
    st.title("Project details")
    st.write("LedgerLens investigates payment complaints and shows the evidence behind its answers.")
    overview, evaluation, proofs, engineering = st.tabs(["How it works", "Evaluation", "Proofs", "Engineering"])
    with overview:
        _render_scores()
        _render_architecture()
    with evaluation:
        st.markdown(
            "**Receipt-backed cutoff verifier** · Offline experiment. The candidate cleared 8 valid dates "
            "and kept all 40 required reviews. All 8 paraphrases still went to review. "
            f"[Cases, comparison and limitations]({REPOSITORY}/docs/evaluation.md#receipt-backed-cutoff-verification)"
        )
        render_evaluation()
    with proofs:
        render_proof()
    with engineering:
        render_engineering()
