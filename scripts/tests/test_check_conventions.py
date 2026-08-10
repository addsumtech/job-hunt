import datetime
import json

import yaml

import check_conventions as cck

TODAY = datetime.date(2026, 8, 9)

GOOD = {
    "market": "cn",
    "conventions": [{
        "id": "cn-boss-profile-is-the-screen",
        "text_en": ("On BOSS直聘 the recruiter does not see your CV file first. What they "
                    "see is the structured profile you filled in at registration — the "
                    "operator's own SEC filing calls it a mini resume — and your full CV "
                    "and contact details reach them only on mutual consent inside the "
                    "chat. Treat those profile fields as the actual screening document "
                    "and write them for a reader who will decide from them alone."),
        "text_zh": ("在 BOSS 直聘上，招聘方一开始看不到你的简历附件，只能看到你注册时填写的在线"
                    "简历；完整简历和联系方式要等双方在聊天中互相同意后才会送达。所以真正被筛的"
                    "是在线资料的那几栏，要按「对方只看这些就下判断」来写。"),
        "applies_when": "Applying through BOSS直聘, on any track (社招, 校招 or 实习).",
        "added": "2026-08-09",
        "review_by": "2027-02-09",
        "source": {"kind": "published",
                   "publisher": "Kanzhun Limited (operator of BOSS直聘)",
                   "title": "Annual Report on Form 20-F for the fiscal year ended "
                            "December 31, 2025",
                   "url": "https://www.sec.gov/Archives/edgar/data/1842827/x.htm",
                   "retrieved": "2026-08-09",
                   "quote": "enterprise users on our platforms can only see a job "
                            "seeker's mini resume that contains limited information"},
        "why": ("The posting shows a job description and a chat button. Nothing on it "
                "tells you that the artefact being screened is your platform profile "
                "rather than the CV you spent your effort on."),
    }],
}


def write(tmp_path, data, name="cn.yaml"):
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")
    return path


def mutate(**changes):
    data = json.loads(json.dumps(GOOD))
    data["conventions"][0].update(changes)
    return data


# ---------- the quiet case, pinned as hard as the firing case ----------

def test_a_real_shipped_entry_produces_no_findings_at_all(tmp_path):
    assert cck.check_file(write(tmp_path, GOOD), TODAY) == []


def test_digits_in_url_title_retrieved_and_quote_are_exempt(tmp_path):
    # The title carries "Form 20-F ... December 31, 2025", the url an EDGAR CIK, the
    # quote a sentence from a filing. None of those is a claim this table is making.
    assert cck.check_file(write(tmp_path, GOOD), TODAY) == []


def test_the_allowlisted_proper_nouns_pass(tmp_path):
    data = mutate(text_en="Some US employers sit outside the H-1B numerical cap, and "
                          "Form I-9 lets the worker choose which documents to present; "
                          "Form I-983 is the employer-side training plan.",
                  text_zh="有些美国雇主不受 H-1B 名额限制；Form I-9 由劳动者自行选择出示"
                          "哪些证件；Form I-983 是雇主一侧的培训计划。")
    assert [f for f in cck.check_file(write(tmp_path, data), TODAY)
            if f.startswith("DIGIT_IN_PROSE")] == []


def test_a_protected_trait_with_a_written_note_passes(tmp_path):
    data = mutate(
        text_en="An employer may restrict hiring to US citizens only where a law "
                "requires it.",
        text_zh="只有在法律要求时，雇主才可以把招聘限定为美国公民。",
        protected_trait_note="The fact IS a citizenship-discrimination rule; naming the "
                             "trait is what makes the complaint route usable.")
    assert [f for f in cck.check_file(write(tmp_path, data), TODAY)
            if f.startswith("PROTECTED_TRAIT")] == []


def test_the_real_entrys_length_ratio_and_modal_balance_are_quiet(tmp_path):
    findings = cck.check_file(write(tmp_path, GOOD), TODAY)
    assert not [f for f in findings if f.startswith("WARN_LENGTH_RATIO")]
    assert not [f for f in findings if f.startswith("WARN_MODAL_ASYMMETRY")]


def test_a_review_by_in_the_future_passes(tmp_path):
    assert cck.check_file(write(tmp_path, mutate(review_by="2026-08-10")), TODAY) == []


# ---------- the firing cases, taken from live violations the reviewer found ----------

def test_51job_in_an_english_body_fails(tmp_path):
    data = mutate(text_en="Alongside 51job there is a state-organised recruitment "
                          "channel worth checking.")
    findings = cck.check_file(write(tmp_path, data), TODAY)
    assert any(f.startswith("DIGIT_IN_PROSE:") and "51job" in f for f in findings)


def test_the_30_percent_ruling_fails_in_both_languages(tmp_path):
    data = mutate(text_en="The 30% ruling is administered by the Belastingdienst.",
                  text_zh="所谓 30% 规则由荷兰税务局管理。")
    findings = cck.check_file(write(tmp_path, data), TODAY)
    assert any(f.startswith("PERCENT_IN_PROSE:") and "text_en" in f for f in findings)
    assert any(f.startswith("PERCENT_IN_PROSE:") and "text_zh" in f for f in findings)


def test_a_directive_number_in_the_body_fails(tmp_path):
    data = mutate(text_en="Directive (EU) 2023/970 gives you a right to the pay range.")
    assert any(f.startswith("DIGIT_IN_PROSE:")
               for f in cck.check_file(write(tmp_path, data), TODAY))


def test_a_protected_trait_without_a_note_fails(tmp_path):
    data = mutate(text_en="Employers here weigh nationality when shortlisting.",
                  text_zh="这里的雇主在初筛时会看国籍。")
    findings = cck.check_file(write(tmp_path, data), TODAY)
    assert any(f.startswith("PROTECTED_TRAIT:") and "nationality" in f for f in findings)
    assert any(f.startswith("PROTECTED_TRAIT:") and "国籍" in f for f in findings)


def test_an_expired_review_by_fails(tmp_path):
    data = mutate(review_by="2026-08-08")
    assert any(f.startswith("EXPIRED_REVIEW_BY:")
               for f in cck.check_file(write(tmp_path, data), TODAY))


def test_a_duplicate_id_fails(tmp_path):
    data = json.loads(json.dumps(GOOD))
    data["conventions"].append(json.loads(json.dumps(GOOD["conventions"][0])))
    assert any(f.startswith("DUPLICATE_ID:")
               for f in cck.check_file(write(tmp_path, data), TODAY))


def test_a_missing_text_zh_fails(tmp_path):
    data = json.loads(json.dumps(GOOD))
    del data["conventions"][0]["text_zh"]
    assert any(f.startswith("MISSING_FIELD:") and "text_zh" in f
               for f in cck.check_file(write(tmp_path, data), TODAY))


def test_a_published_source_without_https_or_a_date_fails(tmp_path):
    data = mutate(source={"kind": "published", "publisher": "X", "title": "Y",
                          "url": "http://example.org", "retrieved": "August 2026"})
    findings = cck.check_file(write(tmp_path, data), TODAY)
    assert any(f.startswith("BAD_SOURCE_URL:") for f in findings)
    assert any(f.startswith("BAD_SOURCE_RETRIEVED:") for f in findings)


def test_an_unknown_source_kind_fails(tmp_path):
    data = mutate(source={"kind": "remembered", "note": "I think so"})
    assert any(f.startswith("BAD_SOURCE_KIND:")
               for f in cck.check_file(write(tmp_path, data), TODAY))


def test_a_maintainer_source_needs_a_note(tmp_path):
    data = mutate(source={"kind": "maintainer"})
    assert any(f.startswith("MISSING_SOURCE_NOTE:")
               for f in cck.check_file(write(tmp_path, data), TODAY))


def test_a_wildly_unbalanced_translation_warns(tmp_path):
    data = mutate(text_zh="见上。")
    assert any(f.startswith("WARN_LENGTH_RATIO:")
               for f in cck.check_file(write(tmp_path, data), TODAY))


def test_modal_asymmetry_warns_when_only_one_language_obliges(tmp_path):
    data = mutate(text_zh="招聘方必须先看在线简历；你必须填满那几栏；完整简历不得在双方同意前"
                          "送达；因此你应当把在线资料当成真正被筛的文件来写。")
    assert any(f.startswith("WARN_MODAL_ASYMMETRY:")
               for f in cck.check_file(write(tmp_path, data), TODAY))


def test_a_delta_of_exactly_three_does_not_warn(tmp_path):
    # Recomputed over all forty source entries, a delta of +3 occurs on
    # nl-weu-language-requirement-must-be-justified, an entry that SHIPS. The bound
    # is strict so the calibration sits outside the measured body, not on its edge.
    # The replacement is length-matched into the ratio band on purpose: a fixture that
    # trips a DIFFERENT warning proves nothing about the one under test.
    data = mutate(text_zh="招聘方必须先看在线简历；你必须把那几栏逐条填满；完整简历与联系方式"
                          "不得在双方同意之前送达，所以要按照对方只看这几栏就下判断的方式来写，"
                          "把最能说明问题的经历放在最前面，别把它当附件的摘要。")
    findings = cck.check_file(write(tmp_path, data), TODAY)
    assert len(cck._MODAL_ZH.findall(data["conventions"][0]["text_zh"])) == 3
    assert findings == [], findings


def test_an_unverified_note_must_name_what_it_disclaims(tmp_path):
    data = json.loads(json.dumps(GOOD))
    data["unverified"] = [{"note": "Nothing was sourced about 猎聘."}]
    assert any(f.startswith("MISSING_UNVERIFIED_DISCLAIMS:")
               for f in cck.check_file(write(tmp_path, data), TODAY))


def test_an_unverified_note_naming_an_unknown_entry_fails(tmp_path):
    data = json.loads(json.dumps(GOOD))
    data["unverified"] = [{"note": "n/a", "disclaims": ["cn-does-not-exist"]}]
    assert any(f.startswith("UNVERIFIED_TARGET_UNKNOWN:")
               for f in cck.check_file(write(tmp_path, data), TODAY))


def test_a_note_disclaiming_a_claim_the_text_still_makes_warns(tmp_path):
    data = json.loads(json.dumps(GOOD))
    data["unverified"] = [{
        "note": ("Not sourced: that the structured profile filled in at registration "
                 "is the actual screening document a recruiter decides from."),
        "disclaims": ["cn-boss-profile-is-the-screen"]}]
    assert any(f.startswith("WARN_UNVERIFIED_OVERLAP:")
               for f in cck.check_file(write(tmp_path, data), TODAY))


# ---------- the CLI ----------

def test_warnings_alone_do_not_fail_the_gate(tmp_path, capsys):
    path = write(tmp_path, mutate(text_zh="见上。"))
    assert cck.main(["--workspace", str(tmp_path), "--market-file", str(path),
                     "--today", "2026-08-09"]) == 0
    assert "WARN_LENGTH_RATIO" in capsys.readouterr().out


def test_a_hard_finding_fails_the_gate_and_journals_a_receipt(tmp_path):
    path = write(tmp_path, mutate(review_by="2026-08-08"))
    assert cck.main(["--workspace", str(tmp_path), "--market-file", str(path),
                     "--today", "2026-08-09"]) == 1
    record = json.loads((tmp_path / "journal.jsonl").read_text(encoding="utf-8"))
    assert record["gate"] == "check_conventions" and record["verdict"] == "fail"


def test_a_missing_market_file_exits_two_and_still_leaves_one_receipt(tmp_path, capsys):
    assert cck.main(["--workspace", str(tmp_path),
                     "--market-file", str(tmp_path / "nope.yaml")]) == 2
    assert "nope.yaml" in capsys.readouterr().err
    receipts = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(receipts) == 1
    assert receipts[0]["gate"] == "check_conventions"
    assert receipts[0]["verdict"] == "could_not_run"


def test_a_workspace_that_does_not_exist_writes_no_journal(tmp_path, capsys):
    missing = tmp_path / "nope"
    assert cck.main(["--workspace", str(missing), "--all"]) == 2
    assert not missing.exists()
    assert "does not exist" in capsys.readouterr().err


def test_the_market_keys_are_the_shared_ones_and_the_root_is_resolved_once():
    import paths
    import vocab
    assert cck.MARKET_KEYS is vocab.MARKET_KEYS
    assert cck.SKILL_ROOT == paths.SKILL_ROOT
    assert cck.CONVENTIONS_DIR == cck.SKILL_ROOT / "references" / "market-conventions"


# --ci is the repo-check mode: same findings, same exit codes, no workspace and no
# receipt. It exists because `make check` and the CI workflow lint tables that live in
# the repo, not artifacts in a user's run — there is nothing to journal into. The pair
# below pins both halves, because a mode with no test is a mode that drifts.

def test_ci_mode_lints_the_shipped_tables_without_a_workspace(capsys):
    """The invocation Makefile and checks.yml actually run. Before --ci existed this
    exited 2 on argparse, which reads on a CI dashboard as a broken market table."""
    assert cck.main(["--ci"]) == 0
    assert "BAD_ARGS" not in capsys.readouterr().err


def test_ci_mode_writes_no_journal_anywhere(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cck.main(["--ci"]) == 0
    capsys.readouterr()
    assert list(tmp_path.iterdir()) == [], "--ci must leave no receipt behind"


def test_ci_and_workspace_together_are_refused(capsys):
    """Not a convenience: accepting both would let a caller believe a receipt was
    written when none was, and the whole point of a receipt is that its absence shows."""
    assert cck.main(["--ci", "--workspace", "/tmp"]) == 2
    assert "BAD_ARGS" in capsys.readouterr().err


def test_gate_mode_still_demands_a_workspace(capsys):
    assert cck.main(["--all"]) == 2
    err = capsys.readouterr().err
    assert "BAD_ARGS" in err and "--ci" in err


def test_ci_mode_still_fails_on_a_bad_table(tmp_path, monkeypatch, capsys):
    """The quiet half of --ci is worthless if the loud half is missing. A digit in a
    prose field must still exit 1 with no workspace in sight."""
    bad = tmp_path / "cn.yaml"
    doc = json.loads(json.dumps(GOOD))
    doc["conventions"][0]["text_en"] = "Screening rejects 38 percent of applicants outright."
    bad.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(cck, "CONVENTIONS_DIR", tmp_path)
    monkeypatch.setattr(cck, "MARKET_KEYS", ("cn",))
    assert cck.main(["--ci", "--today", "2026-08-09"]) == 1
    assert "DIGIT_IN_PROSE" in capsys.readouterr().out


# overlap_reviewed: a note legitimately names the entry it disclaims, so some token
# overlap is ordinary. Firing on all of it made 15 WARN lines print on a fully passing
# run — the "reader learns to skip the line" failure this repo's own testing rule names.
# The record self-revokes, so the three tests below pin all three states.

def _table_with_unverified(note, reviewed=None, text_en=None):
    doc = json.loads(json.dumps(GOOD))
    if text_en is not None:
        doc["conventions"][0]["text_en"] = text_en
    item = {"disclaims": [doc["conventions"][0]["id"]], "note": note}
    if reviewed is not None:
        item["overlap_reviewed"] = reviewed
    doc["unverified"] = [item]
    return doc


def _run(tmp_path, doc):
    p = tmp_path / "cn.yaml"
    p.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return cck.check_file(p, TODAY)


def test_an_unreviewed_overlap_still_warns_and_names_the_tokens(tmp_path):
    """The loud half must survive the carve-out, and the message must tell the reader
    exactly what to record — an instruction without the value is a second lookup."""
    doc = _table_with_unverified(
        "Not sourced: whether the structured profile the recruiter sees at registration "
        "is read before the resume file.")
    found = [f for f in _run(tmp_path, doc) if "UNVERIFIED_OVERLAP" in f]
    assert len(found) == 1 and found[0].startswith("WARN_UNVERIFIED_OVERLAP:")
    assert "overlap_reviewed:" in found[0]


def test_a_reviewed_overlap_is_silent(tmp_path):
    """The quiet case, pinned as hard as the firing one."""
    doc = _table_with_unverified(
        "Not sourced: whether the structured profile the recruiter sees at registration "
        "is read before the resume file.")
    shared = sorted(cck._tokens(doc["unverified"][0]["note"])
                    & cck._tokens(f"{doc['conventions'][0]['text_en']} "
                                  f"{doc['conventions'][0]['text_zh']}"))
    assert len(shared) >= 3, "fixture must actually overlap or this test proves nothing"
    doc["unverified"][0]["overlap_reviewed"] = shared
    assert [f for f in _run(tmp_path, doc) if "UNVERIFIED_OVERLAP" in f] == []


def test_a_review_that_no_longer_covers_the_overlap_comes_back(tmp_path):
    """Self-revoking. Record a review, then change the text so a new word joins the
    overlap: the stale record must not keep the line quiet, or the carve-out becomes a
    permanent silence rather than a one-time human judgement."""
    doc = _table_with_unverified(
        "Not sourced: whether the structured profile the recruiter sees at registration "
        "is read before the resume file.")
    shared = sorted(cck._tokens(doc["unverified"][0]["note"])
                    & cck._tokens(f"{doc['conventions'][0]['text_en']} "
                                  f"{doc['conventions'][0]['text_zh']}"))
    doc["unverified"][0]["overlap_reviewed"] = shared
    # A word the rendered text already uses, and the note did not: the overlap grows,
    # so the recorded review no longer describes what a reader would be looking at.
    doc["unverified"][0]["note"] += " Nor whether the SEC filing wording is current."
    grown = sorted(cck._tokens(doc["unverified"][0]["note"])
                   & cck._tokens(f"{doc['conventions'][0]['text_en']} "
                                 f"{doc['conventions'][0]['text_zh']}"))
    assert grown != shared, "the edit must actually change the overlap or this proves nothing"
    found = [f for f in _run(tmp_path, doc) if "UNVERIFIED_OVERLAP" in f]
    assert len(found) == 1 and found[0].startswith("WARN_UNVERIFIED_OVERLAP_CHANGED:")
