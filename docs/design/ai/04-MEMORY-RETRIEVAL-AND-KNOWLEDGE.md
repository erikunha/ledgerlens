# Memory, RAG, Knowledge and Data Provenance Research Program

## Existing baseline

`search_policies` uses FAISS + query rewriting; `recall_cases` uses semantic case memory; SQL and record tools access account-scoped ledger. Preserve those baseline semantics and add measured alternatives rather than declaring one fashionable RAG architecture superior.

## Retrieval experiments

- Baseline dense FAISS (current) vs BM25/full-text, hybrid weighted search, reranking, query rewriting/no rewriting, decomposition, temporal filtering, lexical identifiers, structured lookups vs semantic matches.
- Retrieval with and without exact date/version, customer/merchant scope, currency, source reliability and business-day locale.
- Graph-style evidence traversals: policy clause → requirement → transaction row → arithmetic → conclusion. Start relational in SQLite/PostgreSQL; specialized graph DB is conditional.
- Query planner chooses SQL, policy, FX or memory route based on observed false-positive and latency risk.
- Context packing benchmark: evidence coverage vs prompt tokens, citation accuracy and truncation.
- Citation reliability: reference points to immutable source hash and excerpt span, not a generated label alone.
- Document ingestion roadmap: optional PDF, CSV, XLSX, policy Markdown, emails *synthetic/sanitized only*, with OCR/vision if needed. Untrusted document content never sets system instructions.

## Memory taxonomy

`short_term_turns` (per session), `working_memory` (per case), `episodic_memory` (past case events), `semantic_memory` (anonymized generalized patterns), `policy_memory` (approved versioned documents), `preferences` (explicit visitor UI choices only).

Memory writes are proposal → validation → scope check → deduplicate → versioned record. Include conflict resolution, TTL, deletion, forget, provenance, poisoned memory quarantine. A malicious case cannot become an approved business policy by being retrieved repeatedly. Learning never silently modifies the ground truth of a historical experiment.

## Deep research horizon

Evaluate graph RAG, contextual/late-chunking methods, knowledge graphs, structured temporal retrieval, neuro-symbolic rules, active retrieval, learned reranking, synthetic query generation, small retrieval models and embedding drift. Every paper or model adoption requires an adversarial evaluation against current baseline and an expense/complexity analysis.

## Key metrics

Recall@k over labeled relevance, MRR/nDCG, negative retrieval rate, evidence attribution precision, version-correctness, faithfulness, token spend, retrieval latency, coverage for multilingual policy, case-level correctness uplift. Measure one category at a time and preserve the exact reference set.
