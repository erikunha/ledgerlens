"""Drive private branch changes and credential consent through Streamlit's widget interface."""

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from ledgerlens.api.wiring import build_wired_app


def _button(page, label):
    return next(button for button in page.button if button.label == label)


def _page(view, client):
    page = AppTest.from_string(f"from app.interactive_views import {view}\n{view}()", default_timeout=30)
    page.session_state["_visitor_http"] = client
    return page.run()


def test_private_branch_preview_commit_undo_reset(tmp_path):
    with TestClient(build_wired_app(runtime_dir=tmp_path)) as client:
        page = _page("render_sandbox", client)
        _button(page, "Open private branch").click().run()
        _button(page, "Preview change").click().run()
        _button(page, "Commit change").click().run()
        assert "Revision 1" in page.caption[0].value
        _button(page, "Undo last change").click().run()
        assert "Revision 0" in page.caption[0].value
        _button(page, "Preview change").click().run()
        _button(page, "Commit change").click().run()
        _button(page, "Reset to published case").click().run()
        assert "Revision 0" in page.caption[0].value
        _button(page, "End session").click().run()
        assert not page.exception
        assert "branch" not in page.session_state


def test_offline_live_view_accepts_no_key(tmp_path):
    with TestClient(build_wired_app(runtime_dir=tmp_path)) as client:
        page = _page("render_live", client)
        assert not page.exception
        assert "offline" in page.info[0].value.lower()
        assert not page.text_input


def test_live_consent_budget_cancel_and_forget(monkeypatch):
    import json

    import httpx

    from app import interactive_views

    monkeypatch.setattr(interactive_views, "offline", lambda: False)
    calls = []
    cancelled = False

    def backend(request):
        nonlocal cancelled
        path = request.url.path
        payload = json.loads(request.content) if request.content else None
        calls.append((path, payload))
        if path.endswith("/cancel"):
            cancelled = True
            body = {}
        elif path.endswith("/run_demo"):
            body = {"status": "cancelled" if cancelled else "running"}
        else:
            body = {
                "/v1/sessions": {"id": "visitor"},
                "/v1/models": {
                    "models": [
                        {
                            "profile_id": "demo",
                            "display_name": "Test provider",
                            "provider": "openai",
                            "enabled_in_public_demo": True,
                        }
                    ]
                },
                "/v1/models/demo": {"price_note": "Fixture pricing."},
                "/v1/credentials": {"provider": "openai", "handle": "opaque", "expires_at": "tomorrow"},
                "/v1/sandboxes": {"id": "branch", "revision": 2},
                "/v1/live-runs": {"run_id": "run_demo"},
                "/v1/live-runs/run_demo/cost": {"model_calls": 0},
                "/v1/credentials/forget": {"forgotten": True},
            }[path]
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(backend), base_url="https://demo.test") as client:
        page = _page("render_live", client)
        key_input = next(field for field in page.text_input if field.label == "Provider API key")
        key_input.set_value("test-only")
        _button(page, "Connect key").click().run()
        assert not any(path == "/v1/credentials" for path, _ in calls)
        next(field for field in page.text_input if field.label == "Provider API key").set_value("test-only")
        page.checkbox[0].check()
        _button(page, "Connect key").click().run()
        assert not any(field.label == "Provider API key" for field in page.text_input)
        next(field for field in page.number_input if field.label == "Model calls").set_value(3)
        _button(page, "Start live run").click().run()
        request = next(body for path, body in calls if path == "/v1/live-runs")
        assert request["limits"]["max_model_calls"] == 3
        assert request["expected_revision"] == 2
        assert request["credential_handle"] == "opaque"
        assert "test-only" not in str(request)
        _button(page, "Cancel run").click().run()
        _button(page, "Forget key").click().run()
        assert not page.exception
        assert "credential" not in page.session_state


@pytest.mark.parametrize("origin", ["http://remote.test", "http://api:8010"])
def test_remote_plaintext_api_cannot_receive_a_key(monkeypatch, origin):
    import httpx

    from app import interactive_views

    monkeypatch.setattr(interactive_views, "offline", lambda: False)

    def no_requests(request):
        raise AssertionError(f"Unexpected request to {request.url.path}")

    with httpx.Client(transport=httpx.MockTransport(no_requests), base_url=origin) as client:
        page = _page("render_live", client)
        assert not page.exception
        assert "HTTPS" in page.error[0].value
        assert not page.text_input


def test_visitors_fork_separate_branches(tmp_path):
    api = build_wired_app(runtime_dir=tmp_path)
    with TestClient(api) as first, TestClient(api) as second:
        pages = [_page("render_sandbox", client) for client in (first, second)]
        for page in pages:
            _button(page, "Open private branch").click().run()
            assert not page.exception
        first_branch = pages[0].session_state.branch[1]
        assert first_branch != pages[1].session_state.branch[1]
        assert second.get(f"/v1/sandboxes/{first_branch}").status_code == 404
