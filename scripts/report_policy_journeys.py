"""Measure policy investigations with OpenAI chat and embeddings on synthetic data."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
from collections import Counter
from decimal import Decimal
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from langchain_openai import OpenAIEmbeddings
from langsmith import tracing_context

from ledgerlens.agents.integrator import Integrator, build_integrator, investigate
from ledgerlens.config import PROJECT_ROOT, get_chat_model, get_settings
from ledgerlens.embeddings import DEFAULT_OPENAI_MODEL
from ledgerlens.memory.long_term import CaseMemory
from ledgerlens.observability.callbacks import redact
from ledgerlens.observability.trace import Span, review_reasons
from ledgerlens.retrieval import META_FILE, POLICIES_DIR, index_dir_for
from ledgerlens.sim.projector import create_database
from ledgerlens.tools.fx import FxClient
from ledgerlens.verify import verify_result
from ledgerlens.verify.claims import _citations
from ledgerlens.verify.nli import StubNli
from scripts.check_policy_index import check
from scripts.measure_openai_verifier import MODEL as VERIFIER_MODEL
from scripts.measure_openai_verifier import EvidenceClassifier

CHARGEBACK = ("chargeback-cutoff", "When does Acme require merchant evidence for a chargeback?")
REFUND = ("refund-versus-chargeback", "Do I need to submit a refund request before the chargeback response deadline?")
PET_INSURANCE = ("pet-insurance", "How much pet insurance coverage does Acme provide?")
EXPLICIT_DEADLINE = (
    "explicit-chargeback-deadline",
    "How far before the dispute response deadline must the merchant submit chargeback evidence?",
)
BASELINE_CASES = (CHARGEBACK, REFUND, PET_INSURANCE)
DEADLINE_CASES = (
    (
        "cutoff-passed",
        "Our merchant evidence cutoff passed, but the dispute response deadline is tomorrow. "
        "Have we lost? What should we do today?",
    ),
    (
        "monday-deadline",
        "The dispute response deadline is Monday and Friday is a business day for our settlement currency. "
        "By which day must we send evidence?",
    ),
    (
        "response-late",
        "We sent the merchant response after the dispute response deadline. What happens to the dispute?",
    ),
)
HOLIDAY_CASES = tuple(
    (
        f"july-cutoff-{currency.lower()}",
        f"Our settlement currency is {currency}. The dispute response deadline "
        "is Monday, July 7, 2025. On what date must we submit evidence?",
    )
    for currency in ("USD", "EUR")
)
CONTROLS = (
    (
        "unseen-usd",
        "USD settlement. Our dispute response deadline is Monday, June 1, 2026. What date is the evidence due?",
    ),
    ("unknown-currency", "Our dispute response deadline is Monday, July 7, 2025. What is our exact cutoff date?"),
    ("verify-status", "Has my specific dispute already been marked lost? Please verify its actual recorded status."),
    ("policy-status", "As a general policy, does passing the evidence cutoff automatically lose the dispute?"),
    ("deadline-paraphrase", "We missed the evidence handoff but still have time to respond. What happens now?"),
    (
        "handoff-tuesday",
        "Our internal deadline for the evidence packet was this morning. The deadline for the merchant response "
        "is tomorrow. Does policy already count this as a loss, and who should act today?",
    ),
    (
        "response-question",
        "Suppose the response itself reaches Acme the day after the response deadline. "
        "What does the dispute policy say happens?",
    ),
    (
        "mixed-no-id",
        "Was my dispute marked lost, and what does policy require if the internal evidence cutoff has passed?",
    ),
    (
        "packet-yesterday",
        "The evidence packet was due yesterday and the merchant response is due today. "
        "Is there still a decision for someone to make?",
    ),
    ("late-send", "The merchant sent the response the day after the response deadline. What does policy require?"),
    ("timing", "The internal evidence cutoff passed. What review is required and when must it happen?"),
    ("refund-trigger", "When does a refund need human review because of its amount?"),
    ("settlement-trigger", "When is a payout considered delayed?"),
    ("fee-trigger", "When is the chargeback fee charged?"),
)
CASES = {case[0]: case for case in (*BASELINE_CASES, EXPLICIT_DEADLINE, *DEADLINE_CASES, *HOLIDAY_CASES, *CONTROLS)}
INDEX_ROOT = PROJECT_ROOT / "data/index"
INDEX_FOLDER = INDEX_ROOT / "policies_openai"
RATE_PER_MILLION = {
    "input": Decimal("2"),
    "cached": Decimal("0.50"),
    "output": Decimal("8"),
    "embedding": Decimal("0.02"),
    "verifier_input": Decimal("0.40"),
    "verifier_cached": Decimal("0.10"),
    "verifier_output": Decimal("1.60"),
}


OPENAI_MODEL = "gpt-4.1"
OPENAI_URL = "https://api.openai.com/v1"
MODEL_TIMEOUT_SECONDS = 45
MAX_GENERATED_TOKENS = 2048
POLICY_TOOL = "search_policies"
TOOL_SPAN = "tool"
POLICY_PREFIX = "policy:"
CLARIFICATION = "ask_for_clarification"
ANSWERED = "answered"
CONFIG_PREFIXES = ("LEDGERLENS_", "OPENAI_")


def report_journey(agent: Integrator, case: tuple[str, str]) -> dict:
    """Record a single investigation without inferring whether any policy claim is correct."""
    case_id, question = case
    searches: dict[str, Span] = {}
    calculations: dict[str, Span] = {}

    def capture(span: Span) -> None:
        if span.run_type == TOOL_SPAN and span.name == POLICY_TOOL:
            searches[span.run_id] = span
        if span.run_type == TOOL_SPAN and span.name == "calculate":
            calculations[span.run_id] = span

    result = None
    failure = None
    try:
        result = investigate(agent, question, thread_id=case_id, on_event=capture)
    except Exception as exc:
        failure = redact(f"{type(exc).__name__}: {exc}")

    observations = []
    for span in searches.values():
        output = span.outputs or {}
        data = output.get("data") or {}
        observations.append(
            {
                "input": span.inputs,
                "candidate_ids": output.get("evidence_ids") if output.get("ok") else None,
                "queries_used": data.get("query_used"),
                "transform_used": data.get("transform"),
                "status": span.status,
                "error": span.error,
            }
        )

    answer = result.answer if result and result.answer.strip() else None
    usage = result.usage if result is not None else None
    action = result.recommended_action if result is not None else None
    if failure:
        status = "error"
    elif answer is None:
        status = "no_answer"
    elif usage and usage.get("cut_by"):
        status = "partial"
    elif action == CLARIFICATION:
        status = "clarification"
    else:
        status = ANSWERED
    citations = None
    if answer is not None:
        passages = {
            evidence.id: json.loads(evidence.content).get("text")
            for evidence in result.evidence
            if evidence.tool == POLICY_TOOL
        }
        citations = [
            {"id": value, "passage": passages.get(value)}
            for value in _citations(answer)[1]
            if value.startswith(POLICY_PREFIX)
        ]

    return {
        "case_id": case_id,
        "question": question,
        "status": status,
        "error": failure,
        "answer": answer,
        "search_observed": True if searches else False if result is not None else None,
        "searches": observations,
        "calculations": [{"inputs": s.inputs, "outputs": s.outputs} for s in calculations.values()],
        "policy_citations": citations,
        "judgment": "pending"
        if status == ANSWERED
        and (not observations or any(search["candidate_ids"] is not None for search in observations))
        else None,
        "usage": usage,
        "recommended_action": action,
        "review_reasons": review_reasons(result) if result is not None else None,
        "claims": [claim.model_dump(mode="json") for claim in result.claims] if result is not None else None,
        "verdicts": [verdict.model_dump(mode="json") for verdict in result.verdicts] if result is not None else None,
        "missing_information": result.missing_information if result is not None else None,
        "requires_human_review": result.requires_human_review if result is not None else None,
        "plan_deviations": result.plan_deviations if result is not None else None,
    }


STUB_VERIFIER = "offline_stub"
VERIFIER_FIELD = "verifier"
VERIFIER_WIRE_MODEL = VERIFIER_MODEL.removeprefix("openai:")
INVESTIGATOR_MODELS = {OPENAI_MODEL, "gpt-4.1-2025-04-14"}
CUTOFF_RECEIPTS = "use_cutoff_receipts"


def run_config(*, use_cutoff_receipts: bool = False, openai_verifier: bool = False):
    """Identify source and index inputs, including edits outside the current commit."""
    paths = (
        "ledgerlens/agents/integrator.py",
        "ledgerlens/prompts/templates.py",
        "ledgerlens/chains/triage.py",
        "ledgerlens/tools/policies.py",
        "scripts/report_policy_journeys.py",
        "scripts/measure_openai_verifier.py",
        "ledgerlens/verify/openai_classifier.py",
        "ledgerlens/tools/calculator.py",
        "ledgerlens/sim/calendars.py",
        "ledgerlens/verify/checks.py",
        "ledgerlens/verify/cutoff_receipt.py",
        "ledgerlens/verify/escalation.py",
        "ledgerlens/verify/__init__.py",
    )
    digests = {name: hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest() for name in paths}
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True).strip()
    return {
        "revision": revision,
        "source_sha256": digests,
        "index": json.loads((INDEX_FOLDER / META_FILE).read_text()),
        "model": OPENAI_MODEL,
        VERIFIER_FIELD: VERIFIER_MODEL if openai_verifier else STUB_VERIFIER,
        CUTOFF_RECEIPTS: use_cutoff_receipts,
        "standard_usd_per_million": {k: str(v) for k, v in RATE_PER_MILLION.items()},
    }


async def run_journeys(root: Path, case_ids: list[str], *, checkpoint=None, configuration=None) -> list[dict]:
    """Run the investigator with OpenAI inference and an isolated index of public policies."""
    provider_settings = get_settings().model_copy(update={"offline": False, "embeddings": "openai"})
    with patch.dict(os.environ):
        for name in tuple(os.environ):
            if name.startswith(CONFIG_PREFIXES):
                del os.environ[name]
        os.environ.update(
            {
                "LEDGERLENS_ENV_FILE": str(root / "unused.env"),
                "LEDGERLENS_OFFLINE": "1",
                "LEDGERLENS_EMBEDDINGS": "openai",
                "LEDGERLENS_RUNTIME_DIR": str(root),
                "LANGSMITH_TRACING": "false",
                "LANGCHAIN_TRACING_V2": "false",
                "LANGCHAIN_TRACING": "false",
                "LANGCHAIN_HANDLER": "",
                "HF_HUB_OFFLINE": "1",
            }
        )
        tokens = Counter()

        def requested(request):
            tokens["requests"] += 1

        async def requested_async(request):
            requested(request)

        def record(response):
            response.read()
            if not response.is_success:
                tokens["unpriced_requests"] += 1
                return
            try:
                body = response.json()
                usage = body.get("usage") or {}
            except (ValueError, AttributeError):
                tokens["unpriced_requests"] += 1
                return
            if "prompt_tokens" not in usage:
                tokens["unpriced_requests"] += 1
            elif response.request.url.path.endswith("/embeddings"):
                tokens["embedding"] += usage["prompt_tokens"]
            elif "completion_tokens" not in usage:
                tokens["unpriced_requests"] += 1
                return
            else:
                response_model = body.get("model")
                if response_model == VERIFIER_WIRE_MODEL:
                    prefix = "verifier_"
                elif response_model in INVESTIGATOR_MODELS:
                    prefix = ""
                else:
                    return
                cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
                tokens[prefix + "cached"] += cached
                tokens[prefix + "input"] += usage["prompt_tokens"] - cached
                tokens[prefix + "output"] += usage["completion_tokens"]
            if "prompt_tokens" in usage:
                tokens["priced_requests"] += 1

        async def record_async(response):
            await response.aread()
            record(response)

        with (
            httpx.Client(trust_env=False, event_hooks={"request": [requested], "response": [record]}) as client,
            tracing_context(enabled=False, parent=False),
        ):
            async with httpx.AsyncClient(
                trust_env=False, event_hooks={"request": [requested_async], "response": [record_async]}
            ) as async_client:
                options = dict(
                    openai_proxy="",
                    http_client=client,
                    http_async_client=async_client,
                    temperature=0,
                    max_tokens=MAX_GENERATED_TOKENS,
                    timeout=MODEL_TIMEOUT_SECONDS,
                    max_retries=0,
                )
                model = get_chat_model(provider_settings, model=OPENAI_MODEL, base_url=OPENAI_URL, **options)
                embeddings = OpenAIEmbeddings(
                    model=DEFAULT_OPENAI_MODEL,
                    api_key=provider_settings.openai_api_key,
                    base_url=OPENAI_URL,
                    http_client=client,
                    http_async_client=async_client,
                    openai_proxy="",
                    max_retries=0,
                )
                index_root = INDEX_ROOT
                issues = check(POLICIES_DIR, index_dir_for(index_root, embeddings))
                if issues:
                    raise ValueError("Invalid policy index: " + ", ".join(issues))
                config = configuration if configuration is not None else run_config()
                nli = (
                    EvidenceClassifier(
                        get_chat_model(provider_settings, model=VERIFIER_MODEL, base_url=OPENAI_URL, **options)
                    )
                    if config.get(VERIFIER_FIELD) == VERIFIER_MODEL
                    else StubNli()
                )
                repetitions = Counter()
                reports = []
                for case_id in case_ids:
                    tokens.clear()
                    repetitions[case_id] += 1
                    case_root = root / f"{case_id}-{repetitions[case_id]}"
                    case_root.mkdir()
                    db_path = case_root / "ledger.db"
                    # Policy questions need the ledger schema but have no customer records.
                    create_database(db_path).close()
                    conditions = []
                    agent = build_integrator(
                        model,
                        db_path=db_path,
                        verifier=partial(
                            verify_result,
                            nli=nli,
                            ledger_db=db_path,
                            review_conditions=conditions,
                            use_cutoff_receipts=config.get(CUTOFF_RECEIPTS, False),
                        ),
                        query_model=model,
                        policy_model=model,
                        triage_model=model,
                        embeddings=embeddings,
                        index_root=index_root,
                        case_memory=CaseMemory(case_root / "memory", embeddings=embeddings),
                        fx_client=FxClient(mode="fixtures"),
                    )
                    report = report_journey(agent, CASES[case_id])
                    report["review_conditions"] = conditions
                    cost = sum(tokens[key] * rate for key, rate in RATE_PER_MILLION.items()) / Decimal(1_000_000)
                    tokens["unpriced_requests"] = tokens["requests"] - tokens["priced_requests"]
                    report.update(
                        repetition=repetitions[case_id],
                        provider_tokens=dict(tokens),
                        estimated_online_usd=str(cost)
                        if tokens["requests"] and not tokens["unpriced_requests"]
                        else None,
                    )
                    reports.append(report)
                    if checkpoint is not None:
                        checkpoint.write(json.dumps({"configuration": config, "case": report}) + "\n")
                        checkpoint.flush()
                        os.fsync(checkpoint.fileno())
                return reports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--case", choices=CASES)
    group.add_argument("--all", action="store_true", help="Run baseline and diagnostic cases.")
    parser.add_argument(
        "--openai-verifier", action="store_true", help="Verify claims with the frozen OpenAI classifier."
    )
    parser.add_argument("--use-cutoff-receipts", action="store_true", help="Evaluate receipt-backed cutoff claims.")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--checkpoint", type=Path, help="Write each completed case to a new JSONL file.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero on operational failures.")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    selected = [args.case] if args.case else list(CASES) if args.all else [case[0] for case in BASELINE_CASES]
    configuration = run_config(use_cutoff_receipts=args.use_cutoff_receipts, openai_verifier=args.openai_verifier)
    with TemporaryDirectory(prefix="ledgerlens_policy_journeys_") as folder:
        if args.checkpoint:
            with args.checkpoint.open("x", encoding="utf-8") as checkpoint:
                cases = asyncio.run(
                    run_journeys(
                        Path(folder), selected * args.repeat, checkpoint=checkpoint, configuration=configuration
                    )
                )
        else:
            cases = asyncio.run(run_journeys(Path(folder), selected * args.repeat, configuration=configuration))
    counts = Counter(case.get("status", "unknown") for case in cases)
    costs = [Decimal(c["estimated_online_usd"]) for c in cases if c.get("estimated_online_usd") is not None]
    billing = {
        "priced_cases": len(costs),
        "total_cases": len(cases),
        "estimated_online_usd": str(sum(costs)) if costs and len(costs) == len(cases) else None,
    }
    print(
        json.dumps(
            {**configuration, "counts": counts, "billing": billing, "cases": cases}, indent=2, ensure_ascii=False
        )
    )
    if args.strict and any(
        c.get("status") in ("error", "partial", "no_answer")
        or c.get("estimated_online_usd") is None
        or any(s.get("error") for s in c.get("searches", []))
        or any((s.get("outputs") or {}).get("ok") is False for s in c.get("calculations", []))
        for c in cases
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
