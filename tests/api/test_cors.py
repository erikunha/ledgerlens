"""The CORS of the wired application: the browser of the visitor calls the backend from another origin.

Why these tests exist: the site of the demo is a static export served on the origin of the site, and the live mode
calls the backend on the origin of the backend, with the cookie of the session. The browser refuses a call of another
origin unless the server says which origins may call it, and the backend had no such answer at all. These tests pin
that answer, and they pin the two refusals that matter: an origin that is not in the list gets no answer of the
origin, and a wildcard is never built (ADR-040).

They pin one list more, the list of the headers the browser may send, because the commit and the undo of a branch of
the sandbox travel with the headers `Idempotency-Key` and `If-Match` (ADR-044). The browser sends both of them in
the preflight of the call, and a list of the headers that loses one of them makes the browser refuse the preflight of
the two calls, so the two calls never reach the facade.

Everything offline, with no key and no network: the tests call the wired application in the process, and no test of
this file opens a socket. The setting is always given to the application explicitly, and the environment of the
machine is never changed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from ledgerlens.api.byok import (  # noqa: E402
    BILLING_DISCLOSURE_HEADER,
    KEY_ERASURE_HEADER,
    KEY_STORAGE_HEADER,
    NO_STORE_HEADERS,
)
from ledgerlens.api.cors import build_cors_middleware, install_cors  # noqa: E402
from ledgerlens.api.sandbox import (  # noqa: E402
    BRANCH_HASH_HEADER,
    BRANCH_STATE_HEADER,
    SCHEMA_VERSION_HEADER,
)
from ledgerlens.api.wiring import build_wired_app  # noqa: E402
from ledgerlens.config import ConfigError, Settings, get_settings  # noqa: E402
from ledgerlens.sandbox.session import SessionIssuer  # noqa: E402
from ledgerlens.sandbox.store import FileBranchStore  # noqa: E402

# The origin of the site of the demo, the one the deployment of the local run declares.
ORIGIN = "http://localhost:3000"
# The origin of a site that the deployment did not declare.
OTHER_ORIGIN = "http://not-declared.example"

# The two headers of the commit and of the undo of a branch (ADR-044). The names are written here and not read from
# the module of the CORS, so that a rename in the module breaks this file loudly instead of hiding behind it.
IDEMPOTENCY_HEADER = "Idempotency-Key"
IF_MATCH_HEADER = "If-Match"

# The request headers that the browser sends without a preflight of their own, the ones of the Fetch specification.
# The middleware of the CORS always allows them, and the guard below leaves them out of its comparison.
SAFELISTED_REQUEST_HEADERS = frozenset({"accept", "accept-language", "content-language", "content-type"})


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    """The wired application of a deployment that declares the origin of the site.

    Why the runtime folder is one of the test: the application writes the material of the demo in it, and the
    repository is never written to by a test.
    """
    return build_wired_app(
        settings=Settings(cors_origins=(ORIGIN,)),
        issuer=SessionIssuer(tmp_path / "session.key"),
        store=FileBranchStore(tmp_path / "store"),
        runtime_dir=tmp_path / "runtime",
    )


@pytest.fixture
def app_without_cors(tmp_path: Path) -> FastAPI:
    """The wired application of a deployment that declares no origin at all."""
    return build_wired_app(
        settings=Settings(),
        issuer=SessionIssuer(tmp_path / "session.key"),
        store=FileBranchStore(tmp_path / "store"),
        runtime_dir=tmp_path / "runtime",
    )


# --- the answer of the browser -----------------------------------------------------------------------


def test_the_declared_origin_is_answered_with_the_origin_and_the_credentials(app: FastAPI) -> None:
    """ADR-040: the origin of the setting is answered with itself, and the credentials are allowed.

    Why the credentials matter: the session of the visitor travels in the cookie of the backend origin, and the
    browser only sends it when the answer of the server allows the credentials.
    """
    with TestClient(app) as client:
        response = client.post("/v1/sessions", headers={"Origin": ORIGIN})

    assert response.status_code == 201, response.text
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


def test_an_origin_that_is_not_declared_is_answered_without_the_header_of_the_origin(app: FastAPI) -> None:
    """ADR-040: only the declared origins may call the backend with the cookie of the visitor."""
    with TestClient(app) as client:
        response = client.post("/v1/sessions", headers={"Origin": OTHER_ORIGIN})

    assert response.status_code == 201, response.text
    assert "access-control-allow-origin" not in response.headers


def test_the_exposed_headers_carry_the_disclosures_the_version_and_the_no_store(app: FastAPI) -> None:
    """ADR-040: the browser may only read the headers the server exposes.

    Why the disclosures are in the list: the three disclosures live in headers, and the frontend renders the words of
    the server, so it needs to read them (FR-003, FR-008, FR-021).
    """
    with TestClient(app) as client:
        response = client.post("/v1/sessions", headers={"Origin": ORIGIN})

    exposed = {name.strip().lower() for name in response.headers["access-control-expose-headers"].split(",")}
    for header in (
        SCHEMA_VERSION_HEADER,
        KEY_STORAGE_HEADER,
        KEY_ERASURE_HEADER,
        BILLING_DISCLOSURE_HEADER,
        BRANCH_HASH_HEADER,
        BRANCH_STATE_HEADER,
        *NO_STORE_HEADERS,
    ):
        assert header.lower() in exposed, header


def test_the_preflight_of_a_post_with_a_json_body_is_answered(app: FastAPI) -> None:
    """ADR-040: the preflight of the browser is answered by the middleware, before the route is reached."""
    with TestClient(app) as client:
        response = client.options(
            "/v1/sessions",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    methods = {method.strip() for method in response.headers["access-control-allow-methods"].split(",")}
    assert {"GET", "POST", "DELETE"} <= methods
    # The preflight is cached for ten minutes, so the browser does not ask again on every call.
    assert response.headers["access-control-max-age"] == "600"


# --- the headers the browser may send ---------------------------------------------------------------------


def test_the_list_of_the_headers_the_browser_may_send_loses_none_of_them() -> None:
    """ADR-044: the list of the headers the browser may send is exact, and it holds the two of the commit.

    Why the list is exact and not a subset: the commit and the undo of a branch travel with the headers
    `Idempotency-Key` and `If-Match`, and the browser sends both of them in the preflight of the call. A list that
    loses one of them makes the browser refuse the preflight of the two calls, and the two calls never reach the
    facade. A subset would let the list lose one of the two headers without a single case of the repository
    noticing, so this case compares the whole list, outside of the headers the browser sends anyway.
    """
    middleware = build_cors_middleware(allowed_origins=(ORIGIN,))

    allowed = {header.strip().lower() for header in middleware.allow_headers}
    named_by_the_deployment = allowed - SAFELISTED_REQUEST_HEADERS

    assert named_by_the_deployment == {
        SCHEMA_VERSION_HEADER.lower(),
        IDEMPOTENCY_HEADER.lower(),
        IF_MATCH_HEADER.lower(),
    }


def test_the_preflight_of_the_commit_is_answered_with_the_two_headers_of_the_commit(app: FastAPI) -> None:
    """ADR-044: the preflight of the commit and of the undo is answered, with the two headers they carry.

    Why the preflight is the thing to answer: the browser sends the headers of the request in the preflight and not
    in the call itself, and it refuses the call when the answer of the preflight does not name them. The middleware
    answers the preflight with `400` and with the reason when one of the headers is missing from the list, so this
    case fails the moment the list loses one of the two.
    """
    requested = ", ".join(("content-type", IDEMPOTENCY_HEADER.lower(), IF_MATCH_HEADER.lower()))
    with TestClient(app) as client:
        response = client.options(
            "/v1/sandboxes/sb_000000000000000000000000/mutations",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": requested,
            },
        )

    assert response.status_code == 200, response.text
    allowed = {name.strip().lower() for name in response.headers["access-control-allow-headers"].split(",")}
    assert IDEMPOTENCY_HEADER.lower() in allowed
    assert IF_MATCH_HEADER.lower() in allowed


# --- the refusals --------------------------------------------------------------------------------------


def test_a_wildcard_is_refused_by_the_setting() -> None:
    """ADR-040: a wildcard with credentials is illegal, and the setting says so out loud."""
    with pytest.raises(ConfigError):
        get_settings(env={"LEDGERLENS_CORS_ORIGINS": "*"})

    with pytest.raises(ConfigError):
        get_settings(env={"LEDGERLENS_CORS_ORIGINS": "http://localhost:3000, *"})


def test_a_wildcard_is_refused_by_the_middleware() -> None:
    """ADR-040: the middleware is never built with a wildcard, whoever asks for it.

    Why the middleware refuses it too: the setting is one of the ways to reach the middleware, and a deployment that
    reached it another way must not end up with a wildcard and the credentials at the same time.
    """
    with pytest.raises(ValueError):
        build_cors_middleware(allowed_origins=("*",))

    with pytest.raises(ValueError):
        build_cors_middleware(allowed_origins=("http://localhost:3000", "*"))


# --- the setting ---------------------------------------------------------------------------------------


def test_the_setting_is_empty_by_default() -> None:
    """ADR-040: the default is empty, and an empty list installs nothing."""
    assert Settings().cors_origins == ()
    assert get_settings(env={"LEDGERLENS_CORS_ORIGINS": ""}).cors_origins == ()


def test_the_setting_reads_the_origins_of_the_environment() -> None:
    """ADR-040: the setting is a comma separated list of exact origins."""
    settings = get_settings(env={"LEDGERLENS_CORS_ORIGINS": "http://localhost:3000, https://demo.example"})

    assert settings.cors_origins == ("http://localhost:3000", "https://demo.example")


# --- the installation ----------------------------------------------------------------------------------


def test_the_default_setting_installs_no_middleware_and_answers_as_it_did(app_without_cors: FastAPI) -> None:
    """ADR-040: a deployment that declares no origin answers exactly as it answered before the CORS existed."""
    assert app_without_cors.user_middleware == []

    with TestClient(app_without_cors) as client:
        response = client.post("/v1/sessions", headers={"Origin": ORIGIN})

    assert response.status_code == 201, response.text
    assert "access-control-allow-origin" not in response.headers


def test_the_middleware_is_built_with_the_parameters_of_the_decision() -> None:
    """ADR-040: the parameters of the middleware are exact."""
    middleware = build_cors_middleware(allowed_origins=(ORIGIN,))

    assert list(middleware.allow_origins) == [ORIGIN]
    assert middleware.allow_credentials is True
    assert set(middleware.allow_methods) == {"GET", "POST", "DELETE", "OPTIONS"}
    assert {
        "content-type",
        "accept",
        SCHEMA_VERSION_HEADER.lower(),
        IDEMPOTENCY_HEADER.lower(),
        IF_MATCH_HEADER.lower(),
    } <= set(middleware.allow_headers)


def test_the_installation_of_an_empty_list_of_origins_adds_nothing(tmp_path: Path) -> None:
    """ADR-040: an empty list installs nothing, so the behaviour of the repository does not change."""
    application = FastAPI()

    install_cors(application, allowed_origins=())

    assert application.user_middleware == []
