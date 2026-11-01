"""Task 6: a master changed only by a recorded online-presence write-back is named as such."""
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_claims
import journal
import online_presence as op

MASTER = {"meta": {"name": "Test User", "language": "en"},
          "skills": {"languages": ["Python"]},
          "experience": [{"title": "Research Engineer", "org": "Acme", "bullets": ["Built Python tools."]}]}


@pytest.fixture
def ws(tmp_path):
    profile_dir = tmp_path / "test-user"
    workspace = profile_dir / "applications" / "acme-engineer-2026-11-01"
    workspace.mkdir(parents=True)
    master = profile_dir / "profile.yaml"
    master.write_text(yaml.safe_dump(MASTER), encoding="utf-8")
    (workspace / "tailored-profile.yaml").write_text(yaml.safe_dump(MASTER), encoding="utf-8")
    assert check_claims.main(["--workspace", str(workspace), "--master", str(master), "--record"]) == 0
    return workspace, master


def record_writeback(master, before, ids=("github:acme/tool",)):
    path = master.parent / "online-presence.yaml"
    record = op.load_record(path)
    record["writebacks"].append({"master": str(master), "before_sha256": before,
                                 "after_sha256": journal.sha256_file(master),
                                 "finding_ids": list(ids), "date": "2026-11-01"})
    op.save_record(path, record)


def grow(master, name):
    data = yaml.safe_load(master.read_text())
    data.setdefault("projects", []).append({"name": name})
    master.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_writeback_chain_reports_master_writeback_not_mutated(ws, capsys):
    workspace, master = ws
    before = journal.sha256_file(master)
    grow(master, "tool")
    record_writeback(master, before)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(workspace)]) == 1
    out = capsys.readouterr().out
    assert "MASTER_WRITEBACK" in out and "github:acme/tool" in out
    assert "MASTER_MUTATED" not in out


def test_two_writebacks_in_a_row_are_one_chain(ws, capsys):
    workspace, master = ws
    first = journal.sha256_file(master)
    grow(master, "tool")
    record_writeback(master, first)
    second = journal.sha256_file(master)
    grow(master, "other")
    record_writeback(master, second, ids=("github:acme/other",))
    capsys.readouterr()
    check_claims.main(["--workspace", str(workspace)])
    out = capsys.readouterr().out
    assert "MASTER_WRITEBACK" in out and "github:acme/other" in out and "MASTER_MUTATED" not in out


def test_unrecorded_edit_after_writeback_is_still_mutated(ws, capsys):
    workspace, master = ws
    before = journal.sha256_file(master)
    grow(master, "tool")
    record_writeback(master, before)
    grow(master, "hand edit")
    capsys.readouterr()
    check_claims.main(["--workspace", str(workspace)])
    out = capsys.readouterr().out
    assert "MASTER_MUTATED" in out and "MASTER_WRITEBACK" not in out


def test_rerecord_clears_the_finding(ws, capsys):
    workspace, master = ws
    before = journal.sha256_file(master)
    grow(master, "tool")
    record_writeback(master, before)
    check_claims.main(["--workspace", str(workspace), "--master", str(master), "--record"])
    capsys.readouterr()
    check_claims.main(["--workspace", str(workspace)])
    out = capsys.readouterr().out
    assert "MASTER_WRITEBACK" not in out and "MASTER_MUTATED" not in out


def test_workspace_outside_the_store_layout_keeps_master_mutated(tmp_path, capsys):
    workspace = tmp_path / "loose-ws"
    workspace.mkdir()
    master = tmp_path / "profile.yaml"
    master.write_text(yaml.safe_dump(MASTER), encoding="utf-8")
    (workspace / "tailored-profile.yaml").write_text(yaml.safe_dump(MASTER), encoding="utf-8")
    check_claims.main(["--workspace", str(workspace), "--master", str(master), "--record"])
    grow(master, "tool")
    capsys.readouterr()
    check_claims.main(["--workspace", str(workspace)])
    assert "MASTER_MUTATED" in capsys.readouterr().out
