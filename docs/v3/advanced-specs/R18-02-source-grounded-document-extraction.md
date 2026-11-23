# LL-V3-R18-02 - Source-grounded document extraction

**Status:** design proposed; not yet implemented. **Strategic lens:** Comparative Advantage and Proof of Work. **Audience:** ML engineer. **Dependencies:** R8 evidence, R13 upload security, R17 fixtures.

## User outcome

Demonstrate OCR/vision/document agent with evidence positions and explicit uncertainty.

## Ownership and compatibility

Only permitted synthetic or licensed images/PDFs by default; processors sandboxed and no outbound upload without BYOK consent; adapt to `EvidenceRef`.

## Typed interfaces and persisted state

Extraction output includes `document_hash, page, bbox_or_span, field_name, normalized_value, confidence_kind, extractor_version, source_license`; no unsupported arbitrary file metadata.

## Algorithm and execution contract

Detect file type/limits, convert safely, extract text/table, parse monetary fields with locale, match to ledger using exact rules, surface contradiction between receipt/policy/ledger; reviewer approves mapping in sandbox.

## Security, invalid states and recovery

Reject executable payloads, password-protected unknown files, oversized decompression bombs; redact addresses/payment details on public share.

## Acceptance scenarios (Given / When / Then)

- Screenshot says 1.000,00 BRL while ledger shows 100.00: discrepancy flagged not auto-corrected.
- Ambiguous OCR digit: abstain or ask user.
- Unlicensed uploaded personal doc: never stored as public fixture.

## Metrics, evidence and regression gates

Field precision/recall, document citation quality, exact money consistency, latency/cost and parser failure stats.

## Definition of done and rollback

Synthetic data manifest, optical errors benchmarks and accessibility text alternative.

No claim of implementation is made by this spec. Shipped status requires passing exact executable tests, a source revision, a sanitized replay/trace, and known limitations in release notes.
