"""The eight policy documents and the 12 policy questions: structure, the facts other tasks rely on,
language, and that every gold chunk id exists.

A chunk id is `<document>#<anchor>`. The anchor is written next to the heading as `{#anchor}`, so
ids stay stable while headings and text can change.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"
POLICIES = DATA / "policies"
QUESTIONS = DATA / "eval" / "policy_questions.jsonl"

DOCUMENTS = {
    "refund-policy": "refund",
    "cross-currency-refunds": "fx",
    "chargeback-handling": "chargeback",
    "duplicate-charges": "duplicate",
    "settlement-schedule": "settlement",
    "fees-and-pricing": "fees",
    "fx-reference-rates": "fx",
    "escalation-and-review": "escalation",
}
TOPICS = {"refund", "fx", "chargeback", "duplicate", "settlement", "fees", "escalation"}
HEADING = re.compile(r"^(#{2,3}) (?P<title>.+?) \{#(?P<anchor>[a-z0-9-]+)\}\s*$")
MAX_CHUNK = 800


def parse(path: Path) -> tuple[dict[str, str], list[dict]]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, f"{path.name} has no front matter"
    meta = dict(line.split(": ", 1) for line in match.group(1).splitlines())
    sections, current = [], None
    for line in text[match.end() :].splitlines():
        heading = HEADING.match(line)
        if heading:
            current = {"title": heading["title"], "anchor": heading["anchor"], "lines": []}
            sections.append(current)
        elif current is not None:
            current["lines"].append(line)
        elif line.startswith("## ") or line.startswith("### "):
            pytest.fail(f"{path.name}: heading without an anchor: {line}")
    for section in sections:
        section["text"] = "\n".join(section.pop("lines")).strip()
    return meta, sections


def split(text: str) -> list[str]:
    """Pieces of at most 800 characters with 100 characters of overlap, as the index builder will do."""
    if len(text) <= MAX_CHUNK:
        return [text]
    pieces, start = [], 0
    while start < len(text):
        pieces.append(text[start : start + MAX_CHUNK])
        if start + MAX_CHUNK >= len(text):
            break
        start += MAX_CHUNK - 100
    return pieces


@pytest.fixture(scope="module")
def corpus() -> dict[str, tuple[dict, list[dict]]]:
    return {path.stem: parse(path) for path in sorted(POLICIES.glob("*.md"))}


@pytest.fixture(scope="module")
def sections(corpus) -> dict[str, dict]:
    return {f"{name}#{s['anchor']}": s for name, (_, items) in corpus.items() for s in items}


def test_there_are_exactly_the_eight_documents(corpus):
    assert set(corpus) == set(DOCUMENTS)


def test_front_matter_has_the_chunk_metadata(corpus):
    for name, (meta, _) in corpus.items():
        assert meta["document"] == name
        assert meta["topic"] == DOCUMENTS[name] and meta["topic"] in TOPICS
        assert meta["version"] == "2026-10-01"
        assert meta["language"] == "en"
        assert meta["title"]


def test_the_company_is_acme_payments(corpus):
    for name in corpus:
        assert "Acme Payments" in (POLICIES / f"{name}.md").read_text(encoding="utf-8"), name


def test_anchors_are_unique_per_document_and_chunk_count_is_about_120(corpus, sections):
    for name, (_, items) in corpus.items():
        anchors = [s["anchor"] for s in items]
        assert len(anchors) == len(set(anchors)), name
        assert len(items) >= 10, f"{name} has only {len(items)} sections"
    chunks = sum(len(split(s["text"])) for s in sections.values())
    assert 100 <= chunks <= 140, chunks


def test_no_section_is_empty_or_much_longer_than_a_chunk(sections):
    for chunk_id, section in sections.items():
        assert len(section["text"]) >= 120, f"{chunk_id} is too short to answer anything"
        assert len(split(section["text"])) <= 2, f"{chunk_id} needs more than two chunks"


def test_text_is_english_and_free_of_dashes(corpus):
    stop_words = (" the ", " of ", " and ", " to ", " is ", " in ")
    for name in corpus:
        text = (POLICIES / f"{name}.md").read_text(encoding="utf-8")
        assert "\u2014" not in text and "\u2013" not in text and " -- " not in text, name
        lowered = f" {text.lower()} "
        assert sum(lowered.count(word) for word in stop_words) > 60, f"{name} does not look like English"


def test_policy_text_never_tells_the_reader_to_follow_instructions_found_in_data(sections):
    text = sections["refund-policy#instructions-in-data"]["text"].lower()
    assert "data" in text and "instruction" in text


FACTS = {
    "refund-policy#refund-window": [r"30 calendar days", r"captured", r"outside_refund_window", r"refund_window_days"],
    "cross-currency-refunds#fx-at-refund-date": [r"refund date", r"payment date", r"not"],
    "cross-currency-refunds#merchant-fx-markup": [
        r"markup",
        r"3\.0\s?%",
        r"reference rate",
        r"settlement terms",
    ],
    "fx-reference-rates#source": [r"European Central Bank", r"previous business day", r"reference", r"not the rate"],
    "duplicate-charges#detection-rule": [r"same merchant", r"same card", r"same amount", r"5 minutes"],
    "duplicate-charges#remedy": [r"in full", r"5 business days", r"later"],
    "chargeback-handling#response-deadline": [r"one business day before", r"card network deadline", r"loses"],
    "chargeback-handling#evidence-checklist": [r"FRD", r"NRC", r"NAD", r"DUP", r"reason code"],
    "settlement-schedule#payout-timing": [
        r"Monday to Sunday",
        r"2 business days",
        r"weekends",
        r"bank holidays",
    ],
    "fees-and-pricing#processing-fee": [r"2\.9\s?%", r"gross volume"],
    "fees-and-pricing#chargeback-fee": [r"15\.00", r"settlement currency", r"chargeback opened"],
    "escalation-and-review#when-to-escalate": [r"contradicted", r"missing data", r"2 days", r"5,000"],
}


@pytest.mark.parametrize("chunk_id", sorted(FACTS))
def test_each_required_chunk_states_its_facts(sections, chunk_id):
    assert chunk_id in sections, f"missing chunk {chunk_id}"
    text = sections[chunk_id]["text"]
    for pattern in FACTS[chunk_id]:
        assert re.search(pattern, text, re.I), f"{chunk_id} lacks /{pattern}/"


def test_the_holiday_example_of_scenario_s08_is_documented(sections):
    text = " ".join(s["text"] for key, s in sections.items() if key.startswith("settlement-schedule#"))
    assert "B3" in text and "TARGET" in text and "October 12" in text


def test_the_internal_cutoff_of_scenario_s03_is_documented(sections):
    text = sections["chargeback-handling#response-deadline"]["text"]
    assert "Friday" in text or "business day before" in text


# -- the 12 policy questions --------------------------------------------------------------------


@pytest.fixture(scope="module")
def questions() -> list[dict]:
    return [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_twelve_questions_six_easy_and_six_hard(questions):
    assert len(questions) == 12
    assert [q["difficulty"] for q in questions].count("easy") == 6
    assert [q["difficulty"] for q in questions].count("hard") == 6
    assert len({q["id"] for q in questions}) == 12
    assert len({q["question"] for q in questions}) == 12


def test_every_gold_chunk_exists_and_each_question_has_one_or_two(questions, sections):
    for q in questions:
        assert 1 <= len(q["gold_chunk_ids"]) <= 2, q["id"]
        for chunk_id in q["gold_chunk_ids"]:
            assert chunk_id in sections, f"{q['id']} points at {chunk_id}"


def test_the_gold_chunks_cover_the_eight_documents(questions):
    documents = {chunk.split("#")[0] for q in questions for chunk in q["gold_chunk_ids"]}
    assert documents == set(DOCUMENTS)


def test_questions_are_everyday_english_and_the_hard_ones_avoid_the_policy_term(questions):
    for q in questions:
        assert q["question"].endswith("?") and q["language"] == "en"
        assert "\u2014" not in q["question"] and "\u2013" not in q["question"]
    hard = {q["id"]: q for q in questions if q["difficulty"] == "hard"}
    text = " ".join(q["question"].lower() for q in hard.values())
    for term in ("chargeback", "refund", "exchange rate", "duplicate charge"):
        assert term not in text, f"a hard question uses the policy term {term!r}"


def test_the_hard_questions_include_the_ones_the_spec_names(questions):
    wanted = {
        "refund-policy#refund-window": "a month",
        "cross-currency-refunds#fx-at-refund-date": "lower",
        "settlement-schedule#payout-timing": "holiday",
        "chargeback-handling#response-deadline": "bank",
        "duplicate-charges#remedy": "twice",
        "fees-and-pricing#processing-fee": "sale",
    }
    hard = {q["gold_chunk_ids"][0]: q["question"] for q in questions if q["difficulty"] == "hard"}
    for chunk_id, word in wanted.items():
        assert chunk_id in hard and word in hard[chunk_id].lower(), chunk_id
