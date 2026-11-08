"""Evaluation set: 30 cases with an expected answer and an expected tool trajectory.

Why it exists: evaluating with a few good cases does not show whether the agent works, and evaluating with no
answer key shows nothing. The cases have two origins:

- **12 from scenarios**: one per planted scenario in `data/scenarios.json`. The question, the expected tools
  and the expected values come from the manifest; the choice of queries is made here.
- **18 natural**: taken from the generated database (6 transaction statuses, 6 payouts, 6 policy questions).
  The expected values come from the tables by code, never from hand-written text.

Each case may declare `equivalent_tools`, the groups of tools that count as the same in the trajectory
scores by equivalence (see `RECORD_LOOKUP_TOOLS`: which swaps count, for which cases and why).

Each case also carries the offline script: the `steps` (the tool, the arguments and, for `query_ledger`, the SQL
the scripted model returns) and the `lines` of the scripted answer, each with the evidence it cites.
The script only applies to the run with no model; online, the question is all the agent gets.

The file `data/eval/eval_cases.jsonl` is the output of `build_cases` over the versioned sample database and is
checked by a test: if the generator or the data change, the test asks to regenerate it with
`uv run python -m ledgerlens.eval.dataset`.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from ledgerlens.config import PROJECT_ROOT
from ledgerlens.retrieval import POLICIES_DIR, load_policy_documents
from ledgerlens.schemas import Claim, Coherence, Evidence, InvestigationResult, Strict
from ledgerlens.verify.claims import extract_claims

CASES_PATH = PROJECT_ROOT / "data" / "eval" / "eval_cases.jsonl"
SCENARIOS_PATH = PROJECT_ROOT / "data" / "scenarios.json"
VERIFICATION_SET_PATH = PROJECT_ROOT / "data" / "eval" / "verification_set.jsonl"
POLICY_QUESTIONS_PATH = PROJECT_ROOT / "data" / "eval" / "policy_questions.jsonl"

# Easy policy questions from the questions file: the vocabulary repeats the excerpt that answers it.
POLICY_QUESTION_IDS = ("PQ-01", "PQ-02", "PQ-03", "PQ-04", "PQ-05", "PQ-06")
# One transaction status per natural case, from least to most rare.
STATUS_CASES = ("captured", "failed", "partially_refunded", "refunded", "disputed", "charged_back")
SETTLEMENT_CASES = 6

# Evidence id prefix by the tool that produces it.
EVIDENCE_PREFIX = {
    "query_ledger": "sql",
    "get_ledger_record": "api",
    "search_policies": "policy",
    "get_reference_fx": "fx",
    "calculate": "calc",
    "recall_cases": "case",
}

# Tool equivalence in the trajectory. Only one kind of case declares a group: looking up a record by id
# (a transaction's status). `get_ledger_record` and `query_ledger` return the same ledger row, the first
# by id and the second through generated SQL, so using one in place of the other reaches the same evidence. In the
# other cases the tools are not interchangeable: policy, FX and calculation bring facts the ledger does not have,
# and a planted scenario tests precisely the choice of tool, so they stay exact. Equivalence only counts in the
# `trajectory_equivalent_*` scores; the `trajectory_*` scores stay exact.
RECORD_LOOKUP_TOOLS = ("get_ledger_record", "query_ledger")

FX_SQL = "SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at"


class ExpectationChange(Strict):
    """An answer key that changed after an online run, with what held before and the reason."""

    cases: list[str]
    before: list[str]
    after: list[str]
    reason: str


# The answer key of the six natural payouts asked for `query_ledger` and `calculate`. In the online run the model read
# the net amount from the table and did not call `calculate`: the answer was right and the trajectory lost points.
# The decision was about the answer key, not the agent, and it stays here and in the report for whoever compares runs.
EXPECTATION_CHANGES = [
    ExpectationChange(
        cases=["EC-19", "EC-20", "EC-21", "EC-22", "EC-23", "EC-24"],
        before=["query_ledger", "calculate"],
        after=["query_ledger"],
        reason=(
            "The question is the payout's net amount, and the settlements table already keeps it in net_minor; in the "
            "six payouts net_minor equals gross_minor - refunds_minor - fees_minor, which is what calculate would "
            "redo with the same three columns, and the settlement_net coherence rule checks that equality by itself. "
            "Calculate is still expected where the question is how the payout was calculated (EC-08, scenario S08)."
        ),
    )
]


class Step(Strict):
    """A tool call of the script. `sql` is the query the scripted model returns to `query_ledger`."""

    tool: str
    args: dict[str, Any]
    sql: str | None = None


class Line(Strict):
    """A sentence of the scripted answer and the evidence it cites."""

    text: str
    evidence: list[str] = []


class EvalCase(Strict):
    """A case: the question, the answer key (facts and tools) and the offline run's script."""

    id: str
    kind: str  # "scenario" or "natural"
    scenario: str | None
    question: str
    expected_facts: list[str]
    expected_tools: list[str]
    steps: list[Step]
    lines: list[Line]
    fx_fault: bool = False
    equivalent_tools: list[list[str]] = []

    @property
    def answer(self) -> str:
        """The scripted answer: each sentence followed by its `[id, id]` citations."""
        parts = [
            f"{line.text} [{', '.join(line.evidence)}]." if line.evidence else f"{line.text}." for line in self.lines
        ]
        return " ".join(parts)


def build_sample_ledger(db_path: Path | str) -> Path:
    """Builds the ledger from the versioned sample and returns the database path."""
    from ledgerlens.sim.config import SimConfig
    from ledgerlens.sim.pipeline import build_ledger

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    build_ledger(SimConfig(source="sample"), path).conn.close()
    return path


def _policy_sentences(policies_dir: Path | str = POLICIES_DIR) -> dict[str, str]:
    """The first sentence of each policy excerpt's body, by `chunk_id`. The first line is the heading."""
    sentences: dict[str, str] = {}
    for document in load_policy_documents(policies_dir):
        body = document.page_content.split("\n", 1)[-1].replace("\n", " ")
        end = body.find(". ")
        sentences[document.metadata["chunk_id"]] = (body if end < 0 else body[:end]).strip().rstrip(".")
    return sentences


def _money(minor: int) -> str:
    return str((Decimal(minor) / 100).quantize(Decimal("0.01")))


def _scenario_cases(scenarios: dict[str, Any], sentences: dict[str, str]) -> list[dict[str, Any]]:
    """The 12 scenario cases. The expected values come from the manifest (`truth`)."""
    truth = {s["id"]: s["truth"] for s in scenarios["scenarios"]}
    t1, t8, t11, t12 = truth["S01"], truth["S08"], truth["S11"], truth["S12"]
    fx_rate_args = {"from_currency": "EUR", "to_currency": "BRL", "date": "2026-10-20"}

    def policy(chunk: str) -> Line:
        return Line(text=sentences[chunk], evidence=[f"policy:{chunk}"])

    plans: dict[str, dict[str, Any]] = {
        "S01": {
            "steps": [
                Step(tool="query_ledger", args={"question": "FX rates applied to TX-2048"}, sql=FX_SQL),
                Step(
                    tool="search_policies",
                    args={"query": "refund in another currency exchange rate", "k": 8, "transform": "none"},
                ),
                Step(tool="get_reference_fx", args=fx_rate_args),
                Step(
                    tool="calculate",
                    args={
                        "operation": "fx_gap_breakdown",
                        "values": {
                            "units": "100.00",
                            "charge_rate": t1["charge_rate"],
                            "refund_reference_rate": t1["reference_rate_refund_date"],
                            "refund_applied_rate": t1["applied_rate"],
                        },
                    },
                ),
            ],
            "lines": [
                Line(text=f"charge_brl {t1['charge_brl']}", evidence=["calc:1"]),
                Line(text=f"refund_brl {t1['refund_brl']}", evidence=["calc:1"]),
                Line(text=f"gap_brl {t1['gap_brl']}", evidence=["calc:1"]),
                Line(text=f"markup_brl {t1['markup_brl']}", evidence=["calc:1"]),
                Line(text=f"refund applied_rate {t1['applied_rate']}", evidence=["sql:1"]),
                policy("fx-reference-rates#comparing-with-applied"),
            ],
            "facts": [t1["charge_brl"], t1["refund_brl"], t1["gap_brl"], t1["markup_brl"]],
        },
        "S02": {
            "steps": [
                Step(
                    tool="query_ledger",
                    args={"question": "transactions TX-2051 and TX-2052"},
                    sql="SELECT id, merchant_id, amount_minor, currency, card_fingerprint FROM transactions "
                    "WHERE id IN ('TX-2051', 'TX-2052') ORDER BY id",
                ),
                Step(
                    tool="search_policies",
                    args={"query": "duplicate charge detection rule", "k": 8, "transform": "none"},
                ),
            ],
            "lines": [
                Line(
                    text=f"{truth['S02']['original']} amount_minor {truth['S02']['refund_minor']}", evidence=["sql:1"]
                ),
                Line(
                    text=f"{truth['S02']['duplicate']} amount_minor {truth['S02']['refund_minor']}", evidence=["sql:1"]
                ),
                policy("duplicate-charges#detection-rule"),
            ],
            "facts": [truth["S02"]["duplicate"], truth["S02"]["original"], str(truth["S02"]["refund_minor"])],
        },
        "S03": {
            "steps": [
                Step(
                    tool="query_ledger",
                    args={"question": "dispute CB-0310"},
                    sql="SELECT id, transaction_id, reason_code, stage, deadline FROM chargebacks WHERE id = 'CB-0310'",
                ),
                Step(
                    tool="search_policies",
                    args={"query": "response deadline for a dispute", "k": 8, "transform": "none"},
                ),
            ],
            "lines": [
                Line(text=f"CB-0310 deadline {truth['S03']['deadline']}", evidence=["sql:1"]),
                Line(text=f"CB-0310 stage {truth['S03']['stage']}", evidence=["sql:1"]),
                Line(text=f"CB-0310 reason_code {truth['S03']['reason_code']}", evidence=["sql:1"]),
                policy("chargeback-handling#response-deadline"),
            ],
            "facts": [truth["S03"]["deadline"], truth["S03"]["stage"], truth["S03"]["reason_code"]],
        },
        "S04": {
            "steps": [
                Step(
                    tool="query_ledger",
                    args={"question": "the status of TX-9999"},
                    sql="SELECT id, status FROM transactions WHERE id = 'TX-9999'",
                ),
            ],
            "lines": [Line(text="TX-9999 row_count 0", evidence=["sql:1"])],
            "facts": ["TX-9999", "row_count 0"],
        },
        "S05": {
            "steps": [
                Step(
                    tool="query_ledger",
                    args={"question": "the purchases of customer C-0205"},
                    sql="SELECT id, merchant_id, amount_minor, currency FROM transactions "
                    "WHERE customer_id = 'C-0205' ORDER BY id",
                ),
            ],
            "lines": [
                Line(text=f"{m['transaction_id']} merchant_id {m['merchant_id']}", evidence=["sql:1"])
                for m in truth["S05"]["matches"]
            ],
            "facts": [v for m in truth["S05"]["matches"] for v in (m["transaction_id"], m["merchant_id"])],
        },
        "S06": {
            "steps": [
                Step(
                    tool="query_ledger",
                    args={"question": "the refund for TX-2090"},
                    sql="SELECT r.id, r.status, r.reason FROM refunds r WHERE r.transaction_id = 'TX-2090'",
                ),
                Step(
                    tool="search_policies",
                    args={"query": "deadline to ask for a refund after capture", "k": 8, "transform": "none"},
                ),
            ],
            "lines": [
                Line(text=f"TX-2090 refund status {truth['S06']['status']}", evidence=["sql:1"]),
                policy(truth["S06"]["policy_chunk"]),
            ],
            "facts": [truth["S06"]["status"], truth["S06"]["policy_chunk"]],
        },
        "S07": {
            "steps": [
                Step(
                    tool="query_ledger",
                    args={"question": "refund R-0720 and transaction TX-2030"},
                    sql="SELECT r.id, r.payout_amount_minor, t.amount_minor FROM refunds r "
                    "JOIN transactions t ON t.id = r.transaction_id WHERE r.id = 'R-0720'",
                ),
                Step(
                    tool="calculate",
                    args={
                        "operation": "difference",
                        "values": {"a": truth["S07"]["charge"], "b": truth["S07"]["refund"]},
                    },
                ),
            ],
            "lines": [
                Line(
                    text=f"R-0720 payout_amount_minor {int(Decimal(truth['S07']['refund']) * 100)}", evidence=["sql:1"]
                ),
                Line(text=f"difference {truth['S07']['difference']}", evidence=["calc:1"]),
            ],
            "facts": [truth["S07"]["difference"], str(int(Decimal(truth["S07"]["refund"]) * 100))],
        },
        "S08": {
            "steps": [
                Step(
                    tool="query_ledger",
                    args={"question": "payout ST-0044"},
                    sql="SELECT * FROM settlements WHERE id = 'ST-0044'",
                ),
                Step(tool="search_policies", args={"query": "when the payout is paid", "k": 8, "transform": "none"}),
                Step(
                    tool="calculate",
                    args={
                        "operation": "net_settlement",
                        "values": {
                            "gross": _money(t8["gross_minor"]),
                            "refunds": "0.00",
                            "fees": _money(t8["fees_minor"]),
                        },
                    },
                ),
            ],
            "lines": [
                Line(text=f"ST-0044 net_minor {t8['net_minor']}", evidence=["sql:1"]),
                Line(text=f"ST-0044 expected_payout_date {t8['expected_payout_date']}", evidence=["sql:1"]),
                Line(text=f"net_settlement {_money(t8['net_minor'])}", evidence=["calc:1"]),
                policy("settlement-schedule#payout-timing"),
            ],
            "facts": [str(t8["net_minor"]), t8["expected_payout_date"], _money(t8["net_minor"])],
        },
        "S09": {
            "steps": [
                Step(
                    tool="query_ledger",
                    args={"question": "refund R-0750"},
                    sql="SELECT id, transaction_id, status FROM refunds WHERE id = 'R-0750'",
                ),
            ],
            "lines": [Line(text=f"R-0750 status {truth['S09']['status']}", evidence=["sql:1"])],
            "facts": ["R-0750", truth["S09"]["status"]],
        },
        "S10": {
            "steps": [
                Step(
                    tool="query_ledger",
                    args={"question": "transaction TX-2099"},
                    sql="SELECT id, amount_minor, currency FROM transactions WHERE id = 'TX-2099'",
                ),
                Step(
                    tool="get_reference_fx", args={"from_currency": "EUR", "to_currency": "ARS", "date": "2026-10-15"}
                ),
            ],
            "lines": [
                Line(text=f"TX-2099 currency {truth['S10']['currency']}", evidence=["sql:1"]),
                Line(text=f"TX-2099 amount_minor {int(Decimal(truth['S10']['amount']) * 100)}", evidence=["sql:1"]),
            ],
            "facts": [truth["S10"]["currency"], str(int(Decimal(truth["S10"]["amount"]) * 100))],
        },
        "S11": {
            "steps": [
                Step(tool="query_ledger", args={"question": "FX rates applied to TX-2048"}, sql=FX_SQL),
                Step(tool="get_reference_fx", args=fx_rate_args),
            ],
            "lines": [
                Line(text=f"refund applied_rate {t1['applied_rate']}", evidence=["sql:1"]),
                Line(text=f"The rate {t11['missing_rate']} was missing because get_reference_fx was unavailable"),
            ],
            "facts": [t11["missing_rate"], t1["applied_rate"]],
            "fx_fault": True,
        },
        "S12": {
            "steps": [
                Step(
                    tool="recall_cases",
                    args={"query": "FX markup on refunds by merchant M-17", "merchant_id": "M-17"},
                ),
            ],
            "lines": [Line(text=t12["finding"], evidence=[f"case:{t12['case_id']}"])],
            "facts": [t12["case_id"]],
        },
    }
    cases = []
    for scenario in scenarios["scenarios"]:
        plan = plans[scenario["id"]]
        expected = scenario["expected_tools"]
        if [s.tool for s in plan["steps"]] != expected:
            raise ValueError(f"{scenario['id']}: the steps do not follow the manifest tools {expected}")
        cases.append(
            {
                "kind": "scenario",
                "scenario": scenario["id"],
                "question": scenario["questions"][0],
                "expected_facts": plan["facts"],
                "expected_tools": expected,
                "steps": plan["steps"],
                "lines": plan["lines"],
                "fx_fault": plan.get("fx_fault", False),
            }
        )
    return cases


def _natural_cases(conn: sqlite3.Connection, sentences: dict[str, str]) -> list[dict[str, Any]]:
    """The 18 natural cases, with the expected values read from the tables."""
    cases: list[dict[str, Any]] = []
    for status in STATUS_CASES:
        # Only transactions from the public base: the scenario ones already have their own case.
        (tx_id,) = conn.execute(
            "SELECT id FROM transactions WHERE status = ? AND origin = 'public' ORDER BY id LIMIT 1", (status,)
        ).fetchone()
        cases.append(
            {
                "kind": "natural",
                "scenario": None,
                "question": f"What is the status of {tx_id}?",
                "expected_facts": [tx_id, status],
                "expected_tools": ["get_ledger_record"],
                "equivalent_tools": [list(RECORD_LOOKUP_TOOLS)],
                "steps": [Step(tool="get_ledger_record", args={"kind": "transaction", "id": tx_id})],
                "lines": [Line(text=f"{tx_id} status {status}", evidence=["api:1"])],
            }
        )
    rows = conn.execute(
        "SELECT id, merchant_id, gross_minor, refunds_minor, fees_minor, net_minor FROM settlements "
        "WHERE refunds_minor > 0 AND id NOT IN ('ST-0044') ORDER BY id LIMIT ?",
        (SETTLEMENT_CASES,),
    ).fetchall()
    for settlement_id, merchant_id, _gross, _refunds, _fees, net in rows:
        # The question is the net amount the table already keeps in `net_minor`: only `query_ledger` is expected.
        # A `calculate` would redo `gross - refunds - fees` with the same columns, with no new fact (see
        # `EXPECTATION_CHANGES`).
        cases.append(
            {
                "kind": "natural",
                "scenario": None,
                "question": f"What was the net amount of payout {settlement_id} for merchant {merchant_id}?",
                # minor or major units count the same for the evaluator, so it is a single fact
                "expected_facts": [str(net)],
                "expected_tools": ["query_ledger"],
                "steps": [
                    Step(
                        tool="query_ledger",
                        args={"question": f"payout {settlement_id}"},
                        sql="SELECT id, gross_minor, refunds_minor, fees_minor, net_minor FROM settlements "
                        f"WHERE id = '{settlement_id}'",
                    ),
                ],
                "lines": [Line(text=f"{settlement_id} net_minor {net}", evidence=["sql:1"])],
            }
        )
    questions = {
        json.loads(line)["id"]: json.loads(line)
        for line in POLICY_QUESTIONS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    for question_id in POLICY_QUESTION_IDS:
        item = questions[question_id]
        (chunk,) = item["gold_chunk_ids"]
        cases.append(
            {
                "kind": "natural",
                "scenario": None,
                "question": item["question"],
                "expected_facts": [chunk],
                "expected_tools": ["search_policies"],
                "steps": [Step(tool="search_policies", args={"query": item["question"], "k": 8, "transform": "none"})],
                "lines": [Line(text=sentences[chunk], evidence=[f"policy:{chunk}"])],
            }
        )
    return cases


def build_cases(db_path: Path | str, *, scenarios_path: Path = SCENARIOS_PATH) -> list[EvalCase]:
    """The 30 cases, in order: 12 from scenarios, then 18 natural. Deterministic for the same database."""
    scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))
    sentences = _policy_sentences()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        raw = _scenario_cases(scenarios, sentences) + _natural_cases(conn, sentences)
    finally:
        conn.close()
    return [EvalCase(id=f"EC-{index:02d}", **item) for index, item in enumerate(raw, start=1)]


def write_cases(cases: list[EvalCase], path: Path = CASES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(case.model_dump_json() + "\n" for case in cases), encoding="utf-8")


def load_cases(path: Path = CASES_PATH) -> list[EvalCase]:
    """Reads the versioned cases, in file order."""
    return [
        EvalCase.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def main() -> None:
    """Regenerates `data/eval/eval_cases.jsonl` over a ledger built from the versioned sample."""
    with tempfile.TemporaryDirectory(prefix="ledgerlens_eval_") as work:
        cases = build_cases(build_sample_ledger(Path(work) / "ledger.db"))
    write_cases(cases)
    print(f"{len(cases)} cases in {CASES_PATH}")


if __name__ == "__main__":
    main()


# --- verification set -------------------------------------------------------------------------------------
# The 43 cases of `data/eval/verification_set.jsonl` validate the verifier: text and numeric claims with the
# expected verdict, and sets of claims where coherence fails (a planted contradiction) or passes.

_VERIFICATION_NOW = datetime(2026, 11, 8, tzinfo=UTC)
_VERIFICATION_TOOLS = {"sql": "query_ledger", "policy": "search_policies", "calc": "calculate"}


def load_verification_cases(path: Path = VERIFICATION_SET_PATH) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def expected_verdict(case: dict[str, Any]) -> str:
    """The case's expected verdict. In a coherence case, planted is `contradicted` and clean is `supported`."""
    if case["type"] == "coherence":
        return "contradicted" if case["planted"] else "supported"
    return str(case["expected"])


def _evidence(evidence_id: str, content: str) -> Evidence:
    source = evidence_id.split(":")[0]
    return Evidence(
        id=evidence_id,
        source_type=source,
        tool=_VERIFICATION_TOOLS[source],
        content=content,
        ref=evidence_id,
        retrieved_at=_VERIFICATION_NOW,
    )


def verification_result(case: dict[str, Any]) -> InvestigationResult:
    """The investigation result the verifier gets: one claim, or several in the coherence cases."""
    if case["type"] == "text":
        evidence = [_evidence("policy:1" if case["evidence"].startswith("Policy") else "sql:1", case["evidence"])]
        claims = [Claim(id="CL1", text=case["claim"], kind="fact", evidence_ids=[evidence[0].id])]
        action = "none"
    elif case["type"] == "numeric":
        evidence = [_evidence("calc:1", case["calc"])]
        claims = extract_claims(f"{case['claim']} [calc:1]", evidence)
        action = "none"
    else:
        evidence = [_evidence(e["id"], e["content"]) for e in case["evidence"]]
        claims = [
            Claim(id=f"CL{i}", text=c["text"], kind="fact", evidence_ids=c["evidence_ids"])
            for i, c in enumerate(case["claims"], 1)
        ]
        action = case["action"]
    return InvestigationResult(
        session_id=f"verification-{case['id']}",
        question="q",
        answer="a",
        claims=claims,
        evidence=evidence,
        verdicts=[],
        coherence=Coherence(passed=True),
        recommended_action=action,
        requires_human_review=False,
    )
