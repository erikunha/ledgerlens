"""The notice of the sources: the conditions of the ECB are quoted, and the lock says the same.

What it guarantees, and why: the NOTICE quotes the three conditions of the European Central Bank for the
use of the reference rates, it says that the cross rates of the committed recordings are computed through
the euro by this project, and the lock of the sources says the same, because a license string that the ECB
does not publish is a license the repository invented (gap 12 of the audit).

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICE = ROOT / "NOTICE"
LOCK = ROOT / "data" / "sources.lock.json"

# The three conditions of the ECB for the use of the reference rates, as the ECB publishes them.
CONDITIONS = (
    "information purposes only",
    "the source must be acknowledged as the European Central Bank",
    "the ECB accepts no responsibility for any use of the rates",
)


def test_the_notice_quotes_the_three_conditions_of_the_ecb() -> None:
    """The NOTICE quotes the three conditions of the ECB for the use of the reference rates."""
    notice = NOTICE.read_text(encoding="utf-8")

    for condition in CONDITIONS:
        assert condition in notice, f"the NOTICE does not quote the condition: {condition}"


def test_the_notice_says_the_cross_rates_are_computed_through_the_euro_by_this_project() -> None:
    """The NOTICE says the cross rates of the recordings are computed through the euro by this project."""
    notice = NOTICE.read_text(encoding="utf-8")

    assert "computed through the euro by this project" in notice


def test_the_lock_says_what_the_notice_says_and_no_license_the_ecb_does_not_publish() -> None:
    """The lock of the sources quotes the conditions of the ECB, and no invented license string."""
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    entry = lock["sources"]["ecb_eurofxref_hist"]

    for condition in CONDITIONS:
        assert condition in entry["license"], f"the lock does not quote the condition: {condition}"
    assert "computed through the euro by this project" in entry["cross_rates_note"]
    assert "CC BY" not in entry["license"], "the ECB does not publish the reference rates under CC BY"
