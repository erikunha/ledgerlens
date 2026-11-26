"""Check the portal's HTTP content negotiation against the real Streamlit frontend."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_portal_serves_same_javascript_with_gzip_and_identity():
    # Streamlit owns one process-wide runtime. A child keeps it separate from AppTest.
    check = r"""
from re import search
from starlette.testclient import TestClient
from app.server import portal

with TestClient(portal) as client:
    home = client.get("/")
    home.raise_for_status()
    asset = search(r'src="([^"]+\.js)"', home.text).group(1)
    plain = client.get(asset, headers={"Accept-Encoding": "identity"})
    plain.raise_for_status()
    with client.stream("GET", asset, headers={"Accept-Encoding": "gzip"}) as response:
        response.raise_for_status()
        assert response.headers["content-encoding"] == "gzip"
        assert "accept-encoding" in response.headers["vary"].lower()
        # TestClient decodes HTTP content, so compare the resulting script bytes.
        assert response.read() == plain.content
    assert "content-encoding" not in plain.headers
"""
    subprocess.run([sys.executable, "-c", check], cwd=ROOT, check=True, timeout=30)
