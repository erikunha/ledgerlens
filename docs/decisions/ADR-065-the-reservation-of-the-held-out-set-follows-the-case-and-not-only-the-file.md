---
type: adr
status: accepted
date: 2026-11-23
---

# ADR-065: The reservation of the held out set follows the case and not only the file

Status: accepted. Date: 2026-11-23.

## Context

The guard of the tuning lives in `ledgerlens/eval/manifest.py`, and `require_tuning_path` is its door. The guard
refused a dataset by its name, a path that no entry of the manifest declared, a path whose role was not `tuning`, a
reserved path, a reserved digest of the bytes and a reserved digest of the records. The reservation of the held out
set lived in the code and not in the manifest, because the manifest is data and a hand edit of it is one line of JSON
away, and the role of an entry is exactly such a line.

The reservation had three doors that looked at the content of a file: the digest of the bytes, the digest of the
records and, for the paths themselves, the name. It was proved in a copy of the tree that a copy of the labelled set
under another name passes those doors, and the second round of the self review wrote that down.

The third door was the one that did not hold. The held out set is not a secret file: it is built from two files that
sit in the public tree, `data/eval/heldout/cases.jsonl` and `data/eval/heldout/labels_adjudicated.jsonl`. The first
carries the claim, the evidence, the ids of the evidence and the id of the case. The second carries the id of the
case and the label. Joining the two on the id produces 48 records, one per case of the set, and the shape of the
join is exactly the shape that the sweep consumes in `ledgerlens/verify/sweep.py`: a claim, an evidence, an id and a
label.

The join is a different file from the labelled set. The labelled set carries seven keys per record and the join
carries five, so the bytes are different and the records are different, and the digest of the records of the join is
not among the reserved digests. The exploit was run and it worked, in four steps:

1. The two files are joined into `data/eval/my_set.jsonl`, with 48 lines.
2. The manifest gets one entry with the path of that file and the role `tuning`.
3. `scripts/pin_calibration.py` prints the problems of the manifest and does not fail on them, and it pins the
   manifest again with the new entry.
4. `scripts/sweep_nli_thresholds.py` passes the guard and sweeps the thresholds over the set.

The consequence is the one that matters for the number: the thresholds are chosen against the held out set, and the
published 0,500 becomes a fit that still reads as a generalization.

What the three doors could not see is the case. A case is the unit the sweep reads, and a rebuild of the set carries
the cases of the set one by one, whatever the bytes of the file are and whatever the name of the file is.

## Decision

**The reservation of the held out set follows the case and not only the file. A reconstruction of the set from its
own sources is refused, and the doors of the reservation are four: the path, the digest of the bytes, the digest of
the records and the digest of the case.**

### The four doors

| the door | what it compares | what it stops |
| --- | --- | --- |
| the path | the path of the file against `HELD_OUT_RESERVED_PATHS` | a file that is renamed to a name that is not reserved, if the manifest declares it |
| the digest of the bytes | the bytes of the file on the disk against `HELD_OUT_RESERVED_DIGESTS` | a copy of the set or of the key under another name, with the same bytes |
| the digest of the records | the records of the file on the disk against `HELD_OUT_RESERVED_RECORD_DIGESTS` | a copy of the set with a newline at the end, with the same records and other bytes |
| the digest of the case | the cases of the file on the disk against `HELD_OUT_RESERVED_CASE_DIGESTS` | a rebuild of the set from its own sources, with other bytes, other records and the same cases |

The fourth door is the one that closes the hole, and the reason is the shape of the exploit. A rebuild that alters
one record still carries the other 47 cases of the set, and a rebuild that carries the labels of the generator
instead of the adjudicated labels still carries the 46 cases on which the two variants agree. A file has to hold
not one case of the set to be refused, and a rebuild of the set holds all of them.

### The case and its projection

The canonical form of a case is the projection that the sweep consumes:

```json
{"claim": ..., "evidence": ..., "evidence_ids": ..., "id": ..., "label": ...}
```

serialised with `json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` and hashed with sha256.
The projection is what makes the two comparable: the labelled set carries seven keys per record and the rebuild
carries five, so the bytes and the records of the two differ, while the projection of the labelled set and the
projection of the join are equal, case by case. The digest of a case is the same for the same case under any name,
in any order and in any file.

The constant that holds the digests is `HELD_OUT_RESERVED_CASE_DIGESTS`, and the function that computes one is
`case_digest` in `ledgerlens/eval/manifest.py`. The door is in `require_tuning_path`, and it reads the file on the
disk when the caller gives the root, because the declaration of the manifest can be a lie and the cases of the file
are the truth.

### Fifty digests, and why the union of the two variants of the labels

The reservation holds the digests of the cases of two label variants, and the union of the two:

- the labels of `data/eval/heldout/labels_adjudicated.jsonl`, the labels of the adjudicated reading;
- the labels of `data/eval/heldout/recipes.jsonl`, the labels of the generator that wrote the set.

The two variants differ on 2 of the 48 cases, so the union holds 50 distinct digests. A reservation that held only
the adjudicated labels would miss a file built with the labels of the key, and the key is the file that anybody can
rebuild, because the generator is public and deterministic. The count is fifty and it is checked by a test, so that
a constant that loses one digest says so instead of refusing a rebuild without a reason.

### The sources of the set are reserved as well

The files the set can be rebuilt from are reserved by their path, by their bytes and by their records:
`data/eval/heldout/cases.jsonl`, `data/eval/heldout/labels_adjudicated.jsonl`,
`data/eval/heldout/labels_reader_a.jsonl` and `data/eval/heldout/labels_reader_b.jsonl`, next to the labelled set
and next to the answer key of the generator. A copy of the cases is a copy of the half of the set that carries the
claims, and the half was a hole of its own.

The scan of the source of the scripts sees the same files. `MARKERS_OF_A_HELD_OUT_FILE` in
`tests/eval/test_tuning_guard.py` names them, and a script that names one of them has to be the instrument of the
reading or the measurement of the programme, the two scripts that are allowed to read the set. No other script of
`scripts/` names one of them.

### The scan of the folder of the sources

The scan for an undeclared JSONL file looked at the files that sit directly in `data/eval/`, and a file in the
folder below it was outside the scan. The scan looks into `data/eval/heldout/` now, so a file that nobody declares
in that folder is a problem that the check says out loud. The sources of the set are not datasets and the code
reserves them, so the scan knows them and does not report them, and the check of the datasets stays green on a tree
that is correct.

### The sentences that are superseded

| the record | the sentence | what it becomes |
| --- | --- | --- |
| [ADR-062](ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md) `:53` | "The answer key is not published, and the guard refuses it by path" | The answer key is not published, and the guard refuses it by the path, by the bytes, by the records and by the cases |
| [ADR-062](ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md) `:69-70` | "It is refused by its path and not by a role, because the answer key has no role: it is not a dataset of the repository." | It is refused by its path and by its content, and not by a role, because the answer key has no role: it is not a dataset of the repository. The path is not the only way a file reaches a tuning script. |
| [ADR-052](ADR-052-the-manifest-of-the-eval-datasets.md) `:139` | "a tuning script that reads it has to fail" | A tuning script that reads it has to fail, and the refusal holds whatever the manifest declares, whatever the name of the file is and whatever the bytes of the file are |

The decision of ADR-052 stands: the manifest is the single source of what the datasets are, the roles are the three
that it named, and the role of a dataset is decided by evidence with the conservative role winning when the evidence
is not clean. What this record adds is the fourth door of the reservation, and the reservation was not the decision
of ADR-052: it was a property of the code that the decision of ADR-052 produced.

### The number that is not a fit only means something while the set is untuned

The number over the held out set is 24 of 48, 0,500, and it is the only number of this repository that is not a
measurement of the fit. That sentence is true only while the set is untuned. A threshold that was chosen over the
set turns the number into a measurement of the fit, and no amount of care with the words of the number brings it
back. The guard is what keeps the sentence true, and the fourth door is what keeps the guard true against a
rebuild of the set.

### The accepted records are not rewritten

ADR-052, ADR-062 and every other accepted record of this repository keep their sentences. An accepted record is not
edited: a change of an accepted decision is a new record (`AGENTS.md:20`). The sentences that the world made false
are named in the table above, and the new record says what is true in the present tense.

## Alternatives considered

- **To refuse the sources of the set by their path only.** Refused. A path names a file and a copy of the file under
  another name has another path, and the whole point of the third door was that the reservation by path stops at the
  name.
- **To reserve the digest of the file of the join, the one the exploit produced.** Refused. The join is not one file:
  it is one file per way of joining, and a reservation of one digest of it is a reservation of that cheat and not of
  the hole. The cases are the thing that does not change.
- **To reserve the digests of the cases of the labelled set only.** Refused. The labels of the generator differ from
  the adjudicated labels in two of the forty eight cases, and a rebuild with the labels of the key would carry 46
  cases of the set and the two that are not. The union of the two variants is the reservation.
- **To compute the case digests on the disk at every call and keep no constant.** Refused. A reservation that is
  computed from the disk is a reservation that moves with the disk, and a disk that moved is exactly what the
  reservation is there to catch. The constant is code that a reader reviews, and a test says that it still matches
  the files.
- **To refuse a file that holds any case of the set, without the root.** Refused. Without the root the guard has no
  file to read, and the declaration of the manifest is not the truth. The doors of the bytes, of the records and of
  the cases need the root, and the callers of the sweep know it.
- **To delete the sources of the set from the tree.** Refused, and it is out of the question anyway: the cases are
  the published content of the set, and the labels are the published content of the reading. The repository needs
  them to publish what it published, and it needs the reservation to keep them out of a tuning.
- **To leave the exploit open and to write it down.** Refused. A hole that is proven and published is a hole that is
  used.

## Consequences

- **The exploit is closed.** The rebuild of the set from its own sources is refused with a sentence: "The file
  'data/eval/my_set.jsonl' holds a case of the held out set, so it may not be tuned against under any name and with
  any role: only the datasets with the role 'tuning' may be tuned against."
- **The number over the held out set does not change.** It stays 24 of 48, 0,500, and it is still the only number of
  the repository that is not a measurement of the fit.
- **The reservation is bigger.** It holds the paths, the digests of the bytes, the digests of the records and the
  digests of the cases of the set and of its sources, and every one of them has to move with the files it names.
- **The scan of the folder of the sources is a door of its own.** A file that nobody declares in
  `data/eval/heldout/` is a problem that the check of the datasets says out loud.
- **The scan of the source of the scripts is a door of its own.** A script that names a source of the set is a
  script that may rebuild it, and the list of the scripts that may is closed.
- **The debt of this record is the same as the debt of ADR-062.** The set was read by machine readers and the
  repository cannot prove that they were blind, and the next reading has to be a human one.

## Links

- [ADR-052, the manifest of the eval datasets](ADR-052-the-manifest-of-the-eval-datasets.md)
- [ADR-062, the role held out exists](ADR-062-the-role-held-out-exists-and-the-sentence-of-adr-052-is-superseded.md)
- [ADR-064, the sentences that assert the blindness of the reading as a fact are superseded](ADR-064-the-sentences-that-assert-the-blindness-of-the-reading-as-a-fact-are-superseded.md)
- [the guard of the tuning](../../ledgerlens/eval/manifest.py)
- [the provenance of the reading](../../data/eval/heldout/provenance.md)
