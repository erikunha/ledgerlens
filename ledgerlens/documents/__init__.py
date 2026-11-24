"""The document pipeline: the fields of a document, where on the page they were read, and the evidence of them.

Why the pipeline exists: the repository reads the ledger, the corpus of the policies and a reference rate, and
it cannot read a picture of a receipt. The pipeline reads the fields of a document, says where on the page it
read each one, and hands the result to the verifier as evidence of the repository.

Why a document is a source of a claim and never an authority: the ledger states what happened, the corpus
states the rules, and a document states what someone wrote down about it. When a document and the ledger
disagree, the case ends with a named decision that a person has to look at, and the pipeline never writes to
the ledger.

Why the pipeline reads only the fixtures of the repository: ADR-P009 forbids the collection of real financial
documents, and the refusal of a path outside `data/fixtures/documents/` happens before the file is opened.
"""
