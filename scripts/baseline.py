"""Writes the baseline record of the repository: what was run, with which version and with which hash.

Why it exists: a number is worth something only if someone else can redo the same run and match it. This script freezes
the state of the code (commit and tree), the environment (Python, uv and the versions pinned in `uv.lock`), the hashes
of the data artifacts the result depends on and the exact output of the offline gate. The result goes to
`verification/baseline.md`, which is the evidence of the LL-V3-R0-01 and LL-V3-R0-02 tasks of the v3 roadmap.

The script does not invent a result: it runs the real gate, `bash scripts/gate.sh`, and transcribes what came out. If a
step fails, the record comes out with the failure, not with an invented number.

The record carries a fingerprint: the sha256 of what determines the result (pinned versions, data hashes and normalised
gate output). The `--check` recomputes that fingerprint and compares it with the one in the record. Date, commit and
tree are left out of the fingerprint on purpose: they change on every documentation commit and do not change the
result.

Usage:

```bash
uv run python scripts/baseline.py            # writes verification/baseline.md
uv run python scripts/baseline.py --check    # only compares the fingerprint with the existing record
uv run python scripts/baseline.py --no-tests # without running the suite (incomplete record, marked as such)
```
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "verification" / "baseline.md"

# The data artifacts the numbers of the repository depend on. A hash change here makes the old result worth less.
DATA_ARTIFACTS = (
    "data/scenarios.json",
    "data/eval/verification_set.jsonl",
    "data/eval/verification_live.jsonl",
    "data/eval/report_online.json",
    "ledgerlens/verify/thresholds.json",
)

# The versions that change the behaviour of the agent. The `uv.lock` is the source; what matters is what runs.
PINNED_PACKAGES = (
    "fastembed",
    "langchain",
    "langchain-core",
    "langchain-openai",
    "langgraph",
    "langsmith",
    "openai",
    "pydantic",
    "sentence-transformers",
    "sqlglot",
    "streamlit",
    "transformers",
)

# The real gate, the same one of `scripts/gate.sh` and the same one the continuous integration runs.
GATE_COMMAND = ("gate", ("bash", "scripts/gate.sh"))
LINT_COMMAND = ("ruff", ("uv", "run", "ruff", "check"))

FINGERPRINT_PATTERN = re.compile(r"<!-- fingerprint: (?P<digest>[0-9a-f]{64}) -->")
DURATION_PATTERN = re.compile(r"\bin \d+(?:\.\d+)?s\b")
CLOCK_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?")
# The pytest writes the clock in parentheses at the end of the score, for example "(0:02:51)".
PAREN_CLOCK_PATTERN = re.compile(r"\(\d+:\d{2}:\d{2}\)")


def _env() -> dict[str, str]:
    """The environment of the gate: offline and with the locale of the CI, so the record is comparable with the CI."""
    env = dict(os.environ)
    env["LEDGERLENS_OFFLINE"] = "1"
    env["LANG"] = "C.UTF-8"
    env["LC_ALL"] = "C.UTF-8"
    return env


def _run(command: list[str] | tuple[str, ...], *, cwd: Path = ROOT) -> tuple[int, str]:
    """The exit code and the combined output (stdout and stderr together, because pytest writes to both)."""
    proc = subprocess.run(list(command), cwd=cwd, capture_output=True, text=True, env=_env(), check=False)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _git(*args: str) -> str:
    code, out = _run(["git", *args])
    return out if code == 0 else ""


def _git_lines(*args: str) -> list[str]:
    return [line for line in _git(*args).splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _locked_versions() -> dict[str, str]:
    """The pinned version of each package that matters, read from the `uv.lock`."""
    lock = ROOT / "uv.lock"
    versions: dict[str, str] = {}
    if not lock.exists():
        return versions
    parsed = tomllib.loads(lock.read_text(encoding="utf-8"))
    for package in parsed.get("package", []):
        name = package.get("name")
        if name in PINNED_PACKAGES:
            versions[name] = package.get("version", "")
    return versions


def _data_rows(path: Path) -> str:
    """How many records the file has, when it is JSONL."""
    with path.open(encoding="utf-8") as handle:
        return str(sum(1 for line in handle if line.strip()))


def _normalize(output: str) -> str:
    """Takes out what changes between two equal runs: the clock and the duration."""
    text = DURATION_PATTERN.sub("in <time>", output)
    text = CLOCK_PATTERN.sub("<date>", text)
    return PAREN_CLOCK_PATTERN.sub("(<clock>)", text)


def _tail(output: str, lines: int = 12) -> str:
    """The end of the output: it is where pytest leaves the score."""
    return "\n".join(output.splitlines()[-lines:])


def _collect(*, run_tests: bool) -> dict[str, object]:
    """Everything that goes into the record: code state, environment, data and the output of the gate."""
    tracked = _git_lines("status", "--porcelain", "--untracked-files=no")
    untracked = _git_lines("ls-files", "--others", "--exclude-standard")
    locked = _locked_versions()

    data: list[tuple[str, str, str]] = []
    for relative in DATA_ARTIFACTS:
        path = ROOT / relative
        if not path.exists():
            data.append((relative, "absent", ""))
            continue
        digest = _sha256(path)
        extra = f"{_data_rows(path)} records" if path.suffix == ".jsonl" else ""
        data.append((relative, digest, extra))

    gates: list[tuple[str, int, str]] = []
    if run_tests:
        name, command = GATE_COMMAND
        code, output = _run(command)
        gates.append((name, code, _tail(output)))
    else:
        name, command = LINT_COMMAND
        code, output = _run(command)
        gates.append((name, code, _tail(output)))
        gates.append(("pytest", -1, "not run in this record (--no-tests)"))

    return {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "tracked_changes": tracked,
        "untracked": untracked,
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "uv": _run(["uv", "--version"])[1],
        "locked": locked,
        "data": data,
        "gates": gates,
    }


def _fingerprint(info: dict[str, object]) -> str:
    """The sha256 of what determines the result: versions, data and gate score, without clock and without commit."""
    payload = {
        "python": info["python"],
        "uv": info["uv"],
        "locked": info["locked"],
        "data": [[relative, digest, extra] for relative, digest, extra in info["data"]],
        "gates": [[name, code, _normalize(output)] for name, code, output in info["gates"]],
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _render(info: dict[str, object], stamp: str) -> str:
    """The record in Markdown."""
    tracked = info["tracked_changes"]
    untracked = info["untracked"]
    lines = [
        "# Baseline of the repository",
        "",
        "Generated by `scripts/baseline.py`. This file is the evidence of LL-V3-R0-01 and LL-V3-R0-02 of the "
        "[v3 roadmap](../docs/roadmap-v3.md).",
        "",
        f"- Run at: {stamp}",
        "- Command: `uv run python scripts/baseline.py`",
        f"- Measured commit: `{info['commit']}`",
        f"- Branch: `{info['branch']}`",
        f"- Changed versioned files: {'none' if not tracked else len(tracked)}",
        "",
    ]
    if tracked:
        lines += ["Changed versioned files at the moment of the record:", ""]
        lines += [f"- `{note}`" for note in tracked]
        lines += [""]

    lines += ["## Environment", ""]
    lines += [
        f"- Python: {info['python']}",
        f"- System: {info['platform']}",
        f"- uv: {info['uv']}",
        "",
        "## Pinned versions",
        "",
        "From the `uv.lock`. It is what runs, not what is installed on the machine.",
        "",
        "| Package | Version |",
        "|---|---|",
    ]
    for name, version in sorted(info["locked"].items()):
        lines.append(f"| {name} | {version} |")

    lines += [
        "",
        "## Hashes of the data artifacts",
        "",
        "A different hash here invalidates the old result.",
        "",
        "| File | sha256 | Note |",
        "|---|---|---|",
    ]
    for relative, digest, extra in info["data"]:
        lines.append(f"| `{relative}` | `{digest}` | {extra} |")

    lines += [
        "",
        "## Output of the offline gate",
        "",
        "`LEDGERLENS_OFFLINE=1`, the same gate the continuous integration runs (`.github/workflows/gate.yml`).",
        "",
    ]
    for name, code, output in info["gates"]:
        status = {0: "ok", -1: "not run"}.get(code, f"failed (code {code})")
        lines += [f"### {name}: {status}", "", "```", output, "```", ""]

    lines += [
        "## What this record does not cover",
        "",
        "- No online execution: the real model and the live exchange rate do not enter here.",
        "- The wall clock time of the online executions is not stable and does not enter here.",
        "- The quality numbers cited in the README come from saved online runs; this record proves the code and the "
        "environment with which they can be reproduced, not that they are equal.",
        "",
    ]

    if untracked:
        python_leaks = [note for note in untracked if note.endswith(".py")]
        lines += ["## Unversioned files", ""]
        lines += [
            "These files exist on the machine and are not in the commit. They do not enter the result of the gate,"
        ]
        lines += ["because pytest collects the versioned tests. If one of them starts being imported, the record"]
        lines += ["stops being valid and has to be redone.", ""]
        lines += [f"- `{note}`" for note in untracked]
        lines += [""]
        if python_leaks:
            lines += [
                f"Warning: {len(python_leaks)} unversioned Python file(s) can enter the execution.",
                "",
            ]
        lines += [""]

    lines += [
        "## Reproducibility fingerprint",
        "",
        "The sha256 below covers the pinned versions, the data hashes and the gate score, without clock and without "
        "commit. `uv run python scripts/baseline.py --check` recomputes that fingerprint and says whether the record "
        "still matches the current state.",
        "",
        f"<!-- fingerprint: {_fingerprint(info)} -->",
        "",
    ]
    return "\n".join(lines)


def _stored_fingerprint() -> str | None:
    """The fingerprint of the existing record, if there is one."""
    if not REGISTRY.exists():
        return None
    match = FINGERPRINT_PATTERN.search(REGISTRY.read_text(encoding="utf-8"))
    return match.group("digest") if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Writes or checks the baseline record of the repository.")
    parser.add_argument("--check", action="store_true", help="compares with the existing record instead of writing")
    parser.add_argument(
        "--no-tests",
        action="store_true",
        help="does not run the suite (the record comes out marked as incomplete)",
    )
    args = parser.parse_args()

    info = _collect(run_tests=not args.no_tests)

    if args.check:
        stored = _stored_fingerprint()
        if stored is None:
            print("record absent or without a fingerprint:", REGISTRY)
            return 1
        current = _fingerprint(info)
        if stored == current:
            print("the record matches the current state")
            return 0
        print("the record does NOT match the current state")
        print(f"  recorded: {stored}")
        print(f"  current:  {current}")
        return 1

    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(_render(info, stamp), encoding="utf-8")
    print("record written in", REGISTRY.relative_to(ROOT))
    for name, code, _ in info["gates"]:
        print(f"  {name}: {'ok' if code == 0 else code}")
    return 0 if all(code == 0 for _, code, _ in info["gates"]) else 1


if __name__ == "__main__":
    sys.exit(main())
