"""Shared test setup: every test runs offline, with no keys and a private runtime directory."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"

# Variables that would send a test online or make it depend on a developer's machine.
_CLEARED = (
    "OPENAI_API_KEY",
    "LANGSMITH_API_KEY",
    "LANGCHAIN_API_KEY",
    "LANGSMITH_PROJECT",
    "LEDGERLENS_MODEL",
    "LEDGERLENS_EMBEDDINGS",
    "LEDGERLENS_LEDGER_API_URL",
)


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Force offline mode, drop credentials, and point the runtime directory at a temp path.

    `LEDGERLENS_ENV_FILE` points at a file that does not exist, so no test reads a real `.env`.
    Returns the runtime directory.
    """
    for name in _CLEARED:
        monkeypatch.delenv(name, raising=False)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.setenv("LEDGERLENS_OFFLINE", "1")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LEDGERLENS_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LEDGERLENS_ENV_FILE", str(tmp_path / "no-such.env"))
    return runtime_dir


@pytest.fixture(autouse=True)
def sample_directory_stays_untouched() -> Iterator[None]:
    """Fails the test that leaves a new file in `data/sample/`, which only keeps the committed sample."""
    before = {p.name for p in SAMPLE_DIR.iterdir()} if SAMPLE_DIR.is_dir() else set()
    yield
    after = {p.name for p in SAMPLE_DIR.iterdir()} if SAMPLE_DIR.is_dir() else set()
    assert after <= before, f"the test left files in data/sample/: {sorted(after - before)}"


class LocalHttpServer:
    """A throwaway HTTP server on 127.0.0.1 that serves canned responses and records every request.

    Tests that exercise download or recording code point it at `base_url`, so nothing leaves the
    machine. A response is registered for a path (query string ignored) or for `path?query`
    (exact match wins).
    """

    def __init__(self) -> None:
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        self.routes: dict[str, tuple[int, bytes, dict[str, str]]] = {}
        self.requests: list[str] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 (stdlib name)
                outer.requests.append(self.path)
                path = self.path.split("?", 1)[0]
                status, body, headers = (
                    outer.routes.get(self.path)
                    or outer.routes.get(path)
                    or (
                        404,
                        b'{"message":"not found"}',
                        {},
                    )
                )
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def add(self, path: str, body: bytes | str, status: int = 200, headers: dict[str, str] | None = None) -> None:
        data = body.encode() if isinstance(body, str) else body
        self.routes[path] = (status, data, headers or {})

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def local_http():
    server = LocalHttpServer()
    try:
        yield server
    finally:
        server.close()
