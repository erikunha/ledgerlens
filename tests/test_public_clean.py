"""The public repository carries no course material, no machine paths of the author, no keys and no Portuguese.

The forbidden words are built from fragments, and the Portuguese markers from escapes, so this file does not
match its own rules.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_WORDS = [
    "in" + "fnet",
    "disci" + "plina",
    "profes" + "sor",
    "enun" + "ciado",
    "rub" + "rica",
    "rub" + "ric",
    "al" + "uno",
    "note" + "book",
    "nb0" + "[0-9]",
    "video" + "_script",
    "vi" + "deo_link",
    "spec" + "-kit",
    r"\." + "spec" + "ify",
]
FORBIDDEN = re.compile("|".join(_WORDS), re.IGNORECASE)
# a course acronym: upper case only and as a whole word
FORBIDDEN_CASE = re.compile(r"\b" + "M" + "BA" + r"\b")
HOME_PATH = re.compile("/" + "Users" + "/|/" + "home" + "/[a-z]")
SECRET = re.compile("sk-[A-Za-z0-9]{20,}|" + "lsv" + "2_[A-Za-z0-9_]{10,}|api_key\\s*=\\s*['\"][A-Za-z0-9]{16,}")
SKIP = {"uv.lock", "tests/test_public_clean.py"}

# ---- Portuguese -----------------------------------------------------------------------------------
# Letters English never uses, words that only exist in Portuguese, and two function words that English
# prose never has between spaces in lower case. " DE " (a country code) and "de_DE" (a locale) do not match.
_PT_LETTERS = re.compile("[\u00e7\u00e3\u00f5\u00c7\u00c3\u00d5]")
_PT_WORDS = re.compile(
    r"\b(?:"
    + "|".join(
        [
            "n\u00e3o",
            "voc\u00ea",
            "reem" + "bolso",
            "co" + "bran\u00e7a",
            "taxa de c\u00e2m" + "bio",
        ]
    )
    + r")\b",
    re.IGNORECASE,
)
_PT_FUNCTION_WORDS = re.compile(" (?:" + "d" + "e" + "|" + "pa" + "ra" + ") ")
PORTUGUESE = (_PT_LETTERS, _PT_WORDS, _PT_FUNCTION_WORDS)
PORTUGUESE_SCOPE = ("ledgerlens/", "app/", "data/", "docs/", "tests/")
PORTUGUESE_SUFFIXES = {".py", ".md", ".jsonl", ".json"}
# Recorded responses of Brazilian public APIs (holiday names, Banco Central bulletins): external data, kept as
# the source returned it.
PORTUGUESE_ALLOWED_FILES = {
    "data/fixtures/holidays/nager_BR_2026.json",
    "data/fixtures/fx/bcb_ptax_EUR_BRL.json",
    "data/fixtures/fx/bcb_ptax_USD_BRL.json",
}
# External proper names, removed from a line before the markers run.
PORTUGUESE_ALLOWED_NAMES = ("Banco Central do Brasil", "Fechamento PTAX")


def _files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    return [name for name in out if name and name not in SKIP and (ROOT / name).is_file()]


def _lines(name: str):
    try:
        text = (ROOT / name).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return  # binary (FAISS index, images)
    yield from enumerate(text.splitlines(), 1)
    # the file name counts too
    yield 0, name


def _offenders(*patterns: re.Pattern[str]) -> list[str]:
    found = []
    for name in _files():
        for number, line in _lines(name):
            if isinstance(line, str) and any(p.search(line) for p in patterns):
                found.append(f"{name}:{number}")
    return found


def is_portuguese(line: str) -> bool:
    for name in PORTUGUESE_ALLOWED_NAMES:
        line = line.replace(name, "")
    return any(p.search(line) for p in PORTUGUESE)


def _portuguese_scope() -> list[str]:
    return [
        name
        for name in _files()
        if (name == "README.md" or name.startswith(PORTUGUESE_SCOPE))
        and Path(name).suffix in PORTUGUESE_SUFFIXES
        and not name.startswith("data/index/")
        and name not in PORTUGUESE_ALLOWED_FILES
    ]


def test_no_course_material_in_tracked_files():
    assert not _offenders(FORBIDDEN, FORBIDDEN_CASE)


def test_no_machine_paths_in_tracked_files():
    assert not _offenders(HOME_PATH)


def test_no_secrets_in_tracked_files():
    assert not _offenders(SECRET)


def test_course_directories_are_absent():
    for name in ("note" + "books", "specs", ".specify", "docs/report", "docs/evidence"):
        assert not (ROOT / name).exists(), name


def test_the_portuguese_markers_catch_portuguese_and_spare_english():
    assert is_portuguese("O " + "reem" + "bolso veio menor.")
    assert is_portuguese("A taxa n\u00e3o foi aplicada.")
    assert is_portuguese("prazo d" + "e 30 dias")
    assert is_portuguese("Execu\u00e7\u00e3o real")
    assert not is_portuguese("The refund came in lower than the payment, see the policy for details.")
    assert not is_portuguese('EURO_AREA = frozenset("AT BE CY DE EE")')
    assert not is_portuguese('FAKER_LOCALES = {"DE": "de_DE"}')
    assert not is_portuguese("Lucía Fernández and the Banco Central do Brasil (Fechamento PTAX)")


def test_the_portuguese_scope_covers_code_data_docs_and_tests():
    scope = set(_portuguese_scope())
    for expected in ("README.md", "ledgerlens/verify/claims.py", "data/policies/refund-policy.md", "tests/conftest.py"):
        assert expected in scope, expected
    assert "uv.lock" not in scope
    assert not any(name.startswith("data/index/") for name in scope)
    assert not scope & PORTUGUESE_ALLOWED_FILES


def test_no_portuguese_in_code_data_docs_or_tests():
    found = []
    for name in _portuguese_scope():
        for number, line in _lines(name):
            if isinstance(line, str) and is_portuguese(line):
                found.append(f"{name}:{number}")
    assert not found, found[:20]


def test_local_tool_folders_are_never_tracked():
    """Planning and editor state live next to the code but must not be published."""
    local = (".plans/", ".claude/", ".obsidian/", ".specify/")
    assert not [name for name in _files() if name.startswith(local)]
