"""Weekly digest, task 5: the gate before a digest email is sent."""
import datetime
import json
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_digest
import digest
import digest_ledger
import discover_fixtures as fx
import paths

D = datetime.date(2026, 11, 9)
READ = "51job-173199597"          # quality: complete
CARD = "51job-173198362"          # quality: card_only


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "store")
    digest.save_settings("Jane Doe", {"enabled": True, "recipient": "jane@example.org",
                                      "schedule": {"weekday": 0, "hour": 9}})
    root = paths.profile_dir("Jane Doe") / "searches"
    root.mkdir(parents=True)
    workspace = fx.build_workspace(root)
    picks(workspace, [{"id": READ, "why": "Python/C++ 与你的项目一致", "gaps": "要求 3 年经验"}])
    sources(workspace, ["51job"], [])
    digest.main(["compose", "--name", "Jane Doe", "--workspace", str(workspace), "--today", "2026-11-09"])
    return workspace


def picks(workspace, roles, unread=0):
    (workspace / "digest-picks.yaml").write_text(
        yaml.safe_dump({"roles": roles, "unread": unread}, allow_unicode=True), encoding="utf-8")


def sources(workspace, checked, unchecked):
    (workspace / "digest-sources.yaml").write_text(
        yaml.safe_dump({"checked": checked, "unchecked": unchecked}, allow_unicode=True), encoding="utf-8")


def codes(workspace, capsys):
    code = check_digest.main(["--workspace", str(workspace), "--name", "Jane Doe"])
    out = capsys.readouterr().out
    return code, {line.split(":", 1)[0] for line in out.splitlines() if line.startswith("DIGEST_")}


def recompose(workspace):
    digest.main(["compose", "--name", "Jane Doe", "--workspace", str(workspace), "--today", "2026-11-09"])


def test_clean_workspace_passes(ws, capsys):
    assert codes(ws, capsys) == (0, set())


def test_empty_week_passes(ws, capsys):
    picks(ws, [])
    recompose(ws)
    assert codes(ws, capsys) == (0, set())


def test_too_many_roles(ws, capsys):
    picks(ws, [{"id": READ, "why": "w", "gaps": "g"}] * 6)
    assert "DIGEST_TOO_MANY_ROLES" in codes(ws, capsys)[1]


def test_row_not_in_shortlist(ws, capsys):
    picks(ws, [{"id": "51job-999", "why": "w", "gaps": "g"}])
    assert "DIGEST_ROW_NOT_IN_SHORTLIST" in codes(ws, capsys)[1]


def test_row_not_read(ws, capsys):
    picks(ws, [{"id": CARD, "why": "w", "gaps": "g"}])
    assert "DIGEST_ROW_NOT_READ" in codes(ws, capsys)[1]


def test_row_already_sent(ws, capsys):
    row = next(r for r in fx.SHORTLIST["rows"] if r["id"] == READ)
    digest_ledger.save_ledger("Jane Doe", digest_ledger.record_sent({"roles": []}, [row], D))
    assert "DIGEST_ROW_ALREADY_SENT" in codes(ws, capsys)[1]


def test_no_reason(ws, capsys):
    picks(ws, [{"id": READ, "why": " ", "gaps": "g"}])
    assert "DIGEST_NO_REASON" in codes(ws, capsys)[1]


def test_unchecked_source_must_be_named(ws, capsys):
    with (ws / "journal.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"action": "adapter_call", "site": "indeed", "classification": "platform_limit",
                             "mode": "discover"}) + "\n")
    assert "DIGEST_UNCHECKED_NOT_NAMED" in codes(ws, capsys)[1]
    sources(ws, ["51job"], [{"site": "indeed", "reason": "verification page"}])
    recompose(ws)
    assert "DIGEST_UNCHECKED_NOT_NAMED" not in codes(ws, capsys)[1]


def test_prediction_language_fails(ws, capsys):
    picks(ws, [{"id": READ, "why": "You have a high chance of getting an interview.", "gaps": "g"}])
    recompose(ws)
    assert "DIGEST_PREDICTION" in codes(ws, capsys)[1]


def test_stale_email_fails(ws, capsys):
    picks(ws, [])                       # picks changed after compose
    assert "DIGEST_EMAIL_STALE" in codes(ws, capsys)[1]


def test_missing_email_cannot_run(ws, capsys):
    (ws / "digest-email.json").unlink()
    assert check_digest.main(["--workspace", str(ws), "--name", "Jane Doe"]) == 2
    assert "digest-email.json" in capsys.readouterr().err


def test_shortlist_gate_failure_is_reported(ws, capsys):
    data = fx.load_shortlist(ws)
    data["rows"][0]["why_matched"] = ""
    fx.save_shortlist(ws, data)
    assert "DIGEST_SHORTLIST_GATE" in codes(ws, capsys)[1]



def test_a_logged_in_source_is_allowed_with_the_user_present(ws, capsys):
    # Revision 2026-11-02: the digest runs in a session the user is present for.
    (ws / "raw" / "linkedin-1.json").write_text("[]", encoding="utf-8")
    assert "DIGEST_LOGGED_IN_SOURCE" not in codes(ws, capsys)[1]


def test_recompose_after_a_gate_run_still_passes(ws, capsys):
    # Real run 2026-11-02: check_shortlist saw the previous lint receipt for the old
    # email text (STALE_RECEIPT) because check_digest linted it only afterwards.
    assert codes(ws, capsys) == (0, set())
    picks(ws, [])
    recompose(ws)
    assert codes(ws, capsys) == (0, set())
