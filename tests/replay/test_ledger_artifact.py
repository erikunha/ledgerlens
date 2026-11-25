"""The artifact of the ledger of the recorded demo: the movements of the account and the reads of the recording.

What they prove, and why: (a) the artifact of the canonical bundle carries the account that the note of the bundle
names and the kind `customer`, because an artifact without an account is a table without a subject; (b) it carries the
two movements of the account, with the decimal texts `100.00` and `549.31` and never a float of money, because the
browser never calculates money; (c) its reads are the reads of the recording, field by field, because the artifact
publishes what the run read and nothing else; (d) its rows are exactly the two rows of the recorded event, in both
directions, because a row the run did not read is a row the site would publish without a witness; (e) its
`snapshot_sha256` is the digest the manifest of the bundle declares, because that digest is the claim of identity
between the artifact and the recording; (f) an artifact of another recording is refused, with the two digests that
differ; (g) the artifact is written and read back byte for byte, and the check finds the difference when the file on
the disk is not the one the bundle and the ledger produce; (h) the producer writes the frozen file of the scenario and
refuses to write anything when the ledger it rebuilt is not the ledger the recording read; (i) the file the producer
writes is the file the repository commits, byte for byte, so the producer cannot drift away from the frozen artifact
without a test turning red; (j) the reader refuses a file that is not the artifact of the ledger, and the reason names
the file; (k) the bytes of the artifact keep the format of the repository, with sorted keys, two spaces of indentation
and a final line; (l) the note of a manifest that names two accounts is refused, and the reason names both of them;
(m) the identifiers of a read are the identifiers the statement named, and not a list written by hand.

Everything here runs offline, with no key and with no network. The ledger of the account is rebuilt by the test with
the same rule the capture used, and the test proves that the rebuilt file is the file the recording read by comparing
its digest with the one the manifest declares. The canonical bundle is only read, and the file the producer writes goes
under `tmp_path`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from ledgerlens.api.accounts import scoped_ledger
from ledgerlens.replay.bundle import BundleManifest
from ledgerlens.replay.ledger_artifact import (
    ACCOUNT_PATTERN,
    LEDGER_FILE,
    LEDGER_PAGE_SIZE,
    LEDGER_SCHEMA_VERSION,
    LedgerArtifactError,
    account_of_manifest,
    build_ledger_artifact,
    check_ledger_artifact,
    ledger_artifact_bytes,
    ledger_reads_from_events,
    read_ledger_artifact,
    write_ledger_artifact,
)
from ledgerlens.sim.config import SimConfig
from ledgerlens.sim.pipeline import build_ledger

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "data" / "eval" / "replay" / "s01"
PRODUCER = ROOT / "scripts" / "build_ledger_artifact.py"

# The frozen artifact of the ledger, beside the folder of the bundle. It is written by the producer and committed
# with the bundle, and the two have to stay the same bytes.
FROZEN_LEDGER = ROOT / "data" / "eval" / "replay" / "ledger" / "s01.json"

# The digest of the ledger of the account of the recording, the one the manifest of the bundle declares. It is the
# identity of the ledger of the recording, and the artifact publishes it.
SNAPSHOT_SHA256 = "31c8f7fab2f48e1649dbb8480587eb3f511084ed56876df2bec7647a6156945a"

# The two movements of the account, in the shape of the ledger of the branch of the sandbox.
EXPECTED_ROWS = [
    {
        "kind": "transaction",
        "id": "TX-2048",
        "at": "2026-10-15T09:12:00Z",
        "amount": "100.00",
        "currency": "EUR",
        "status": "refunded",
    },
    {
        "kind": "refund",
        "id": "R-0731",
        "at": "2026-10-20T14:05:00Z",
        "amount": "549.31",
        "currency": "BRL",
        "status": "paid",
    },
]

# The one read of the recording: the call of `query_ledger` of the sequence number 19.
EXPECTED_READ = {
    "evidence_id": "sql:1",
    "seq": 19,
    "tool": "query_ledger",
    "sql": (
        "SELECT * FROM (SELECT f.kind, f.applied_rate, f.applied_at, m.id AS merchant_id, "
        "m.name AS merchant_name, m.fx_plan FROM fx_applied AS f JOIN transactions AS t "
        "ON t.id = f.transaction_id JOIN merchants AS m ON m.id = t.merchant_id "
        "WHERE f.transaction_id = 'TX-2048' ORDER BY f.applied_at) LIMIT 50"
    ),
    "columns": ["kind", "applied_rate", "applied_at", "merchant_id", "merchant_name", "fx_plan"],
    "row_count": 2,
    "truncated": False,
    "records": ["TX-2048"],
    "rows": [
        {
            "kind": "charge",
            "applied_rate": "5.6679",
            "applied_at": "2026-10-15T09:12:04Z",
            "merchant_id": "M-17",
            "merchant_name": "Lumen Travel GmbH",
            "fx_plan": "markup",
        },
        {
            "kind": "refund",
            "applied_rate": "5.4931",
            "applied_at": "2026-10-20T14:30:00Z",
            "merchant_id": "M-17",
            "merchant_name": "Lumen Travel GmbH",
            "fx_plan": "markup",
        },
    ],
}


def _load_script(name: str, path: Path):
    """A script of the repository, loaded as a module so the test can drive its command line."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build_ledger_artifact_script = _load_script("build_ledger_artifact", PRODUCER)


def _manifest(bundle: Path = CANONICAL) -> BundleManifest:
    """The manifest of a bundle, as the core reads it."""
    return BundleManifest.from_dict(json.loads((bundle / "manifest.json").read_text(encoding="utf-8")))


def _events(bundle: Path = CANONICAL) -> list[dict]:
    """The recorded events of a bundle, parsed as they were recorded."""
    text = (bundle / "events.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _ledger_event(sql: str, seq: int = 19) -> dict:
    """One event of the tool of the ledger, as the recording wrote it, with the statement it ran.

    Why the test builds one: the recording of the repository names the transaction `TX-2048` and only that one, so a
    projection that answered with a list written by hand would pass every test that reads the canonical bundle.
    """
    return {
        "seq": seq,
        "payload": {
            "name": "query_ledger",
            "outputs": {
                "evidence_ids": ["sql:1"],
                "data": {
                    "sql": sql,
                    "columns": ["kind", "applied_rate", "applied_at"],
                    "row_count": 1,
                    "truncated": False,
                    "rows": [["charge", "5.6679", "2026-10-15T09:12:04Z"]],
                },
            },
        },
    }


def _keys_are_sorted(value: object) -> bool:
    """Whether the keys of every object of a document are in the order the format of the repository asks for.

    Why it walks the whole document: the format is sorted at every level, and a key out of order deep inside the
    artifact breaks the digest the repository pins.
    """
    if isinstance(value, dict):
        keys = list(value)
        if keys != sorted(keys):
            return False
        return all(_keys_are_sorted(item) for item in value.values())
    if isinstance(value, list):
        return all(_keys_are_sorted(item) for item in value)
    return True


@pytest.fixture(scope="module")
def account_ledger(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The ledger of the account of the recording, rebuilt the way the capture built it.

    The digest of the rebuilt file is compared with the one the manifest declares, so a test that runs against a
    ledger the recording did not read fails before it asserts anything else.
    """
    root = tmp_path_factory.mktemp("ledger")
    base = root / "ledger.db"
    build_ledger(SimConfig(source="sample"), base).conn.close()
    account_db = scoped_ledger(base, "C-0412", root / "account.db")
    digest = hashlib.sha256(account_db.read_bytes()).hexdigest()
    assert digest == SNAPSHOT_SHA256, "the rebuilt ledger is not the ledger the recording read"
    return account_db


@pytest.fixture(scope="module")
def artifact(account_ledger: Path) -> dict:
    """The artifact of the canonical bundle, built from the recording and the ledger of its account."""
    return build_ledger_artifact(CANONICAL, account_ledger)


def test_the_artifact_carries_the_account_the_note_of_the_bundle_names(artifact: dict):
    """The account comes from the recording, and the kind comes from the core."""
    manifest = _manifest()

    assert account_of_manifest(manifest) == "C-0412"
    assert ACCOUNT_PATTERN.match("C-0412")
    assert ACCOUNT_PATTERN.match("M-17")
    assert not ACCOUNT_PATTERN.match("S01")

    assert len(artifact["accounts"]) == 1
    account = artifact["accounts"][0]
    assert account["id"] == "C-0412"
    assert account["kind"] == "customer"
    assert account["name"] == "Mariana Albuquerque Costa"


def test_the_artifact_carries_the_two_movements_of_the_account_and_nothing_else(artifact: dict):
    """The movements are the rows of the ledger of the branch, with the money as a decimal text."""
    rows = artifact["accounts"][0]["rows"]

    assert rows == EXPECTED_ROWS
    assert [row["id"] for row in rows] == ["TX-2048", "R-0731"]
    assert [row["amount"] for row in rows] == ["100.00", "549.31"]
    # The amount is a text and never a float: the browser never calculates money.
    assert all(isinstance(row["amount"], str) for row in rows)
    assert [row["kind"] for row in rows] == ["transaction", "refund"]


def test_the_reads_of_the_artifact_are_the_reads_of_the_recording(artifact: dict):
    """The read carries the citation, the sequence number, the statement and the rows, field by field."""
    reads = artifact["accounts"][0]["reads"]

    assert len(reads) == 1
    read = reads[0]
    assert read["evidence_id"] == "sql:1"
    assert read["seq"] == 19
    assert read["tool"] == "query_ledger"
    assert read["sql"] == EXPECTED_READ["sql"]
    assert read["columns"] == EXPECTED_READ["columns"]
    assert read["row_count"] == 2
    assert read["truncated"] is False
    assert read["records"] == ["TX-2048"]
    assert read["rows"] == EXPECTED_READ["rows"]


def test_the_projection_of_the_events_is_the_read_of_the_artifact(artifact: dict):
    """The projection of the recorded events is the read the artifact publishes, and the other way round."""
    reads = ledger_reads_from_events(_events())

    assert reads == artifact["accounts"][0]["reads"]


def test_the_rows_of_the_artifact_are_the_rows_of_the_recorded_event(artifact: dict):
    """No row of the artifact is a row the run did not read, in either direction."""
    recorded = next(
        event
        for event in _events()
        if event["seq"] == 19 and event["payload"].get("name") == "query_ledger"
    )
    recorded_rows = recorded["payload"]["outputs"]["data"]["rows"]
    artifact_rows = artifact["accounts"][0]["reads"][0]["rows"]

    # The recorded rows are positional lists, and the artifact names the values with the columns.
    assert [list(row.values()) for row in artifact_rows] == recorded_rows
    assert artifact_rows == EXPECTED_READ["rows"]
    assert len(artifact_rows) == len(recorded_rows)


def test_the_read_of_a_record_publishes_the_records_the_tool_returned():
    """A run that read the ledger with the record tool publishes those records and not an empty read.

    The recording of a real model read the ledger with the tool that returns one record, and the artifact used to
    publish no read at all for it, so the two catalogs of the site looked different for no reason.
    """
    event = {
        "seq": 17,
        "payload": {
            "name": "get_ledger_record",
            "outputs": {
                "evidence_ids": ["api:1"],
                "data": {
                    "transaction": {"id": "TX-2048", "amount_major": "100.00", "currency": "EUR"},
                    "refunds": [{"id": "R-0731", "payout_amount_major": "549.31", "payout_currency": "BRL"}],
                    "fx_applied": [{"id": "FX-9001", "applied_rate": "5.6679"}],
                    "chargebacks": [],
                },
            },
        },
    }

    reads = ledger_reads_from_events([event])

    assert len(reads) == 1
    read = reads[0]
    assert read["tool"] == "get_ledger_record"
    assert read["evidence_id"] == "api:1"
    assert read["seq"] == 17
    assert read["row_count"] == 3
    assert read["records"] == ["TX-2048", "R-0731", "FX-9001"]
    assert [row["collection"] for row in read["rows"]] == ["transaction", "refunds", "fx_applied"]
    # Every value of a row is a text, because the contract of the browser types every value of a row as a text.
    assert all(isinstance(value, str) for row in read["rows"] for value in row.values())


def test_the_read_of_a_record_carries_no_statement():
    """The tool that reads a record never wrote one, so the read publishes no statement."""
    event = {
        "seq": 17,
        "payload": {
            "name": "get_ledger_record",
            "outputs": {"evidence_ids": ["api:1"], "data": {"transaction": {"id": "TX-2048"}}},
        },
    }

    read = ledger_reads_from_events([event])[0]

    assert read["sql"] == ""
    assert read["columns"][0] == "collection"
    assert read["rows"] == [{"collection": "transaction", "id": "TX-2048"}]


def test_the_identity_of_the_artifact_with_the_recording_holds(artifact: dict):
    """The artifact publishes the digest of the ledger the recording read, and the scenario it belongs to."""
    manifest = _manifest()

    assert artifact["snapshot_sha256"] == manifest.snapshot_sha256 == SNAPSHOT_SHA256
    assert artifact["scenario"] == manifest.scenario == "S01"
    assert artifact["schema_version"] == LEDGER_SCHEMA_VERSION == "1"
    assert artifact["page_size"] == LEDGER_PAGE_SIZE == 50


def test_the_artifact_is_written_and_read_back_byte_for_byte(artifact: dict, tmp_path: Path):
    """The writer puts the same bytes on the disk every time, and the reader gives the artifact back."""
    path = tmp_path / LEDGER_FILE

    written = write_ledger_artifact(path, artifact)

    assert written == path
    assert path.read_bytes() == ledger_artifact_bytes(artifact)
    assert read_ledger_artifact(path) == artifact
    assert ledger_artifact_bytes(artifact) == ledger_artifact_bytes(artifact)


def test_the_artifact_is_the_same_every_time_it_is_built(account_ledger: Path):
    """The artifact is a pure function of the ledger and of the recording."""
    first = build_ledger_artifact(CANONICAL, account_ledger)
    second = build_ledger_artifact(CANONICAL, account_ledger)

    assert ledger_artifact_bytes(first) == ledger_artifact_bytes(second)


def test_the_check_finds_no_difference_in_the_file_the_producer_wrote(artifact: dict, tmp_path: Path):
    """The file the producer writes is the file the bundle and the ledger would produce."""
    path = tmp_path / LEDGER_FILE
    write_ledger_artifact(path, artifact)

    assert check_ledger_artifact(CANONICAL, path) == []


def test_the_check_finds_the_difference_when_the_file_on_the_disk_is_another_one(
    artifact: dict, tmp_path: Path
):
    """A file that is not the one the bundle and the ledger produce is reported, one line per difference."""
    path = tmp_path / LEDGER_FILE
    tampered = dict(artifact)
    tampered["snapshot_sha256"] = "0" * 64
    write_ledger_artifact(path, tampered)

    differences = check_ledger_artifact(CANONICAL, path)

    assert differences
    assert any("snapshot_sha256" in difference for difference in differences)


def test_an_artifact_of_another_recording_is_refused_with_the_two_digests_that_differ(
    artifact: dict, tmp_path: Path
):
    """The refusal names the digest of the artifact and the digest of the recording."""
    path = tmp_path / LEDGER_FILE
    other = dict(artifact)
    other["snapshot_sha256"] = "1" * 64
    write_ledger_artifact(path, other)

    differences = check_ledger_artifact(CANONICAL, path)

    assert differences
    refusal = " ".join(differences)
    assert "1" * 64 in refusal
    assert SNAPSHOT_SHA256 in refusal


def test_a_bundle_whose_note_names_no_account_is_refused(account_ledger: Path, tmp_path: Path):
    """An artifact without an account is a table without a subject, so the bundle is refused."""
    bundle = tmp_path / "s01"
    shutil.copytree(CANONICAL, bundle)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    manifest["note"] = "A recording that names no account at all."
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    assert account_of_manifest(_manifest(bundle)) is None
    with pytest.raises(LedgerArtifactError):
        build_ledger_artifact(bundle, account_ledger)


def test_a_ledger_that_cannot_be_read_is_refused(account_ledger: Path, tmp_path: Path):
    """A ledger the producer cannot open is a refusal with a reason, and never a traceback."""
    with pytest.raises(LedgerArtifactError):
        build_ledger_artifact(CANONICAL, tmp_path / "missing.db")


def test_the_producer_writes_the_frozen_file_of_the_scenario(tmp_path: Path):
    """The producer writes the file of the scenario and nothing else."""
    out = tmp_path / "ledger"

    assert build_ledger_artifact_script.main(["--bundle", str(CANONICAL), "--out", str(out)]) == 0

    written = out / "s01.json"
    assert written.is_file()
    assert sorted(path.name for path in out.iterdir()) == ["s01.json"]
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["snapshot_sha256"] == SNAPSHOT_SHA256
    assert payload["accounts"][0]["id"] == "C-0412"


def test_the_producer_refuses_a_bundle_whose_ledger_is_not_the_one_the_recording_read(tmp_path: Path):
    """A digest that differs is a refusal with a readable reason, and nothing is written."""
    bundle = tmp_path / "s01"
    shutil.copytree(CANONICAL, bundle)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    manifest["snapshot_sha256"] = "2" * 64
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    out = tmp_path / "ledger"

    assert build_ledger_artifact_script.main(["--bundle", str(bundle), "--out", str(out)]) == 1
    assert not out.exists() or not any(out.iterdir())


def test_the_producer_writes_the_committed_file_byte_for_byte(tmp_path: Path):
    """The file the repository commits is the file the producer writes, byte for byte.

    Why it matters: the frozen artifact is written by the producer and never by hand, so the producer can drift away
    from the committed file and the whole gate stays green. This case pins the two together.
    """
    out = tmp_path / "ledger"

    assert build_ledger_artifact_script.main(["--bundle", str(CANONICAL), "--out", str(out)]) == 0

    written = out / "s01.json"
    assert written.is_file()
    assert FROZEN_LEDGER.is_file()
    assert written.read_bytes() == FROZEN_LEDGER.read_bytes()


def test_the_reader_refuses_a_file_that_is_not_a_json_document(tmp_path: Path):
    """A file that is not a JSON document is refused, and the reason names the file."""
    broken = tmp_path / LEDGER_FILE
    broken.write_text("{not json\n", encoding="utf-8")

    with pytest.raises(LedgerArtifactError) as refusal:
        read_ledger_artifact(broken)

    reason = str(refusal.value)
    assert reason.strip()
    assert LEDGER_FILE in reason


def test_the_reader_refuses_a_json_document_that_is_not_an_object(tmp_path: Path):
    """A JSON document of another shape is refused, and the reason names the file."""
    broken = tmp_path / LEDGER_FILE
    broken.write_text(json.dumps(["not", "an", "object"]) + "\n", encoding="utf-8")

    with pytest.raises(LedgerArtifactError) as refusal:
        read_ledger_artifact(broken)

    reason = str(refusal.value)
    assert reason.strip()
    assert LEDGER_FILE in reason


def test_the_bytes_of_the_artifact_keep_the_format_of_the_repository(artifact: dict):
    """The bytes of the artifact are the format of the repository: sorted keys, two spaces and a final line."""
    payload = ledger_artifact_bytes(artifact)

    text = payload.decode("utf-8")
    assert json.loads(text) == artifact
    assert _keys_are_sorted(json.loads(text))

    # The indentation is two spaces: the first level of the document is at two and the second at four.
    indents = {len(line) - len(line.lstrip(" ")) for line in text.splitlines() if line.strip()}
    assert 2 in indents
    assert 4 in indents
    assert all(indent % 2 == 0 for indent in indents)
    assert "\t" not in text

    # The document ends with a final line, and with one final line only.
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_the_note_of_the_manifest_that_names_two_accounts_is_refused():
    """A note that names two accounts is refused, and the reason names both of them."""
    data = json.loads((CANONICAL / "manifest.json").read_text(encoding="utf-8"))
    data["note"] = (
        "Deterministic execution of the scenario S01, accounts C-0412 and M-17, with the scripted model and the "
        "recorded exchange rate."
    )

    with pytest.raises(LedgerArtifactError) as refusal:
        account_of_manifest(BundleManifest.from_dict(data))

    reason = str(refusal.value)
    assert "C-0412" in reason
    assert "M-17" in reason


def test_the_records_of_a_read_are_the_identifiers_the_statement_named():
    """The identifiers of a read come from the statement, and not from a list written by hand.

    Why the statement is a different one: the recording of the repository names the transaction `TX-2048` and only
    that one, so a projection that answered with a list written by hand would pass every other test.
    """
    sql = (
        "SELECT * FROM (SELECT kind, applied_rate, applied_at FROM fx_applied "
        "WHERE transaction_id = 'TX-9999' ORDER BY applied_at) LIMIT 50"
    )

    reads = ledger_reads_from_events([_ledger_event(sql)])

    assert len(reads) == 1
    assert reads[0]["records"] == ["TX-9999"]


# --- the contract of the published artifact ---------------------------------------------------------------


def test_the_values_of_a_row_are_published_as_text(artifact: dict) -> None:
    """Every value of a row of a read is text, because the contract of the browser says so.

    Why the test exists: the published artifact is read by the browser, and the schema of the browser types the
    values of a row as strings. An artifact that carries a number is a file the browser refuses, and the panel of
    the ledger shows the reason of the refusal instead of the ledger.

    Why the value is not lost: the text of a number is the number, and the recording keeps the original form.
    """
    for account in artifact["accounts"]:
        for read in account["reads"]:
            for row in read["rows"]:
                for key, value in row.items():
                    assert isinstance(value, str), (
                        f"the value of {key} of a read of {artifact['scenario']} is a {type(value).__name__} and not "
                        "text: the browser refuses the artifact"
                    )


def test_every_published_artifact_carries_text_in_every_row() -> None:
    """The artifacts that the tree publishes pass the contract of the browser.

    Why the files of the tree and not a fixture: the defect this test closes was in the published files, and a test
    over a fixture would not have found it. The files are the ones the site serves.

    Why every row and not only the rows of the reads: the movements of the account are rows too, and the currency of
    a refund that was never paid out was published as nothing, which the browser refuses like it refuses a number.
    """
    published = sorted((ROOT / "data" / "eval" / "replay" / "ledger").glob("*.json"))
    published += sorted((ROOT / "site" / "replay").glob("*/ledger.json"))
    assert published, "the tree publishes no artifact of the ledger"

    offenders: list[str] = []
    for path in published:
        data = json.loads(path.read_text(encoding="utf-8"))
        for account in data.get("accounts", []):
            for read in account.get("reads", []):
                for row in read.get("rows", []):
                    for key, value in row.items():
                        if not isinstance(value, str):
                            offenders.append(f"{path.name}: a read has {key} that is a {type(value).__name__}")
            for row in account.get("rows", []):
                for key, value in row.items():
                    if not isinstance(value, str):
                        offenders.append(f"{path.name}: a movement has {key} that is a {type(value).__name__}")
                    if key == "currency" and not value:
                        offenders.append(f"{path.name}: a movement has a currency that is empty")
    assert offenders == [], "a published artifact carries a value that is not text: " + "; ".join(offenders)


def test_the_currency_of_a_refund_that_was_never_paid_out_is_the_currency_asked_back() -> None:
    """A movement that never moved money still names the currency of the money that was asked back.

    Why it matters: the currency of the row of the branch layer is the currency of the payout, and a refund that was
    rejected has no payout. The published file asks for a currency that is not empty, and the currency of the refund
    is the currency of the transaction that was refunded.

    Why the artifact of the scenario S08 and not a fixture: the account of the merchant of S08 is the one that holds
    the rejected refund, and the published artifact is the file that the site reads.
    """
    data = json.loads((ROOT / "data" / "eval" / "replay" / "ledger" / "s08.json").read_text(encoding="utf-8"))
    movements = data["accounts"][0]["rows"]
    rejected = [row for row in movements if row["kind"] == "refund" and row["status"] == "rejected"]

    assert rejected, "the account of the merchant holds no rejected refund to prove the rule"
    for row in rejected:
        assert row["currency"], f"the rejected refund {row['id']} has no currency in the published artifact"
        assert row["amount"] == "0.00", f"the rejected refund {row['id']} claims an amount that was not paid"
