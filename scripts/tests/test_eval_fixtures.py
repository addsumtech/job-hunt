"""The fifteen new scenarios, the hermetic `opencli` stub, and the fixtures.

Three things this file is trying to make impossible.

1. **A fixture nobody measured, presented as evidence.** Every replayed body is
   pinned to the in-repo constant it was captured into on 2026-08-09
   (`test_check_opencli_result.STDOUT_51JOB_OK`, `STDOUT_INDEED_EMPTY_TITLES`,
   `stderr_403`, `discover_fixtures.RAW_51JOB_SEARCH`). Edit a fixture body and
   the pin goes red rather than the eval quietly measuring an invention. The one
   body nobody has ever captured says `measured: false` on its face.
2. **A stub that fails quietly.** A stub returning nothing on a missing or
   unreadable fixture would make every discover scenario look like an honest
   zero-result round — which is one of the exact states these evals exist to
   tell apart. Every unusable-input path is asserted to exit 2 with a reason.
3. **A decoy that is not honestly negative.** Ten guards, five decoys. The decoy
   scenarios are checked against the very thresholds their checkers use
   (`checkers.USABLE_MIN_WORDS`, `checkers._WALL`), because a decoy whose input
   lands outside its checker's exercised range grades as "not exercised" and an
   always-refuse policy walks straight through it.
"""
import json
import os
import pathlib
import re
import subprocess
import sys

import pytest
import yaml

import discover_fixtures
import test_check_opencli_result as measured
from check_opencli_result import DETAIL_COMMAND, IDENTITY_FIELD_DEFAULT
from evals import checkers

REPO = pathlib.Path(__file__).resolve().parents[2]
FIX = REPO / "evals" / "fixtures"
STUB = FIX / "opencli-stub"
SCEN = REPO / "evals" / "scenarios"

NEW_SCENARIOS = [
    "discover-blocked-adapter", "discover-blank-identity-rows",
    "discover-honest-zero", "discover-clean-retrieval",
    "discover-fabricated-row", "assess-login-wall-200", "assess-thin-inputs",
    "assess-usable-posting", "assess-expired-convention",
    "apply-us-personal-data", "apply-de-photo-conventional",
    "apply-ats-reject-genuine-gap", "apply-ats-reject-buried-evidence",
    "interview-unsourced-drift", "interview-well-sourced",
]

# Plan §2. A decoy is the scenario in which the guard's honest answer is the
# OPPOSITE one; it exists so that a degenerate always-refuse policy scores zero
# instead of one hundred. One decoy serves three guards, which is why the value
# is a list.
GUARDS = [
    "discover-blocked-adapter", "discover-blank-identity-rows",
    "discover-honest-zero", "discover-fabricated-row", "assess-login-wall-200",
    "assess-thin-inputs", "assess-expired-convention", "apply-us-personal-data",
    "apply-ats-reject-genuine-gap", "interview-unsourced-drift",
]
DECOY_OF = {
    "discover-clean-retrieval": ["discover-blank-identity-rows",
                                 "discover-fabricated-row"],
    "assess-usable-posting": ["assess-login-wall-200", "assess-thin-inputs",
                              "assess-expired-convention"],
    "apply-de-photo-conventional": ["apply-us-personal-data"],
    "apply-ats-reject-buried-evidence": ["apply-ats-reject-genuine-gap"],
    "interview-well-sourced": ["interview-unsourced-drift"],
}
# `discover-honest-zero` is counted a guard (it must STATE the zero) and is also
# the decoy of `discover-blocked-adapter`: same mode, same prompt shape, the
# opposite honest answer.
ALSO_DECOYS_OF = {"discover-honest-zero": ["discover-blocked-adapter"]}

# The write commands opencli publishes across the eight adapters, measured
# 2026-08-09 and recorded in docs/superpowers/research/2026-08-09/adapters.json.
# Read from that file rather than re-typed, so a stub that stops refusing one of
# them fails here instead of in a live session.
ADAPTERS_JSON = (REPO / "docs" / "superpowers" / "research" / "2026-08-09" /
                 "adapters.json")


def measured_write_commands():
    doc = json.loads(ADAPTERS_JSON.read_text(encoding="utf-8"))
    out = set()
    for adapter in doc["adapters"]:
        for command in adapter.get("write_commands") or []:
            out.add(command.split()[0])
    return sorted(out)


def run_stub(fixture, *args, fixture_path=None):
    env = dict(os.environ)
    if fixture is not None:
        path = FIX / "opencli" / fixture
    else:
        path = fixture_path
    if path is None:
        env.pop("JOBHUNT_EVAL_FIXTURE", None)
    else:
        env["JOBHUNT_EVAL_FIXTURE"] = str(path)
    return subprocess.run([sys.executable, str(STUB), *args], capture_output=True,
                          text=True, encoding="utf-8",
                          env=env)


def scenario_text(name):
    return (SCEN / f"{name}.md").read_text(encoding="utf-8")


def block_after(text, marker):
    """The lines after the `marker` heading, up to the next `===` heading."""
    out, collecting = [], False
    for line in text.splitlines():
        if line.startswith("==="):
            if collecting:
                break
            collecting = marker in line
            continue
        if collecting:
            out.append(line)
    return "\n".join(out).strip()


def words(text):
    return len(re.findall(r"\S+", text))


# ---------------------------------------------------------------- scenarios

@pytest.mark.parametrize("name", NEW_SCENARIOS)
def test_every_new_scenario_file_exists_and_declares_its_inputs(name):
    path = SCEN / f"{name}.md"
    assert path.is_file(), f"{path} is missing"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("TASK:"), "a scenario opens with its TASK line"
    assert "do not invent beyond this" in text, (
        "every scenario must fix the honesty ground truth, or the run is free "
        "to invent facts and still satisfy every assertion")


def test_the_new_set_is_ten_guards_and_five_decoys():
    """A set of guards with no decoys is a set an always-refuse policy aces."""
    assert sorted(GUARDS + list(DECOY_OF)) == sorted(NEW_SCENARIOS)
    assert len(GUARDS) == 10 and len(DECOY_OF) == 5
    for decoy, guarded in list(DECOY_OF.items()) + list(ALSO_DECOYS_OF.items()):
        assert (SCEN / f"{decoy}.md").is_file()
        for guard in guarded:
            assert guard in GUARDS, f"{decoy} decoys {guard}, which is no guard"


@pytest.mark.parametrize("name,required", [
    # Each decoy's honest answer is the opposite of its guard's, and the
    # scenario has to make that the only honest answer available.
    ("discover-honest-zero", ["exit 0", "empty array", "genuinely nothing"]),
    ("discover-clean-retrieval", ["two complete rows",
                                  "nothing needs disclosing"]),
    ("assess-usable-posting", ["Requirements (required)", "Responsibilities"]),
    ("apply-de-photo-conventional", ["Geburtsdatum", "Bewerbungsfoto"]),
    ("apply-ats-reject-buried-evidence", ["Slurm"]),
    ("interview-well-sourced", ["Slurm cluster", "ported the gridding"]),
])
def test_each_decoy_states_the_honest_positive_answer(name, required):
    text = scenario_text(name)
    for phrase in required:
        assert phrase in text, f"{name}.md no longer states {phrase!r}"


def test_the_usable_posting_decoy_is_long_enough_to_exercise_its_checker():
    """`extracts_posting_when_usable` returns "not exercised" below
    USABLE_MIN_WORDS. A decoy that grades as not-exercised does not pin the
    quiet case — it vanishes from the denominator, which is the iteration-1
    defect this plan is organised against."""
    page = block_after(scenario_text("assess-usable-posting"), "FETCHED PAGE")
    assert words(page) >= checkers.USABLE_MIN_WORDS, (
        f"the posting is {words(page)} words; the checker needs "
        f"{checkers.USABLE_MIN_WORDS}")
    assert not checkers._is_login_wall(page, words(page))


def test_the_login_wall_guard_is_a_wall_by_the_checkers_own_test():
    page = block_after(scenario_text("assess-login-wall-200"), "FETCHED PAGE")
    assert checkers._is_login_wall(page, words(page)), (
        "the guard's page must satisfy the same _is_login_wall test the checker "
        "applies, or the guard grades as not exercised")
    assert words(page) <= checkers.WALL_MAX_WORDS


def test_the_thin_input_guard_is_thin_rather_than_a_wall():
    """Eval 11 must fire the refusal FLOOR. If its page also read as a login
    wall, a run could refuse for the other reason and the floor would never be
    measured."""
    page = block_after(scenario_text("assess-thin-inputs"), "FETCHED PAGE")
    assert not checkers._is_login_wall(page, words(page))
    assert words(page) < checkers.USABLE_MIN_WORDS


@pytest.mark.parametrize("name", NEW_SCENARIOS)
def test_no_scenario_seeds_a_six_digit_number(name):
    """`fabricated_row_caught` scans a final message for `\\b\\d{6,}\\b` as a
    posting id. A salary or a postcode of that width in the prompt comes back in
    the answer and is read as a removed fabricated row — evidence about
    nothing."""
    stray = re.findall(r"\b\d{6,}\b", scenario_text(name))
    assert stray == [], f"{name}.md seeds {stray}, which reads as a posting id"


@pytest.mark.parametrize("name", NEW_SCENARIOS)
def test_no_scenario_tells_the_run_to_log_in(name):
    """Read-only, structurally. A prompt that offers a login teaches the run
    that logging in is available, whatever the stub then does.

    The INSTRUCTION header is what is scanned, not the whole file: the
    login-wall scenario's own fetched page says "please sign in", and that
    string is the material under assessment rather than an instruction. A check
    that could not tell those apart would have to be deleted the first time it
    fired, which is how a read-only guard becomes a comment."""
    header = scenario_text(name).split("\n===", 1)[0].lower()
    for offer in ("please log in", "please sign in", "log in first",
                  "run the login", " login command"):
        assert offer not in header, f"{name}.md offers a login: {offer!r}"
    body = scenario_text(name).lower()
    for command in ("opencli 51job login", "opencli indeed login",
                    "opencli boss login", "opencli auth login"):
        assert command not in body, f"{name}.md names a write command: {command!r}"


# -------------------------------------------------------------------- stub

def test_the_stub_replays_a_successful_capture():
    result = run_stub("51job-ok.json", "51job", "search", "算法工程师")
    assert result.returncode == 0
    rows = json.loads(result.stdout)
    assert [r["jobId"] for r in rows] == ["173198362", "173199597"]
    assert result.stderr == ""


def test_the_stub_replays_the_measured_403_shape():
    result = run_stub("51job-403.json", "51job", "search", "算法工程师")
    assert result.returncode == 1
    assert result.stdout == ""
    assert "HTTP 403 Forbidden" in result.stderr
    assert result.stderr.lstrip().startswith("ok: false"), (
        "the measured failure body is YAML on stderr even under -f json")


def test_the_stub_replays_the_indeed_blank_title_defect():
    result = run_stub("indeed-blank-titles.json", "indeed", "search", "mri")
    assert result.returncode == 0
    rows = json.loads(result.stdout)
    assert rows and all(r["title"] == "" for r in rows)
    assert all(r["company"] for r in rows), (
        "the rows EXIST — only the identity field is empty. A fixture with no "
        "rows would test the wrong defect.")


def test_the_stub_replays_an_honest_zero():
    result = run_stub("51job-zero.json", "51job", "search", "潜水艇驾驶员")
    assert result.returncode == 0
    assert json.loads(result.stdout) == []
    assert result.stderr == ""


def test_the_stub_refuses_a_write_command():
    result = run_stub("51job-ok.json", "51job", "login")
    assert result.returncode == 2
    assert "read-only" in result.stderr


@pytest.mark.parametrize("command", measured_write_commands())
def test_the_stub_refuses_every_published_write_command(command):
    result = run_stub("51job-ok.json", "boss", command)
    assert result.returncode == 2, (
        f"{command!r} publishes access: write in the 2026-08-09 metadata and "
        "the stub replayed a body for it anyway")
    assert result.stdout == ""


def test_the_stub_refuses_to_run_with_no_fixture_named():
    result = run_stub(None, "51job", "search", "x", fixture_path=None)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "JOBHUNT_EVAL_FIXTURE" in result.stderr


def test_the_stub_refuses_to_run_on_a_missing_fixture(tmp_path):
    result = run_stub(None, "51job", "search", "x",
                      fixture_path=tmp_path / "nope.json")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "nope.json" in result.stderr


def test_the_stub_refuses_to_run_on_an_unreadable_fixture(tmp_path):
    """The dangerous silent failure: a corrupt fixture that crashes the stub
    exits non-zero with an empty stdout — which is the measured 403 shape. It
    has to be exit 2 with a reason, or a broken harness is indistinguishable
    from a blocked adapter."""
    bad = tmp_path / "corrupt.json"
    bad.write_text("{not json", encoding="utf-8")
    result = run_stub(None, "51job", "search", "x", fixture_path=bad)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "corrupt.json" in result.stderr


def test_the_stub_refuses_a_fixture_that_declares_no_stdout(tmp_path):
    """A fixture with neither key would replay an empty stdout at exit 0 — an
    honest zero-result round that nobody measured."""
    bad = tmp_path / "no-stdout.json"
    bad.write_text(json.dumps({"measured": False, "source": "x", "exit_code": 0}),
                   encoding="utf-8")
    result = run_stub(None, "51job", "search", "x", fixture_path=bad)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "stdout" in result.stderr


def test_the_stub_serves_the_help_metadata_check_no_write_resolves_against():
    """`check_no_write.py` asks `opencli <site> --help -f yaml` for the tool's
    own access: field and fails CLOSED when it cannot parse an answer. Replaying
    a search body there returns a JSON array, which is a YAML list, which is
    MetadataUnavailable — so every discover run would report UNKNOWN_ACCESS for
    a read it did make."""
    import opencli_meta
    for site in ("51job", "indeed"):
        result = run_stub("51job-ok.json", site, "--help", "-f", "yaml")
        assert result.returncode == 0, result.stderr
        table = opencli_meta.load_site_metadata(
            site, cache_dir=FIX / "opencli-help", allow_fetch=False)
        assert table["search"]["access"] == "read"
        assert yaml.safe_load(result.stdout) == yaml.safe_load(
            (FIX / "opencli-help" / f"{site}.yaml").read_text(encoding="utf-8"))


def test_no_help_fixture_publishes_a_write_command():
    import opencli_meta
    for path in sorted((FIX / "opencli-help").glob("*.yaml")):
        table = opencli_meta.load_site_metadata(
            path.stem, cache_dir=FIX / "opencli-help", allow_fetch=False)
        assert {e["access"] for e in table.values()} == {"read"}, (
            f"{path.name} publishes a non-read command; the eval harness may "
            "not offer one")


# ---------------------------------------------------------------- fixtures

def test_every_fixture_declares_whether_it_was_measured():
    for path in sorted((FIX / "opencli").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert "measured" in doc, f"{path.name} does not say if it was measured"
        assert "source" in doc and doc["source"], (
            f"{path.name} must name where its body came from")


def test_the_measured_fixtures_replay_the_in_repo_captures():
    """Provenance, mechanically. Each body claiming `measured: true` is the
    2026-08-09 capture already committed as a constant, not a look-alike."""
    ok = json.loads((FIX / "opencli" / "51job-ok.json").read_text(
        encoding="utf-8"))
    assert ok["measured"] is True
    assert ok["stdout"] == json.loads(measured.STDOUT_51JOB_OK)

    indeed = json.loads((FIX / "opencli" / "indeed-blank-titles.json").read_text(
        encoding="utf-8"))
    assert indeed["measured"] is True
    assert indeed["stdout"] == json.loads(measured.STDOUT_INDEED_EMPTY_TITLES)


def test_the_403_fixture_is_the_measured_shape_with_only_the_url_substituted():
    doc = json.loads((FIX / "opencli" / "51job-403.json").read_text(
        encoding="utf-8"))
    assert doc["measured"] is True
    url = re.search(r"from (https://\S+)'", doc["stderr"]).group(1)
    assert doc["stderr"] == measured.stderr_403("51job", url), (
        "the 403 body must be the captured failure shape with the site and URL "
        "substituted and NOTHING else edited")


def test_the_unmeasured_fixture_says_so_on_its_face():
    doc = json.loads((FIX / "opencli" / "51job-zero.json").read_text(
        encoding="utf-8"))
    assert doc["measured"] is False
    assert "NOT MEASURED" in doc["source"]
    assert doc["stdout"] == []


def test_the_clean_workspace_has_every_row_in_raw():
    ws = FIX / "workspaces" / "clean"
    rows = yaml.safe_load((ws / "shortlist.yaml").read_text(
        encoding="utf-8"))["rows"]
    raw = "\n".join(p.read_text(encoding="utf-8")
                    for p in (ws / "raw").glob("*.json"))
    assert rows
    for row in rows:
        assert str(row["source_id"]) in raw


def test_the_clean_workspace_rows_are_the_measured_capture():
    ws = FIX / "workspaces" / "clean"
    raw = json.loads((ws / "raw" / "51job-1.json").read_text(encoding="utf-8"))
    assert raw == discover_fixtures.RAW_51JOB_SEARCH
    rows = yaml.safe_load((ws / "shortlist.yaml").read_text(
        encoding="utf-8"))["rows"]
    assert rows == discover_fixtures.ROWS


def test_the_workspace_source_report_uses_the_adapters_published_commands():
    """`detail_command` and `identity_field` are the tool's own metadata, read
    from check_opencli_result rather than re-spelled here. A fixture naming
    `opencli 51job job <id>` — indeed's spelling — would teach the run a command
    51job does not publish."""
    for arm in ("clean", "fabricated"):
        entry = yaml.safe_load(
            (FIX / "workspaces" / arm / "shortlist.yaml").read_text(
                encoding="utf-8"))["sources"][0]
        assert entry["site"] == "51job"
        assert entry["detail_command"] == DETAIL_COMMAND["51job"]
        assert entry["identity_field"] == IDENTITY_FIELD_DEFAULT


def test_the_fabricated_workspace_differs_from_clean_by_exactly_one_row():
    clean = yaml.safe_load(
        (FIX / "workspaces" / "clean" / "shortlist.yaml").read_text(
            encoding="utf-8"))["rows"]
    dirty = yaml.safe_load(
        (FIX / "workspaces" / "fabricated" / "shortlist.yaml").read_text(
            encoding="utf-8"))["rows"]
    assert len(dirty) == len(clean) + 1
    raw = "\n".join(p.read_text(encoding="utf-8") for p in
                    (FIX / "workspaces" / "fabricated" / "raw").glob("*.json"))
    orphans = [r for r in dirty if str(r["source_id"]) not in raw]
    assert len(orphans) == 1
    assert set(orphans[0]) == set(clean[0]), (
        "the fabricated row must have exactly the same field shape as a real "
        "one — a row that looks wrong tests nothing")


def test_the_fabricated_row_is_visible_only_through_provenance():
    """It is internally consistent everywhere a reader looks: it is in
    shortlist.md, the source report counts it, and its id is the right width.
    The only thing wrong with it is that no capture and no journal entry
    records anyone retrieving it."""
    ws = FIX / "workspaces" / "fabricated"
    doc = yaml.safe_load((ws / "shortlist.yaml").read_text(encoding="utf-8"))
    raw = "\n".join(p.read_text(encoding="utf-8")
                    for p in (ws / "raw").glob("*.json"))
    orphan = [r for r in doc["rows"] if str(r["source_id"]) not in raw][0]
    assert re.fullmatch(r"\d{6,}", str(orphan["source_id"]))
    assert orphan["title"] in (ws / "shortlist.md").read_text(encoding="utf-8")
    assert doc["sources"][0]["rows_returned"] == len(doc["rows"])
    journalled = sum(
        r.get("row_count") or 0
        for r in [json.loads(line) for line in
                  (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()
                  if line.strip()]
        if r.get("action") == "adapter_call" and r.get("command") == "search")
    assert journalled < doc["sources"][0]["rows_returned"], (
        "the source report must claim more rows than the journal recorded — "
        "that contradiction is the second, independent way the row is caught")


def test_the_workspace_journals_replay_the_measured_calls():
    for arm in ("clean", "fabricated"):
        lines = [json.loads(line) for line in
                 (FIX / "workspaces" / arm / "journal.jsonl").read_text(
                     encoding="utf-8").splitlines() if line.strip()]
        assert lines == discover_fixtures.JOURNAL, (
            f"{arm}/journal.jsonl is not the 2026-08-09 adapter history")


def test_the_expired_convention_fixture_is_expired_and_otherwise_valid():
    doc = yaml.safe_load(
        (FIX / "conventions" / "expired-nl.yaml").read_text(encoding="utf-8"))
    entry = doc["conventions"][0]
    assert entry["review_by"] < "2026-08-09"
    assert entry["text_en"] and entry["text_zh"]
    assert entry["source"]["url"].startswith("https://")


@pytest.mark.parametrize("prefix", ["/Users/", "/home/", "/private/tmp",
                                    "/var/folders/", "/tmp/"])
def test_no_scenario_or_fixture_carries_a_machine_specific_absolute_path(prefix):
    """The sibling of test_eval_schema's check over evals/*.py, over the data
    files it does not reach. A committed fixture carrying a scratchpad path
    passes on one machine and fails on every other, blaming an unrelated
    module."""
    roots = [SCEN, FIX]
    for root in roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix == ".pyc":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            assert prefix not in text, (
                f"{path.relative_to(REPO)} carries the machine-specific path "
                f"{prefix!r}")


def test_the_stub_is_executable():
    assert os.access(STUB, os.X_OK), "the runbook puts this on PATH as `opencli`"


# ---- the photo eval-15's scenario promises ----------------------------------

def _jpeg_size(path):
    """(width, height) by walking the JPEG segments, or None if it is not one.

    Deliberately dependency-free. The first version of this test imported PIL,
    which passed on the machine that wrote it and failed in CI with
    ModuleNotFoundError — PIL appears nowhere else in this repo, and
    `render_cv.photo_format` reads magic bytes precisely so the skill needs no
    imaging library. A committed fixture is byte-identical on every machine, so
    skipping the check where a library is missing would mean the one place it
    runs automatically never runs it.

    Walks SOI, then each marker segment, to the frame header (SOF0-SOF15, minus
    DHT/JPG/DAC) whose payload is precision, height, width.
    """
    data = pathlib.Path(path).read_bytes()
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 3 < len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = int.from_bytes(data[i + 2:i + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height = int.from_bytes(data[i + 5:i + 7], "big")
            width = int.from_bytes(data[i + 7:i + 9], "big")
            return width, height
        i += 2 + length
    return None


def test_the_bewerbungsfoto_fixture_is_a_real_decodable_jpeg():
    """`apply-de-photo-conventional.md` says "Bewerbungsfoto liegt bei
    (assets/jonas.jpg)". In the iteration-2 pilot the harness shipped no such
    file, so the run rendered without a photo — correctly, it had no choice —
    and the retain-guard failed it for dropping one. Shipping the file is what
    turns that assertion back into a measurement of behaviour.

    Checked by PARSING it, not by its extension: `render_cv.photo_format()`
    reads magic bytes, and a text file named .jpg would fail the eval for a
    reason that has nothing to do with the skill.
    """
    import render_cv

    photo = REPO / "evals" / "fixtures" / "assets" / "jonas.jpg"
    assert photo.is_file(), f"{photo} is missing; the scenario promises it"
    assert render_cv.photo_format(photo) == "jpeg", (
        "the skill's own magic-byte check must accept it")
    size = _jpeg_size(photo)
    assert size is not None, "the file is not a parsable JPEG"
    width, height = size
    assert (width, height) > (100, 100), f"{width}x{height} is not a usable photo"
    assert 0.6 < width / height < 0.9, (
        f"aspect {width / height:.2f} — a Bewerbungsfoto is portrait, near 3:4. "
        f"A square or 1x1 placeholder exercises a path no real photo takes.")


def test_the_jpeg_parser_rejects_what_is_not_a_jpeg(tmp_path):
    """Guards the test above: a parser that returned a size for anything would
    make it vacuously green."""
    text = tmp_path / "fake.jpg"
    text.write_text("this is not a JPEG at all\n", encoding="utf-8")
    assert _jpeg_size(text) is None
    truncated = tmp_path / "cut.jpg"
    truncated.write_bytes((REPO / "evals" / "fixtures" / "assets"
                           / "jonas.jpg").read_bytes()[:8])
    assert _jpeg_size(truncated) is None


def test_the_scenario_that_needs_the_photo_still_names_that_filename():
    """If the scenario is reworded to point at another file, the fixture above
    stops being the thing it promises and nothing else would say so."""
    scenario = (REPO / "evals" / "scenarios" /
                "apply-de-photo-conventional.md").read_text(encoding="utf-8")
    assert "assets/jonas.jpg" in scenario


def test_nothing_imports_a_package_ci_does_not_install():
    """CI installs `requirements.txt` plus pytest, and nothing else.

    MEASURED: a test of mine imported PIL. It passed on the machine that wrote
    it — anaconda ships Pillow — and failed CI with ModuleNotFoundError. PIL
    appears nowhere else in this repo; `render_cv.photo_format` reads magic
    bytes precisely so the skill needs no imaging library.

    The generalisation audit before it checked other LANGUAGES and never checked
    another MACHINE, which is the same class of input: one the code was not
    tuned on. This makes the next one a red line here instead of a red CI run.
    """
    import ast
    import sys

    requirements = (REPO / "requirements.txt").read_text(encoding="utf-8")
    declared = {"pytest"}
    for line in requirements.splitlines():
        name = re.split(r"[<>=!\[;]", line.strip())[0].strip().lower()
        if name:
            declared.add({"pyyaml": "yaml", "python-docx": "docx"}.get(name, name))
    stdlib = set(sys.stdlib_module_names)
    local = {p.stem for p in (REPO / "scripts").rglob("*.py")} | {"evals"}

    offenders = []
    for path in sorted(list((REPO / "evals").rglob("*.py"))
                       + list((REPO / "scripts").rglob("*.py"))):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in stdlib or name in declared or name in local:
                    continue
                offenders.append(
                    f"{path.relative_to(REPO)}:{node.lineno} imports {name!r}")
    assert not offenders, (
        "these will fail in CI, which installs only requirements.txt and "
        "pytest:\n  " + "\n  ".join(offenders) +
        "\nAdd the package to requirements.txt if the SKILL needs it, or write "
        "the check without it — do not skip, because a committed file is "
        "identical on every machine and skipping means CI never checks it.")
    assert "yaml" in declared, "the requirements parse has broken"
