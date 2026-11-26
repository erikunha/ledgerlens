"""The public repository carries no course material, no machine paths of the author, no keys and no Portuguese.

The forbidden words are built from fragments, and the Portuguese markers from escapes, so this file does not
match its own rules.

The shapes of the secrets are the shapes of the scrubber of the repository, read from its own source, so the guard
of the public repository is never narrower than the scrubber. The fakes that the repository carries on purpose are
spared by their exact text, so a real credential is refused wherever it is written.
"""

import ast
import re
import subprocess
import sys
from collections.abc import Callable
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
# A home path written with a tilde is a path of the machine of a person too, and the guard of the public
# repository has to refuse it like the other two shapes. The branch names a directory of the home, because
# the dot folders are conventional names that a platform defines and that a workflow of the continuous
# integration may use without naming the machine of anybody.
HOME_PATH = re.compile("/" + "Users" + "/|/" + "home" + "/[a-z]|~" + "/[A-Za-z]")
SKIP = {"uv.lock", "tests/test_public_clean.py"}

# ---- The secrets -----------------------------------------------------------------------------------
# The scrubber of the repository is the reference: `ledgerlens/observability/callbacks.py` redacts what it writes to
# the observability, and a value that the repository would redact is a value that this guard refuses.
SCRUBBER_SOURCE = ROOT / "ledgerlens" / "observability" / "callbacks.py"


def _the_pattern_of_the_scrubber() -> str:
    """The pattern of the secrets of the scrubber of the repository, read from its own source.

    Why it is read and not written here: a copy of a pattern drifts from the pattern it copies, and the guard of the
    public repository has to stay wider than the scrubber of the repository for as long as the scrubber lives.
    """
    tree = ast.parse(SCRUBBER_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        named = any(isinstance(target, ast.Name) and "SECRET" in target.id for target in node.targets)
        if named and isinstance(node.value, ast.Call) and node.value.args:
            return str(ast.literal_eval(node.value.args[0]))
    raise AssertionError("the scrubber of the repository holds no pattern of the secrets")


# The shapes that the scrubber of the repository does not know, and that the guard adds. They are the shape of a key
# of an account of a provider, the shape of a connection string that carries a password and the shape of an
# assignment of a key in a source or in a configuration.
EXTRA_SECRET_SHAPES: dict[str, str] = {
    "account_key": r"(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{20,}",
    "connection_string": r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s:/@]+:[^\s:/@]{3,}@",
    "key_assignment": r"api_key\s*=\s*['\"][A-Za-z0-9]{16,}",
}
SECRET = re.compile("(" + _the_pattern_of_the_scrubber() + ")|" + "|".join(EXTRA_SECRET_SHAPES.values()))

# The fakes that the repository carries on purpose: the fixtures of the tests of the domain and of the front, the
# documentation of the design package and the text of the scrubber itself. They are spared by their exact text, so a
# real credential is refused wherever it is written and only these exact strings pass.
SECRET_FAKES = frozenset(
    {
        "sk-" + "adjusted",
        "sk-" + "coverage",
        "sk-" + "fakefake1234",
        "sk-" + "first-not-real",
        "sk-" + "second-not-real",
        "sk-" + "sensitive",
        "sk-" + "test-key",
        "sk-" + "test-key-not-real",
        "sk-" + "test-secret-marker",
        "sk-" + "visitor-key-not-real",
        "sk-" + "weighted",
        "sk-" + "weighted-decision-utility",
        # The slug of ADR-087 holds the same shape by accident: the tail of the word "task" followed by a hyphen
        # is the head of the shape of a key of a provider. The fake is the exact text of the slug, so a real
        # credential written anywhere else is still refused.
        "sk-the-identity-of-the-" + "reviewer-is-the-session-and-the-agent-never-decides",
        "Bear" + "er ...",
        "Bear" + "er abc.def-123",
    }
)
# The fakes are matched as a whole word of the alphabet of a secret: a fake that is the prefix of a longer value is
# not a fake, and the value that carries it is refused.
_FAKES = re.compile(
    "|".join(re.escape(fake) + r"(?![A-Za-z0-9_\-])" for fake in sorted(SECRET_FAKES, key=len, reverse=True))
)


def _without_the_fakes(line: str) -> str:
    """The line without the fakes that the repository carries on purpose.

    Why the fakes are taken out and the lines are not spared: a line of the documentation may carry a fake and a real
    credential at the same time, and the real credential has to be refused.
    """
    return _FAKES.sub(" ", line)


# The values that the guard has to refuse, one per shape. They are built from fragments, so this file does not hold
# the shape of a secret in its own text.
BAD_VALUES: dict[str, str] = {
    "provider_key": "sk-" + "proj-abcdefghijklmnopqrstuvwxyz012345",
    "account_key": "sk_" + "live_abcdefghijklmnopqrstuvwxyz012345",
    "tracing_token": "lsv" + "2_pt_abcdefghijklmnopqrstuvwxyz",
    "authorization": "Bear" + "er abcdefghijklmnopqrstuvwx",
    "repository_token": "ghp_" + "abcdefghijklmnopqrstuvwxyz0123456789",
    "cloud_key_id": "AKIA" + "ABCDEFGHIJKLMNOP",
    "search_key": "AIza" + "abcdefghijklmnopqrstuvwxyz0123456789",
    "connection_string": "postgresql://user:" + "hunter2pass@db:5432/x",
    "key_assignment": "api_key = '" + "abcdefghijklmnopqrst'",
}

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


def _offenders(*patterns: re.Pattern[str], prepare: Callable[[str], str] | None = None) -> list[str]:
    """The places where a pattern of the rules matches, line by line.

    Why the line may be prepared before it is read: the guard of the secrets spares the fakes that the repository
    carries on purpose, and it spares them without sparing the rest of the line.
    """
    found = []
    for name in _files():
        for number, line in _lines(name):
            if isinstance(line, str) and any(p.search(prepare(line) if prepare else line) for p in patterns):
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
    assert not _offenders(SECRET, prepare=_without_the_fakes)


def test_the_guard_of_the_secrets_fires_on_a_value_of_every_shape() -> None:
    """Every shape that the guard knows refuses a value of that shape.

    Why the values are built from fragments: this file does not hold the shape of a secret in its own text.
    """
    for shape, value in BAD_VALUES.items():
        assert SECRET.search(_without_the_fakes(value)), shape


def test_the_guard_of_the_secrets_is_never_narrower_than_the_scrubber_of_the_repository() -> None:
    """The guard of the public repository holds the pattern of the scrubber of the repository.

    Why it matters: the scrubber decides what the repository writes to the observability, and the guard decides what
    the repository may hold. A value that the scrubber would redact is a value that the guard has to refuse, and the
    only way to be sure of it is to hold the very pattern of the scrubber.
    """
    assert f"({_the_pattern_of_the_scrubber()})" in SECRET.pattern
    scrubber = re.compile(_the_pattern_of_the_scrubber())
    for value in BAD_VALUES.values():
        if scrubber.search(value):
            assert SECRET.search(value), value


def test_the_guard_of_the_secrets_spares_the_material_of_the_repository() -> None:
    """The material of the repository that carries a shape on purpose passes the guard.

    Why the values are here and not only in the list of the fakes: a shape that the guard refuses and that the
    repository needs is a shape that the guard has to know, and the test says which one.
    """
    for value in (
        "sk-weighted",
        "sk-visitor-key-not-real",
        "Bearer abc.def-123",
        "postgresql://ledgerlens@postgres:5432/ledgerlens_sandbox",
        "postgresql://ledgerlens@127.0.0.1:5433/ledgerlens_sandbox",
    ):
        assert not SECRET.search(_without_the_fakes(value)), value


def test_the_fakes_that_the_guard_spares_are_in_the_repository() -> None:
    """Every fake that the guard spares is a fake that the repository really carries.

    Why it matters: a list of exemptions that grows values nobody writes is a list that hides real credentials, and
    this test keeps the list honest.
    """
    material = "\n".join(
        line for name in _files() for _, line in _lines(name) if isinstance(line, str)
    )
    for fake in SECRET_FAKES:
        assert fake in material, fake


# ---- The dashes ------------------------------------------------------------------------------------
# The rule of the repository is a zero tolerance one: no em dash and no en dash in any file of the repository.
# The two characters are built from escapes, so this file does not match its own rule.
DASHES = re.compile("[\u2013\u2014]")

# The folders that hold the recordings of a real model, the canonical bundles and the published copies.
#
# Why these and no other: the rule of the dashes governs the writing of this repository, and a recording of a real
# model is the writing of the model. The bundle publishes the answer the run gave (ADR-076), so a dash in that
# answer is a fact about the run and not a style of this repository, and the repository never edits the text of a
# run (ADR-080). The recordings of the scripted model are the writing of this repository and stay inside the rule.
DASH_EXEMPT = ("data/eval/replay-real/", "site/replay-real/")


def _dash_offenders() -> list[str]:
    """The places where a dash of the rule is, outside the recordings of a real model."""
    return [hit for hit in _offenders(DASHES) if not hit.startswith(DASH_EXEMPT)]


def test_no_dashes_in_tracked_files():
    """No em dash and no en dash anywhere. The rule is a zero tolerance one."""
    assert not _dash_offenders()


def test_the_dash_rule_spares_the_recordings_of_a_real_model_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recording of a real model may carry a dash; the rest of the repository may not.

    Why the exemption and not the refusal of the recording: the answer of a model is not written to a rule, so a
    recording refused for a dash is a recording that has to be made again, and the catalogue of a real model would
    be published by a coin flip (ADR-080).

    Why the exemption is narrow: the folders of the recordings of the real model are the only ones spared, and the
    recordings of the scripted model and the documentation are inside the rule as they always were.
    """
    recording = "data/eval/replay-real/s11/events.jsonl"
    scripted = "data/eval/replay/s11/events.jsonl"
    documentation = "docs/frontend.md"
    for name in (recording, scripted, documentation):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"the answer carries a dash {chr(0x2014)} here\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    monkeypatch.setattr(sys.modules[__name__], "_files", lambda: [recording, scripted, documentation])

    assert _dash_offenders() == [f"{scripted}:1", f"{documentation}:1"]


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
