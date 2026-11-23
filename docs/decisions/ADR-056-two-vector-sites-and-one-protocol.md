---
type: adr
status: proposed
date: 2026-11-22
---

# ADR-056: Two vector sites and one protocol

Status: proposed. Date: 2026-11-22.

## Context

The repository has a promise about the vector library, and it is in the two places a reader looks first.

`ledgerlens/retrieval.py:1-5` says that the module "is the only place in the project that talks to FAISS, so
switching vector libraries touches one file". [ADR-006](ADR-006-embeddings-and-index.md) repeats it at line 21: the
FAISS version is pinned "behind `ledgerlens/retrieval.py` so a future swap touches a single file".

The promise is false, and it is false in the place that matters.

### The second site

`ledgerlens/memory/long_term.py:36` imports the library directly: `from langchain_community.vectorstores import
FAISS`. The module uses it at `:200` (`FAISS.load_local`), at `:211` (`FAISS.from_documents`) and at `:112`
(`store.similarity_search_with_score`), and it names the type in its own signatures (`:83`, `:185`, `:207`, `:217`).
The case memory is the long term memory of the agent, and the tool that reads it is on the critical path of an
investigation: `recall_cases` (`ledgerlens/tools/cases.py:111-118`) calls `CaseMemory.recall` (`:85`), which calls
`_store` (`ledgerlens/memory/long_term.py:108`).

ADR-030 (line 50) and `ledgerlens/sandbox/memory.py:13` already write the dependency of the case memory down, so the
two sites are known to the people who wrote those sentences and invisible to the sentence of the docstring.

### The two sites differ

The policy index is a build artifact: `scripts/build_index.py` builds it, the tool only loads it, and it refuses to be
built at query time (`ledgerlens/retrieval.py:17`, `ledgerlens/tools/policies.py:9-10`, `docs/contracts/tools.md:213`).

The case index is live data, and it rebuilds itself at read time. `_store` (`ledgerlens/memory/long_term.py:185-205`)
compares the number of cases in the meta with the number of records (`:199`) and, when they differ, builds the whole
index again from the records (`:204`), with the embeddings, inside the call. The cost lands inside a tool call, on the
critical path of `recall_cases`, and it is invisible: nothing logs it and the caller receives a list of cases as if the
answer had been free.

### The third site, and what the audit said

The runtime audit of 2026-11-22 reported that `ledgerlens/eval/run.py:158-176` imports fastembed directly. The code
does not say that. The runner imports `FastEmbedEmbeddings` from `ledgerlens.embeddings`
(`ledgerlens/eval/run.py:58`) and declares a class that extends it (`:175-184`) over a model that counts the words and
hashes each of them into 64 positions (`:155-172`). The only import of fastembed in the repository is inside a
function of the embedding layer (`ledgerlens/embeddings.py:22-26`), the place ADR-006 line 20 chose. The runner does
not touch FAISS either: it builds its index through the builder of the retrieval (`ledgerlens/eval/run.py:83`,
`:203-208`).

So the third site is real, and it is not what the audit said it was: it is a third embedding site, not a third vector
site. The distinction matters for the decision. The runner has to build its own vectors, for two reasons that are both
real: the run has to be reproducible offline, with no download of 67 MB and no network, and the vectors of the report
must be a function of the text and of nothing else. The word count model gives that: the same text always gives the
same vector, on any machine, with no model file. That is a legitimate exception, and it has to be written down as a
decision, because the alternative is that the next person reads it as an accident and swaps the real model in, which
would make the offline report measure another thing.

### What the false promise costs

A reader who believes it is misled about the shape of the repository, and the cost is paid the day the swap happens: a
swap touches `ledgerlens/retrieval.py` and `ledgerlens/memory/long_term.py`. The promise said one file.

## Decision

**Two vector sites, one protocol, and the promise becomes a check.**

### 1. The claim is corrected, and ADR-006 is not rewritten

The sentence of `ledgerlens/retrieval.py:4-5` is false and is replaced. ADR-006 is accepted, and this record does not
change it; it says what it means for it. The promise of line 21 was false as written, because two files talked to
FAISS. This record makes it true, and the file it names is `ledgerlens/vectorstore.py` and not
`ledgerlens/retrieval.py`. The other sentences of that line are untouched: the version of the library is pinned, the
vectors are normalized, and the L2 distance orders like the cosine.

### 2. The protocol lives in `ledgerlens/vectorstore.py`

A new module is the only module of `ledgerlens/` that imports `langchain_community.vectorstores`. It offers three
operations and a handle:

| operation | what it does | who calls it |
| --- | --- | --- |
| `load_index(folder, embeddings)` | reads the folder of an index and returns the handle, refusing when the files are absent | both sites |
| `search_index(handle, query, k)` | the k closest texts to the query, with the distance | both sites |
| `add_to_index(handle, items, ids)` | adds the texts with their ids and returns the handle | the case site only |

The handle is a `typing.Protocol` (`VectorStore`) with the operations the callers use, so that no site names FAISS in a
signature and the type of the store never leaves the module. The module owns the three things the two sites do today
in the same way and that a swap has to change together: the import of the library, the normalization of the vectors
(`normalize_L2=True` in `ledgerlens/retrieval.py:146` and `:185`, in `ledgerlens/memory/long_term.py:201-202` and
`:211-213`) and the consent to open the pickle (`ledgerlens/retrieval.py:182-185`).

The meta file stays with each site, because the two metas do not mean the same thing: the meta of the policy index
describes an artifact of the repository (ADR-055 adds the digest of the corpus to it) and the meta of the case index
describes a live set of records (`ledgerlens/memory/long_term.py:220-227`). What the meta means stays where it is.

### 3. The two sites keep their own lifecycle

The policy index is built by a script and only loaded. The case index is written by the process that writes a case:
`write_case` adds the record to the index and saves it (`ledgerlens/memory/long_term.py:249-257`). The rebuild at read
time stays, because the case index is written by one process and read by another and a mismatch of the count is a real
state of the disk. What this record decides is that the rebuild stops being an invisible side effect of a search: the
case memory logs it with the count that did not match and the elapsed time, and `recall_cases` says it in the note of
the envelope (`ledgerlens/tools/cases.py:88`). It is not removed, because removing it would break the case memory of a
session written by another process.

### 4. The evaluation runner is a declared third site

The runner keeps `OfflineEmbeddings` (`ledgerlens/eval/run.py:175-184`) and its own index folder, and it goes through
the same protocol module as the other two sites. The reason is written down in the docstring of the runner, so that the
exception is a decision and not an accident. The cost of the decision is named here: the offline report measures the
plumbing and not the quality of a model (the note of the runner says so, `ledgerlens/eval/run.py:110-115`), and the
retrieval of the offline run says nothing about the retrieval of the production one, because the vectors are not the
vectors of the model.

### 5. The promise becomes a check

A test reads the modules of `ledgerlens/` and refuses any import of `langchain_community.vectorstores` outside
`ledgerlens/vectorstore.py`. The style is the one of the guard of the public repository, which parses the source with
`ast` (`tests/test_public_clean.py`). A promise with a test is a rule, and a promise in prose is a promise that
drifts.

### 6. The tasks

The tasks follow the format of `specs/004-r4-verifier-calibration/tasks.md`. The file that would carry them,
`specs/005-r4-runtime-latency-and-cost-per-case/tasks.md`, does not exist today, so the ids below are reserved.

- [ ] T126 Write the module `ledgerlens/vectorstore.py` with the handle protocol `VectorStore` and the three
  operations `load_index`, `search_index` and `add_to_index`, with the test in `tests/retrieval/test_vectorstore.py`
  that a search returns the closest texts with the distance
- [ ] T127 Move the import of FAISS and its three uses out of `ledgerlens/retrieval.py` into the protocol module,
  keeping `build_policy_index`, `load_policy_index` and `search_policy_index` with the same signatures and the same
  results, with the tests of `tests/tools/test_build_index.py` and `tests/tools/test_policies.py` green
- [ ] T128 Move the import of FAISS and its three uses out of `ledgerlens/memory/long_term.py` into the protocol
  module, keeping the behavior of `CaseMemory` the same, with the test of `tests/memory/test_long_term.py` green
- [ ] T129 Write the guard in `tests/retrieval/test_vectorstore_boundary.py` that reads the modules of `ledgerlens/`
  with `ast` and refuses any import of `langchain_community.vectorstores` outside `ledgerlens/vectorstore.py`
- [ ] T130 Write the note of the rebuild in the case memory: the result of the recall says whether the index was
  rebuilt, and `recall_cases` says it in the note of the envelope, with the test in `tests/tools/test_recall_cases.py`
- [ ] T131 Correct the docstring of `ledgerlens/retrieval.py:4-5`, so that no file says that one file talks to FAISS,
  and write in the docstring of `ledgerlens/eval/run.py` why the runner builds its own vectors

### 7. What this record does not change

The embedding, the format of the index, the metadata of the passages and the numbers of ADR-006 stay. The public
functions of `ledgerlens/retrieval.py` and the methods of `CaseMemory` keep their names and their behavior. The rule
that the policy index is a build artifact and the rule that the case index is live data stay, and this record only
names them.

## Alternatives considered

- **Correct the claim and do nothing else.** The cheapest answer, and it leaves two sites that talk to the same
  library in two different ways, with the duplication of the normalization and of the consent of the pickle.
- **Extract the protocol and leave the claim as it is.** Then the false sentence stays in the file it lives in.
- **Move the case memory into the retrieval module.** The two have different lifecycles (a build artifact and live
  data), different scopes (the repository and the session, ADR-030) and different formats of the text they index.
- **Make the case index a build artifact, like the policy index.** Then a case written by a session would need a build
  step before another session could read it, and a write would become a batch.
- **Leave the rebuild at read time exactly as it is, silently.** The cost stays invisible, and the cost of an answer
  is a number nobody can price.

## Consequences

- The promise of ADR-006 line 21 becomes true, in a different file, and with a test that refuses when it stops being
  true.
- A future swap of the vector library touches `ledgerlens/vectorstore.py`, and the two sites keep their behavior
  because the behavior lives in the sites.
- The cost of the read time rebuild of the case index becomes visible in the log and in the note of the envelope, and it
  stays where it is, on the critical path of `recall_cases`.
- The evaluation runner keeps its own vectors, and the reason is written where the next person will read it.

## The debt of this record

Two debts.

The first is the size of the protocol. It was written to be small (three operations and a handle), and it will grow:
the day a fourth operation appears, the protocol has to be reviewed as a decision, because a protocol that grows is a
framework.

The second is the measurement of the cost. The number of the latency does not exist yet: `ledgerlens/eval/run.py` has
no latency metric and `data/eval/report_online.md` has no latency column. Until it exists, this record is a visibility
and not a fix.
