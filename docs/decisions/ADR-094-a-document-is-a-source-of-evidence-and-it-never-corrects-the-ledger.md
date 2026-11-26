---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-094: A document is a source of evidence and it never corrects the ledger

Status: accepted. Date: 2026-11-24.

## Context

The design package
[LL-V3-R18-02, source-grounded document extraction](../design/advanced-specs/R18-02-source-grounded-document-extraction.md)
proposes a document pipeline that reads the fields of a document, says where on the page it read each one, and
hands the result to the verifier as evidence. The repository reads three things: the ledger, the corpus of the
policies and a reference rate. It cannot read a picture of a receipt, and it has no way to hold two accounts of
the same event at once.

The milestone of [specs/019](../../specs/019-r18-source-grounded-document-extraction/spec.md) adds the
pipeline, and the rule that shapes every decision of it is that a document is a source of a claim and never an
authority. The ledger states what happened; the corpus states the rules; a document states what someone wrote
down about it.

## Decision

**A document is a source of evidence and it never corrects the ledger, the extraction produces `Evidence` of
the repository with a source of `doc`, a disagreement between a document and the ledger is a decision that a
person has to look at, the pipeline reads only the fixtures of the repository, and the vision path never
publishes a value the deterministic parser did not confirm.**

1. **The extraction produces `Evidence` of the repository with a source of `doc`.** The verifier consumes the
   extraction without learning a second kind of evidence, and the id of a document evidence matches the scheme
   of the repository. A document is a source of a claim and never an authority.
2. **The ledger keeps the authority of what happened.** When a document and the ledger disagree, the case ends
   with a named decision that a person has to look at, exactly as
   [ADR-074](ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md) decides for every other
   disagreement in the repository. The pipeline never writes to the ledger, and no task of the milestone adds
   such a write.
3. **The pipeline reads only the fixtures of `data/fixtures/documents/` and refuses every other path before
   opening it.** [ADR-P009](../design/adrs/ADR-P009-privacy-scope.md) forbids the collection of real
   financial documents, and the refusal happens before the file is opened, so a document that was never allowed
   to be read is never read.
4. **The deterministic path ships first.** The offline gate runs with no key and no network, so a pipeline
   whose only path asks a vision model could never be part of it. The deterministic parser reads the text layer
   of a document and parses the money with the locale of the document.
5. **The vision path never publishes a value the deterministic parser did not confirm.** The vision path
   exists, it is bounded by the ceiling of the run of
   [ADR-054](ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md), and a value that only the model read
   carries the kind of confidence that names the doubt. The model proposes and the deterministic parser
   decides.
6. **A value that was not read with certainty is not a value.** A blurred field carries no value, and its kind
   of confidence names the doubt, and the case asks the person.

## Alternatives considered

- **To let the extraction correct the ledger when a document disagrees with it.** Refused. The ledger states
  what happened, and a document states what someone wrote down about it. A disagreement is a finding that a
  person has to look at, and the pipeline never writes to the ledger.
- **To let the pipeline read any path the caller names.** Refused. ADR-P009 forbids the collection of real
  financial documents, and the pipeline reads only the fixtures of the repository. The refusal happens before
  the file is opened.
- **To let the vision path publish the values it reads.** Refused. The model proposes and the deterministic
  parser decides, and a value that only the model read carries the kind of confidence that names the doubt.
- **To parse the money of a document with a float.** Refused. The money of a document is a `Decimal` with the
  locale of the document, and a float is already a rounded number.

## Consequences

- **The repository has the document pipeline**, in `ledgerlens/documents/`: the detection and the refusals
  (`detect.py`, `security.py`, `license.py`), the conversion (`convert.py`), the fields and the money
  (`fields.py`, `money.py`), the evidence (`evidence.py`), the match (`match.py`), the vision path
  (`vision.py`) and the redaction (`redact.py`), with the tests in `tests/documents/`.
- **The tool of the extraction is in `ledgerlens/tools/documents.py`**, with the envelope of the repository
  and the `Evidence` of the repository, and it is in the catalog of the tools.
- **The fixtures of the documents are in `data/fixtures/documents/`**, with their manifest and their license,
  and they are synthetic: the repository keeps no document of a visitor.
- **The page of the documents is [the page of the documents](../documents.md)**, with the fields of the
  repository, the kinds of confidence, the limits of the file security and the statement that a document never
  corrects the ledger.

## Links

- [ADR-005, the guarded text to SQL](ADR-005-guarded-text-to-sql.md)
- [ADR-013, the public trace is a versioned contract](ADR-013-public-trace-as-a-versioned-contract.md)
- [ADR-054, the agent loop has a ceiling in every path](ADR-054-the-agent-loop-has-a-ceiling-in-every-path.md)
- [ADR-074, a case ends in a decision and the decision belongs to the code](ADR-074-a-case-ends-in-a-decision-and-the-decision-belongs-to-the-code.md)
- [the page of the documents](../documents.md)
- [the specification of the milestone](../../specs/019-r18-source-grounded-document-extraction/spec.md)
- [the design package](../design/advanced-specs/R18-02-source-grounded-document-extraction.md)
