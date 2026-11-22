---
type: adr
status: accepted
date: 2026-11-22
---

# ADR-045: The ledger of the recorded demo is a published artifact of the site

Status: accepted. Date: 2026-11-22.

## Context

The home page of the site says, in its own words, that LedgerLens shows the evidence behind every
answer: "the ledger rows it read, the policy it applied and the arithmetic it did". Two of the three
are on the site today. The policy is in the tab of the evidence, the piece by piece, with the chunk
the run retrieved. The arithmetic is in the tab of the decision, with the decimal text of the
calculation and the currency the run read. **The ledger rows are not on the site at all.** The
evidence card of the citation `sql:1` shows the SQL of the query and nothing else: the rows the
query returned are inside the recording and inside the recording only.

The plan of the release R1 asked for the table of the ledger, the account switcher and the detail of
a row, in the tasks T063 to T070 of `specs/001-r1-public-replay/tasks.md`, and it was never built.
ADR-043 named the whole group as the debt of the next milestone, with the warning that a table of
a thousand rows needs its own artifact and its own account switcher, and ADR-044 repeated the
warning when it deferred the panel of the ledger of the branch of the sandbox, because "the
ledger of a branch is a table of a thousand rows".

This ADR is the decision of that milestone. It decides what the artifact of the ledger is, who
writes it, how the gate pins it, how the browser reads it and what it does not deliver.

The facts of the repository decide the shape, and every fact below was measured, not assumed.

**The recording reads the ledger exactly once.** The bundle `data/eval/replay/s01/` holds 57 events
and one single call of the tool `query_ledger`. The call is the span of the sequence number 19, its
output carries the citation `sql:1`, and the statement it ran is:

```sql
SELECT * FROM (SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at) LIMIT 50
```

The result carries two rows and says so: `row_count` is 2 and `truncated` is `false`. The two rows
are the rate of the charge and the rate of the refund of the transaction `TX-2048`, and the columns
the run asked for are `kind`, `applied_rate` and `applied_at`:

| kind | applied_rate | applied_at |
| --- | --- | --- |
| charge | 5.6679 | 2026-10-15T09:12:04Z |
| refund | 5.4931 | 2026-10-20T14:30:00Z |

**The account of the recording is `C-0412`, and the recording names it in words.** The note of the
manifest says: "Deterministic execution of the scenario S01, account C-0412, with the scripted model
and the recorded exchange rate." The public dataset `data/scenarios.json` says the same, with the
customer `C-0412` and the transaction `TX-2048`. The events themselves never name the account: the
identifier `C-0412` appears zero times in the 57 events, and the identifier `M-17` of the merchant
appears zero times as well. The transaction `TX-2048` appears 47 times.

**The ledger of that account is frozen with the recording, and the bundle pins it by digest.** The
capture of `scripts/capture_replay.py` runs the agent against the ledger of the account alone, the
file `account.db` that `scoped_ledger` of `ledgerlens/api/accounts.py` writes, and the manifest
declares the sha256 of that file as its `snapshot_sha256`. Rebuilding the very same ledger today
reproduces the file byte for byte, and the digest is the one the bundle declares:

```
26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f
```

That ledger of the account holds one merchant, one customer, one transaction, one refund, two
rates, no chargeback, no settlement and eight events. The movements of the account are two rows:

| kind | id | at | amount | currency | status |
| --- | --- | --- | --- | --- | --- |
| transaction | TX-2048 | 2026-10-15T09:12:00Z | 100.00 | EUR | refunded |
| refund | R-0731 | 2026-10-20T14:05:00Z | 549.31 | BRL | paid |

**The full ledger of the simulator is a different thing, and it is much bigger.** The base ledger
holds 24 merchants, 1418 customers, 2114 transactions, 1934 rates, 359 refunds, 10 chargebacks,
286 settlements and 8911 events: 2483 movements over 1442 accounts. The recording read NONE of
them, except the ledger of the account of the scenario. The account of the merchant of the
scenario, `M-17`, holds 73 transactions on its own.

**The row of a ledger in this repository already has a shape.** The branch layer writes the rows of
the ledger of a branch in `_ledger_items` of `ledgerlens/sandbox/branch.py`, and the row carries a
kind, an identifier, a moment, an amount as a decimal text, a currency and a status. The amount is
never a float: `format_minor` of `ledgerlens/sandbox/mutation.py` turns the minor units into a
decimal text. That shape is the contract between the ledger of the recorded demo and the ledger of
the branch of the sandbox, and the milestone keeps it.

**The site is a static export and the artifacts have ONE source of truth.** ADR-042 decided that
the folder `site/replay/` is published by the export of the repository and that the build of the
frontend copies it into `apps/web/public/replay/`, so that there is never a second copy in the
history of the tree. ADR-043 decided the rules of the reader of the replay: the state of the visit
lives in the URL with a closed allow list, the money of the interface is the decimal text of the
artifact, the browser never calculates a value, the outline of the headings never skips a level,
the controls are never `disabled`, the state is never only a colour and the `aria-current` sits on
the row.

**The bundle is sealed.** `load_bundle` of `ledgerlens/replay/bundle.py` refuses a folder that holds
a file the manifest does not declare, and the digest of the bundle is the sha256 of the manifest.
The artifact of the ledger therefore cannot live inside the bundle, and adding it cannot move the
digest of the bundle.

## Decision

**The rows the run read are published as an artifact of the site, next to the recording, and they
are read by the browser from the published artifacts like every other artifact. The browser never
calls anybody for them.**

**The artifact is the ledger of the account of the recording, with the reads of the recording
marked in it. It is published per scenario, it is frozen with the recording, and the gate pins its
digest.**

**The ledger is a fifth tab of the replay, between the tab of the execution and the tab of the
evidence, and the state of the visitor in it (the account that is chosen and the row that is open)
never goes in the URL.**

**The money of the ledger is the decimal text of the artifact. The browser never sums it, never
rounds it and never converts it. The rate that the run read is not money and never wears the
currency of the run.**

### The artifact

#### The file and its place

The published file is `site/replay/s01/ledger.json`, inside the folder of the scenario, beside the
events, the manifest and the provenance. The name of the file is `ledger.json`, and it is the
name of the constant `LEDGER_FILE` of the module that owns the artifact.

The frozen source of the published file is `data/eval/replay/ledger/s01.json`: it lives beside the
folder of the bundle, OUTSIDE the sealed bundle, and it is committed with it. It is written by the
producer of the artifact and it never changes once it is written, exactly like the bundle.

**The artifact stays outside the bundle, and the reason is the seal.** `load_bundle` refuses any
file of the folder of a bundle that the manifest does not declare, so a file of the ledger inside
`data/eval/replay/s01/` would make the bundle unreadable. The artifact is therefore a file beside
the bundle, and the export of the site copies it into the folder of the scenario.

**The digest of the bundle does not move.** The digest of the bundle is the sha256 of the manifest,
and the manifest of the bundle is not touched by this milestone: the artifact is not a file of the
bundle, the manifest declares no file of the ledger, and the events are not rewritten. The
published provenance gains the digest of the artifact under its own name and the card of the
catalog gains the digest of the artifact under its own name, and nothing else moves.

#### The shape of the artifact

The artifact is one JSON document, written with the format the repository uses everywhere (sorted
keys, two spaces, a final line), and it carries:

```json
{
  "schema_version": "1",
  "scenario": "S01",
  "snapshot_sha256": "26849ada6f60c63fa30a0b085fd1ff473508d18a5892498cade13b7dc436ee2f",
  "page_size": 50,
  "accounts": [
    {
      "id": "C-0412",
      "kind": "customer",
      "name": "Mariana Albuquerque Costa",
      "rows": [
        {
          "kind": "transaction",
          "id": "TX-2048",
          "at": "2026-10-15T09:12:00Z",
          "amount": "100.00",
          "currency": "EUR",
          "status": "refunded"
        },
        {
          "kind": "refund",
          "id": "R-0731",
          "at": "2026-10-20T14:05:00Z",
          "amount": "549.31",
          "currency": "BRL",
          "status": "paid"
        }
      ],
      "reads": [
        {
          "evidence_id": "sql:1",
          "seq": 19,
          "tool": "query_ledger",
          "sql": "SELECT * FROM (SELECT kind, applied_rate, applied_at FROM fx_applied WHERE transaction_id = 'TX-2048' ORDER BY applied_at) LIMIT 50",
          "columns": ["kind", "applied_rate", "applied_at"],
          "row_count": 2,
          "truncated": false,
          "records": ["TX-2048"],
          "rows": [
            { "kind": "charge", "applied_rate": "5.6679", "applied_at": "2026-10-15T09:12:04Z" },
            { "kind": "refund", "applied_rate": "5.4931", "applied_at": "2026-10-20T14:30:00Z" }
          ]
        }
      ]
    }
  ]
}
```

The rules of the shape:

- **`rows` are the movements of the account, in the shape of the ledger of the branch.** The fields
  are `kind`, `id`, `at`, `amount`, `currency` and `status`, the same six fields and the same
  meaning as `_ledger_items` of `ledgerlens/sandbox/branch.py`, so that one table can render the
  ledger of the recorded demo and the ledger of the branch of the sandbox. The `kind` is one of
  `transaction`, `refund` and `chargeback`. The order is the order of the ledger: oldest first.
- **`amount` is the decimal text of the ledger, never a number.** The amount of the transaction is
  the text `100.00` and the amount of the refund is the text `549.31`, written by `format_minor` of
  the core. The browser never sees a float of money.
- **`reads` are the reads of the ledger that the recording holds.** One read per call of the tool
  `query_ledger` that the recording made. A read carries the citation of the evidence
  (`evidence_id`), the sequence number of the event that closed it (`seq`), the name of the tool,
  the statement it ran, the names of the columns it asked for, the number of rows it returned, the
  flag that says whether the result was cut, the identifiers of the records it named, and the rows
  themselves.
- **`records` are the identifiers the statement named.** The producer finds them in the text of the
  statement, so a read that named nothing publishes an empty list and never an invented one. For
  the recording of `S01` it is the single identifier `TX-2048`.
- **The rows of a read keep the values the recording wrote and take the names of the columns the
  recording declared.** The recorded row is the positional list
  `["charge", "5.6679", "2026-10-15T09:12:04Z"]` and the recorded columns are
  `["kind", "applied_rate", "applied_at"]`; the artifact names the values with the columns, in the
  order the recording declared, and it never invents a column, never reorders a value and never
  repairs one.
- **`snapshot_sha256` is the digest of the ledger the recording read.** It is the digest the
  manifest of the bundle declares, and it is the claim of identity between the artifact and the
  recording. It answers, for the ledger, the question that ADR-043 left open: the export now
  publishes the hash of the ledger that the run read.
- **`page_size` is the number of rows of a page.** It is 50, the same number as the page of the
  ledger of the branch (`LEDGER_PAGE_SIZE` of `ledgerlens/sandbox/branch.py`) and the same number
  as the limit the recorded statement carried, so that the two ledgers are paged the same way.
- **`accounts` is a list, even when it holds one account.** The artifact of a recording that read
  the ledger of one account holds that account and no other, and the format is a list because a
  recording that read many accounts publishes many accounts. The switcher of the accounts reads
  this list and nothing else.

#### The rows and how many

For the recording the site publishes today:

- **the account**: one, `C-0412`, of the kind `customer`, the name of the simulated customer.
- **the movements**: two rows, the transaction `TX-2048` and the refund `R-0731`, with the decimal
  texts `100.00` EUR and `549.31` BRL.
- **the reads**: one, the call of `query_ledger` of the sequence number 19, with the citation
  `sql:1`, and with two rows, the rate of the charge `5.6679` and the rate of the refund `5.4931`.

So the table of the ledger of the account shows **two rows**, and the detail of the transaction
shows **the two rows the run read**. Those four rows are the whole truth of the recording: the run
read two rows of the ledger of the account `C-0412`, and the account holds two movements.

**The rows that the run read are the rates, and the movements are the ledger.** The recording read
the rates of the transaction `TX-2048` and nothing else: it never asked for the transaction and
never asked for the refund. The artifact publishes both, because they are two different facts: the
movements of the account, and the rows the run read. The interface says which is which in words,
and the rule is fixed: **the table shows the movements of the account, and a movement that a read
names carries the words "Read by the run"**. A movement that no read names carries no mark, and the
detail of it says that the recording read no record of it.

#### Per scenario and not once for the site

**The artifact is published per scenario, inside the folder of the scenario, and not once for the
site.** Three reasons:

- The rows belong to the recording of one scenario and to the ledger of one account. A single file
  for the whole site would mix the accounts of twelve scenarios and would publish rows that no
  recording read.
- The bundle is per scenario and the digest of the bundle is per scenario. An artifact that sits
  beside the bundles of the site has no bundle to answer for.
- The export already publishes a folder per scenario and one index that lists them. The artifact
  follows the rule of the export and the rule of the frontend, which reads the folder of the
  scenario of the card.

#### The sha256 that the gate pins

The gate pins **the sha256 of the published file** `site/replay/s01/ledger.json`. The digest is
declared in two places of the published artifacts, under names of their own:

- in the provenance of the scenario, under `artifacts`, with the key `ledger.json`;
- in the card of the catalog, with the key `ledger_sha256`.

The three digests of the published scenario are therefore a chain, and every link of it is
checked: the digest of the file of the events is the digest the manifest declares, the digest of
the file of the ledger is the digest the provenance declares, and the digest of the provenance file
is the digest the card of the catalog declares. The browser checks the same chain with the Web
Crypto, and the panel of the ledger says out loud that the integrity was not checked when the
browser offered no Web Crypto.

The digest of the file is not written in this ADR because the file does not exist yet: it is
computed when the producer writes the artifact and the export publishes it, and it is pinned in
the table of the pinned digests of `tests/replay/test_site_export.py`, where the digests of every
published file live today.

### The Python side

#### The module that owns the artifact

The module that owns the artifact is `ledgerlens/replay/ledger_artifact.py`, new. It lives with the
bundle and the export, because the artifact is a thing of the recorded demo and not a thing of the
interface. It carries a docstring that says what it does and why, in the style of the repository,
and it declares its surface in an `__all__`.

Its surface is:

```python
LEDGER_FILE = "ledger.json"
LEDGER_SCHEMA_VERSION = "1"
LEDGER_PAGE_SIZE = 50
ACCOUNT_PATTERN = re.compile(r"^[CM]-[0-9]+$")


class LedgerArtifactError(Exception):
    """The artifact cannot be built or does not hold up."""


def build_ledger_artifact(bundle_dir: Path, ledger_db: Path) -> dict[str, Any]: ...
def ledger_artifact_bytes(artifact: dict[str, Any]) -> bytes: ...
def write_ledger_artifact(path: Path, artifact: dict[str, Any]) -> Path: ...
def read_ledger_artifact(path: Path) -> dict[str, Any]: ...
def check_ledger_artifact(bundle_dir: Path, path: Path) -> list[str]: ...
def ledger_reads_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
```

The rules of the module:

- **`build_ledger_artifact` is the function that builds the artifact, and `write_ledger_artifact` is
  the function that writes it.** The builder takes the folder of the bundle and the file of the
  ledger of the account, it reads the movements out of the ledger with the same rule the branch
  layer uses (`_ledger_items` of `ledgerlens/sandbox/branch.py`, so that the shape of the row is
  written in one place), it reads the reads out of the recorded events with
  `ledger_reads_from_events`, it reads the account out of the note of the manifest, and it returns
  the artifact as a dictionary. The writer takes the artifact and the path of the file and puts
  the bytes of the artifact on the disk.
- **The account comes from the recording, and the recording has to name it.** The note of the
  manifest is the place where the capture names the account it ran against, and the producer reads
  the identifier with the pattern `ACCOUNT_PATTERN`. A bundle whose note names no account is
  refused: an artifact without an account is a table without a subject.
- **The kind of the account comes from the core, not from a second spelling.** The producer uses
  `account_kind` of `ledgerlens/api/accounts.py`, which is the ONE place that knows the shape of
  an account identifier, and it never declares a pattern of its own for it.
- **`ledger_reads_from_events` is a projection and never a decision.** It reads the events whose
  payload names the tool `query_ledger`, it takes the data of the output, and it publishes the
  citation, the sequence number, the statement, the columns, the number of rows, the flag of the
  cut and the rows. It never fills a gap and never repairs a value: a read whose output carries
  no rows is published with no rows.
- **`ledger_artifact_bytes` writes the same bytes every time.** The format is the one of the
  repository: sorted keys, two spaces, a final line. The artifact is a pure function of the ledger
  and of the recording.
- **`check_ledger_artifact` is the function that checks it.** It compares the file on the disk with
  the artifact that the bundle and the ledger would produce, one line per difference, and it never
  writes anything.

#### The producer

The producer is `scripts/build_ledger_artifact.py`, new. It is the only command that writes the
frozen file `data/eval/replay/ledger/<slug>.json`, and it runs offline, with no key and with no
network.

What it does, in this order:

1. It opens the bundle with `load_bundle` of the core, so the hashes, the secret and the order of
   the events are checked before anything is written.
2. It rebuilds the ledger of the account, the same way the capture did: the base ledger with
   `build_ledger` of `ledgerlens/sim/pipeline.py` and `SimConfig(source="sample")`, and then the
   ledger of the account with `scoped_ledger` of `ledgerlens/api/accounts.py`.
3. **It proves that the ledger it rebuilt is the ledger the recording read.** The sha256 of the
   file of the ledger has to be the `snapshot_sha256` that the manifest of the bundle declares. A
   digest that differs is a refusal with a readable reason, and nothing is written.
4. It builds the artifact with `build_ledger_artifact` and writes it with `write_ledger_artifact`.

The command takes the folder of the bundle and the folder of the output, and it defaults to the
canonical bundle of `data/eval/replay/` and to `data/eval/replay/ledger/`. The exit code is 0 when
the artifact was written and 1 when it was refused.

**The capture is not edited.** The capture of `scripts/capture_replay.py` stays as it is, and the
artifact is produced by the producer, after the capture. The reason is the seal and the
immutability: the recording is frozen and names the commit it was made from, and a command that
rewrites one of the two halves of the milestone would put the other half in doubt. The export
refuses when the artifact of a scenario is missing or when it belongs to another recording, so a
capture without a producer is a red gate and not a silent hole.

#### The export

`ledgerlens/replay/site_export.py` is changed, and only in the export of the scenario.

- **The export reads the frozen artifact of the scenario** and refuses the scenario when the
  artifact does not hold up. The two refusals are: the artifact declares a `snapshot_sha256` that
  is not the digest the bundle declares (the artifact belongs to another recording), and the note
  of the bundle names an account while the artifact is missing (the recording owes the site the
  ledger of that account). The refusal is an `ExportError`, never a traceback, and it names the
  scenario and the reason.
- **The export writes the file** `site/replay/<slug>/ledger.json` with the bytes of the frozen
  artifact, byte for byte. The file joins `SCENARIO_ARTIFACT_NAMES`, so the write of the export
  removes it when the scenario leaves the set, and it is never the file of somebody else.
- **The export declares the digest of the file** in the provenance of the scenario, under
  `artifacts`, with the key `ledger.json`, and in the card of the catalog, with the key
  `ledger_sha256`. The card declares it only when the scenario published the file.
- **The export is still a pure function of its inputs.** The inputs are the bundle, the public
  dataset and the frozen artifact of the scenario, and every timestamp comes from the manifest of
  the bundle. Running the export twice leaves the same bytes on the disk.

The contract of the export, in one table:

| | |
| --- | --- |
| The file it publishes | `site/replay/<slug>/ledger.json` |
| Where it reads it from | `data/eval/replay/ledger/<slug>.json`, beside the folder of the bundle |
| What it declares | `artifacts["ledger.json"]` in the provenance, `ledger_sha256` in the card |
| What it refuses | an artifact whose `snapshot_sha256` is not the digest of the bundle, and a bundle that names an account and has no artifact |
| What it never touches | the manifest of the bundle, the events, the digest of the bundle |

#### The check in `scripts/gate.sh`

**The check of the artifact is the step that already exists, and no new step is needed.** The gate
of the Python of the repository runs, after the tests offline:

```bash
echo "== export check (offline)"
uv run python scripts/export_replay_site.py --check
```

That step calls `check_export`, which compares every file the export declares with the file on the
disk and reports every file that is on the disk and is not declared. The file of the ledger is one
of the declared files, so the step compares `site/replay/s01/ledger.json` with the bytes the export
would write, and it fails with the name of the file when they differ. A frozen artifact that was
edited without publishing it fails the same step, and a published file that was edited by hand
fails it too.

**The second half of the chain is checked by `scripts/verify_replay_digests.py`**, the cross check
of the artifacts that the site publishes against the canonical bundle of the repository. The gate
of the repository runs it in a step of its own, and the test suite drives the same script the same
way the gate does, so the check is proved in both places. This milestone teaches it the file of
the ledger: it compares the published file with the frozen file byte for byte, it checks that the
provenance publishes the digest of the file that is really on the disk, and it checks that the
card of the catalog publishes the digest of the provenance. The rule that no file is published
beside the ones the export accounts for stays, and the file of the ledger is one of the files the
export accounts for.

**The third half of the chain is checked by the test**, the one that proves the artifact matches
what the run read. The export can prove that the published file is the frozen file, and the frozen
file can prove that it is the ledger of the recording by the digest of the snapshot, but only the
test can prove that the rows of the artifact are the rows of the recorded events, because that is a
comparison between the artifact and the events.

#### The test that proves the artifact matches what the run read

The test is `tests/replay/test_ledger_artifact.py`, new, and it runs with no key and with no
network.

What it proves, against the canonical bundle of the repository:

- **The reads of the artifact are the reads of the recording.** The test reads the 57 events of
  `data/eval/replay/s01/events.jsonl`, projects them with `ledger_reads_from_events`, and asserts
  that the reads of the artifact are those reads, field by field: the citation `sql:1`, the
  sequence number 19, the statement, the three columns, the number of rows 2, the flag of the cut
  and the two rows with their values.
- **No row of the artifact is a row the run did not read.** The rows of the reads of the artifact
  are compared with the rows of the recorded event, and the comparison is exact, in both
  directions.
- **The movements of the artifact are the movements of the ledger of the account**, with the
  decimal texts `100.00` and `549.31`, and the identifiers `TX-2048` and `R-0731`.
- **The identity of the artifact with the recording holds**: the `snapshot_sha256` of the artifact
  is the digest the manifest of the bundle declares, and the account of the artifact is the account
  the note of the bundle names.
- **The artifact is refused when it belongs to another recording**, and the refusal names the two
  digests that differ.
- **The artifact is written and read back byte for byte**, and `check_ledger_artifact` finds the
  difference when the file on the disk is not the one the bundle and the ledger would produce.

The test that the export publishes the file, that it declares the digest of the file in the
provenance and in the card, and that it refuses the two cases above, lives in
`tests/replay/test_site_export.py`, which is changed by this milestone because it pins the set of
the published files and the digest of each one of them.

### The front

#### The tab

**The ledger is the fifth tab of the replay, and it sits between the tab of the execution and the
tab of the evidence.** The order of the tabs is `execution`, `ledger`, `evidence`, `decision`,
`provenance`.

The reasons:

- The home page promises three things, the ledger rows, the policy and the arithmetic. Two of them
  have their own place today: the policy in the tab of the evidence, the arithmetic in the tab of
  the decision. The third one deserves a place of its own, and a table with a pagination, a
  switcher and a detail does not fit under the panel of the answer.
- The order follows the order of the promise and the order of the work of the run: the reader sees
  what the run did (the execution), then the rows it read (the ledger), then what it gathered
  (the evidence), then what it concluded (the decision), and then the proof of the recording (the
  provenance).
- The tab is a view of the DATA the recording read, and the four tabs of ADR-043 describe the
  recording, its evidence, its decision and its proof. The allow list of the URL grows by exactly
  one value, `ledger`, and it stays closed: the query string carries `tab` and `speed` and nothing
  else, exactly as ADR-043 decided.

The route does not change. The ledger is a tab of the route of the scenario, and its address is
`/replay/scenario/S01?tab=ledger`.

The outline of the headings of the new tab never skips a level: the route carries the `h1` of the
page and the `h2` of the scenario, the tab carries the `h3` of its section, the panel of the
ledger carries the `h4`, the detail of a row carries the `h5`. It is the same shape as the other
four tabs.

#### The components and their props

The components live in `apps/web/features/ledger/`, and every one of them carries a docstring in
English that says what it does and why, and a complete `__all__`.

**`LedgerPanel`, the panel of the tab.** It owns the state of the visitor: the account that is
chosen and the row that is open. Neither of them goes in the URL.

```ts
export interface LedgerPanelProps {
  /** The artifact of the ledger of the scenario, when the site published one. */
  readonly ledger: LedgerArtifact | null;
  /** The reason the artifact could not be read, when it could not be read. */
  readonly error: string | null;
  /** Whether the integrity of the file of the ledger was really checked. */
  readonly integrity?: BundleIntegrity | null;
}
```

**The third prop came from the verifier of the milestone.** The record asks the panel to say out loud that
the integrity was not checked when the browser offered no Web Crypto, and the two props above had no
place to carry that fact: the panel would have had to invent it or stay silent. The prop carries the
answer of the reader of the artifacts, the panel draws the sentence, and no other place can forget it.

Its rules: it draws the switcher of the accounts, the table of the movements and the detail of the
row that is open; it says in words how many rows the recording read; it shows the reason when the
artifact is not available, and it shows nothing else, because a half drawn ledger is worse than no
ledger; and it never reads the network.

**`LedgerTable`, the table of the movements.** It draws the rows of the account with the table of
the design system, `Table` of `apps/web/components/ui/Table.tsx`, and it never reorders them: the
order the visitor sees is the order the artifact declares.

```ts
export interface LedgerTableProps {
  /** The movements of the account, in the order of the artifact. */
  readonly rows: readonly LedgerRow[];
  /** The reads of the recording, so that the table can mark the rows the run read. */
  readonly reads: readonly LedgerRead[];
  /** The identifier of the row that is open, when a row is open. */
  readonly openRowId: string | null;
  /** Called when the visitor opens a row, or closes it with null. */
  readonly onOpenRow: (rowId: string | null) => void;
  /** The number of rows of a page, the number the artifact declares. */
  readonly pageSize: number;
  /** The page that is on the screen, counting from zero. */
  readonly page: number;
  /** Called when the visitor asks for another page. */
  readonly onPageChange: (page: number) => void;
}
```

Its rules: the caption names the table and it is the accessible name of the table; the first
column is the row header (`th` with `scope="row"`), as the table of the design system does; the
row that is open carries `aria-current="true"` through the callback `rowAttributes` of the table,
and the attribute sits on the row and not on a cell; a movement that a read names carries the words
"Read by the run" in its cell, because the state is never only a colour; the amount is written
with `formatMoney` of `apps/web/lib/format/money.ts`, with the currency of the artifact, and the
browser never sums the column and never shows a total.

**`LedgerRowDetail`, the detail of the row that is open.** It draws the row that is open and the
reads of the recording that name it.

```ts
export interface LedgerRowDetailProps {
  /** The movement that is open. */
  readonly row: LedgerRow;
  /** The reads of the recording, so that the panel can show the ones that name the row. */
  readonly reads: readonly LedgerRead[];
}
```

Its rules: it draws the six fields of the row, one by one, with the names the artifact gives them;
it draws the reads that name the row, with the citation, the sequence number of the event, the
statement and the rows of the read; and it says in words that the recording read no record of the
row when no read names it. It never calculates a value and it never shows a total.

**`AccountSwitcher`, the switcher of the accounts.** It switches the account whose movements are on
the screen.

```ts
export interface AccountSwitcherProps {
  /** The accounts the artifact publishes. */
  readonly accounts: readonly LedgerAccount[];
  /** The account that is on the screen. */
  readonly selectedAccountId: string;
  /** Called when the visitor chooses another account. */
  readonly onSelectAccount: (accountId: string) => void;
}
```

Its rules: it is a group of buttons with `aria-pressed`, inside a group with the accessible name
"The accounts of the recording"; the chosen account is the pressed one and it carries the words of
the state and not only a colour; **when the artifact publishes one account, the switcher says in
words that the recording read the ledger of one account**, and the account is still a button, so
that the control does not change its shape when a recording reads many; and the account that is
chosen never goes in the URL.

**`ledger.css`, the styles of the feature.** It follows the pattern of
`apps/web/features/sandbox/sandbox.css`: it declares no colour of its own and it uses the tokens of
`apps/web/app/globals.css`. It carries the rule of the row that is open, and the rule says that
the colour is never the only mark, because the words are already in the row.

### The rules of the browser

Every rule of this section has a reason, and every one of them is a rule of the interface and not
a suggestion.

- **The money is the decimal text of the artifact.** The amount of a movement is read as the text
  it is (`"100.00"`, `"549.31"`) and it is written with `formatMoney`, which groups the digits and
  changes no digit. The browser never calls `Number`, never calls `parseFloat`, never multiplies,
  never rounds, never pads a fraction and never converts a currency. The reason is the same one
  ADR-043 gave: a binary float of a financial amount is a different amount.
  **The ban is about the MONEY.** The page of a table multiplies an index by a size of a page, because
  a page is a position in a list and not an amount, and the rule as it was written said "never
  multiplies" without saying of what. The verifier of the milestone asked the question, and the rule
  now says what it always meant.
- **The browser never sums the column.** There is no total row, there is no total in the caption
  and there is no total in the detail, and there will never be one. A total of the interface is a
  number that the browser calculated, and a number that the browser calculated is a number that no
  artifact carries.
- **A rate is not money.** The `applied_rate` of a read is a rate and not an amount: it carries no
  currency and it is written with the text of the artifact, exactly as it was read, and never with
  `formatMoney` and never with the currency of the run. The reason is the rule of ADR-043 about the
  percentage: a unit written on a value would say something false about it.
- **The rows are paginated and the page never holds a thousand rows.** The table renders at most
  `page_size` rows, the number the artifact declares (50), and the visitor moves between the pages
  with the control of the pagination. The artifact holds every row, but the DOM of the table never
  holds more than one page of them, because a DOM of a thousand rows is a DOM that a reader with a
  keyboard has to walk through row by row.
- **The state of the visitor never goes in the URL.** The account that is chosen and the row that
  is open live in the memory of the panel and in nothing else. The query string carries `tab` and
  `speed`, the two keys the contract of ADR-043 allows, and a parameter that holds anything else
  is ignored. The reason is the rule of the repository: the URL never carries anything that came
  from a visitor.
- **The table has a caption and a header for every column.** The caption is the accessible name of
  the table, and it names the account and the kind of the rows. The header of every column says
  what the column holds, the way the header of the duration says "the duration the capture
  measured" and not "duration".
- **The state is never only a colour.** The row that is open carries the words "Open" and the
  movement that the run read carries the words "Read by the run", and the account that is chosen
  carries the state of the pressed button. The colour of a badge never carries a state alone.
- **The controls are never `disabled`.** The control of the pagination that would do nothing says
  so with `aria-disabled="true"` and a sentence a reader can hear, pointed at with
  `aria-describedby`. The reason is the one ADR-043 gave: a focus that is dropped on the body of
  the document sends the next Tab back to the top of the page.
- **The outline of the headings never skips a level.** The tab carries the `h3`, the panel the
  `h4`, the detail of a row the `h5`, and the table of the design system carries the `caption`
  and never a heading of its own.
- **The `aria-current` sits on the row.** The row that is open carries `aria-current="true"`
  through the callback `rowAttributes` of the table of the design system, and the callback is what
  says which row is the open one, because the table never decides that for anybody.
- **The browser reads nothing else.** `apps/web/lib/api/replay.ts` is the ONE place of the
  frontend that reads the published artifacts, and it reads the file of the ledger there, beside
  the manifest, the events and the provenance. The fence of the network of
  `apps/web/tests/unit/network-fence.test.ts` keeps holding, because the file of the ledger is
  read by the module the fence names.

### The sets

The four sets have disjoint files. **A file named in two sets is a defect of this ADR.**

Every module that this milestone writes in the frontend ALSO exports a constant `__all__` that
carries its whole surface, so that a reader who opens a file sees the surface at once.

#### Set A, the Python of the artifact

| File | Status | Public surface |
| --- | --- | --- |
| `ledgerlens/replay/ledger_artifact.py` | new | `LEDGER_FILE`, `LEDGER_SCHEMA_VERSION`, `LEDGER_PAGE_SIZE`, `ACCOUNT_PATTERN`, `LedgerArtifactError`, `account_of_manifest`, `build_ledger_artifact`, `ledger_artifact_bytes`, `write_ledger_artifact`, `read_ledger_artifact`, `check_ledger_artifact`, `ledger_reads_from_events` |
| `ledgerlens/replay/site_export.py` | changed | the export publishes the file of the ledger, declares its digest and refuses the two cases |
| `scripts/build_ledger_artifact.py` | new | the producer of the frozen artifact |
| `scripts/verify_replay_digests.py` | new | the cross check accounts for the file of the ledger |
| `tests/replay/test_ledger_artifact.py` | new | the test that proves the artifact matches what the run read |
| `tests/replay/test_site_export.py` | changed | the set of the published files and the pinned digests |

Set A touches no file of the frontend and no file of `apps/`.

#### Set B, the library and the state of the frontend

| File | Status | Public surface |
| --- | --- | --- |
| `apps/web/lib/api/schemas.ts` | changed | `LedgerArtifact`, `LedgerAccount`, `LedgerRow`, `LedgerRead`, `LedgerReadRow`, and the field `ledger_sha256` of `ScenarioIndexEntry` |
| `apps/web/lib/api/replay.ts` | changed | the field `ledger` of `LoadedReplay`, the reading of the file of the ledger, and the check of its digest in `verifyBundleDigests` |
| `apps/web/lib/replay/validate.ts` | changed | `validateLedgerArtifact` |
| `apps/web/lib/replay/ledger.ts` | new | `LEDGER_UNAVAILABLE`, `selectLedgerAccounts`, `selectLedgerRows`, `selectLedgerReads`, `selectReadsForRecord`, `ledgerRowIsRead`, `paginateLedgerRows` |
| `apps/web/lib/state/urlState.ts` | changed | `REPLAY_TABS` gains the value `ledger` |
| `apps/web/features/replay/ReplayProvider.tsx` | changed | the field `ledger` of `ReplayState` and the action `loaded` that carries it |

Set B touches no file of `features/ledger/` and no file of the components of the panel.

#### Set C, the components of the ledger

| File | Status | Public surface |
| --- | --- | --- |
| `apps/web/features/ledger/LedgerPanel.tsx` | new | `LedgerPanelProps`, `LedgerPanel` |
| `apps/web/features/ledger/LedgerTable.tsx` | new | `LedgerTableProps`, `LedgerTable`, plus `LedgerAccountContext` and `LedgerAccountContextValue` |
| `apps/web/features/ledger/LedgerRowDetail.tsx` | new | `LedgerRowDetailProps`, `LedgerRowDetail` |
| `apps/web/features/ledger/AccountSwitcher.tsx` | new | `AccountSwitcherProps`, `AccountSwitcher` |
| `apps/web/features/ledger/ledger.css` | new | the styles of the feature |
| `apps/web/features/replay/ReplayViewer.tsx` | changed | the fifth tab and the panel of the ledger |

#### Set D, the documentation and the journey

| File | Status | Public surface |
| --- | --- | --- |
| `docs/frontend.md` | changed | the section "The ledger of the recorded demo" |
| `apps/web/tests/e2e/ledger.spec.ts` | new | the journey of the tab of the ledger |

### The seam between the sets

The files that this milestone changes OUTSIDE the sets are these, and each one changed for the
reason the table gives:

| File | Status | What changed and why |
| --- | --- | --- |
| `site/replay/s01/ledger.json` | new | the published artifact, written by the export of Set A |
| `site/replay/s01/provenance.json` | changed | the provenance publishes the digest of the file of the ledger |
| `site/replay/index.json` | changed | the card of the catalog publishes the digest of the file of the ledger |
| `data/eval/replay/ledger/s01.json` | new | the frozen artifact, written by the producer of Set A and committed with the bundle |
| `scripts/gate.sh` | changed | the gate grew the two steps that the prose of this record asks for: the cross check of the digests (`== replay digests (offline)`) and the measurement of the budget (`== replay budget (offline)`), both after the check of the export |
| `scripts/measure_replay_budget.py` | new | the measurement of the payload of a scenario against the budget that SC-004 declares |
| `scripts/verify_replay_digests.py` | new | the cross check of the published artifacts against the canonical bundle, and the check of the file of the ledger |
| `scripts/capture_replay.py` | not changed | the artifact is produced by the producer, after the capture, so that the recording is never rewritten |
| `apps/web/tests/unit/network-fence.test.ts` | not changed | the file of the ledger is read by the module that the fence names, `lib/api/replay.ts` |
| `apps/web/components/ui/Table.tsx` | not changed | the table of the design system already takes the attribute of a row through `rowAttributes` |
| `apps/web/app/globals.css` | not changed | the styles of the feature live in the stylesheet of the feature and use the tokens of the design system |
| `docs/decisions/ADR-043-the-public-site-of-the-design-package-is-complete.md` | not changed | this ADR answers the open question of ADR-043 about the hash of the published ledger, and it does not edit the record of the past |

The milestone also wrote the files that close the OPEN tasks of the release R1, and they are named here
so that a reader of this record knows exactly which files the milestone touched:

| File | Status | What changed and why |
| --- | --- | --- |
| `apps/web/tests/e2e/landing.spec.ts` | new | the journey of the landing (T027) |
| `apps/web/tests/e2e/playback.spec.ts` | new | the journey of the playback, the pause and the reset (T039) |
| `apps/web/tests/e2e/mobile.spec.ts` | new | the journey of the narrow screen and the assertion of the overflow (T078) |
| `apps/web/tests/unit/replay-reducer.test.ts` | new | the unit tests of the reducer (T024) |
| `apps/web/tests/unit/replay-validate.test.ts` | new | the unit tests of the validators (T025) |
| `apps/web/app/(public)/replay/scenario/[scenario]/page.tsx` | changed | the metadata of the route of a scenario (T038) |
| `specs/001-r1-public-replay/quickstart.md` | new | the quickstart of the release, with the commands that really run (T086) |
| `specs/001-r1-public-replay/recorded-gate-run.md` | new | the record of a real run of the gate (T090) |
| `docs/architecture.md` | changed | the link to the quickstart of the release |

The four files of `site/replay/` and the file of `data/eval/replay/ledger/` are the OUTPUT of the
milestone: they are written by the export and by the producer, and they are committed with the
code that writes them. They are not written by hand, and a change of them without a change of the
code that produces them fails the gate.

### The tests that each set owes

Every test runs with NO key and NO network. The unit tests of the frontend stub the fetch with the
artifacts the repository publishes, and the end to end suite runs against the static export served
as plain files.

Set A owes:

- `tests/replay/test_ledger_artifact.py`: the artifact of the canonical bundle carries the account
  that the note of the bundle names and the kind `customer`; it carries the two movements of the
  account, with the decimal texts `100.00` and `549.31` and the identifiers `TX-2048` and
  `R-0731`, and nothing else; its reads are the reads of the recording, field by field, with the
  citation `sql:1`, the sequence number 19, the statement and the three columns; its rows are
  exactly the two rows of the recorded event, in both directions; its `snapshot_sha256` is the
  digest the manifest of the bundle declares; an artifact of another recording is refused, with the
  two digests that differ; the artifact is written and read back byte for byte, and the check
  finds the difference when the file on the disk is not the one the bundle and the ledger produce.
- `tests/replay/test_site_export.py`: the export publishes the file of the ledger of the scenario
  and declares its digest in the provenance and in the card; the set of the published files of a
  scenario is the four files and the index; the export refuses an artifact whose digest is not the
  digest of the bundle; the export refuses a bundle that names an account and has no artifact; the
  table of the pinned digests carries the file of the ledger.
- `scripts/verify_replay_digests.py` is driven by its own test: the cross check compares the
  published file with the frozen file byte for byte, it checks the digest the provenance publishes
  and the digest the card publishes, and it refuses a published folder that holds a file nobody
  accounts for.

Set B owes:

- `apps/web/tests/unit/api-replay.test.ts`: the loader reads the file of the ledger beside the
  bundle; **a bundle without a file of the ledger is NOT refused**, because the ledger is a
  sidecar and the recording is still a recording, and the state carries the reason; a file of the
  ledger that is not a JSON document is not a refusal either, and the reason says what happened;
  the check of the integrity compares the digest of the file of the ledger with the digest the
  provenance publishes, and it says out loud that the integrity was not checked when the browser
  offered no Web Crypto.
- `apps/web/tests/unit/replay-ledger.test.ts`: the selectors of the ledger: the accounts come from
  the artifact and there is one of them; the rows of the chosen account keep the order of the
  artifact; the reads of the chosen account keep the order of the recording; a read names a
  movement exactly when the identifier of the movement is one of the records of the read; the
  pagination returns one page of at most `page_size` rows and never a page that is out of range.
- `apps/web/tests/unit/url-state.test.ts`: the allow list of the tabs carries `ledger` and the
  other three values are unchanged; a tab that is not in the list is ignored and the default
  holds; the query string carries only `tab` and `speed`, and a parameter that holds an
  identifier of a row or an account is ignored.

Set C owes:

- `apps/web/tests/unit/features/ledger-panel.test.tsx`: the panel shows the movements of the
  artifact with the amount and the currency of the artifact; it marks the movement that the run
  read with the words "Read by the run" and leaves the other one unmarked; it opens the detail of
  the row that the visitor opens and closes it; the detail shows the reads that name the row and
  says in words that the recording read no record of a row that no read names; the switcher shows
  the account of the artifact and says in words that the recording read the ledger of one account;
  the panel shows the reason when the artifact is not available, and it shows nothing else.
- `apps/web/tests/unit/features/ledger-accessibility.test.tsx`: the table carries a caption and a
  header for every column; the row that is open carries `aria-current="true"` and the attribute
  sits on the row; the state is never only a colour; the controls of the pagination are never
  `disabled` and carry `aria-disabled` with a reason; the outline of the headings of the tab
  never skips a level; the state of the visitor never reaches the URL.
- `apps/web/tests/unit/features/replay-viewer.test.tsx`: the reader of the replay has the fifth tab,
  the tab opens the panel of the ledger, and the state of the visit still carries only the tab and
  the speed.

Set D owes:

- `apps/web/tests/e2e/ledger.spec.ts`: the journey of the tab of the ledger: the tab opens from
  the address and from the row of the tabs; the table shows the two movements of the account; the
  visitor opens a row and the detail shows the reads that name it; the control of the pagination
  says which page it is on; and the URL of the page holds the identifier of the scenario, the tab
  and the speed, and nothing else.
- `docs/frontend.md`: the section "The ledger of the recorded demo", with the artifact, the shape
  of the row, the rules of the browser and the debts.

### What the milestone does not deliver, and why

- **The ledger of the BRANCH of the sandbox.** The route `GET /v1/sandboxes/{id}/ledger` exists
  and the front does not call it. The ledger of a branch is a different thing: it is the state of
  the branch of a visitor, it moves with the mutations, it lives on the origin of the backend and
  it is read with the cursor of the next page. It is NOT the ledger of the recorded demo, and the
  two never mix: one is an artifact of the site, the other is a call to the backend with the
  credentials of the visitor (ADR-038, ADR-040, ADR-044). What the debt wants: a component that
  reads the ledger of the branch through the same client, with the cursor and the account switcher
  that goes with it. The row shape of this milestone is the shape of the branch ledger, so that
  component can be written when the work comes.
- **The thousands of rows of the full ledger.** The simulated ledger holds 2114 transactions, 1934
  rates, 359 refunds, 10 chargebacks and 286 settlements over 24 merchants and 1418 customers:
  2483 movements. The recording read the ledger of ONE account, and the digest of the snapshot is
  the proof that the ledger of the account is the ledger of the recording. Publishing the whole
  ledger would publish rows that no recording read, and the artifact would stop being the ledger
  of the recording. What the debt wants: an artifact of its own, with the account switcher over the
  accounts and the pagination that goes with it, and a decision about the rows the site is allowed
  to publish.
- **The search.** The site has no search over the ledger. A search needs the rows of every
  account, and the artifact of this milestone holds the rows of one. What the debt wants: a search
  over the published artifact, which means the artifact of the full ledger first.
- **The published result of the recording.** The `run_result` of the bundle is still not published,
  and this milestone does not change that: it is the debt that ADR-043 named, and the claim of the
  recording is still rendered as `Not available` with the identifier and the note of the verdict.
- **The link between the rate of the refund and the refund `R-0731`.** The recorded statement asked for
  `kind`, `applied_rate` and `applied_at`, and it did not ask for the identifier of the refund, so
  the artifact cannot say that the rate `5.4931` is the rate of the refund `R-0731`: the statement
  names the transaction and nothing else. What the debt wants: a recording that reads the refund as
  well, which is a new capture and not a new interface.

## Alternatives considered

- **(a) Publish only the rows the run read, and nothing else.** The artifact would carry the two
  rates, with the three columns the recording asked for, and the table of the ledger would carry
  no identifier of a row, no amount of money and no date of a movement. It was rejected because the
  row of a ledger in this repository already has a shape (the shape of `_ledger_items`), because the
  promise of the home page is the ledger, and because a table whose rows have no identifiers has no
  row to open and no detail to show.
- **(b) Rebuild the ledger of the account at the time of the export and compare the digest of the
  file with the digest of the snapshot.** It was rejected because the bytes of a file of SQLite
  depend on the version of the library that wrote it: the header of the file carries the number of
  the version of SQLite. The export would refuse on a machine with another version of SQLite, and
  the gate of the repository would be red for a reason that has nothing to do with the recording.
  The digest is the proof of the identity of the ledger, and the proof belongs to the producer, once,
  and not to the export, every time.
- **(c) Put the artifact inside the bundle.** It was rejected because `load_bundle` refuses a
  folder that holds a file the manifest does not declare, and because the digest of the bundle is
  the digest of the manifest: a file of the ledger inside the bundle would move the digest of the
  bundle, and the bundle is frozen and names the commit it was made from.
- **(d) Publish one artifact of the ledger for the whole site.** It was rejected because the rows
  belong to the recording of one scenario and to the ledger of one account, and a file for the
  whole site would mix the accounts of the scenarios and would publish rows that no recording
  read.
- **(e) Put the ledger in the tab of the evidence, under the panel of the answer.** It was
  rejected because the evidence of the answer is the evidence of the claims, and a table with a
  pagination, a switcher and a detail does not belong under it. The evidence of the answer keeps
  the citation `sql:1` and the statement of the query, and the rows of the query get a place of
  their own.
- **(f) Let the browser call the backend for the rows, the way the live mode and the sandbox do.**
  It was rejected because the recorded demo calls nobody, and because the rows of a recording are
  frozen with the recording: they are an artifact of the site and not a call.

## Consequences

The site shows the ledger rows it read. A visitor of the scenario `S01` opens the tab of the
ledger, sees the ledger of the account `C-0412` with the two movements of the account, sees which
of them the run read, opens the transaction `TX-2048` and sees the two rows the recording read,
with the citation `sql:1`, the statement that produced them and the sequence number of the event
that closed the call. Every value of that panel is a text of a published artifact, and the browser
calculated nothing.

The chain of the digests of the published scenario is closed: the digest of the events is the
digest the manifest declares, the digest of the file of the ledger is the digest the provenance
declares, the digest of the provenance is the digest the card of the catalog declares, and the
digest of the ledger of the account is the digest the recording declares as its snapshot. The gate
of the repository checks the chain on the disk, the cross check of the published artifacts checks
it against the canonical bundle, and the browser checks it with the Web Crypto and says out loud
when it could not.

The shape of the row of the ledger is now written in one place and it is the shape of the branch
ledger, so the panel of the ledger of the sandbox, which is the debt of ADR-044, will be written
against a contract that already exists.

The four sets are independent. The contract between the workers is this ADR: the file names, the
exported names, the shapes and the props are written down here, so that a worker can write against
the code of another set before it exists.

## What the verifier of the milestone found, and what was corrected in it

Two independent verifiers read this record and the code it describes, one for the Python half and one
for the frontend half, and they wrote twenty-two mutations that had to turn a test red. Every one of
the twelve rules of the browser is proved by a mutation that breaks exactly that rule. The frontend
verifier wrote seven findings and the code was corrected in the milestone, not in the record alone:

- **The integrity of the file of the ledger was never said out loud to the visitor.** The loader
  computed it and the state carried it and no component read it. The panel now takes the third prop
  of this record and draws the sentence, and the test proves that the sentence is there when the
  integrity is unknown and that it is absent when the file was really checked.
- **The field of the integrity said "checked" in two cases in which nothing was compared.** A site
  that published no file of the ledger and a provenance that published no digest of it are both cases
  of nothing to compare, and the field now says "unknown" in both. The test proves both.
- **Two rules of the detail of a row had no test at all.** The six fields of the movement and the
  header of every column of a read are now proved by two cases, and a mutation that deletes one of
  the six fields or that renames one of the headers turns them red.
- **The stylesheet carried the rule of the row that is open in a comment and nowhere else.** The rule
  is now a rule of the sheet, and it changes the SURFACE of the row and not only its colour.
- **The table exported two names that this record did not pin.** The names are now pinned here.
- **The inventory of the files of this record did not match the tree.** The seam table now says that
  the gate changed, that the cross check and the measurement of the budget are new, and it names the
  files that the open tasks of the release R1 brought with them.
- **The cross check printed the digest of the manifest under the name of the provenance file.** The
  label of the line is the label of the file it really is.

And the open question about the word "multiplies" was answered in the rule itself: the ban is about
the money, and the page of a table multiplies an index by a size of a page.

## What the verifier of the Python half found, and what was corrected in it

The verifier of the Python half wrote THIRTY mutations of the code of this milestone, on a copy of
the repository outside it, and twenty-three of them turned a test red and SEVEN stayed green. The
seven that stayed green are gaps of the PROOF, and the code was corrected and the proof was closed:

- **The export leaked a traceback instead of refusing.** The helper that reads the account out of the
  note of the manifest refuses a note that names more than one account, and the export caught only its
  own error, so the refusal escaped as a raw traceback. The export translates the refusal of the
  artifact into its own, names the scenario and the reason, and the caller prints that and stops.
- **The frozen artifact was not pinned to the producer.** The committed file is written by the
  producer, but nothing compared the committed file with a fresh run of the producer, so the two
  could drift apart silently. The proof that they are the same bytes is now a test.
- **Two of the three cross check cases of the file of the ledger were masked.** The three checks
  guard one another, and disabling the comparison with the frozen file, or the check of the digest
  that the provenance publishes, left the whole suite green. Each of the two now has a case of its
  own that goes red when the check is removed: one tampers the FROZEN file and the other tampers the
  digest that the PROVENANCE publishes, because those are the two tampers that only that check can
  catch.
- **The refusal of a broken file and the format of the bytes were never exercised.** Both are now
  proved by cases of their own.
- **The refusal of a note that names more than one account was never exercised.** It is now.
- **The identifiers of a read were not proved to come from the statement.** The canonical statement
  names one identifier, so a hard-coded list would pass every test. The case uses another statement
  now.
- **The producer of the artifact had no `__all__` and the measurement of the budget had no test at
  all.** Both are closed.
- **The module exported a name that this record did not pin.** The name is pinned here now.

The question about a row with more values than the read declares columns was answered in the code:
the artifact NEVER repairs a value, and a row that does not match the columns of its read is a
refusal and not a truncation.

## The debt

- **The identity of the ledger depends on the bytes of a file of SQLite.** The producer rebuilds
  the ledger of the account and compares the sha256 of the file with the digest that the manifest
  of the bundle declares. The bytes of a file of SQLite carry the number of the version of the
  library that wrote it, so the producer refuses on a machine with another version of SQLite, even
  when the rows are the same rows. What the debt wants: a digest of the CONTENT of the ledger,
  written by the capture next to the digest of the file, so that the identity of the ledger does
  not depend on the version of a library. That needs a new version of the contract of the bundle,
  and the contract of the design package cannot be edited (ADR-023).
- **The artifact of a scenario is produced by a command that is not the capture.** A capture that
  is not followed by the producer leaves the gate red, and that is the rule and not an accident.
  What the debt wants: the capture that writes the artifact of the scenario it just recorded, from
  the very file of the ledger it ran against, so that the two halves of the milestone are produced
  by the same command.
- **The catalog of the scenarios does not carry the account.** The card of the catalog publishes
  the digest of the artifact and the question of the scenario, and not the account whose ledger is
  published. What the debt wants: the account of the scenario in the card, when the recording
  names one.
- **The table of the ledger reads the whole artifact into the memory of the browser.** The
  artifact of the recorded demo holds four rows and the pagination is a formality, but an artifact
  of the full ledger would hold thousands of rows and the browser would read all of them. What the
  debt wants: a page of the artifact read from the file itself, the way the branch ledger is read
  with its cursor.
- **The search of the ledger, the full ledger and the ledger of the branch** are the three debts
  named in the section about what the milestone does not deliver.

## The facts this ADR could not establish from the repository

- **The sha256 of the published file `site/replay/s01/ledger.json`** cannot be written in this
  record: the file does not exist yet. It is computed when the producer writes the artifact and
  the export publishes it, and it is pinned in the table of the pinned digests of
  `tests/replay/test_site_export.py`.
- **The shape of the artifact is a decision and not a fact of the repository.** The repository
  holds no artifact of the ledger today: the bundle carries the rows inside the events, the
  frontend reads the SQL of the citation `sql:1` and shows nothing else, and the contract of the
  design package declares no ledger artifact. The shape written here is the transcription of what
  the recording holds, in the shape of the row of the ledger that the branch layer already writes.
- **The name of the account of a recording is read from the note of the manifest**, which is free
  text written by the capture. The identifier is read with a pattern and the producer refuses a
  bundle whose note names no account, but the rule depends on the note of the capture keeping its
  shape.
