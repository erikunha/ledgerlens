"""The CORS of the wired application: the browser of the visitor calls the backend from another origin.

Why it exists: the site of the demo is a static export served on the origin of the site, and the live mode of the
browser calls the backend on the origin of the backend, with the cookie of the session. The browser refuses a call of
another origin unless the server says which origins may call it, and the backend had no such answer at all. This
module is that answer: one middleware, installed by the wired application, and only when the deployment declares the
origins (ADR-040).

What it decides, and why it is written here and not in the wiring: the origins of the browser, the methods, the
headers that travel and the headers that may be read are the policy of the deployment, and the policy lives in one
place with its own tests.

Why the list of the headers that travel holds the two headers of the commit and of the undo of a branch: the browser
sends the headers of a request in the preflight of the call, and it refuses the call when the answer of the preflight
does not name them, so the commit and the undo of the sandbox would never reach the facade (ADR-044).

What it does not decide: a deployment that declares no origin installs nothing, and the backend then answers exactly
as it answered before this module existed.

Why the whole surface of the module is written in the `__all__`: the decision record of the milestone asks every
module that it writes to carry its whole surface in one list, so that a reader who opens this file sees the names
that the policy of the CORS uses, the six constants and the two functions, without opening another file.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ledgerlens.api.byok import (
    BILLING_DISCLOSURE_HEADER,
    KEY_ERASURE_HEADER,
    KEY_STORAGE_HEADER,
    NO_STORE_HEADERS,
)
from ledgerlens.api.sandbox import BRANCH_HASH_HEADER, BRANCH_STATE_HEADER, SCHEMA_VERSION_HEADER

__all__ = [
    "ALLOWED_HEADERS",
    "ALLOWED_METHODS",
    "EXPOSED_HEADERS",
    "IDEMPOTENCY_KEY_HEADER",
    "IF_MATCH_HEADER",
    "PREFLIGHT_MAX_AGE",
    "build_cors_middleware",
    "install_cors",
]

# The methods of the routes of the demo: a GET, a POST and a DELETE, and the preflight that the middleware answers.
ALLOWED_METHODS = ("GET", "POST", "DELETE", "OPTIONS")

# The two headers that the commit and the undo of a branch travel with (ADR-044). The browser sends them in the
# preflight of the call, and a list of the headers that loses one of them makes the browser refuse the preflight of
# the two calls, so the two calls never reach the facade.
IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
IF_MATCH_HEADER = "If-Match"

# The headers the browser may send: the bodies are JSON, the version header is the one the facade publishes, and the
# two headers of the commit and of the undo of a branch are the ones the browser sends in the preflight of the call.
ALLOWED_HEADERS = (
    "Content-Type",
    "Accept",
    SCHEMA_VERSION_HEADER,
    IDEMPOTENCY_KEY_HEADER,
    IF_MATCH_HEADER,
)

# The headers the browser may read: the four of the facade, the two of the branch and the trio of the no store.
# The names come from the modules that own them, so a rename of a constant never leaves a stale name here.
EXPOSED_HEADERS = (
    SCHEMA_VERSION_HEADER,
    KEY_STORAGE_HEADER,
    KEY_ERASURE_HEADER,
    BILLING_DISCLOSURE_HEADER,
    BRANCH_HASH_HEADER,
    BRANCH_STATE_HEADER,
    *NO_STORE_HEADERS,
)

# The life of the preflight in the browser: ten minutes.
PREFLIGHT_MAX_AGE = 600


async def _the_placeholder_application(scope: Any, receive: Any, send: Any) -> None:
    """The application that the middleware is built with when the middleware is only looked at.

    Why the placeholder exists: the middleware of starlette is built around the application it wraps, and the one that
    is built here never answers, because the one that serves is the one that the wiring installs (ADR-040).
    """
    raise RuntimeError("the CORS of the wired application is never built to answer on its own")


def _the_options(*, allowed_origins: Sequence[str]) -> dict[str, Any]:
    """The parameters of the middleware of the CORS, read from the origins of the deployment.

    Why the wildcard is refused here: a wildcard with credentials is illegal in the Fetch specification, and it would
    let any site of the internet drive the API with the session of the visitor (ADR-040).
    """
    origins = [origin.strip() for origin in allowed_origins if origin.strip()]
    if any("*" in origin for origin in origins):
        raise ValueError(
            "the CORS is built with the exact origins of the deployment and never with the wildcard, because a "
            "wildcard with credentials is illegal and would let any site drive the API with the session of the visitor"
        )
    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": list(ALLOWED_METHODS),
        "allow_headers": list(ALLOWED_HEADERS),
        "expose_headers": list(EXPOSED_HEADERS),
        "max_age": PREFLIGHT_MAX_AGE,
    }


def build_cors_middleware(*, allowed_origins: Sequence[str]) -> CORSMiddleware:
    """The middleware of the CORS of the wired application, for the browser of the visitor.

    Why the origins are exact and never a wildcard: a wildcard with credentials is illegal in the Fetch specification,
    and it would let any site of the internet drive the API with the session of the visitor (ADR-040).

    Why the credentials are allowed: the session of the visitor travels in the cookie of the backend origin, and the
    browser only sends it when the answer of the server allows the credentials.
    """
    return CORSMiddleware(app=_the_placeholder_application, **_the_options(allowed_origins=allowed_origins))


def install_cors(app: FastAPI, *, allowed_origins: Sequence[str]) -> None:
    """Installs the CORS on the application, when the deployment declares the origins.

    Why nothing is installed when the list is empty: a deployment that declares no origin answers exactly as it
    answered before, and the middleware is not installed at all (ADR-040).

    Why the middleware adds no route: the list of the routes of the wired application is pinned by ADR-039, and a
    CORS that answered on a path of its own would change the contract of the deployment.
    """
    origins = [origin.strip() for origin in allowed_origins if origin.strip()]
    if not origins:
        return
    app.add_middleware(CORSMiddleware, **_the_options(allowed_origins=origins))
