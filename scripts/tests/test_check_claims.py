import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_claims
import journal

MASTER = {
    "meta": {"name": "Test User"},
    "skills": {"languages": ["Python", "C++"], "infra": ["Docker"]},
    "experience": [{"title": "Research Engineer", "org": "Acme",
                    "bullets": ["Built a PyTorch reconstruction pipeline on a GPU cluster."]}],
    "education": [{"degree": "MSc Computer Science", "institution": "TU Delft"}],
    "certifications": ["AWS Certified Cloud Practitioner (2024)"],
}


def _setup(tmp_path, tailored, claims=None):
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    master = tmp_path / "profile.yaml"
    master.write_text(yaml.safe_dump(MASTER, allow_unicode=True), encoding="utf-8")
    (ws / "tailored-profile.yaml").write_text(
        yaml.safe_dump(tailored, allow_unicode=True), encoding="utf-8")
    if claims is not None:
        (ws / "claims.yaml").write_text(
            yaml.safe_dump(claims, allow_unicode=True), encoding="utf-8")
    check_claims.main(["--workspace", str(ws), "--master", str(master), "--record"])
    return ws, master


def test_an_unchanged_tailoring_passes_quietly(tmp_path, capsys):
    ws, _ = _setup(tmp_path, MASTER)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_term_the_master_mentions_only_in_a_bullet_is_sourced(tmp_path, capsys):
    """The cry-wolf case. 'PyTorch' appears in a master bullet but not in the
    master's skills list; surfacing it into Skills is honest reframing, which is
    the whole point of the skill. Firing here would make the gate unusable."""
    tailored = {**MASTER, "skills": {"languages": ["Python", "C++"],
                                     "ml": ["PyTorch"], "infra": ["Docker"]}}
    ws, _ = _setup(tmp_path, tailored)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_new_term_with_no_claims_row_fails(tmp_path, capsys):
    tailored = {**MASTER, "skills": {"languages": ["Python"], "infra": ["Docker", "Kubernetes"]}}
    ws, _ = _setup(tmp_path, tailored)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("UNSOURCED:")
    assert '"Kubernetes"' in out
    assert "skills.infra" in out
    assert "claims.yaml" in out


def test_a_new_term_with_a_claims_row_passes(tmp_path, capsys):
    tailored = {**MASTER, "skills": {"languages": ["Python"], "infra": ["Docker", "Kubernetes"]}}
    claims = [{"term": "Kubernetes", "where": "tailored-profile.yaml:skills.infra",
               "source_kind": "session-answer",
               "source_ref": "user confirmed 2 years of k8s at Acme, 2026-08-09",
               "session_date": "2026-08-09", "retracted": None}]
    ws, _ = _setup(tmp_path, tailored, claims)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_the_retracted_key_is_required_but_null_is_its_normal_value(tmp_path, capsys):
    """`retracted: null` is what a live claim looks like — requiring a
    non-empty string would invalidate every honest row. The KEY must still be
    present: in a schema where "absent" and "not retracted" look identical, a
    withdrawn claim leaves no scar, and a scar is the whole point of the field.
    Plan 4's check_mock.py requires the same six keys."""
    tailored = {**MASTER, "skills": {"infra": ["Kubernetes"]}}
    row = {"term": "Kubernetes", "where": "tailored-profile.yaml:skills.infra",
           "source_kind": "session-answer", "source_ref": "x",
           "session_date": "2026-08-09", "retracted": None}
    ws, _ = _setup(tmp_path / "null-is-fine", tailored, [row])
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""

    absent = {k: v for k, v in row.items() if k != "retracted"}
    ws2, _ = _setup(tmp_path / "key-absent", tailored, [absent])
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws2)]) == 1
    assert "BAD_CLAIM_ROW" in capsys.readouterr().out


def test_a_retracted_row_does_not_source_the_claim(tmp_path, capsys):
    tailored = {**MASTER, "skills": {"infra": ["Kubernetes"]}}
    claims = [{"term": "Kubernetes", "where": "tailored-profile.yaml:skills.infra",
               "source_kind": "session-answer", "source_ref": "x",
               "session_date": "2026-08-09", "retracted": "walk-back-2026-08-09"}]
    ws, _ = _setup(tmp_path, tailored, claims)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    assert "RETRACTED_CLAIM" in capsys.readouterr().out


def test_an_inflated_title_is_caught(tmp_path, capsys):
    tailored = {**MASTER, "experience": [{"title": "Head of Reconstruction", "org": "Acme",
                                          "bullets": ["Built a PyTorch pipeline."]}]}
    ws, _ = _setup(tmp_path, tailored)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "UNSOURCED" in out and "experience[0].title" in out


def test_bad_claim_rows_are_reported_individually(tmp_path, capsys):
    claims = [
        {"term": "K8s", "where": "x", "source_kind": "guesswork",
         "source_ref": "y", "session_date": "2026-08-09", "retracted": None},
        {"term": "Rust", "where": "x", "source_kind": "profile-line",
         "source_ref": "y", "session_date": "9 Aug 2026", "retracted": None},
        {"term": "Go", "source_kind": "profile-line", "source_ref": "y",
         "session_date": "2026-08-09", "retracted": None},
    ]
    ws, _ = _setup(tmp_path, MASTER, claims)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "BAD_CLAIM_ROW: claims.yaml[0]" in out and "guesswork" in out
    assert "BAD_CLAIM_ROW: claims.yaml[1]" in out and "9 Aug 2026" in out
    assert "BAD_CLAIM_ROW: claims.yaml[2]" in out and "where" in out


def test_a_mutated_master_fails_the_gate(tmp_path, capsys):
    ws, master = _setup(tmp_path, MASTER)
    capsys.readouterr()
    narrowed = {**MASTER, "skills": {"languages": ["Python"]}}
    master.write_text(yaml.safe_dump(narrowed, allow_unicode=True), encoding="utf-8")
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "MASTER_MUTATED" in out
    assert "never mutated by tailoring" in out


def test_verifying_without_a_recorded_fingerprint_is_exit_2(tmp_path, capsys):
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "tailored-profile.yaml").write_text("meta: {}\n", encoding="utf-8")
    assert check_claims.main(["--workspace", str(ws)]) == 2
    assert "NO_MASTER_FINGERPRINT" in capsys.readouterr().err


def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_path(tmp_path):
    ws, _ = _setup(tmp_path, MASTER)
    check_claims.main(["--workspace", str(ws)])
    (ws / check_claims.FINGERPRINT).unlink()
    assert check_claims.main(["--workspace", str(ws)]) == 2
    verdicts = [r["verdict"] for r in journal.read_receipts(ws, "check_claims")]
    assert verdicts == ["recorded", "pass", "could_not_run"]
