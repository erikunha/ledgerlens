"""Check that the Project page puts measured results and technical scope in reach."""

from streamlit.testing.v1 import AppTest


def test_project_explains_execution_and_links_published_results():
    page = AppTest.from_string(
        "from app.project_view import render_project\nrender_project()", default_timeout=30
    ).run()

    assert not page.exception
    assert [item.value for item in page.title] == ["Project details"]
    assert [item.label for item in page.tabs] == ["How it works", "Evaluation", "Proofs", "Engineering"]
    overview = page.tabs[0]
    scores = {item.label: item.value for item in overview.metric}
    assert scores == {
        "Agent correctness · tuning set": "81.67%",
        "OpenAI verifier accuracy · held-out set": "43 / 48",
        "Policy questions resolved · development rerun": "14 / 17",
    }
    copy = "\n".join(item.value for item in (*overview.markdown, *overview.caption))
    for detail in (
        "30 cases · 3 repeats",
        "report_online.json",
        "report_heldout.json",
        "policy_journey_review.json",
        "append-only",
        "Deterministic checks",
        "published snapshot",
        "selected model also checks claims",
        "OpenAI may charge",
        "?view=case-simulator",
    ):
        assert detail in copy
    assert page.tabs[1].get("download_button")
    assert page.tabs[2].get("download_button")
    assert page.tabs[3].get("download_button")


def test_project_evaluation_links_the_candidate_and_its_coverage_limit():
    page = AppTest.from_string(
        "from app.project_view import render_project\nrender_project()", default_timeout=30
    ).run()
    evaluation = "\n".join(item.value for item in page.tabs[1].markdown)
    assert "Receipt-backed cutoff verifier" in evaluation
    assert "8 paraphrases" in evaluation
    assert "docs/evaluation.md#receipt-backed-cutoff-verification" in evaluation


def test_evaluation_research_quotes_link_to_the_original_sources():
    page = AppTest.from_string(
        "from app.project_view import render_project\nrender_project()", default_timeout=30
    ).run()
    research = next(item.value for item in page.tabs[1].markdown if "Claim-level precision" in item.value)
    assert research.count("> “") == 4
    for source in ("aclanthology.org", "arxiv.org/abs/2406.12045", "oreilly.com", "cambridge.org"):
        assert source in research
