---
description: "Task list for source-grounded document extraction"
---

# Tasks: Source-grounded document extraction

**Input**: Design documents from `specs/019-r18-source-grounded-document-extraction/`

**Prerequisites**: plan.md (required), spec.md (required), the design package of the release
(`docs/design/advanced-specs/R18-02-source-grounded-document-extraction.md`), ADR-005, ADR-013, ADR-054, ADR-061 and
ADR-074 of `docs/decisions/`, ADR-P007 and ADR-P009 of `docs/design/adrs/`, and the code the pipeline builds on:
`ledgerlens/schemas.py` for the `Evidence`, `ledgerlens/tools/envelope.py` for the envelope and the scheme of the
ids, `ledgerlens/tools/ledger_api.py` for the read-only surface of the ledger, `ledgerlens/verify/escalation.py` for
the decision of the code and `ledgerlens/offline.py` for the scripted model

**Tests**: Every task that changes the behaviour of the repository ships its test before its code, and the gate of
the Python side is green before the commit. The tests of the pipeline live in `tests/documents/` and run offline
with `LEDGERLENS_OFFLINE=1`. Every test of this list is written to fail before the code of its task and to pass
after it. The pipeline reads only `data/fixtures/documents/`, so no test of this list opens a document of a
visitor, and no test writes a document to the disk of the repository.

**Organization**: Tasks are grouped by the layer of the pipeline that they build, from the decision that starts it
to the tool that exposes it. The ids of this list start at T501 and are unique in the repository; the ids of the
specifications `001` to `006` end at T172, and the blocks of the lists that run in parallel are kept apart, so that
two people can work on this list and on another list at the same time. The tasks marked `[P]` touch disjoint files
and can run in parallel with each other.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[DELIVERED]**: the task is done, and the sentence names what it delivered
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `ledgerlens/`, `tests/`, `scripts/`, `data/`, `docs/` at repository root
- Paths shown below assume single project

## The decision that starts the milestone

**Purpose**: a document is a source of a claim, it never corrects the ledger, and the pipeline reads only the
fixtures of the repository.

- [x] T501 Write the record of the decision in
  `docs/decisions/ADR-080-a-document-is-a-source-of-evidence-and-it-never-corrects-the-ledger.md`, with the number
  the index shows as free at the time of writing, saying that the extraction produces `Evidence` of the repository
  with a source of `doc`, that the ledger keeps the authority of what happened, that a disagreement between a
  document and the ledger is a decision that a person has to look at, that the pipeline reads only the fixtures of
  `data/fixtures/documents/` and refuses every other path before opening it, and that the vision path never
  publishes a value the deterministic parser did not confirm. Run `uv run python scripts/build_docs_index.py` to
  regenerate `docs/decisions/README.md` and commit the result. The record does not change any accepted record

## The fixtures of the documents

**Purpose**: the pipeline has documents to read that belong to the repository and to nobody else.

  - **DELIVERED**: the record is `docs/decisions/ADR-094-a-document-is-a-source-of-evidence-and-it-never-corrects-the-ledger.md`: the extraction produces `Evidence` of the repository with a source of `doc`, the ledger keeps the authority of what happened, a disagreement is a decision that a person has to look at, the pipeline reads only the fixtures and the vision path never publishes a value the parser did not confirm. The index was regenerated.
- [x] T502 Write the synthetic fixtures under `data/fixtures/documents/` with their manifest
  `data/fixtures/documents/manifest.json`: a Brazilian receipt that says `1.000,00 BRL` while the ledger of the
  fixture says `100.00`, an American receipt that says `1,000.00 USD`, a receipt with a blurred last digit, a
  receipt with an amount in two currencies, a receipt with too many decimal places and a document in a language the
  extractor does not read. Every fixture carries its digest and its license, and the docstring of the manifest says
  that the fixtures are synthetic and that the repository keeps no document of a visitor
  - **DELIVERED**: the fixtures are in `data/fixtures/documents/` with the manifest `manifest.json`: the Brazilian receipt, the American receipt, the blurred receipt, the receipt in two currencies, the receipt with too many decimals and the document in a language the extractor does not read, each with its digest and its license, and the manifest says they are synthetic.
- [x] T503 Write `tests/documents/test_license.py` first, expecting that every fixture of the manifest carries a
  license and that the extraction refuses a fixture whose license is unknown. Then write
  `ledgerlens/documents/license.py` with the check of the license, with a docstring that says why a document
  without a declared license is not read

## The detection and the refusals

**Purpose**: a file that must not be opened is refused before it is opened.

  - **DELIVERED**: the test is in `tests/documents/test_license.py` and the module is in `ledgerlens/documents/license.py`: every fixture of the manifest carries a license and the extraction refuses a fixture whose license is unknown.
- [x] T504 Write `tests/documents/test_only_fixtures.py` first, expecting that a path outside
  `data/fixtures/documents/` is refused with the reason and that the file was not opened, with a spy over the
  open. Then write `ledgerlens/documents/detect.py` with the check of the path, with a docstring that says that the
  refusal happens before the file is opened and not after
  - **DELIVERED**: the test is in `tests/documents/test_only_fixtures.py` and the module is in `ledgerlens/documents/detect.py`: a path outside `data/fixtures/documents/` is refused with the reason and the file was not opened, with a spy over the open.
- [x] T505 Write `tests/documents/test_file_security.py` first, expecting that a file with an executable payload, a
  file whose compressed form expands past the limit, a file protected by a password and a file that is bigger than
  the limit are each refused with a readable reason and that the temporary directory is empty after each refusal.
  Then write `ledgerlens/documents/security.py` with the four checks and the limits, with a docstring that says
  which reader is attacked by each check and why the check happens before the conversion

## The conversion

**Purpose**: the text of a document is read without a shell and without a temporary file that survives.

  - **DELIVERED**: the test is in `tests/documents/test_file_security.py` and the module is in `ledgerlens/documents/security.py`: the executable payload, the compressed bomb, the password and the size are each refused with a readable reason, and the temporary directory is empty after each refusal.
- [x] T506 Write `ledgerlens/documents/convert.py` with the reader of the text layer of a PDF and the decoder of an
  image, refusing a file that needs a converter that is not installed with a readable reason, and with a docstring
  that says that the conversion never calls a shell and never leaves a temporary file behind. Add
  `pypdf` and `Pillow` to the dependencies of `pyproject.toml` as optional extras, so that the offline gate does
  not need them, and write `tests/documents/test_convert.py` that expects the text layer of the fixture and the
  refusal when the extra is absent

## The fields and the money

**Purpose**: every field says where it was read, and every amount is a `Decimal` with the locale of the document.

  - **DELIVERED**: the module is in `ledgerlens/documents/convert.py` and `pypdf` and `Pillow` are optional extras of `pyproject.toml`. The test is in `tests/documents/test_convert.py`: the text layer of the fixture and the refusal when the extra is absent.
- [x] T507 Write `tests/documents/test_money_parsing.py` first, expecting that the amount of the Brazilian fixture
  is one thousand and not one, that the amount of the American fixture is one thousand and that both are
  `Decimal`. Then write `ledgerlens/documents/money.py` with the locale of the document and the parse of the
  amount, with a docstring that says that the parse never uses a float and that the rounding of a document is not a
  rounding of the ledger
  - **DELIVERED**: the test is in `tests/documents/test_money_parsing.py` and the module is in `ledgerlens/documents/money.py`: the amount of the Brazilian fixture is one thousand and not one, the amount of the American fixture is one thousand, and both are `Decimal`.
- [x] T508 Write `tests/documents/test_extraction_output.py` first, expecting that every field of the result
  carries the digest of the document, the page, the position, the name, the value, the kind of confidence, the
  version of the extractor and the license, and expecting the refusal when the version is missing. Then write
  `ledgerlens/documents/fields.py` with the fields of the repository and their positions, with a docstring that says
  what a field is and why it carries the page and the position
  - **DELIVERED**: the test is in `tests/documents/test_extraction_output.py` and the module is in `ledgerlens/documents/fields.py`: every field carries the digest, the page, the position, the name, the value, the kind of confidence, the version and the license, and the extraction is refused when the version is missing.
- [x] T509 Write `tests/documents/test_uncertainty.py` first, expecting that the blurred field carries no value,
  that its kind of confidence names the doubt and that the case asks the person. Then extend
  `ledgerlens/documents/fields.py` with the kinds of confidence, with a docstring that says that a value that was
  not read with certainty is not a value

## The evidence of the document

**Purpose**: the verifier consumes the extraction without learning a second kind of evidence.

  - **DELIVERED**: the test is in `tests/documents/test_uncertainty.py` and the kinds of confidence are in `ledgerlens/documents/fields.py`: the blurred field carries no value, its kind of confidence names the doubt and the case asks the person.
- [x] T510 Write `tests/documents/test_evidence_kind.py` first, expecting that the id of a document evidence
  matches the scheme of `ledgerlens/tools/envelope.py` and that the `EvidenceSource` and the `ToolName` literals of
  `ledgerlens/schemas.py` carry the new member. Then extend `ledgerlens/schemas.py`, `ledgerlens/tools/envelope.py`
  and the trace contract of `ledgerlens/observability/trace_event.py` with the source `doc`, keeping the docstrings
  of the modules and adding one to the function that builds the id
  - **DELIVERED**: the `EvidenceSource` and the `ToolName` literals of `ledgerlens/schemas.py`, the scheme of `ledgerlens/tools/envelope.py` and the map of `ledgerlens/agents/integrator.py` carry the source `doc` and the tool `extract_document`. The test is in `tests/documents/test_evidence_kind.py`.
- [x] T511 Write `ledgerlens/documents/evidence.py` with the construction of the `Evidence` records of the
  extraction, with a docstring that says that a document is a source of a claim and never an authority, and write
  `tests/documents/test_evidence_kind.py` again with the expectation that the evidence of a document carries the
  `ref` that holds the page and the position

## The match and the disagreement

**Purpose**: the document and the ledger may disagree, and the case says so and changes nothing.

  - **DELIVERED**: the module is in `ledgerlens/documents/evidence.py`: the `Evidence` records of the extraction carry the `ref` that holds the page and the position. The test is in `tests/documents/test_evidence_kind.py`.
- [x] T512 Write `tests/documents/test_discrepancy.py` first, expecting that a document that disagrees with the
  ledger produces a flag with the difference computed with `Decimal`, that the ledger of the fixture is byte for
  byte the same before and after the extraction and that the decision of the case names the disagreement. Then
  write `ledgerlens/documents/match.py` with the match through the read-only surface of `ledgerlens/tools/ledger_api.py`,
  with a docstring that says that the module never writes to the ledger and that a disagreement is a finding

## The boundaries of the pipeline

**Purpose**: the pipeline stays inside the rules of the repository.

  - **DELIVERED**: the test is in `tests/documents/test_discrepancy.py` and the module is in `ledgerlens/documents/match.py`: a document that disagrees with the ledger produces a flag with the difference computed with `Decimal`, the ledger is byte for byte the same before and after, and the decision names the disagreement.
- [x] T513 [P] Write `tests/documents/test_domain_boundary.py` first, reading the modules of
  `ledgerlens/documents/` with `ast` and expecting that none of them carries a SQL string and that none of them
  imports `ledgerlens.api`. The match against the ledger goes through `ledgerlens/tools/ledger_api.py`
  - **DELIVERED**: the test is in `tests/documents/test_domain_boundary.py`: no module of `ledgerlens/documents/` carries a SQL string and none imports `ledgerlens.api`, read with `ast`.
- [x] T514 [P] Write `tests/documents/test_vision_path.py` first, expecting that with no model reachable the tool
  refuses with a reason, that with the scripted model of `ledgerlens/offline.py` the number of the calls stays
  inside the ceiling of ADR-054 and that no field that only the model read becomes a value. Then write
  `ledgerlens/documents/vision.py` with the vision path, with a docstring that says that the model proposes and the
  deterministic parser decides
  - **DELIVERED**: the test is in `tests/documents/test_vision_path.py` and the module is in `ledgerlens/documents/vision.py`: with no model reachable the tool refuses, the calls stay inside the ceiling of ADR-054 and no field that only the model read becomes a value.
- [x] T515 [P] Write `tests/documents/test_redaction.py` first, expecting that the addresses and the card digits
  of the fixture are gone from the shared copy and that the flag of the redaction is present. Then write
  `ledgerlens/documents/redact.py`, with a docstring that says that a shared copy is a copy and never the document

## The tool that the agent calls

**Purpose**: the extraction is reachable by the agent and it is documented where the catalog expects it.

  - **DELIVERED**: the test is in `tests/documents/test_redaction.py` and the module is in `ledgerlens/documents/redact.py`: the addresses and the card digits of the fixture are gone from the shared copy and the flag of the redaction is present.
- [x] T516 Write `ledgerlens/tools/documents.py` with the tool of the extraction, with the envelope of
  `ledgerlens/tools/envelope.py` and the `Evidence` of the repository, with a docstring that says what the tool
  does and what it refuses, and write `tests/documents/test_tool.py` that expects the shape of the envelope for a
  success and for each refusal
  - **DELIVERED**: the tool is in `ledgerlens/tools/documents.py` with the envelope of `ledgerlens/tools/envelope.py` and the `Evidence` of the repository. The test is in `tests/documents/test_tool.py`: the shape of the envelope for a success and for each refusal.
- [x] T517 Write the tool in `docs/tools.md` and in `docs/contracts/tools.md` with the same name, the same
  description, the same type and the same kind of integration as the code, and let
  `tests/test_tools_catalog.py` expect the new tool in the catalog

## The documentation that closes the milestone

**Purpose**: a reader of the evidence knows what a document is and what it is not.

  - **DELIVERED**: the tool is in `docs/tools.md` and in `docs/contracts/tools.md` with the same name, the same description, the same type and the same kind of integration as the code, and `tests/test_tools_catalog.py` expects the new tool in the catalog.
- [x] T518 [P] Write `docs/documents.md` with the fields of the repository and where they are read, the kinds of
  confidence and what each one means, the limits of the file security and the reason of each refusal, the statement
  that the pipeline reads only the fixtures of the repository, and the statement that a document never corrects the
  ledger. Link it from `docs/README.md` by running `uv run python scripts/build_docs_index.py`

  - **DELIVERED**: the page is in `docs/documents.md`: the fields of the repository, the kinds of confidence, the limits of the file security, the statement that the pipeline reads only the fixtures and the statement that a document never corrects the ledger. The index was regenerated with `uv run python scripts/build_docs_index.py`.