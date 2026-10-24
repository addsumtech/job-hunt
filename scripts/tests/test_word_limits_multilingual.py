import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_word_limits


def test_korean_declared_character_limit_rejects_one_character_over():
    at_limit = "### 경험 (20자 이내)\n" + "가" * 20
    over = "### 경험 (20자 이내)\n" + "가" * 21
    posting = {"application_type": "structured"}
    assert not any("WORD_LIMIT" in f for f in check_word_limits.findings_for(at_limit, posting))
    assert check_word_limits.sections(over)[0][2] == 21
    assert check_word_limits.findings_for(over, posting)


def test_mixed_words_are_not_lost_beside_cjk():
    assert check_word_limits._words("Python경험 SQL 技术") == 6
    assert check_word_limits._words("Python SQL experience") == 3


@pytest.mark.parametrize("heading,expected", [
    ("动机（1,000字以内）", 1000),
    ("研究计划（不超过1000字）", 1000),
    ("研究计划（不超过2,000字）", 2000),
    ("动机（１，０００字以内）", 1000),
    ("志望動機（800字程度）", 800),
    ("志望動機（1,200文字以内）", 1200),
    ("자기소개 (1,000자 이내)", 1000),
    ("지원동기 (최대 1,500자)", 1500),
])
def test_a_cjk_character_limit_with_a_separator_is_read_whole(heading, expected):
    """`(1,000자 이내)` was a limit of 0: every Korean answer reported over it."""
    assert check_word_limits.sections(f"### {heading}\n가\n")[0][1] == expected


def test_a_chinese_answer_under_a_comma_grouped_cap_passes():
    text = "### 研究计划（不超过2,000字）\n" + "我负责该项目的交付与验收。" * 100 + "\n"
    assert check_word_limits.sections(text)[0][2] == 1200
    assert check_word_limits.findings_for(text, {"application_type": "structured"}) == []
