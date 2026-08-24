"""`Run` -- the read-only view of one eval run directory.

Two properties get pinned harder than the accessors themselves, because they are
the ones whose failure is silent:

* **read-only.** Every accessor is called against a fixture directory and the
  directory is then compared byte-for-byte. A harness that creates an empty
  `outputs/` while grading has changed the artifact it is measuring.
* **the results root is outside the repo.** Runs carry a real person's profile
  data. The quiet case (the default, and a legitimate override) is pinned as hard
  as the firing case (an override pointing into the repo), because a safety check
  that fires on correct input is a safety check somebody switches off.
"""
import json
import pathlib
import sys

import pytest

# evals/ is importable from the repo root. scripts/tests/conftest.py gains this
# insert in Task 1 of the eval-rebuild plan; until that lands the module does it
# itself, and the insert is idempotent either way.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals import runlib  # noqa: E402


@pytest.fixture
def run_dir(tmp_path):
    out = tmp_path / "eval-5" / "with_skill" / "run-1" / "outputs"
    (out / "workspace" / "raw").mkdir(parents=True)
    (out / "final-message.md").write_text(
        "本轮 51job 返回 403，未取得真实岗位。\n输出为方向级 shortlist。\n",
        encoding="utf-8")
    (out / "RUN_NOTES.md").write_text("no notes\n", encoding="utf-8")
    (out / "workspace" / "shortlist.md").write_text(
        "## §0.2 披露\n\n取得真实岗位：        否\n", encoding="utf-8")
    (out / "workspace" / "shortlist.yaml").write_text(
        "rows: []\nshortfall_reason: adapter 403\n", encoding="utf-8")
    (out / "workspace" / "journal.jsonl").write_text(
        json.dumps({"action": "adapter_call", "site": "51job", "exit_code": 1,
                    "classification": "not_logged_in", "row_count": 0}) + "\n"
        + json.dumps({"action": "gate", "gate": "check_shortlist",
                      "verdict": "pass"}) + "\n"
        + "{ this line is not json\n",
        encoding="utf-8")
    return out.parent


def test_reads_text_relative_to_outputs(run_dir):
    run = runlib.Run(run_dir)
    assert "403" in run.read("final-message.md")
    assert "披露" in run.read("workspace/shortlist.md")


def test_a_missing_file_reads_as_none_rather_than_raising(run_dir):
    assert runlib.Run(run_dir).read("workspace/fit-assessment.md") is None


def test_yaml_and_json_load(run_dir):
    run = runlib.Run(run_dir)
    assert run.load_yaml("workspace/shortlist.yaml")["rows"] == []
    assert run.load_yaml("workspace/nope.yaml") is None


def test_journal_keeps_unparsable_lines_instead_of_dropping_them(run_dir):
    records = runlib.Run(run_dir).journal()
    assert len(records) == 3
    assert records[-1]["_unparsable"].startswith("{ this line")


def test_adapter_calls_and_receipts_filter_by_action(run_dir):
    run = runlib.Run(run_dir)
    assert [c["site"] for c in run.adapter_calls()] == ["51job"]
    assert [r["gate"] for r in run.receipts()] == ["check_shortlist"]
    assert run.receipts("check_no_write") == []


def test_all_text_concatenates_the_reader_facing_surfaces(run_dir):
    text = runlib.Run(run_dir).all_text()
    assert "方向级 shortlist" in text and "取得真实岗位" in text


def test_first_line_containing_returns_the_line_verbatim(run_dir):
    run = runlib.Run(run_dir)
    assert run.first_line_containing("方向级") == "输出为方向级 shortlist。"
    assert run.first_line_containing("zzz") is None


def test_first_line_containing_can_be_scoped_to_one_surface(run_dir):
    """Unscoped, prose wins: the final message says 未取得真实岗位, which CONTAINS
    取得真实岗位, so the sentence is returned ahead of the disclosure row. A
    checker that splits a line on its label to read the ANSWER must scope, or it
    reads 「。」 off a sentence and calls the disclosure filled in."""
    run = runlib.Run(run_dir)
    assert run.first_line_containing("取得真实岗位") == \
        "本轮 51job 返回 403，未取得真实岗位。"
    assert run.first_line_containing(
        "取得真实岗位", rel="workspace/shortlist.md") == "取得真实岗位：        否"
    assert run.first_line_containing("取得真实岗位", rel="workspace/gone.md") is None


def test_iter_runs_walks_every_eval_arm_and_run(tmp_path):
    for eid, arm, n in ((5, "baseline", 1), (5, "with_skill", 1),
                        (5, "with_skill", 2), (7, "baseline", 1)):
        (tmp_path / f"eval-{eid}" / arm / f"run-{n}" / "outputs").mkdir(
            parents=True)
    found = sorted((e, a, n) for e, a, n, _ in runlib.iter_runs(tmp_path))
    assert found == [(5, "baseline", 1), (5, "with_skill", 1),
                     (5, "with_skill", 2), (7, "baseline", 1)]


def test_the_results_root_is_outside_the_repo():
    """A results tree inside the repo is one `git add` away from publishing a
    real person's profile data."""
    assert runlib.REPO_ROOT not in runlib.RESULTS_ROOT.parents
    assert runlib.RESULTS_ROOT != runlib.REPO_ROOT


def test_the_output_contract_names_the_four_required_artifacts():
    assert runlib.OUTPUT_CONTRACT == (
        "final-message.md", "RUN_NOTES.md", "workspace/", "stderr.log")


# --- the results root: the firing case and its quiet twin ----------------------

def test_a_results_root_inside_the_repo_is_refused(tmp_path):
    """The firing case. The message must name the path, or whoever hits it at
    2am has a rule and no offender."""
    inside = tmp_path / "repo" / "evals" / "results"
    with pytest.raises(ValueError) as excinfo:
        runlib.resolve_results_root(env_value=str(inside),
                                    repo_root=tmp_path / "repo")
    assert str(inside.resolve()) in str(excinfo.value)


def test_the_repo_root_itself_is_refused_as_a_results_root(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError):
        runlib.resolve_results_root(env_value=str(repo), repo_root=repo)


def test_a_results_root_beside_the_repo_is_accepted(tmp_path):
    """The quiet twin. `<repo>-workspace/` shares a prefix with the repo path but
    is not inside it -- a check that rejected this one would be switched off."""
    repo = tmp_path / "job-hunt"
    beside = tmp_path / "job-hunt-workspace" / "iteration-2"
    assert runlib.resolve_results_root(env_value=str(beside),
                                       repo_root=repo) == beside.resolve()


def test_the_default_root_is_used_when_the_override_is_unset_or_blank(tmp_path):
    default = tmp_path / "elsewhere"
    for blank in (None, "", "   "):
        assert runlib.resolve_results_root(
            env_value=blank, repo_root=tmp_path / "repo",
            default=default) == default.resolve()


def test_the_override_is_read_from_the_environment(tmp_path, monkeypatch):
    elsewhere = tmp_path / "somewhere-else"
    monkeypatch.setenv(runlib.RESULTS_ROOT_ENV, str(elsewhere))
    assert runlib.resolve_results_root() == elsewhere.resolve()


def test_no_committed_file_of_this_task_carries_a_machine_specific_path():
    """A committed absolute path is correct on exactly one machine. This repo has
    paid for that once already, in a fixture nobody could run."""
    for name in ("evals/runlib.py", "scripts/tests/test_eval_runlib.py"):
        text = (_REPO_ROOT / name).read_text(encoding="utf-8")
        # Assembled from pieces so this test does not fail itself on its own
        # source -- the check is real, not a spelling of the forbidden strings.
        stems = ["/" + part + "/" for part in ("Users", "home", "root")]
        stems += ["/private/" + "tmp/", "/var/" + "folders/", "C:" + "\\"]
        for stem in stems:
            assert stem not in text, f"{name} hard-codes {stem!r}"


# --- read-only means read-only -------------------------------------------------

def _snapshot(root):
    """Every path under root, with file bytes. Directories included, so a created
    empty directory is caught as well as a written byte."""
    snap = {}
    for p in sorted(pathlib.Path(root).rglob("*")):
        rel = str(p.relative_to(root))
        snap[rel] = p.read_bytes() if p.is_file() else "<dir>"
    return snap


def test_every_accessor_leaves_the_run_directory_byte_identical(run_dir):
    before = _snapshot(run_dir)
    run = runlib.Run(run_dir)
    run.path("workspace/shortlist.yaml")
    run.exists("final-message.md")
    run.exists("workspace/nothing-here.md")
    run.read("final-message.md")
    run.read("workspace/absent.md")
    run.load_yaml("workspace/shortlist.yaml")
    run.load_json("workspace/absent.json")
    run.journal()
    run.adapter_calls()
    run.receipts()
    run.receipts("check_shortlist")
    run.all_text()
    run.first_line_containing("403")
    run.glob_workspace("raw/*.json")
    list(runlib.iter_runs(run_dir.parents[1]))
    assert _snapshot(run_dir) == before


def test_a_run_directory_that_does_not_exist_is_not_created_by_reading(tmp_path):
    ghost = tmp_path / "eval-9" / "with_skill" / "run-1"
    run = runlib.Run(ghost)
    assert run.read("final-message.md") is None
    assert run.exists("final-message.md") is False
    assert run.journal() == [] and run.all_text() == ""
    assert run.glob_workspace("*.md") == []
    assert not ghost.exists(), "reading a missing run created it"


# --- path handling -------------------------------------------------------------

@pytest.mark.parametrize("rel", ["../../baseline/run-1/outputs/final-message.md",
                                 "..", "/etc/passwd"])
def test_a_path_that_leaves_the_run_is_refused(run_dir, rel):
    """A checker that can address ../baseline grades the wrong arm and never
    notices."""
    with pytest.raises(ValueError):
        runlib.Run(run_dir).read(rel)


def test_a_dotted_path_that_stays_inside_the_run_still_reads(run_dir):
    """The quiet twin of the escape check: normalising is not forbidding."""
    run = runlib.Run(run_dir)
    assert "403" in run.read("workspace/../final-message.md")
    assert run.exists("workspace/") is True
    assert run.path(".") == run.outputs


def test_a_directory_reads_as_none_rather_than_raising(run_dir):
    assert runlib.Run(run_dir).read("workspace") is None


# --- loaders -------------------------------------------------------------------

def test_load_json_parses_reads_missing_as_none_and_malformed_as_none(run_dir):
    out = run_dir / "outputs"
    (out / "grading-ish.json").write_text('{"passed": null}\n', encoding="utf-8")
    (out / "broken.json").write_text("{not json\n", encoding="utf-8")
    run = runlib.Run(run_dir)
    assert run.load_json("grading-ish.json") == {"passed": None}
    assert run.load_json("absent.json") is None
    assert run.load_json("broken.json") is None


def test_malformed_yaml_is_none_rather_than_an_exception(run_dir):
    (run_dir / "outputs" / "workspace" / "bad.yaml").write_text(
        "rows: [unclosed\n", encoding="utf-8")
    assert runlib.Run(run_dir).load_yaml("workspace/bad.yaml") is None


# --- the journal ---------------------------------------------------------------

def test_a_journal_line_that_is_valid_json_but_not_a_record_is_reported(run_dir):
    """`"just a string"` parses. It is still not a record, and a caller doing
    .get() on it would crash three files away from the corruption."""
    (run_dir / "outputs" / "workspace" / "journal.jsonl").write_text(
        '"just a string"\n[1, 2]\n{"action": "gate", "gate": "check_apply"}\n',
        encoding="utf-8")
    records = runlib.Run(run_dir).journal()
    assert [r.get("_unparsable") for r in records[:2]] == ['"just a string"',
                                                           "[1, 2]"]
    assert [r["gate"] for r in runlib.Run(run_dir).receipts()] == ["check_apply"]


def test_blank_journal_lines_are_not_findings(run_dir):
    """The quiet twin: a trailing newline is not a corrupt journal."""
    (run_dir / "outputs" / "workspace" / "journal.jsonl").write_text(
        '{"action": "gate", "gate": "check_apply"}\n\n\n', encoding="utf-8")
    assert runlib.Run(run_dir).journal() == [{"action": "gate",
                                              "gate": "check_apply"}]


def test_an_absent_journal_is_an_empty_list_not_an_error(tmp_path):
    (tmp_path / "run-1" / "outputs").mkdir(parents=True)
    run = runlib.Run(tmp_path / "run-1")
    assert run.journal() == [] and run.adapter_calls() == [] \
        and run.receipts() == []


# --- iter_runs -----------------------------------------------------------------

def test_iter_runs_orders_evals_and_runs_numerically(tmp_path):
    """Lexicographic order puts eval-10 before eval-2; a reader watching runs
    stream past in that order cannot tell a gap from a sort."""
    for eid, n in ((2, 1), (2, 10), (2, 2), (10, 1)):
        (tmp_path / f"eval-{eid}" / "baseline" / f"run-{n}" / "outputs").mkdir(
            parents=True)
    assert [(e, n) for e, _a, n, _r in runlib.iter_runs(tmp_path)] == [
        (2, 1), (2, 2), (2, 10), (10, 1)]


def test_iter_runs_ignores_paths_that_are_not_runs(tmp_path):
    (tmp_path / "eval-5" / "baseline" / "run-1" / "outputs").mkdir(parents=True)
    (tmp_path / "eval-5" / "baseline" / "run-notes.md").write_text("x")
    (tmp_path / "eval-5" / "baseline" / "run-2").write_text("a file, not a run")
    (tmp_path / "eval-notes").mkdir()
    (tmp_path / "benchmark.json").write_text("{}")
    assert [(e, a, n) for e, a, n, _ in runlib.iter_runs(tmp_path)] == [
        (5, "baseline", 1)]


def test_iter_runs_yields_a_run_bound_to_its_own_directory(tmp_path):
    (tmp_path / "eval-5" / "with_skill" / "run-3" / "outputs").mkdir(parents=True)
    (_e, _a, _n, run), = runlib.iter_runs(tmp_path)
    assert run.dir == tmp_path / "eval-5" / "with_skill" / "run-3"
    assert run.outputs == run.dir / "outputs"


def test_iter_runs_refuses_a_missing_iteration_directory(tmp_path):
    """A silent empty iteration reads as "no runs yet", which is the iteration-1
    defect: a missing arm absorbed into a mean."""
    with pytest.raises(NotADirectoryError):
        list(runlib.iter_runs(tmp_path / "iteration-99"))


def test_an_empty_but_present_iteration_directory_is_simply_empty(tmp_path):
    """The quiet twin: existing-and-empty is a fact about the run tree, not an
    error about the path."""
    assert list(runlib.iter_runs(tmp_path)) == []


# --- glob_workspace ------------------------------------------------------------

def test_glob_workspace_finds_the_run_s_own_captures_sorted(run_dir):
    """Provenance checkers cross-reference every row against raw/*.json; a glob
    that quietly returns nothing turns "no capture backs this row" into "no rows
    to check"."""
    raw = run_dir / "outputs" / "workspace" / "raw"
    for name in ("51job-2.json", "51job-1.json", "notes.md"):
        (raw / name).write_text("{}", encoding="utf-8")
    found = runlib.Run(run_dir).glob_workspace("raw/*.json")
    assert [p.name for p in found] == ["51job-1.json", "51job-2.json"]
    assert runlib.Run(run_dir).glob_workspace("mock/*.md") == []


def test_glob_workspace_on_a_run_without_a_workspace_is_empty(tmp_path):
    (tmp_path / "run-1" / "outputs").mkdir(parents=True)
    assert runlib.Run(tmp_path / "run-1").glob_workspace("*.json") == []


# --- the reader-facing surface set ---------------------------------------------

def test_reader_facing_is_a_subset_of_what_a_human_reads(run_dir):
    """A string buried in a raw capture is not a claim, so all_text must not see
    it -- otherwise every "did the run say X" checker can be satisfied by the
    fixture the run downloaded."""
    (run_dir / "outputs" / "workspace" / "raw" / "51job.json").write_text(
        json.dumps({"note": "no matching jobs"}), encoding="utf-8")
    assert "no matching jobs" not in runlib.Run(run_dir).all_text()


def test_the_results_root_is_absolute_however_it_was_resolved(tmp_path,
                                                              monkeypatch):
    """A relative results root means "wherever this happened to be invoked from",
    which is how one iteration's runs end up in two trees."""
    assert runlib.RESULTS_ROOT.is_absolute()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(runlib.RESULTS_ROOT_ENV, "relative-results")
    resolved = runlib.resolve_results_root()
    assert resolved.is_absolute() and resolved == (tmp_path / "relative-results").resolve()


def test_a_relative_override_that_lands_in_the_repo_is_still_refused(monkeypatch):
    """`--results ./evals/out` from the repo root is the easy way to make this
    mistake, and cwd is what turns it into a path inside the tree."""
    monkeypatch.chdir(_REPO_ROOT)
    monkeypatch.setenv(runlib.RESULTS_ROOT_ENV, "eval-results")
    with pytest.raises(ValueError):
        runlib.resolve_results_root()
