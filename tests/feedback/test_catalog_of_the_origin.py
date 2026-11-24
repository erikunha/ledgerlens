"""The catalog of the origin: the record names the catalog of its bundle, and the two are not the same thing.

What they guarantee, and why: the record names the catalog of its bundle, and a record of the catalog of a
real model says that the recording is not reproducible byte for byte, under ADR-075, because the two catalogs
are not the same kind of thing: the catalog of the scripted model is reproducible byte for byte and the
catalog of a real model is the recording of one run of one model.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations


def test_the_record_names_the_catalog_of_its_bundle(record) -> None:
    """The catalog of the bundle is a field of the record, and it is one of the two published catalogs."""
    assert record.catalog == "replay"


def test_a_record_of_the_catalog_of_a_real_model_says_the_recording_is_not_reproducible(record_factory) -> None:
    """The catalog of a real model is the recording of one run, and the record says so."""
    real = record_factory(catalog="replay-real")

    assert "not reproducible byte for byte" in real.reproducibility_statement()


def test_a_record_of_the_catalog_of_the_scripted_model_says_the_recording_is_reproducible(record) -> None:
    """The catalog of the scripted model is reproducible byte for byte, and the record says so."""
    assert "reproducible byte for byte" in record.reproducibility_statement()
    assert "not reproducible" not in record.reproducibility_statement()
