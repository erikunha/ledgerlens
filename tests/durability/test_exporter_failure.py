"""The failure of the exporter: the run finishes with an answer, and the error of the exporter is recorded locally.

What they guarantee, and why: when the exporter of the forensic export fails, the run finishes with an answer
and the error of the exporter is recorded locally, because the export is a convenience of the run, and a run
that ended with the error of the exporter instead of an answer for the visitor would be a run that failed for
a reason that is not the reason of the visitor.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from ledgerlens.durability.export import export_or_record


def test_the_failure_of_the_exporter_is_recorded_and_the_answer_stands() -> None:
    """The export that fails is a record, and the answer of the run is not the error of the exporter."""
    record: list[str] = []
    # An event whose payload cannot be cleaned is an event that breaks the exporter.
    broken = [{"payload": object()}]

    export = export_or_record(broken, [], record=record)  # type: ignore[arg-type]

    assert export is None
    assert record
    assert "the export of the run failed" in record[0]
