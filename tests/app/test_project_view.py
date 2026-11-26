"""Check that the Project page puts measured results and technical scope in reach."""

from streamlit.testing.v1 import AppTest


def test_project_explains_execution_and_links_published_results():
    page = AppTest.from_string(
        "from app.project_view import render_project\nrender_project()", default_timeout=30
    ).run()

    assert not page.exception
    assert "Project" in [item.value for item in page.title]
    assert [item.label for item in page.tabs] == ["How it works", "Evaluation", "Proofs", "Engineering"]
    overview = page.tabs[0]
    scores = {item.label: item.value for item in overview.metric}
    assert scores == {
        "Agent correctness · tuning set": "81.67%",
        "Verifier accuracy · held-out set": "24 / 48",
        "Policy questions resolved · development": "7 / 17",
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
        "Learned verification",
        "OpenAI may charge",
        "?view=Sandbox",
    ):
        assert detail in copy
    assert page.tabs[1].get("download_button")
    assert page.tabs[2].get("download_button")
    assert page.tabs[3].get("download_button")
