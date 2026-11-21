"""The public repository carries no course material, no machine paths of the author, no keys and no Portuguese.

The forbidden words are built from fragments, and the Portuguese markers from escapes, so this file does not
match its own rules.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The specification toolkit is part of the work, so its folder name is allowed. What is not allowed is the local
# planning state it holds, and the feature branches it used to create outside the release branch. The toolkit
# scripts name the state file they manage, and those lines alone are tool code (_tooling_files exempts them).
_STATE_FILE = r"\.specify/feature\.json"
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
    _STATE_FILE,
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
PORTUGUESE_SCOPE = ("ledgerlens/", "app/", "data/", "docs/", "tests/", "specs/", ".specify/")
PORTUGUESE_SUFFIXES = {".py", ".md", ".jsonl", ".json", ".txt", ".sh", ".yaml", ".yml"}
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


_TOOLING_STATE_PATH = re.compile(_STATE_FILE)


def _tooling_files() -> list[str]:
    """The paths of the specification toolkit that name its own state file, and only those.

    The toolkit is tool code, so the lines naming the state file it manages are exempt from the content rules of
    this repository. The exemption is those paths alone: every other path of a toolkit file is scanned again, and
    the rules still apply to everything the toolkit produces, the constitution and the specs included.
    """
    return [
        f"{name}:{number}"
        for name in _files()
        if name.startswith(".specify/scripts/") or name.startswith(".specify/templates/")
        for number, line in _lines(name)
        if isinstance(line, str) and _TOOLING_STATE_PATH.search(line)
    ]


def is_portuguese(line: str) -> bool:
    for name in PORTUGUESE_ALLOWED_NAMES:
        line = line.replace(name, "")
    return any(p.search(line) for p in PORTUGUESE)


def _portuguese_scope() -> list[str]:
    # ADR-016 keeps English as the source of truth and gives the Brazilian Portuguese translation layer the
    # only surfaces that may carry the language, so exactly docs/pt-BR/** and README.pt-BR.md leave the scan.
    return [
        name
        for name in _files()
        if (name == "README.md" or name.startswith(PORTUGUESE_SCOPE))
        and Path(name).suffix in PORTUGUESE_SUFFIXES
        and not name.startswith("data/index/")
        and name not in PORTUGUESE_ALLOWED_FILES
        and not name.startswith("docs/pt-BR/")
        and name != "README.pt-BR.md"
    ]


def test_no_course_material_in_tracked_files():
    tooling = set(_tooling_files())
    found = [hit for hit in _offenders(FORBIDDEN, FORBIDDEN_CASE) if hit not in tooling]
    assert not found, found[:20]


def test_course_scan_exempts_only_the_state_file_paths(tmp_path, monkeypatch):
    """A toolkit file is not exempt as a whole: only the paths naming its state file are, its other paths are not."""
    name = ".specify/scripts/resolve_feature.sh"
    script = tmp_path / name
    script.parent.mkdir(parents=True)
    state_line = "reads " + ".specify/feature" + ".json"
    course_line = "kept a " + "note" + "book"
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    monkeypatch.setattr(sys.modules[__name__], "_files", lambda: [name])
    script.write_text(state_line + "\n", encoding="utf-8")
    test_no_course_material_in_tracked_files()
    script.write_text(state_line + "\n" + course_line + "\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        test_no_course_material_in_tracked_files()


def test_course_scan_exempts_only_the_scripts_and_templates_folders(tmp_path, monkeypatch):
    """The exemption reaches the toolkit code folders alone: the same state-file line in any other folder of the
    toolkit names per-machine planning state, so it stays an offender and the scan must fail on it."""
    state_line = "reads " + ".specify/feature" + ".json"
    names = [".specify/scripts/x.sh", ".specify/memory/plan.md"]
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True)
        path.write_text(state_line + "\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "_files", lambda: [names[0]])
    test_no_course_material_in_tracked_files()
    monkeypatch.setattr(sys.modules[__name__], "_files", lambda: [names[1]])
    with pytest.raises(AssertionError):
        test_no_course_material_in_tracked_files()


def test_no_machine_paths_in_tracked_files():
    assert not _offenders(HOME_PATH)


def test_no_secrets_in_tracked_files():
    assert not _offenders(SECRET)


def test_course_directories_are_absent():
    """The course material stays out. The spec-kit folders are part of the work and do stay in."""
    for name in ("note" + "books", "docs/report", "docs/evidence"):
        assert not (ROOT / name).exists(), name


def test_the_spec_kit_folders_are_present():
    """The spec-kit toolkit and the specs it writes are versioned, so the plan is readable with the code."""
    assert (ROOT / ".specify" / "memory" / "constitution.md").is_file()
    assert (ROOT / "specs").is_dir()
    assert list((ROOT / "specs").glob("*/spec.md")), "no feature spec is versioned"


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


def test_portuguese_scan_covers_shell_yaml_text_and_config_specs(tmp_path, monkeypatch):
    """specs/ shell, YAML and plain text files carry the Portuguese scan, not only code and document files."""
    names = ["specs/edge/run.sh", "specs/edge/run.yaml", "specs/edge/notes.txt", "specs/edge/config.yml"]
    (tmp_path / "specs" / "edge").mkdir(parents=True)
    marker = "prazo d" + "e 30 dias"
    for name in names:
        (tmp_path / name).write_text(marker + "\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    monkeypatch.setattr(sys.modules[__name__], "_files", lambda: list(names))
    assert set(_portuguese_scope()) == set(names)
    with pytest.raises(AssertionError):
        test_no_portuguese_in_code_data_docs_or_tests()


def test_portuguese_allowance_is_only_the_pt_br_translation_layer(tmp_path, monkeypatch):
    """The ADR-016 allowance is narrow: the same Portuguese line passes only in the translation layer
    (docs/pt-BR/** and README.pt-BR.md) and stays refused in every other scanned path, lookalikes included."""
    marker = "prazo d" + "e 30 dias"
    allowed = ["README.pt-BR.md", "docs/pt-BR/roadmap-v3.md"]
    refused = [
        "README.md",
        "docs/roadmap-v3.md",
        "ledgerlens/verify/claims.py",
        "tests/conftest.py",
        # a path that merely carries the locale in its name is not the translation layer
        "ledgerlens/pt-BR/x.py",
        "docs/pt-BR-notes.md",
    ]
    names = allowed + refused
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(marker + "\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    monkeypatch.setattr(sys.modules[__name__], "_files", lambda: list(names))
    scope = set(_portuguese_scope())
    for name in allowed:
        assert name not in scope, name
    for name in refused:
        assert name in scope, name
    for name in allowed:
        monkeypatch.setattr(sys.modules[__name__], "_files", lambda n=name: [n])
        test_no_portuguese_in_code_data_docs_or_tests()
    for name in refused:
        monkeypatch.setattr(sys.modules[__name__], "_files", lambda n=name: [n])
        with pytest.raises(AssertionError):
            test_no_portuguese_in_code_data_docs_or_tests()


def test_local_tool_folders_are_never_tracked():
    """Planning and editor state live next to the code but must not be published.

    The specification toolkit is the exception: it is part of the work, and the constitution and the specs it writes
    have to be readable next to the code. What stays out is its per-machine state.
    """
    local = (".plans/", ".claude/", ".obsidian/")
    assert not [name for name in _files() if name.startswith(local)]
    assert not [name for name in _files() if name.startswith(".specify/") and name.endswith("feature.json")]
