import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_letter
import journal

POSTING = {"company": "Acme Medical Systems B.V.",
           "role_title": "Senior Reconstruction Engineer",
           "must_haves": ["MRI reconstruction"]}

PARA = ("I have spent four years building GPU reconstruction pipelines for clinical "
        "MRI, and the work your team published on motion-resolved cine recon is the "
        "closest thing I have seen to the problem I want to keep solving. At Acme I "
        "rebuilt the solver that cut a twelve-minute scan to seven, working directly "
        "with radiographers to keep the protocol changes clinically safe and "
        "auditable across three hospital sites. ")


# PARA is 67 words (measured). The default body is FOUR paragraphs — 277 words,
# inside both the 250–400 word band and the 3–4 paragraph band. Three paragraphs
# would be 210 words, which trips the gate's own floor: every "passes silently"
# test would then fail, and the fixture would be teaching the reader that this
# gate cries wolf.
#
# The salutation and closing are ENGLISH because the body is. This fixture used
# to open "Geachte heer/mevrouw," and sign off "Met vriendelijke groet," around
# English paragraphs and was called well-formed — the mixed-language letter
# motivation-letter.md forbids, which the gate now reports.
def _letter(body=None, **over):
    d = {"sender": {"name": "Test User", "email": "t@x.com", "location": "Delft"},
         "recipient": {"name": "Hiring Team", "company": "Acme Medical Systems B.V.",
                       "location": "Eindhoven"},
         "date": "2026-08-09",
         "salutation": "Dear Hiring Team,",
         "body": body if body is not None else [
             PARA + "I am applying for the Senior Reconstruction Engineer role.",
             PARA, PARA, PARA],
         "closing": "Kind regards,"}
    d.update(over)
    return d


def _ws(tmp_path, letter, posting=POSTING):
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "letter.yaml").write_text(yaml.safe_dump(letter, allow_unicode=True),
                                    encoding="utf-8")
    if posting is not None:
        (ws / "posting.yaml").write_text(yaml.safe_dump(posting, allow_unicode=True),
                                         encoding="utf-8")
    return ws


def test_a_well_formed_letter_passes_silently(tmp_path, capsys):
    ws = _ws(tmp_path, _letter())
    assert check_letter.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_markdown_in_a_body_string_is_caught(tmp_path, capsys):
    """render_letter passes body strings through untouched, so '**bold**' prints
    four asterisks on the PDF."""
    body = _letter()["body"]
    body[1] = "I **rebuilt** the solver. " + PARA
    ws = _ws(tmp_path, _letter(body=body))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "MARKDOWN_IN_BODY: body[1]" in out and "**" in out


def test_a_bulleted_body_paragraph_is_caught(tmp_path, capsys):
    body = _letter()["body"]
    body[2] = "- MRI reconstruction\n- GPU solvers\n" + PARA   # stays in the word band
    ws = _ws(tmp_path, _letter(body=body))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "MARKDOWN_IN_BODY: body[2]" in out
    assert "WORD_COUNT" not in out and "PARA_COUNT" not in out


def test_word_count_below_the_floor_is_caught(tmp_path, capsys):
    ws = _ws(tmp_path, _letter(body=["Short.", "Also short.", "Still short."]))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "WORD_COUNT" in out and "250" in out and "400" in out


def test_word_count_above_the_ceiling_is_caught(tmp_path, capsys):
    ws = _ws(tmp_path, _letter(body=[PARA * 3, PARA * 3, PARA * 3]))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    assert "WORD_COUNT" in capsys.readouterr().out


def test_paragraph_count_outside_three_to_four_is_caught(tmp_path, capsys):
    """`motivation-letter.md:121`: "3–4 paragraphs total. Never a single
    monolithic block. Never more than 4 unless a specific structure requires it
    (rare)." A gate that silently permitted 5 would be enforcing a rule the
    reference does not contain."""
    ws = _ws(tmp_path, _letter(body=[PARA * 2, PARA * 2]))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    assert "PARA_COUNT" in capsys.readouterr().out
    ws = _ws(tmp_path / "five", _letter(body=[PARA] * 5))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "PARA_COUNT" in out and "5 paragraphs" in out


def test_sender_name_in_the_closing_prints_twice(tmp_path, capsys):
    """render_letter appends sender.name after the closing automatically."""
    ws = _ws(tmp_path, _letter(closing="Kind regards,\nTest User"))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "NAME_DUPLICATED" in out and "Test User" in out


def test_a_wrong_company_is_caught(tmp_path, capsys):
    letter = _letter()
    letter["recipient"]["company"] = "Acme Manufacturing"
    ws = _ws(tmp_path, letter)
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "COMPANY_MISMATCH" in out and "Acme Medical Systems B.V." in out


def test_a_shorter_but_matching_company_name_is_accepted(tmp_path, capsys):
    """'Acme Medical Systems' addressed to 'Acme Medical Systems B.V.' is
    correct in a letter; only a genuinely different name is an error."""
    letter = _letter()
    letter["recipient"]["company"] = "Acme Medical Systems"
    ws = _ws(tmp_path, letter)
    assert check_letter.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_letter_that_never_names_the_role_is_caught(tmp_path, capsys):
    ws = _ws(tmp_path, _letter(body=[PARA, PARA, PARA, PARA]))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "ROLE_NOT_NAMED" in out and "Senior Reconstruction Engineer" in out
    assert "WORD_COUNT" not in out and "PARA_COUNT" not in out   # one finding, not three


def test_a_posting_without_a_company_field_fails_loudly(tmp_path, capsys):
    ws = _ws(tmp_path, _letter(), posting={"role_title": "Senior Reconstruction Engineer"})
    assert check_letter.main(["--workspace", str(ws)]) == 1
    assert "NO_COMPANY_IN_POSTING" in capsys.readouterr().out


def test_a_missing_posting_is_exit_2(tmp_path, capsys):
    ws = _ws(tmp_path, _letter(), posting=None)
    assert check_letter.main(["--workspace", str(ws)]) == 2
    assert "posting.yaml" in capsys.readouterr().err


def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_path(tmp_path):
    ws = _ws(tmp_path, _letter())
    check_letter.main(["--workspace", str(ws)])
    (ws / "posting.yaml").unlink()
    assert check_letter.main(["--workspace", str(ws)]) == 2
    assert [r["verdict"] for r in journal.read_receipts(ws, "check_letter")] == \
        ["pass", "could_not_run"]


# ---------------------------------------------------------------------------
# `250-350 words` is a rule about ENGLISH words and `len(split())` is a rule
# about spaces. Chinese and Japanese have neither, so a 306-character Chinese
# letter counted as "3 words" and failed WORD_COUNT — a gate that could never
# be satisfied in those languages, which is a gate people route around.
#
# The band is NOT rescaled: this skill has no sourced length convention for a
# CJK letter, and inventing one is the fabrication it bans everywhere else.
# ---------------------------------------------------------------------------

_ZH_PARA = "我在莱顿大学医学中心从事心脏磁共振重建的博士研究，专注于从高度欠采样的数据中恢复高质量图像。"
_ZH_LETTER = {"body": [_ZH_PARA, _ZH_PARA + "另外我熟悉容器化部署。",
                       _ZH_PARA + "期待与贵司交流。"],
              "recipient": {"company": "阿里巴巴"}}
_ZH_POSTING = {"company": "阿里巴巴", "role_title": "算法工程师"}


def test_a_chinese_letter_does_not_fail_an_english_word_count():
    out = check_letter.findings_for(_ZH_LETTER, _ZH_POSTING)
    assert not any(f.startswith("WORD_COUNT:") for f in out), out


def test_a_chinese_letter_reports_its_real_length_as_a_notice():
    notices = check_letter.notices_for(_ZH_LETTER)
    assert len(notices) == 1
    assert notices[0].startswith("NOTICE_CJK_LENGTH_UNSCORED")
    assert "characters" in notices[0]


def test_an_english_letter_is_still_scored_and_notices_nothing():
    """The twin. The whole band still applies where the unit is a word."""
    short = {"body": ["Too short."] * 3, "recipient": {"company": "Acme"}}
    out = check_letter.findings_for(short, {"company": "Acme", "role_title": "x"})
    assert any(f.startswith("WORD_COUNT:") for f in out), out
    assert check_letter.notices_for(short) == []


def test_dominance_is_a_ratio_not_a_trigger_on_any_cjk_character():
    """An English letter naming one Chinese employer is an English letter."""
    body = ["word " * 100, "word " * 100, "word " * 100 + "at 阿里巴巴."]
    assert not check_letter.cjk_dominant(" ".join(body))
    assert check_letter.cjk_dominant("我在莱顿大学医学中心从事研究 with Python")


# ---------------------------------------------------------------------------
# render_letter used to print `Dear Hiring Manager,` / `Sincerely,` on every
# letter regardless of language, against motivation-letter.md:272 — "Never mix
# languages in one letter" — in the renderer that file drives. Those defaults
# are gone for languages the skill cannot source, so the gate is what stops a
# letter shipping with no opener at all.
# ---------------------------------------------------------------------------

def _lang_letter(lang, **kw):
    d = {"meta": {"language": lang}, "body": ["Genoeg tekst hier."],
         "recipient": {"company": "Acme"}}
    d.update(kw)
    return d


@pytest.mark.parametrize("lang,codes", [
    # No sourced opener AND no sourced sign-off: the skill has nothing to offer
    # and says so rather than inventing either.
    ("zh", {"NO_SALUTATION", "NO_CLOSING"}),
    ("ja", {"NO_SALUTATION", "NO_CLOSING"}),
    ("pl", {"NO_SALUTATION", "NO_CLOSING"}),
    # Both halves sourced. `de` and `nl` used to report NO_CLOSING here, which
    # an independent pass called out as an asymmetry: five languages had a
    # localized opener and were then given an English sign-off or none at all.
    # references/motivation-letter.md now carries the closings too.
    ("de", set()),
    ("nl", set()),
    ("fr", set()),
    ("en", set()),
])
def test_a_missing_line_the_skill_cannot_source_is_reported(lang, codes):
    out = check_letter.findings_for(_lang_letter(lang), {"company": "Acme",
                                                    "role_title": "r"})
    got = {f.split(":")[0] for f in out if f.startswith("NO_")}
    assert got == codes, out


def test_writing_the_lines_silences_it():
    """The twin: this must be satisfiable by writing the letter properly, or it
    is a gate that fails every CJK letter forever."""
    out = check_letter.findings_for(
        _lang_letter("zh", salutation="尊敬的招聘团队：", closing="此致敬礼"),
        {"company": "Acme", "role_title": "r"})
    assert not [f for f in out if f.startswith("NO_")], out


def test_a_declared_cjk_language_beats_the_character_ratio():
    """An independent pass found the ratio flipping on an honest letter: a
    Chinese letter to a multinational keeps team names, levels and tool names in
    English — the ordinary register — and enough of them made a 105-word Chinese
    letter get scored against a 250-word English band it can never meet.

    The candidate declared the language; that is better evidence than counting
    glyphs, so `meta.language` wins and the ratio is only the fallback."""
    body = ["I would like to introduce my background: "
            "在Google Cloud Platform的Distributed Systems and Storage "
            "Infrastructure团队负责存储基础设施的设计与实现。"] * 3
    letter = {"meta": {"language": "zh"}, "body": body,
              "recipient": {"company": "A"},
              "salutation": "尊敬的招聘团队：", "closing": "此致敬礼"}
    assert check_letter.cjk_dominant(" ".join(body), "zh")
    out = check_letter.findings_for(letter, {"company": "A", "role_title": "r"})
    assert not any(f.startswith("WORD_COUNT") for f in out), out
    assert check_letter.notices_for(letter)


def test_an_english_letter_is_still_measured_in_words():
    """The twin: `meta.language` must not become a way to switch the band off."""
    letter = {"meta": {"language": "en"}, "body": ["Too short."] * 3,
              "recipient": {"company": "A"}}
    out = check_letter.findings_for(letter, {"company": "A", "role_title": "r"})
    assert any(f.startswith("WORD_COUNT") for f in out), out


# ---------------------------------------------------------------------------
# A letter written to the schema motivation-letter.md §4 documents has no `meta`,
# and this gate read meta.language with "en" as the default — so a Chinese letter
# with no salutation or closing was told "Dear Hiring Team," covered it, rendered
# with English furniture, and PASSED.
# ---------------------------------------------------------------------------

_ZH_DOCUMENTED = {
    "sender": {"name": "张伟", "email": "zhangwei@example.com", "location": "上海"},
    "recipient": {"name": "招聘团队", "company": "阿里巴巴", "location": "杭州"},
    "date": "2026-10-24",
    "body": ["您好，我希望应聘推荐算法工程师一职。我在推荐系统方向有五年经验，负责过召回模块的重构。",
             "在上一份工作中，我主导了分布式训练框架的迁移，训练时长明显缩短。",
             "期待有机会进一步交流。"]}
_ZH_DOCUMENTED_POSTING = {"company": "阿里巴巴", "role_title": "推荐算法工程师"}


def test_a_chinese_letter_with_no_meta_and_no_lines_fails(tmp_path, capsys):
    ws = _ws(tmp_path, _ZH_DOCUMENTED, posting=_ZH_DOCUMENTED_POSTING)
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "NO_SALUTATION" in out and "NO_CLOSING" in out and "'zh'" in out


def test_the_same_letter_with_its_own_lines_passes(tmp_path, capsys):
    """The twin: writing the lines in the letter's language is the whole fix."""
    letter = dict(_ZH_DOCUMENTED, salutation="尊敬的招聘团队：", closing="此致敬礼")
    ws = _ws(tmp_path, letter, posting=_ZH_DOCUMENTED_POSTING)
    assert check_letter.main(["--workspace", str(ws)]) == 0, capsys.readouterr().out


@pytest.mark.parametrize("meta", [None, {"language": "en"}])
def test_an_english_salutation_and_closing_on_a_chinese_body_are_reported(meta):
    """Written out explicitly, or the renderer's English default because
    meta.language says en: either way the body is Chinese."""
    letter = dict(_ZH_DOCUMENTED, salutation="Dear Hiring Team,", closing="Sincerely,")
    if meta:
        letter["meta"] = meta
    out = check_letter.findings_for(letter, _ZH_DOCUMENTED_POSTING)
    codes = {f.split(":")[0] for f in out}
    assert {"SALUTATION_LANGUAGE_MISMATCH", "CLOSING_LANGUAGE_MISMATCH"} <= codes, out
    assert any("Chinese (zh)" in f for f in out)


def test_a_renderer_default_in_the_wrong_language_says_where_it_came_from():
    letter = dict(_ZH_DOCUMENTED, meta={"language": "en"})
    out = [f for f in check_letter.findings_for(letter, _ZH_DOCUMENTED_POSTING)
           if f.startswith("SALUTATION_LANGUAGE_MISMATCH")]
    assert out and "render_letter's default" in out[0] and "meta.language" in out[0]


def test_a_dutch_opener_on_an_english_body_is_reported():
    out = check_letter.findings_for(
        _letter(salutation="Geachte heer/mevrouw,", closing="Met vriendelijke groet,"),
        POSTING)
    assert any(f.startswith("SALUTATION_LANGUAGE_MISMATCH") and "Dutch (nl)" in f
               and "English (en)" in f for f in out), out
    assert any(f.startswith("CLOSING_LANGUAGE_MISMATCH") for f in out), out


@pytest.mark.parametrize("letter", [
    # Same language throughout, in each script.
    _letter(),
    dict(_ZH_DOCUMENTED, salutation="尊敬的招聘团队：", closing="此致敬礼"),
    {"body": [("Ich habe vier Jahre lang Datenpipelines für ein Unternehmen aufgebaut, "
               "und die Arbeit Ihres Teams ist genau das Problem, an dem ich mit Ihnen "
               "weiter arbeiten möchte. ") * 3],
     "salutation": "Sehr geehrte Frau Weber,", "closing": "Mit freundlichen Grüßen"},
    # A Chinese name inside an English salutation is still an English salutation.
    _letter(salutation="Dear 张伟,"),
    # A Chinese letter that keeps its team names in English is a Chinese letter.
    {"meta": {"language": "zh"}, "salutation": "尊敬的招聘团队：", "closing": "此致敬礼",
     "body": ["I would like to introduce my background: 在Google Cloud Platform的"
              "Distributed Systems and Storage Infrastructure团队负责存储基础设施的设计与实现。"]
     * 3},
    # A greeting the gate does not know is not evidence of a mismatch.
    _letter(salutation="Hello there,", closing="Cheers,"),
])
def test_a_letter_in_one_language_has_no_mismatch(letter):
    out = check_letter.findings_for(letter, POSTING)
    assert not [f for f in out if "LANGUAGE_MISMATCH" in f], out


def test_the_gate_reads_the_workspace_profile_as_the_renderer_does(tmp_path, capsys):
    """A Polish letter: the body detector does not know Polish and the tailored
    profile does. The renderer prints no opener for pl; the gate must say so
    rather than judge an English default that is never rendered."""
    letter = {"recipient": {"company": "Acme"},
              "body": ["Przez cztery lata budowałem potoki danych dla firmy."] * 3}
    ws = _ws(tmp_path, letter, posting={"company": "Acme", "role_title": "danych"})
    (ws / "tailored-profile.yaml").write_text(
        yaml.safe_dump({"meta": {"language": "pl", "target_market": "pl"}}),
        encoding="utf-8")
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "NO_SALUTATION" in out and "'pl'" in out


# ---------------------------------------------------------------------------
# "Data Scientist (m/w/d)" is how a German posting writes the title — the gender
# marker is required there, and no letter repeats it. ROLE_NOT_NAMED fired on a
# letter that named "Data Scientist" exactly.
# ---------------------------------------------------------------------------

_DE_PARA = "Ich habe vier Jahre lang Modelle für Kreditrisiken entwickelt und betrieben. "
_DE_LETTER = {"salutation": "Sehr geehrte Damen und Herren,",
              "closing": "Mit freundlichen Grüßen", "recipient": {"company": "Acme GmbH"},
              "body": [_DE_PARA * 7 + "Ich bewerbe mich als Data Scientist bei Acme.",
                       _DE_PARA * 7, _DE_PARA * 7]}


@pytest.mark.parametrize("title", [
    "Data Scientist (m/w/d)", "Data Scientist (w/m/d)", "Data Scientist (f/m/x)",
    "Data Scientist (m/f/d)", "Data Scientist (H/F)", "Data Scientist (m/v)",
    "Data Scientist (all genders)", "Data Scientist m/w/d", "Data Scientist [m/w/div]",
])
def test_a_gender_marker_is_not_part_of_the_role(title):
    out = check_letter.findings_for(_DE_LETTER, {"company": "Acme GmbH",
                                                 "role_title": title})
    assert not [f for f in out if f.startswith("ROLE_NOT_NAMED")], out


def test_the_rest_of_the_title_is_still_required():
    """The twin: only the marker is dropped. A letter that names "Data Scientist"
    has not named "Senior Data Scientist (m/w/d)"."""
    out = check_letter.findings_for(_DE_LETTER, {"company": "Acme GmbH",
                                                 "role_title": "Senior Data Scientist (m/w/d)"})
    assert any(f.startswith("ROLE_NOT_NAMED") and "(m/w/d)" in f for f in out), out
    assert check_letter.role_without_gender_marker("UX/UI Designer (m/w/d)") == "UX/UI Designer"


# ---------------------------------------------------------------------------
# `——` is ONE mark in Chinese (破折号), typed as two U+2014, and was counted as
# two: two ordinary uses read as four and tripped EM_DASH_DENSITY's floor of 3.
# ---------------------------------------------------------------------------

def _zh_with_dashes(n):
    body = ["我希望应聘推荐算法工程师一职——这是我过去五年一直在做的方向。",
            "在上一份工作中，我主导了分布式训练框架的迁移——训练时长明显缩短。",
            "期待有机会进一步交流。"]
    if n == 3:
        body[2] = "期待有机会进一步交流——无论结果如何。"
    return {"meta": {"language": "zh"}, "salutation": "尊敬的招聘团队：",
            "closing": "此致敬礼", "recipient": {"company": "阿里巴巴"}, "body": body}


def test_a_chinese_double_dash_counts_as_one_mark():
    out = check_letter.findings_for(_zh_with_dashes(2), _ZH_DOCUMENTED_POSTING)
    assert not [f for f in out if f.startswith("EM_DASH_DENSITY")], out


def test_three_chinese_dashes_are_still_three():
    """The twin: the mark is counted once, not ignored."""
    out = check_letter.findings_for(_zh_with_dashes(3), _ZH_DOCUMENTED_POSTING)
    assert any(f.startswith("EM_DASH_DENSITY") and ": 3 em dashes" in f for f in out), out


# A real-length Chinese letter: about 300 characters and three ordinary 破折号.
# Counted as words, each run of Han between two punctuation marks was ONE word,
# so the body measured 22 "words" and three marks read as 13.6 per 100 — the
# same three dashes in a 300-word English letter are 1.0 and pass.
_ZH_REAL_LENGTH = {
    "meta": {"language": "zh"}, "salutation": "尊敬的招聘团队：", "closing": "此致敬礼",
    "recipient": {"company": "阿里巴巴"},
    "body": ["您好，我希望应聘推荐算法工程师一职——这是我过去五年一直在做的方向。"
             "我在推荐系统方向负责过召回模块的重构，也参与过排序模型的迭代。",
             "在上一份工作中，我主导了分布式训练框架的迁移——训练时长从十二小时缩短到七小时，"
             "同时保证了线上效果稳定。之后我又负责了特征平台的建设，把新特征上线的周期"
             "从两周缩短到三天，并和数据团队一起建立了离线评估与线上实验的对照流程。",
             "我希望把这些经验带到贵司的推荐团队——尤其是冷启动和长尾内容分发这两个方向。"
             "期待有机会进一步交流，也愿意在面试中详细介绍相关项目的设计与取舍。"]}


def test_three_dashes_in_a_real_length_chinese_letter_are_ordinary():
    out = check_letter.findings_for(_ZH_REAL_LENGTH, _ZH_DOCUMENTED_POSTING)
    assert not [f for f in out if f.startswith("EM_DASH_DENSITY")], out


# ---------------------------------------------------------------------------
# The receipt names what the verdict read. With no meta.language and a body the
# detector cannot place, the language — and with it NO_SALUTATION / NO_CLOSING —
# comes from tailored-profile.yaml. The receipt hashed letter.yaml and
# posting.yaml only, so check_apply's STALE_RECEIPT could not see a profile edit
# that turned this gate's pass into a fail.
# ---------------------------------------------------------------------------

# 288 words in three paragraphs, so the English word band is met when the
# profile says `en`; the body detector does not know Polish.
_PL_LETTER = {"recipient": {"company": "Acme"},
              "body": ["Przez cztery lata budowałem potoki danych dla firmy. " * 12] * 3}
_PL_POSTING = {"company": "Acme", "role_title": "danych"}


def _profile(ws, language):
    (ws / "tailored-profile.yaml").write_text(
        yaml.safe_dump({"meta": {"language": language, "target_market": "pl"}}),
        encoding="utf-8")


def test_a_profile_that_decides_the_language_is_in_the_receipt(tmp_path):
    import check_apply
    ws = _ws(tmp_path, _PL_LETTER, posting=_PL_POSTING)
    _profile(ws, "en")      # English defaults cover the letter: the gate passes
    assert check_letter.main(["--workspace", str(ws)]) == 0
    receipt = journal.read_receipts(ws, "check_letter")[-1]
    assert receipt["input_hashes"].get("tailored-profile.yaml") == \
        journal.sha256_file(ws / "tailored-profile.yaml"), receipt["input_hashes"]
    _profile(ws, "pl")      # the same letter now has no sourced salutation
    stale = check_apply._stale_inputs(ws, "check_letter", receipt)
    assert any(f.startswith("STALE_RECEIPT") and "tailored-profile.yaml" in f
               for f in stale), stale
    assert check_letter.main(["--workspace", str(ws)]) == 1


def test_a_profile_the_letter_never_consults_stays_out_of_the_receipt(tmp_path):
    """The twin: a letter that settles its own language does not read the
    profile, so a CV edit must not stale the letter's pass."""
    ws = _ws(tmp_path, _letter())
    _profile(ws, "de")
    assert check_letter.main(["--workspace", str(ws)]) == 0
    hashes = journal.read_receipts(ws, "check_letter")[-1]["input_hashes"]
    assert set(hashes) == {"letter.yaml", "posting.yaml"}, hashes
    declared = dict(_PL_LETTER, meta={"language": "pl"})
    ws = _ws(tmp_path / "declared", declared, posting=_PL_POSTING)
    _profile(ws, "en")
    check_letter.main(["--workspace", str(ws)])
    hashes = journal.read_receipts(ws, "check_letter")[-1]["input_hashes"]
    assert "tailored-profile.yaml" not in hashes, hashes


def test_a_profile_without_meta_is_bound_with_the_one_that_decided(tmp_path):
    """render_letter falls through tailored-profile.yaml to profile.yaml when the
    first has no meta, so giving the first a meta later changes the language:
    both are inputs."""
    ws = _ws(tmp_path, _PL_LETTER, posting=_PL_POSTING)
    (ws / "tailored-profile.yaml").write_text("skills: [Python]\n", encoding="utf-8")
    (ws / "profile.yaml").write_text(yaml.safe_dump({"meta": {"language": "pl"}}),
                                     encoding="utf-8")
    assert check_letter.main(["--workspace", str(ws)]) == 1
    hashes = journal.read_receipts(ws, "check_letter")[-1]["input_hashes"]
    assert {"tailored-profile.yaml", "profile.yaml"} <= set(hashes), hashes
