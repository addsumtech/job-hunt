import json

import lint_no_prediction as lint

ORDINARY = """# Fit assessment — MR Reconstruction Scientist

```
must-have 强证据：   8 of 11   （partial 2，gap 1，无证据 0）
核心职责已证实：     4 of 6
职级匹配：           平级
可补缺口所需投入：   一晚
投递建议：           大概率被筛掉
```

⚠️ 以上是对证据的清点，不是对结果的预判。每一项都连同它的证据引用一起印出，分母可以逐条审计；
本 skill 不给出面试或录用的可能性估计，也不给 0–100 分。要不要投，由你决定。

| Requirement | level | screening | match |
|---|---|---|---|
| C++ | required | knockout | strong |
| Kubernetes | required | weighted | gap |

Source of the posting: https://www.gov.uk/2026/08/09/example-vacancy
"""

CITED_RUBRIC = """The advert names the employer's own framework, so here is that scale
in its own words:

> Level 3 — Demonstrates the behaviour consistently; 100% of the named criteria are
> evidenced with examples.
> — Civil Service, Success Profiles: Behaviours, https://www.gov.uk/government/publications/success-profiles

That is the list the panel was asked to look for. It is not a statement about you.
"""

# The exact shape modes/assess.md §10 mandates on 大概率被筛掉 / 硬性阻断.
OTHER_HALF = """## 那该怎么办

策略：`skill_sprint` 技能冲刺

## 30/60/90 计划

| 目标 | 行动 | 验收标准 |
|---|---|---|
| 补上分布式训练 | 把单卡训练器移植到 torchrun | 仓库 README 里有两卡运行日志 |

## 路线图

| 阶段 | 输出物 |
|---|---|
| 第一阶段 | 一份可复现的两卡训练日志 |
"""

# The shape Plan 4's assessor emits. The candidate really said "40%"; the tag is
# the finding, and deleting the quote would delete the finding and keep the file.
MOCK_ASSESSMENT = """MOCK-PROVENANCE-V1
pass=provenance
FINDING: tag=OVER-CLAIM | ref=Q1 | quote=it came out roughly 40% faster end to end
FINDING: tag=UNSOURCED-FACT | ref=Q1 | quote=we benchmarked it on about 200 patient scans
END-MOCK-PROVENANCE-V1
"""


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------- the quiet case, pinned as hard as the firing case ----------

def test_an_ordinary_assessment_passes(tmp_path, capsys):
    _write(tmp_path, "fit-assessment.md", ORDINARY)
    assert lint.main(["--workspace", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_the_counted_facts_line_is_not_a_score_pattern():
    assert lint.scan_text("must-have 强证据：   8 of 11", "x") == []


def test_the_likely_screen_out_label_does_not_fire_its_own_lint():
    assert lint.scan_text("投递建议：大概率被筛掉", "x") == []
    assert lint.scan_text("APPLY VERDICT: likely_screen_out", "x") == []


def test_the_required_disclaimer_passes():
    zh = ("⚠️ 以上是对证据的清点，不是对结果的预判。本 skill 不给出面试或录用的可能性估计，"
          "也不给 0–100 分。")
    en = ("This is a count of evidence, not a forecast of the outcome. This skill states "
          "no interview or hiring outcome estimate and no 0–100 score.")
    assert lint.scan_text(zh, "x") == []
    assert lint.scan_text(en, "x") == []


def test_a_url_with_a_date_path_is_not_a_score_pattern():
    assert lint.scan_text("See https://www.gov.uk/2026/08/09/example", "x") == []


def test_a_url_with_percent_encoding_is_not_a_percent():
    assert lint.scan_text("See https://example.org/a%20b", "x") == []


def test_the_word_strong_as_a_match_label_does_not_fire():
    assert lint.scan_text("| C++ | required | knockout | strong |", "x") == []
    assert lint.scan_text("Your C++ evidence is strong and recent.", "x") == []


def test_a_cited_published_employer_rubric_is_allowed(tmp_path):
    _write(tmp_path, "fit-assessment.md", CITED_RUBRIC)
    assert lint.main(["--workspace", str(tmp_path)]) == 0


def test_the_mandated_30_60_90_table_is_not_a_score(tmp_path):
    # modes/assess.md §10 REQUIRES this table on 大概率被筛掉 and 硬性阻断. A lint
    # that fires on it fails every assessment that obeys its own mode file.
    assert lint.scan_text("## 30/60/90 计划", "x") == []
    assert lint.scan_text("Here is the 30 / 60 / 90 plan.", "x") == []
    assert lint.scan_text(OTHER_HALF, "x") == []
    _write(tmp_path, "fit-assessment.md", ORDINARY + "\n" + OTHER_HALF)
    assert lint.main(["--workspace", str(tmp_path)]) == 0


def test_a_verbatim_candidate_quote_inside_a_mock_block_is_exempt(tmp_path):
    # An honest transcript is the one place a number a HUMAN said is the evidence.
    assert lint.scan_text(MOCK_ASSESSMENT, "x") == []
    _write(tmp_path, "mock/assessment-1.md", MOCK_ASSESSMENT)
    assert lint.main(["--workspace", str(tmp_path)]) == 0


# ---------- the firing cases ----------

def test_a_percentage_fires():
    findings = lint.scan_text("Keyword coverage is 73% of the must-haves.", "x")
    assert len(findings) == 1 and findings[0].startswith("PERCENT:")


def test_a_slash_score_fires():
    findings = lint.scan_text("You score 8/11 on the requirements.", "x")
    assert len(findings) == 1 and findings[0].startswith("SCORE_PATTERN:")


def test_the_roadmap_mask_is_that_one_token_and_nothing_wider():
    # The exemption must not become a licence: a neighbouring score still fires,
    # and a score on the same line as the horizon still fires.
    assert lint.scan_text("30/60/91 is not the horizon", "x")
    assert lint.scan_text("130/60/90", "x")
    findings = lint.scan_text("## 30/60/90 计划 — 你目前 8/11", "x")
    assert len(findings) == 1 and "8/11" in findings[0]


def test_the_mock_exemption_is_the_quote_payload_and_nothing_wider():
    # The assessor's own prose is not a quote, and a quote= outside a block is not
    # exempt -- otherwise the exemption is a lint-dodge anyone can type.
    inside_prose = ("MOCK-PROVENANCE-V1\n"
                    "NOTE: the candidate is a strong candidate | quote=she said so\n"
                    "END-MOCK-PROVENANCE-V1\n")
    assert any(f.startswith("PREDICTION_WORD:") for f in
               lint.scan_text(inside_prose, "x"))
    loose = "FINDING: tag=OVER-CLAIM | quote=roughly 40% faster\n"
    assert any(f.startswith("PERCENT:") for f in lint.scan_text(loose, "x"))
    unterminated = ("MOCK-PROVENANCE-V1\n"
                    "FINDING: tag=OVER-CLAIM | quote=roughly 40% faster\n")
    assert any(f.startswith("PERCENT:") for f in lint.scan_text(unterminated, "x"))


def test_english_prediction_vocabulary_fires():
    for text in ["You are a strong candidate for this role.",
                 "Your chances here are good.",
                 "The probability of an interview is high.",
                 "The odds are in your favour.",
                 "You are likely to be interviewed.",
                 "This CV would pass the screen."]:
        findings = lint.scan_text(text, "x")
        assert findings and findings[0].startswith("PREDICTION_WORD:"), text


def test_chinese_prediction_vocabulary_fires():
    for text in ["面试概率不低。", "这个岗位的通过率很高。", "命中率一般。", "录取率未知。"]:
        findings = lint.scan_text(text, "x")
        assert findings and findings[0].startswith("PREDICTION_WORD:"), text


def test_a_blockquote_without_an_attribution_url_is_not_allowed():
    text = ("> Level 3 — 100% of the named criteria are evidenced.\n"
            "> — Civil Service, Success Profiles\n\nSo that is the bar.\n")
    findings = lint.scan_text(text, "x")
    assert findings and findings[0].startswith("PERCENT:")


def test_the_gate_scans_every_named_surface(tmp_path):
    _write(tmp_path, "shortlist.md", "Interview probability: high.\n")
    _write(tmp_path, "mock/assessment-1.md", "You are a weak candidate.\n")
    _write(tmp_path, "mock/cheatsheet.md", "Coverage 9/10.\n")
    assert lint.main(["--workspace", str(tmp_path)]) == 1
    findings = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()
                ][0]["findings"]
    surfaces = {f.split(" ", 1)[1].split(":")[0] for f in findings}
    assert surfaces == {"shortlist.md", "mock/assessment-1.md", "mock/cheatsheet.md"}


def test_no_target_files_exits_two_and_still_leaves_exactly_one_receipt(tmp_path, capsys):
    assert lint.main(["--workspace", str(tmp_path)]) == 2
    assert "no rendered file" in capsys.readouterr().err
    receipts = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(receipts) == 1
    assert receipts[0]["gate"] == "lint_no_prediction"
    assert receipts[0]["verdict"] == "could_not_run"


def test_a_workspace_that_does_not_exist_writes_no_journal(tmp_path, capsys):
    missing = tmp_path / "nope"
    assert lint.main(["--workspace", str(missing)]) == 2
    assert not missing.exists()
    assert "does not exist" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# The fifth masking: numbers this round CAPTURED.
#
# Found in use, not in review. A real LinkedIn card in the 2026-09-02 medical
# imaging round is titled "AI AI/ML Engineer (100 % remote) (m/f/d)". discover
# renders row titles exactly as captured, and this lint bans "%" from
# shortlist.md, so the two rules contradicted each other and the artifact that
# failed was the honest one. There is no wording that fixes it: the "%" is the
# employer's.
#
# The masking is a lookup against the captures, so the tests that matter are the
# ones that show it DISCRIMINATING -- exempting the quotation while still firing
# on a number the model made up, and on a number reused away from its neighbours.
# ---------------------------------------------------------------------------
import json as _json

import lint_no_prediction as lnp
from findings import codes


def _out(found: list) -> str:
    """scan_text returns lines; the code assertions take the joined output."""
    return "\n".join(found)


def _round(tmp_path, card_title="AI AI/ML Engineer (100 % remote) (m/f/d)"):
    ws = tmp_path / "job-profiles" / "tester" / "searches" / "r"
    (ws / "raw").mkdir(parents=True)
    (ws / "raw" / "linkedin-1.json").write_text(
        _json.dumps([{"title": card_title, "company": "EWOR",
                      "url": "https://example.invalid/1"}]),
        encoding="utf-8")
    return ws


def test_a_percentage_inside_a_captured_job_title_is_not_a_finding(tmp_path):
    ws = _round(tmp_path)
    corpus = lnp.capture_corpus(ws)
    line = "### 3. AI AI/ML Engineer (100 % remote) (m/f/d) — EWOR"
    assert lnp.scan_text(line, "shortlist.md", corpus) == []


def test_the_same_line_is_a_finding_without_the_capture_behind_it(tmp_path):
    """The exemption must come from the capture, not from the shape of the line.

    Without this pair the masking could be blanking every '%' it sees and both
    the fix and its test would still look right.
    """
    line = "### 3. AI AI/ML Engineer (100 % remote) (m/f/d) — EWOR"
    assert codes(_out(lnp.scan_text(line, "shortlist.md", ""))) == {"PERCENT"}


def test_a_number_reused_away_from_its_captured_neighbours_still_fires(tmp_path):
    """The narrowing that keeps this from being an off switch.

    The card contains "100 %". Quoting it is reporting; writing "100 % chance of
    an interview" is the invented number this whole lint exists to stop, and the
    digits being present somewhere in the capture must not launder it.
    """
    ws = _round(tmp_path)
    corpus = lnp.capture_corpus(ws)
    line = "- 这一行有 100 % 的把握过筛"
    assert "PERCENT" in codes(_out(lnp.scan_text(line, "shortlist.md", corpus)))


def test_an_invented_number_absent_from_the_capture_still_fires(tmp_path):
    ws = _round(tmp_path)
    corpus = lnp.capture_corpus(ws)
    line = "- 匹配度 87 % ，建议投递"
    assert "PERCENT" in codes(_out(lnp.scan_text(line, "shortlist.md", corpus)))


def test_the_corpus_is_built_from_captures_and_not_from_authored_files(tmp_path):
    """The property that stops the masking becoming self-authorising.

    shortlist.yaml and shortlist.md are written by the model. If either fed the
    corpus, writing the number into one would exempt it from the other, and this
    gate would check that the model agrees with itself.
    """
    ws = _round(tmp_path)
    (ws / "shortlist.yaml").write_text(
        "rows:\n  - raw_text: 'match 93 % likely'\n", encoding="utf-8")
    (ws / "shortlist.md").write_text("match 93 % likely\n", encoding="utf-8")
    corpus = lnp.capture_corpus(ws)
    assert "93" not in corpus
    assert "PERCENT" in codes(_out(lnp.scan_text("match 93 % likely", "x", corpus)))


def test_a_posting_source_capture_also_exempts_its_own_wording(tmp_path):
    """assess/apply have the same conflict: a posting that says "20% travel"
    cannot be quoted in fit-assessment.md without this masking."""
    ws = tmp_path / "job-profiles" / "tester" / "applications" / "a"
    ws.mkdir(parents=True)
    (ws / "posting-source.txt").write_text(
        "The role involves 20% travel to客户现场.", encoding="utf-8")
    corpus = lnp.capture_corpus(ws)
    assert lnp.scan_text("The role involves 20% travel to客户现场.",
                         "fit-assessment.md", corpus) == []


def test_an_unreadable_capture_fails_closed(tmp_path):
    """A corpus that cannot be built must remove nothing, never everything."""
    ws = _round(tmp_path)
    (ws / "raw" / "broken.json").write_text("{not json", encoding="utf-8")
    corpus = lnp.capture_corpus(ws)
    assert "PERCENT" in codes(_out(lnp.scan_text("匹配 55 %", "x", corpus)))


def test_a_prediction_word_in_the_capture_is_not_exempted_by_it(tmp_path):
    """The narrowing that keeps this masking about NUMBERS.

    Mutation-found: deleting the `_NUMERIC_TOKEN` filter left every test green
    while widening the exemption to any token the capture contains -- so a
    posting that happens to use the word "chances" would authorise the model to
    write it about the candidate. A number in the capture is the employer's fact
    and quoting it is reporting; the judgement vocabulary is never the
    employer's to lend.
    """
    ws = tmp_path / "job-profiles" / "tester" / "applications" / "a"
    ws.mkdir(parents=True)
    (ws / "posting-source.txt").write_text(
        "Boost your chances of success in this role.", encoding="utf-8")
    corpus = lnp.capture_corpus(ws)
    found = lnp.scan_text("Boost your chances of success in this role.",
                          "fit-assessment.md", corpus)
    assert "PREDICTION_WORD" in codes(_out(found))
