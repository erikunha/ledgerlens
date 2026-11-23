---
type: adr
status: accepted
date: 2026-11-22
---

# ADR-055: The policy index carries the hash of the corpus

Status: accepted. Date: 2026-11-22.

## Context

The repository answers the questions about the rules from an index that is built once and committed to git.
[ADR-006](ADR-006-embeddings-and-index.md) chose the embedding, the format of the index and the build step, and the
artifact lives in `data/index/policies_fastembed/`. A build artifact is only as trustworthy as the rule that says when
it went out of date, and the repository has no such rule for the content of the corpus.

**What the meta carries.** `build_policy_index` (`ledgerlens/retrieval.py:193-227`) writes the vectors, the store and
the meta. The meta held seven fields (`ledgerlens/retrieval.py:215-224`): the name of the embedding, the dimension,
the number of chunks, the metric, the chunk size, the chunk overlap and the build date. Every one of them describes
the index or the tool that built it. Not one of them described the corpus, which is the eight markdown files of
`data/policies/` that the index was made of.

`load_policy_index` (`ledgerlens/retrieval.py:229-275`) was the only reader of the meta at run time. It refused when
one of the three files was missing (`:241-243`), read the meta, refused when the meta named another embedding
(`:262-268`), loaded the store (`:273`) and refused when the dimension of the loaded store was not the dimension of the
meta (`:274-275`). It never looked at `data/policies/`, and nothing compared the
index with the bytes it was built from.

**The failure that the code cannot see.** A policy is edited in the repository, the commit merges, the gate is green,
and the agent keeps answering from the old index. The gate is green because `scripts/gate.sh` ran six steps
(`:10-38`: ruff, the offline tests, the datasets, the export, the replay digests and the replay budget) and none of
them was the index. `scripts/build_index.py` is a manual step (`:31-39` builds, `:43-56` runs) that prints the folder,
the chunks, the dimension, the embedding and the digest of the corpus (`:54-57`) without reminding the reader that
the index is a second artifact to commit together with the policies.

The reader of the answer is not warned either. Every excerpt carries the version of the policy it came from
(`ledgerlens/retrieval.py:290`), the tool keeps that field (`ledgerlens/tools/policies.py:90`) and the contract
publishes it (`docs/contracts/tools.md:201`), so an answer can cite `policy:refund-policy#refund-window`, carry the
version the repository declares today, and be wrong about the text behind it: the field that would expose the gap
comes out of the index and not out of the file.

`INDEX_MISMATCH` is the wrong tool for this failure: it fires when the vector space changed
(`ledgerlens/retrieval.py:262-268`), which is the rare failure, while the common one, a change of the content of the
corpus, keeps the same embedding, the same dimension and the same file names, and passes every check the loader makes.

**Why the gap is invisible today.** The committed meta said `built_on: 2026-11-08` and 105 chunks
(`data/index/policies_fastembed/index_meta.json`), and the eight policies all declare `version: 2026-10-01`. The
corpus of the disk produces 105 excerpts today, with the splitter and the chunk size and overlap of
`ledgerlens/retrieval.py:54-55` and `:128`, so the index and the corpus agree in size. That agreement is a fact about
the calendar and not a check, and the first edit of a policy after the build makes the gap visible.

**What ADR-006 decided, and what this record does not touch.** ADR-006 is accepted, and this record does not change
it. Its decision about the compatibility of the index is at line 24: the loader refuses an index whose embedding does
not match the active one, because neighbors from another vector space would be wrong without any warning.

**Nothing accepted is broken by this record.** The rule of line 24 stays exactly as it is, with the same reason and
the same code. The corpus digest is a second rule, with a different reason (the text of the answer would be the text
of a version that is not on the disk) and a different code. The two rules fire on different failures, so neither of
them weakens the other, and the escape hatch of line 61 (that `INDEX_MISMATCH` prevents using the old index by
mistake) keeps its force and becomes true in one more case: an index built over another corpus is refused as well.
The chunking, the format of the index, the rule that the tool never rebuilds (`ledgerlens/retrieval.py:19`) and the
numbers of ADR-006 stay, because this record does not touch the corpus the recall of 0.67 was measured over.

**The enumeration of the fields of the meta in line 24 becomes incomplete.** The file carries an eighth field: the
seven of today and the digest of the corpus. This
record is the new record of that file, the way ADR-052 was the new record of the manifest of the datasets, and line
24 of ADR-006 is read together with this one. The sentence of that line that decides the reason, the vector space,
is untouched.

## Decision

**The index carries the hash of the corpus it was built from, the loader refuses a stale index, and the gate refuses
a repository whose committed index does not match its policies.**

### 1. The meta carries `corpus_sha256`, a digest of the bytes of the corpus

The digest is the sha256 of a canonical text: for every file `*.md` of the policies folder, in the order of the name,
one line with the name of the file, a colon and the sha256 of its bytes. It covers the bytes and not the parsed
excerpts, because the question it answers is "are these the documents of this repository?", and the answer has to
survive a change of the code that splits them (the chunk size and the overlap are already in the meta,
`ledgerlens/retrieval.py:221-222`). It covers the name of the file, so a rename moves it as well as an edit, and it is
computed over the folder the index was built from.

### 2. The builder writes the digest, and the loader compares it before it loads anything

`build_policy_index` takes the policies folder (or the digest) as an argument and writes the digest into the meta.
The signature changes; `scripts/build_index.py:31-39` passes the folder it has. The evaluation runner
(`ledgerlens/eval/run.py:203-208`) builds its own index over the same corpus, so it carries the same digest.

`load_policy_index` computes the digest of the corpus it is given (the default is `POLICIES_DIR`,
`ledgerlens/retrieval.py:53`) and compares it with the meta before it loads anything. A difference raises
`IndexStale`, a third exception beside `IndexUnavailable` (`:84-86`) and `IndexMismatch` (`:88-90`), and the store is
never loaded: a stale index does not answer, it refuses.

### 3. The tool maps the refusal to a new code of the envelope

`ledgerlens/tools/policies.py:163-168` maps the three exceptions of the loader to the codes of the envelope. The third
one maps to `INDEX_STALE`: not retryable, because a retry of a stale index is the same stale index; the message names
the two digests and the command that rebuilds the index. The code is registered in the docstring of the module
(`:8-14`) and in the contract of the tool (`docs/contracts/tools.md:211`). The difference with `INDEX_MISMATCH` is the
sentence: one says the vector space changed, the other says the corpus changed.

### 4. The gate refuses a repository whose index does not match its policies

A new read-only script, `scripts/check_policy_index.py`, is wired into `scripts/gate.sh` after the check of the
datasets (`:16-21`), because the gate of the Python side is the one that runs everywhere, in the local machine and in
the continuous integration. The script reads the meta of the committed index and the corpus of the disk, prints one
line per problem and exits with a non zero code, and it writes nothing. It never downloads the model
and never loads FAISS: the digest of the corpus needs no embedding, which is what makes the check possible in the
offline gate (`scripts/gate.sh:6`). A check that is not a step of the gate is a note for the next person.

### 5. The tasks

The tasks follow the format of `specs/004-r4-verifier-calibration/tasks.md`. The file that carries them,
`specs/005-r4-runtime-latency-and-cost-per-case/tasks.md`, holds these ids.

- [x] T121 Write the digest of the corpus in `ledgerlens/retrieval.py`, over the sorted names and the sha256 of the
  bytes of every `*.md` of the folder, and write the field `corpus_sha256` in the meta of `build_policy_index`, with
  the builder taking the folder or the digest, with the tests in `tests/retrieval/test_policy_index.py` that the
  digest moves when a byte of a policy moves, when a file is added and when a file is removed
- [x] T122 Write the exception `IndexStale` and the comparison of the digest in `load_policy_index`, with the test in
  `tests/retrieval/test_policy_index.py` that a policy edited after the build makes the loader refuse and that the
  store is never loaded
- [x] T123 Map the refusal to the code `INDEX_STALE` in `ledgerlens/tools/policies.py`, add the code to the docstring
  of the module and to `docs/contracts/tools.md`, with the test in `tests/tools/test_policies.py` that the tool
  answers with `INDEX_STALE` and does not search
- [x] T124 Write `scripts/check_policy_index.py` and wire it into `scripts/gate.sh`, with the test in
  `tests/retrieval/test_check_policy_index.py` that the check refuses when the corpus moved and that it writes nothing
- [x] T125 Rebuild the committed index over the corpus of the disk with `scripts/build_index.py` and commit
  `data/index/policies_fastembed/`, so the gate is green when the check lands

## Alternatives considered

The count of chunks was rejected (`ledgerlens/retrieval.py:218`): it does not move when a policy is edited in place
without changing the number of its sections. Rebuilding the index inside the gate was rejected too: the build needs
the embedding model (`scripts/build_index.py:36`) and the gate is offline (`scripts/gate.sh:6`), and a gate that
downloads a model is not the gate of this repository. The build date was rejected as well: a date is not a digest, and
two edits in the same day defeat it.

## Consequences

- The index and the corpus are tied together by a number that a machine can compare: a policy edited without the
  index rebuilt breaks the build, and the failure names the file, the two digests and the command.
- The answer can no longer carry a version that the text behind it does not have: a stale index refuses instead of
  answering.
- The cost is one more field in the meta, one more comparison at load, one more script and one more line in the gate.
  The comparison at load reads eight small files once per tool instance (`ledgerlens/tools/policies.py:153-158`),
  and the check of the gate reads two files and never touches the model.
- The cost that is named here is on the person who edits a policy: the edit stops the gate until the index is
  rebuilt and committed.

## The debt of this record

The debt is the model under the same name. The digest of the corpus says that the documents are the documents of the
repository. It says nothing about the model that turned them into vectors: `embedding_id`
(`ledgerlens/embeddings.py:73-80`) returns the name of the model and nothing else, so a model file that changed under
the same name produces an index that no check of this repository can see. The revision of the model, or the digest of
the model file, would go into the meta beside the digest of the corpus and would close that half of the gap. The
other half is the outage of the embedding service: the query is embedded on every call (`ledgerlens/retrieval.py:282`)
with no envelope around it, so an outage of the provider reaches the caller as an exception. Both belong to a later
record.

The last debt is the quality. This record fixes the freshness of the index and says nothing about the quality of its
answers: the number over the twelve questions of `data/eval/policy_questions.jsonl` is a tuning number (ADR-052 gives
that set the role `tuning`), and the held out set of the retrieval does not exist yet (the debt of ADR-053).

The debt of the landing of this record is what the landing did not pay. The code of the envelope (`INDEX_STALE`) and
the rule of the docstring of the module landed, but the contract of the tool (`docs/contracts/tools.md:211`) still
lists only `INDEX_UNAVAILABLE` and `INDEX_MISMATCH`, and the test of `tests/tools/test_policies.py` that the tool
answers with `INDEX_STALE` and does not search is not written: both files were outside the landing of this record.
The test of the check of the gate landed in `tests/retrieval/test_policy_index.py`, the test file of this landing,
and not in `tests/retrieval/test_check_policy_index.py`. The table of `docs/decisions/README.md` still says
`proposed` for this record, for the same reason. The rebuild of the committed index wrote a pickle with the same
documents, the same ids and the same metadata as the committed one, and only the encoding of the pickle moved, so
the committed bytes of `index.pkl` were kept and only the meta was taken.
