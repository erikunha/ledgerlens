# Feature Specification: Source-grounded document extraction

**Feature Branch**: `feature/v3`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Design documents: [R18-02, source-grounded document extraction](../../docs/design/advanced-specs/R18-02-source-grounded-document-extraction.md),
[ADR-005, the guarded text to SQL and the read-only connection](../../docs/decisions/ADR-005-guarded-text-to-sql.md),
[ADR-054, the agent loop has a ceiling in every path](../../docs/decisions/ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md),
[ADR-061, the corpus of the policies is the contract of a fictional company](../../docs/decisions/ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md),
[ADR-074, a case ends in a decision and the decision belongs to the code](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md),
[ADR-P007, one evidence-first agent by default](../../docs/design/adrs/ADR-P007-no-multiagent-by-default.md),
[ADR-P009, the privacy scope of the public project](../../docs/design/adrs/ADR-P009-privacy-scope.md) and
[the release train, the R18 contract](../../docs/design/roadmap/RELEASE-TRAIN-2027-2030.md). User description: "The
repository reads a ledger, a corpus of policies and a reference rate. It cannot read a receipt, and when a
merchant sends a picture of a receipt and the ledger says another number, the repository has no way to hold both.
This specification adds a document pipeline that extracts the fields of a document, says where on the page it read
them, and never corrects the ledger with what it read."

## What exists today and what the package proposes

The package proposes an OCR and vision pipeline that produces evidence with positions and explicit uncertainty, and
that refuses a document it is not allowed to keep. It is a design note of the frozen import and nothing of it
exists in the repository.

There is no document ingestion of any kind. There is no OCR dependency, no PDF reader, no image decoder and no
upload. What exists is the shape a document has to fit into:

| What the package names | What the repository has | What is missing |
|---|---|---|
| `EvidenceRef` | `Evidence` in `ledgerlens/schemas.py`, with an id of the form `sql:1`, `policy:3`, a `source_type`, a `tool`, the `content`, the `ref` and the `retrieved_at` | a source for a document and the position of the text on the page |
| adapt to `EvidenceRef` | the envelope of the tools in `ledgerlens/tools/envelope.py`, whose id scheme starts with one of `sql`, `api`, `policy`, `fx`, `calc` or `case`, and whose `ok` and `error` shapes the agent reads | one member in the scheme and one member in the literal of the tools |
| the extract and the match | the read-only ledger surface of `ledgerlens/tools/ledger_api.py` and the calculator of `ledgerlens/tools/calculator.py` | the extraction itself and the matching rule |
| the contradiction between receipt, policy and ledger | the escalation of `ledgerlens/verify/escalation.py` and the decision of the code under ADR-074 | the third source of the contradiction, the document |
| only permitted synthetic or licensed images and PDFs | ADR-009 keeps the public data first and the simulation for the gaps; ADR-P009 forbids the collection of real financial documents | the fixtures and the refusal of an unlicensed document |

Four adaptations the port makes, because the repository had already decided the neighbouring question.

1. **A document is a source of evidence, and it never corrects the ledger.** The package says the discrepancy
   between a receipt and the ledger is flagged and not corrected automatically. The repository already holds that
   rule for a different source: under ADR-074 a case ends in a decision and the decision belongs to the code, and
   under ADR-061 the corpus of the policies states the rules while the ledger states the facts. The port keeps the
   ledger as the authority of what happened and makes the document a source of a claim about it, with the position
   of the text that carries the claim.
2. **The evidence id scheme gains one member and nothing else.** The id of a document evidence becomes `doc:<id>`,
   the `EvidenceSource` literal gains `doc` and the `ToolName` literal gains the tool of the extraction. The scheme
   is checked in `ledgerlens/tools/envelope.py` and in `ledgerlens/schemas.py`, and the trace of ADR-013 carries the
   same vocabulary, so the trace contract is checked too. The package's `EvidenceRef` schema of
   `docs/design/contracts/schemas/v3-evidence-ref.schema.json`, with its `source_kind` of `simulated_document` and its
   `trust_level`, is the shape of the reference that the new evidence carries, and the port maps it onto the
   repository's `Evidence` instead of introducing a second kind of evidence.
3. **No upload ships.** The package assumes that a document arrives from somewhere. ADR-P009 forbids the collection
   of real financial documents by a visitor, and the repository is a public laboratory. The pipeline therefore reads
   the synthetic documents of `data/fixtures/documents/` and refuses everything else by default. A document that a
   visitor brings is out of scope, and the decision to accept one, if it is ever taken, needs its own record.
4. **The deterministic path ships first and the model is optional.** The offline gate of the repository runs with
   no key and no network, so a pipeline that needs a vision model cannot be the only path. The extraction has a
   deterministic part, which reads the text layer of a document and parses the money with the locale of the
   document, and an optional part that asks a vision model when the file has no text layer. The optional part is
   bounded by the ceiling of the run of ADR-054, it never decides, and when no model is reachable the tool refuses
   with a reason instead of guessing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read a receipt and say where each field was read (Priority: P1)

The analyst asks what the receipt of a refund says. The tool reads the document of the fixture, and for every
field it returns the page, the position of the text on the page, the name of the field, the value it read, the
kind of confidence it has and the version of the extractor that read it. The analyst can open the document and see
the same field in the same place.

**Why this priority**: a value without a position is a value the reader has to trust. The whole point of the
extraction is that a person can check it against the document.

**Independent test**: run the extraction over the fixture of a receipt and assert that every field carries a page
and a position that lies inside the page, a field name, a value, a kind of confidence and the version of the
extractor, and assert that the position of the amount of the receipt is the position of the printed amount.

### User Story 2 - See a receipt that disagrees with the ledger and get a flag, not a correction (Priority: P1)

The receipt says one thousand and zero reais, with the Brazilian format of one thousand as a dot, and the ledger
says one hundred reais. The tool reports the two values, the difference computed with `Decimal`, and the case ends
with a decision that names the disagreement. The ledger does not change, and the answer of the analyst says that
the document and the ledger disagree and that a person has to look at it.

**Why this priority**: a document that corrects the ledger silently turns a picture into an accounting entry. The
repository decides the other way everywhere else, and the rule of the money is `Decimal` and never a float.

**Independent test**: extract the amount of the fixture whose receipt and ledger disagree and assert that the
difference is computed with `Decimal`, that the ledger of the fixture is byte for byte the same before and after the
extraction, and that the decision of the case is the one that names the disagreement.

### User Story 3 - Be told that the extraction is not sure instead of being given a guess (Priority: P1)

The analyst uploads a photograph of a receipt where the last digit of the amount is blurred. The tool does not
answer with a number. It returns the field, the position, the two readings it could not separate and a kind of
confidence that says the value is not decided, and the case asks the person.

**Why this priority**: an amount that is guessed is an amount that goes into an answer and into a comparison, and
the reader of the answer cannot tell it from an amount that was read.

**Independent test**: run the extraction over the fixture of a blurred digit and assert that the result carries no
value for that field, that it carries the kind of confidence that names the doubt and that the decision of the case
is to ask the person.

### User Story 4 - Be refused a file that must not be opened (Priority: P1)

The analyst points the tool at a file that carries an executable payload, at a file whose compressed form expands
past the limit, at a file that is protected by a password and at a file that is bigger than the limit. Each one is
refused with a readable reason and a non zero exit code, before the file is opened and before anything is written
to the disk.

**Why this priority**: the pipeline reads files that a person brought, and a file that is read by an image decoder
or by a converter is an attack surface.

**Independent test**: pass each one of the four files and assert that the refusal names the reason, that the
exception is not a traceback and that no temporary file survives the refusal.

### User Story 5 - Read a document that was never stored (Priority: P1)

The analyst points the tool at a document of a visitor. The tool refuses it, because the repository does not accept
the documents of a visitor and never stores one. The fixtures of the repository are the only documents that the
pipeline reads.

**Why this priority**: ADR-P009 is a safety invariant and not a preference, and a public laboratory that keeps the
documents of its visitors is a laboratory with a different purpose.

**Independent test**: point the extraction at a path that is outside `data/fixtures/documents/` and assert that it is
refused with the reason and that the file was not copied, not opened and not read.

### User Story 6 - See the version of the extractor that read a document (Priority: P2)

The analyst reads the evidence of a document and sees the version of the extractor that produced it and the
license of the source of the document. Two extractions of the same document with two different versions are two
different pieces of evidence and the reader can tell them apart.

**Why this priority**: the extractor changes, and an evidence without the version of the extractor cannot be
reproduced.

**Independent test**: extract the same document twice and assert that both results carry the same version and the
same license, and assert that the evidence refuses to be written when the version is missing.

### Edge Cases

- A document with no text layer and no model reachable: the tool refuses with the reason that no model is
  reachable, and it never returns a value.
- A document that names an amount in two currencies: both are returned with their currencies, and the tool never
  picks one.
- A document whose amount carries more decimal places than the currency admits: the value is read with `Decimal`
  and the excess is reported, never rounded away silently.
- A document that is a copy of another fixture: the digest of the document is the same, and the two references are
  told apart by the path and not by the content.
- A document in a language the extractor does not read: the text is returned with the kind of confidence that names
  the language, and no monetary field is parsed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The output of an extraction carries, for every field, the digest of the document, the page, the
  position of the text on the page, the name of the field, the normalized value, the kind of confidence, the
  version of the extractor and the license of the source. A result that misses the version of the extractor is
  refused.
  - Test: `tests/documents/test_extraction_output.py` expects every field of the result to carry the eight values,
    and expects the refusal when the version is missing.
- **FR-002**: The result of an extraction is an `Evidence` of the repository, with a source of `doc`, and the id
  scheme of `ledgerlens/tools/envelope.py` and the literals of `ledgerlens/schemas.py` carry that source. The
  trace of ADR-013 carries the same vocabulary.
  - Test: `tests/documents/test_evidence_kind.py` expects the id of a document evidence to match the scheme of the
    envelope, and `tests/tools/test_tools_catalog.py` expects the new tool in the catalog of the tools.
- **FR-003**: The monetary field of a document is parsed with the locale of the document and is a `Decimal`. The
  amount of the receipt of one thousand reais in the Brazilian format is one thousand and not one.
  - Test: `tests/documents/test_money_parsing.py` expects the amount of the Brazilian fixture to be the value of
    one thousand with two decimal places, and expects the amount of the American fixture to be the value of one
    thousand with two decimal places, and expects a `Decimal` in both cases.
- **FR-004**: A document that disagrees with the ledger produces a flag and never a correction. The ledger of the
  fixture is byte for byte the same before and after the extraction, and the decision of the case names the
  disagreement.
  - Test: `tests/documents/test_discrepancy.py` expects the flag, expects the ledger to be unchanged and expects
    the decision to name the disagreement.
- **FR-005**: A field that the extractor cannot read with certainty produces no value. The result carries the kind
  of confidence that names the doubt and the case asks the person.
  - Test: `tests/documents/test_uncertainty.py` expects no value for the blurred field, expects the kind of
    confidence and expects the decision to ask the person.
- **FR-006**: A file that carries an executable payload, a file whose compressed form expands past the limit, a
  file protected by a password and a file that is bigger than the limit are refused with a readable reason before
  the file is opened, and no temporary file survives the refusal.
  - Test: `tests/documents/test_file_security.py` expects the four refusals, the reason in the message and an
    empty temporary directory after each of them.
- **FR-007**: The pipeline reads only the documents of `data/fixtures/documents/` and refuses every other path
  without opening, reading or copying the file.
  - Test: `tests/documents/test_only_fixtures.py` expects the refusal for a path outside the folder of the
    fixtures and expects that the file was not read, with a spy over the open.
- **FR-008**: The document evidence carries the license of the source, and a document whose license is unknown is
  refused.
  - Test: `tests/documents/test_license.py` expects the license in the result and the refusal for a fixture whose
    license is unknown.
- **FR-009**: The pipeline never speaks SQL and never imports the API. The matching against the ledger goes
  through the read-only surface of the domain, the same way `ledgerlens/tools/ledger_api.py` does.
  - Test: `tests/documents/test_domain_boundary.py` reads the modules of `ledgerlens/documents/` with `ast` and
    expects no SQL string and no import of `ledgerlens.api`.
- **FR-010**: The part of the pipeline that asks a model is bounded by the ceiling of the run, it never decides a
  value on its own, and with no model reachable the tool refuses with a reason.
  - Test: `tests/documents/test_vision_path.py` expects the refusal with no model, expects that the number of the
    calls of the model stays inside the ceiling of ADR-054 with the scripted model, and expects that no field that
    the model read alone becomes a value.
- **FR-011**: The redaction of a document that is shared removes the addresses and the payment details, and the
  shared copy carries the flag that says it was redacted.
  - Test: `tests/documents/test_redaction.py` expects the addresses and the card digits of the fixture to be gone
    from the shared copy and the flag to be present.
- **FR-012**: The tool of the extraction is documented in `docs/tools.md` and in `docs/contracts/tools.md` with the
  same name, the same description and the same kind of integration as the code.
  - Test: `tests/test_tools_catalog.py` expects the new tool in both documents.

### Key Entities

- **Document**: a file of the folder `data/fixtures/documents/`, with its digest, its license and its pages.
- **Field**: one value read from a document, with the page, the position, the name, the normalized value, the kind
  of confidence and the version of the extractor that read it.
- **Kind of confidence**: the named quality of a field: `read` when the deterministic parser read it, `confirmed`
  when a model read it and the deterministic parser agreed, `doubtful` when the model read it and the parser did
  not agree, and `absent` when no value was read at all.
- **Disagreement**: the named finding that a document and the ledger hold different values for the same thing. It is
  a finding and not a correction.
- **Extraction manifest**: the record of the digest of the document, the license of the source, the version of the
  extractor and the count of the fields, the same way the bundle manifest carries the digest of every file.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every field of every extraction carries the digest of the document, the page, the position, the name,
  the value, the kind of confidence, the version of the extractor and the license.
- **SC-002**: The amount of the Brazilian fixture is one thousand and not one, and the amount of every monetary field
  is a `Decimal`.
- **SC-003**: The ledger of a fixture is byte for byte the same before and after an extraction, and a disagreement
  is a named decision.
- **SC-004**: A field that cannot be read with certainty carries no value, and the case asks the person.
- **SC-005**: The four dangerous files are refused with a readable reason before the file is opened, and no
  temporary file survives.
- **SC-006**: A path outside `data/fixtures/documents/` is refused without the file being opened.
- **SC-007**: No module of `ledgerlens/documents/` imports `ledgerlens.api` and none carries a SQL string.
- **SC-008**: With no model reachable the tool refuses, and the number of the calls of the model stays inside the
  ceiling of the run.
- **SC-009**: The catalog of the tools carries the new tool in the code and in both documents.
- **SC-010**: The whole suite runs offline with `LEDGERLENS_OFFLINE=1`, with no key and no network.

## Assumptions

- The fixtures of the documents are synthetic and belong to the repository, under ADR-009. Their license is
  declared in the manifest of the fixtures and the pipeline refuses a document whose license is unknown.
- The deterministic parser reads the text layer of a document. A document that has no text layer needs the vision
  path, and the vision path needs a provider, so it is not part of the offline gate.
- The extraction is a source of a claim and never an authority. The ledger states what happened and the corpus of
  the policies states the rules.
- The vision path is bounded by the ceiling of the run of ADR-054, and it never publishes a value that the
  deterministic parser did not confirm.
- The fields of the documents are the fields the repository already works with: the amounts, the currencies, the
  identifiers of the ledger and the dates.
- Nothing in this specification is built yet.

## Out of scope

- The acceptance of a document from a visitor. The pipeline reads the fixtures of the repository, and the decision
  to accept one needs a record of its own.
- The storage of a document in the database and the retention of a document after a run. The extraction reads a
  file and returns evidence.
- The improvement of the retrieval over documents, the reranker and the memory. The extraction produces evidence
  and the rest of the chain consumes it as it consumes any other evidence.
- The multimodal parts that are not a document: the voice, the video and the audio.
- The publication of a document in the site.

## Design documents

- [R18-02, source-grounded document extraction](../../docs/design/advanced-specs/R18-02-source-grounded-document-extraction.md)
- [ADR-005, the guarded text to SQL and the read-only connection](../../docs/decisions/ADR-005-guarded-text-to-sql.md)
- [ADR-013, the public trace is a versioned contract](../../docs/decisions/ADR-013-public-trace-as-a-versioned-contract.md)
- [ADR-054, the agent loop has a ceiling in every path](../../docs/decisions/ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md)
- [ADR-061, the corpus of the policies is the contract of a fictional company](../../docs/decisions/ADR-061-the-corpus-of-the-policies-is-the-contract-of-a-fictional-company.md)
- [ADR-074, a case ends in a decision and the decision belongs to the code](../../docs/decisions/ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md)
- [ADR-P007, one evidence-first agent by default](../../docs/design/adrs/ADR-P007-no-multiagent-by-default.md)
- [ADR-P009, the privacy scope of the public project](../../docs/design/adrs/ADR-P009-privacy-scope.md)
- [the evidence ref schema of the package](../../docs/design/contracts/schemas/v3-evidence-ref.schema.json)
- [the release train, the R18 contract](../../docs/design/roadmap/RELEASE-TRAIN-2027-2030.md)
- [the implementation plan of this specification](plan.md) and [its tasks](tasks.md)

## Status

Nothing in this specification is built. The repository holds the evidence model, the envelope of the tools, the
read-only ledger surface and the decision of the code, and it holds none of the document pipeline, of the fixtures
of the documents, of the source `doc` of the evidence and of the tool of the extraction.

The decision this specification needs is written down before the first task: a document is a source of evidence, it
never corrects the ledger, and the pipeline reads only the fixtures of the repository. That record is the next free
number of `docs/decisions/` (ADR-080 at the time of writing; check
[the index of the decisions](../../docs/decisions/README.md) before creating the file). It does not change any
accepted record.
