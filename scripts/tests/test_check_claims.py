import copy
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_claims
import journal
import render_cv

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

MASTER = {
    "meta": {"name": "Test User"},
    "skills": {"languages": ["Python", "C++"], "infra": ["Docker"]},
    "experience": [{"title": "Research Engineer", "org": "Acme",
                    "bullets": ["Built a PyTorch reconstruction pipeline on a GPU cluster."]}],
    "education": [{"degree": "MSc Computer Science", "institution": "TU Delft"}],
    "certifications": ["AWS Certified Cloud Practitioner (2024)"],
}


def _setup(tmp_path, tailored, claims=None, master=None):
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    master_profile = MASTER if master is None else master
    master = tmp_path / "profile.yaml"
    master.write_text(yaml.safe_dump(master_profile, allow_unicode=True),
                      encoding="utf-8")
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
    # "baseline_recorded", not "recorded": --record fingerprints the master and
    # verifies nothing, and check_apply.py must be able to tell that apart from a
    # verification pass that found nothing. See journal.VERDICTS.
    assert verdicts == ["baseline_recorded", "pass", "could_not_run"]
    assert set(verdicts) <= set(journal.VERDICTS)


# ─────────────────────────────────────────────────────────────────────────────
# The master side: parsed leaves matched on whole tokens, not raw file bytes.
#
# Every case below was confirmed passing (exit 0, zero findings) against the
# `key in master_text` implementation this replaced.
# ─────────────────────────────────────────────────────────────────────────────

# Verbatim, because yaml.safe_dump cannot write a comment and a comment is where
# one of the confirmed bypasses lived: master.read_text() included them, so the
# schema's own commented examples licensed claims.
FIVE_MASTER_TEXT = """\
# Canonical career profile. Single source of truth. Renderers read this.
# headings: optional. Example (Korean): {experience: "경력"}.
meta:
  name: "Test User"
contact:
  email: "test@example.com"
skills:
  languages: ["Python", "JavaScript"]
  frameworks: ["django"]
education:
  - degree: "MSc Computer Science (in progress, expected 2027)"
    institution: "TU Delft"
"""

FIVE_TAILORED = {
    "meta": {"name": "Test User"},
    "contact": {"email": "test@example.com"},
    "skills": {"languages": ["Python", "JavaScript", "Go", "Java", "AI"],
               "frameworks": ["django"]},
    "certifications": ["MSc"],
    "education": [{"degree": "MSc Computer Science", "institution": "TU Delft"}],
}


def _setup_master_text(tmp_path, master_text, tailored, claims=None):
    """Like _setup, but the master is written VERBATIM — comments and all."""
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    master = tmp_path / "profile.yaml"
    master.write_text(master_text, encoding="utf-8")
    (ws / "tailored-profile.yaml").write_text(
        yaml.safe_dump(tailored, allow_unicode=True), encoding="utf-8")
    if claims is not None:
        (ws / "claims.yaml").write_text(
            yaml.safe_dump(claims, allow_unicode=True), encoding="utf-8")
    check_claims.main(["--workspace", str(ws), "--master", str(master), "--record"])
    return ws, master


def _finding_for(out, term):
    """The one reported line about `term`, or None."""
    hits = [line for line in out.splitlines() if f'"{term}"' in line]
    assert len(hits) <= 1, f"{term} reported {len(hits)} times: {hits}"
    return hits[0] if hits else None


def test_the_five_substring_fabrications_are_all_reported(tmp_path, capsys):
    """Each of these was sourced by a substring of a longer word, and passed.

    Go by `django`, Java by `JavaScript`, AI by `email` — which is in every
    profile using the canonical schema, so `AI` was permanently unfalsifiable —
    a fabricated `MSc` certification by the real degree, and the degree's own
    "(in progress)" simply deleted, because the short form is a substring of the
    long one."""
    ws, _ = _setup_master_text(tmp_path, FIVE_MASTER_TEXT, FIVE_TAILORED)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out

    for term, code, where in (("Go", "UNSOURCED", "skills.languages"),
                              ("Java", "UNSOURCED", "skills.languages"),
                              ("AI", "UNSOURCED", "skills.languages"),
                              ("MSc", "UNSOURCED", "certifications[0]"),
                              ("MSc Computer Science", "QUALIFIER_STRIPPED",
                               "education[0].degree")):
        line = _finding_for(out, term)
        assert line, f"{term} is not reported at all"
        assert line.startswith(code), line
        assert where in line, line
    # and the honest half of the same file stays quiet
    for quiet in ("Python", "JavaScript", "django", "TU Delft"):
        assert _finding_for(out, quiet) is None


def test_a_yaml_comment_is_not_a_source(tmp_path, capsys):
    """The leaf parse, not the word boundary, is what kills this class: a
    comment's words are still words. `assets/profile.example.yaml` ships a
    commented example that sourced `PhD` in every profile derived from it."""
    master = ('meta:\n  name: "Test User"\n'
              '# education example: degree: "PhD Applied Physics"\n'
              'skills:\n  languages: ["Python"]\n')
    tailored = {"meta": {"name": "Test User"}, "skills": {"languages": ["Python"]},
                "education": [{"degree": "PhD Applied Physics",
                               "institution": "TU Delft"}]}
    ws, _ = _setup_master_text(tmp_path, master, tailored)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert 'UNSOURCED: "PhD Applied Physics"' in out
    assert "education[0].degree" in out


def test_a_link_is_not_evidence_of_a_skill(tmp_path, capsys):
    """contact.links and projects[].links are excluded from the permitted set.

    Whole-token matching already makes a bare URL inert — `github.com/dana/
    tableau-scratch` normalizes to ONE token, so no slug inside it can source
    anything. What the exclusion still buys is the `{label, url}` form that
    `assets/profile.example.yaml:47` documents: the label is the name of a
    service the candidate has an account on, and an account is not a skill."""
    master = {"meta": {"name": "Test User"},
              "contact": {"email": "t@example.com",
                          "links": {"github": "github.com/dana/tableau-scratch",
                                    "tableau": {"label": "Tableau Public",
                                                "url": "public.tableau.com/dana"}}},
              "skills": {"bi": ["Power BI"]},
              "projects": [{"name": "Recon", "role": "Author",
                            "links": [{"label": "PyTorch", "url": "git.io/x"}]}]}
    tailored = {**master,
                "skills": {"bi": ["Power BI", "Tableau Public", "Tableau", "PyTorch"]}}
    ws, _ = _setup(tmp_path, tailored, master=master)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert 'UNSOURCED: "Tableau Public"' in out    # the link LABEL sources nothing
    assert 'UNSOURCED: "Tableau"' in out           # nor does a slug inside the URL
    assert 'UNSOURCED: "PyTorch"' in out           # projects[].links, same rule
    assert _finding_for(out, "Power BI") is None


def test_a_fact_the_master_states_in_another_section_is_sourced(tmp_path, capsys):
    """A whole field stated anywhere in the master is sourced wherever the
    tailoring puts it — this gate asks where a string came from, not whether the
    section it landed in is the best one. The case that makes this necessary is
    ordinary in the markets this skill targets: a PhD candidate's university is
    both their `education[].institution` and their employer."""
    master = {"meta": {"name": "Test User"},
              "education": [{"degree": "PhD Computer Science",
                             "institution": "Leiden University Medical Center"}],
              "experience": [{"title": "PhD Candidate", "org": "LUMC",
                              "bullets": ["Built a reconstruction pipeline."]}]}
    tailored = copy.deepcopy(master)
    tailored["experience"][0]["org"] = "Leiden University Medical Center"
    ws, _ = _setup(tmp_path, tailored, master=master)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


# ── scope: the atomic families that were never scanned ──────────────────────

SCOPE_MASTER = {
    "meta": {"name": "Test User"},
    "experience": [{"title": "Research Engineer", "org": "LUMC",
                    "bullets": ["Built a reconstruction pipeline."]}],
    "education": [{"degree": "MSc Computer Science", "institution": "TU Delft"}],
    "projects": [{"name": "Recon", "role": "Author"}],
    "publications": ["Doe, J. (2024). Fast recon. MELBA 2(1)."],
    "awards": ["Best Poster, ISMRM 2024"],
    "volunteer": ["Mentor at CoderDojo Leiden, 2022–present"],
    "board": ["Advisory board member, TechForward (2023–present)"],
    "skills": {"languages": ["Python"]},
}

FABRICATIONS = {
    "experience[0].org": ("Philips Research",
                          lambda p: p["experience"][0].__setitem__("org", "Philips Research")),
    "education[0].institution": ("ETH Zurich",
                                 lambda p: p["education"][0].__setitem__("institution", "ETH Zurich")),
    "projects[0].role": ("Staff Engineer, Google Brain",
                         lambda p: p["projects"][0].__setitem__("role", "Staff Engineer, Google Brain")),
    "publications[1]": ("Doe, J. (2026). Nature 640, 12-19.",
                        lambda p: p["publications"].append("Doe, J. (2026). Nature 640, 12-19.")),
    "awards[1]": ("Turing Award, 2025", lambda p: p["awards"].append("Turing Award, 2025")),
    "volunteer[1]": ("Chair, Dutch Society of Radiology",
                     lambda p: p["volunteer"].append("Chair, Dutch Society of Radiology")),
    "board[1]": ("Non-executive director, Siemens Healthineers",
                 lambda p: p["board"].append("Non-executive director, Siemens Healthineers")),
}


@pytest.mark.parametrize("where", sorted(FABRICATIONS))
def test_a_fabricated_atomic_fact_is_reported_in_every_scanned_family(
        where, tmp_path, capsys):
    """An org, an institution, a publication, an award, a project role, a
    volunteer post and a board seat are each either true or fabricated — unlike a
    bullet, which is prose about work the candidate really did. All seven passed."""
    term, fabricate = FABRICATIONS[where]
    tailored = copy.deepcopy(SCOPE_MASTER)
    fabricate(tailored)
    ws, _ = _setup(tmp_path, tailored, master=SCOPE_MASTER)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert f'UNSOURCED: "{term}"' in out
    assert where in out


def test_the_unchanged_wide_profile_stays_quiet(tmp_path, capsys):
    """The quiet half of the scope extension: seven more families scanned must
    not mean seven more ways for an untouched profile to fail."""
    ws, _ = _setup(tmp_path, SCOPE_MASTER, master=SCOPE_MASTER)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


# ── QUALIFIER_STRIPPED, and the honest reframings it must not fire on ───────

QUALIFIER_MASTER = {
    "meta": {"name": "Test User"},
    "experience": [{"title": "Senior ML Engineer", "org": "Acme BV",
                    "bullets": ["Shipped a recon pipeline."]}],
    "education": [{"degree": "MSc Computer Science (in progress, expected 2027)",
                   "institution": "TU Delft"}],
    "skills": {"languages": ["English (native)", "Dutch (B1)"],
               "ml": ["PyTorch Lightning"]},
    "certifications": ["AWS Certified Cloud Practitioner (2024)",
                       "BLS Provider (expired 2023)"],
}


def test_a_dropped_status_qualifier_is_reported(tmp_path, capsys):
    """Dropping "(in progress)" / "(B1)" / "(expired 2023)" upgrades a real
    credential into a stronger one. Each was a silent pass: the short form is a
    substring of the long one."""
    tailored = copy.deepcopy(QUALIFIER_MASTER)
    tailored["education"][0]["degree"] = "MSc Computer Science"
    tailored["skills"]["languages"] = ["English (native)", "Dutch"]
    tailored["certifications"][1] = "BLS Provider"
    ws, _ = _setup(tmp_path, tailored, master=QUALIFIER_MASTER)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    for term, where in (("MSc Computer Science", "education[0].degree"),
                        ("Dutch", "skills.languages"),
                        ("BLS Provider", "certifications[1]")):
        line = _finding_for(out, term)
        assert line and line.startswith("QUALIFIER_STRIPPED"), (term, line)
        assert where in line, line
    assert "in progress" in out and "B1" in out and "expired 2023" in out


def test_qualifier_stripped_does_not_fire_on_an_honest_reframe(tmp_path, capsys):
    """The quiet case for the same rule, and the reason it is not implemented as
    "a substring of a master leaf": each of these IS a substring relation, and
    each is a truthful reframing this skill exists to permit.

      Senior ML Engineer → ML Engineer    an honest DE-escalation
      PyTorch Lightning  → PyTorch        a real component of a real tool
      Acme BV            → Acme           a dropped legal-entity suffix
      AWS … Practitioner (2024) → …       a dropped YEAR, which is not a status
      English (native)   → English        dropping a qualifier that STRENGTHENED
    """
    tailored = copy.deepcopy(QUALIFIER_MASTER)
    tailored["experience"][0]["title"] = "ML Engineer"
    tailored["experience"][0]["org"] = "Acme"
    tailored["skills"]["ml"] = ["PyTorch"]
    tailored["skills"]["languages"] = ["English", "Dutch (B1)"]
    tailored["certifications"][0] = "AWS Certified Cloud Practitioner"
    ws, _ = _setup(tmp_path, tailored, master=QUALIFIER_MASTER)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_status_qualifier_is_caught_without_the_brackets(tmp_path, capsys):
    """Punctuation is not the rule; the closed status vocabulary is. A master that
    writes ", in progress" instead of "(in progress)" must not be a way through."""
    master = {"meta": {"name": "Test User"},
              "education": [{"degree": "BSc Physics, in progress",
                             "institution": "TU Delft"}],
              "certifications": ["First Aid — expired 2024"]}
    tailored = {**master,
                "education": [{"degree": "BSc Physics", "institution": "TU Delft"}],
                "certifications": ["First Aid"]}
    ws, _ = _setup(tmp_path, tailored, master=master)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert _finding_for(out, "BSc Physics").startswith("QUALIFIER_STRIPPED")
    assert _finding_for(out, "First Aid").startswith("QUALIFIER_STRIPPED")


def test_a_trailing_parenthetical_that_is_not_a_status_stays_quiet(tmp_path, capsys):
    """The reason the vocabulary is closed and `learning` is not in it: dropping a
    context note is not an upgrade, and `PyTorch (deep learning)` is ordinary."""
    master = {"meta": {"name": "Test User"},
              "skills": {"ml": ["PyTorch (deep learning)", "scikit-learn (classical ML)"]},
              "experience": [{"title": "Data Scientist (maternity cover)", "org": "Acme",
                              "bullets": ["Shipped a model."]}]}
    tailored = {**master,
                "skills": {"ml": ["PyTorch", "scikit-learn"]},
                "experience": [{"title": "Data Scientist", "org": "Acme",
                                "bullets": ["Shipped a model."]}]}
    ws, _ = _setup(tmp_path, tailored, master=master)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_leading_status_word_counts_and_a_leading_seniority_word_does_not(
        tmp_path, capsys):
    """Position is not the rule; the vocabulary is. "Conversational German" →
    "German" upgrades the claim wherever the qualifier sat, while "Senior ML
    Engineer" → "ML Engineer" drops a word that is not a status and must not
    fire."""
    master = {"meta": {"name": "Test User"},
              "skills": {"languages": ["Conversational German", "Fluent English"]},
              "experience": [{"title": "Senior ML Engineer", "org": "Acme",
                              "bullets": ["Shipped a model."]}]}
    tailored = {**master,
                "skills": {"languages": ["German", "English"]},
                "experience": [{"title": "ML Engineer", "org": "Acme",
                                "bullets": ["Shipped a model."]}]}
    ws, _ = _setup(tmp_path, tailored, master=master)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert _finding_for(out, "German").startswith("QUALIFIER_STRIPPED")
    assert _finding_for(out, "English") is None      # "Fluent" is not a weakener
    assert _finding_for(out, "ML Engineer") is None  # nor is "Senior"


def test_a_status_word_inside_a_longer_dropped_phrase_is_not_a_qualifier(
        tmp_path, capsys):
    """The dropped span must be a status and nothing else. "Engineer, Basic
    Materials Group" → "Engineer" drops the word `basic`, but it also drops a
    department, so it is a shortened title, not a stripped qualifier."""
    master = {"meta": {"name": "Test User"},
              "experience": [{"title": "Engineer, Basic Materials Group",
                              "org": "Acme", "bullets": ["Ran the lab."]}]}
    tailored = copy.deepcopy(master)
    tailored["experience"][0]["title"] = "Engineer"
    ws, _ = _setup(tmp_path, tailored, master=master)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_chinese_status_qualifier_is_caught(tmp_path, capsys):
    """Same rule, in the second language this skill renders CVs in."""
    master = {"meta": {"name": "李雷"},
              "education": [{"degree": "计算机科学硕士（在读）", "institution": "清华大学"}],
              "skills": {"语言": ["荷兰语（B1）", "英语（流利）"]}}
    tailored = {**master,
                "education": [{"degree": "计算机科学硕士", "institution": "清华大学"}],
                "skills": {"语言": ["荷兰语", "英语"]}}
    ws, _ = _setup(tmp_path, tailored, master=master)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert _finding_for(out, "计算机科学硕士").startswith("QUALIFIER_STRIPPED")
    assert _finding_for(out, "荷兰语").startswith("QUALIFIER_STRIPPED")
    # 英语（流利）→ 英语 drops a qualifier that STRENGTHENED the claim: quiet.
    assert _finding_for(out, "英语") is None


def test_a_claims_row_sources_a_stripped_qualifier(tmp_path, capsys):
    """The degree really was awarded since the master was written. That is what
    claims.yaml is for, and the finding must be answerable."""
    tailored = copy.deepcopy(QUALIFIER_MASTER)
    tailored["education"][0]["degree"] = "MSc Computer Science"
    claims = [{"term": "MSc Computer Science",
               "where": "tailored-profile.yaml:education[0].degree",
               "source_kind": "session-answer",
               "source_ref": "user confirmed the degree was conferred 2026-07",
               "session_date": "2026-08-16", "retracted": None}]
    ws, _ = _setup(tmp_path, tailored, claims, master=QUALIFIER_MASTER)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


# ── short tokens, in both directions ────────────────────────────────────────

SHORT_MASTER = {
    "meta": {"name": "Test User"},
    "skills": {"languages": ["R", "C++", "C#", ".NET", "Go"]},
    "experience": [{"title": "Engineer", "org": "Acme",
                    "bullets": ["Ported the solver from MATLAB to C++.",
                                "Statistical analysis in R."]}],
}


def test_a_two_character_skill_is_sourced_by_its_own_leaf_or_bullet(tmp_path, capsys):
    """`Go`, `AI`, `R`, `C` are real skills AND substrings of everything. The old
    gate handled that by skipping every term shorter than two characters, i.e. by
    never checking `R` or `C` at all. A whole-token index checks them and still
    finds them: `C++` and `.NET` survive normalization intact, and a term that
    ends a sentence ("… in R.") still matches."""
    tailored = {**SHORT_MASTER,
                "skills": {"languages": ["R", "C++", "C#", ".NET", "Go"],
                           "from_bullets": ["MATLAB", "C++", "R"]}}
    ws, _ = _setup(tmp_path, tailored, master=SHORT_MASTER)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_one_character_skill_the_master_never_mentions_is_reported(tmp_path, capsys):
    """The other direction: `len(key) < 2` was an unconditional bypass, so a
    single-character fabrication could never be reported at all."""
    master = {"meta": {"name": "Test User"}, "skills": {"languages": ["Ruby"]}}
    tailored = {**master, "skills": {"languages": ["Ruby", "R"]}}
    ws, _ = _setup(tmp_path, tailored, master=master)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    assert 'UNSOURCED: "R"' in capsys.readouterr().out


# ── scripts without word delimiters ─────────────────────────────────────────

CJK_MASTER = {
    "meta": {"name": "李雷"},
    "skills": {"技术": ["Python"]},
    "experience": [{"title": "算法工程师", "org": "飞利浦医疗",
                    "bullets": ["使用深度学习方法重建磁共振图像。"]}],
}


def test_a_chinese_term_is_sourced_by_a_chinese_bullet(tmp_path, capsys):
    """Word boundaries are a property of space-delimited scripts. Chinese writes
    without them, so one bullet is one token — a token test alone would report
    every skill on every Chinese CV as unsourced, which is the cry-wolf failure,
    not a fix. For such a term, containment inside a single leaf is the test."""
    tailored = {**CJK_MASTER, "skills": {"技术": ["Python", "深度学习"]}}
    ws, _ = _setup(tmp_path, tailored, master=CJK_MASTER)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_chinese_fabrication_is_still_reported(tmp_path, capsys):
    tailored = {**CJK_MASTER, "skills": {"技术": ["Python", "强化学习"]}}
    ws, _ = _setup(tmp_path, tailored, master=CJK_MASTER)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    assert 'UNSOURCED: "强化学习"' in capsys.readouterr().out


# ── the honest-reframing workspace: every ✓-Allowed move, all silent ────────
#
# Built verbatim from references/gap-analysis.md §2 ALLOWED. If the gate fires on
# this workspace it is firing on the skill's own documented output, and the reader
# learns to skip the line.

REFRAME_MASTER = {
    "meta": {"name": "Dana Okafor", "headline": "Data Engineer"},
    "contact": {"email": "dana@example.com",
                "links": {"github": "github.com/danao"}},
    "summary": "Data engineer working on retail analytics.",
    "experience": [
        {"title": "Senior Data Engineer", "org": "Northwind Retail BV",
         "start": "2021-03", "end": "present",
         "bullets": [
             "Wrote Python scripts to automate data cleaning, scheduled in Airflow.",
             "Built executive dashboards in Power BI for the trading desk.",
             "Improved system performance in the nightly batch.",
             "Reviewed colleagues' merge requests every sprint.",
             "Built the HTTP services the storefront calls at checkout.",
         ]}],
    "education": [{"degree": "BSc Software Engineering",
                   "institution": "Universiteit Twente", "start": "2014", "end": "2018"}],
    "skills": {"Technical": ["Python", "SQL", "Power BI"],
               "Languages": ["English (fluent)", "Dutch (B1)"]},
    "certifications": ["AWS Certified Cloud Practitioner (2024)"],
    "awards": ["Northwind Engineering Award, 2023"],
    "volunteer": ["Mentor at CoderDojo Utrecht, 2019–present"],
    "achievements": ["Cut the nightly batch window from 6 hours to 90 minutes."],
}

REFRAME_TAILORED = {
    **REFRAME_MASTER,
    # ✓ Reordering and reprioritising bullets; rewording real achievements in the
    #   posting's terminology; quantifying real impact; honest transferable framing.
    "experience": [
        {"title": "Data Engineer",              # ✓ an honest DE-escalation
         "org": "Northwind Retail",             # ✓ dropped legal-entity suffix
         "start": "2021-03", "end": "present",
         "bullets": [
             "Automated the ETL data-cleaning pipeline in Python on Airflow, "
             "cutting pre-processing time by 60%.",
             "Owned the HTTP/REST services behind checkout.",
             "Experienced with Power BI for executive dashboards; familiar with "
             "Tableau's interface from evaluations.",
             "Code-reviewed every sprint; onboarded two joiners.",
         ]}],
    # ✓ rewording an achievement into the posting's terms
    "achievements": ["Cut the nightly batch window 4× (6h → 90min)."],
    # ✓ regrouping real skills; ✓ surfacing a skill the master mentions only in a
    #   bullet; ✓ adding real-but-omitted detail the user confirmed (claims.yaml)
    "skills": {"Technical": ["Python", "SQL", "Airflow", "Docker"],
               "BI & Analytics": ["Power BI"],
               "APIs": ["REST API design"],
               "Languages": ["English (fluent)", "Dutch (B1)"]},
    "certifications": ["AWS Certified Cloud Practitioner"],   # ✓ dropped year
    "volunteer": ["Mentor at CoderDojo Utrecht"],             # ✓ dropped date tail
}

REFRAME_CLAIMS = [
    {"term": "Docker", "where": "tailored-profile.yaml:skills.Technical",
     "source_kind": "session-answer",
     "source_ref": "user: 'I use Docker every day locally' (2026-08-16)",
     "session_date": "2026-08-16", "retracted": None},
    {"term": "REST API design", "where": "tailored-profile.yaml:skills.APIs",
     "source_kind": "profile-line",
     "source_ref": "profile.yaml:experience[0].bullets[4] — built the HTTP services "
                   "the storefront calls at checkout",
     "session_date": "2026-08-16", "retracted": None},
]


def test_the_honest_reframing_workspace_is_silent(tmp_path, capsys):
    ws, _ = _setup(tmp_path, REFRAME_TAILORED, REFRAME_CLAIMS, master=REFRAME_MASTER)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_the_same_workspace_still_catches_the_keyword_insert(tmp_path, capsys):
    """The mutation of the quiet case: one keyword from the posting, dropped into
    the same honest workspace with no row behind it, is still reported."""
    tailored = copy.deepcopy(REFRAME_TAILORED)
    tailored["skills"]["Technical"].append("Kubernetes")
    tailored["skills"]["BI & Analytics"].append("Tableau")
    ws, _ = _setup(tmp_path, tailored, REFRAME_CLAIMS, master=REFRAME_MASTER)
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert 'UNSOURCED: "Kubernetes"' in out
    assert 'UNSOURCED: "Tableau"' in out


# ── the scope registry ──────────────────────────────────────────────────────

def test_every_rendered_section_is_classified_scanned_or_out_of_scope():
    """Nothing derived the SCANNED set from the RENDERED set, which is how eight
    languages of section labels were added to render_cv without anyone deciding
    whether the new sections are checked. This is that derivation."""
    rendered = set(render_cv._ALL_SECTIONS)
    scanned = set(check_claims.SCANNED_SECTIONS)
    out_of_scope = set(check_claims.OUT_OF_SCOPE_SECTIONS)
    assert not scanned & out_of_scope
    assert rendered == scanned | out_of_scope, (
        f"unclassified rendered section(s): {sorted(rendered - scanned - out_of_scope)}; "
        f"classified but not rendered: {sorted(scanned | out_of_scope - rendered)}")
    for section, reason in check_claims.OUT_OF_SCOPE_SECTIONS.items():
        assert len(reason.split()) >= 8, f"{section} needs a written reason, not a label"


EXPECTED_SCANNED_PATHS = [
    "awards[0]",
    "board[0]",
    "certifications[0]",
    "education[0].degree",
    "education[0].institution",
    "experience[0].org",
    "experience[0].title",
    "projects[0].role",
    "publications[0]",
    "skills.languages",
    "skills.technical",
    "volunteer[0]",
]


def test_the_scanned_field_paths_of_the_full_profile_are_pinned():
    """Field-path granular on purpose. A section added to the fixture, or a field
    quietly dropped from the walk, changes this list and someone has to decide."""
    profile = yaml.safe_load(
        (FIXTURES / "full_profile.yaml").read_text(encoding="utf-8"))
    claims = check_claims.atomic_claims(profile)
    assert sorted({where for _term, where, _family in claims}) == EXPECTED_SCANNED_PATHS
    # every scanned section the fixture fills contributes at least one path …
    for section in check_claims.SCANNED_SECTIONS:
        if profile.get(section):
            assert any(w == section or w.startswith(f"{section}.")
                       or w.startswith(f"{section}[") for _t, w, _f in claims), section
    # … and no out-of-scope section contributes any, though the fixture fills them
    for section in check_claims.OUT_OF_SCOPE_SECTIONS:
        assert profile.get(section), f"{section} must be present to prove it is skipped"
        assert not any(w.startswith(section) for _t, w, _f in claims), section


def test_every_scanned_family_has_master_evidence_of_its_own_kind():
    """The families the tailored side reports against are the families the master
    side supplies — one walker, so the two cannot drift apart."""
    profile = yaml.safe_load(
        (FIXTURES / "full_profile.yaml").read_text(encoding="utf-8"))
    _exact, _prose, families = check_claims.master_sources(profile)
    assert {f for _t, _w, f in check_claims.atomic_claims(profile)} == set(families)


# ── a master the gate cannot parse is not a master that verified anything ───

def test_an_unparseable_master_is_reported_and_nothing_is_declared_sourced(
        tmp_path, capsys):
    ws, master = _setup_master_text(
        tmp_path, 'meta:\n  name: "Test User"\nskills:\n  languages: ["Python"]\n',
        {"meta": {"name": "Test User"}, "skills": {"languages": ["Python"]}})
    master.write_text("meta:\n  name: [unclosed\n", encoding="utf-8")
    capsys.readouterr()
    assert check_claims.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "MASTER_UNREADABLE" in out
    # not a flood of UNSOURCED derived from a master nobody could read
    assert "UNSOURCED" not in out


# ---------------------------------------------------------------------------
# Dropped qualifiers, in every language this skill renders a CV in.
#
# Audited 2026-09-05: the vocabulary was English plus Simplified Chinese, so
# `MSc Informatik (in Bearbeitung, voraussichtlich 2027)` -> `MSc Informatik`
# came back `sourced`. That is the load-bearing rule of the whole skill — never
# present a credential you do not hold — failing on the candidate's language
# rather than on the substance of the claim.
#
# The quiet list is the longer one on purpose. `dropped_status` requires the
# WHOLE dropped span to be status-or-connective, and widening the connective set
# to five more languages is exactly the change that could start firing on
# ordinary reframings like `ML Engineer` off `Senior ML Engineer`.
# ---------------------------------------------------------------------------

_DROPS_A_QUALIFIER = [
    ("MSc Informatik", "MSc Informatik (in Bearbeitung, voraussichtlich 2027)"),
    ("MSc Informatica", "MSc Informatica (verwacht 2027, nog niet afgerond)"),
    ("Master Informatique", "Master Informatique (en cours, prévu 2027)"),
    ("Máster en Informática", "Máster en Informática (en curso, previsto 2027)"),
    ("Laurea Informatica", "Laurea Informatica (in corso, previsto 2027)"),
    ("修士（情報工学）", "修士（情報工学）（2027年修了見込み）"),
    ("석사 컴퓨터공학", "석사 컴퓨터공학 (재학중, 2027 졸업예정)"),
    ("计算机硕士", "计算机硕士（在读）"),
    ("Deutsch", "Deutsch (Grundkenntnisse)"),
    ("Nederlands", "Nederlands (basiskennis)"),
    ("日本語", "日本語（日常会話）"),
    ("한국어", "한국어 (초급)"),
    ("English", "English (basic)"),
    ("MSc CS", "MSc CS (in progress, expected 2027)"),
]

_DROPS_NOTHING_THAT_MATTERS = [
    ("AWS Certified", "AWS Certified (2024)"),
    ("Nederlands", "Nederlands (moedertaal)"),
    ("Python", "Python (deep learning)"),
    ("Engineer", "Engineer (maternity cover)"),
    ("ASML", "ASML BV"),
    ("PyTorch", "PyTorch (Meta)"),
    ("Manager", "Manager (Amsterdam)"),
    # a FINISHED degree, in the two languages whose "finished" word now sits in
    # the ignorable set — dropping it claims nothing the leaf denies
    ("MSc Informatica", "MSc Informatica (afgerond 2024)"),
    ("MSc Informatik", "MSc Informatik (abgeschlossen 2024)"),
    ("ML Engineer", "Senior ML Engineer"),
    ("Engineer", "Engineer, Basic Materials Group"),
    ("Volksbank", "de Volksbank"),
    ("Ingegneria", "Ingegneria della Informazione"),
    ("修士", "修士（情報工学）"),
]


@pytest.mark.parametrize("term,leaf", _DROPS_A_QUALIFIER,
                         ids=[t[1][:28] for t in _DROPS_A_QUALIFIER])
def test_an_unfinished_or_limited_claim_is_reported_in_any_language(term, leaf):
    assert check_claims.relation(term, leaf) == check_claims.QUALIFIER


@pytest.mark.parametrize("term,leaf", _DROPS_NOTHING_THAT_MATTERS,
                         ids=[t[1][:28] for t in _DROPS_NOTHING_THAT_MATTERS])
def test_an_honest_reframing_is_still_silent(term, leaf):
    assert check_claims.relation(term, leaf) == check_claims.SOURCED
