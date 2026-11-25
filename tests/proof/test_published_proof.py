"""The published proof: the export under `site/proof/` matches the bundle, and a drift fails the check.

What they guarantee, and why: the export under `site/proof/` matches the bundle it was built from, and the
check fails when a published proof does not match, because a published proof that drifted from its bundle is
a proof that asks the reader to trust the name and not the bytes.

Everything here runs offline, with no key and with no network.
"""

from __future__ import annotations

from pathlib import Path

from ledgerlens.proof.export import build_proof_export, check_proof_export, write_proof_export

ROOT = Path(__file__).resolve().parents[2]
PROOF_DIR = ROOT / "site" / "proof"


def test_the_published_proof_matches_the_bundle_it_was_built_from() -> None:
    """The export of the proofs on the disk is the export the bundles produce."""
    files = build_proof_export(ROOT)

    assert check_proof_export(files, PROOF_DIR) == []


def test_the_check_fails_when_a_published_proof_does_not_match(root, tmp_path) -> None:
    """A proof that drifted from its bundle is a proof the gate refuses."""
    files = build_proof_export(root)
    out_dir = tmp_path / "proof"
    write_proof_export(files, out_dir)
    name = next(name for name in files if name != "index.json")
    (out_dir / name).write_text('{"drifted": true}\n', encoding="utf-8")

    problems = check_proof_export(files, out_dir)

    assert any(name in problem and "does not match" in problem for problem in problems)


def test_the_check_fails_when_a_published_proof_has_no_bundle(root, tmp_path) -> None:
    """A proof without a bundle is a proof nobody can check, and the gate refuses it."""
    files = build_proof_export(root)
    out_dir = tmp_path / "proof"
    write_proof_export(files, out_dir)
    (out_dir / ("f" * 64 + ".json")).write_text("{}\n", encoding="utf-8")

    problems = check_proof_export(files, out_dir)

    assert any("has no bundle" in problem for problem in problems)
