# The document pipeline

The pipeline reads the fields of a document, says where on the page it read each one, and hands the result to
the verifier as evidence of the repository. A document is a source of a claim and never an authority: the
ledger states what happened, the corpus states the rules, and a document states what someone wrote down about
it. When a document and the ledger disagree, the case ends with a named decision that a person has to look at,
and the pipeline never writes to the ledger.

The pipeline reads only the fixtures of `data/fixtures/documents/`, and it refuses every other path before
opening it. The fixtures are synthetic: the repository keeps no document of a visitor (ADR-P009).

## The fields of the repository

Every field of a document says where it was read: the page and the position of it. The fields of the
repository are the merchant, the date, the transaction and the total of the document, and each one carries the
digest of the document, the page, the position, the kind of confidence, the version of the extractor and the
license of the document.

## The kinds of confidence

| Kind | What it means |
| --- | --- |
| `read` | The value was read with certainty from the text layer of the document. |
| `uncertain` | The value names a doubt: a blurred field carries no value, and the case asks the person. |
| `not_read` | The value was not read: the document does not carry it, or the pipeline does not read it. |

A value that was not read with certainty is not a value. The vision path of the pipeline exists for the
documents whose text layer cannot be read, and the model proposes and the deterministic parser decides: a
value that only the model read carries the kind of confidence that names the doubt, and it never becomes a
value of the extraction.

## The limits of the file security

A file that must not be opened is refused before it is converted, and the refusal names the check that
refused it:

| Check | The reader it answers |
| --- | --- |
| The executable payload | The machine that opens the file. |
| The compressed bomb | The disk of the machine. |
| The password | The reader that asks for a secret. |
| The size | The memory of the machine. |

## The money of a document

The money of a document is a `Decimal` with the locale of the document, and the parse never uses a float. The
amount `1.000,00` is one thousand in the Brazilian locale and one in the American locale, and the parse reads
the locale of the document. The rounding of a document is not a rounding of the ledger.

## A document never corrects the ledger

The match of a document against the ledger reads the record of the ledger through the read-only surface of
the repository, and a disagreement between the document and the ledger is a finding with the difference
computed with `Decimal`. The case ends with a named decision that a person has to look at, and the ledger is
not corrected.

## Links

- [the specification of the milestone](../specs/019-r18-source-grounded-document-extraction/spec.md)
- [ADR-094, a document is a source of evidence and it never corrects the ledger](decisions/ADR-094-a-document-is-a-source-of-evidence-and-it-never-corrects-the-ledger.md)
- [the package of the pipeline](../ledgerlens/documents/)
- [the fixtures of the documents](../data/fixtures/documents/)
