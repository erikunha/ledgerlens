"""The rollback of the laboratory: with the flag off, no route of the laboratory answers, and the fixtures stay data.

What they guarantee, and why: (a) the application of `ledgerlens/api/` built with the flag off has no route of
the laboratory, because a feature that stays after the flag is off is a feature that was never behind the flag;
(b) the fixtures of `data/adversarial/fixtures/` stay readable as data, because the rollback of the laboratory
is the rollback of a route and never the deletion of the attacks, which are data of the repository.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

from ledgerlens.api.byok import create_app

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "adversarial" / "fixtures"


def test_no_route_of_the_laboratory_answers_with_the_flag_off() -> None:
    """The application has no route of the laboratory: the laboratory is run by the tests and by the script."""
    app = create_app()
    routes = [getattr(route, "path", "") for route in app.routes]

    assert not any("adversarial" in path or "/lab" in path for path in routes)


def test_the_fixtures_stay_readable_as_data() -> None:
    """The rollback of the laboratory is the rollback of a route, never the deletion of the attacks."""
    fixtures = sorted(FIXTURES.glob("*.json"))
    assert fixtures
    for path in fixtures:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
