"""Exercise the shipped recordings and receipts through their Streamlit controls."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

SITE = Path(__file__).resolve().parents[2] / "site"


@pytest.fixture(autouse=True)
def app_imports(monkeypatch):
    monkeypatch.syspath_prepend(str(SITE.parent / "app"))


def view(name):
    return AppTest.from_string(f"from artifact_views import render_{name}\nrender_{name}()", default_timeout=30).run()


def test_replay_selects_each_recording_and_event():
    page = view("replay")
    for index, catalog in enumerate(("replay", "replay-real")):
        page.radio[0].set_value(page.radio[0].options[index]).run()
        record = json.loads((SITE / catalog / "index.json").read_text())[1]
        page.selectbox[0].select(record["id"]).run()
        assert record["question"] in [item.value for item in page.markdown]
        events = (SITE / catalog / record["bundle_path"] / "events.jsonl").read_text().splitlines()
        page.selectbox[1].select(len(events)).run()
        assert json.loads(page.json[-1].value)["seq"] == len(events)
        assert not page.exception


@pytest.mark.parametrize("name", ["evaluation", "proof", "engineering"])
def test_source_views_allow_selection(name):
    page = view(name)
    assert not page.exception
    assert len(page.selectbox[0].options) > 1
    page.selectbox[0].select_index(1).run()
    assert not page.exception
    assert page.get("download_button")


def test_missing_catalog_reports_error(monkeypatch, tmp_path):
    import artifact_views

    monkeypatch.setattr(artifact_views, "SITE", tmp_path)
    page = view("replay")
    assert page.error
    assert not page.exception
