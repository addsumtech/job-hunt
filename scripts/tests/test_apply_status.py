import json

import apply_status
import check_render_freshness
import parse_verdicts


def test_resume_reuses_saved_reviews_until_dispatch_inputs_change(tmp_path, capsys):
    args = ["--workspace", str(tmp_path)]
    assert apply_status.main(args) == 0
    assert json.loads(capsys.readouterr().out)["missing"] == ["posting.yaml"]

    # The source master lives in the profile store; a round only records its fingerprint.
    for name in ("posting.yaml", "master-fingerprint.json", "tailored-profile.yaml"):
        (tmp_path / name).touch()
    cv = tmp_path / "cv.md"
    cv.write_text("# Tailored CV", encoding="utf-8")
    round_args = ["--round", "2"]
    assert check_render_freshness.main(args + round_args + ["--record", str(cv)]) == 0
    ats = tmp_path / "judge-2-ats.txt"
    ats.write_text("VERDICT: PASS\n", encoding="utf-8")
    before = (tmp_path / "journal.jsonl").read_bytes()
    capsys.readouterr()
    assert apply_status.main(args) == 0
    paused = json.loads(capsys.readouterr().out)
    assert paused["round"] == 2
    assert paused["transcripts"] == {"ats": "PASS", "recruiter": "missing", "hiring-manager": "missing"}
    assert "existing review tasks" in paused["next"]
    assert (tmp_path / "journal.jsonl").read_bytes() == before

    flags = []
    for name in paused["transcripts"]:
        path = tmp_path / f"judge-2-{name}.txt"
        path.write_text("VERDICT: PASS\n", encoding="utf-8")
        flags += [f"--{name}", str(path)]
    assert "parse_verdicts.py" in apply_status.status(tmp_path)["next"]
    assert parse_verdicts.main(args + round_args + flags) == 0
    assert "check_render_freshness.py" in apply_status.status(tmp_path)["next"]
    assert check_render_freshness.main(args + round_args) == 0
    assert "check_apply.py" in apply_status.status(tmp_path)["next"]

    cv.write_text("# Revised CV", encoding="utf-8")
    stale = apply_status.status(tmp_path)
    assert stale["dispatch"] == "missing or stale"
    assert "--record" in stale["next"]
