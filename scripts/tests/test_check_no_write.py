"""Tests for scripts/check_no_write.py.

The authority for read/write is opencli's OWN published `access:` field, not a
list we maintain — a maintained list goes stale the day a new command ships and
the staleness is invisible. These fixtures are trimmed copies of real
`opencli <site> --help -f yaml` output from 2026-08-09.
"""
import json

import check_no_write as cnw

BOSS_HELP = """site: boss
command_count: 5
commands:
  - name: search
    access: read
  - name: detail
    access: read
  - name: greet
    access: write
  - name: batchgreet
    access: write
  - name: login
    access: write
"""

INDEED_HELP = """site: indeed
command_count: 2
commands:
  - name: job
    access: read
    aliases:
      - detail
      - view
  - name: search
    access: read
"""

JOB51_HELP = """site: 51job
command_count: 2
commands:
  - name: search
    access: read
  - name: detail
    access: read
"""


def build(tmp_path, records):
    cache = tmp_path / "raw" / "opencli-help"
    cache.mkdir(parents=True)
    (cache / "boss.yaml").write_text(BOSS_HELP, encoding="utf-8")
    (cache / "indeed.yaml").write_text(INDEED_HELP, encoding="utf-8")
    (cache / "51job.yaml").write_text(JOB51_HELP, encoding="utf-8")
    with (tmp_path / "journal.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return tmp_path


def run(tmp_path):
    return cnw.main(["--workspace", str(tmp_path), "--no-fetch"])


CLEAN = [
    {"action": "adapter_call", "site": "51job", "command": "search",
     "exit_code": 0, "classification": "ok",
     "command_line": "opencli 51job search 算法工程师 --limit 20 -f json"},
    {"action": "adapter_call", "site": "51job", "command": "detail",
     "exit_code": 0, "classification": "ok",
     "command_line": "opencli 51job detail 173199597 -f json"},
    {"action": "adapter_call", "site": "indeed", "command": "detail",
     "exit_code": 0, "classification": "ok",
     "command_line": "opencli indeed detail 152875498075cf99 -f json"},
    {"action": "tool_call",
     "command_line": "opencli auth status --site boss,linkedin -f json"},
    {"action": "tool_call", "command_line": "opencli boss --help -f yaml"},
    {"action": "gate", "gate": "check_shortlist", "verdict": "pass"},
]


def test_a_read_only_journal_is_completely_quiet(tmp_path, capsys):
    build(tmp_path, CLEAN)
    assert run(tmp_path) == 0
    assert capsys.readouterr().out == ""


def test_alias_resolves_to_its_canonical_read_command(tmp_path):
    # `indeed detail` is an ALIAS of `indeed job`; only the canonical entry
    # carries access:. Resolving via the alias must not fail closed.
    build(tmp_path, CLEAN)
    assert cnw.resolve_access(
        "indeed", "detail", tmp_path / "raw" / "opencli-help", False) == "read"


def test_greet_recorded_as_an_adapter_call_fails(tmp_path, capsys):
    build(tmp_path, CLEAN + [
        {"action": "adapter_call", "site": "boss", "command": "greet",
         "exit_code": 0, "classification": "ok"},
    ])
    assert run(tmp_path) == 1
    out = capsys.readouterr().out
    assert out.startswith("WRITE_COMMAND:")
    assert "opencli boss greet" in out
    assert "access: write" in out


def test_greet_hidden_in_a_command_line_only_record_fails(tmp_path, capsys):
    build(tmp_path, CLEAN + [
        {"action": "note",
         "command_line": "opencli boss greet --job-id abc --text 'hello'"},
    ])
    assert run(tmp_path) == 1
    assert "WRITE_COMMAND:" in capsys.readouterr().out


def test_profile_prefix_does_not_hide_a_write(tmp_path, capsys):
    build(tmp_path, CLEAN + [
        {"action": "note",
         "command_line": "opencli --profile n4drczmg boss batchgreet --limit 5"},
    ])
    assert run(tmp_path) == 1
    assert "opencli boss batchgreet" in capsys.readouterr().out


def test_an_unknown_site_fails_closed(tmp_path, capsys):
    build(tmp_path, CLEAN + [
        {"action": "adapter_call", "site": "zhilian", "command": "search",
         "exit_code": 0, "classification": "ok"},
    ])
    assert run(tmp_path) == 1
    out = capsys.readouterr().out
    assert "UNKNOWN_ACCESS:" in out
    assert "opencli zhilian search" in out


def test_auth_refresh_is_not_silently_allowed(tmp_path, capsys):
    # The `auth` namespace publishes NO access: field, so only `auth status`
    # is allow-listed. Anything else in that namespace fails closed.
    build(tmp_path, CLEAN + [
        {"action": "note", "command_line": "opencli auth refresh --all"},
    ])
    assert run(tmp_path) == 1
    assert "UNKNOWN_ACCESS:" in capsys.readouterr().out


def test_an_unparsable_journal_line_is_reported(tmp_path, capsys):
    build(tmp_path, CLEAN)
    with (tmp_path / "journal.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{ this is not json\n")
    assert run(tmp_path) == 1
    assert "UNPARSABLE_JOURNAL_LINE:" in capsys.readouterr().out


def test_missing_journal_exits_2_and_still_leaves_a_receipt(tmp_path, capsys):
    # Exit-2 discipline: the workspace exists, so exactly one receipt is
    # written, with verdict could_not_run. A gate that exits silently is
    # indistinguishable from a gate nobody ran.
    (tmp_path / "raw" / "opencli-help").mkdir(parents=True)
    assert run(tmp_path) == 2
    assert "journal.jsonl" in capsys.readouterr().err
    lines = (tmp_path / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    receipt = json.loads(lines[0])
    assert receipt["gate"] == "check_no_write"
    assert receipt["verdict"] == "could_not_run"


def test_a_missing_workspace_directory_exits_2_with_no_receipt(tmp_path, capsys):
    # The ONE case with no receipt: there is no directory to append to. The
    # gate's docstring says so, and this pins it, so the two exit-2 shapes
    # stay distinguishable to whoever reads the journal afterwards.
    missing = tmp_path / "nope"
    assert cnw.main(["--workspace", str(missing), "--no-fetch"]) == 2
    assert "workspace not found" in capsys.readouterr().err
    assert not missing.exists()


def test_exactly_one_receipt_is_appended(tmp_path):
    build(tmp_path, CLEAN)
    before = len((tmp_path / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines())
    assert run(tmp_path) == 0
    lines = (tmp_path / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(lines) == before + 1
    receipt = json.loads(lines[-1])
    assert receipt["action"] == "gate"
    assert receipt["gate"] == "check_no_write"
    assert receipt["verdict"] == "pass"


def test_parse_command_line_edge_cases():
    assert cnw.parse_command_line(
        "opencli 51job search 算法工程师 --limit 2") == ("51job", "search")
    assert cnw.parse_command_line("opencli boss --help -f yaml") is None
    assert cnw.parse_command_line("opencli auth status -f json") == ("auth", "status")
    assert cnw.parse_command_line("python3 scripts/check_shortlist.py") is None
    assert cnw.parse_command_line("") is None
    assert cnw.parse_command_line(
        "/Users/x/.local/bin/opencli boss greet") == ("boss", "greet")
