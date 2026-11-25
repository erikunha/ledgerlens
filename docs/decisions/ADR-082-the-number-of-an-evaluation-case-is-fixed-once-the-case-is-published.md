---
type: adr
status: accepted
date: 2026-11-24
---

# ADR-082: The number of an evaluation case is fixed once the case is published

Status: accepted. Date: 2026-11-24.

## Context

The evaluation names every case by its number, from EC-01 to EC-31, and the numbers are the identity of the case:
the report of the online run carries the score of each case by its number, the record of the answer key that changed
after that run names the six payouts by their number, and the memory of the case of a variant is keyed by it.

The numbers came from the place of the case in the list: the scenarios in the order of the manifest, then the natural
cases. The scenario S13 was added to the manifest, and the naive numbering moved every natural case by one: the six
payouts went from EC-19 to EC-20, the policy questions went from EC-25 to EC-26, and the published report of the
online run of the past would have named, for every case, a case it did not run.

The report is the record of a run that happened, with the set of cases that existed then. A number that moves makes
that record describe a set of cases that did not exist at the time of the run, and the reader who compares two runs
by the number of the case compares two different cases.

Two ways were open to the repository:

- **To renumber the cases and to rewrite the report.** Refused. The report of the past run would be rewritten to
  describe a run that did not happen, and the numbers a reader took from it would answer a different question.
- **To number the scenarios after the natural cases.** Refused for the same reason, and it moves the natural cases
  instead of the new one.

## Decision

**A case keeps the number it was published with. A case added later takes the next free number.**

1. **The twelve scenarios of the first version keep the numbers 1 to 12**, the natural cases keep the numbers 13 to 30,
   and the scenario S13 takes the number 31.
2. **The number is decided by the code, not by the position of the list.** `ledgerlens/eval/dataset.py` holds
   `PUBLISHED_SCENARIO_COUNT`, the number of scenarios that were published when the numbers were fixed, and
   `_case_ids` hands the numbers out: the scenarios that were there first take 1 to 12, the natural cases take 13 to
   30, and a scenario published later takes the next free number, after the last natural case.
3. **The file of the cases is in the order of the numbers**, so a reader who opens the file finds the case of a number
   where the number says.
4. **The report of the online run keeps the numbers of the run it recorded**, and the answer key that changed after
   that run keeps naming the same cases.

## Alternatives considered

- **To number the cases by their position in the list.** Refused. It is the rule that moved the numbers of the cases
  that were published, and it would move them again on the next scenario.
- **To leave the gap in the numbers.** Refused. A number that names nothing is a hole in the identity of the cases,
  and the file of the cases would have a gap that a reader has to explain.
- **To number the scenarios after the natural cases and to renumber the natural ones.** Refused, as above: the numbers
  of the published cases would move.

## Consequences

- **The published report of the online run stays true**, and the case it names is the case it ran.
- **A case added later takes the next free number**, and the numbers of the cases that came before it do not move.
- **The file of the cases is sorted by the number**, and the test that says so is in `tests/eval/test_dataset.py`.
- **The numbers of the cases are not consecutive when a scenario joins later**, and the reason is in the code that
  hands them out.

## Links

- [ADR-008, the evaluation design in LangSmith](ADR-008-evaluation-design.md)
- [the dataset of the evaluation](../../ledgerlens/eval/dataset.py)
- [the report of the online run](../../data/eval/report_online.json)
